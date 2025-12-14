#!/usr/bin/env python3
"""
Phase 2: 가격 매력도 분석 시스템
매일 감시 리스트 종목들의 가격 매력도를 분석하여 매매 적기를 판단
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
import logging
import time

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.config.api_config import APIConfig
from core.utils.log_utils import get_logger
from core.interfaces.trading import IPriceAnalyzer, PriceAttractiveness, TechnicalSignal
from hantu_common.indicators.trend import SlopeIndicator
from hantu_common.indicators.volume import VolumePriceAnalyzer, RelativeVolumeStrength, VolumeClusterAnalyzer
from core.config import trading_config as TCONF

# 새로운 아키텍처 imports - 사용 가능할 때만 import
try:
    from core.plugins.decorators import plugin
    from core.di.injector import inject
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

class PatternAnalysis:
    """패턴 분석 클래스"""
    
    def detect_candlestick_patterns(self, p_ohlc_data):
        """캔들스틱 패턴 감지"""
        try:
            if len(p_ohlc_data) < 3:
                return []
            
            patterns = []
            
            # 기본적인 패턴들을 검사
            # 망치형 패턴 (Hammer)
            for i in range(1, len(p_ohlc_data)):
                _v_prev = p_ohlc_data[i-1]
                _v_curr = p_ohlc_data[i]
                
                # 망치형: 작은 몸통 + 긴 아래 그림자
                _v_body = abs(_v_curr["close"] - _v_curr["open"])
                _v_total_range = _v_curr["high"] - _v_curr["low"]
                _v_lower_shadow = _v_curr["open"] - _v_curr["low"] if _v_curr["close"] > _v_curr["open"] else _v_curr["close"] - _v_curr["low"]
                
                if _v_total_range > 0 and _v_body / _v_total_range < 0.3 and _v_lower_shadow / _v_total_range > 0.6:
                    patterns.append("hammer")
            
            # 기타 패턴들도 간단히 구현
            if len(p_ohlc_data) >= 2:
                _v_last = p_ohlc_data[-1]
                _v_prev = p_ohlc_data[-2]
                
                # 상승 포용형 (Bullish Engulfing)
                if (_v_prev["close"] < _v_prev["open"] and  # 이전 캔들이 음봉
                    _v_last["close"] > _v_last["open"] and  # 현재 캔들이 양봉
                    _v_last["open"] < _v_prev["close"] and  # 현재 시가가 이전 종가보다 낮음
                    _v_last["close"] > _v_prev["open"]):   # 현재 종가가 이전 시가보다 높음
                    patterns.append("bullish_engulfing")
                
                # 도지 (Doji)
                _v_body = abs(_v_last["close"] - _v_last["open"])
                _v_total_range = _v_last["high"] - _v_last["low"]
                if _v_total_range > 0 and _v_body / _v_total_range < 0.1:
                    patterns.append("doji")
            
            return patterns
            
        except Exception as e:
            return []
    
    def detect_support_resistance(self, p_prices):
        """지지선/저항선 감지"""
        try:
            if len(p_prices) < 5:
                return {"support": [], "resistance": []}
            
            # 간단한 지지선/저항선 감지 로직
            _v_support_levels = []
            _v_resistance_levels = []
            
            # 최근 가격들을 기반으로 지지선/저항선 추정
            _v_min_price = min(p_prices[-10:]) if len(p_prices) >= 10 else min(p_prices)
            _v_max_price = max(p_prices[-10:]) if len(p_prices) >= 10 else max(p_prices)
            _v_current_price = p_prices[-1]
            
            # 지지선: 최저가 근처
            _v_support_levels.append(_v_min_price)
            _v_support_levels.append(_v_min_price * 1.02)  # 2% 위
            
            # 저항선: 최고가 근처
            _v_resistance_levels.append(_v_max_price)
            _v_resistance_levels.append(_v_max_price * 0.98)  # 2% 아래
            
            return {
                "support": _v_support_levels,
                "resistance": _v_resistance_levels
            }
            
        except Exception as e:
            return {"support": [], "resistance": []}

class VolumeAnalysis:
    """거래량 분석 클래스"""
    
    def calculate_enhanced_volume_score(self, p_volumes, p_prices):
        """향상된 거래량 점수 계산"""
        try:
            if len(p_volumes) < 2:
                return 50.0
            
            # 최근 거래량과 평균 거래량 비교
            _v_recent_volume = p_volumes[-1]
            _v_avg_volume = sum(p_volumes) / len(p_volumes)
            
            if _v_avg_volume == 0:
                return 50.0
            
            _v_volume_ratio = _v_recent_volume / _v_avg_volume
            
            # 거래량 비율에 따른 점수 계산
            if _v_volume_ratio >= 2.0:
                return 90.0
            elif _v_volume_ratio >= 1.5:
                return 75.0
            elif _v_volume_ratio >= 1.2:
                return 60.0
            else:
                return 40.0
                
        except Exception as e:
            return 50.0
    
    def analyze_volume_pattern(self, p_volumes, p_prices):
        """거래량 패턴 분석"""
        try:
            if len(p_volumes) < 3:
                return {
                    'trend': 'neutral',
                    'strength': 50.0,
                    'consistency': 50.0
                }
            
            # 거래량 추세 분석
            _v_recent_avg = sum(p_volumes[-3:]) / 3
            _v_older_avg = sum(p_volumes[:-3]) / len(p_volumes[:-3]) if len(p_volumes) > 3 else _v_recent_avg
            
            if _v_older_avg == 0:
                _v_trend = 'neutral'
            elif _v_recent_avg > _v_older_avg * 1.2:
                _v_trend = 'increasing'
            elif _v_recent_avg < _v_older_avg * 0.8:
                _v_trend = 'decreasing'
            else:
                _v_trend = 'neutral'
            
            # 강도 계산
            _v_strength = min(100.0, (_v_recent_avg / _v_older_avg * 50.0) if _v_older_avg > 0 else 50.0)
            
            return {
                'trend': _v_trend,
                'strength': _v_strength,
                'consistency': 70.0  # 임시 고정값
            }
            
        except Exception as e:
            return {
                'trend': 'neutral',
                'strength': 50.0,
                'consistency': 50.0
            }
    
    def calculate_volume_score(self, p_volume_data):
        """거래량 점수 계산"""
        try:
            _v_base_score = 50.0
            
            # 추세에 따른 점수 조정
            if p_volume_data['trend'] == 'increasing':
                _v_base_score += 20.0
            elif p_volume_data['trend'] == 'decreasing':
                _v_base_score -= 10.0
            
            # 강도에 따른 점수 조정
            _v_strength_factor = (p_volume_data['strength'] - 50.0) / 100.0
            _v_base_score += _v_strength_factor * 20.0
            
            return max(0.0, min(100.0, _v_base_score))
            
        except Exception as e:
            return 50.0



@dataclass
class TechnicalSignalLegacy:
    """기술적 신호 데이터 클래스 (기존 호환성용)"""
    signal_type: str        # 신호 유형 (bollinger, macd, rsi 등)
    signal_name: str        # 신호 이름
    strength: float         # 신호 강도 (0-100)
    confidence: float       # 신뢰도 (0-1)
    description: str        # 신호 설명
    timestamp: str          # 신호 발생 시간

@dataclass
class PriceAttractivenessLegacy:
    """가격 매력도 분석 결과 (기존 호환성용)"""
    stock_code: str
    stock_name: str
    analysis_date: str
    current_price: float
    
    # 종합 점수
    total_score: float              # 총 매력도 점수 (0-100)
    technical_score: float          # 기술적 분석 점수
    volume_score: float             # 거래량 분석 점수
    pattern_score: float            # 패턴 분석 점수
    
    # 세부 분석 결과
    technical_signals: List[TechnicalSignalLegacy]
    entry_price: float              # 권장 진입가
    target_price: float             # 목표가
    stop_loss: float                # 손절가
    expected_return: float          # 기대 수익률
    risk_score: float               # 리스크 점수 (0-100)
    confidence: float               # 전체 신뢰도 (0-1)
    
    # 추가 정보
    selection_reason: str           # 선정 이유
    market_condition: str           # 시장 상황
    sector_momentum: float          # 섹터 모멘텀
    sector: str = ""                # 섹터
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return asdict(self)
    
    def to_price_attractiveness(self) -> PriceAttractiveness:
        """새로운 PriceAttractiveness로 변환"""
        # TechnicalSignalLegacy를 TechnicalSignal로 변환
        _v_signals = []
        for signal in self.technical_signals:
            _v_signals.append(TechnicalSignal(
                signal_type=signal.signal_type,
                signal_name=signal.signal_name,
                strength=signal.strength,
                confidence=signal.confidence,
                description=signal.description,
                timestamp=datetime.fromisoformat(signal.timestamp) if isinstance(signal.timestamp, str) else signal.timestamp
            ))
        
        return PriceAttractiveness(
            stock_code=self.stock_code,
            stock_name=self.stock_name,
            analysis_date=datetime.fromisoformat(self.analysis_date) if isinstance(self.analysis_date, str) else self.analysis_date,
            current_price=self.current_price,
            total_score=self.total_score,
            technical_score=self.technical_score,
            volume_score=self.volume_score,
            pattern_score=self.pattern_score,
            technical_signals=_v_signals,
            entry_price=self.entry_price,
            target_price=self.target_price,
            stop_loss=self.stop_loss,
            expected_return=self.expected_return,
            risk_score=self.risk_score,
            confidence=self.confidence,
            selection_reason=self.selection_reason,
            market_condition=self.market_condition,
            sector_momentum=self.sector_momentum,
            sector=self.sector
        )

class TechnicalIndicators:
    """기술적 지표 계산 클래스"""
    
    @staticmethod
    def calculate_bollinger_bands(p_prices: List[float], p_period: int = 20, p_std_dev: float = 2.0) -> Tuple[float, float, float]:
        """볼린저 밴드 계산"""
        try:
            if len(p_prices) < p_period:
                return 0.0, 0.0, 0.0
            
            _v_prices = np.array(p_prices[-p_period:])
            _v_sma = np.mean(_v_prices)
            _v_std = np.std(_v_prices)
            
            _v_upper = _v_sma + (p_std_dev * _v_std)
            _v_lower = _v_sma - (p_std_dev * _v_std)
            
            return _v_upper, _v_sma, _v_lower
            
        except Exception as e:
            logger.error(f"볼린저 밴드 계산 오류: {e}")
            return 0.0, 0.0, 0.0

    @staticmethod
    def calculate_macd(p_prices: List[float], p_fast: int = 12, p_slow: int = 26, p_signal: int = 9) -> Tuple[float, float, float]:
        """MACD 계산"""
        try:
            if len(p_prices) < p_slow:
                return 0.0, 0.0, 0.0
            
            _v_prices = np.array(p_prices)
            
            # EMA 계산
            _v_ema_fast = TechnicalIndicators._calculate_ema(_v_prices, p_fast)
            _v_ema_slow = TechnicalIndicators._calculate_ema(_v_prices, p_slow)
            
            # MACD Line
            _v_macd_line = _v_ema_fast[-1] - _v_ema_slow[-1]
            
            # Signal Line (MACD의 EMA)
            if len(_v_prices) >= p_slow + p_signal:
                _v_macd_values = _v_ema_fast[p_slow-1:] - _v_ema_slow[p_slow-1:]
                _v_signal_line = TechnicalIndicators._calculate_ema(_v_macd_values, p_signal)[-1]
            else:
                _v_signal_line = _v_macd_line
            
            # Histogram
            _v_histogram = _v_macd_line - _v_signal_line
            
            return _v_macd_line, _v_signal_line, _v_histogram
            
        except Exception as e:
            logger.error(f"MACD 계산 오류: {e}")
            return 0.0, 0.0, 0.0

    @staticmethod
    def calculate_rsi(p_prices: List[float], p_period: int = 14) -> float:
        """RSI 계산"""
        try:
            if len(p_prices) < p_period + 1:
                return 50.0
            
            _v_deltas = np.diff(p_prices)
            _v_gains = np.where(_v_deltas > 0, _v_deltas, 0)
            _v_losses = np.where(_v_deltas < 0, -_v_deltas, 0)
            
            _v_avg_gain = np.mean(_v_gains[-p_period:])
            _v_avg_loss = np.mean(_v_losses[-p_period:])
            
            if _v_avg_loss == 0:
                return 100.0
            
            _v_rs = _v_avg_gain / _v_avg_loss
            _v_rsi = 100 - (100 / (1 + _v_rs))
            
            return _v_rsi
            
        except Exception as e:
            logger.error(f"RSI 계산 오류: {e}")
            return 50.0

    @staticmethod
    def _calculate_ema(p_values: np.ndarray, p_period: int) -> np.ndarray:
        """지수이동평균 계산"""
        _v_alpha = 2.0 / (p_period + 1)
        _v_ema = np.zeros_like(p_values)
        _v_ema[0] = p_values[0]

        for i in range(1, len(p_values)):
            _v_ema[i] = _v_alpha * p_values[i] + (1 - _v_alpha) * _v_ema[i-1]

        return _v_ema

    @staticmethod
    def calculate_stochastic(p_highs: List[float], p_lows: List[float], p_closes: List[float],
                             p_k_period: int = 14, p_d_period: int = 3) -> Tuple[float, float]:
        """
        스토캐스틱 오실레이터 계산

        %K = ((현재 종가 - N일간 최저가) / (N일간 최고가 - N일간 최저가)) × 100
        %D = %K의 M일간 SMA

        Args:
            p_highs: 고가 리스트
            p_lows: 저가 리스트
            p_closes: 종가 리스트
            p_k_period: %K 기간 (기본 14일)
            p_d_period: %D 기간 (기본 3일)

        Returns:
            Tuple[%K, %D]
        """
        try:
            if len(p_closes) < p_k_period:
                return 50.0, 50.0

            _v_highs = np.array(p_highs)
            _v_lows = np.array(p_lows)
            _v_closes = np.array(p_closes)

            # %K 계산: 최근 p_k_period 기간 사용
            _v_k_values = []
            for i in range(p_k_period - 1, len(_v_closes)):
                _v_highest_high = np.max(_v_highs[i - p_k_period + 1:i + 1])
                _v_lowest_low = np.min(_v_lows[i - p_k_period + 1:i + 1])

                if _v_highest_high == _v_lowest_low:
                    _v_k = 50.0
                else:
                    _v_k = ((_v_closes[i] - _v_lowest_low) / (_v_highest_high - _v_lowest_low)) * 100

                _v_k_values.append(_v_k)

            if not _v_k_values:
                return 50.0, 50.0

            # 현재 %K
            _v_current_k = _v_k_values[-1]

            # %D 계산: %K의 SMA
            if len(_v_k_values) >= p_d_period:
                _v_current_d = np.mean(_v_k_values[-p_d_period:])
            else:
                _v_current_d = _v_current_k

            return float(_v_current_k), float(_v_current_d)

        except Exception as e:
            logger.error(f"스토캐스틱 계산 오류: {e}")
            return 50.0, 50.0

    @staticmethod
    def calculate_cci(p_highs: List[float], p_lows: List[float], p_closes: List[float],
                      p_period: int = 20) -> float:
        """
        CCI (Commodity Channel Index) 계산

        CCI = (Typical Price - SMA(TP)) / (0.015 × Mean Deviation)
        Typical Price = (High + Low + Close) / 3

        해석:
        - CCI > +100: 과매수 구간
        - CCI < -100: 과매도 구간 (매수 신호)
        - CCI가 -100 이하에서 상승 반전: 강한 매수 신호

        Args:
            p_highs: 고가 리스트
            p_lows: 저가 리스트
            p_closes: 종가 리스트
            p_period: CCI 기간 (기본 20일)

        Returns:
            CCI 값
        """
        try:
            if len(p_closes) < p_period:
                return 0.0

            _v_highs = np.array(p_highs[-p_period:])
            _v_lows = np.array(p_lows[-p_period:])
            _v_closes = np.array(p_closes[-p_period:])

            # Typical Price 계산
            _v_tp = (_v_highs + _v_lows + _v_closes) / 3

            # TP의 SMA
            _v_tp_sma = np.mean(_v_tp)

            # Mean Deviation 계산
            _v_mean_deviation = np.mean(np.abs(_v_tp - _v_tp_sma))

            # CCI 계산
            if _v_mean_deviation == 0:
                return 0.0

            _v_current_tp = _v_tp[-1]
            _v_cci = (_v_current_tp - _v_tp_sma) / (0.015 * _v_mean_deviation)

            return float(_v_cci)

        except Exception as e:
            logger.error(f"CCI 계산 오류: {e}")
            return 0.0

    @staticmethod
    def calculate_atr(p_highs: List[float], p_lows: List[float], p_closes: List[float],
                      p_period: int = 14) -> float:
        """
        ATR (Average True Range) 계산 - 변동성 지표

        True Range = max(H-L, |H-PC|, |L-PC|)
        ATR = SMA(TR, period)

        Args:
            p_highs: 고가 리스트
            p_lows: 저가 리스트
            p_closes: 종가 리스트
            p_period: ATR 기간 (기본 14일)

        Returns:
            ATR 값
        """
        try:
            if len(p_closes) < p_period + 1:
                return 0.0

            _v_highs = np.array(p_highs)
            _v_lows = np.array(p_lows)
            _v_closes = np.array(p_closes)

            # True Range 계산
            _v_tr_list = []
            for i in range(1, len(_v_closes)):
                _v_h = _v_highs[i]
                _v_l = _v_lows[i]
                _v_pc = _v_closes[i - 1]  # Previous Close

                _v_tr = max(
                    _v_h - _v_l,              # High - Low
                    abs(_v_h - _v_pc),        # |High - Previous Close|
                    abs(_v_l - _v_pc)         # |Low - Previous Close|
                )
                _v_tr_list.append(_v_tr)

            if len(_v_tr_list) < p_period:
                return 0.0

            # ATR = SMA of True Range
            _v_atr = np.mean(_v_tr_list[-p_period:])

            return float(_v_atr)

        except Exception as e:
            logger.error(f"ATR 계산 오류: {e}")
            return 0.0

@plugin(
    name="price_analyzer",
    version="1.0.0",
    description="가격 매력도 분석 플러그인",
    author="HantuQuant",
    dependencies=["api_config", "logger"],
    category="daily_selection"
)
class PriceAnalyzer(IPriceAnalyzer):
    """가격 매력도 분석 클래스 - 새로운 아키텍처 적용"""
    
    def _safe_get_float(self, p_value, p_default: float = 0.0) -> float:
        """안전하게 float 값을 추출하는 헬퍼 메서드"""
        try:
            if isinstance(p_value, list):
                if p_value:
                    return float(p_value[-1])  # 리스트의 마지막 값 사용
                else:
                    return p_default
            elif isinstance(p_value, (int, float)):
                return float(p_value)
            elif isinstance(p_value, str):
                try:
                    return float(p_value)
                except (ValueError, TypeError):
                    return p_default
            else:
                return p_default
        except (ValueError, TypeError, IndexError):
            return p_default

    def _safe_get_list(self, p_value, p_default_size: int = 30) -> List[float]:
        """안전하게 리스트를 추출하는 헬퍼 메서드"""
        try:
            if isinstance(p_value, list) and p_value:
                return [float(x) for x in p_value if isinstance(x, (int, float))]
            elif isinstance(p_value, (int, float)):
                # 단일 값인 경우 더미 데이터 생성
                return self._generate_dummy_price_data(float(p_value), p_default_size)
            else:
                return self._generate_dummy_price_data(50000.0, p_default_size)
        except (ValueError, TypeError):
            return self._generate_dummy_price_data(50000.0, p_default_size)

    @inject
    def __init__(self, 
                 p_config_file: str = "core/config/api_config.py",
                 config=None,
                 logger=None):
        """초기화 메서드"""
        self._config = config or APIConfig()
        self._logger = logger or get_logger(__name__)
        self._market_condition = "neutral"
        self._sector_momentum_cache = {}
        
        # 기술지표 계산을 위한 인디케이터 초기화
        self._v_indicators = TechnicalIndicators()
        
        # 거래량 분석을 위한 인디케이터 초기화
        self._v_volume_analysis = VolumeAnalysis()
        
        # 패턴 분석을 위한 인디케이터 초기화
        self._v_patterns = PatternAnalysis()
        
        self._logger.info("PriceAnalyzer 초기화 완료 (새 아키텍처)")

    def analyze_price_attractiveness(self, p_stock_data: Dict) -> PriceAttractiveness:
        """단일 종목 가격 매력도 분석 (새 인터페이스 구현)"""
        try:
            # 기존 로직 사용하여 분석 수행
            _v_legacy_result = self._analyze_price_attractiveness_legacy(p_stock_data)
            
            # 새로운 형식으로 변환
            return _v_legacy_result.to_price_attractiveness()
            
        except Exception as e:
            self._logger.error(f"가격 매력도 분석 오류: {e}")
            return self._create_default_result(p_stock_data)

    def analyze_multiple_stocks(self, p_stock_list: List[Dict]) -> List[PriceAttractiveness]:
        """다중 종목 가격 매력도 분석 (새 인터페이스 구현)"""
        _v_results = []
        
        for _v_stock_data in p_stock_list:
            try:
                _v_result = self.analyze_price_attractiveness(_v_stock_data)
                _v_results.append(_v_result)
            except Exception as e:
                self._logger.error(f"종목 {_v_stock_data.get('stock_code', 'Unknown')} 분석 오류: {e}")
                continue
        
        # 점수 순으로 정렬
        _v_results.sort(key=lambda x: x.total_score, reverse=True)
        
        self._logger.info(f"다중 종목 분석 완료: {len(_v_results)}개 종목")
        return _v_results

    def analyze_technical_indicators(self, p_stock_data: Dict) -> Tuple[float, List[TechnicalSignal]]:
        """기술적 지표 분석 (새 인터페이스 구현)"""
        try:
            _v_score, _v_legacy_signals = self._analyze_technical_indicators(p_stock_data)
            
            # 새로운 형식으로 변환
            _v_signals = []
            for signal in _v_legacy_signals:
                _v_signals.append(TechnicalSignal(
                    signal_type=signal.signal_type,
                    signal_name=signal.signal_name,
                    strength=signal.strength,
                    confidence=signal.confidence,
                    description=signal.description,
                    timestamp=datetime.fromisoformat(signal.timestamp) if isinstance(signal.timestamp, str) else signal.timestamp
                ))
            
            return _v_score, _v_signals
            
        except Exception as e:
            self._logger.error(f"기술적 지표 분석 오류: {e}")
            return 0.0, []

    def analyze_volume_pattern(self, p_stock_data: Dict) -> float:
        """거래량 패턴 분석 (새 인터페이스 구현)"""
        try:
            return self._analyze_volume(p_stock_data)
        except Exception as e:
            self._logger.error(f"거래량 패턴 분석 오류: {e}")
            return 0.0

    def detect_patterns(self, p_stock_data: Dict) -> float:
        """가격 패턴 감지 (새 인터페이스 구현)"""
        try:
            return self._analyze_patterns(p_stock_data)
        except Exception as e:
            self._logger.error(f"패턴 감지 오류: {e}")
            return 0.0

    def _analyze_price_attractiveness_legacy(self, p_stock_data: Dict) -> PriceAttractivenessLegacy:
        """기존 가격 매력도 분석 로직 (호환성용)"""
        try:
            _v_stock_code = p_stock_data.get("stock_code", "")
            _v_stock_name = p_stock_data.get("stock_name", "")
            
            # current_price가 리스트인 경우 첫 번째 값 또는 마지막 값 사용
            _v_current_price_raw = p_stock_data.get("current_price", 0.0)
            if isinstance(_v_current_price_raw, list):
                _v_current_price = float(_v_current_price_raw[-1]) if _v_current_price_raw else 0.0
            else:
                _v_current_price = float(_v_current_price_raw) if _v_current_price_raw else 0.0
            
            _v_sector = p_stock_data.get("sector", "")
            
            # 0이거나 음수인 경우 기본값 설정
            if _v_current_price <= 0:
                _v_current_price = 50000.0  # 기본값
            
            # 각 분석 영역별 점수 계산
            _v_technical_score, _v_technical_signals = self._analyze_technical_indicators(p_stock_data)
            _v_volume_score = self._analyze_volume(p_stock_data)
            _v_pattern_score = self._analyze_patterns(p_stock_data)
            
            # 기울기 지표 분석 추가
            _v_slope_score, _v_slope_signals = self._analyze_slope_indicators(p_stock_data)
            _v_technical_signals.extend(_v_slope_signals)
            
            # 종합 점수 계산 (가중 평균)
            _v_total_score = (
                _v_technical_score * 0.40 +    # 기술적 분석 40%
                _v_volume_score * 0.30 +       # 거래량 분석 30%
                _v_pattern_score * 0.20 +      # 패턴 분석 20%
                _v_slope_score * 0.10          # 기울기 분석 10%
            )
            
            # 진입가, 목표가, 손절가 계산
            _v_entry_price, _v_target_price, _v_stop_loss = self._calculate_target_stop(_v_current_price, _v_total_score)
            _v_expected_return = ((_v_target_price - _v_entry_price) / _v_entry_price) * 100 if _v_entry_price > 0 else 0.0
            
            # 리스크 점수 및 신뢰도 계산
            _v_risk_score = self._calculate_risk_score(p_stock_data, _v_total_score)
            _v_confidence = self._calculate_confidence(_v_technical_signals, _v_total_score)
            
            # 선정 이유 및 시장 상황
            _v_selection_reason = self._generate_selection_reason(_v_technical_signals, _v_total_score)
            _v_market_condition = self._get_market_condition()
            _v_sector_momentum = self._get_sector_momentum(_v_sector)
            
            return PriceAttractivenessLegacy(
                stock_code=_v_stock_code,
                stock_name=_v_stock_name,
                analysis_date=datetime.now().isoformat(),
                current_price=_v_current_price,
                total_score=round(_v_total_score, 2),
                technical_score=round(_v_technical_score, 2),
                volume_score=round(_v_volume_score, 2),
                pattern_score=round(_v_pattern_score, 2),
                technical_signals=_v_technical_signals,
                entry_price=_v_entry_price,
                target_price=_v_target_price,
                stop_loss=_v_stop_loss,
                expected_return=round(_v_expected_return, 2),
                risk_score=round(_v_risk_score, 2),
                confidence=round(_v_confidence, 3),
                selection_reason=_v_selection_reason,
                market_condition=_v_market_condition,
                sector_momentum=round(_v_sector_momentum, 2),
                sector=_v_sector
            )
            
        except Exception as e:
            self._logger.error(f"가격 매력도 분석 오류: {e}")
            return self._create_default_result_legacy(p_stock_data)

    def _create_default_result(self, p_stock_data: Dict) -> PriceAttractiveness:
        """기본 결과 생성 (새 인터페이스용)"""
        return PriceAttractiveness(
            stock_code=p_stock_data.get("stock_code", ""),
            stock_name=p_stock_data.get("stock_name", ""),
            analysis_date=datetime.now(),
            current_price=p_stock_data.get("current_price", 0.0),
            total_score=0.0,
            technical_score=0.0,
            volume_score=0.0,
            pattern_score=0.0,
            technical_signals=[],
            entry_price=p_stock_data.get("current_price", 0.0),
            target_price=p_stock_data.get("current_price", 0.0),
            stop_loss=p_stock_data.get("current_price", 0.0),
            expected_return=0.0,
            risk_score=100.0,
            confidence=0.0,
            selection_reason="분석 실패",
            market_condition="unknown",
            sector_momentum=0.0,
            sector=p_stock_data.get("sector", "")
        )

    def _create_default_result_legacy(self, p_stock_data: Dict) -> PriceAttractivenessLegacy:
        """기본 결과 생성 (기존 호환성용)"""
        return PriceAttractivenessLegacy(
            stock_code=p_stock_data.get("stock_code", ""),
            stock_name=p_stock_data.get("stock_name", ""),
            analysis_date=datetime.now().isoformat(),
            current_price=p_stock_data.get("current_price", 0.0),
            total_score=0.0,
            technical_score=0.0,
            volume_score=0.0,
            pattern_score=0.0,
            technical_signals=[],
            entry_price=p_stock_data.get("current_price", 0.0),
            target_price=p_stock_data.get("current_price", 0.0),
            stop_loss=p_stock_data.get("current_price", 0.0),
            expected_return=0.0,
            risk_score=100.0,
            confidence=0.0,
            selection_reason="분석 실패",
            market_condition="unknown",
            sector_momentum=0.0,
            sector=p_stock_data.get("sector", "")
        )

    def _get_sector_momentum(self, p_sector: str) -> float:
        """섹터 모멘텀 조회 (캐시 사용)"""
        if p_sector in self._sector_momentum_cache:
            return self._sector_momentum_cache[p_sector]
        
        # 실제로는 섹터 데이터를 조회해야 하지만, 여기서는 시뮬레이션
        _v_momentum = np.random.uniform(-5.0, 15.0)  # -5% ~ 15% 범위
        self._sector_momentum_cache[p_sector] = _v_momentum
        
        return _v_momentum

    def _analyze_technical_indicators(self, p_stock_data: Dict) -> Tuple[float, List[TechnicalSignalLegacy]]:
        """기술적 지표 분석 (기존 로직)"""
        _v_signals = []
        _v_scores = []
        
        # 안전하게 현재가 추출
        _v_current_price = self._safe_get_float(p_stock_data.get("current_price", 50000))
        if _v_current_price <= 0:
            _v_current_price = 50000.0
        
        # 실데이터 기반 보조 데이터 구성 시도
        _v_prices = self._safe_get_list(p_stock_data.get("recent_close_prices", []), p_default_size=30)
        _v_highs = [p * 1.02 for p in _v_prices]
        _v_lows = [p * 0.98 for p in _v_prices]
        _v_volumes = self._safe_get_list(p_stock_data.get("recent_volumes", []), p_default_size=len(_v_prices) or 30)
        
        # 볼린저 밴드 분석
        _v_bb_upper, _v_bb_middle, _v_bb_lower = TechnicalIndicators.calculate_bollinger_bands(_v_prices)
        
        if _v_current_price <= _v_bb_lower * 1.02:  # 하단 밴드 근처
            _v_signals.append(TechnicalSignalLegacy(
                signal_type="bollinger",
                signal_name="bollinger_bottom_touch",
                strength=80.0,
                confidence=0.7,
                description="볼린저 밴드 하단 접촉 후 반등 신호",
                timestamp=datetime.now().isoformat()
            ))
            _v_scores.append(80.0)
        elif _v_current_price >= _v_bb_upper * 0.98:  # 상단 밴드 근처
            _v_scores.append(20.0)
        else:
            _v_scores.append(50.0)
        
        # MACD 분석
        _v_macd, _v_signal, _v_histogram = TechnicalIndicators.calculate_macd(_v_prices)
        if _v_macd > _v_signal and _v_histogram > 0:
            _v_signals.append(TechnicalSignalLegacy(
                signal_type="macd",
                signal_name="macd_bullish",
                strength=70.0,
                confidence=0.6,
                description="MACD 골든크로스 신호",
                timestamp=datetime.now().isoformat()
            ))
            _v_scores.append(70.0)
        else:
            _v_scores.append(40.0)
        
        # RSI 분석
        _v_rsi = TechnicalIndicators.calculate_rsi(_v_prices)
        if _v_rsi <= 30:
            _v_signals.append(TechnicalSignalLegacy(
                signal_type="rsi",
                signal_name="rsi_oversold_recovery",
                strength=85.0,
                confidence=0.8,
                description="RSI 과매도 구간에서 반등 신호",
                timestamp=datetime.now().isoformat()
            ))
            _v_scores.append(85.0)
        elif _v_rsi >= 70:
            _v_scores.append(15.0)
        else:
            _v_scores.append(50.0)
        
        # 스토캐스틱 분석 (실제 계산)
        _v_k, _v_d = TechnicalIndicators.calculate_stochastic(_v_highs, _v_lows, _v_prices)
        if _v_k <= 20 and _v_d <= 20:
            _v_signals.append(TechnicalSignalLegacy(
                signal_type="stochastic",
                signal_name="stochastic_oversold",
                strength=75.0,
                confidence=0.7,
                description=f"스토캐스틱 과매도 신호 (%K={_v_k:.1f}, %D={_v_d:.1f})",
                timestamp=datetime.now().isoformat()
            ))
            _v_scores.append(75.0)
        elif _v_k <= 30:
            _v_scores.append(60.0)
        elif _v_k >= 80:
            _v_scores.append(25.0)  # 과매수 구간
        else:
            _v_scores.append(45.0)

        # CCI 분석 (실제 계산)
        _v_cci = TechnicalIndicators.calculate_cci(_v_highs, _v_lows, _v_prices)
        if _v_cci <= -100:
            _v_signals.append(TechnicalSignalLegacy(
                signal_type="cci",
                signal_name="cci_oversold",
                strength=70.0,
                confidence=0.65,
                description=f"CCI 과매도 신호 (CCI={_v_cci:.1f})",
                timestamp=datetime.now().isoformat()
            ))
            _v_scores.append(70.0)
        elif _v_cci <= -50:
            _v_scores.append(55.0)
        elif _v_cci >= 100:
            _v_scores.append(25.0)  # 과매수 구간
        else:
            _v_scores.append(40.0)
        
        # 주문호가/체결 기반 보강 (있을 때만)
        try:
            ob = p_stock_data.get("orderbook") or {}
            # bid1/ask1 가격 추출 (키 대소문자 무시)
            def _find_key(d, prefix):
                for k, v in d.items():
                    if k.lower().startswith(prefix):
                        return float(v)
                return 0.0
            bid1 = _find_key(ob, "bidp1") or _find_key(ob, "bidp_1")
            ask1 = _find_key(ob, "askp1") or _find_key(ob, "askp_1")
            if bid1 > 0 and ask1 > 0 and ask1 >= bid1:
                spread = (ask1 - bid1) / ((ask1 + bid1) / 2)
                if spread < 0.0005:
                    _v_scores.append(5.0)
                elif spread > 0.005:
                    _v_scores.append(-5.0)
        except Exception:
            pass

        try:
            uptick_ratio = p_stock_data.get("uptick_ratio")
            if isinstance(uptick_ratio, (int, float)):
                if uptick_ratio > 0.6:
                    _v_scores.append(5.0)
                elif uptick_ratio < 0.4:
                    _v_scores.append(-5.0)
        except Exception:
            pass

        # VWAP 괴리 반영 (분봉 기반)
        try:
            recent_bars = p_stock_data.get("minute_bars")
            if (recent_bars is None) or (isinstance(recent_bars, list) and len(recent_bars) == 0):
                # 필요 시 API로 보충
                try:
                    from core.api.kis_api import KISAPI
                    api = KISAPI()
                    df_mb = api.get_minute_bars(p_stock_data.get("stock_code", ""), time_unit=1, count=30)
                except Exception:
                    df_mb = None
            else:
                df_mb = recent_bars
            if df_mb is not None:
                import pandas as _pd
                if isinstance(df_mb, dict):
                    df_mb = _pd.DataFrame(df_mb)
                closes = _pd.to_numeric(df_mb.get('close', df_mb.get('stck_prpr', [])), errors='coerce')
                vols = _pd.to_numeric(df_mb.get('volume', df_mb.get('acml_vol', [])), errors='coerce')
                if len(closes) > 0 and len(vols) > 0 and closes.notna().any() and vols.notna().any():
                    vwap = (closes * vols).sum() / max(1.0, vols.sum())
                    if _v_current_price > 0 and vwap > 0:
                        dev = abs(_v_current_price - vwap) / vwap
                        if dev <= TCONF.VWAP_DEVIATION_MAX:
                            _v_scores.append(5.0)
                        else:
                            _v_scores.append(-5.0)
        except Exception:
            pass

        # 평균 점수 계산 (보강 반영)
        _v_average_score = sum(_v_scores) / len(_v_scores) if _v_scores else 50.0
        
        return float(_v_average_score), _v_signals
    
    def _analyze_volume(self, p_stock_data: Dict) -> float:
        """거래량 분석"""
        try:
            # 안전하게 현재가와 거래량 데이터 추출
            _v_current_price = self._safe_get_float(p_stock_data.get("current_price", 50000))
            _v_volume_raw = p_stock_data.get("volume", 1000000)
            _v_current_volume = self._safe_get_float(_v_volume_raw, 1000000)
            
            # 실데이터가 있으면 사용, 없으면 안전 기본
            _v_volumes = self._safe_get_list(p_stock_data.get("recent_volumes", []), p_default_size=20)
            if not _v_volumes or len(_v_volumes) < 2:
                _v_volumes = [_v_current_volume * (0.8 + i * 0.02) for i in range(20)]
            _v_prices = self._safe_get_list(p_stock_data.get("recent_close_prices", []), p_default_size=20)
            if not _v_prices or len(_v_prices) < 2:
                _v_prices = self._generate_dummy_price_data(_v_current_price, 20)
            
            # 거래량 분석
            _v_volume_score = self._v_volume_analysis.calculate_enhanced_volume_score(_v_volumes, _v_prices)
            
            return float(_v_volume_score)
            
        except Exception as e:
            self._logger.error(f"거래량 분석 오류: {e}")
            return 50.0

    def _analyze_patterns(self, p_stock_data: Dict) -> float:
        """패턴 분석"""
        try:
            # 안전하게 현재가 추출
            _v_current_price = self._safe_get_float(p_stock_data.get("current_price", 50000))
            
            # 실데이터가 있으면 사용, 없으면 기본 생성
            _v_prices = self._safe_get_list(p_stock_data.get("recent_close_prices", []), p_default_size=10)
            if not _v_prices or len(_v_prices) < 2:
                _v_prices = self._generate_dummy_price_data(_v_current_price, 10)
            _v_ohlc_data = []
            
            for i, price in enumerate(_v_prices):
                _v_ohlc_data.append({
                    "open": price * 0.995,
                    "high": price * 1.015,
                    "low": price * 0.985,
                    "close": price,
                    "volume": 1000000 + i * 50000
                })
            
            # 패턴 분석
            _v_patterns = self._v_patterns.detect_candlestick_patterns(_v_ohlc_data)
            
            # 패턴 점수 계산
            if _v_patterns:
                _v_pattern_score = 75.0  # 패턴이 감지되면 높은 점수
            else:
                _v_pattern_score = 45.0  # 패턴 없으면 낮은 점수
            
            return float(_v_pattern_score)
            
        except Exception as e:
            self._logger.error(f"패턴 분석 오류: {e}")
            return 50.0
    
    def _analyze_slope_indicators(self, p_stock_data: Dict) -> Tuple[float, List[TechnicalSignal]]:
        """기울기 지표 분석"""
        _v_signals = []
        _v_score = 0.0
        
        try:
            # OHLCV 데이터: 입력에 recent_* 있으면 DataFrame 구성
            _v_recent_close = self._safe_get_list(p_stock_data.get("recent_close_prices", []), p_default_size=60)
            _v_recent_vol = self._safe_get_list(p_stock_data.get("recent_volumes", []), p_default_size=len(_v_recent_close) or 60)
            if _v_recent_close and len(_v_recent_close) >= 60:
                dates = pd.date_range(end=datetime.now().date(), periods=len(_v_recent_close), freq='D')
                _v_ohlcv_data = pd.DataFrame({
                    'date': dates,
                    'open': [p * 0.997 for p in _v_recent_close],
                    'high': [p * 1.008 for p in _v_recent_close],
                    'low': [p * 0.992 for p in _v_recent_close],
                    'close': _v_recent_close,
                    'volume': _v_recent_vol
                })
            else:
                _v_ohlcv_data = self._generate_ohlcv_data(p_stock_data)
            
            if _v_ohlcv_data is None or len(_v_ohlcv_data) < 60:
                logger.warning("기울기 분석을 위한 데이터 부족")
                return 50.0, []
            
            _v_slope_indicator = SlopeIndicator(_v_ohlcv_data)
            
            # 1. 가격 기울기 분석 (30점)
            _v_price_slope_5d = _v_slope_indicator.calculate_price_slope(5)
            _v_price_slope_20d = _v_slope_indicator.calculate_price_slope(20)
            
            if _v_price_slope_5d > 0.5:
                _v_signals.append(TechnicalSignal(
                    signal_type="slope",
                    signal_name="strong_price_uptrend",
                    strength=80.0,
                    confidence=0.8,
                    description=f"강한 가격 상승 기울기 (5일: {_v_price_slope_5d:.2f}%)",
                    timestamp=datetime.now().isoformat()
                ))
                _v_score += 30.0
            elif _v_price_slope_5d > 0.2:
                _v_signals.append(TechnicalSignal(
                    signal_type="slope",
                    signal_name="moderate_price_uptrend",
                    strength=60.0,
                    confidence=0.6,
                    description=f"보통 가격 상승 기울기 (5일: {_v_price_slope_5d:.2f}%)",
                    timestamp=datetime.now().isoformat()
                ))
                _v_score += 20.0
            elif _v_price_slope_5d > 0:
                _v_score += 10.0
            
            # 2. 이동평균 기울기 분석 (25점)
            _v_ma5_slope = _v_slope_indicator.calculate_ma_slope(5, 3)
            _v_ma20_slope = _v_slope_indicator.calculate_ma_slope(20, 5)
            _v_ma60_slope = _v_slope_indicator.calculate_ma_slope(60, 10)
            
            if _v_ma20_slope > 0.3:
                _v_signals.append(TechnicalSignal(
                    signal_type="slope",
                    signal_name="strong_ma_uptrend",
                    strength=75.0,
                    confidence=0.7,
                    description=f"강한 이동평균 상승 기울기 (20일: {_v_ma20_slope:.2f}%)",
                    timestamp=datetime.now().isoformat()
                ))
                _v_score += 25.0
            elif _v_ma20_slope > 0.1:
                _v_score += 15.0
            elif _v_ma20_slope > 0:
                _v_score += 8.0
            
            # 3. 추세 일관성 분석 (20점)
            _v_trend_consistency = _v_slope_indicator.check_trend_consistency()
            
            if _v_trend_consistency:
                _v_signals.append(TechnicalSignal(
                    signal_type="slope",
                    signal_name="trend_consistency",
                    strength=85.0,
                    confidence=0.8,
                    description="단기-중기-장기 추세 일관성 확인",
                    timestamp=datetime.now().isoformat()
                ))
                _v_score += 20.0
            
            # 4. 기울기 가속도 분석 (15점)
            _v_acceleration = _v_slope_indicator.calculate_slope_acceleration()
            
            if _v_acceleration > 0.3:
                _v_signals.append(TechnicalSignal(
                    signal_type="slope",
                    signal_name="strong_acceleration",
                    strength=90.0,
                    confidence=0.9,
                    description=f"강한 기울기 가속 ({_v_acceleration:.2f}%)",
                    timestamp=datetime.now().isoformat()
                ))
                _v_score += 15.0
            elif _v_acceleration > 0.1:
                _v_score += 10.0
            elif _v_acceleration > 0:
                _v_score += 5.0
            
            # 5. 기울기 강도 분석 (10점)
            _v_slope_strength = _v_slope_indicator.get_slope_strength()
            
            if _v_slope_strength == 'strong_up':
                _v_signals.append(TechnicalSignal(
                    signal_type="slope",
                    signal_name="strong_slope_strength",
                    strength=95.0,
                    confidence=0.9,
                    description="매우 강한 상승 기울기 강도",
                    timestamp=datetime.now().isoformat()
                ))
                _v_score += 10.0
            elif _v_slope_strength == 'weak_up':
                _v_score += 6.0
            
            # 최종 점수 정규화 (0-100점)
            _v_normalized_score = min(_v_score, 100.0)
            
            return _v_normalized_score, _v_signals
            
        except Exception as e:
            logger.error(f"기울기 분석 중 오류 발생: {e}")
            return 50.0, []
    
    def _generate_ohlcv_data(self, p_stock_data: Dict) -> Optional[pd.DataFrame]:
        """주식 데이터로부터 OHLCV DataFrame 생성 (기울기 분석용)"""
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
            _v_base_price = _v_current_price * 0.92  # 시작가는 현재가의 92%
            _v_price = _v_base_price
            _v_base_volume = 1500000  # 기본 거래량
            
            for i in range(60):
                # 가격 변화 시뮬레이션 (상승 추세)
                _v_change = np.random.normal(0.003, 0.018)  # 평균 0.3% 상승, 표준편차 1.8%
                _v_price *= (1 + _v_change)
                _v_prices.append(_v_price)
                
                # 거래량 시뮬레이션 (거래량 비율 반영)
                _v_volume_multiplier = 1.0 + (_v_volume_ratio - 1.0) * 0.1  # 점진적 증가
                _v_volume = _v_base_volume * _v_volume_multiplier * np.random.uniform(0.6, 1.8)
                _v_volumes.append(_v_volume)
            
            # 마지막 가격을 현재가로 조정
            _v_prices[-1] = _v_current_price
            
            # DataFrame 생성
            _v_ohlcv_data = pd.DataFrame({
                'date': _v_dates,
                'open': [p * 0.997 for p in _v_prices],
                'high': [p * 1.008 for p in _v_prices],
                'low': [p * 0.992 for p in _v_prices],
                'close': _v_prices,
                'volume': _v_volumes
            })
            
            return _v_ohlcv_data
            
        except Exception as e:
            logger.error(f"OHLCV 데이터 생성 오류: {e}")
            return None
    
    def _calculate_target_stop(self, p_entry_price: float, p_score: float) -> Tuple[float, float, float]:
        """진입가, 목표가, 손절가 계산"""
        # 점수에 따른 목표 수익률 조정
        _v_target_return = 0.05 + (p_score / 100) * 0.15  # 5-20%
        _v_stop_loss_ratio = 0.05  # 5% 손절
        
        # 진입가는 현재가와 동일
        _v_entry_price = p_entry_price
        _v_target_price = p_entry_price * (1 + _v_target_return)
        _v_stop_loss = p_entry_price * (1 - _v_stop_loss_ratio)
        
        return _v_entry_price, _v_target_price, _v_stop_loss
    
    def _calculate_historical_volatility(self, p_prices: List[float], p_period: int = 20) -> float:
        """
        역사적 변동성 계산 (연율화)

        변동성 = 일간 수익률의 표준편차 × √252

        Args:
            p_prices: 종가 리스트
            p_period: 계산 기간 (기본 20일)

        Returns:
            연율화된 변동성 (예: 0.25 = 25%)
        """
        try:
            if len(p_prices) < p_period + 1:
                return 0.25  # 기본값

            _v_prices = np.array(p_prices[-(p_period + 1):])
            _v_returns = np.diff(np.log(_v_prices))  # 로그 수익률

            # 일간 변동성
            _v_daily_volatility = np.std(_v_returns)

            # 연율화 (252 거래일 기준)
            _v_annual_volatility = _v_daily_volatility * np.sqrt(252)

            return float(_v_annual_volatility)

        except Exception as e:
            logger.error(f"변동성 계산 오류: {e}")
            return 0.25

    def _calculate_var(self, p_prices: List[float], p_position_value: float,
                       p_confidence: float = 0.95, p_period: int = 20) -> float:
        """
        VaR (Value at Risk) 계산 - 파라메트릭 방법

        VaR = 포지션 가치 × Z점수 × 변동성 × √보유기간

        Args:
            p_prices: 종가 리스트
            p_position_value: 포지션 가치
            p_confidence: 신뢰수준 (기본 95%)
            p_period: 변동성 계산 기간

        Returns:
            VaR 금액 (원 단위)
        """
        try:
            from scipy import stats

            # 변동성 계산
            _v_volatility = self._calculate_historical_volatility(p_prices, p_period)

            # Z점수 (신뢰수준에 따른)
            _v_z_score = stats.norm.ppf(p_confidence)

            # 1일 VaR
            _v_var = p_position_value * _v_z_score * _v_volatility / np.sqrt(252)

            return float(abs(_v_var))

        except ImportError:
            # scipy 없으면 간단한 근사값 사용
            _v_volatility = self._calculate_historical_volatility(p_prices, p_period)
            _v_z_score = 1.645 if p_confidence == 0.95 else 2.326  # 95%, 99%
            _v_var = p_position_value * _v_z_score * _v_volatility / np.sqrt(252)
            return float(abs(_v_var))
        except Exception as e:
            logger.error(f"VaR 계산 오류: {e}")
            return p_position_value * 0.02  # 기본 2%

    def _calculate_risk_score(self, p_stock_data: Dict, p_total_score: float) -> float:
        """
        향상된 리스크 점수 계산

        리스크 요소:
        1. 기본 리스크 (매력도 역수)
        2. 변동성 리스크 (ATR 또는 역사적 변동성)
        3. 시가총액 리스크 (소형주일수록 높음)
        4. 거래량 리스크 (유동성)
        5. 섹터 리스크 (섹터 모멘텀 역수)
        """
        _v_base_risk = 100 - p_total_score  # 매력도가 높을수록 리스크 낮음

        # 동적 변동성 계산 (고정값 대신)
        _v_prices = self._safe_get_list(p_stock_data.get("recent_close_prices", []), 30)
        _v_highs = [p * 1.02 for p in _v_prices]
        _v_lows = [p * 0.98 for p in _v_prices]

        # ATR 기반 변동성
        _v_atr = TechnicalIndicators.calculate_atr(_v_highs, _v_lows, _v_prices)
        _v_current_price = self._safe_get_float(p_stock_data.get("current_price", 50000))

        if _v_current_price > 0 and _v_atr > 0:
            _v_atr_pct = (_v_atr / _v_current_price) * 100
            _v_volatility_risk = min(_v_atr_pct * 5, 50)  # ATR%의 5배, 최대 50점
        else:
            # 역사적 변동성 사용
            _v_hist_vol = self._calculate_historical_volatility(_v_prices)
            _v_volatility_risk = min(_v_hist_vol * 100, 50)

        # 시가총액 고려 (작을수록 위험)
        _v_market_cap = p_stock_data.get("market_cap", 1000000000000)
        if _v_market_cap >= 10000000000000:  # 10조 이상 대형주
            _v_size_risk = 5
        elif _v_market_cap >= 1000000000000:  # 1조 이상 중형주
            _v_size_risk = 15
        elif _v_market_cap >= 100000000000:  # 1000억 이상 소형주
            _v_size_risk = 30
        else:  # 1000억 미만 초소형주
            _v_size_risk = 50

        # 거래량 리스크 (유동성)
        _v_volume = p_stock_data.get("volume", 1000000)
        _v_avg_volume = p_stock_data.get("avg_volume", 1000000)
        if _v_avg_volume > 0:
            _v_volume_ratio = _v_volume / _v_avg_volume
            if _v_volume_ratio >= 1.5:
                _v_liquidity_risk = 5  # 높은 유동성
            elif _v_volume_ratio >= 0.8:
                _v_liquidity_risk = 15
            else:
                _v_liquidity_risk = 30  # 낮은 유동성
        else:
            _v_liquidity_risk = 20

        # 섹터 리스크
        _v_sector_momentum = p_stock_data.get("sector_momentum", 0.0)
        if _v_sector_momentum > 0.05:
            _v_sector_risk = 5
        elif _v_sector_momentum > 0:
            _v_sector_risk = 15
        elif _v_sector_momentum > -0.05:
            _v_sector_risk = 25
        else:
            _v_sector_risk = 40

        # 가중 평균 리스크 점수
        _v_total_risk = (
            _v_base_risk * 0.25 +
            _v_volatility_risk * 0.30 +
            _v_size_risk * 0.20 +
            _v_liquidity_risk * 0.15 +
            _v_sector_risk * 0.10
        )

        return min(_v_total_risk, 100.0)
    
    def _calculate_confidence(self, p_signals: List[TechnicalSignal], p_score: float) -> float:
        """신뢰도 계산"""
        if not p_signals:
            return 0.3
        
        _v_signal_confidence = np.mean([signal.confidence for signal in p_signals])
        _v_score_confidence = p_score / 100
        
        return (_v_signal_confidence + _v_score_confidence) / 2
    
    def _generate_selection_reason(self, p_signals: List[TechnicalSignal], p_score: float) -> str:
        """선정 이유 생성"""
        if not p_signals:
            return f"종합 점수 {p_score:.1f}점으로 매수 고려 구간"
        
        _v_main_signals = [signal.description for signal in p_signals[:3]]
        return " + ".join(_v_main_signals)
    
    def _get_market_condition(self) -> str:
        """현재 시장 상황 판단"""
        # 실제로는 시장 지수 분석을 통해 판단
        return "sideways"  # 임시로 횡보장 반환
    
    def _generate_dummy_price_data(self, p_current_price: float, p_days: int = 30) -> List[float]:
        """더미 가격 데이터 생성 (실제로는 API에서 가져옴)"""
        _v_prices = []
        _v_price = p_current_price * 0.95  # 시작가는 현재가보다 5% 낮게
        
        for i in range(p_days):
            _v_change = np.random.normal(0, 0.02)  # 평균 0, 표준편차 2%의 변화
            _v_price *= (1 + _v_change)
            _v_prices.append(_v_price)
        
        # 마지막 가격을 현재가로 조정
        _v_prices[-1] = p_current_price
        
        return _v_prices
    
    def save_analysis_results(self, p_results: List[PriceAttractiveness], p_file_path: str = None) -> bool:
        """분석 결과 저장"""
        try:
            if not p_file_path:
                _v_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                p_file_path = f"data/daily_selection/price_analysis_{_v_timestamp}.json"
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(p_file_path), exist_ok=True)
            
            _v_save_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
                "analysis_count": len(p_results),
                "results": [result.to_dict() for result in p_results],
                "metadata": {
                    "analyzer_version": "1.0.0",
                    "weights": self._v_weights
                }
            }
            
            with open(p_file_path, 'w', encoding='utf-8') as f:
                json.dump(_v_save_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"분석 결과 저장 완료: {p_file_path}")
            return True
            
        except Exception as e:
            logger.error(f"분석 결과 저장 실패: {e}")
            return False

if __name__ == "__main__":
    # 테스트 실행
    analyzer = PriceAnalyzer()
    
    # 테스트 데이터
    test_stock = {
        "stock_code": "005930",
        "stock_name": "삼성전자",
        "current_price": 56800,
        "sector": "반도체",
        "market_cap": 450000000000000,
        "volatility": 0.25,
        "sector_momentum": 0.05
    }
    
    # 분석 실행
    result = analyzer.analyze_price_attractiveness(test_stock)
    print(f"분석 결과: {result.stock_name} - 점수: {result.total_score:.1f}")
    print(f"선정 이유: {result.selection_reason}")
    
    # 결과 저장
    analyzer.save_analysis_results([result]) 