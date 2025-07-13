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
from hantu_common.indicators.trend import SlopeIndicator
from hantu_common.indicators.volume import VolumePriceAnalyzer, RelativeVolumeStrength, VolumeClusterAnalyzer

logger = get_logger(__name__)

@dataclass
class TechnicalSignal:
    """기술적 신호 데이터 클래스"""
    signal_type: str        # 신호 유형 (bollinger, macd, rsi 등)
    signal_name: str        # 신호 이름
    strength: float         # 신호 강도 (0-100)
    confidence: float       # 신뢰도 (0-1)
    description: str        # 신호 설명
    timestamp: str          # 신호 발생 시간

@dataclass
class PriceAttractiveness:
    """가격 매력도 분석 결과"""
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
    technical_signals: List[TechnicalSignal]
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

class TechnicalIndicators:
    """기술적 지표 계산 클래스"""
    
    @staticmethod
    def calculate_bollinger_bands(p_prices: List[float], p_period: int = 20, p_std_dev: float = 2.0) -> Tuple[float, float, float]:
        """볼린저 밴드 계산
        
        Args:
            p_prices: 가격 리스트
            p_period: 이동평균 기간
            p_std_dev: 표준편차 배수
            
        Returns:
            (상단밴드, 중간밴드, 하단밴드)
        """
        if len(p_prices) < p_period:
            # 데이터가 부족한 경우 현재가 기준으로 임시 밴드 생성
            if len(p_prices) > 0:
                _v_current = p_prices[-1]
                _v_middle = _v_current
                _v_std = _v_current * 0.02  # 2% 표준편차 가정
                _v_upper = _v_middle + (p_std_dev * _v_std)
                _v_lower = _v_middle - (p_std_dev * _v_std)
                return _v_upper, _v_middle, _v_lower
            else:
                return 0.0, 0.0, 0.0
            
        _v_prices = np.array(p_prices[-p_period:])
        _v_middle = np.mean(_v_prices)
        _v_std = np.std(_v_prices)
        
        # 표준편차가 0인 경우 (모든 가격이 동일) 처리
        if _v_std == 0:
            _v_std = _v_middle * 0.01  # 1% 기본 표준편차
        
        _v_upper = _v_middle + (p_std_dev * _v_std)
        _v_lower = _v_middle - (p_std_dev * _v_std)
        
        return _v_upper, _v_middle, _v_lower
    
    @staticmethod
    def calculate_macd(p_prices: List[float], p_fast: int = 12, p_slow: int = 26, p_signal: int = 9) -> Tuple[float, float, float]:
        """MACD 계산
        
        Args:
            p_prices: 가격 리스트
            p_fast: 빠른 이동평균 기간
            p_slow: 느린 이동평균 기간
            p_signal: 신호선 기간
            
        Returns:
            (MACD, Signal, Histogram)
        """
        if len(p_prices) < p_slow + p_signal:
            return 0.0, 0.0, 0.0
            
        _v_prices = np.array(p_prices)
        
        # EMA 계산
        _v_ema_fast = TechnicalIndicators._calculate_ema(_v_prices, p_fast)
        _v_ema_slow = TechnicalIndicators._calculate_ema(_v_prices, p_slow)
        
        _v_macd = _v_ema_fast - _v_ema_slow
        _v_signal = TechnicalIndicators._calculate_ema(_v_macd, p_signal)
        _v_histogram = _v_macd - _v_signal
        
        return float(_v_macd[-1]), float(_v_signal[-1]), float(_v_histogram[-1])
    
    @staticmethod
    def calculate_rsi(p_prices: List[float], p_period: int = 14) -> float:
        """RSI 계산
        
        Args:
            p_prices: 가격 리스트
            p_period: 계산 기간
            
        Returns:
            RSI 값
        """
        if len(p_prices) < p_period + 1:
            return 50.0
            
        _v_prices = np.array(p_prices)
        _v_deltas = np.diff(_v_prices)
        
        _v_gains = np.where(_v_deltas > 0, _v_deltas, 0)
        _v_losses = np.where(_v_deltas < 0, -_v_deltas, 0)
        
        _v_avg_gain = np.mean(_v_gains[-p_period:])
        _v_avg_loss = np.mean(_v_losses[-p_period:])
        
        if _v_avg_loss == 0:
            return 100.0
            
        _v_rs = _v_avg_gain / _v_avg_loss
        _v_rsi = 100 - (100 / (1 + _v_rs))
        
        return float(_v_rsi)
    
    @staticmethod
    def calculate_stochastic(p_highs: List[float], p_lows: List[float], p_closes: List[float], 
                           p_k_period: int = 14, p_d_period: int = 3) -> Tuple[float, float]:
        """스토캐스틱 계산
        
        Args:
            p_highs: 고가 리스트
            p_lows: 저가 리스트
            p_closes: 종가 리스트
            p_k_period: %K 기간
            p_d_period: %D 기간
            
        Returns:
            (%K, %D)
        """
        if len(p_closes) < p_k_period:
            return 50.0, 50.0
            
        _v_highs = np.array(p_highs[-p_k_period:])
        _v_lows = np.array(p_lows[-p_k_period:])
        _v_close = p_closes[-1]
        
        _v_highest_high = np.max(_v_highs)
        _v_lowest_low = np.min(_v_lows)
        
        if _v_highest_high == _v_lowest_low:
            _v_k = 50.0
        else:
            _v_k = 100 * (_v_close - _v_lowest_low) / (_v_highest_high - _v_lowest_low)
        
        # %D는 %K의 이동평균 (간단히 현재값 사용)
        _v_d = _v_k
        
        return float(_v_k), float(_v_d)
    
    @staticmethod
    def calculate_cci(p_highs: List[float], p_lows: List[float], p_closes: List[float], p_period: int = 20) -> float:
        """CCI (Commodity Channel Index) 계산
        
        Args:
            p_highs: 고가 리스트
            p_lows: 저가 리스트
            p_closes: 종가 리스트
            p_period: 계산 기간
            
        Returns:
            CCI 값
        """
        if len(p_closes) < p_period:
            return 0.0
            
        # Typical Price 계산
        _v_tp = [(h + l + c) / 3 for h, l, c in zip(p_highs[-p_period:], p_lows[-p_period:], p_closes[-p_period:])]
        _v_sma = np.mean(_v_tp)
        
        # Mean Deviation 계산
        _v_mad = np.mean([abs(tp - _v_sma) for tp in _v_tp])
        
        if _v_mad == 0:
            return 0.0
            
        _v_cci = (_v_tp[-1] - _v_sma) / (0.015 * _v_mad)
        
        return float(_v_cci)
    
    @staticmethod
    def _calculate_ema(p_values: np.ndarray, p_period: int) -> np.ndarray:
        """지수이동평균 계산"""
        _v_alpha = 2.0 / (p_period + 1)
        _v_ema = np.zeros_like(p_values)
        _v_ema[0] = p_values[0]
        
        for i in range(1, len(p_values)):
            _v_ema[i] = _v_alpha * p_values[i] + (1 - _v_alpha) * _v_ema[i-1]
            
        return _v_ema

