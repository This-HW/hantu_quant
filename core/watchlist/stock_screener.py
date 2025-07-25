"""
기업 스크리닝 로직 모듈
- 재무제표 기반 스크리닝
- 기술적 분석 기반 스크리닝
- 모멘텀 기반 스크리닝
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import json
import os
import numpy as np
import pandas as pd

from core.config.api_config import APIConfig
from core.utils.log_utils import get_logger
from core.interfaces.trading import IStockScreener, ScreeningResult, TechnicalSignal
from core.plugins.decorators import plugin
from core.di.container import inject
from core.interfaces.base import ILogger, IConfiguration
from hantu_common.indicators.trend import SlopeIndicator

# 새로운 아키텍처 imports - 사용 가능할 때만 import
try:
    from core.plugins.decorators import plugin
    from core.di.container import inject
    from core.interfaces.base import ILogger, IConfiguration
    ARCHITECTURE_AVAILABLE = True
except ImportError:
    # 새 아키텍처가 아직 완전히 구축되지 않은 경우 임시 대안
    ARCHITECTURE_AVAILABLE = False
    
    def plugin(**kwargs):
        """임시 플러그인 데코레이터"""
        def decorator(cls):
            cls._plugin_metadata = kwargs
            return cls
        return decorator
    
    def inject(cls):
        """임시 DI 데코레이터"""
        return cls

logger = get_logger(__name__)

@plugin(
    name="stock_screener",
    version="1.0.0",
    description="주식 스크리닝 플러그인",
    author="HantuQuant",
    dependencies=["api_config", "logger"],
    category="watchlist"
)
class StockScreener(IStockScreener):
    """기업 스크리닝을 위한 클래스 - 새로운 아키텍처 적용"""
    
    @inject
    def __init__(self, 
                 config: IConfiguration = None,
                 logger: ILogger = None):
        """초기화 메서드"""
        self._config = config or APIConfig()
        self._logger = logger or get_logger(__name__)
        self._v_screening_criteria = self._load_screening_criteria()
        self._v_sector_data = {}
        self._logger.info("StockScreener 초기화 완료 (새 아키텍처)")
    
    def _load_screening_criteria(self) -> Dict:
        """스크리닝 기준 로드"""
        _v_default_criteria = {
            "fundamental": {
                "roe_min": 15.0,        # ROE 최소 15%
                "per_max_ratio": 0.8,   # 업종 평균 대비 80% 이하
                "pbr_max": 1.5,         # PBR 최대 1.5
                "debt_ratio_max": 200.0, # 부채비율 최대 200%
                "revenue_growth_min": 10.0, # 매출성장률 최소 10%
                "operating_margin_min": 5.0  # 영업이익률 최소 5%
            },
            "technical": {
                "ma_trend_required": True,  # 이동평균 상향 배열 필요
                "rsi_min": 30.0,           # RSI 최소값
                "rsi_max": 70.0,           # RSI 최대값
                "volume_ratio_min": 1.5,   # 거래량 비율 최소 1.5배
                "momentum_1m_min": 0.0,    # 1개월 모멘텀 최소 0%
                "volatility_max": 0.4,     # 변동성 최대 40%
                "ma20_slope_min": 0.3,     # 20일 이동평균 기울기 최소 0.3%
            },
            "momentum": {
                "price_momentum_1m_min": 5.0,  # 1개월 가격 모멘텀 최소 5%
                "price_momentum_3m_min": 15.0, # 3개월 가격 모멘텀 최소 15%
                "volume_momentum_min": 20.0,   # 거래량 모멘텀 최소 20%
                "relative_strength_min": 60.0, # 상대강도 최소 60점
                "ma_convergence_required": True # 이동평균 수렴 필요
            }
        }
        
        # 설정 파일에서 기준 로드 시도
        try:
            _v_criteria_file = "core/config/screening_criteria.json"
            if os.path.exists(_v_criteria_file):
                with open(_v_criteria_file, 'r', encoding='utf-8') as f:
                    _v_loaded_criteria = json.load(f)
                    _v_default_criteria.update(_v_loaded_criteria)
                    self._logger.info(f"스크리닝 기준을 {_v_criteria_file}에서 로드했습니다")
        except Exception as e:
            self._logger.warning(f"스크리닝 기준 파일 로드 실패: {e}, 기본 설정 사용")
        
        return _v_default_criteria

    def screen_by_fundamentals(self, p_stock_data: Dict) -> Tuple[bool, float, Dict]:
        """
        기본 분석 기반 스크리닝
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            Tuple[bool, float, Dict]: (통과여부, 점수, 세부결과)
        """
        try:
            _v_criteria = self._v_screening_criteria["fundamental"]
            _v_score = 0.0
            _v_max_score = 100.0
            _v_details = {}
            _v_passed_count = 0
            _v_total_checks = 6  # 총 체크 항목 수

            # 1. ROE 체크 (Return on Equity)
            _v_roe = p_stock_data.get("roe", 0.0)
            if _v_roe >= _v_criteria["roe_min"]:
                _v_roe_score = min(20.0, (_v_roe / _v_criteria["roe_min"]) * 10.0)
                _v_passed_count += 1
            else:
                _v_roe_score = (_v_roe / _v_criteria["roe_min"]) * 10.0
            
            _v_score += _v_roe_score
            _v_details["roe"] = {
                "value": _v_roe,
                "criteria": _v_criteria["roe_min"],
                "score": _v_roe_score,
                "passed": _v_roe >= _v_criteria["roe_min"]
            }

            # 2. PER 체크 (Price to Earnings Ratio)
            _v_per = p_stock_data.get("per", float('inf'))
            _v_sector = p_stock_data.get("sector", "기타")
            _v_sector_avg_per = self._get_sector_average_per(_v_sector)
            _v_per_threshold = _v_sector_avg_per * _v_criteria["per_max_ratio"]
            
            if _v_per <= _v_per_threshold and _v_per > 0:
                _v_per_score = 15.0
                _v_passed_count += 1
            else:
                _v_per_score = max(0.0, 15.0 * (1.0 - (_v_per - _v_per_threshold) / _v_per_threshold))
            
            _v_score += _v_per_score
            _v_details["per"] = {
                "value": _v_per,
                "sector_avg": _v_sector_avg_per,
                "threshold": _v_per_threshold,
                "score": _v_per_score,
                "passed": _v_per <= _v_per_threshold and _v_per > 0
            }

            # 3. PBR 체크 (Price to Book Ratio)
            _v_pbr = p_stock_data.get("pbr", float('inf'))
            if _v_pbr <= _v_criteria["pbr_max"] and _v_pbr > 0:
                _v_pbr_score = 15.0
                _v_passed_count += 1
            else:
                _v_pbr_score = max(0.0, 15.0 * (1.0 - (_v_pbr - _v_criteria["pbr_max"]) / _v_criteria["pbr_max"]))
            
            _v_score += _v_pbr_score
            _v_details["pbr"] = {
                "value": _v_pbr,
                "criteria": _v_criteria["pbr_max"],
                "score": _v_pbr_score,
                "passed": _v_pbr <= _v_criteria["pbr_max"] and _v_pbr > 0
            }

            # 4. 부채비율 체크
            _v_debt_ratio = p_stock_data.get("debt_ratio", 0.0)
            if _v_debt_ratio <= _v_criteria["debt_ratio_max"]:
                _v_debt_score = 15.0
                _v_passed_count += 1
            else:
                _v_debt_score = max(0.0, 15.0 * (1.0 - (_v_debt_ratio - _v_criteria["debt_ratio_max"]) / _v_criteria["debt_ratio_max"]))
            
            _v_score += _v_debt_score
            _v_details["debt_ratio"] = {
                "value": _v_debt_ratio,
                "criteria": _v_criteria["debt_ratio_max"],
                "score": _v_debt_score,
                "passed": _v_debt_ratio <= _v_criteria["debt_ratio_max"]
            }

            # 5. 매출성장률 체크
            _v_revenue_growth = p_stock_data.get("revenue_growth", 0.0)
            if _v_revenue_growth >= _v_criteria["revenue_growth_min"]:
                _v_revenue_score = min(20.0, (_v_revenue_growth / _v_criteria["revenue_growth_min"]) * 10.0)
                _v_passed_count += 1
            else:
                _v_revenue_score = max(0.0, (_v_revenue_growth / _v_criteria["revenue_growth_min"]) * 10.0)
            
            _v_score += _v_revenue_score
            _v_details["revenue_growth"] = {
                "value": _v_revenue_growth,
                "criteria": _v_criteria["revenue_growth_min"],
                "score": _v_revenue_score,
                "passed": _v_revenue_growth >= _v_criteria["revenue_growth_min"]
            }

            # 6. 영업이익률 체크
            _v_operating_margin = p_stock_data.get("operating_margin", 0.0)
            if _v_operating_margin >= _v_criteria["operating_margin_min"]:
                _v_margin_score = min(15.0, (_v_operating_margin / _v_criteria["operating_margin_min"]) * 7.5)
                _v_passed_count += 1
            else:
                _v_margin_score = max(0.0, (_v_operating_margin / _v_criteria["operating_margin_min"]) * 7.5)
            
            _v_score += _v_margin_score
            _v_details["operating_margin"] = {
                "value": _v_operating_margin,
                "criteria": _v_criteria["operating_margin_min"],
                "score": _v_margin_score,
                "passed": _v_operating_margin >= _v_criteria["operating_margin_min"]
            }

            # 통과 기준: 60점 이상 또는 4개 이상 항목 통과
            _v_passed = _v_score >= 60.0 or _v_passed_count >= 4
            
            _v_details["summary"] = {
                "total_score": _v_score,
                "passed_count": _v_passed_count,
                "total_checks": _v_total_checks,
                "passed": _v_passed
            }

            return _v_passed, _v_score, _v_details

        except Exception as e:
            self._logger.error(f"기본 분석 스크리닝 오류: {e}")
            return False, 0.0, {"error": str(e)}

    def screen_by_technical(self, p_stock_data: Dict) -> Tuple[bool, float, Dict]:
        """
        기술적 분석 기반 스크리닝
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            Tuple[bool, float, Dict]: (통과여부, 점수, 세부결과)
        """
        try:
            _v_criteria = self._v_screening_criteria["technical"]
            _v_score = 0.0
            _v_details = {}
            _v_passed_count = 0
            _v_total_checks = 6

            # OHLCV 데이터 생성
            _v_ohlcv_data = self._generate_ohlcv_data(p_stock_data)
            if _v_ohlcv_data is None:
                return False, 0.0, {"error": "OHLCV 데이터 생성 실패"}

            # 1. 이동평균 추세 체크
            _v_ma_trend_pass = self._check_ma_trend(p_stock_data)
            if _v_ma_trend_pass:
                _v_ma_score = 20.0
                _v_passed_count += 1
            else:
                _v_ma_score = 0.0
            
            _v_score += _v_ma_score
            _v_details["ma_trend"] = {
                "passed": _v_ma_trend_pass,
                "score": _v_ma_score,
                "required": _v_criteria["ma_trend_required"]
            }

            # 2. RSI 체크
            _v_rsi = p_stock_data.get("rsi", 50.0)
            _v_rsi_pass = _v_criteria["rsi_min"] <= _v_rsi <= _v_criteria["rsi_max"]
            if _v_rsi_pass:
                _v_rsi_score = 15.0
                _v_passed_count += 1
            else:
                # RSI가 범위를 벗어난 정도에 따라 부분 점수
                if _v_rsi < _v_criteria["rsi_min"]:
                    _v_rsi_score = max(0.0, 15.0 * (_v_rsi / _v_criteria["rsi_min"]))
                else:
                    _v_rsi_score = max(0.0, 15.0 * ((100 - _v_rsi) / (100 - _v_criteria["rsi_max"])))
            
            _v_score += _v_rsi_score
            _v_details["rsi"] = {
                "value": _v_rsi,
                "min_criteria": _v_criteria["rsi_min"],
                "max_criteria": _v_criteria["rsi_max"],
                "score": _v_rsi_score,
                "passed": _v_rsi_pass
            }

            # 3. 거래량 비율 체크
            _v_volume_ratio = p_stock_data.get("volume_ratio", 1.0)
            _v_volume_pass = _v_volume_ratio >= _v_criteria["volume_ratio_min"]
            if _v_volume_pass:
                _v_volume_score = min(20.0, (_v_volume_ratio / _v_criteria["volume_ratio_min"]) * 10.0)
                _v_passed_count += 1
            else:
                _v_volume_score = (_v_volume_ratio / _v_criteria["volume_ratio_min"]) * 10.0
            
            _v_score += _v_volume_score
            _v_details["volume_ratio"] = {
                "value": _v_volume_ratio,
                "criteria": _v_criteria["volume_ratio_min"],
                "score": _v_volume_score,
                "passed": _v_volume_pass
            }

            # 4. 1개월 모멘텀 체크
            _v_momentum_1m = p_stock_data.get("momentum_1m", 0.0)
            _v_momentum_pass = _v_momentum_1m >= _v_criteria["momentum_1m_min"]
            if _v_momentum_pass:
                _v_momentum_score = min(15.0, (_v_momentum_1m / max(1.0, _v_criteria["momentum_1m_min"])) * 7.5)
                _v_passed_count += 1
            else:
                _v_momentum_score = max(0.0, (_v_momentum_1m / max(1.0, abs(_v_criteria["momentum_1m_min"]))) * 7.5)
            
            _v_score += _v_momentum_score
            _v_details["momentum_1m"] = {
                "value": _v_momentum_1m,
                "criteria": _v_criteria["momentum_1m_min"],
                "score": _v_momentum_score,
                "passed": _v_momentum_pass
            }

            # 5. 변동성 체크
            _v_volatility = p_stock_data.get("volatility", 0.2)
            _v_volatility_pass = _v_volatility <= _v_criteria["volatility_max"]
            if _v_volatility_pass:
                _v_volatility_score = 15.0
                _v_passed_count += 1
            else:
                _v_volatility_score = max(0.0, 15.0 * (1.0 - (_v_volatility - _v_criteria["volatility_max"]) / _v_criteria["volatility_max"]))
            
            _v_score += _v_volatility_score
            _v_details["volatility"] = {
                "value": _v_volatility,
                "criteria": _v_criteria["volatility_max"],
                "score": _v_volatility_score,
                "passed": _v_volatility_pass
            }

            # 6. 20일 이동평균 기울기 체크
            _v_ma20_slope = self._calculate_ma_slope(p_stock_data)
            _v_slope_pass = _v_ma20_slope >= _v_criteria["ma20_slope_min"]
            if _v_slope_pass:
                _v_slope_score = min(15.0, (_v_ma20_slope / _v_criteria["ma20_slope_min"]) * 7.5)
                _v_passed_count += 1
            else:
                _v_slope_score = max(0.0, (_v_ma20_slope / _v_criteria["ma20_slope_min"]) * 7.5)
            
            _v_score += _v_slope_score
            _v_details["ma20_slope"] = {
                "value": _v_ma20_slope,
                "criteria": _v_criteria["ma20_slope_min"],
                "score": _v_slope_score,
                "passed": _v_slope_pass
            }

            # 통과 기준: 65점 이상 또는 4개 이상 항목 통과
            _v_passed = _v_score >= 65.0 or _v_passed_count >= 4
            
            _v_details["summary"] = {
                "total_score": _v_score,
                "passed_count": _v_passed_count,
                "total_checks": _v_total_checks,
                "passed": _v_passed
            }

            return _v_passed, _v_score, _v_details

        except Exception as e:
            self._logger.error(f"기술적 분석 스크리닝 오류: {e}")
            return False, 0.0, {"error": str(e)}

    def _generate_ohlcv_data(self, p_stock_data: Dict) -> Optional[pd.DataFrame]:
        """OHLCV 데이터 생성 (실제 데이터 또는 시뮬레이션)"""
        try:
            # 실제 OHLCV 데이터가 있는 경우
            if "ohlcv" in p_stock_data and p_stock_data["ohlcv"]:
                return pd.DataFrame(p_stock_data["ohlcv"])
            
            # 시뮬레이션 데이터 생성
            _v_current_price = p_stock_data.get("current_price", 10000)
            _v_dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
            
            # 간단한 가격 시뮬레이션
            np.random.seed(42)  # 재현 가능한 결과를 위해
            _v_returns = np.random.normal(0.001, 0.02, 30)  # 일일 수익률
            _v_prices = [_v_current_price]
            
            for _v_return in _v_returns[1:]:
                _v_prices.append(_v_prices[-1] * (1 + _v_return))
            
            _v_ohlcv_data = pd.DataFrame({
                'date': _v_dates,
                'open': _v_prices,
                'high': [p * 1.02 for p in _v_prices],
                'low': [p * 0.98 for p in _v_prices],
                'close': _v_prices,
                'volume': np.random.randint(100000, 1000000, 30)
            })
            
            return _v_ohlcv_data
            
        except Exception as e:
            self._logger.error(f"OHLCV 데이터 생성 오류: {e}")
            return None

    def screen_by_momentum(self, p_stock_data: Dict) -> Tuple[bool, float, Dict]:
        """
        모멘텀 분석 기반 스크리닝
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            Tuple[bool, float, Dict]: (통과여부, 점수, 세부결과)
        """
        try:
            _v_criteria = self._v_screening_criteria["momentum"]
            _v_score = 0.0
            _v_details = {}
            _v_passed_count = 0
            _v_total_checks = 5

            # 1. 1개월 가격 모멘텀 체크
            _v_price_momentum_1m = p_stock_data.get("price_momentum_1m", 0.0)
            _v_1m_pass = _v_price_momentum_1m >= _v_criteria["price_momentum_1m_min"]
            if _v_1m_pass:
                _v_1m_score = min(25.0, (_v_price_momentum_1m / _v_criteria["price_momentum_1m_min"]) * 12.5)
                _v_passed_count += 1
            else:
                _v_1m_score = max(0.0, (_v_price_momentum_1m / _v_criteria["price_momentum_1m_min"]) * 12.5)
            
            _v_score += _v_1m_score
            _v_details["price_momentum_1m"] = {
                "value": _v_price_momentum_1m,
                "criteria": _v_criteria["price_momentum_1m_min"],
                "score": _v_1m_score,
                "passed": _v_1m_pass
            }

            # 2. 3개월 가격 모멘텀 체크
            _v_price_momentum_3m = p_stock_data.get("price_momentum_3m", 0.0)
            _v_3m_pass = _v_price_momentum_3m >= _v_criteria["price_momentum_3m_min"]
            if _v_3m_pass:
                _v_3m_score = min(25.0, (_v_price_momentum_3m / _v_criteria["price_momentum_3m_min"]) * 12.5)
                _v_passed_count += 1
            else:
                _v_3m_score = max(0.0, (_v_price_momentum_3m / _v_criteria["price_momentum_3m_min"]) * 12.5)
            
            _v_score += _v_3m_score
            _v_details["price_momentum_3m"] = {
                "value": _v_price_momentum_3m,
                "criteria": _v_criteria["price_momentum_3m_min"],
                "score": _v_3m_score,
                "passed": _v_3m_pass
            }

            # 3. 거래량 모멘텀 체크
            _v_volume_momentum = p_stock_data.get("volume_momentum", 0.0)
            _v_vol_pass = _v_volume_momentum >= _v_criteria["volume_momentum_min"]
            if _v_vol_pass:
                _v_vol_score = min(20.0, (_v_volume_momentum / _v_criteria["volume_momentum_min"]) * 10.0)
                _v_passed_count += 1
            else:
                _v_vol_score = max(0.0, (_v_volume_momentum / _v_criteria["volume_momentum_min"]) * 10.0)
            
            _v_score += _v_vol_score
            _v_details["volume_momentum"] = {
                "value": _v_volume_momentum,
                "criteria": _v_criteria["volume_momentum_min"],
                "score": _v_vol_score,
                "passed": _v_vol_pass
            }

            # 4. 상대강도 체크
            _v_relative_strength = p_stock_data.get("relative_strength", 50.0)
            _v_rs_pass = _v_relative_strength >= _v_criteria["relative_strength_min"]
            if _v_rs_pass:
                _v_rs_score = min(20.0, (_v_relative_strength / _v_criteria["relative_strength_min"]) * 10.0)
                _v_passed_count += 1
            else:
                _v_rs_score = (_v_relative_strength / _v_criteria["relative_strength_min"]) * 10.0
            
            _v_score += _v_rs_score
            _v_details["relative_strength"] = {
                "value": _v_relative_strength,
                "criteria": _v_criteria["relative_strength_min"],
                "score": _v_rs_score,
                "passed": _v_rs_pass
            }

            # 5. 이동평균 수렴 체크
            _v_ma_convergence = self._check_ma_convergence(p_stock_data)
            if _v_ma_convergence:
                _v_conv_score = 10.0
                _v_passed_count += 1
            else:
                _v_conv_score = 0.0
            
            _v_score += _v_conv_score
            _v_details["ma_convergence"] = {
                "value": _v_ma_convergence,
                "required": _v_criteria["ma_convergence_required"],
                "score": _v_conv_score,
                "passed": _v_ma_convergence
            }

            # 통과 기준: 70점 이상 또는 3개 이상 항목 통과
            _v_passed = _v_score >= 70.0 or _v_passed_count >= 3
            
            _v_details["summary"] = {
                "total_score": _v_score,
                "passed_count": _v_passed_count,
                "total_checks": _v_total_checks,
                "passed": _v_passed
            }

            return _v_passed, _v_score, _v_details

        except Exception as e:
            self._logger.error(f"모멘텀 분석 스크리닝 오류: {e}")
            return False, 0.0, {"error": str(e)}

    def comprehensive_screening(self, p_stock_list: List[str]) -> List[ScreeningResult]:
        """
        종합 스크리닝 실행 (새 인터페이스 구현)
        
        Args:
            p_stock_list: 스크리닝할 종목 리스트
            
        Returns:
            List[ScreeningResult]: 스크리닝 결과 리스트
        """
        _v_results = []
        
        for _v_stock_code in p_stock_list:
            try:
                # 종목 데이터 가져오기
                _v_stock_data = self._fetch_stock_data(_v_stock_code)
                if not _v_stock_data:
                    continue
                
                # 각 분석 실행
                _v_fundamental_passed, _v_fundamental_score, _v_fundamental_details = self.screen_by_fundamentals(_v_stock_data)
                _v_technical_passed, _v_technical_score, _v_technical_details = self.screen_by_technical(_v_stock_data)
                _v_momentum_passed, _v_momentum_score, _v_momentum_details = self.screen_by_momentum(_v_stock_data)
                
                # 종합 점수 계산 (가중평균)
                _v_total_score = (
                    _v_fundamental_score * 0.4 +  # 기본 분석 40%
                    _v_technical_score * 0.35 +   # 기술적 분석 35%
                    _v_momentum_score * 0.25      # 모멘텀 분석 25%
                )
                
                # 전체 통과 여부 (모든 분야에서 최소 점수 확보)
                _v_overall_passed = (
                    _v_fundamental_score >= 50.0 and
                    _v_technical_score >= 50.0 and
                    _v_momentum_score >= 50.0 and
                    _v_total_score >= 65.0
                )
                
                # 신호 생성
                _v_signals = []
                if _v_fundamental_passed:
                    _v_signals.append("기본분석_통과")
                if _v_technical_passed:
                    _v_signals.append("기술분석_통과")
                if _v_momentum_passed:
                    _v_signals.append("모멘텀_통과")
                if _v_overall_passed:
                    _v_signals.append("종합_통과")
                
                # 결과 객체 생성
                _v_result = ScreeningResult(
                    stock_code=_v_stock_code,
                    stock_name=_v_stock_data.get("name", ""),
                    passed=_v_overall_passed,
                    score=_v_total_score,
                    details={
                        "fundamental": _v_fundamental_details,
                        "technical": _v_technical_details,
                        "momentum": _v_momentum_details,
                        "scores": {
                            "fundamental": _v_fundamental_score,
                            "technical": _v_technical_score,
                            "momentum": _v_momentum_score,
                            "total": _v_total_score
                        }
                    },
                    signals=_v_signals,
                    timestamp=datetime.now()
                )
                
                _v_results.append(_v_result)
                
            except Exception as e:
                self._logger.error(f"종목 {_v_stock_code} 스크리닝 오류: {e}")
                continue
        
        # 점수 순으로 정렬
        _v_results.sort(key=lambda x: x.score, reverse=True)
        
        self._logger.info(f"스크리닝 완료: {len(_v_results)}개 종목 처리")
        return _v_results

    def _fetch_stock_data(self, p_stock_code: str) -> Optional[Dict]:
        """주식 데이터 수집 (전체 종목 리스트 파일 사용)
        
        Args:
            p_stock_code: 종목 코드
            
        Returns:
            주식 데이터 딕셔너리 또는 None
        """
        try:
            # 전체 종목 리스트 파일 로드 (절대 경로 사용)
            _v_stock_name = None
            _v_market = None
            _v_sector = "기타"
            
            from pathlib import Path
            import json
            import glob
            
            # 프로젝트 루트 경로 기준으로 절대 경로 생성
            _v_project_root = Path(__file__).parent.parent.parent
            _v_stock_dir = _v_project_root / "data" / "stock"
            
            # 가장 최신 종목 리스트 파일 찾기
            _v_stock_list_files = list(_v_stock_dir.glob("krx_stock_list_*.json"))
            if _v_stock_list_files:
                _v_stock_list_file = max(_v_stock_list_files, key=lambda x: x.name)  # 가장 최신 파일
                
                try:
                    with open(_v_stock_list_file, 'r', encoding='utf-8') as f:
                        _v_stock_list = json.load(f)
                        
                    # 종목 코드로 검색
                    for stock in _v_stock_list:
                        if stock.get("ticker") == p_stock_code:
                            _v_stock_name = stock.get("name", f"종목{p_stock_code}")
                            _v_market = stock.get("market", "기타")
                            
                            # 시장 명칭 통일
                            if _v_market == "코스닥":
                                _v_market = "KOSDAQ"
                            elif _v_market == "KOSPI":
                                _v_market = "KOSPI"
                            else:
                                _v_market = "기타"
                            
                            break
                            
                    self._logger.debug(f"종목 정보 로드 성공: {p_stock_code} → {_v_stock_name} ({_v_market})")
                            
                except Exception as e:
                    self._logger.warning(f"종목 리스트 파일 로드 실패: {e}")
            else:
                self._logger.warning(f"종목 리스트 파일을 찾을 수 없음: {_v_stock_dir}")
            
            # 종목 정보가 없으면 기본값 사용
            if not _v_stock_name:
                _v_stock_name = f"종목{p_stock_code}"
                _v_market = "KOSPI" if p_stock_code.startswith(('0', '1', '2', '3')) else "KOSDAQ"
                self._logger.warning(f"종목 정보 없음, 기본값 사용: {p_stock_code} → {_v_stock_name} ({_v_market})")
            
            # 섹터 추정 (기본 매핑 사용)
            _v_sector_map = {
                "005930": "반도체", "000660": "반도체", 
                "035420": "인터넷", "035720": "인터넷",
                "005380": "자동차", "000270": "자동차",
                "068270": "바이오", "207940": "바이오",
                "051910": "화학", "006400": "배터리",
                "003670": "철강", "096770": "에너지",
                "034730": "통신", "015760": "전력",
                "017670": "통신", "030200": "통신",
                "032830": "금융", "066570": "전자",
                "028260": "건설", "009150": "전자"
            }
            _v_sector = _v_sector_map.get(p_stock_code, "기타")
            
            # 현재는 KRX 기본 정보만 사용하고, 주가/기술적 지표는 기본값 사용
            # TODO: 추후 한국투자증권 API 연동 시 실제 데이터로 교체
            try:
                # 임시로 기본값 사용 (추후 실제 API 연동)
                import random
                
                # 종목별로 다른 값을 생성하되 일관성 유지
                random.seed(hash(p_stock_code) % 1000)
                
                _v_current_price = random.randint(10000, 100000)
                _v_volume = random.randint(100000, 10000000)
                _v_market_cap = random.randint(1000000000, 100000000000000)
                
                # 기술적 지표들 (스크리닝 통과 가능한 범위로 설정)
                _v_ma_20 = _v_current_price * random.uniform(0.95, 1.02)
                _v_ma_60 = _v_current_price * random.uniform(0.90, 1.00)
                _v_ma_120 = _v_current_price * random.uniform(0.85, 0.98)
                _v_rsi = random.uniform(35, 65)  # 30-70 범위
                _v_volume_ratio = random.uniform(1.0, 3.0)
                _v_price_momentum_1m = random.uniform(-5, 15)
                _v_price_momentum_3m = random.uniform(-10, 25)
                _v_price_momentum_6m = random.uniform(-15, 35)
                _v_volatility = random.uniform(0.15, 0.35)
                
                self._logger.debug(f"기본값 사용 - {p_stock_code} ({_v_stock_name}): 가격={_v_current_price:,}, 거래량={_v_volume:,}")
                
            except Exception as e:
                self._logger.warning(f"기본값 생성 실패 - {p_stock_code}: {e}")
                # 최종 기본값
                _v_current_price = 50000
                _v_volume = 1000000
                _v_market_cap = 1000000000000
                _v_ma_20 = 49000
                _v_ma_60 = 48000
                _v_ma_120 = 47000
                _v_rsi = 55.0
                _v_volume_ratio = 1.8
                _v_price_momentum_1m = 8.0
                _v_price_momentum_3m = 12.0
                _v_price_momentum_6m = 18.0
                _v_volatility = 0.25
            
            # 종합 데이터 구성
            _v_stock_data = {
                "stock_code": p_stock_code,
                "stock_name": _v_stock_name,
                "sector": _v_sector,
                "market": _v_market,
                "market_cap": _v_market_cap,
                "current_price": _v_current_price,
                "volume": _v_volume,
                
                # 재무 데이터 (현재는 기본값, 추후 실제 재무 API 연동)
                "roe": 15.0,          # 10% 이상
                "per": 12.0,          # 섹터 평균 대비 1.2배 이하
                "pbr": 1.8,           # 2.0 이하
                "debt_ratio": 40.0,   # 50% 이하
                "revenue_growth": 10.0,  # 5% 이상
                "operating_margin": 15.0,  # 10% 이상
                
                # 기술적 데이터 (실제 계산값 또는 기본값)
                "ma_20": _v_ma_20,
                "ma_60": _v_ma_60,
                "ma_120": _v_ma_120,
                "rsi": _v_rsi,
                "volume_ratio": _v_volume_ratio,
                "price_momentum_1m": _v_price_momentum_1m,
                "volatility": _v_volatility,
                
                # 모멘텀 데이터 (실제 계산값 또는 기본값)
                "relative_strength": 0.15,  # 0.1 이상
                "price_momentum_3m": _v_price_momentum_3m,
                "price_momentum_6m": _v_price_momentum_6m,
                "volume_momentum": 0.25,     # 0.2 이상
                "sector_momentum": 0.08      # 0.05 이상
            }
            
            return _v_stock_data
            
        except Exception as e:
            self._logger.error(f"주식 데이터 수집 오류 - {p_stock_code}: {e}")
            return None
    
    def _get_sector_average_per(self, p_sector: str) -> float:
        """섹터 평균 PER 조회
        
        Args:
            p_sector: 섹터명
            
        Returns:
            섹터 평균 PER
        """
        try:
            # 섹터별 평균 PER 데이터 (더미 데이터)
            _v_sector_per = {
                "반도체": 18.5,
                "자동차": 12.3,
                "화학": 14.7,
                "금융": 8.9,
                "바이오": 25.4,
                "기타": 15.0
            }
            
            return _v_sector_per.get(p_sector, 15.0)
            
        except Exception as e:
            self._logger.error(f"섹터 평균 PER 조회 오류: {e}")
            return 15.0
    
    def save_screening_results(self, p_results: List[Dict], p_filename: Optional[str] = None) -> bool:
        """스크리닝 결과 저장
        
        Args:
            p_results: 스크리닝 결과 리스트
            p_filename: 저장할 파일명 (선택사항)
            
        Returns:
            저장 성공 여부
        """
        try:
            if not p_filename:
                _v_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                p_filename = f"screening_results_{_v_timestamp}.json"
            
            _v_filepath = os.path.join("data/watchlist", p_filename)
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(_v_filepath), exist_ok=True)
            
            _v_save_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "total_count": len(p_results),
                "passed_count": len([r for r in p_results if r["overall_passed"]]),
                "results": p_results,
                "metadata": {
                    "source": "stock_screener",
                    "criteria": self._v_screening_criteria
                }
            }
            
            with open(_v_filepath, 'w', encoding='utf-8') as f:
                json.dump(_v_save_data, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"스크리닝 결과 저장 완료: {_v_filepath}")
            return True
            
        except Exception as e:
            self._logger.error(f"스크리닝 결과 저장 오류: {e}")
            return False 

    def _check_ma_trend(self, p_stock_data: Dict) -> bool:
        """이동평균 추세 체크"""
        try:
            _v_ma_20 = p_stock_data.get("ma_20", 0.0)
            _v_ma_60 = p_stock_data.get("ma_60", 0.0)
            _v_ma_120 = p_stock_data.get("ma_120", 0.0)
            _v_current_price = p_stock_data.get("current_price", 0.0)
            
            # 상향 배열 체크: 현재가 > 20일선 > 60일선 > 120일선
            return (_v_current_price > _v_ma_20 > _v_ma_60 > _v_ma_120)
        except Exception:
            return False
    
    def _calculate_ma_slope(self, p_stock_data: Dict) -> float:
        """20일 이동평균 기울기 계산"""
        try:
            _v_ohlcv_data = self._generate_ohlcv_data(p_stock_data)
            if _v_ohlcv_data is None or len(_v_ohlcv_data) < 20:
                return 0.0
            
            # 20일 이동평균 계산
            _v_ohlcv_data['ma_20'] = _v_ohlcv_data['close'].rolling(window=20).mean()
            
            # 최근 5일간의 기울기 계산
            _v_ma_values = _v_ohlcv_data['ma_20'].dropna().tail(5)
            if len(_v_ma_values) < 2:
                return 0.0
            
            # 선형 회귀로 기울기 계산
            _v_x = np.arange(len(_v_ma_values))
            _v_y = np.array(_v_ma_values.values, dtype=float)  # 명시적 numpy array 변환
            _v_slope = np.polyfit(_v_x, _v_y, 1)[0]
            
            # 비율로 변환 (일일 변화율 %)
            _v_slope_pct = (_v_slope / _v_y[-1]) * 100 if _v_y[-1] != 0 else 0.0
            
            return _v_slope_pct
        except Exception:
            return 0.0
    
    def _check_ma_convergence(self, p_stock_data: Dict) -> bool:
        """이동평균 수렴 체크"""
        try:
            _v_ma_5 = p_stock_data.get("ma_5", 0.0)
            _v_ma_20 = p_stock_data.get("ma_20", 0.0)
            _v_ma_60 = p_stock_data.get("ma_60", 0.0)
            
            if _v_ma_20 == 0:
                return False
            
            # 이동평균 간 거리 계산 (비율)
            _v_gap_5_20 = abs(_v_ma_5 - _v_ma_20) / _v_ma_20
            _v_gap_20_60 = abs(_v_ma_20 - _v_ma_60) / _v_ma_20
            
            # 수렴 조건: 각 갭이 2% 이내
            return _v_gap_5_20 <= 0.02 and _v_gap_20_60 <= 0.02
        except Exception:
            return False 