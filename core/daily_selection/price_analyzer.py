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
            _v_current_price = p_stock_data.get("current_price", 0.0)
            _v_sector = p_stock_data.get("sector", "")
            
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
        
        # 더미 가격 데이터 생성 (실제로는 API에서 가져옴)
        _v_prices = self._generate_dummy_price_data(p_stock_data.get("current_price", 50000))
        _v_highs = [p * 1.02 for p in _v_prices]
        _v_lows = [p * 0.98 for p in _v_prices]
        _v_volumes = [1000000 + i * 10000 for i in range(len(_v_prices))]
        
        # 볼린저 밴드 분석
        _v_bb_upper, _v_bb_middle, _v_bb_lower = TechnicalIndicators.calculate_bollinger_bands(_v_prices)
        _v_current_price = _v_prices[-1]
        
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
        
        # 스토캐스틱 분석
        _v_k, _v_d = self._v_indicators.calculate_stochastic(_v_highs, _v_lows, _v_prices)
        if _v_k <= 20 and _v_d <= 20:
            _v_signals.append(TechnicalSignalLegacy(
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
            _v_signals.append(TechnicalSignalLegacy(
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
        """거래량 분석 (향상된 버전)"""
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
        """패턴 분석"""
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
        """기울기 지표 분석"""
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
    
    def _calculate_target_stop(self, p_entry_price: float, p_score: float) -> Tuple[float, float]:
        """목표가와 손절가 계산"""
        # 점수에 따른 목표 수익률 조정
        _v_target_return = 0.05 + (p_score / 100) * 0.15  # 5-20%
        _v_stop_loss_ratio = 0.05  # 5% 손절
        
        _v_target_price = p_entry_price * (1 + _v_target_return)
        _v_stop_loss = p_entry_price * (1 - _v_stop_loss_ratio)
        
        return _v_target_price, _v_stop_loss
    
    def _calculate_risk_score(self, p_stock_data: Dict, p_total_score: float) -> float:
        """리스크 점수 계산"""
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