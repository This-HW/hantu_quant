"""
분석 관련 인터페이스 정의

이 모듈은 종목 분석을 위한 인터페이스들을 정의합니다.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any
import pandas as pd
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """분석 결과 기본 클래스"""
    stock_code: str
    stock_name: str
    analysis_date: str
    score: float
    confidence: float
    details: Dict[str, Any]


@dataclass
class ScreeningResult(AnalysisResult):
    """스크리닝 결과 클래스"""
    passed: bool
    fundamental_score: float
    technical_score: float
    momentum_score: float
    selection_reason: str


@dataclass
class PriceAnalysisResult(AnalysisResult):
    """가격 분석 결과 클래스"""
    current_price: float
    entry_price: float
    target_price: float
    stop_loss: float
    expected_return: float
    risk_score: float
    technical_signals: List[Dict]


class IStockScreener(ABC):
    """종목 스크리닝 인터페이스"""
    
    @abstractmethod
    def screen_by_fundamentals(self, stock_data: Dict) -> Tuple[bool, float, Dict]:
        """재무제표 기반 스크리닝"""
        pass
    
    @abstractmethod
    def screen_by_technical(self, stock_data: Dict) -> Tuple[bool, float, Dict]:
        """기술적 분석 기반 스크리닝"""
        pass
    
    @abstractmethod
    def screen_by_momentum(self, stock_data: Dict) -> Tuple[bool, float, Dict]:
        """모멘텀 기반 스크리닝"""
        pass
    
    @abstractmethod
    def comprehensive_screening(self, stock_list: List[str]) -> List[ScreeningResult]:
        """종합 스크리닝"""
        pass
    
    @abstractmethod
    def set_screening_criteria(self, criteria: Dict) -> bool:
        """스크리닝 기준 설정"""
        pass
    
    @abstractmethod
    def get_screening_criteria(self) -> Dict:
        """스크리닝 기준 조회"""
        pass


class IPriceAnalyzer(ABC):
    """가격 분석기 인터페이스"""
    
    @abstractmethod
    def analyze_price_attractiveness(self, stock_data: Dict) -> PriceAnalysisResult:
        """가격 매력도 분석"""
        pass
    
    @abstractmethod
    def analyze_multiple_stocks(self, stock_list: List[Dict]) -> List[PriceAnalysisResult]:
        """다중 종목 분석"""
        pass
    
    @abstractmethod
    def calculate_technical_indicators(self, stock_data: Dict) -> Dict:
        """기술적 지표 계산"""
        pass
    
    @abstractmethod
    def analyze_volume_pattern(self, stock_data: Dict) -> Dict:
        """거래량 패턴 분석"""
        pass
    
    @abstractmethod
    def detect_price_patterns(self, stock_data: Dict) -> List[Dict]:
        """가격 패턴 탐지"""
        pass
    
    @abstractmethod
    def calculate_risk_metrics(self, stock_data: Dict) -> Dict:
        """리스크 지표 계산"""
        pass


class ITechnicalIndicator(ABC):
    """기술적 지표 인터페이스"""
    
    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> Dict:
        """지표 계산"""
        pass
    
    @abstractmethod
    def get_signals(self, data: pd.DataFrame) -> List[Dict]:
        """매매 신호 생성"""
        pass
    
    @abstractmethod
    def get_parameters(self) -> Dict:
        """지표 파라미터 조회"""
        pass
    
    @abstractmethod
    def set_parameters(self, params: Dict) -> bool:
        """지표 파라미터 설정"""
        pass


class IMomentumIndicator(ITechnicalIndicator):
    """모멘텀 지표 인터페이스"""
    
    @abstractmethod
    def calculate_momentum(self, prices: List[float], period: int) -> float:
        """모멘텀 계산"""
        pass
    
    @abstractmethod
    def calculate_rsi(self, prices: List[float], period: int) -> float:
        """RSI 계산"""
        pass
    
    @abstractmethod
    def calculate_stochastic(self, highs: List[float], lows: List[float], 
                           closes: List[float], k_period: int, d_period: int) -> Tuple[float, float]:
        """스토캐스틱 계산"""
        pass


class ITrendIndicator(ITechnicalIndicator):
    """추세 지표 인터페이스"""
    
    @abstractmethod
    def calculate_moving_average(self, prices: List[float], period: int) -> float:
        """이동평균 계산"""
        pass
    
    @abstractmethod
    def calculate_macd(self, prices: List[float], fast: int, slow: int, signal: int) -> Tuple[float, float, float]:
        """MACD 계산"""
        pass
    
    @abstractmethod
    def calculate_bollinger_bands(self, prices: List[float], period: int, std_dev: float) -> Tuple[float, float, float]:
        """볼린저 밴드 계산"""
        pass
    
    @abstractmethod
    def calculate_slope(self, prices: List[float], period: int) -> float:
        """기울기 계산"""
        pass


class IVolumeIndicator(ITechnicalIndicator):
    """거래량 지표 인터페이스"""
    
    @abstractmethod
    def calculate_volume_profile(self, prices: List[float], volumes: List[float]) -> Dict:
        """거래량 프로파일 계산"""
        pass
    
    @abstractmethod
    def calculate_relative_volume(self, volumes: List[float], period: int) -> float:
        """상대 거래량 계산"""
        pass
    
    @abstractmethod
    def analyze_volume_price_trend(self, prices: List[float], volumes: List[float]) -> Dict:
        """거래량-가격 추세 분석"""
        pass


class IVolatilityIndicator(ITechnicalIndicator):
    """변동성 지표 인터페이스"""
    
    @abstractmethod
    def calculate_atr(self, highs: List[float], lows: List[float], closes: List[float], period: int) -> float:
        """ATR 계산"""
        pass
    
    @abstractmethod
    def calculate_volatility(self, prices: List[float], period: int) -> float:
        """변동성 계산"""
        pass
    
    @abstractmethod
    def calculate_volatility_percentile(self, prices: List[float], period: int, lookback: int) -> float:
        """변동성 백분위 계산"""
        pass


class IPatternRecognizer(ABC):
    """패턴 인식 인터페이스"""
    
    @abstractmethod
    def detect_candlestick_patterns(self, ohlc_data: List[Dict]) -> List[str]:
        """캔들스틱 패턴 탐지"""
        pass
    
    @abstractmethod
    def detect_chart_patterns(self, price_data: List[float]) -> List[Dict]:
        """차트 패턴 탐지"""
        pass
    
    @abstractmethod
    def detect_support_resistance(self, prices: List[float], volumes: List[float]) -> Dict:
        """지지/저항 탐지"""
        pass
    
    @abstractmethod
    def calculate_pattern_reliability(self, pattern_type: str, historical_data: List[Dict]) -> float:
        """패턴 신뢰도 계산"""
        pass 