class PatternRecognition:
    """가격 패턴 인식 클래스"""
    
    @staticmethod
    def detect_support_resistance(p_prices: List[float], p_volumes: List[float] = None) -> Dict[str, float]:
        """지지선/저항선 감지
        
        Args:
            p_prices: 가격 리스트
            p_volumes: 거래량 리스트 (선택사항)
            
        Returns:
            지지선/저항선 정보
        """
        if len(p_prices) < 20:
            return {"support": 0.0, "resistance": 0.0, "strength": 0.0}
            
        _v_prices = np.array(p_prices[-20:])
        _v_current = _v_prices[-1]
        
        # 간단한 지지/저항선 계산 (최고가/최저가 기준)
        _v_resistance = np.max(_v_prices)
        _v_support = np.min(_v_prices)
        
        # 현재가와의 거리로 강도 계산
        _v_resistance_dist = (_v_resistance - _v_current) / _v_current
        _v_support_dist = (_v_current - _v_support) / _v_current
        
        _v_strength = min(_v_resistance_dist, _v_support_dist) * 100
        
        return {
            "support": float(_v_support),
            "resistance": float(_v_resistance),
            "strength": float(_v_strength)
        }
    
    @staticmethod
    def detect_candlestick_patterns(p_ohlc_data: List[Dict]) -> List[str]:
        """캔들스틱 패턴 감지
        
        Args:
            p_ohlc_data: OHLC 데이터 리스트
            
        Returns:
            감지된 패턴 리스트
        """
        if len(p_ohlc_data) < 3:
            return []
            
        _v_patterns = []
        _v_last = p_ohlc_data[-1]
        _v_prev = p_ohlc_data[-2] if len(p_ohlc_data) >= 2 else _v_last
        
        # 망치형 패턴 (Hammer)
        if PatternRecognition._is_hammer(_v_last):
            _v_patterns.append("hammer")
        
        # 도지 패턴 (Doji)
        if PatternRecognition._is_doji(_v_last):
            _v_patterns.append("doji")
        
        # 엔걸핑 패턴 (Engulfing)
        if PatternRecognition._is_bullish_engulfing(_v_prev, _v_last):
            _v_patterns.append("bullish_engulfing")
        
        return _v_patterns
    
    @staticmethod
    def _is_hammer(p_candle: Dict) -> bool:
        """망치형 패턴 판정"""
        _v_body = abs(p_candle["close"] - p_candle["open"])
        _v_lower_shadow = min(p_candle["open"], p_candle["close"]) - p_candle["low"]
        _v_upper_shadow = p_candle["high"] - max(p_candle["open"], p_candle["close"])
        
        return (_v_lower_shadow > 2 * _v_body and 
                _v_upper_shadow < 0.1 * _v_body and 
                _v_body > 0)
    
    @staticmethod
    def _is_doji(p_candle: Dict) -> bool:
        """도지 패턴 판정"""
        _v_body = abs(p_candle["close"] - p_candle["open"])
        _v_range = p_candle["high"] - p_candle["low"]
        
        return _v_body < 0.1 * _v_range if _v_range > 0 else False
    
    @staticmethod
    def _is_bullish_engulfing(p_prev: Dict, p_current: Dict) -> bool:
        """상승 엔걸핑 패턴 판정"""
        _v_prev_bearish = p_prev["close"] < p_prev["open"]
        _v_current_bullish = p_current["close"] > p_current["open"]
        _v_engulfing = (p_current["open"] < p_prev["close"] and 
                       p_current["close"] > p_prev["open"])
        
        return _v_prev_bearish and _v_current_bullish and _v_engulfing

