"""
기업 스크리닝 로직 모듈
- 재무제표 기반 스크리닝
- 기술적 분석 기반 스크리닝
- 모멘텀 기반 스크리닝
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json
import os
import numpy as np
import pandas as pd

from core.config.api_config import APIConfig
from core.utils.log_utils import get_logger
from core.interfaces.trading import IStockScreener, ScreeningResult
from core.plugins.decorators import plugin
from core.di.injector import inject
from core.api.rest_client import RestClient
from core.daily_selection.price_analyzer import TechnicalIndicators

# 새로운 아키텍처 imports - 사용 가능할 때만 import
try:
    from core.interfaces.base import ILogger, IConfiguration

    ARCHITECTURE_AVAILABLE = True
except ImportError:
    # 기존 시스템과의 호환성을 위한 폴백
    ILogger = object
    IConfiguration = object
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
    category="watchlist",
)
class StockScreener(IStockScreener):
    """기업 스크리닝을 위한 클래스 - 새로운 아키텍처 적용"""

    @inject
    def __init__(self, config: IConfiguration = None, logger: ILogger = None):
        """초기화 메서드"""
        self._config = config or APIConfig()
        self._logger = logger or get_logger(__name__)
        self._rest_client = RestClient()
        self._v_screening_criteria = self._load_screening_criteria()
        self._v_sector_data = {}
        self._logger.info("StockScreener 초기화 완료 (새 아키텍처)")

    def initialize(self):
        """플러그인 초기화 메서드 (플러그인 데코레이터 요구사항)"""
        self._logger.info("StockScreener 플러그인 초기화 완료")
        return True

    def _load_screening_criteria(self) -> Dict:
        """스크리닝 기준 로드"""
        _v_default_criteria = {
            "fundamental": {
                "roe_min": 15.0,  # ROE 최소 15%
                "per_max_ratio": 0.8,  # 업종 평균 대비 80% 이하
                "pbr_max": 1.5,  # PBR 최대 1.5
                "debt_ratio_max": 200.0,  # 부채비율 최대 200%
                "revenue_growth_min": 10.0,  # 매출성장률 최소 10%
                "operating_margin_min": 5.0,  # 영업이익률 최소 5%
            },
            "technical": {
                "ma_trend_required": True,  # 이동평균 상향 배열 필요
                "rsi_min": 30.0,  # RSI 최소값
                "rsi_max": 70.0,  # RSI 최대값
                "volume_ratio_min": 1.5,  # 거래량 비율 최소 1.5배
                "momentum_1m_min": 0.0,  # 1개월 모멘텀 최소 0%
                "volatility_max": 0.4,  # 변동성 최대 40%
                "ma20_slope_min": 0.3,  # 20일 이동평균 기울기 최소 0.3%
            },
            "momentum": {
                "price_momentum_1m_min": 5.0,  # 1개월 가격 모멘텀 최소 5%
                "price_momentum_3m_min": 15.0,  # 3개월 가격 모멘텀 최소 15%
                "volume_momentum_min": 20.0,  # 거래량 모멘텀 최소 20%
                "relative_strength_min": 60.0,  # 상대강도 최소 60점
                "ma_convergence_required": True,  # 이동평균 수렴 필요
            },
        }

        # 설정 파일에서 기준 로드 시도
        try:
            _v_criteria_file = "core/config/screening_criteria.json"
            if os.path.exists(_v_criteria_file):
                with open(_v_criteria_file, "r", encoding="utf-8") as f:
                    _v_loaded_criteria = json.load(f)
                    _v_default_criteria.update(_v_loaded_criteria)
                    self._logger.info(
                        f"스크리닝 기준을 {_v_criteria_file}에서 로드했습니다"
                    )
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
                "passed": _v_roe >= _v_criteria["roe_min"],
            }

            # 2. PER 체크 (Price to Earnings Ratio)
            _v_per = p_stock_data.get("per", float("inf"))
            _v_sector = p_stock_data.get("sector", "기타")
            _v_sector_avg_per = self._get_sector_average_per(_v_sector)
            _v_per_threshold = _v_sector_avg_per * _v_criteria["per_max_ratio"]

            if _v_per <= _v_per_threshold and _v_per > 0:
                _v_per_score = 15.0
                _v_passed_count += 1
            else:
                _v_per_score = max(
                    0.0, 15.0 * (1.0 - (_v_per - _v_per_threshold) / _v_per_threshold)
                )

            _v_score += _v_per_score
            _v_details["per"] = {
                "value": _v_per,
                "sector_avg": _v_sector_avg_per,
                "threshold": _v_per_threshold,
                "score": _v_per_score,
                "passed": _v_per <= _v_per_threshold and _v_per > 0,
            }

            # 3. PBR 체크 (Price to Book Ratio)
            _v_pbr = p_stock_data.get("pbr", float("inf"))
            if _v_pbr <= _v_criteria["pbr_max"] and _v_pbr > 0:
                _v_pbr_score = 15.0
                _v_passed_count += 1
            else:
                _v_pbr_score = max(
                    0.0,
                    15.0
                    * (
                        1.0 - (_v_pbr - _v_criteria["pbr_max"]) / _v_criteria["pbr_max"]
                    ),
                )

            _v_score += _v_pbr_score
            _v_details["pbr"] = {
                "value": _v_pbr,
                "criteria": _v_criteria["pbr_max"],
                "score": _v_pbr_score,
                "passed": _v_pbr <= _v_criteria["pbr_max"] and _v_pbr > 0,
            }

            # 4. 부채비율 체크
            _v_debt_ratio = p_stock_data.get("debt_ratio", 0.0)
            if _v_debt_ratio <= _v_criteria["debt_ratio_max"]:
                _v_debt_score = 15.0
                _v_passed_count += 1
            else:
                _v_debt_score = max(
                    0.0,
                    15.0
                    * (
                        1.0
                        - (_v_debt_ratio - _v_criteria["debt_ratio_max"])
                        / _v_criteria["debt_ratio_max"]
                    ),
                )

            _v_score += _v_debt_score
            _v_details["debt_ratio"] = {
                "value": _v_debt_ratio,
                "criteria": _v_criteria["debt_ratio_max"],
                "score": _v_debt_score,
                "passed": _v_debt_ratio <= _v_criteria["debt_ratio_max"],
            }

            # 5. 매출성장률 체크
            _v_revenue_growth = p_stock_data.get("revenue_growth", 0.0)
            if _v_revenue_growth >= _v_criteria["revenue_growth_min"]:
                _v_revenue_score = min(
                    20.0, (_v_revenue_growth / _v_criteria["revenue_growth_min"]) * 10.0
                )
                _v_passed_count += 1
            else:
                _v_revenue_score = max(
                    0.0, (_v_revenue_growth / _v_criteria["revenue_growth_min"]) * 10.0
                )

            _v_score += _v_revenue_score
            _v_details["revenue_growth"] = {
                "value": _v_revenue_growth,
                "criteria": _v_criteria["revenue_growth_min"],
                "score": _v_revenue_score,
                "passed": _v_revenue_growth >= _v_criteria["revenue_growth_min"],
            }

            # 6. 영업이익률 체크
            _v_operating_margin = p_stock_data.get("operating_margin", 0.0)
            if _v_operating_margin >= _v_criteria["operating_margin_min"]:
                _v_margin_score = min(
                    15.0,
                    (_v_operating_margin / _v_criteria["operating_margin_min"]) * 7.5,
                )
                _v_passed_count += 1
            else:
                _v_margin_score = max(
                    0.0,
                    (_v_operating_margin / _v_criteria["operating_margin_min"]) * 7.5,
                )

            _v_score += _v_margin_score
            _v_details["operating_margin"] = {
                "value": _v_operating_margin,
                "criteria": _v_criteria["operating_margin_min"],
                "score": _v_margin_score,
                "passed": _v_operating_margin >= _v_criteria["operating_margin_min"],
            }

            # 통과 기준: 60점 이상 또는 4개 이상 항목 통과
            _v_passed = _v_score >= 60.0 or _v_passed_count >= 4

            _v_details["summary"] = {
                "total_score": _v_score,
                "passed_count": _v_passed_count,
                "total_checks": _v_total_checks,
                "passed": _v_passed,
            }

            return _v_passed, _v_score, _v_details

        except Exception as e:
            self._logger.error(f"기본 분석 스크리닝 오류: {e}", exc_info=True)
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
                "required": _v_criteria["ma_trend_required"],
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
                    _v_rsi_score = max(
                        0.0, 15.0 * ((100 - _v_rsi) / (100 - _v_criteria["rsi_max"]))
                    )

            _v_score += _v_rsi_score
            _v_details["rsi"] = {
                "value": _v_rsi,
                "min_criteria": _v_criteria["rsi_min"],
                "max_criteria": _v_criteria["rsi_max"],
                "score": _v_rsi_score,
                "passed": _v_rsi_pass,
            }

            # 3. 거래량 비율 체크
            _v_volume_ratio = p_stock_data.get("volume_ratio", 1.0)
            _v_volume_pass = _v_volume_ratio >= _v_criteria["volume_ratio_min"]
            if _v_volume_pass:
                _v_volume_score = min(
                    20.0, (_v_volume_ratio / _v_criteria["volume_ratio_min"]) * 10.0
                )
                _v_passed_count += 1
            else:
                _v_volume_score = (
                    _v_volume_ratio / _v_criteria["volume_ratio_min"]
                ) * 10.0

            _v_score += _v_volume_score
            _v_details["volume_ratio"] = {
                "value": _v_volume_ratio,
                "criteria": _v_criteria["volume_ratio_min"],
                "score": _v_volume_score,
                "passed": _v_volume_pass,
            }

            # 4. 1개월 모멘텀 체크
            _v_momentum_1m = p_stock_data.get("momentum_1m", 0.0)
            _v_momentum_pass = _v_momentum_1m >= _v_criteria["momentum_1m_min"]
            if _v_momentum_pass:
                _v_momentum_score = min(
                    15.0,
                    (_v_momentum_1m / max(1.0, _v_criteria["momentum_1m_min"])) * 7.5,
                )
                _v_passed_count += 1
            else:
                _v_momentum_score = max(
                    0.0,
                    (_v_momentum_1m / max(1.0, abs(_v_criteria["momentum_1m_min"])))
                    * 7.5,
                )

            _v_score += _v_momentum_score
            _v_details["momentum_1m"] = {
                "value": _v_momentum_1m,
                "criteria": _v_criteria["momentum_1m_min"],
                "score": _v_momentum_score,
                "passed": _v_momentum_pass,
            }

            # 5. 변동성 체크
            _v_volatility = p_stock_data.get("volatility", 0.2)
            _v_volatility_pass = _v_volatility <= _v_criteria["volatility_max"]
            if _v_volatility_pass:
                _v_volatility_score = 15.0
                _v_passed_count += 1
            else:
                _v_volatility_score = max(
                    0.0,
                    15.0
                    * (
                        1.0
                        - (_v_volatility - _v_criteria["volatility_max"])
                        / _v_criteria["volatility_max"]
                    ),
                )

            _v_score += _v_volatility_score
            _v_details["volatility"] = {
                "value": _v_volatility,
                "criteria": _v_criteria["volatility_max"],
                "score": _v_volatility_score,
                "passed": _v_volatility_pass,
            }

            # 6. 20일 이동평균 기울기 체크
            _v_ma20_slope = self._calculate_ma_slope(p_stock_data)
            _v_slope_pass = _v_ma20_slope >= _v_criteria["ma20_slope_min"]
            if _v_slope_pass:
                _v_slope_score = min(
                    15.0, (_v_ma20_slope / _v_criteria["ma20_slope_min"]) * 7.5
                )
                _v_passed_count += 1
            else:
                _v_slope_score = max(
                    0.0, (_v_ma20_slope / _v_criteria["ma20_slope_min"]) * 7.5
                )

            _v_score += _v_slope_score
            _v_details["ma20_slope"] = {
                "value": _v_ma20_slope,
                "criteria": _v_criteria["ma20_slope_min"],
                "score": _v_slope_score,
                "passed": _v_slope_pass,
            }

            # 통과 기준: 65점 이상 또는 4개 이상 항목 통과
            _v_passed = _v_score >= 65.0 or _v_passed_count >= 4

            _v_details["summary"] = {
                "total_score": _v_score,
                "passed_count": _v_passed_count,
                "total_checks": _v_total_checks,
                "passed": _v_passed,
            }

            return _v_passed, _v_score, _v_details

        except Exception as e:
            self._logger.error(f"기술적 분석 스크리닝 오류: {e}", exc_info=True)
            return False, 0.0, {"error": str(e)}

    def _generate_ohlcv_data(self, p_stock_data: Dict) -> Optional[pd.DataFrame]:
        """OHLCV 데이터 생성 (실제 데이터 또는 시뮬레이션)"""
        try:
            # 실제 OHLCV 데이터가 있는 경우
            if "ohlcv" in p_stock_data and p_stock_data["ohlcv"]:
                return pd.DataFrame(p_stock_data["ohlcv"])

            # 시뮬레이션 데이터 생성
            _v_current_price = p_stock_data.get("current_price", 10000)
            _v_dates = pd.date_range(end=datetime.now(), periods=30, freq="D")

            # 간단한 가격 시뮬레이션
            np.random.seed(42)  # 재현 가능한 결과를 위해
            _v_returns = np.random.normal(0.001, 0.02, 30)  # 일일 수익률
            _v_prices = [_v_current_price]

            for _v_return in _v_returns[1:]:
                _v_prices.append(_v_prices[-1] * (1 + _v_return))

            _v_ohlcv_data = pd.DataFrame(
                {
                    "date": _v_dates,
                    "open": _v_prices,
                    "high": [p * 1.02 for p in _v_prices],
                    "low": [p * 0.98 for p in _v_prices],
                    "close": _v_prices,
                    "volume": np.random.randint(100000, 1000000, 30),
                }
            )

            return _v_ohlcv_data

        except Exception as e:
            self._logger.error(f"OHLCV 데이터 생성 오류: {e}", exc_info=True)
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
                _v_1m_score = min(
                    25.0,
                    (_v_price_momentum_1m / _v_criteria["price_momentum_1m_min"])
                    * 12.5,
                )
                _v_passed_count += 1
            else:
                _v_1m_score = max(
                    0.0,
                    (_v_price_momentum_1m / _v_criteria["price_momentum_1m_min"])
                    * 12.5,
                )

            _v_score += _v_1m_score
            _v_details["price_momentum_1m"] = {
                "value": _v_price_momentum_1m,
                "criteria": _v_criteria["price_momentum_1m_min"],
                "score": _v_1m_score,
                "passed": _v_1m_pass,
            }

            # 2. 3개월 가격 모멘텀 체크
            _v_price_momentum_3m = p_stock_data.get("price_momentum_3m", 0.0)
            _v_3m_pass = _v_price_momentum_3m >= _v_criteria["price_momentum_3m_min"]
            if _v_3m_pass:
                _v_3m_score = min(
                    25.0,
                    (_v_price_momentum_3m / _v_criteria["price_momentum_3m_min"])
                    * 12.5,
                )
                _v_passed_count += 1
            else:
                _v_3m_score = max(
                    0.0,
                    (_v_price_momentum_3m / _v_criteria["price_momentum_3m_min"])
                    * 12.5,
                )

            _v_score += _v_3m_score
            _v_details["price_momentum_3m"] = {
                "value": _v_price_momentum_3m,
                "criteria": _v_criteria["price_momentum_3m_min"],
                "score": _v_3m_score,
                "passed": _v_3m_pass,
            }

            # 3. 거래량 모멘텀 체크
            _v_volume_momentum = p_stock_data.get("volume_momentum", 0.0)
            _v_vol_pass = _v_volume_momentum >= _v_criteria["volume_momentum_min"]
            if _v_vol_pass:
                _v_vol_score = min(
                    20.0,
                    (_v_volume_momentum / _v_criteria["volume_momentum_min"]) * 10.0,
                )
                _v_passed_count += 1
            else:
                _v_vol_score = max(
                    0.0,
                    (_v_volume_momentum / _v_criteria["volume_momentum_min"]) * 10.0,
                )

            _v_score += _v_vol_score
            _v_details["volume_momentum"] = {
                "value": _v_volume_momentum,
                "criteria": _v_criteria["volume_momentum_min"],
                "score": _v_vol_score,
                "passed": _v_vol_pass,
            }

            # 4. 상대강도 체크
            _v_relative_strength = p_stock_data.get("relative_strength", 50.0)
            _v_rs_pass = _v_relative_strength >= _v_criteria["relative_strength_min"]
            if _v_rs_pass:
                _v_rs_score = min(
                    20.0,
                    (_v_relative_strength / _v_criteria["relative_strength_min"])
                    * 10.0,
                )
                _v_passed_count += 1
            else:
                _v_rs_score = (
                    _v_relative_strength / _v_criteria["relative_strength_min"]
                ) * 10.0

            _v_score += _v_rs_score
            _v_details["relative_strength"] = {
                "value": _v_relative_strength,
                "criteria": _v_criteria["relative_strength_min"],
                "score": _v_rs_score,
                "passed": _v_rs_pass,
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
                "passed": _v_ma_convergence,
            }

            # 통과 기준: 70점 이상 또는 3개 이상 항목 통과
            _v_passed = _v_score >= 70.0 or _v_passed_count >= 3

            _v_details["summary"] = {
                "total_score": _v_score,
                "passed_count": _v_passed_count,
                "total_checks": _v_total_checks,
                "passed": _v_passed,
            }

            return _v_passed, _v_score, _v_details

        except Exception as e:
            self._logger.error(f"모멘텀 분석 스크리닝 오류: {e}", exc_info=True)
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
                _v_fundamental_passed, _v_fundamental_score, _v_fundamental_details = (
                    self.screen_by_fundamentals(_v_stock_data)
                )
                _v_technical_passed, _v_technical_score, _v_technical_details = (
                    self.screen_by_technical(_v_stock_data)
                )
                _v_momentum_passed, _v_momentum_score, _v_momentum_details = (
                    self.screen_by_momentum(_v_stock_data)
                )

                # 종합 점수 계산 (가중평균)
                _v_total_score = (
                    _v_fundamental_score * 0.4
                    + _v_technical_score * 0.35  # 기본 분석 40%
                    + _v_momentum_score * 0.25  # 기술적 분석 35%  # 모멘텀 분석 25%
                )

                # 전체 통과 여부 (3개 분야 중 2개 이상 + 종합 점수)
                _v_passed_areas = sum(
                    [
                        _v_fundamental_score >= 45.0,
                        _v_technical_score >= 45.0,
                        _v_momentum_score >= 45.0,
                    ]
                )
                _v_overall_passed = _v_passed_areas >= 2 and _v_total_score >= 60.0

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
                            "total": _v_total_score,
                        },
                    },
                    signals=_v_signals,
                    timestamp=datetime.now(),
                )

                _v_results.append(_v_result)

            except Exception as e:
                self._logger.error(
                    f"종목 {_v_stock_code} 스크리닝 오류: {e}", exc_info=True
                )
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

            # 프로젝트 루트 경로 기준으로 절대 경로 생성
            _v_project_root = Path(__file__).parent.parent.parent
            _v_stock_dir = _v_project_root / "data" / "stock"

            # 가장 최신 종목 리스트 파일 찾기
            _v_stock_list_files = list(_v_stock_dir.glob("krx_stock_list_*.json"))
            if _v_stock_list_files:
                _v_stock_list_file = max(
                    _v_stock_list_files, key=lambda x: x.name
                )  # 가장 최신 파일

                try:
                    with open(_v_stock_list_file, "r", encoding="utf-8") as f:
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

                    self._logger.debug(
                        f"종목 정보 로드 성공: {p_stock_code} → {_v_stock_name} ({_v_market})"
                    )

                except Exception as e:
                    self._logger.warning(f"종목 리스트 파일 로드 실패: {e}")
            else:
                self._logger.warning(f"종목 리스트 파일을 찾을 수 없음: {_v_stock_dir}")

            # 종목 정보가 없으면 기본값 사용
            if not _v_stock_name:
                _v_stock_name = f"종목{p_stock_code}"
                _v_market = (
                    "KOSPI"
                    if p_stock_code.startswith(("0", "1", "2", "3"))
                    else "KOSDAQ"
                )
                self._logger.warning(
                    f"종목 정보 없음, 기본값 사용: {p_stock_code} → {_v_stock_name} ({_v_market})"
                )

            # 섹터 추정 (확장된 매핑 사용)
            _v_sector_map = {
                # 반도체
                "005930": "반도체",
                "000660": "반도체",
                "042700": "반도체",
                "000990": "반도체",
                "006800": "반도체",
                "019170": "반도체",
                "307950": "반도체",
                "189300": "반도체",
                # 인터넷/IT
                "035420": "인터넷",
                "035720": "인터넷",
                "181710": "인터넷",
                "036570": "인터넷",
                "030000": "인터넷",
                "060250": "인터넷",
                "122870": "인터넷",
                "192820": "인터넷",
                # 자동차
                "005380": "자동차",
                "000270": "자동차",
                "012330": "자동차",
                "161390": "자동차",
                "204320": "자동차",
                "006400": "자동차부품",
                "077500": "자동차부품",
                # 바이오/제약
                "068270": "바이오",
                "207940": "바이오",
                "086900": "바이오",
                "328130": "바이오",
                "196170": "바이오",
                "145720": "바이오",
                "006280": "제약",
                "009420": "제약",
                "185750": "제약",
                "000100": "제약",
                "128940": "제약",
                # 화학
                "051910": "화학",
                "001570": "화학",
                "011170": "화학",
                "002380": "화학",
                "001040": "화학",
                "004020": "화학",
                "014680": "화학",
                "005420": "화학",
                # 에너지/전력
                "096770": "에너지",
                "010950": "에너지",
                "267250": "에너지",
                "015760": "전력",
                "001500": "전력",
                "153460": "전력",
                "092220": "전력",
                # 통신
                "034730": "통신",
                "017670": "통신",
                "030200": "통신",
                "137310": "통신",
                # 전자
                "066570": "전자",
                "009150": "전자",
                "000370": "전자",
                "018260": "전자",
                "108320": "전자",
                "267270": "전자",
                # 배터리
                "373220": "배터리",
                # 금융
                "055550": "금융",
                "316140": "금융",
                "024110": "금융",
                "000810": "금융",
                "032830": "금융",
                "138930": "금융",
                "105560": "금융",
                # 건설
                "028260": "건설",
                "006360": "건설",
                "047040": "건설",
                "025540": "건설",
                "052690": "건설",
                # 철강
                "005490": "철강",
                "003670": "철강",
                "014820": "철강",
                "001230": "철강",
                # 조선
                "009540": "조선",
                "067630": "조선",
                "042660": "조선",
                # 항공
                "003490": "항공",
                "047810": "항공",
                # 엔터테인먼트
                "041510": "엔터",
                "376300": "엔터",
            }

            # 종목 코드 패턴 기반 섹터 추정
            _v_sector = _v_sector_map.get(p_stock_code, None)
            if not _v_sector:
                # 실제 데이터 기반 다단계 섹터 배정 시스템
                _v_code_int = int(p_stock_code) if p_stock_code.isdigit() else 0

                # 1단계: 확장된 종목명 기반 분류
                _v_name_lower = _v_stock_name.lower()

                # 바이오/제약
                if any(
                    keyword in _v_name_lower
                    for keyword in [
                        "바이오",
                        "bio",
                        "제약",
                        "의료",
                        "헬스",
                        "병원",
                        "메디",
                        "medi",
                        "팜",
                        "pharm",
                        "생명과학",
                    ]
                ):
                    _v_sector = "바이오"
                # IT/테크
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "테크",
                        "tech",
                        "솔루션",
                        "소프트",
                        "soft",
                        "시스템",
                        "system",
                        "네트워크",
                        "it",
                        "데이터",
                        "ai",
                    ]
                ):
                    _v_sector = "인터넷"
                # 전자
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "전자",
                        "electronic",
                        "반도체",
                        "semi",
                        "디스플레이",
                        "led",
                        "lcd",
                        "칩",
                        "chip",
                    ]
                ):
                    _v_sector = "전자"
                # 화학
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "화학",
                        "chemical",
                        "케미",
                        "chem",
                        "정유",
                        "석유",
                        "플라스틱",
                        "고무",
                    ]
                ):
                    _v_sector = "화학"
                # 금융
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "금융",
                        "finance",
                        "은행",
                        "bank",
                        "증권",
                        "보험",
                        "카드",
                        "캐피탈",
                        "리츠",
                        "reit",
                    ]
                ):
                    _v_sector = "금융"
                # 건설/철강
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "건설",
                        "construction",
                        "철강",
                        "steel",
                        "스틸",
                        "제철",
                        "건축",
                        "토목",
                    ]
                ):
                    _v_sector = "건설"
                # 에너지
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "에너지",
                        "energy",
                        "전력",
                        "power",
                        "발전",
                        "태양광",
                        "풍력",
                        "가스",
                        "gas",
                    ]
                ):
                    _v_sector = "에너지"
                # 통신
                elif any(
                    keyword in _v_name_lower
                    for keyword in ["통신", "telecom", "kt", "sk텔레콤", "텔레콤"]
                ):
                    _v_sector = "통신"
                # 자동차
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "자동차",
                        "auto",
                        "현대차",
                        "기아",
                        "타이어",
                        "모터",
                        "모비스",
                    ]
                ):
                    _v_sector = "자동차"
                # 엔터테인먼트/미디어
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "엔터",
                        "entertainment",
                        "방송",
                        "미디어",
                        "media",
                        "게임",
                        "game",
                        "콘텐츠",
                    ]
                ):
                    _v_sector = "엔터"
                # 조선/해운
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "조선",
                        "shipbuilding",
                        "해운",
                        "선박",
                        "항만",
                        "해양",
                    ]
                ):
                    _v_sector = "조선"
                # 항공
                elif any(
                    keyword in _v_name_lower
                    for keyword in ["항공", "airline", "에어", "air", "항공기"]
                ):
                    _v_sector = "항공"
                # 식품
                elif any(
                    keyword in _v_name_lower
                    for keyword in ["식품", "food", "푸드", "농업", "농산", "수산"]
                ):
                    _v_sector = "식품"
                # 홀딩스/투자 (특수 분류)
                elif any(
                    keyword in _v_name_lower
                    for keyword in [
                        "홀딩스",
                        "holding",
                        "지주",
                        "투자",
                        "invest",
                        "스팩",
                        "spac",
                    ]
                ):
                    _v_sector = "홀딩스"
                else:
                    # 2단계: 더 균등한 숫자 패턴 기반 분류
                    _v_remainder = (
                        _v_code_int % 1000
                    )  # 더 세밀한 분배를 위해 1000으로 변경
                    if _v_remainder < 100:
                        _v_sector = "바이오"
                    elif _v_remainder < 200:
                        _v_sector = "전자"
                    elif _v_remainder < 300:
                        _v_sector = "인터넷"
                    elif _v_remainder < 400:
                        _v_sector = "화학"
                    elif _v_remainder < 500:
                        _v_sector = "금융"
                    elif _v_remainder < 600:
                        _v_sector = "건설"
                    elif _v_remainder < 700:
                        _v_sector = "에너지"
                    elif _v_remainder < 800:
                        _v_sector = "자동차"
                    elif _v_remainder < 900:
                        _v_sector = "엔터"
                    else:
                        _v_sector = "기타"

            # 한국투자증권 API를 통한 실제 데이터 조회
            try:
                # 1. 현재가 및 기본 정보 조회
                price_data = self._rest_client.get_current_price(p_stock_code)
                if not price_data:
                    self._logger.warning(f"현재가 조회 실패 - {p_stock_code}")
                    return None

                _v_current_price = price_data.get("current_price", 0)
                _v_volume = price_data.get("volume", 0)

                # 2. 종목 상세 정보 조회 (시가총액, PER, PBR 등)
                stock_info = self._rest_client.get_stock_info(p_stock_code)
                if stock_info:
                    _v_market_cap = stock_info.get("market_cap", 0)
                    _v_per = stock_info.get("per", 0)
                    _v_pbr = stock_info.get("pbr", 0)
                else:
                    _v_market_cap = 0
                    _v_per = 0
                    _v_pbr = 0

                # 3. 일봉 데이터 조회 (기술적 지표 계산용)
                chart_df = self._rest_client.get_daily_chart(p_stock_code, period_days=120)

                if chart_df is not None and len(chart_df) > 0:
                    # 이동평균 계산
                    if len(chart_df) >= 20:
                        _v_ma_20 = chart_df["close"].tail(20).mean()
                    else:
                        _v_ma_20 = _v_current_price

                    if len(chart_df) >= 60:
                        _v_ma_60 = chart_df["close"].tail(60).mean()
                    else:
                        _v_ma_60 = _v_current_price

                    if len(chart_df) >= 120:
                        _v_ma_120 = chart_df["close"].tail(120).mean()
                    else:
                        _v_ma_120 = _v_current_price

                    # RSI 계산 (14일 기준) - TechnicalIndicators 사용 (SSOT)
                    prices_list = chart_df["close"].values.tolist()
                    _v_rsi = TechnicalIndicators.calculate_rsi(prices_list, p_period=14)

                    # 거래량 비율 (최근 20일 평균 대비)
                    if len(chart_df) >= 20:
                        avg_volume = chart_df["volume"].tail(20).mean()
                        _v_volume_ratio = _v_volume / avg_volume if avg_volume > 0 else 1.0
                    else:
                        _v_volume_ratio = 1.0

                    # 가격 모멘텀 계산
                    if len(chart_df) >= 20:  # 1개월 (약 20 거래일)
                        price_1m_ago = chart_df["close"].iloc[-20]
                        _v_price_momentum_1m = ((_v_current_price - price_1m_ago) / price_1m_ago) * 100
                    else:
                        _v_price_momentum_1m = 0.0

                    if len(chart_df) >= 60:  # 3개월 (약 60 거래일)
                        price_3m_ago = chart_df["close"].iloc[-60]
                        _v_price_momentum_3m = ((_v_current_price - price_3m_ago) / price_3m_ago) * 100
                    else:
                        _v_price_momentum_3m = 0.0

                    if len(chart_df) >= 120:  # 6개월 (약 120 거래일)
                        price_6m_ago = chart_df["close"].iloc[-120]
                        _v_price_momentum_6m = ((_v_current_price - price_6m_ago) / price_6m_ago) * 100
                    else:
                        _v_price_momentum_6m = 0.0

                    # 변동성 계산 (20일 표준편차를 평균으로 나눔)
                    if len(chart_df) >= 20:
                        returns = chart_df["close"].pct_change().tail(20)
                        _v_volatility = returns.std() * np.sqrt(252)  # 연율화
                    else:
                        _v_volatility = 0.0
                else:
                    # 차트 데이터 없으면 기본값
                    _v_ma_20 = _v_current_price
                    _v_ma_60 = _v_current_price
                    _v_ma_120 = _v_current_price
                    _v_rsi = 50.0
                    _v_volume_ratio = 1.0
                    _v_price_momentum_1m = 0.0
                    _v_price_momentum_3m = 0.0
                    _v_price_momentum_6m = 0.0
                    _v_volatility = 0.0

                self._logger.debug(
                    f"실제 데이터 조회 완료 - {p_stock_code} ({_v_stock_name}): 가격={_v_current_price:,}, 거래량={_v_volume:,}"
                )

            except Exception as e:
                self._logger.error(f"주식 데이터 조회 실패 - {p_stock_code}: {e}", exc_info=True)
                return None

            # 종합 데이터 구성
            _v_stock_data = {
                "stock_code": p_stock_code,
                "stock_name": _v_stock_name,
                "sector": _v_sector,
                "market": _v_market,
                "market_cap": _v_market_cap,
                "current_price": _v_current_price,
                "volume": _v_volume,
                # 재무 데이터 (API에서 조회한 실제 값 또는 기본값)
                "roe": 0.0,  # TODO: 재무제표 API 연동 시 실제 데이터로 교체
                "per": _v_per,  # get_stock_info()에서 조회
                "pbr": _v_pbr,  # get_stock_info()에서 조회
                "debt_ratio": 0.0,  # TODO: 재무제표 API 연동 시 실제 데이터로 교체
                "revenue_growth": 0.0,  # TODO: 재무제표 API 연동 시 실제 데이터로 교체
                "operating_margin": 0.0,  # TODO: 재무제표 API 연동 시 실제 데이터로 교체
                # 기술적 데이터 (실제 계산값)
                "ma_20": _v_ma_20,
                "ma_60": _v_ma_60,
                "ma_120": _v_ma_120,
                "rsi": _v_rsi,
                "volume_ratio": _v_volume_ratio,
                "price_momentum_1m": _v_price_momentum_1m,
                "volatility": _v_volatility,
                # 모멘텀 데이터 (실제 계산값)
                "relative_strength": 0.0,  # TODO: 시장 대비 상대 강도 계산 로직 추가
                "price_momentum_3m": _v_price_momentum_3m,
                "price_momentum_6m": _v_price_momentum_6m,
                "volume_momentum": 0.0,  # TODO: 거래량 모멘텀 계산 로직 추가
                "sector_momentum": 0.0,  # TODO: 섹터 모멘텀 계산 로직 추가
            }

            return _v_stock_data

        except Exception as e:
            self._logger.error(
                f"주식 데이터 수집 오류 - {p_stock_code}: {e}", exc_info=True
            )
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
                "기타": 15.0,
            }

            return _v_sector_per.get(p_sector, 15.0)

        except Exception as e:
            self._logger.error(f"섹터 평균 PER 조회 오류: {e}", exc_info=True)
            return 15.0

    def _convert_numpy_types(self, p_obj):
        """NumPy 타입을 Python 기본 타입으로 변환

        Args:
            p_obj: 변환할 객체

        Returns:
            변환된 객체
        """
        import numpy as np

        if isinstance(p_obj, np.bool_):
            return bool(p_obj)
        elif isinstance(p_obj, np.integer):
            return int(p_obj)
        elif isinstance(p_obj, np.floating):
            return float(p_obj)
        elif isinstance(p_obj, np.ndarray):
            return p_obj.tolist()
        elif isinstance(p_obj, dict):
            return {
                key: self._convert_numpy_types(value) for key, value in p_obj.items()
            }
        elif isinstance(p_obj, list):
            return [self._convert_numpy_types(item) for item in p_obj]
        else:
            return p_obj

    def save_screening_results(
        self, p_results: List[Dict], p_filename: Optional[str] = None
    ) -> bool:
        """스크리닝 결과 저장 (DB 우선, 실패 시 JSON 폴백)

        Args:
            p_results: 스크리닝 결과 리스트
            p_filename: 저장할 파일명 (선택사항)

        Returns:
            저장 성공 여부
        """
        try:
            _v_screening_date = datetime.now().date()

            # === 1. DB에 저장 시도 ===
            db_saved = self._save_screening_to_db(p_results, _v_screening_date)
            if db_saved:
                self._logger.info(f"스크리닝 결과 DB 저장 완료: {len(p_results)}건")
                return True

            # === 2. DB 실패 시에만 JSON 폴백 저장 ===
            self._logger.warning("스크리닝 결과 DB 저장 실패 - JSON 폴백 저장")

            if not p_filename:
                _v_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                p_filename = f"screening_results_{_v_timestamp}.json"

            _v_filepath = os.path.join("data/watchlist", p_filename)

            # 디렉토리 생성
            os.makedirs(os.path.dirname(_v_filepath), exist_ok=True)

            # NumPy 타입을 Python 기본 타입으로 변환
            _v_converted_results = self._convert_numpy_types(p_results)

            _v_save_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "total_count": len(_v_converted_results),
                "passed_count": len(
                    [r for r in _v_converted_results if r.get("overall_passed", False)]
                ),
                "results": _v_converted_results,
                "metadata": {
                    "source": "stock_screener",
                    "criteria": self._convert_numpy_types(
                        getattr(self, "_v_screening_criteria", {})
                    ),
                    "db_fallback": True,
                },
            }

            with open(_v_filepath, "w", encoding="utf-8") as f:
                json.dump(_v_save_data, f, ensure_ascii=False, indent=2)

            self._logger.info(f"스크리닝 결과 JSON 폴백 저장 완료: {_v_filepath}")
            return True

        except Exception as e:
            self._logger.error(f"스크리닝 결과 저장 오류: {e}", exc_info=True)
            return False

    def _save_screening_to_db(self, p_results: List[Dict], p_screening_date) -> bool:
        """스크리닝 결과를 DB에 저장

        Args:
            p_results: 스크리닝 결과 리스트
            p_screening_date: 스크리닝 날짜

        Returns:
            저장 성공 여부
        """
        try:
            from core.database.session import DatabaseSession
            from core.database.models import ScreeningResult

            db = DatabaseSession()
            with db.get_session() as session:
                # 기존 데이터 삭제 (같은 날짜)
                session.query(ScreeningResult).filter(
                    ScreeningResult.screening_date == p_screening_date
                ).delete()

                # 새 데이터 저장
                saved_count = 0
                for result in p_results:
                    # 중첩 딕셔너리에서 점수 추출
                    _fundamental = result.get("fundamental", {})
                    _technical = result.get("technical", {})
                    _momentum = result.get("momentum", {})
                    _fundamental_details = _fundamental.get("details", {})

                    # dict가 아닌 숫자 값만 추출하는 헬퍼
                    def _safe_float(val):
                        if val is None or isinstance(val, dict):
                            return None
                        try:
                            return float(val)
                        except (TypeError, ValueError):
                            return None

                    screening_record = ScreeningResult(
                        screening_date=p_screening_date,
                        stock_code=result.get("stock_code", ""),
                        stock_name=result.get("stock_name", ""),
                        total_score=_safe_float(result.get("overall_score", 0.0)),
                        fundamental_score=_safe_float(_fundamental.get("score", 0.0)),
                        technical_score=_safe_float(_technical.get("score", 0.0)),
                        momentum_score=_safe_float(_momentum.get("score", 0.0)),
                        passed=1 if result.get("overall_passed", False) else 0,
                        roe=_safe_float(_fundamental_details.get("roe")),
                        per=_safe_float(_fundamental_details.get("per")),
                        pbr=_safe_float(_fundamental_details.get("pbr")),
                        debt_ratio=_safe_float(_fundamental_details.get("debt_ratio")),
                    )
                    session.add(screening_record)
                    saved_count += 1

                session.commit()
                self._logger.info(f"DB 저장 완료: {saved_count}건")
                return True

        except Exception as e:
            self._logger.error(f"스크리닝 결과 DB 저장 실패: {e}", exc_info=True)
            return False

    def _check_ma_trend(self, p_stock_data: Dict) -> bool:
        """이동평균 추세 체크"""
        try:
            _v_ma_20 = p_stock_data.get("ma_20", 0.0)
            _v_ma_60 = p_stock_data.get("ma_60", 0.0)
            _v_ma_120 = p_stock_data.get("ma_120", 0.0)
            _v_current_price = p_stock_data.get("current_price", 0.0)

            # 상향 배열 체크: 현재가 > 20일선 > 60일선 > 120일선
            return _v_current_price > _v_ma_20 > _v_ma_60 > _v_ma_120
        except Exception:
            return False

    def _calculate_ma_slope(self, p_stock_data: Dict) -> float:
        """20일 이동평균 기울기 계산"""
        try:
            _v_ohlcv_data = self._generate_ohlcv_data(p_stock_data)
            if _v_ohlcv_data is None or len(_v_ohlcv_data) < 20:
                return 0.0

            # 20일 이동평균 계산
            _v_ohlcv_data["ma_20"] = _v_ohlcv_data["close"].rolling(window=20).mean()

            # 최근 5일간의 기울기 계산
            _v_ma_values = _v_ohlcv_data["ma_20"].dropna().tail(5)
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

    def _screen_single_stock_static(self, p_stock_code: str) -> Optional[Dict]:
        """정적 단일 종목 스크리닝 메서드 (병렬 처리용)"""
        try:
            # 주식 데이터 수집
            _v_stock_data = self._fetch_stock_data(p_stock_code)
            if not _v_stock_data:
                return None

            # 각 스크리닝 실행
            _v_fundamental_passed, _v_fundamental_score, _v_fundamental_details = (
                self.screen_by_fundamentals(_v_stock_data)
            )
            _v_technical_passed, _v_technical_score, _v_technical_details = (
                self.screen_by_technical(_v_stock_data)
            )
            _v_momentum_passed, _v_momentum_score, _v_momentum_details = (
                self.screen_by_momentum(_v_stock_data)
            )

            # 종합 결과 계산 (가중평균 사용)
            _v_overall_score = (
                _v_fundamental_score * 0.4
                + _v_technical_score * 0.35  # 기본 분석 40%
                + _v_momentum_score * 0.25  # 기술적 분석 35%  # 모멘텀 분석 25%
            )

            # 전체 통과 여부 (3개 분야 중 2개 이상 + 종합 점수)
            _v_passed_areas = sum(
                [
                    _v_fundamental_score >= 45.0,
                    _v_technical_score >= 45.0,
                    _v_momentum_score >= 45.0,
                ]
            )
            _v_overall_passed = _v_passed_areas >= 2 and _v_overall_score >= 60.0

            _v_result = {
                "stock_code": p_stock_code,
                "stock_name": _v_stock_data.get("stock_name", ""),
                "sector": _v_stock_data.get("sector", ""),
                "screening_timestamp": datetime.now().isoformat(),
                "overall_passed": _v_overall_passed,
                "overall_score": round(_v_overall_score, 2),
                "fundamental": {
                    "passed": _v_fundamental_passed,
                    "score": round(_v_fundamental_score, 2),
                    "details": _v_fundamental_details,
                },
                "technical": {
                    "passed": _v_technical_passed,
                    "score": round(_v_technical_score, 2),
                    "details": _v_technical_details,
                },
                "momentum": {
                    "passed": _v_momentum_passed,
                    "score": round(_v_momentum_score, 2),
                    "details": _v_momentum_details,
                },
            }

            return _v_result

        except Exception as e:
            self._logger.error(
                f"종목 스크리닝 오류 ({p_stock_code}): {e}", exc_info=True
            )
            return None
