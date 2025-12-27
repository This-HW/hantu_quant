"""
백테스트 사용 예시

이 모듈은 백테스트 엔진의 다양한 사용 예시를 제공합니다.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.backtest import (
    BacktestEngine,
    BacktestConfig,
    RiskConfig,
    MACrossStrategy,
    RSIMeanReversionStrategy,
    BollingerBreakoutStrategy,
    CombinedStrategy,
    visualize_backtest,
    MODERATE_CONFIG,
)


def generate_sample_data(
    stock_codes: list,
    days: int = 500,
    start_price: float = 50000
) -> dict:
    """
    테스트용 샘플 데이터 생성

    Args:
        stock_codes: 종목 코드 리스트
        days: 데이터 일수
        start_price: 시작 가격

    Returns:
        종목별 OHLCV DataFrame 딕셔너리
    """
    np.random.seed(42)
    data = {}

    for code in stock_codes:
        dates = pd.date_range(
            end=datetime.now(),
            periods=days,
            freq='B'  # 영업일
        )

        # 랜덤 워크 + 추세
        returns = np.random.randn(days) * 0.02  # 2% 일간 변동성
        trend = np.linspace(0, 0.3, days)  # 30% 상승 추세
        price_mult = np.cumprod(1 + returns) * (1 + trend)
        close = start_price * price_mult

        # OHLCV 생성
        high = close * (1 + np.abs(np.random.randn(days)) * 0.01)
        low = close * (1 - np.abs(np.random.randn(days)) * 0.01)
        open_price = close * (1 + np.random.randn(days) * 0.005)
        volume = np.random.randint(100000, 1000000, days)

        df = pd.DataFrame({
            'open': open_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        }, index=dates)

        df.attrs['stock_code'] = code
        df.attrs['stock_name'] = f'샘플종목_{code}'
        data[code] = df

    return data


def example_basic_backtest():
    """기본 백테스트 예시"""
    print("=" * 60)
    print("예시 1: 기본 이동평균 크로스 전략 백테스트")
    print("=" * 60)

    # 1. 샘플 데이터 생성
    data = generate_sample_data(['005930', '035720', '000660'], days=500)

    # 2. 설정
    config = BacktestConfig(
        initial_capital=100_000_000,  # 1억원
        position_size_value=0.1,       # 10% 포지션
        risk=RiskConfig(
            max_positions=5,
            stop_loss_pct=0.03,        # 3% 손절
            take_profit_pct=0.08,      # 8% 익절
            use_dynamic_stops=False
        )
    )

    # 3. 전략
    strategy = MACrossStrategy(short_period=5, long_period=20)

    # 4. 백테스트 실행
    engine = BacktestEngine(config)
    result = engine.run(strategy, data)

    # 5. 결과 출력
    print(result.summary())

    return result


def example_rsi_strategy():
    """RSI 평균회귀 전략 예시"""
    print("=" * 60)
    print("예시 2: RSI 평균회귀 전략 백테스트")
    print("=" * 60)

    data = generate_sample_data(['005930', '035720'], days=400)

    config = BacktestConfig(
        initial_capital=50_000_000,
        position_size_value=0.15,
    )

    strategy = RSIMeanReversionStrategy(
        rsi_period=14,
        oversold=30,
        overbought=70
    )

    engine = BacktestEngine(config)
    result = engine.run(strategy, data)

    print(result.summary())
    return result


def example_bollinger_strategy():
    """볼린저 밴드 전략 예시"""
    print("=" * 60)
    print("예시 3: 볼린저 밴드 돌파 전략 백테스트")
    print("=" * 60)

    data = generate_sample_data(['005930'], days=300)

    strategy = BollingerBreakoutStrategy(
        period=20,
        std_dev=2.0
    )

    result = BacktestEngine(MODERATE_CONFIG).run(strategy, data)

    print(result.summary())
    return result


def example_combined_strategy():
    """복합 전략 예시"""
    print("=" * 60)
    print("예시 4: 복합 전략 (MA + RSI + Bollinger)")
    print("=" * 60)

    data = generate_sample_data(['005930', '035720', '000660'], days=500)

    # 여러 전략 조합
    strategies = [
        MACrossStrategy(short_period=5, long_period=20),
        RSIMeanReversionStrategy(rsi_period=14),
        BollingerBreakoutStrategy(period=20),
    ]

    combined = CombinedStrategy(
        strategies=strategies,
        min_agreement=2  # 최소 2개 전략 동의 시 진입
    )

    config = BacktestConfig(
        initial_capital=100_000_000,
        position_size_value=0.08,
        risk=RiskConfig(
            max_positions=8,
            use_trailing_stop=True
        )
    )

    result = BacktestEngine(config).run(combined, data)

    print(result.summary())
    return result


def example_with_visualization():
    """시각화 포함 예시"""
    print("=" * 60)
    print("예시 5: 시각화 포함 전체 분석")
    print("=" * 60)

    import os

    data = generate_sample_data(['005930', '035720', '000660', '051910'], days=500)

    strategy = MACrossStrategy(short_period=10, long_period=30)

    config = BacktestConfig(
        initial_capital=100_000_000,
        position_size_value=0.05,
        name="MA Cross Strategy Test"
    )

    result = BacktestEngine(config).run(strategy, data)

    print(result.summary())

    # 결과 저장
    output_dir = './backtest_results'
    os.makedirs(output_dir, exist_ok=True)

    # JSON 결과 저장
    result.to_json(f'{output_dir}/result.json')

    # 시각화 저장
    visualize_backtest(result, save_dir=output_dir, show=False)

    print(f"\n결과가 {output_dir}/ 에 저장되었습니다:")
    print("  - result.json: 백테스트 결과 데이터")
    print("  - equity_curve.png: 자산 곡선")
    print("  - returns_dist.png: 수익률 분포")
    print("  - metrics_summary.png: 지표 요약")
    print("  - report.html: HTML 보고서")

    return result


def example_compare_strategies():
    """전략 비교 예시"""
    print("=" * 60)
    print("예시 6: 여러 전략 성과 비교")
    print("=" * 60)

    data = generate_sample_data(['005930', '035720', '000660'], days=500)

    strategies = [
        ('MA Cross (5/20)', MACrossStrategy(5, 20)),
        ('MA Cross (10/30)', MACrossStrategy(10, 30)),
        ('RSI Mean Reversion', RSIMeanReversionStrategy()),
        ('Bollinger Breakout', BollingerBreakoutStrategy()),
    ]

    config = BacktestConfig(
        initial_capital=100_000_000,
        position_size_value=0.05,
    )

    results = []

    for name, strategy in strategies:
        engine = BacktestEngine(config)
        result = engine.run(strategy, data)
        results.append((name, result))

    # 비교 테이블 출력
    print("\n전략 비교 결과:")
    print("-" * 100)
    print(f"{'전략':<25} {'총수익률':>12} {'연환산':>10} {'MDD':>10} {'샤프':>8} {'승률':>8} {'거래수':>8}")
    print("-" * 100)

    for name, result in results:
        print(f"{name:<25} {result.total_return:>11.2f}% {result.annual_return:>9.2f}% "
              f"{result.max_drawdown:>9.2f}% {result.sharpe_ratio:>7.2f} "
              f"{result.win_rate:>7.1f}% {result.total_trades:>7}")

    print("-" * 100)

    return results


def example_with_real_data_integration():
    """실제 데이터 연동 예시 (구조만 제공)"""
    print("=" * 60)
    print("예시 7: 실제 데이터 연동 (KIS API)")
    print("=" * 60)

    print("""
