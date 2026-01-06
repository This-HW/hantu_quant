"""
기업 평가 엔진
- 종합 점수 계산
- 섹터별 비교 분석
- 평가 기준 동적 조정
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from dataclasses import dataclass

from core.utils.log_utils import get_logger

logger = get_logger(__name__)

@dataclass
class EvaluationWeights:
    """평가 가중치 설정"""
    fundamental: float = 0.4    # 재무제표 기반 40%
    technical: float = 0.3      # 기술적 분석 30%
    momentum: float = 0.2       # 모멘텀 분석 20%
    sector: float = 0.1         # 섹터 분석 10%
    
    def validate(self) -> bool:
        """가중치 합계 검증"""
        _v_total = self.fundamental + self.technical + self.momentum + self.sector
        return abs(_v_total - 1.0) < 0.01

@dataclass
class MarketCondition:
    """시장 상황 정보"""
    volatility_index: float     # 변동성 지수
    market_trend: str          # 상승/하락/횡보
    interest_rate: float       # 기준금리
    economic_indicator: str    # 경제지표 상태
    
class EvaluationEngine:
    """기업 평가 엔진 클래스"""
    
    def __init__(self, p_config_file: str = "data/watchlist/evaluation_config.json"):
        """초기화 메서드
        
        Args:
            p_config_file: 평가 설정 파일 경로
        """
        self._v_config_file = p_config_file
        self._v_weights = EvaluationWeights()
        self._v_sector_data = {}
        self._v_market_condition = None
        self._v_evaluation_history = []
        
        # 설정 로드
        self._load_config()
        
        # 섹터 데이터 로드
        self._load_sector_data()
        
        logger.info("EvaluationEngine 초기화 완료")
    
    def calculate_comprehensive_score(self, p_stock_data: Dict) -> Tuple[float, Dict]:
        """종합 점수 계산
        
        Args:
            p_stock_data: 주식 데이터
            
        Returns:
            (종합 점수, 세부 점수 딕셔너리)
        """
        try:
            # 각 영역별 점수 계산
            _v_fundamental_score = self._calculate_fundamental_score(p_stock_data)
            _v_technical_score = self._calculate_technical_score(p_stock_data)
            _v_momentum_score = self._calculate_momentum_score(p_stock_data)
            _v_sector_score = self._calculate_sector_score(p_stock_data)
            
            # 시장 상황 고려한 가중치 조정
            _v_adjusted_weights = self._adjust_weights_for_market()
            
            # 종합 점수 계산
            _v_comprehensive_score = (
                _v_fundamental_score * _v_adjusted_weights.fundamental +
                _v_technical_score * _v_adjusted_weights.technical +
                _v_momentum_score * _v_adjusted_weights.momentum +
                _v_sector_score * _v_adjusted_weights.sector
            )
            
            # 세부 점수 정보
            _v_score_details = {
                "comprehensive_score": round(_v_comprehensive_score, 2),
                "fundamental_score": round(_v_fundamental_score, 2),
                "technical_score": round(_v_technical_score, 2),
                "momentum_score": round(_v_momentum_score, 2),
                "sector_score": round(_v_sector_score, 2),
                "weights_used": {
                    "fundamental": _v_adjusted_weights.fundamental,
                    "technical": _v_adjusted_weights.technical,
                    "momentum": _v_adjusted_weights.momentum,
                    "sector": _v_adjusted_weights.sector
                },
                "evaluation_timestamp": datetime.now().isoformat()
            }
            
            logger.debug(f"종합 점수 계산 완료 - 종목: {p_stock_data.get('stock_code')}, 점수: {_v_comprehensive_score:.2f}")
            
            return _v_comprehensive_score, _v_score_details
            
        except Exception as e:
            logger.error(f"종합 점수 계산 오류: {e}", exc_info=True)
            return 0.0, {}
    
    def _calculate_fundamental_score(self, p_stock_data: Dict) -> float:
        """재무제표 기반 점수 계산
        
        Args:
            p_stock_data: 주식 데이터
            
        Returns:
            재무제표 점수 (0-100)
        """
        try:
            _v_score = 0.0
            _v_max_score = 6.0
            
            # ROE 점수 (0-20점)
            _v_roe = p_stock_data.get("roe", 0.0)
            if _v_roe >= 20:
                _v_score += 1.0
            elif _v_roe >= 15:
                _v_score += 0.8
            elif _v_roe >= 10:
                _v_score += 0.6
            elif _v_roe >= 5:
                _v_score += 0.4
            
            # PER 점수 (업종 평균 대비)
            _v_per = p_stock_data.get("per", 999.0)
            _v_sector_avg_per = self._get_sector_average("per", p_stock_data.get("sector", ""))
            if _v_sector_avg_per > 0:
                _v_per_ratio = _v_per / _v_sector_avg_per
                if _v_per_ratio <= 0.6:
                    _v_score += 1.0
                elif _v_per_ratio <= 0.8:
                    _v_score += 0.8
                elif _v_per_ratio <= 1.0:
                    _v_score += 0.6
                elif _v_per_ratio <= 1.2:
                    _v_score += 0.4
            
            # PBR 점수
            _v_pbr = p_stock_data.get("pbr", 999.0)
            if _v_pbr <= 1.0:
                _v_score += 1.0
            elif _v_pbr <= 1.5:
                _v_score += 0.8
            elif _v_pbr <= 2.0:
                _v_score += 0.6
            elif _v_pbr <= 3.0:
                _v_score += 0.4
            
            # 부채비율 점수
            _v_debt_ratio = p_stock_data.get("debt_ratio", 999.0)
            if _v_debt_ratio <= 50:
                _v_score += 1.0
            elif _v_debt_ratio <= 100:
                _v_score += 0.8
            elif _v_debt_ratio <= 150:
                _v_score += 0.6
            elif _v_debt_ratio <= 200:
                _v_score += 0.4
            
            # 매출성장률 점수
            _v_revenue_growth = p_stock_data.get("revenue_growth", 0.0)
            if _v_revenue_growth >= 20:
                _v_score += 1.0
            elif _v_revenue_growth >= 15:
                _v_score += 0.8
            elif _v_revenue_growth >= 10:
                _v_score += 0.6
            elif _v_revenue_growth >= 5:
                _v_score += 0.4
            
            # 영업이익률 점수
            _v_operating_margin = p_stock_data.get("operating_margin", 0.0)
            if _v_operating_margin >= 15:
                _v_score += 1.0
            elif _v_operating_margin >= 10:
                _v_score += 0.8
            elif _v_operating_margin >= 5:
                _v_score += 0.6
            elif _v_operating_margin >= 2:
                _v_score += 0.4
            
            # 정규화 (0-100점)
            return (_v_score / _v_max_score) * 100.0
            
        except Exception as e:
            logger.error(f"재무제표 점수 계산 오류: {e}", exc_info=True)
            return 0.0
    
    def _calculate_technical_score(self, p_stock_data: Dict) -> float:
        """기술적 분석 점수 계산
        
        Args:
            p_stock_data: 주식 데이터
            
        Returns:
            기술적 분석 점수 (0-100)
        """
        try:
            _v_score = 0.0
            _v_max_score = 5.0
            
            # 이동평균 배열 점수
            _v_current_price = p_stock_data.get("current_price", 0.0)
            _v_ma_20 = p_stock_data.get("ma_20", 0.0)
            _v_ma_60 = p_stock_data.get("ma_60", 0.0)
            _v_ma_120 = p_stock_data.get("ma_120", 0.0)
            
            if _v_current_price > _v_ma_20 > _v_ma_60 > _v_ma_120:
                _v_score += 1.0  # 완벽한 상향 배열
            elif _v_current_price > _v_ma_20 > _v_ma_60:
                _v_score += 0.8  # 단기 상향 배열
            elif _v_current_price > _v_ma_20:
                _v_score += 0.6  # 현재가 > 20일선
            elif _v_current_price > _v_ma_60:
                _v_score += 0.4  # 현재가 > 60일선
            
            # RSI 점수 (적정 구간)
            _v_rsi = p_stock_data.get("rsi", 50.0)
            if 40 <= _v_rsi <= 60:
                _v_score += 1.0  # 중립 구간
            elif 30 <= _v_rsi <= 70:
                _v_score += 0.8  # 적정 구간
            elif 20 <= _v_rsi <= 80:
                _v_score += 0.6  # 주의 구간
            elif 10 <= _v_rsi <= 90:
                _v_score += 0.4  # 위험 구간
            
            # 거래량 점수
            _v_volume_ratio = p_stock_data.get("volume_ratio", 0.0)
            if _v_volume_ratio >= 3.0:
                _v_score += 1.0  # 급증
            elif _v_volume_ratio >= 2.0:
                _v_score += 0.8  # 증가
            elif _v_volume_ratio >= 1.5:
                _v_score += 0.6  # 평균 이상
            elif _v_volume_ratio >= 1.0:
                _v_score += 0.4  # 평균 수준
            
            # 가격 모멘텀 점수
            _v_momentum_1m = p_stock_data.get("price_momentum_1m", 0.0)
            if _v_momentum_1m >= 10:
                _v_score += 1.0
            elif _v_momentum_1m >= 5:
                _v_score += 0.8
            elif _v_momentum_1m >= 0:
                _v_score += 0.6
            elif _v_momentum_1m >= -5:
                _v_score += 0.4
            
            # 변동성 점수 (적정 수준)
            _v_volatility = p_stock_data.get("volatility", 0.0)
            if 0.15 <= _v_volatility <= 0.25:
                _v_score += 1.0  # 적정 변동성
            elif 0.1 <= _v_volatility <= 0.3:
                _v_score += 0.8  # 양호한 변동성
            elif 0.05 <= _v_volatility <= 0.4:
                _v_score += 0.6  # 주의 변동성
            elif _v_volatility <= 0.5:
                _v_score += 0.4  # 높은 변동성
            
            # 정규화 (0-100점)
            return (_v_score / _v_max_score) * 100.0
            
        except Exception as e:
            logger.error(f"기술적 분석 점수 계산 오류: {e}", exc_info=True)
            return 0.0
    
    def _calculate_momentum_score(self, p_stock_data: Dict) -> float:
        """모멘텀 점수 계산
        
        Args:
            p_stock_data: 주식 데이터
            
        Returns:
            모멘텀 점수 (0-100)
        """
        try:
            _v_score = 0.0
            _v_max_score = 4.0
            
            # 상대강도 점수
            _v_relative_strength = p_stock_data.get("relative_strength", 0.0)
            if _v_relative_strength >= 0.2:
                _v_score += 1.0
            elif _v_relative_strength >= 0.1:
                _v_score += 0.8
            elif _v_relative_strength >= 0.0:
                _v_score += 0.6
            elif _v_relative_strength >= -0.1:
                _v_score += 0.4
            
            # 다기간 가격 모멘텀 점수
            _v_momentum_1m = p_stock_data.get("price_momentum_1m", 0.0)
            _v_momentum_3m = p_stock_data.get("price_momentum_3m", 0.0)
            _v_momentum_6m = p_stock_data.get("price_momentum_6m", 0.0)
            
            _v_avg_momentum = np.mean([_v_momentum_1m, _v_momentum_3m, _v_momentum_6m])
            if _v_avg_momentum >= 15:
                _v_score += 1.0
            elif _v_avg_momentum >= 10:
                _v_score += 0.8
            elif _v_avg_momentum >= 5:
                _v_score += 0.6
            elif _v_avg_momentum >= 0:
                _v_score += 0.4
            
            # 거래량 모멘텀 점수
            _v_volume_momentum = p_stock_data.get("volume_momentum", 0.0)
            if _v_volume_momentum >= 0.3:
                _v_score += 1.0
            elif _v_volume_momentum >= 0.2:
                _v_score += 0.8
            elif _v_volume_momentum >= 0.1:
                _v_score += 0.6
            elif _v_volume_momentum >= 0.0:
                _v_score += 0.4
            
            # 섹터 모멘텀 점수
            _v_sector_momentum = p_stock_data.get("sector_momentum", 0.0)
            if _v_sector_momentum >= 0.1:
                _v_score += 1.0
            elif _v_sector_momentum >= 0.05:
                _v_score += 0.8
            elif _v_sector_momentum >= 0.0:
                _v_score += 0.6
            elif _v_sector_momentum >= -0.05:
                _v_score += 0.4
            
            # 정규화 (0-100점)
            return (_v_score / _v_max_score) * 100.0
            
        except Exception as e:
            logger.error(f"모멘텀 점수 계산 오류: {e}", exc_info=True)
            return 0.0
    
    def _calculate_sector_score(self, p_stock_data: Dict) -> float:
        """섹터 점수 계산
        
        Args:
            p_stock_data: 주식 데이터
            
        Returns:
            섹터 점수 (0-100)
        """
        try:
            _v_sector = p_stock_data.get("sector", "기타")
            _v_sector_info = self._v_sector_data.get(_v_sector, {})
            
            _v_score = 0.0
            _v_max_score = 3.0
            
            # 섹터 성과 점수
            _v_sector_performance = _v_sector_info.get("performance", 0.0)
            if _v_sector_performance >= 10:
                _v_score += 1.0
            elif _v_sector_performance >= 5:
                _v_score += 0.8
            elif _v_sector_performance >= 0:
                _v_score += 0.6
            elif _v_sector_performance >= -5:
                _v_score += 0.4
            
            # 섹터 밸류에이션 점수
            _v_sector_valuation = _v_sector_info.get("valuation_level", "normal")
            if _v_sector_valuation == "undervalued":
                _v_score += 1.0
            elif _v_sector_valuation == "normal":
                _v_score += 0.8
            elif _v_sector_valuation == "slightly_overvalued":
                _v_score += 0.6
            elif _v_sector_valuation == "overvalued":
                _v_score += 0.4
            
            # 섹터 전망 점수
            _v_sector_outlook = _v_sector_info.get("outlook", "neutral")
            if _v_sector_outlook == "very_positive":
                _v_score += 1.0
            elif _v_sector_outlook == "positive":
                _v_score += 0.8
            elif _v_sector_outlook == "neutral":
                _v_score += 0.6
            elif _v_sector_outlook == "negative":
                _v_score += 0.4
            
            # 정규화 (0-100점)
            return (_v_score / _v_max_score) * 100.0
            
        except Exception as e:
            logger.error(f"섹터 점수 계산 오류: {e}", exc_info=True)
            return 50.0  # 기본값
    
    def compare_with_sector(self, p_stock_data: Dict) -> Dict:
        """섹터 내 상대적 순위 계산
        
        Args:
            p_stock_data: 주식 데이터
            
        Returns:
            섹터 비교 결과
        """
        try:
            _v_sector = p_stock_data.get("sector", "기타")
            _v_sector_info = self._v_sector_data.get(_v_sector, {})
            
            _v_comparison = {
                "sector": _v_sector,
                "sector_rank": "N/A",
                "sector_percentile": 0.0,
                "vs_sector_average": {},
                "sector_leaders": [],
                "recommendation": "hold"
            }
            
            # 섹터 평균 대비 비교
            _v_sector_averages = _v_sector_info.get("averages", {})
            
            for metric in ["roe", "per", "pbr", "debt_ratio", "revenue_growth"]:
                _v_stock_value = p_stock_data.get(metric, 0.0)
                _v_sector_avg = _v_sector_averages.get(metric, 0.0)
                
                if _v_sector_avg > 0:
                    _v_ratio = _v_stock_value / _v_sector_avg
                    _v_comparison["vs_sector_average"][metric] = {
                        "stock_value": _v_stock_value,
                        "sector_average": _v_sector_avg,
                        "ratio": round(_v_ratio, 2),
                        "better_than_average": _v_ratio > 1.0 if metric in ["roe", "revenue_growth"] else _v_ratio < 1.0
                    }
            
            # 섹터 리더 정보
            _v_comparison["sector_leaders"] = _v_sector_info.get("leaders", [])
            
            # 투자 추천
            _v_comprehensive_score, _ = self.calculate_comprehensive_score(p_stock_data)
            
            if _v_comprehensive_score >= 80:
                _v_comparison["recommendation"] = "strong_buy"
            elif _v_comprehensive_score >= 70:
                _v_comparison["recommendation"] = "buy"
            elif _v_comprehensive_score >= 60:
                _v_comparison["recommendation"] = "hold"
            elif _v_comprehensive_score >= 50:
                _v_comparison["recommendation"] = "weak_hold"
            else:
                _v_comparison["recommendation"] = "sell"
            
            return _v_comparison
            
        except Exception as e:
            logger.error(f"섹터 비교 오류: {e}", exc_info=True)
            return {}
    
    def _adjust_weights_for_market(self) -> EvaluationWeights:
        """시장 상황에 따른 가중치 조정
        
        Returns:
            조정된 가중치
        """
        try:
            _v_adjusted_weights = EvaluationWeights(
                fundamental=self._v_weights.fundamental,
                technical=self._v_weights.technical,
                momentum=self._v_weights.momentum,
                sector=self._v_weights.sector
            )
            
            if self._v_market_condition:
                # 변동성이 높은 시장에서는 기술적 분석 비중 증가
                if self._v_market_condition.volatility_index > 25:
                    _v_adjusted_weights.technical += 0.1
                    _v_adjusted_weights.fundamental -= 0.05
                    _v_adjusted_weights.momentum -= 0.05
                
                # 하락 시장에서는 재무제표 비중 증가
                if self._v_market_condition.market_trend == "하락":
                    _v_adjusted_weights.fundamental += 0.1
                    _v_adjusted_weights.momentum -= 0.1
                
                # 상승 시장에서는 모멘텀 비중 증가
                elif self._v_market_condition.market_trend == "상승":
                    _v_adjusted_weights.momentum += 0.1
                    _v_adjusted_weights.fundamental -= 0.05
                    _v_adjusted_weights.technical -= 0.05
            
            # 가중치 정규화
            _v_total = (_v_adjusted_weights.fundamental + _v_adjusted_weights.technical + 
                       _v_adjusted_weights.momentum + _v_adjusted_weights.sector)
            
            if _v_total > 0:
                _v_adjusted_weights.fundamental /= _v_total
                _v_adjusted_weights.technical /= _v_total
                _v_adjusted_weights.momentum /= _v_total
                _v_adjusted_weights.sector /= _v_total
            
            return _v_adjusted_weights
            
        except Exception as e:
            logger.error(f"가중치 조정 오류: {e}", exc_info=True)
            return self._v_weights
    
    def update_market_condition(self, p_market_condition: MarketCondition) -> None:
        """시장 상황 업데이트
        
        Args:
            p_market_condition: 시장 상황 정보
        """
        self._v_market_condition = p_market_condition
        logger.info(f"시장 상황 업데이트: {p_market_condition.market_trend}, 변동성: {p_market_condition.volatility_index}")
    
    def _load_config(self) -> None:
        """평가 설정 로드"""
        try:
            if os.path.exists(self._v_config_file):
                with open(self._v_config_file, 'r', encoding='utf-8') as f:
                    _v_config = json.load(f)
                
                _v_weights_data = _v_config.get("weights", {})
                self._v_weights = EvaluationWeights(
                    fundamental=_v_weights_data.get("fundamental", 0.4),
                    technical=_v_weights_data.get("technical", 0.3),
                    momentum=_v_weights_data.get("momentum", 0.2),
                    sector=_v_weights_data.get("sector", 0.1)
                )
                
                logger.info("평가 설정 로드 완료")
            else:
                logger.info("기본 평가 설정 사용")
                self._save_config()
                
        except Exception as e:
            logger.error(f"평가 설정 로드 오류: {e}", exc_info=True)
    
    def _save_config(self) -> None:
        """평가 설정 저장"""
        try:
            os.makedirs(os.path.dirname(self._v_config_file), exist_ok=True)
            
            _v_config = {
                "weights": {
                    "fundamental": self._v_weights.fundamental,
                    "technical": self._v_weights.technical,
                    "momentum": self._v_weights.momentum,
                    "sector": self._v_weights.sector
                },
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self._v_config_file, 'w', encoding='utf-8') as f:
                json.dump(_v_config, f, ensure_ascii=False, indent=2)
            
            logger.debug("평가 설정 저장 완료")
            
        except Exception as e:
            logger.error(f"평가 설정 저장 오류: {e}", exc_info=True)
    
    def _load_sector_data(self) -> None:
        """섹터 데이터 로드"""
        try:
            # 더미 섹터 데이터 (실제로는 외부 데이터 소스에서 로드)
            self._v_sector_data = {
                "반도체": {
                    "performance": 8.5,
                    "valuation_level": "normal",
                    "outlook": "positive",
                    "averages": {
                        "roe": 15.2,
                        "per": 18.5,
                        "pbr": 1.8,
                        "debt_ratio": 35.0,
                        "revenue_growth": 12.3
                    },
                    "leaders": ["삼성전자", "SK하이닉스", "LG전자"]
                },
                "자동차": {
                    "performance": -2.1,
                    "valuation_level": "undervalued",
                    "outlook": "neutral",
                    "averages": {
                        "roe": 8.7,
                        "per": 12.3,
                        "pbr": 0.9,
                        "debt_ratio": 65.0,
                        "revenue_growth": 5.8
                    },
                    "leaders": ["현대차", "기아", "현대모비스"]
                },
                "화학": {
                    "performance": 3.2,
                    "valuation_level": "normal",
                    "outlook": "neutral",
                    "averages": {
                        "roe": 11.5,
                        "per": 14.7,
                        "pbr": 1.2,
                        "debt_ratio": 45.0,
                        "revenue_growth": 7.9
                    },
                    "leaders": ["LG화학", "SK이노베이션", "롯데케미칼"]
                },
                "기타": {
                    "performance": 0.0,
                    "valuation_level": "normal",
                    "outlook": "neutral",
                    "averages": {
                        "roe": 10.0,
                        "per": 15.0,
                        "pbr": 1.3,
                        "debt_ratio": 50.0,
                        "revenue_growth": 8.0
                    },
                    "leaders": []
                }
            }
            
            logger.info("섹터 데이터 로드 완료")
            
        except Exception as e:
            logger.error(f"섹터 데이터 로드 오류: {e}", exc_info=True)
    
    def _get_sector_average(self, p_metric: str, p_sector: str) -> float:
        """섹터 평균값 조회
        
        Args:
            p_metric: 지표명
            p_sector: 섹터명
            
        Returns:
            섹터 평균값
        """
        try:
            _v_sector_info = self._v_sector_data.get(p_sector, {})
            _v_averages = _v_sector_info.get("averages", {})
            return _v_averages.get(p_metric, 0.0)
            
        except Exception as e:
            logger.error(f"섹터 평균값 조회 오류: {e}", exc_info=True)
            return 0.0
    
    def set_weights(self, p_weights: EvaluationWeights) -> bool:
        """평가 가중치 설정
        
        Args:
            p_weights: 새로운 가중치
            
        Returns:
            설정 성공 여부
        """
        try:
            if not p_weights.validate():
                logger.error("가중치 합계가 1.0이 아닙니다.")
                return False
            
            self._v_weights = p_weights
            self._save_config()
            
            logger.info(f"평가 가중치 업데이트: 재무={p_weights.fundamental}, 기술={p_weights.technical}, 모멘텀={p_weights.momentum}, 섹터={p_weights.sector}")
            return True
            
        except Exception as e:
            logger.error(f"가중치 설정 오류: {e}", exc_info=True)
            return False 