"""
Phase 4: AI 학습 시스템 - 데이터 전처리 시스템

실제 API에서 수집한 데이터를 AI 학습에 적합한 형태로 전처리
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from core.utils.log_utils import get_logger
from core.api.kis_api import KISAPI
from core.learning.features.feature_selector import FeatureSelector

logger = get_logger(__name__)

@dataclass
class PreprocessedData:
    """전처리된 데이터 클래스"""
    features: np.ndarray  # 피처 데이터 (N x 17)
    labels: np.ndarray    # 라벨 데이터 (N,) - 성과 (0: 손실, 1: 수익)
    feature_names: List[str]  # 피처 이름들
    stock_codes: List[str]    # 종목 코드들
    dates: List[str]          # 날짜들
    metadata: Dict[str, Any]  # 메타데이터

class RealDataPreprocessor:
    """실제 API 데이터 전처리기"""
    
    def __init__(self):
        """초기화"""
        self._logger = logger
        self._api_client = KISAPI()
        self._feature_selector = FeatureSelector()
        
        # 전처리 설정
        self._min_price = 1000  # 최소 주가 (단위: 원)
        self._max_price = 1000000  # 최대 주가
        self._min_volume = 1000  # 최소 거래량
        self._missing_threshold = 0.1  # 결측치 허용 비율
        
        self._logger.info("RealDataPreprocessor 초기화 완료")
    
    def collect_and_preprocess_stock_data(self, stock_codes: List[str], 
                                        period_days: int = 100) -> Optional[PreprocessedData]:
        """주식 데이터 수집 및 전처리
        
        Args:
            stock_codes: 종목 코드 리스트
            period_days: 수집 기간 (일)
            
        Returns:
            Optional[PreprocessedData]: 전처리된 데이터
        """
        try:
            self._logger.info(f"실제 데이터 수집 및 전처리 시작: {len(stock_codes)}개 종목")
            
            all_features = []
            all_labels = []
            valid_stock_codes = []
            valid_dates = []
            
            for stock_code in stock_codes:
                # 1. 실제 주가 데이터 수집
                ohlcv_data = self._api_client.get_daily_chart(stock_code, period_days)
                
                if ohlcv_data is None or len(ohlcv_data) < 70:
                    self._logger.warning(f"데이터 부족으로 스킵: {stock_code}")
                    continue
                
                # 2. 데이터 품질 검증
                if not self._validate_data_quality(ohlcv_data, stock_code):
                    continue
                
                # 3. 주식 정보 수집
                stock_info = self._api_client.get_stock_info(stock_code)
                if not stock_info:
                    self._logger.warning(f"종목 정보 부족으로 스킵: {stock_code}")
                    continue
                
                # 4. 피처 추출용 데이터 구성
                stock_data = {
                    'stock_code': stock_code,
                    'current_price': stock_info['current_price'],
                    'volume_ratio': self._calculate_volume_ratio(ohlcv_data),
                    'ohlcv_data': ohlcv_data
                }
                
                # 5. 피처 추출
                features = self._feature_selector.extract_all_features_from_stock_data(stock_data)
                feature_array = features.to_array()
                
                # 6. 라벨 생성 (향후 7일 수익률 기준)
                label = self._generate_performance_label(ohlcv_data)
                
                # 7. 데이터 추가
                all_features.append(feature_array)
                all_labels.append(label)
                valid_stock_codes.append(stock_code)
                valid_dates.append(pd.Timestamp(ohlcv_data.index[-1]).strftime('%Y-%m-%d'))
                
                self._logger.debug(f"데이터 처리 완료: {stock_code}")
            
            if not all_features:
                self._logger.error("처리된 데이터가 없습니다")
                return None
            
            # 8. 배열 변환 및 정규화
            features_array = np.array(all_features)
            labels_array = np.array(all_labels)
            
            # 9. 최종 전처리
            features_processed = self._normalize_features(features_array)
            
            # 10. 결과 구성
            preprocessed_data = PreprocessedData(
                features=features_processed,
                labels=labels_array,
                feature_names=self._feature_selector.get_feature_summary()['slope_features']['names'] + 
                             self._feature_selector.get_feature_summary()['volume_features']['names'],
                stock_codes=valid_stock_codes,
                dates=valid_dates,
                metadata={
                    'total_stocks': len(stock_codes),
                    'valid_stocks': len(valid_stock_codes),
                    'period_days': period_days,
                    'preprocessing_timestamp': datetime.now().isoformat(),
                    'success_rate': len(valid_stock_codes) / len(stock_codes) * 100
                }
            )
            
            self._logger.info(f"실제 데이터 전처리 완료: {len(valid_stock_codes)}/{len(stock_codes)}개 종목 성공")
            return preprocessed_data
            
        except Exception as e:
            self._logger.error(f"실제 데이터 전처리 오류: {e}")
            return None
    
    def _validate_data_quality(self, ohlcv_data: pd.DataFrame, stock_code: str) -> bool:
        """데이터 품질 검증
        
        Args:
            ohlcv_data: OHLCV 데이터
            stock_code: 종목 코드
            
        Returns:
            bool: 품질 검증 통과 여부
        """
        try:
            # 1. 기본 데이터 검증
            if ohlcv_data.empty or len(ohlcv_data) < 70:
                self._logger.warning(f"데이터 길이 부족: {stock_code} - {len(ohlcv_data)}일")
                return False
            
            # 2. 가격 범위 검증
            current_price = ohlcv_data['close'].iloc[-1]
            if current_price < self._min_price or current_price > self._max_price:
                self._logger.warning(f"가격 범위 이상: {stock_code} - {current_price}원")
                return False
            
            # 3. 거래량 검증
            avg_volume = ohlcv_data['volume'].mean()
            if avg_volume < self._min_volume:
                self._logger.warning(f"거래량 부족: {stock_code} - {avg_volume}")
                return False
            
            # 4. 결측치 검증
            missing_ratio = ohlcv_data.isnull().sum().sum() / (len(ohlcv_data) * len(ohlcv_data.columns))
            if missing_ratio > self._missing_threshold:
                self._logger.warning(f"결측치 과다: {stock_code} - {missing_ratio:.2%}")
                return False
            
            # 5. 이상값 검증 (가격 변동률 체크)
            price_changes = ohlcv_data['close'].pct_change().abs()
            extreme_changes = (price_changes > 0.30).sum()  # 30% 이상 변동
            if extreme_changes > 5:  # 5일 이상
                self._logger.warning(f"극단적 가격 변동 과다: {stock_code}")
                return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"데이터 품질 검증 오류: {e}")
            return False
    
    def _calculate_volume_ratio(self, ohlcv_data: pd.DataFrame) -> float:
        """거래량 비율 계산
        
        Args:
            ohlcv_data: OHLCV 데이터
            
        Returns:
            float: 최근 거래량 비율
        """
        try:
            recent_volume = ohlcv_data['volume'].tail(5).mean()
            avg_volume = ohlcv_data['volume'].mean()
            
            return recent_volume / avg_volume if avg_volume > 0 else 1.0
            
        except Exception as e:
            self._logger.error(f"거래량 비율 계산 오류: {e}")
            return 1.0
    
    def _generate_performance_label(self, ohlcv_data: pd.DataFrame) -> int:
        """성과 라벨 생성 (향후 7일 수익률 기준)
        
        Args:
            ohlcv_data: OHLCV 데이터
            
        Returns:
            int: 라벨 (0: 손실, 1: 수익)
        """
        try:
            # 실제 환경에서는 미래 데이터를 알 수 없으므로
            # 여기서는 과거 데이터를 기반으로 시뮬레이션
            
            if len(ohlcv_data) < 7:
                return 0
            
            # 현재가 기준 7일 전 가격과 비교
            current_price = ohlcv_data['close'].iloc[-1]
            past_price = ohlcv_data['close'].iloc[-7]
            
            return_rate = (current_price - past_price) / past_price
            
            # 5% 이상 수익 시 1, 그렇지 않으면 0
            return 1 if return_rate > 0.05 else 0
            
        except Exception as e:
            self._logger.error(f"성과 라벨 생성 오류: {e}")
            return 0
    
    def _normalize_features(self, features: np.ndarray) -> np.ndarray:
        """피처 정규화
        
        Args:
            features: 피처 배열 (N x 17)
            
        Returns:
            np.ndarray: 정규화된 피처 배열
        """
        try:
            from sklearn.preprocessing import StandardScaler
            
            scaler = StandardScaler()
            normalized_features = scaler.fit_transform(features)
            
            self._logger.debug(f"피처 정규화 완료: {features.shape}")
            return normalized_features
            
        except ImportError:
            self._logger.warning("sklearn 미설치로 정규화 스킵")
            return features
        except Exception as e:
            self._logger.error(f"피처 정규화 오류: {e}")
            return features
    
    def save_preprocessed_data(self, data: PreprocessedData, filepath: str) -> bool:
        """전처리된 데이터 저장
        
        Args:
            data: 전처리된 데이터
            filepath: 저장 경로
            
        Returns:
            bool: 저장 성공 여부
        """
        try:
            save_data = {
                'features': data.features.tolist(),
                'labels': data.labels.tolist(),
                'feature_names': data.feature_names,
                'stock_codes': data.stock_codes,
                'dates': data.dates,
                'metadata': data.metadata
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"전처리된 데이터 저장 완료: {filepath}")
            return True
            
        except Exception as e:
            self._logger.error(f"데이터 저장 오류: {e}")
            return False
    
    def load_preprocessed_data(self, filepath: str) -> Optional[PreprocessedData]:
        """전처리된 데이터 로드
        
        Args:
            filepath: 데이터 파일 경로
            
        Returns:
            Optional[PreprocessedData]: 로드된 데이터
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
            
            return PreprocessedData(
                features=np.array(save_data['features']),
                labels=np.array(save_data['labels']),
                feature_names=save_data['feature_names'],
                stock_codes=save_data['stock_codes'],
                dates=save_data['dates'],
                metadata=save_data['metadata']
            )
            
        except Exception as e:
            self._logger.error(f"데이터 로드 오류: {e}")
            return None
    
    def get_preprocessing_stats(self, data: PreprocessedData) -> Dict[str, Any]:
        """전처리 통계 정보 반환
        
        Args:
            data: 전처리된 데이터
            
        Returns:
            Dict[str, Any]: 통계 정보
        """
        try:
            features_mean = np.mean(data.features, axis=0)
            features_std = np.std(data.features, axis=0)
            
            return {
                'data_shape': data.features.shape,
                'label_distribution': {
                    'positive': int(np.sum(data.labels)),
                    'negative': int(len(data.labels) - np.sum(data.labels)),
                    'positive_ratio': float(np.mean(data.labels))
                },
                'feature_stats': {
                    'mean': features_mean.tolist(),
                    'std': features_std.tolist(),
                    'feature_names': data.feature_names
                },
                'metadata': data.metadata
            }
            
        except Exception as e:
            self._logger.error(f"통계 정보 생성 오류: {e}")
            return {} 