class VolumeAnalysis:
    """거래량 분석 클래스 (향상된 버전)"""
    
    @staticmethod
    def analyze_volume_pattern(p_volumes: List[float], p_prices: List[float]) -> Dict[str, float]:
        """거래량 패턴 분석 (기본 버전)
        
        Args:
            p_volumes: 거래량 리스트
            p_prices: 가격 리스트
            
        Returns:
            거래량 분석 결과
        """
        if len(p_volumes) < 20 or len(p_prices) < 20:
            return {"volume_surge": 0.0, "price_volume_correlation": 0.0, "volume_trend": 0.0}
        
        _v_volumes = np.array(p_volumes[-20:])
        _v_prices = np.array(p_prices[-20:])
        _v_current_volume = _v_volumes[-1]
        _v_avg_volume = np.mean(_v_volumes[:-1])
        
        # 거래량 급증 계산
        _v_volume_surge = (_v_current_volume / _v_avg_volume) if _v_avg_volume > 0 else 1.0
        
        # 가격-거래량 상관관계
        _v_price_changes = np.diff(_v_prices)
        _v_volume_changes = np.diff(_v_volumes)
        
        if len(_v_price_changes) > 0 and len(_v_volume_changes) > 0:
            _v_correlation = np.corrcoef(_v_price_changes, _v_volume_changes)[0, 1]
            _v_correlation = 0.0 if np.isnan(_v_correlation) else _v_correlation
        else:
            _v_correlation = 0.0
        
        # 거래량 추세
        _v_volume_trend = np.polyfit(range(len(_v_volumes)), _v_volumes, 1)[0]
        
        return {
            "volume_surge": float(_v_volume_surge),
            "price_volume_correlation": float(_v_correlation),
            "volume_trend": float(_v_volume_trend)
        }
    
    @staticmethod
    def analyze_enhanced_volume_pattern(p_ohlcv_data: pd.DataFrame) -> Dict[str, Any]:
        """향상된 거래량 패턴 분석
        
        Args:
            p_ohlcv_data: OHLCV 데이터
            
        Returns:
            향상된 거래량 분석 결과
        """
        try:
            if p_ohlcv_data is None or len(p_ohlcv_data) < 20:
                return {"enhanced_analysis": False, "basic_score": 50.0}
            
            # 1. 거래량-가격 조합 분석
            _v_volume_price_analyzer = VolumePriceAnalyzer(p_ohlcv_data)
            _v_volume_price_analysis = _v_volume_price_analyzer.calculate("comprehensive")
            
            # 2. 상대적 거래량 강도 분석
            _v_relative_volume_analyzer = RelativeVolumeStrength(p_ohlcv_data)
            _v_relative_volume_analysis = _v_relative_volume_analyzer.calculate("comprehensive")
            
            # 3. 거래량 클러스터 분석
            _v_cluster_analyzer = VolumeClusterAnalyzer(p_ohlcv_data)
            _v_cluster_analysis = _v_cluster_analyzer.calculate("comprehensive")
            
            # 4. 종합 점수 계산
            _v_combined_score = VolumeAnalysis._calculate_enhanced_volume_score(
                _v_volume_price_analysis,
                _v_relative_volume_analysis,
                _v_cluster_analysis
            )
            
            return {
                "enhanced_analysis": True,
                "combined_score": _v_combined_score,
                "volume_price_analysis": _v_volume_price_analysis,
                "relative_volume_analysis": _v_relative_volume_analysis,
                "cluster_analysis": _v_cluster_analysis
            }
            
        except Exception as e:
            logger.error(f"향상된 거래량 분석 중 오류 발생: {e}")
            return {"enhanced_analysis": False, "basic_score": 50.0}
    
    @staticmethod
    def _calculate_enhanced_volume_score(p_volume_price_analysis: Dict, 
                                      p_relative_volume_analysis: Dict, 
                                      p_cluster_analysis: Dict) -> float:
        """향상된 거래량 점수 계산
        
        Args:
            p_volume_price_analysis: 거래량-가격 분석 결과
            p_relative_volume_analysis: 상대적 거래량 분석 결과
            p_cluster_analysis: 클러스터 분석 결과
            
        Returns:
            향상된 거래량 점수 (0-100)
        """
        _v_score = 0.0
        
        # 1. 거래량-가격 조합 점수 (40점)
        _v_correlation = p_volume_price_analysis.get("correlation", 0.0)
        _v_divergence = p_volume_price_analysis.get("divergence", {})
        _v_momentum = p_volume_price_analysis.get("momentum", {})
        
        # 상관관계 점수 (15점)
        _v_correlation_score = min(abs(_v_correlation) * 15, 15)
        
        # 다이버전스 점수 (15점)
        _v_divergence_signal = _v_divergence.get("signal", "neutral")
        if _v_divergence_signal == "bullish_divergence":
            _v_divergence_score = 15
        elif _v_divergence_signal == "neutral":
            _v_divergence_score = 8
        else:
            _v_divergence_score = 3
        
        # 모멘텀 점수 (10점)
        _v_momentum_strength = _v_momentum.get("strength", "neutral")
        if _v_momentum_strength == "strong_bullish":
            _v_momentum_score = 10
        elif _v_momentum_strength == "moderate_bullish":
            _v_momentum_score = 7
        elif _v_momentum_strength == "neutral":
            _v_momentum_score = 5
        else:
            _v_momentum_score = 2
        
        _v_score += _v_correlation_score + _v_divergence_score + _v_momentum_score
        
        # 2. 상대적 거래량 강도 점수 (35점)
        _v_relative_ratio = p_relative_volume_analysis.get("relative_ratio", {})
        _v_rank = p_relative_volume_analysis.get("rank", {})
        _v_intensity = p_relative_volume_analysis.get("intensity", {})
        
        # 상대적 비율 점수 (15점)
        _v_vs_own_avg = _v_relative_ratio.get("vs_own_avg", 1.0)
        if _v_vs_own_avg >= 2.0:
            _v_ratio_score = 15
        elif _v_vs_own_avg >= 1.5:
            _v_ratio_score = 10
        elif _v_vs_own_avg >= 1.2:
            _v_ratio_score = 7
        else:
            _v_ratio_score = 3
        
        # 순위 점수 (10점)
        _v_percentile = _v_rank.get("percentile", 50.0)
        _v_rank_score = min(_v_percentile / 10, 10)
        
        # 강도 점수 (10점)
        _v_intensity_value = _v_intensity.get("intensity", 0.0)
        _v_intensity_score = min(_v_intensity_value * 2, 10)
        
        _v_score += _v_ratio_score + _v_rank_score + _v_intensity_score
        
        # 3. 클러스터 분석 점수 (25점)
        _v_clusters = p_cluster_analysis.get("clusters", [])
        _v_distribution = p_cluster_analysis.get("distribution", {})
        _v_anomalies = p_cluster_analysis.get("anomalies", [])
        
        # 클러스터 점수 (10점)
        _v_cluster_count = len(_v_clusters)
        _v_cluster_score = min(_v_cluster_count * 2, 10)
        
        # 분포 점수 (10점)
        _v_skewness = abs(_v_distribution.get("skewness", 0.0))
        _v_distribution_score = min(_v_skewness * 5, 10)
        
        # 이상치 점수 (5점)
        _v_high_anomalies = [a for a in _v_anomalies if a.get("anomaly_type") == "high"]
        _v_anomaly_score = min(len(_v_high_anomalies), 5)
        
        _v_score += _v_cluster_score + _v_distribution_score + _v_anomaly_score
        
        return min(_v_score, 100.0)
    
    @staticmethod
    def calculate_volume_score(p_volume_data: Dict[str, float]) -> float:
        """거래량 점수 계산 (기본 버전)
        
        Args:
            p_volume_data: 거래량 분석 데이터
            
        Returns:
            거래량 점수 (0-100)
        """
        _v_surge_score = min(p_volume_data.get("volume_surge", 1.0) * 20, 40)
        _v_correlation_score = abs(p_volume_data.get("price_volume_correlation", 0.0)) * 30
        _v_trend_score = max(0, p_volume_data.get("volume_trend", 0.0) * 1000000) * 30
        
        return min(_v_surge_score + _v_correlation_score + _v_trend_score, 100.0)
    
    @staticmethod
    def calculate_enhanced_volume_score(p_stock_data: Dict, p_ohlcv_data: pd.DataFrame = None) -> float:
        """향상된 거래량 점수 계산
        
        Args:
            p_stock_data: 주식 데이터
            p_ohlcv_data: OHLCV 데이터 (선택적)
            
        Returns:
            향상된 거래량 점수 (0-100)
        """
        try:
            # 향상된 분석이 가능한 경우
            if p_ohlcv_data is not None and len(p_ohlcv_data) >= 20:
                _v_enhanced_analysis = VolumeAnalysis.analyze_enhanced_volume_pattern(p_ohlcv_data)
                if _v_enhanced_analysis.get("enhanced_analysis", False):
                    return _v_enhanced_analysis.get("combined_score", 50.0)
            
            # 기본 분석 사용
            _v_volumes = [1000000 + i * 50000 for i in range(20)]
            _v_prices = [p_stock_data.get("current_price", 50000) * (1 + i * 0.01) for i in range(20)]
            
            _v_volume_data = VolumeAnalysis.analyze_volume_pattern(_v_volumes, _v_prices)
            return VolumeAnalysis.calculate_volume_score(_v_volume_data)
            
        except Exception as e:
            logger.error(f"향상된 거래량 점수 계산 중 오류 발생: {e}")
            return 50.0