실제 데이터 연동 예시 코드:

from core.api.kis_api import KISAPI
from core.backtest import BacktestEngine, BacktestConfig, MACrossStrategy

# KIS API 초기화
kis = KISAPI()

# 종목 리스트
stock_codes = ['005930', '035720', '000660']

# 과거 데이터 조회
data = {}
for code in stock_codes:
    df = kis.get_daily_prices(code, period=500)
    df.attrs['stock_code'] = code
    data[code] = df

# 백테스트 실행
config = BacktestConfig(initial_capital=100_000_000)
strategy = MACrossStrategy(short_period=5, long_period=20)

engine = BacktestEngine(config)
result = engine.run(strategy, data)

print(result.summary())
""")


if __name__ == '__main__':
    # 모든 예시 실행
    print("\n" + "=" * 80)
    print("백테스트 엔진 사용 예시")
    print("=" * 80 + "\n")

    # 기본 예시
    example_basic_backtest()
    print("\n")

    # RSI 전략
    example_rsi_strategy()
    print("\n")

    # 볼린저 밴드 전략
    example_bollinger_strategy()
    print("\n")

    # 복합 전략
    example_combined_strategy()
    print("\n")

    # 전략 비교
    example_compare_strategies()
    print("\n")

    # 시각화 예시
    example_with_visualization()
    print("\n")

    # 실제 데이터 연동 가이드
    example_with_real_data_integration()
