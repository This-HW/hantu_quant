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
                "volatility_max": 0.4      # 변동성 최대 40%
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
            _v_max_score = 5.0  # 총 5개 지표
            
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
            
            # 정규화된 점수 계산 (0-100점)
            _v_normalized_score = (_v_score / _v_max_score) * 100.0
            
            # 통과 기준: 5개 지표 중 3개 이상 통과
            _v_passed = _v_score >= 3.0
            
            logger.debug(f"기술적 스크리닝 - 종목: {p_stock_data.get('stock_code')}, 점수: {_v_normalized_score:.1f}, 통과: {_v_passed}")
            
            return _v_passed, _v_normalized_score, _v_results
            
        except Exception as e:
            logger.error(f"기술적 스크리닝 오류: {e}")
            return False, 0.0, {}
    
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
        """주식 데이터 수집
        
        Args:
            p_stock_code: 종목 코드
            
        Returns:
            주식 데이터 딕셔너리 또는 None
        """
        try:
            # 여기서 실제 API 호출을 통해 데이터 수집
            # 현재는 더미 데이터로 구현
            
            # TODO: 실제 API 호출 구현
            # - 한국투자증권 API를 통한 재무 데이터 수집
            # - 기술적 지표 계산
            # - 모멘텀 데이터 계산
            
            # 종목별 섹터 정보 설정
            _v_sector_map = {
                "005930": "반도체",
                "000660": "반도체", 
                "035420": "인터넷",
                "005380": "자동차",
                "000270": "자동차",
                "068270": "바이오",
                "207940": "바이오",
                "035720": "인터넷",
                "051910": "화학",
                "006400": "배터리",
                "003670": "철강",
                "096770": "에너지",
                "034730": "통신",
                "015760": "전력",
                "017670": "통신",
                "030200": "통신",
                "032830": "금융",
                "066570": "전자",
                "028260": "건설",
                "009150": "전자"
            }
            
            _v_stock_names = {
                "005930": "삼성전자",
                "000660": "SK하이닉스",
                "035420": "NAVER",
                "005380": "현대차",
                "000270": "기아",
                "068270": "셀트리온",
                "207940": "삼성바이오로직스",
                "035720": "카카오",
                "051910": "LG화학",
                "006400": "삼성SDI",
                "003670": "포스코홀딩스",
                "096770": "SK이노베이션",
                "034730": "SK",
                "015760": "한국전력",
                "017670": "SK텔레콤",
                "030200": "KT",
                "032830": "삼성생명",
                "066570": "LG전자",
                "028260": "삼성물산",
                "009150": "삼성전기"
            }
            
            _v_dummy_data = {
                "stock_code": p_stock_code,
                "stock_name": _v_stock_names.get(p_stock_code, f"종목{p_stock_code}"),
                "sector": _v_sector_map.get(p_stock_code, "기타"),
                "market_cap": 1000000000000,
                "current_price": 50000,
                # 재무 데이터 (스크리닝 기준 통과하도록 조정)
                "roe": 15.0,          # 10% 이상
                "per": 12.0,          # 섹터 평균 대비 1.2배 이하
                "pbr": 1.8,           # 2.0 이하
                "debt_ratio": 40.0,   # 50% 이하
                "revenue_growth": 10.0,  # 5% 이상
                "operating_margin": 15.0,  # 10% 이상
                # 기술적 데이터 (스크리닝 기준 통과하도록 조정)
                "ma_20": 49000,
                "ma_60": 48000,
                "ma_120": 47000,
                "rsi": 55.0,          # 30-70 범위
                "volume_ratio": 1.8,  # 1.5 이상
                "price_momentum_1m": 8.0,  # 5% 이상
                "volatility": 0.25,   # 30% 이하
                # 모멘텀 데이터 (스크리닝 기준 통과하도록 조정)
                "relative_strength": 0.15,  # 0.1 이상
                "price_momentum_3m": 12.0,
                "price_momentum_6m": 18.0,
                "volume_momentum": 0.25,     # 0.2 이상
                "sector_momentum": 0.08      # 0.05 이상
            }
            
            return _v_dummy_data
            
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