"""
거래 관련 인터페이스들
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class OrderType(Enum):
    """주문 타입"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """주문 상태"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"


@dataclass
class Order:
    """주문 정보"""
    order_id: str
    stock_code: str
    order_type: OrderType
    quantity: int
    price: float
    status: OrderStatus
    timestamp: datetime
    filled_quantity: int = 0
    filled_price: float = 0.0


@dataclass
class Position:
    """포지션 정보"""
    stock_code: str
    quantity: int
    average_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    timestamp: datetime


@dataclass
class TradingSignal:
    """거래 신호"""
    stock_code: str
    signal_type: str  # BUY, SELL, HOLD
    strength: float   # 0-100
    confidence: float # 0-1
    target_price: float
    stop_loss: float
    reasoning: str
    timestamp: datetime


@dataclass
class RiskMetrics:
    """리스크 지표"""
    var_1d: float           # 1일 VaR
    var_5d: float           # 5일 VaR
    max_drawdown: float     # 최대 손실
    sharpe_ratio: float     # 샤프 비율
    volatility: float       # 변동성
    beta: float             # 베타
    correlation: float      # 시장 상관관계


class ITradingStrategy(ABC):
    """거래 전략 인터페이스"""
    
    @abstractmethod
    def generate_signals(self, market_data: Dict) -> List[TradingSignal]:
        """거래 신호 생성"""
        pass
    
    @abstractmethod
    def calculate_position_size(self, signal: TradingSignal, portfolio_value: float) -> int:
        """포지션 크기 계산"""
        pass
    
    @abstractmethod
    def should_exit_position(self, position: Position, current_data: Dict) -> bool:
        """포지션 청산 여부 판단"""
        pass
    
    @abstractmethod
    def get_strategy_parameters(self) -> Dict:
        """전략 파라미터 조회"""
        pass
    
    @abstractmethod
    def set_strategy_parameters(self, params: Dict) -> bool:
        """전략 파라미터 설정"""
        pass
    
    @abstractmethod
    def backtest(self, historical_data: pd.DataFrame) -> Dict:
        """백테스트 실행"""
        pass


class ITrader(ABC):
    """거래 실행자 인터페이스"""
    
    @abstractmethod
    async def execute_order(self, order: Order) -> bool:
        """주문 실행"""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """주문 취소"""
        pass
    
    @abstractmethod
    def get_order_status(self, order_id: str) -> OrderStatus:
        """주문 상태 조회"""
        pass
    
    @abstractmethod
    def get_active_orders(self) -> List[Order]:
        """활성 주문 조회"""
        pass
    
    @abstractmethod
    def get_order_history(self, days: int = 30) -> List[Order]:
        """주문 이력 조회"""
        pass
    
    @abstractmethod
    async def start_trading(self, target_codes: List[str]) -> bool:
        """거래 시작"""
        pass
    
    @abstractmethod
    async def stop_trading(self) -> bool:
        """거래 중지"""
        pass
    
    @abstractmethod
    def is_trading_active(self) -> bool:
        """거래 활성 상태 확인"""
        pass


class IPositionManager(ABC):
    """포지션 관리자 인터페이스"""
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """포지션 목록 조회"""
        pass
    
    @abstractmethod
    def get_position(self, stock_code: str) -> Optional[Position]:
        """특정 종목 포지션 조회"""
        pass
    
    @abstractmethod
    def update_position(self, stock_code: str, quantity: int, price: float) -> bool:
        """포지션 업데이트"""
        pass
    
    @abstractmethod
    def close_position(self, stock_code: str) -> bool:
        """포지션 청산"""
        pass
    
    @abstractmethod
    def calculate_portfolio_value(self) -> float:
        """포트폴리오 가치 계산"""
        pass
    
    @abstractmethod
    def calculate_unrealized_pnl(self) -> float:
        """미실현 손익 계산"""
        pass
    
    @abstractmethod
    def calculate_realized_pnl(self) -> float:
        """실현 손익 계산"""
        pass
    
    @abstractmethod
    def get_portfolio_summary(self) -> Dict:
        """포트폴리오 요약 조회"""
        pass


class IRiskManager(ABC):
    """리스크 관리자 인터페이스"""
    
    @abstractmethod
    def calculate_risk_metrics(self, positions: List[Position]) -> RiskMetrics:
        """리스크 지표 계산"""
        pass
    
    @abstractmethod
    def check_position_risk(self, position: Position) -> bool:
        """포지션 리스크 확인"""
        pass
    
    @abstractmethod
    def check_portfolio_risk(self, positions: List[Position]) -> bool:
        """포트폴리오 리스크 확인"""
        pass
    
    @abstractmethod
    def suggest_position_size(self, signal: TradingSignal, portfolio_value: float) -> int:
        """리스크 기반 포지션 크기 제안"""
        pass
    
    @abstractmethod
    def should_stop_trading(self, portfolio_metrics: Dict) -> bool:
        """거래 중지 여부 판단"""
        pass
    
    @abstractmethod
    def get_risk_limits(self) -> Dict:
        """리스크 한계 조회"""
        pass
    
    @abstractmethod
    def set_risk_limits(self, limits: Dict) -> bool:
        """리스크 한계 설정"""
        pass


