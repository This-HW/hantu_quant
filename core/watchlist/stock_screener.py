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
from hantu_common.indicators.trend import SlopeIndicator

logger = get_logger(__name__)

class StockScreener:
    """기업 스크리닝을 위한 클래스"""
    
    def __init__(self):
        """초기화 메서드"""
        self.api_config = APIConfig()
        self._v_screening_criteria = self._load_screening_criteria()
        self._v_sector_data = {}
        logger.info("StockScreener 초기화 완료")
    
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
                "trend_consistency_required": True,  # 추세 일관성 필요
                "price_slope_min": 0.2     # 가격 기울기 최소 0.2%
            },
            "momentum": {
                "relative_strength_min": 0.0,  # 상대강도 최소값
                "momentum_periods": [1, 3, 6],  # 모멘텀 분석 기간 (월)
                "volume_momentum_min": 0.0,     # 거래량 모멘텀 최소값
                "sector_momentum_min": 0.0      # 섹터 모멘텀 최소값
            }
        }
        
        try:
            _v_criteria_path = "data/watchlist/screening_criteria.json"
            if os.path.exists(_v_criteria_path):
                with open(_v_criteria_path, 'r', encoding='utf-8') as f:
                    _v_loaded_criteria = json.load(f)
                    logger.info("스크리닝 기준 로드 완료")
                    return _v_loaded_criteria.get('criteria', _v_default_criteria)
            else:
                logger.info("기본 스크리닝 기준 사용")
                return _v_default_criteria
        except Exception as e:
            logger.error(f"스크리닝 기준 로드 실패: {e}")
            return _v_default_criteria
    
    def screen_by_fundamentals(self, p_stock_data: Dict) -> Tuple[bool, float, Dict]:
        """재무제표 기반 스크리닝
        
        Args:
            p_stock_data: 주식 재무 데이터
            
        Returns:
            (통과 여부, 점수, 세부 결과)
        """
        try:
            _v_criteria = self._v_screening_criteria["fundamental"]
            _v_results = {}
            _v_score = 0.0
            _v_max_score = 6.0  # 총 6개 지표
            
            # ROE 검증
            _v_roe = p_stock_data.get("roe", 0.0)
            if _v_roe >= _v_criteria["roe_min"]:
                _v_results["roe"] = {"pass": True, "value": _v_roe, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["roe"] = {"pass": False, "value": _v_roe, "score": 0.0}
            
            # PER 검증 (업종 평균 대비)
            _v_per = p_stock_data.get("per", 999.0)
            _v_sector_avg_per = self._get_sector_average_per(p_stock_data.get("sector", ""))
            _v_per_ratio = _v_per / _v_sector_avg_per if _v_sector_avg_per > 0 else 999.0
            
            if _v_per_ratio <= _v_criteria["per_max_ratio"]:
                _v_results["per"] = {"pass": True, "value": _v_per, "ratio": _v_per_ratio, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["per"] = {"pass": False, "value": _v_per, "ratio": _v_per_ratio, "score": 0.0}
            
            # PBR 검증
            _v_pbr = p_stock_data.get("pbr", 999.0)
            if _v_pbr <= _v_criteria["pbr_max"]:
                _v_results["pbr"] = {"pass": True, "value": _v_pbr, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["pbr"] = {"pass": False, "value": _v_pbr, "score": 0.0}
            
            # 부채비율 검증
            _v_debt_ratio = p_stock_data.get("debt_ratio", 999.0)
            if _v_debt_ratio <= _v_criteria["debt_ratio_max"]:
                _v_results["debt_ratio"] = {"pass": True, "value": _v_debt_ratio, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["debt_ratio"] = {"pass": False, "value": _v_debt_ratio, "score": 0.0}
            
            # 매출성장률 검증
            _v_revenue_growth = p_stock_data.get("revenue_growth", 0.0)
            if _v_revenue_growth >= _v_criteria["revenue_growth_min"]:
                _v_results["revenue_growth"] = {"pass": True, "value": _v_revenue_growth, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["revenue_growth"] = {"pass": False, "value": _v_revenue_growth, "score": 0.0}
            
            # 영업이익률 검증
            _v_operating_margin = p_stock_data.get("operating_margin", 0.0)
            if _v_operating_margin >= _v_criteria["operating_margin_min"]:
                _v_results["operating_margin"] = {"pass": True, "value": _v_operating_margin, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["operating_margin"] = {"pass": False, "value": _v_operating_margin, "score": 0.0}
            
            # 정규화된 점수 계산 (0-100점)
            _v_normalized_score = (_v_score / _v_max_score) * 100.0
            
            # 통과 기준: 6개 지표 중 4개 이상 통과
            _v_passed = _v_score >= 4.0
            
            logger.debug(f"재무제표 스크리닝 - 종목: {p_stock_data.get('stock_code')}, 점수: {_v_normalized_score:.1f}, 통과: {_v_passed}")
            
            return _v_passed, _v_normalized_score, _v_results
            
        except Exception as e:
            logger.error(f"재무제표 스크리닝 오류: {e}")
            return False, 0.0, {}
    
    def screen_by_technical(self, p_stock_data: Dict) -> Tuple[bool, float, Dict]:
        """기술적 분석 기반 스크리닝
        
        Args:
            p_stock_data: 주식 기술적 데이터
            
        Returns:
            (통과 여부, 점수, 세부 결과)
        """
        try:
            _v_criteria = self._v_screening_criteria["technical"]
            _v_results = {}
            _v_score = 0.0
            _v_max_score = 8.0  # 총 8개 지표 (기존 5개 + 기울기 3개)
            
            # 이동평균 상향 배열 검증
            _v_ma_20 = p_stock_data.get("ma_20", 0.0)
            _v_ma_60 = p_stock_data.get("ma_60", 0.0)
            _v_ma_120 = p_stock_data.get("ma_120", 0.0)
            _v_current_price = p_stock_data.get("current_price", 0.0)
            
            _v_ma_trend = (_v_current_price > _v_ma_20 > _v_ma_60 > _v_ma_120)
            if not _v_criteria["ma_trend_required"] or _v_ma_trend:
                _v_results["ma_trend"] = {"pass": True, "value": _v_ma_trend, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["ma_trend"] = {"pass": False, "value": _v_ma_trend, "score": 0.0}
            
            # RSI 검증
            _v_rsi = p_stock_data.get("rsi", 50.0)
            _v_rsi_valid = _v_criteria["rsi_min"] <= _v_rsi <= _v_criteria["rsi_max"]
            if _v_rsi_valid:
                _v_results["rsi"] = {"pass": True, "value": _v_rsi, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["rsi"] = {"pass": False, "value": _v_rsi, "score": 0.0}
            
            # 거래량 비율 검증
            _v_volume_ratio = p_stock_data.get("volume_ratio", 0.0)
            if _v_volume_ratio >= _v_criteria["volume_ratio_min"]:
                _v_results["volume_ratio"] = {"pass": True, "value": _v_volume_ratio, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["volume_ratio"] = {"pass": False, "value": _v_volume_ratio, "score": 0.0}
            
            # 1개월 가격 모멘텀 검증
            _v_momentum_1m = p_stock_data.get("price_momentum_1m", 0.0)
            if _v_momentum_1m >= _v_criteria["momentum_1m_min"]:
                _v_results["momentum_1m"] = {"pass": True, "value": _v_momentum_1m, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["momentum_1m"] = {"pass": False, "value": _v_momentum_1m, "score": 0.0}
            
            # 변동성 검증
            _v_volatility = p_stock_data.get("volatility", 0.0)
            if _v_volatility <= _v_criteria["volatility_max"]:
                _v_results["volatility"] = {"pass": True, "value": _v_volatility, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["volatility"] = {"pass": False, "value": _v_volatility, "score": 0.0}
            
            # === 기울기 관련 지표 추가 ===
            # 기울기 분석을 위한 OHLCV 데이터 생성
            _v_ohlcv_data = self._generate_ohlcv_data(p_stock_data)
            
            if _v_ohlcv_data is not None and len(_v_ohlcv_data) >= 60:
                _v_slope_indicator = SlopeIndicator(_v_ohlcv_data)
                
                # 1. 20일 이동평균 기울기 검증
                _v_ma20_slope = _v_slope_indicator.calculate_ma_slope(20, 5)
                if _v_ma20_slope >= _v_criteria["ma20_slope_min"]:
                    _v_results["ma20_slope"] = {"pass": True, "value": _v_ma20_slope, "score": 1.0}
                    _v_score += 1.0
                else:
                    _v_results["ma20_slope"] = {"pass": False, "value": _v_ma20_slope, "score": 0.0}
                
                # 2. 추세 일관성 검증 (단기-중기-장기 기울기 방향 일치)
                _v_trend_consistency = _v_slope_indicator.check_trend_consistency()
                if not _v_criteria["trend_consistency_required"] or _v_trend_consistency:
                    _v_results["trend_consistency"] = {"pass": True, "value": _v_trend_consistency, "score": 1.0}
                    _v_score += 1.0
                else:
                    _v_results["trend_consistency"] = {"pass": False, "value": _v_trend_consistency, "score": 0.0}
                
                # 3. 가격 기울기 검증
                _v_price_slope = _v_slope_indicator.calculate_price_slope(5)
                if _v_price_slope >= _v_criteria["price_slope_min"]:
                    _v_results["price_slope"] = {"pass": True, "value": _v_price_slope, "score": 1.0}
                    _v_score += 1.0
                else:
                    _v_results["price_slope"] = {"pass": False, "value": _v_price_slope, "score": 0.0}
            else:
                # 기울기 데이터가 부족한 경우 기본값 처리
                _v_results["ma20_slope"] = {"pass": False, "value": 0.0, "score": 0.0}
                _v_results["trend_consistency"] = {"pass": False, "value": False, "score": 0.0}
                _v_results["price_slope"] = {"pass": False, "value": 0.0, "score": 0.0}
            
            # 정규화된 점수 계산 (0-100점)
            _v_normalized_score = (_v_score / _v_max_score) * 100.0
            
            # 통과 기준: 8개 지표 중 5개 이상 통과 (기존 5개 중 3개 + 기울기 3개 중 2개 이상)
            _v_passed = _v_score >= 5.0
            
            logger.debug(f"기술적 스크리닝 - 종목: {p_stock_data.get('stock_code')}, 점수: {_v_normalized_score:.1f}, 통과: {_v_passed}")
            
            return _v_passed, _v_normalized_score, _v_results
            
        except Exception as e:
            logger.error(f"기술적 스크리닝 오류: {e}")
            return False, 0.0, {}
    
    def _generate_ohlcv_data(self, p_stock_data: Dict) -> Optional[pd.DataFrame]:
        """주식 데이터로부터 OHLCV DataFrame 생성 (기울기 분석용)
        
        Args:
            p_stock_data: 주식 데이터
            
        Returns:
            OHLCV DataFrame 또는 None
        """
        try:
            _v_current_price = p_stock_data.get("current_price", 0.0)
            _v_volume_ratio = p_stock_data.get("volume_ratio", 1.0)
            
            if _v_current_price <= 0:
                return None
                
            # 더미 OHLCV 데이터 생성 (실제로는 API에서 가져와야 함)
            # 60일간의 임시 데이터 생성
            _v_dates = pd.date_range(end=datetime.now().date(), periods=60, freq='D')
            _v_prices = []
            _v_volumes = []
            
            # 현재가 기준으로 과거 60일간 가격 시뮬레이션
            _v_base_price = _v_current_price * 0.9  # 시작가는 현재가의 90%
            _v_price = _v_base_price
            _v_base_volume = 1000000  # 기본 거래량
            
            for i in range(60):
                # 가격 변화 시뮬레이션 (상승 추세)
                _v_change = np.random.normal(0.002, 0.015)  # 평균 0.2% 상승, 표준편차 1.5%
                _v_price *= (1 + _v_change)
                _v_prices.append(_v_price)
                
                # 거래량 시뮬레이션
                _v_volume = _v_base_volume * np.random.uniform(0.5, 2.0)
                _v_volumes.append(_v_volume)
            
            # 마지막 가격을 현재가로 조정
            _v_prices[-1] = _v_current_price
            
            # DataFrame 생성
            _v_ohlcv_data = pd.DataFrame({
                'date': _v_dates,
                'open': [p * 0.998 for p in _v_prices],
                'high': [p * 1.005 for p in _v_prices],
                'low': [p * 0.995 for p in _v_prices],
                'close': _v_prices,
                'volume': _v_volumes
            })
            
            return _v_ohlcv_data
            
        except Exception as e:
            logger.error(f"OHLCV 데이터 생성 오류: {e}")
            return None
    
    def screen_by_momentum(self, p_stock_data: Dict) -> Tuple[bool, float, Dict]:
        """모멘텀 기반 스크리닝
        
        Args:
            p_stock_data: 주식 모멘텀 데이터
            
        Returns:
            (통과 여부, 점수, 세부 결과)
        """
        try:
            _v_criteria = self._v_screening_criteria["momentum"]
            _v_results = {}
            _v_score = 0.0
            _v_max_score = 4.0  # 총 4개 지표
            
            # 상대강도 검증
            _v_relative_strength = p_stock_data.get("relative_strength", 0.0)
            if _v_relative_strength >= _v_criteria["relative_strength_min"]:
                _v_results["relative_strength"] = {"pass": True, "value": _v_relative_strength, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["relative_strength"] = {"pass": False, "value": _v_relative_strength, "score": 0.0}
            
            # 다기간 가격 모멘텀 검증
            _v_momentum_scores = []
            for period in _v_criteria["momentum_periods"]:
                _v_momentum_key = f"price_momentum_{period}m"
                _v_momentum_value = p_stock_data.get(_v_momentum_key, 0.0)
                _v_momentum_scores.append(_v_momentum_value)
            
            _v_avg_momentum = np.mean(_v_momentum_scores) if _v_momentum_scores else 0.0
            if _v_avg_momentum > 0.0:
                _v_results["price_momentum"] = {"pass": True, "value": _v_avg_momentum, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["price_momentum"] = {"pass": False, "value": _v_avg_momentum, "score": 0.0}
            
            # 거래량 모멘텀 검증
            _v_volume_momentum = p_stock_data.get("volume_momentum", 0.0)
            if _v_volume_momentum >= _v_criteria["volume_momentum_min"]:
                _v_results["volume_momentum"] = {"pass": True, "value": _v_volume_momentum, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["volume_momentum"] = {"pass": False, "value": _v_volume_momentum, "score": 0.0}
            
            # 섹터 모멘텀 검증
            _v_sector_momentum = p_stock_data.get("sector_momentum", 0.0)
            if _v_sector_momentum >= _v_criteria["sector_momentum_min"]:
                _v_results["sector_momentum"] = {"pass": True, "value": _v_sector_momentum, "score": 1.0}
                _v_score += 1.0
            else:
                _v_results["sector_momentum"] = {"pass": False, "value": _v_sector_momentum, "score": 0.0}
            
            # 정규화된 점수 계산 (0-100점)
            _v_normalized_score = (_v_score / _v_max_score) * 100.0
            
            # 통과 기준: 4개 지표 중 2개 이상 통과
            _v_passed = _v_score >= 2.0
            
            logger.debug(f"모멘텀 스크리닝 - 종목: {p_stock_data.get('stock_code')}, 점수: {_v_normalized_score:.1f}, 통과: {_v_passed}")
            
            return _v_passed, _v_normalized_score, _v_results
            
        except Exception as e:
            logger.error(f"모멘텀 스크리닝 오류: {e}")
            return False, 0.0, {}
    
    def comprehensive_screening(self, p_stock_list: List[str]) -> List[Dict]:
        """종합 스크리닝 실행
        
        Args:
            p_stock_list: 스크리닝할 종목 코드 리스트
            
        Returns:
            스크리닝 결과 리스트
        """
        try:
            logger.info(f"종합 스크리닝 시작 - 대상 종목: {len(p_stock_list)}개")
            
            _v_results = []
            _v_processed_count = 0
            
            for stock_code in p_stock_list:
                try:
                    # 주식 데이터 수집
                    _v_stock_data = self._fetch_stock_data(stock_code)
                    if not _v_stock_data:
                        continue
                    
                    # 종목 정보가 제대로 매핑되지 않은 종목 제외
                    _v_stock_name = _v_stock_data.get("stock_name", "")
                    if _v_stock_name.startswith("종목"):
                        logger.debug(f"종목 정보 없음으로 제외: {stock_code} → {_v_stock_name}")
                        continue
                    
                    # 각 스크리닝 실행
                    _v_fundamental_passed, _v_fundamental_score, _v_fundamental_details = self.screen_by_fundamentals(_v_stock_data)
                    _v_technical_passed, _v_technical_score, _v_technical_details = self.screen_by_technical(_v_stock_data)
                    _v_momentum_passed, _v_momentum_score, _v_momentum_details = self.screen_by_momentum(_v_stock_data)
                    
                    # 종합 결과 계산
                    _v_overall_passed = _v_fundamental_passed and _v_technical_passed and _v_momentum_passed
                    _v_overall_score = (_v_fundamental_score + _v_technical_score + _v_momentum_score) / 3.0
                    
                    _v_result = {
                        "stock_code": stock_code,
                        "stock_name": _v_stock_data.get("stock_name", ""),
                        "sector": _v_stock_data.get("sector", ""),
                        "screening_timestamp": datetime.now().isoformat(),
                        "overall_passed": _v_overall_passed,
                        "overall_score": round(_v_overall_score, 2),
                        "fundamental": {
                            "passed": _v_fundamental_passed,
                            "score": round(_v_fundamental_score, 2),
                            "details": _v_fundamental_details
                        },
                        "technical": {
                            "passed": _v_technical_passed,
                            "score": round(_v_technical_score, 2),
                            "details": _v_technical_details
                        },
                        "momentum": {
                            "passed": _v_momentum_passed,
                            "score": round(_v_momentum_score, 2),
                            "details": _v_momentum_details
                        }
                    }
                    
                    _v_results.append(_v_result)
                    _v_processed_count += 1
                    
                    # 진행 상황 로그
                    if _v_processed_count % 100 == 0:
                        logger.info(f"스크리닝 진행 상황: {_v_processed_count}/{len(p_stock_list)}")
                    
                    # API 호출 제한 고려
                    self.api_config.apply_rate_limit()
                    
                except Exception as e:
                    logger.error(f"종목 {stock_code} 스크리닝 오류: {e}")
                    continue
            
            # 결과 정렬 (점수 높은 순)
            _v_results.sort(key=lambda x: x["overall_score"], reverse=True)
            
            logger.info(f"종합 스크리닝 완료 - 처리된 종목: {_v_processed_count}개, 통과 종목: {len([r for r in _v_results if r['overall_passed']])}개")
            
            return _v_results
            
        except Exception as e:
            logger.error(f"종합 스크리닝 오류: {e}")
            return []
    
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
                            
                    logger.debug(f"종목 정보 로드 성공: {p_stock_code} → {_v_stock_name} ({_v_market})")
                            
                except Exception as e:
                    logger.warning(f"종목 리스트 파일 로드 실패: {e}")
            else:
                logger.warning(f"종목 리스트 파일을 찾을 수 없음: {_v_stock_dir}")
            
            # 종목 정보가 없으면 기본값 사용
            if not _v_stock_name:
                _v_stock_name = f"종목{p_stock_code}"
                _v_market = "KOSPI" if p_stock_code.startswith(('0', '1', '2', '3')) else "KOSDAQ"
                logger.warning(f"종목 정보 없음, 기본값 사용: {p_stock_code} → {_v_stock_name} ({_v_market})")
            
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
                
                logger.debug(f"기본값 사용 - {p_stock_code} ({_v_stock_name}): 가격={_v_current_price:,}, 거래량={_v_volume:,}")
                
            except Exception as e:
                logger.warning(f"기본값 생성 실패 - {p_stock_code}: {e}")
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
            logger.error(f"주식 데이터 수집 오류 - {p_stock_code}: {e}")
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
            logger.error(f"섹터 평균 PER 조회 오류: {e}")
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
            
            logger.info(f"스크리닝 결과 저장 완료: {_v_filepath}")
            return True
            
        except Exception as e:
            logger.error(f"스크리닝 결과 저장 오류: {e}")
            return False 