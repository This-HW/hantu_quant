"""
Phase 4: AI 학습 시스템 - 데이터 수집 시스템
Phase 1,2 결과 데이터와 실제 성과 데이터를 수집하고 AI 학습용 데이터로 변환
"""

import os
import json
import glob
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import numpy as np
from dataclasses import asdict

# 인터페이스 및 데이터 클래스 import
from core.interfaces.learning import (
    ILearningDataCollector, LearningData, 
    IFeatureEngineer, FeatureSet
)
from core.learning.config.settings import get_learning_config
from core.learning.utils.logging import get_learning_logger
from core.learning.data.storage import get_learning_storage
# 임시 플러그인 시스템 (추후 실제 아키텍처로 교체)
def plugin(**kwargs):
    """임시 플러그인 데코레이터"""
    def decorator(cls):
        cls._plugin_metadata = kwargs
        return cls
    return decorator

def inject(cls):
    """임시 DI 데코레이터"""
    return cls

logger = get_learning_logger(__name__)

@plugin(
    name="learning_data_collector",
    version="1.0.0",
    description="AI 학습용 데이터 수집 플러그인",
    author="HantuQuant",
    dependencies=["learning_config", "learning_storage"],
    category="learning"
)
class LearningDataCollector(ILearningDataCollector):
    """AI 학습용 데이터 수집 시스템"""
    
    @inject
    def __init__(self, config=None, storage=None):
        """초기화"""
        self._config = config or get_learning_config()
        self._storage = storage or get_learning_storage()
        self._logger = logger
        
        # 데이터 경로 설정
        self._project_root = Path(__file__).parent.parent.parent.parent
        self._watchlist_dir = self._project_root / "data" / "watchlist"
        self._daily_selection_dir = self._project_root / "data" / "daily_selection"
        self._stock_dir = self._project_root / "data" / "stock"
        
        self._logger.info("LearningDataCollector 초기화 완료")
    
    def collect_historical_data(self, stock_codes: List[str], 
                               start_date: str, end_date: str) -> List[LearningData]:
        """과거 데이터 수집"""
        try:
            self._logger.info(f"과거 데이터 수집 시작: {len(stock_codes)}개 종목, {start_date} ~ {end_date}")
            
            _v_learning_data = []
            
            # 날짜 범위 생성
            _v_date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            
            for _v_date in _v_date_range:
                _v_date_str = _v_date.strftime('%Y-%m-%d')
                
                # 각 날짜의 Phase 1, 2 결과 수집
                _v_phase1_results = self.collect_phase1_results(_v_date_str)
                _v_phase2_results = self.collect_phase2_results(_v_date_str)
                
                # 실제 성과 데이터 수집 (7일 후 성과)
                _v_future_date = (_v_date + timedelta(days=7)).strftime('%Y-%m-%d')
                _v_performance_data = self.collect_actual_performance(stock_codes, _v_date_str, _v_future_date)
                
                # 데이터 병합
                _v_merged_data = self._merge_data(_v_phase1_results, _v_phase2_results, _v_performance_data, _v_date_str)
                _v_learning_data.extend(_v_merged_data)
            
            self._logger.info(f"과거 데이터 수집 완료: {len(_v_learning_data)}개 데이터")
            return _v_learning_data
            
        except Exception as e:
            self._logger.error(f"과거 데이터 수집 오류: {e}")
            return []
    
    def collect_phase1_results(self, date: str) -> List[Dict]:
        """Phase 1 스크리닝 결과 수집"""
        try:
            _v_results = []
            
            # 스크리닝 결과 파일 검색
            _v_date_patterns = [
                datetime.strptime(date, '%Y-%m-%d').strftime('%Y%m%d'),
                datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m-%d'),
                date
            ]
            
            for _v_pattern in _v_date_patterns:
                _v_pattern_files = list(self._watchlist_dir.glob(f"*{_v_pattern}*.json"))
                _v_pattern_files.extend(list(self._watchlist_dir.glob(f"screening_results*{_v_pattern}*.json")))
                
                if _v_pattern_files:
                    for _v_file in _v_pattern_files:
                        _v_data = self._load_json_file(_v_file)
                        if _v_data and "results" in _v_data:
                            _v_results.extend(_v_data["results"])
                    break
            
            # 감시 리스트 데이터도 수집
            _v_watchlist_files = list(self._watchlist_dir.glob("watchlist*.json"))
            for _v_file in _v_watchlist_files:
                _v_data = self._load_json_file(_v_file)
                if _v_data and "data" in _v_data and "stocks" in _v_data["data"]:
                    _v_stocks = _v_data["data"]["stocks"]
                    for _v_stock in _v_stocks:
                        if _v_stock.get("added_date", "").startswith(date):
                            _v_results.append(_v_stock)
            
            self._logger.debug(f"Phase 1 결과 수집 완료: {date} - {len(_v_results)}개")
            return _v_results
            
        except Exception as e:
            self._logger.error(f"Phase 1 결과 수집 오류: {e}")
            return []
    
    def collect_phase2_results(self, date: str) -> List[Dict]:
        """Phase 2 일일 선정 결과 수집"""
        try:
            _v_results = []
            
            # 일일 선정 결과 파일 검색
            _v_date_patterns = [
                datetime.strptime(date, '%Y-%m-%d').strftime('%Y%m%d'),
                datetime.strptime(date, '%Y-%m-%d').strftime('%Y-%m-%d'),
                date
            ]
            
            for _v_pattern in _v_date_patterns:
                _v_pattern_files = list(self._daily_selection_dir.glob(f"*{_v_pattern}*.json"))
                _v_pattern_files.extend(list(self._daily_selection_dir.glob(f"daily_selection*{_v_pattern}*.json")))
                
                if _v_pattern_files:
                    for _v_file in _v_pattern_files:
                        _v_data = self._load_json_file(_v_file)
                        if _v_data and "data" in _v_data and "selected_stocks" in _v_data["data"]:
                            _v_results.extend(_v_data["data"]["selected_stocks"])
                    break
            
            # 가격 분석 결과 파일도 수집
            _v_price_files = list(self._daily_selection_dir.glob(f"price_analysis*{date}*.json"))
            for _v_file in _v_price_files:
                _v_data = self._load_json_file(_v_file)
                if _v_data and "results" in _v_data:
                    _v_results.extend(_v_data["results"])
            
            self._logger.debug(f"Phase 2 결과 수집 완료: {date} - {len(_v_results)}개")
            return _v_results
            
        except Exception as e:
            self._logger.error(f"Phase 2 결과 수집 오류: {e}")
            return []
    
    def collect_actual_performance(self, stock_codes: List[str], 
                                 start_date: str, end_date: str) -> Dict[str, Dict]:
        """실제 성과 데이터 수집"""
        try:
            _v_performance_data = {}
            
            # 실제 구현에서는 API나 데이터베이스에서 주가 데이터 수집
            # 여기서는 시뮬레이션 데이터 생성
            for _v_stock_code in stock_codes:
                _v_performance_data[_v_stock_code] = self._simulate_performance(_v_stock_code, start_date, end_date)
            
            self._logger.debug(f"실제 성과 수집 완료: {len(_v_performance_data)}개 종목")
            return _v_performance_data
            
        except Exception as e:
            self._logger.error(f"실제 성과 수집 오류: {e}")
            return {}
    
    def validate_data_quality(self, data: List[LearningData]) -> Dict[str, Any]:
        """데이터 품질 검증"""
        try:
            _v_quality_report = {
                "total_records": len(data),
                "valid_records": 0,
                "invalid_records": 0,
                "missing_fields": {},
                "data_types": {},
                "value_ranges": {},
                "quality_score": 0.0
            }
            
            for _v_record in data:
                _v_is_valid = True
                
                # 필수 필드 검증
                if not _v_record.stock_code or not _v_record.stock_name:
                    _v_is_valid = False
                    _v_quality_report["missing_fields"]["stock_info"] = _v_quality_report["missing_fields"].get("stock_info", 0) + 1
                
                # Phase 1 데이터 검증
                if not _v_record.phase1_data:
                    _v_is_valid = False
                    _v_quality_report["missing_fields"]["phase1_data"] = _v_quality_report["missing_fields"].get("phase1_data", 0) + 1
                
                # Phase 2 데이터 검증
                if not _v_record.phase2_data:
                    _v_is_valid = False
                    _v_quality_report["missing_fields"]["phase2_data"] = _v_quality_report["missing_fields"].get("phase2_data", 0) + 1
                
                # 실제 성과 데이터 검증
                if not _v_record.actual_performance:
                    _v_is_valid = False
                    _v_quality_report["missing_fields"]["actual_performance"] = _v_quality_report["missing_fields"].get("actual_performance", 0) + 1
                
                if _v_is_valid:
                    _v_quality_report["valid_records"] += 1
                else:
                    _v_quality_report["invalid_records"] += 1
            
            # 품질 점수 계산
            if _v_quality_report["total_records"] > 0:
                _v_quality_report["quality_score"] = _v_quality_report["valid_records"] / _v_quality_report["total_records"]
            
            self._logger.info(f"데이터 품질 검증 완료: {_v_quality_report['quality_score']:.2%} 품질")
            return _v_quality_report
            
        except Exception as e:
            self._logger.error(f"데이터 품질 검증 오류: {e}")
            return {"error": str(e)}
    
    def _merge_data(self, phase1_results: List[Dict], phase2_results: List[Dict], 
                   performance_data: Dict[str, Dict], date: str) -> List[LearningData]:
        """데이터 병합"""
        try:
            _v_merged_data = []
            
            # Phase 1 결과를 기준으로 병합
            for _v_phase1 in phase1_results:
                _v_stock_code = _v_phase1.get("stock_code", "")
                _v_stock_name = _v_phase1.get("stock_name", "")
                
                if not _v_stock_code:
                    continue
                
                # Phase 2 결과 찾기
                _v_phase2_data = {}
                for _v_phase2 in phase2_results:
                    if _v_phase2.get("stock_code") == _v_stock_code:
                        _v_phase2_data = _v_phase2
                        break
                
                # 실제 성과 데이터 찾기
                _v_performance = performance_data.get(_v_stock_code, {})
                
                # 시장 상황 판단
                _v_market_condition = self._determine_market_condition(date)
                
                # LearningData 객체 생성
                _v_learning_data = LearningData(
                    stock_code=_v_stock_code,
                    stock_name=_v_stock_name,
                    date=date,
                    phase1_data=_v_phase1,
                    phase2_data=_v_phase2_data,
                    actual_performance=_v_performance,
                    market_condition=_v_market_condition,
                    metadata={
                        "merge_timestamp": datetime.now().isoformat(),
                        "data_sources": {
                            "phase1": bool(_v_phase1),
                            "phase2": bool(_v_phase2_data),
                            "performance": bool(_v_performance)
                        }
                    }
                )
                
                _v_merged_data.append(_v_learning_data)
            
            return _v_merged_data
            
        except Exception as e:
            self._logger.error(f"데이터 병합 오류: {e}")
            return []
    
    def _load_json_file(self, file_path: Path) -> Optional[Dict]:
        """JSON 파일 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self._logger.error(f"JSON 파일 로드 오류 {file_path}: {e}")
            return None
    
    def _simulate_performance(self, stock_code: str, start_date: str, end_date: str) -> Dict[str, float]:
        """성과 데이터 시뮬레이션 (실제 구현에서는 API 사용)"""
        try:
            # 시드 설정으로 재현 가능한 결과 생성
            np.random.seed(hash(stock_code + start_date) % 1000)
            
            # 기본 수익률 생성 (-20% ~ +30% 범위)
            _v_base_return = np.random.normal(0.05, 0.15)  # 평균 5%, 표준편차 15%
            _v_base_return = max(-0.2, min(0.3, _v_base_return))  # 범위 제한
            
            # 리스크 지표 생성
            _v_volatility = np.random.uniform(0.1, 0.4)
            _v_max_drawdown = np.random.uniform(0.05, 0.25)
            _v_sharpe_ratio = _v_base_return / _v_volatility if _v_volatility > 0 else 0
            
            # 구간별 수익률 생성
            _v_returns = {
                "1d_return": np.random.normal(0.01, 0.03),
                "3d_return": np.random.normal(0.02, 0.05),
                "7d_return": _v_base_return,
                "14d_return": np.random.normal(_v_base_return * 1.5, 0.1),
                "30d_return": np.random.normal(_v_base_return * 2.0, 0.15)
            }
            
            # 리스크 지표
            _v_risk_metrics = {
                "volatility": _v_volatility,
                "max_drawdown": _v_max_drawdown,
                "sharpe_ratio": _v_sharpe_ratio,
                "var_95": np.random.uniform(0.03, 0.08),
                "beta": np.random.uniform(0.5, 1.5)
            }
            
            # 거래 정보
            _v_trading_info = {
                "avg_volume": np.random.uniform(100000, 5000000),
                "volume_increase": np.random.uniform(0.8, 2.5),
                "price_change": _v_base_return,
                "trading_days": 7
            }
            
            return {
                **_v_returns,
                **_v_risk_metrics,
                **_v_trading_info
            }
            
        except Exception as e:
            self._logger.error(f"성과 시뮬레이션 오류: {e}")
            return {}
    
    def _determine_market_condition(self, date: str) -> str:
        """시장 상황 판단"""
        try:
            # 실제 구현에서는 시장 지수 데이터 분석
            # 여기서는 간단한 시뮬레이션
            _v_date_hash = hash(date) % 100
            
            if _v_date_hash < 30:
                return "bull_market"
            elif _v_date_hash < 60:
                return "sideways"
            elif _v_date_hash < 85:
                return "bear_market"
            else:
                return "volatile"
                
        except Exception:
            return "neutral"
    
    def get_data_statistics(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """데이터 통계 정보 조회"""
        try:
            _v_stats = {
                "date_range": {
                    "start": start_date,
                    "end": end_date
                },
                "file_counts": {
                    "phase1_files": len(list(self._watchlist_dir.glob("*.json"))),
                    "phase2_files": len(list(self._daily_selection_dir.glob("*.json"))),
                    "stock_files": len(list(self._stock_dir.glob("*.json")))
                },
                "data_coverage": {},
                "quality_metrics": {}
            }
            
            # 날짜별 데이터 커버리지 확인
            _v_date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            _v_coverage = {}
            
            for _v_date in _v_date_range:
                _v_date_str = _v_date.strftime('%Y-%m-%d')
                _v_phase1_count = len(self.collect_phase1_results(_v_date_str))
                _v_phase2_count = len(self.collect_phase2_results(_v_date_str))
                
                _v_coverage[_v_date_str] = {
                    "phase1_count": _v_phase1_count,
                    "phase2_count": _v_phase2_count,
                    "has_data": _v_phase1_count > 0 or _v_phase2_count > 0
                }
            
            _v_stats["data_coverage"] = _v_coverage
            
            # 전체 커버리지 계산
            _v_total_days = len(_v_date_range)
            _v_days_with_data = sum(1 for d in _v_coverage.values() if d["has_data"])
            _v_stats["quality_metrics"]["coverage_rate"] = _v_days_with_data / _v_total_days if _v_total_days > 0 else 0
            
            return _v_stats
            
        except Exception as e:
            self._logger.error(f"데이터 통계 조회 오류: {e}")
            return {"error": str(e)}


# 전역 인스턴스
_data_collector = None

def get_data_collector() -> LearningDataCollector:
    """데이터 수집기 전역 인스턴스 반환"""
    global _data_collector
    if _data_collector is None:
        _data_collector = LearningDataCollector()
    return _data_collector 