class IPortfolioOptimizer(ABC):
    """포트폴리오 최적화 인터페이스"""
    
    @abstractmethod
    def optimize_portfolio(self, available_stocks: List[str], 
                         expected_returns: Dict[str, float],
                         risk_matrix: pd.DataFrame) -> Dict[str, float]:
        """포트폴리오 최적화"""
        pass
    
    @abstractmethod
    def rebalance_portfolio(self, current_positions: List[Position],
                          target_weights: Dict[str, float]) -> List[Order]:
        """포트폴리오 리밸런싱"""
        pass
    
    @abstractmethod
    def calculate_efficient_frontier(self, stocks: List[str],
                                   expected_returns: Dict[str, float],
                                   risk_matrix: pd.DataFrame) -> List[Dict]:
        """효율적 프런티어 계산"""
        pass


class IPerformanceAnalyzer(ABC):
    """성과 분석기 인터페이스"""
    
    @abstractmethod
    def calculate_returns(self, positions: List[Position], 
                         time_period: str = "daily") -> pd.Series:
        """수익률 계산"""
        pass
    
    @abstractmethod
    def calculate_benchmark_comparison(self, portfolio_returns: pd.Series,
                                     benchmark_returns: pd.Series) -> Dict:
        """벤치마크 비교"""
        pass
    
    @abstractmethod
    def generate_performance_report(self, positions: List[Position],
                                  orders: List[Order]) -> Dict:
        """성과 보고서 생성"""
        pass
    
    @abstractmethod
    def calculate_attribution_analysis(self, positions: List[Position]) -> Dict:
        """성과 기여도 분석"""
        pass


class IOrderManager(ABC):
    """주문 관리자 인터페이스"""
    
    @abstractmethod
    def create_order(self, stock_code: str, order_type: OrderType,
                    quantity: int, price: float) -> Order:
        """주문 생성"""
        pass
    
    @abstractmethod
    def validate_order(self, order: Order) -> bool:
        """주문 유효성 검증"""
        pass
    
    @abstractmethod
    def submit_order(self, order: Order) -> bool:
        """주문 제출"""
        pass
    
    @abstractmethod
    def monitor_orders(self) -> List[Order]:
        """주문 모니터링"""
        pass
    
    @abstractmethod
    def handle_order_fill(self, order_id: str, filled_quantity: int, 
                         filled_price: float) -> bool:
        """주문 체결 처리"""
        pass 

# ===== Phase 1: 감시 리스트 인터페이스 =====

@dataclass
class ScreeningResult:
    """스크리닝 결과 데이터 클래스"""
    stock_code: str
    stock_name: str
    passed: bool
    score: float
    details: Dict[str, Any]
    signals: List[str]
    timestamp: datetime

@dataclass
class WatchlistEntry:
    """감시 리스트 항목 데이터 클래스"""
    stock_code: str
    stock_name: str
    added_date: datetime
    added_reason: str
    target_price: float
    stop_loss: float
    sector: str
    screening_score: float
    status: str = "active"
    notes: str = ""

class IStockScreener(ABC):
    """주식 스크리닝 인터페이스"""
    
    @abstractmethod
    def screen_by_fundamentals(self, stock_data: Dict) -> Tuple[bool, float, Dict]:
        """기본 분석 기반 스크리닝"""
        pass
    
    @abstractmethod
    def screen_by_technical(self, stock_data: Dict) -> Tuple[bool, float, Dict]:
        """기술적 분석 기반 스크리닝"""
        pass
    
    @abstractmethod
    def screen_by_momentum(self, stock_data: Dict) -> Tuple[bool, float, Dict]:
        """모멘텀 분석 기반 스크리닝"""
        pass
    
    @abstractmethod
    def comprehensive_screening(self, stock_list: List[str]) -> List[ScreeningResult]:
        """종합 스크리닝 실행"""
        pass

class IWatchlistManager(ABC):
    """감시 리스트 관리 인터페이스"""
    
    @abstractmethod
    def add_stock(self, entry: WatchlistEntry) -> bool:
        """종목 추가"""
        pass
    
    @abstractmethod
    def remove_stock(self, stock_code: str, permanent: bool = False) -> bool:
        """종목 제거"""
        pass
    
    @abstractmethod
    def update_stock(self, stock_code: str, updates: Dict) -> bool:
        """종목 정보 업데이트"""
        pass
    
    @abstractmethod
    def get_stock(self, stock_code: str) -> Optional[WatchlistEntry]:
        """종목 조회"""
        pass
    
    @abstractmethod
    def list_stocks(self, status: Optional[str] = None, sector: Optional[str] = None) -> List[WatchlistEntry]:
        """종목 목록 조회"""
        pass
    
    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """통계 정보 조회"""
        pass

# ===== Phase 2: 일일 선정 인터페이스 =====

@dataclass
class TechnicalSignal:
    """기술적 신호 데이터 클래스"""
    signal_type: str
    signal_name: str
    strength: float
    confidence: float
    description: str
    timestamp: datetime

