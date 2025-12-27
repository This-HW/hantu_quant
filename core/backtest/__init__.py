"""
백테스트 엔진 패키지

과거 데이터로 전략을 검증하고 성과를 분석합니다.

사용 예시:
    from core.backtest import BacktestEngine, BacktestConfig, MACrossStrategy

    # 설정
    config = BacktestConfig(
        initial_capital=100_000_000,
        position_size_value=0.05
    )

    # 전략
    strategy = MACrossStrategy(short_period=5, long_period=20)

    # 백테스트 실행
    engine = BacktestEngine(config)
    result = engine.run(strategy, data)

    # 결과 출력
    print(result.summary())

    # 시각화
    from core.backtest import visualize_backtest
    visualize_backtest(result, save_dir='./results')
"""

from .config import (
    BacktestConfig,
    CommissionConfig,
    SlippageConfig,
    RiskConfig,
    PositionSizeMethod,
    CommissionType,
    CONSERVATIVE_CONFIG,
    MODERATE_CONFIG,
    AGGRESSIVE_CONFIG,
)

from .result import (
    BacktestResult,
    BacktestStatus,
    Trade,
    Position,
    DailySnapshot,
    MetricsCalculator,
)

from .strategy import (
    BaseStrategy,
    Signal,
    SignalType,
    MACrossStrategy,
    RSIMeanReversionStrategy,
    BollingerBreakoutStrategy,
    CombinedStrategy,
    LSTMPredictionStrategy,
)

from .engine import (
    BacktestEngine,
    run_backtest,
)

from .visualizer import (
    BacktestVisualizer,
    visualize_backtest,
)

__all__ = [
    # Config
    'BacktestConfig',
    'CommissionConfig',
    'SlippageConfig',
    'RiskConfig',
    'PositionSizeMethod',
    'CommissionType',
    'CONSERVATIVE_CONFIG',
    'MODERATE_CONFIG',
    'AGGRESSIVE_CONFIG',

    # Result
    'BacktestResult',
    'BacktestStatus',
    'Trade',
    'Position',
    'DailySnapshot',
    'MetricsCalculator',

    # Strategy
    'BaseStrategy',
    'Signal',
    'SignalType',
    'MACrossStrategy',
    'RSIMeanReversionStrategy',
    'BollingerBreakoutStrategy',
    'CombinedStrategy',
    'LSTMPredictionStrategy',

    # Engine
    'BacktestEngine',
    'run_backtest',

    # Visualizer
    'BacktestVisualizer',
    'visualize_backtest',
]

__version__ = '1.0.0'