class PriceAnalyzer:
    """가격 매력도 분석 메인 클래스"""
    
    def __init__(self, p_config_file: str = "core/config/api_config.py"):
        """초기화
        
        Args:
            p_config_file: 설정 파일 경로
        """
        self._v_config = APIConfig()
        self._v_indicators = TechnicalIndicators()
        self._v_patterns = PatternRecognition()
        self._v_volume_analysis = VolumeAnalysis()
        
        # 분석 가중치 설정 (기울기 분석 추가)
        self._v_weights = {
            "technical": 0.3,    # 기술적 지표
            "volume": 0.25,      # 거래량 분석
            "pattern": 0.25,     # 패턴 분석
            "slope": 0.2         # 기울기 분석 (NEW)
        }
        
        logger.info("가격 매력도 분석기 초기화 완료")
    
    def analyze_price_attractiveness(self, p_stock_data: Dict) -> PriceAttractiveness:
        """종목의 가격 매력도 분석
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            가격 매력도 분석 결과
        """
        try:
            _v_stock_code = p_stock_data.get("stock_code", "")
            _v_stock_name = p_stock_data.get("stock_name", "")
            
            logger.info(f"가격 매력도 분석 시작: {_v_stock_code} ({_v_stock_name})")
            
            # 기술적 분석
            _v_technical_score, _v_technical_signals = self._analyze_technical_indicators(p_stock_data)
            
            # 거래량 분석
            _v_volume_score = self._analyze_volume(p_stock_data)
            
            # 패턴 분석
            _v_pattern_score = self._analyze_patterns(p_stock_data)
            
            # 기울기 분석 (NEW)
            _v_slope_score, _v_slope_signals = self._analyze_slope_indicators(p_stock_data)
            
            # 종합 점수 계산
            _v_total_score = (
                _v_technical_score * self._v_weights["technical"] +
                _v_volume_score * self._v_weights["volume"] +
                _v_pattern_score * self._v_weights["pattern"] +
                _v_slope_score * self._v_weights["slope"]
            )
            
            # 기울기 신호를 기술적 신호에 통합
            _v_technical_signals.extend(_v_slope_signals)
            
            # 진입가, 목표가, 손절가 계산
            _v_entry_price = p_stock_data.get("current_price", 0.0)
            _v_target_price, _v_stop_loss = self._calculate_target_stop(_v_entry_price, _v_total_score)
            
            # 기대 수익률 및 리스크 계산
            _v_expected_return = ((_v_target_price - _v_entry_price) / _v_entry_price * 100) if _v_entry_price > 0 else 0.0
            _v_risk_score = self._calculate_risk_score(p_stock_data, _v_total_score)
            
            # 신뢰도 계산
            _v_confidence = self._calculate_confidence(_v_technical_signals, _v_total_score)
            
            # 선정 이유 생성
            _v_selection_reason = self._generate_selection_reason(_v_technical_signals, _v_total_score)
            
            # 시장 상황 및 섹터 모멘텀
            _v_market_condition = self._get_market_condition()
            _v_sector_momentum = p_stock_data.get("sector_momentum", 0.0)
            
            # 결과 생성
            _v_result = PriceAttractiveness(
                stock_code=_v_stock_code,
                stock_name=_v_stock_name,
                analysis_date=datetime.now().strftime("%Y-%m-%d"),
                current_price=_v_entry_price,
                total_score=_v_total_score,
                technical_score=_v_technical_score,
                volume_score=_v_volume_score,
                pattern_score=_v_pattern_score,
                technical_signals=_v_technical_signals,
                entry_price=_v_entry_price,
                target_price=_v_target_price,
                stop_loss=_v_stop_loss,
                expected_return=_v_expected_return,
                risk_score=_v_risk_score,
                confidence=_v_confidence,
                selection_reason=_v_selection_reason,
                market_condition=_v_market_condition,
                sector_momentum=_v_sector_momentum,
                sector=p_stock_data.get("sector", "기타")
            )
            
            logger.info(f"가격 매력도 분석 완료: {_v_stock_code} - 점수: {_v_total_score:.1f}")
            
            return _v_result
            
        except Exception as e:
            logger.error(f"가격 매력도 분석 중 오류 발생: {e}")
            return self._create_default_result(p_stock_data)
    
    def _analyze_technical_indicators(self, p_stock_data: Dict) -> Tuple[float, List[TechnicalSignal]]:
        """기술적 지표 분석
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            (기술적 점수, 기술적 신호 리스트)
        """
        _v_signals = []
        _v_scores = []
        
        # 더미 가격 데이터 생성 (실제로는 API에서 가져옴)
        _v_prices = self._generate_dummy_price_data(p_stock_data.get("current_price", 50000))
        _v_highs = [p * 1.02 for p in _v_prices]
        _v_lows = [p * 0.98 for p in _v_prices]
        _v_volumes = [1000000 + i * 10000 for i in range(len(_v_prices))]
        
        # 볼린저 밴드 분석
        _v_bb_upper, _v_bb_middle, _v_bb_lower = self._v_indicators.calculate_bollinger_bands(_v_prices)
        _v_current_price = _v_prices[-1]
        
        if _v_current_price <= _v_bb_lower * 1.02:  # 하단 밴드 근처
            _v_signals.append(TechnicalSignal(
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
        _v_macd, _v_signal, _v_histogram = self._v_indicators.calculate_macd(_v_prices)
        if _v_macd > _v_signal and _v_histogram > 0:
            _v_signals.append(TechnicalSignal(
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
        _v_rsi = self._v_indicators.calculate_rsi(_v_prices)
        if _v_rsi <= 30:
            _v_signals.append(TechnicalSignal(
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
        
        # 스토캐스틱 분석
        _v_k, _v_d = self._v_indicators.calculate_stochastic(_v_highs, _v_lows, _v_prices)
        if _v_k <= 20 and _v_d <= 20:
            _v_signals.append(TechnicalSignal(
                signal_type="stochastic",
                signal_name="stochastic_oversold",
                strength=75.0,
                confidence=0.6,
                description="스토캐스틱 과매도 신호",
                timestamp=datetime.now().isoformat()
            ))
            _v_scores.append(75.0)
        else:
            _v_scores.append(45.0)
        
        # CCI 분석
        _v_cci = self._v_indicators.calculate_cci(_v_highs, _v_lows, _v_prices)
        if _v_cci <= -100:
            _v_signals.append(TechnicalSignal(
                signal_type="cci",
                signal_name="cci_oversold",
                strength=70.0,
                confidence=0.5,
                description="CCI 과매도 구간 진입",
                timestamp=datetime.now().isoformat()
            ))
            _v_scores.append(70.0)
        else:
            _v_scores.append(40.0)
        
        _v_technical_score = np.mean(_v_scores) if _v_scores else 50.0
        
        return _v_technical_score, _v_signals
    
    def _analyze_volume(self, p_stock_data: Dict) -> float:
        """거래량 분석 (향상된 버전)
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            거래량 점수
        """
        try:
            # OHLCV 데이터 생성
            _v_ohlcv_data = self._generate_ohlcv_data(p_stock_data)
            
            # 향상된 거래량 분석 시도
            _v_enhanced_score = self._v_volume_analysis.calculate_enhanced_volume_score(
                p_stock_data, _v_ohlcv_data
            )
            
            logger.debug(f"향상된 거래량 분석 점수: {_v_enhanced_score:.1f}")
            
            return _v_enhanced_score
            
        except Exception as e:
            logger.error(f"거래량 분석 중 오류 발생: {e}")
            
            # 기본 거래량 분석으로 폴백
            _v_volumes = [1000000 + i * 50000 for i in range(20)]
            _v_prices = [p_stock_data.get("current_price", 50000) * (1 + i * 0.01) for i in range(20)]
            
            _v_volume_data = self._v_volume_analysis.analyze_volume_pattern(_v_volumes, _v_prices)
            _v_volume_score = self._v_volume_analysis.calculate_volume_score(_v_volume_data)
            
            return _v_volume_score
    
    def _analyze_patterns(self, p_stock_data: Dict) -> float:
        """패턴 분석
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            패턴 점수
        """
        _v_current_price = p_stock_data.get("current_price", 50000)
        
        # 더미 OHLC 데이터 생성
        _v_ohlc_data = []
        for i in range(5):
            _v_base_price = _v_current_price * (1 + (i - 2) * 0.01)
            _v_ohlc_data.append({
                "open": _v_base_price,
                "high": _v_base_price * 1.02,
                "low": _v_base_price * 0.98,
                "close": _v_base_price * (1.01 if i % 2 == 0 else 0.99)
            })
        
        # 패턴 감지
        _v_patterns = self._v_patterns.detect_candlestick_patterns(_v_ohlc_data)
        _v_support_resistance = self._v_patterns.detect_support_resistance([d["close"] for d in _v_ohlc_data])
        
        # 패턴 점수 계산
        _v_pattern_score = 50.0  # 기본 점수
        
        if "hammer" in _v_patterns:
            _v_pattern_score += 20.0
        if "bullish_engulfing" in _v_patterns:
            _v_pattern_score += 25.0
        if "doji" in _v_patterns:
            _v_pattern_score += 10.0
        
        # 지지선 근처에서 추가 점수
        _v_support = _v_support_resistance.get("support", 0)
        if _v_support > 0 and abs(_v_current_price - _v_support) / _v_current_price < 0.02:
            _v_pattern_score += 15.0
        
        return min(_v_pattern_score, 100.0)
    
    def _analyze_slope_indicators(self, p_stock_data: Dict) -> Tuple[float, List[TechnicalSignal]]:
        """기울기 지표 분석
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            (기울기 점수, 기울기 신호 리스트)
        """
        _v_signals = []
        _v_score = 0.0
        
        try:
            # OHLCV 데이터 생성
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
    
    def _calculate_target_stop(self, p_entry_price: float, p_score: float) -> Tuple[float, float]:
        """목표가와 손절가 계산
        
        Args:
            p_entry_price: 진입가
            p_score: 매력도 점수
            
        Returns:
            (목표가, 손절가)
        """
        # 점수에 따른 목표 수익률 조정
        _v_target_return = 0.05 + (p_score / 100) * 0.15  # 5-20%
        _v_stop_loss_ratio = 0.05  # 5% 손절
        
        _v_target_price = p_entry_price * (1 + _v_target_return)
        _v_stop_loss = p_entry_price * (1 - _v_stop_loss_ratio)
        
        return _v_target_price, _v_stop_loss
    
    def _calculate_risk_score(self, p_stock_data: Dict, p_total_score: float) -> float:
        """리스크 점수 계산
        
        Args:
            p_stock_data: 종목 데이터
            p_total_score: 총 매력도 점수
            
        Returns:
            리스크 점수 (0-100, 높을수록 위험)
        """
        _v_base_risk = 100 - p_total_score  # 매력도가 높을수록 리스크 낮음
        
        # 변동성 고려
        _v_volatility = p_stock_data.get("volatility", 0.25)
        _v_volatility_risk = _v_volatility * 100
        
        # 시가총액 고려 (작을수록 위험)
        _v_market_cap = p_stock_data.get("market_cap", 1000000000000)
        _v_size_risk = max(0, 50 - (_v_market_cap / 1000000000000) * 10)
        
        _v_total_risk = (_v_base_risk + _v_volatility_risk + _v_size_risk) / 3
        
        return min(_v_total_risk, 100.0)
    
    def _calculate_confidence(self, p_signals: List[TechnicalSignal], p_score: float) -> float:
        """신뢰도 계산
        
        Args:
            p_signals: 기술적 신호 리스트
            p_score: 총 점수
            
        Returns:
            신뢰도 (0-1)
        """
        if not p_signals:
            return 0.3
        
        _v_signal_confidence = np.mean([signal.confidence for signal in p_signals])
        _v_score_confidence = p_score / 100
        
        return (_v_signal_confidence + _v_score_confidence) / 2
    
    def _generate_selection_reason(self, p_signals: List[TechnicalSignal], p_score: float) -> str:
        """선정 이유 생성
        
        Args:
            p_signals: 기술적 신호 리스트
            p_score: 총 점수
            
        Returns:
            선정 이유 문자열
        """
        if not p_signals:
            return f"종합 점수 {p_score:.1f}점으로 매수 고려 구간"
        
        _v_main_signals = [signal.description for signal in p_signals[:3]]
        return " + ".join(_v_main_signals)
    
    def _get_market_condition(self) -> str:
        """현재 시장 상황 판단
        
        Returns:
            시장 상황 ('bull_market', 'bear_market', 'sideways')
        """
        # 실제로는 시장 지수 분석을 통해 판단
        return "sideways"  # 임시로 횡보장 반환
    
    def _generate_dummy_price_data(self, p_current_price: float, p_days: int = 30) -> List[float]:
        """더미 가격 데이터 생성 (실제로는 API에서 가져옴)
        
        Args:
            p_current_price: 현재가
            p_days: 생성할 일수
            
        Returns:
            가격 데이터 리스트
        """
        _v_prices = []
        _v_price = p_current_price * 0.95  # 시작가는 현재가보다 5% 낮게
        
        for i in range(p_days):
            _v_change = np.random.normal(0, 0.02)  # 평균 0, 표준편차 2%의 변화
            _v_price *= (1 + _v_change)
            _v_prices.append(_v_price)
        
        # 마지막 가격을 현재가로 조정
        _v_prices[-1] = p_current_price
        
        return _v_prices
    
    def _create_default_result(self, p_stock_data: Dict) -> PriceAttractiveness:
        """기본 결과 객체 생성 (오류 시 사용)
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            기본 PriceAttractiveness 객체
        """
        _v_current_price = p_stock_data.get("current_price", 0.0)
        
        return PriceAttractiveness(
            stock_code=p_stock_data.get("stock_code", ""),
            stock_name=p_stock_data.get("stock_name", ""),
            analysis_date=datetime.now().strftime("%Y-%m-%d"),
            current_price=_v_current_price,
            total_score=50.0,
            technical_score=50.0,
            volume_score=50.0,
            pattern_score=50.0,
            technical_signals=[],
            entry_price=_v_current_price,
            target_price=_v_current_price * 1.05,
            stop_loss=_v_current_price * 0.95,
            expected_return=5.0,
            risk_score=50.0,
            confidence=0.3,
            selection_reason="분석 데이터 부족",
            market_condition="unknown",
            sector_momentum=0.0,
            sector=p_stock_data.get("sector", "")
        )
    
    def analyze_multiple_stocks(self, p_stock_list: List[Dict]) -> List[PriceAttractiveness]:
        """여러 종목 일괄 분석
        
        Args:
            p_stock_list: 종목 데이터 리스트
            
        Returns:
            분석 결과 리스트
        """
        _v_results = []
        
        logger.info(f"일괄 분석 시작: {len(p_stock_list)}개 종목")
        
        for i, stock_data in enumerate(p_stock_list):
            try:
                _v_result = self.analyze_price_attractiveness(stock_data)
                _v_results.append(_v_result)
                
                # 진행 상황 로깅
                if (i + 1) % 10 == 0:
                    logger.info(f"분석 진행: {i + 1}/{len(p_stock_list)} 완료")
                
                # API 호출 제한 고려한 딜레이
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"종목 분석 실패 ({stock_data.get('stock_code', 'Unknown')}): {e}")
                continue
        
        logger.info(f"일괄 분석 완료: {len(_v_results)}개 결과")
        return _v_results
    
    def save_analysis_results(self, p_results: List[PriceAttractiveness], p_file_path: str = None) -> bool:
        """분석 결과 저장
        
        Args:
            p_results: 분석 결과 리스트
            p_file_path: 저장 파일 경로
            
        Returns:
            저장 성공 여부
        """
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