@dataclass
class PriceAttractiveness:
    """가격 매력도 분석 결과"""
    stock_code: str
    stock_name: str
    analysis_date: datetime
    current_price: float
    
    # 종합 점수
    total_score: float
    technical_score: float
    volume_score: float
    pattern_score: float
    
    # 세부 분석 결과
    technical_signals: List[TechnicalSignal]
    entry_price: float
    target_price: float
    stop_loss: float
    expected_return: float
    risk_score: float
    confidence: float
    
    # 추가 정보
    selection_reason: str
    market_condition: str
    sector_momentum: float
    sector: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class DailySelection:
    """일일 선정 종목 데이터 클래스"""
    stock_code: str
    stock_name: str
    selection_date: datetime
    selection_reason: str
    price_attractiveness: float
    entry_price: float
    target_price: float
    stop_loss: float
    expected_return: float      # 기대 수익률 필드 추가
    risk_score: float
    volume_score: float
    technical_signals: List[str]
    sector: str
    market_cap: float
    priority: int
    position_size: float
    confidence: float           # 신뢰도 (0-1)
    predicted_class: int = 1    # 예측 분류 (0: 실패예상, 1: 성공예상) - Phase 4 학습용
    model_name: str = "ensemble"  # 예측 모델명

    def to_dict(self) -> Dict:
        return asdict(self)

class IPriceAnalyzer(ABC):
    """가격 분석 인터페이스"""
    
    @abstractmethod
    def analyze_price_attractiveness(self, stock_data: Dict) -> PriceAttractiveness:
        """단일 종목 가격 매력도 분석"""
        pass
    
    @abstractmethod
    def analyze_multiple_stocks(self, stock_list: List[Dict]) -> List[PriceAttractiveness]:
        """다중 종목 가격 매력도 분석"""
        pass
    
    @abstractmethod
    def analyze_technical_indicators(self, stock_data: Dict) -> Tuple[float, List[TechnicalSignal]]:
        """기술적 지표 분석"""
        pass
    
    @abstractmethod
    def analyze_volume_pattern(self, stock_data: Dict) -> float:
        """거래량 패턴 분석"""
        pass
    
    @abstractmethod
    def detect_patterns(self, stock_data: Dict) -> float:
        """가격 패턴 감지"""
        pass

class IDailyUpdater(ABC):
    """일일 업데이트 인터페이스"""
    
    @abstractmethod
    def run_daily_update(self, force_run: bool = False) -> bool:
        """일일 업데이트 실행"""
        pass
    
    @abstractmethod
    def analyze_market_condition(self) -> str:
        """시장 상황 분석"""
        pass
    
    @abstractmethod
    def filter_and_select_stocks(self, analysis_results: List[PriceAttractiveness]) -> List[PriceAttractiveness]:
        """종목 필터링 및 선정"""
        pass
    
    @abstractmethod
    def create_daily_trading_list(self, selected_stocks: List[PriceAttractiveness]) -> Dict:
        """일일 매매 리스트 생성"""
        pass
    
    @abstractmethod
    def start_scheduler(self) -> None:
        """스케줄러 시작"""
        pass
    
    @abstractmethod
    def stop_scheduler(self) -> None:
        """스케줄러 중지"""
        pass

# ===== 공통 유틸리티 인터페이스 =====

class IMarketDataProvider(ABC):
    """시장 데이터 제공 인터페이스"""
    
    @abstractmethod
    def get_stock_data(self, stock_code: str) -> Optional[Dict]:
        """종목 데이터 조회"""
        pass
    
    @abstractmethod
    def get_market_indicators(self) -> Dict[str, float]:
        """시장 지표 조회"""
        pass
    
    @abstractmethod
    def get_sector_data(self, sector: str) -> Dict[str, Any]:
        """섹터 데이터 조회"""
        pass


class ISellEngine(ABC):
    """매도 엔진 인터페이스"""
    
    @abstractmethod
    def add_position(self, stock_code: str, stock_name: str, entry_price: float, 
                    quantity: int, entry_date: str) -> bool:
        """포지션 추가"""
        pass
    
    @abstractmethod
    def update_position_price(self, stock_code: str, current_price: float) -> bool:
        """포지션 현재가 업데이트"""
        pass
    
    @abstractmethod
    def check_sell_signals(self, stock_data: Dict[str, Any]) -> List[Any]:
        """매도 신호 검사"""
        pass
    
    @abstractmethod
    def execute_sell_order(self, sell_signal: Any, quantity_ratio: float = 1.0) -> bool:
        """매도 주문 실행"""
        pass
    
    @abstractmethod
    def get_positions_summary(self) -> Dict[str, Any]:
        """포지션 요약 정보 반환"""
        pass


class ISellStrategy(ABC):
    """개별 매도 전략 인터페이스"""
    
    @abstractmethod
    def check_signal(self, position_info: Dict, stock_data: Dict) -> Optional[Any]:
        """매도 신호 확인"""
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """전략명 반환"""
        pass 