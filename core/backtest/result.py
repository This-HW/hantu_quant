"""
백테스트 결과 모듈

백테스트 실행 결과를 저장하고 성과 지표를 계산합니다.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime, date
from enum import Enum
import pandas as pd
import numpy as np
from scipy import stats
import json


class BacktestStatus(Enum):
    """백테스트 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Trade:
    """개별 거래 기록"""
    trade_id: int
    stock_code: str
    stock_name: str
    entry_date: str
    entry_price: float
    entry_quantity: int
    exit_date: Optional[str] = None
    exit_price: Optional[float] = None
    exit_quantity: Optional[int] = None
    side: str = "long"               # "long" 또는 "short"
    exit_reason: str = ""            # "signal", "stop_loss", "take_profit", "trailing", "timeout"

    # 비용
    entry_commission: float = 0
    exit_commission: float = 0
    slippage_cost: float = 0

    # 결과 (청산 후 계산)
    pnl: float = 0                   # 손익 (비용 차감 전)
    pnl_pct: float = 0               # 손익률 (%)
    net_pnl: float = 0               # 순손익 (비용 차감 후)
    net_pnl_pct: float = 0           # 순손익률 (%)
    holding_days: int = 0            # 보유 기간

    def is_closed(self) -> bool:
        return self.exit_date is not None

    def is_winner(self) -> bool:
        return self.net_pnl > 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Position:
    """현재 포지션"""
    stock_code: str
    stock_name: str
    entry_date: str
    entry_price: float
    quantity: int
    current_price: float = 0
    stop_loss: float = 0
    take_profit: float = 0
    trailing_stop: float = 0
    unrealized_pnl: float = 0
    unrealized_pnl_pct: float = 0
    highest_price: float = 0         # 트레일링 스탑용

    def update_price(self, price: float):
        """현재가 업데이트"""
        self.current_price = price
        self.highest_price = max(self.highest_price, price)
        self.unrealized_pnl = (price - self.entry_price) * self.quantity
        self.unrealized_pnl_pct = (price - self.entry_price) / self.entry_price * 100


@dataclass
class DailySnapshot:
    """일별 스냅샷"""
    date: str
    equity: float                    # 총 자산
    cash: float                      # 현금
    positions_value: float           # 포지션 가치
    daily_pnl: float                 # 일간 손익
    daily_return: float              # 일간 수익률
    cumulative_return: float         # 누적 수익률
    drawdown: float                  # 현재 낙폭
    num_positions: int               # 보유 포지션 수
    num_trades: int                  # 당일 거래 수


@dataclass
class BacktestResult:
    """백테스트 결과"""
    # 메타 정보
    backtest_id: str = ""
    strategy_name: str = ""
    start_date: str = ""
    end_date: str = ""
    status: BacktestStatus = BacktestStatus.PENDING
    execution_time: float = 0        # 실행 시간 (초)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 설정 정보
    initial_capital: float = 0
    final_capital: float = 0
    config_snapshot: Dict[str, Any] = field(default_factory=dict)

    # 수익률 지표
    total_return: float = 0          # 총 수익률 (%)
    annual_return: float = 0         # 연환산 수익률 (%)
    monthly_return_avg: float = 0    # 월평균 수익률 (%)
    daily_return_avg: float = 0      # 일평균 수익률 (%)
    daily_return_std: float = 0      # 일간 수익률 표준편차

    # 리스크 지표
    volatility: float = 0            # 연간 변동성
    max_drawdown: float = 0          # 최대 낙폭 (%)
    max_drawdown_duration: int = 0   # MDD 지속 기간 (일)
    avg_drawdown: float = 0          # 평균 낙폭 (%)

    # 위험조정수익률
    sharpe_ratio: float = 0          # 샤프 비율
    sortino_ratio: float = 0         # 소르티노 비율
    calmar_ratio: float = 0          # 칼마 비율
    information_ratio: float = 0     # 정보 비율

    # 거래 통계
    total_trades: int = 0            # 총 거래 수
    winning_trades: int = 0          # 승리 거래 수
    losing_trades: int = 0           # 패배 거래 수
    win_rate: float = 0              # 승률 (%)
    profit_factor: float = 0         # 손익비
    payoff_ratio: float = 0          # 평균 이익/평균 손실

    avg_profit: float = 0            # 평균 이익
    avg_loss: float = 0              # 평균 손실
    largest_win: float = 0           # 최대 이익
    largest_loss: float = 0          # 최대 손실
    consecutive_wins: int = 0        # 최대 연속 승리
    consecutive_losses: int = 0      # 최대 연속 패배
    avg_holding_days: float = 0      # 평균 보유 기간

    # 비용 분석
    total_commission: float = 0      # 총 수수료
    total_slippage: float = 0        # 총 슬리피지
    total_tax: float = 0             # 총 세금
    cost_return_impact: float = 0    # 비용이 수익률에 미친 영향 (%)

    # 고급 통계
    var_95: float = 0                # VaR 95%
    var_99: float = 0                # VaR 99%
    cvar_95: float = 0               # CVaR 95%
    cvar_99: float = 0               # CVaR 99%
    skewness: float = 0              # 왜도
    kurtosis: float = 0              # 첨도
    positive_months: int = 0         # 양수 수익 월 수
    negative_months: int = 0         # 음수 수익 월 수

    # 상세 데이터
    trades: List[Trade] = field(default_factory=list)
    daily_snapshots: List[DailySnapshot] = field(default_factory=list)
    monthly_returns: Dict[str, float] = field(default_factory=dict)
    yearly_returns: Dict[str, float] = field(default_factory=dict)

    def get_equity_curve(self) -> pd.Series:
        """자산 곡선 반환"""
        if not self.daily_snapshots:
            return pd.Series()
        dates = [s.date for s in self.daily_snapshots]
        equity = [s.equity for s in self.daily_snapshots]
        return pd.Series(equity, index=pd.to_datetime(dates))

    def get_drawdown_curve(self) -> pd.Series:
        """낙폭 곡선 반환"""
        if not self.daily_snapshots:
            return pd.Series()
        dates = [s.date for s in self.daily_snapshots]
        drawdown = [s.drawdown for s in self.daily_snapshots]
        return pd.Series(drawdown, index=pd.to_datetime(dates))

    def get_daily_returns(self) -> pd.Series:
        """일간 수익률 시리즈 반환"""
        if not self.daily_snapshots:
            return pd.Series()
        dates = [s.date for s in self.daily_snapshots]
        returns = [s.daily_return for s in self.daily_snapshots]
        return pd.Series(returns, index=pd.to_datetime(dates))

    def get_trades_df(self) -> pd.DataFrame:
        """거래 내역 DataFrame 반환"""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([t.to_dict() for t in self.trades])

    def to_dict(self) -> Dict[str, Any]:
        """결과를 딕셔너리로 변환"""
        result = {
            'backtest_id': self.backtest_id,
            'strategy_name': self.strategy_name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'status': self.status.value,
            'execution_time': self.execution_time,
            'created_at': self.created_at,

            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,

            'total_return': self.total_return,
            'annual_return': self.annual_return,
            'volatility': self.volatility,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,

            'total_trades': self.total_trades,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'avg_holding_days': self.avg_holding_days,

            'total_commission': self.total_commission,
            'total_slippage': self.total_slippage,

            'var_95': self.var_95,
            'var_99': self.var_99,
        }
        return result

    def to_json(self, filepath: str):
        """결과를 JSON 파일로 저장"""
        data = self.to_dict()
        data['trades'] = [t.to_dict() for t in self.trades]
        data['daily_snapshots'] = [asdict(s) for s in self.daily_snapshots]
        data['monthly_returns'] = self.monthly_returns
        data['yearly_returns'] = self.yearly_returns

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def summary(self) -> str:
        """결과 요약 문자열 반환"""
        return f"""
========================================
백테스트 결과 요약: {self.strategy_name}
========================================
기간: {self.start_date} ~ {self.end_date}
상태: {self.status.value}
실행시간: {self.execution_time:.2f}초

[수익률]
  총 수익률: {self.total_return:.2f}%
  연환산 수익률: {self.annual_return:.2f}%
  최종 자본: {self.final_capital:,.0f}원

[리스크]
  최대 낙폭 (MDD): {self.max_drawdown:.2f}%
  연간 변동성: {self.volatility:.2f}%
  VaR (95%): {self.var_95:.2f}%

[위험조정수익률]
  샤프 비율: {self.sharpe_ratio:.2f}
  소르티노 비율: {self.sortino_ratio:.2f}
  칼마 비율: {self.calmar_ratio:.2f}

[거래 통계]
  총 거래: {self.total_trades}회
  승률: {self.win_rate:.1f}%
  손익비: {self.profit_factor:.2f}
  평균 보유기간: {self.avg_holding_days:.1f}일

[비용]
  총 수수료: {self.total_commission:,.0f}원
  총 슬리피지: {self.total_slippage:,.0f}원
========================================
"""


class MetricsCalculator:
    """성과 지표 계산기"""

    TRADING_DAYS_PER_YEAR = 252
    RISK_FREE_RATE = 0.035  # 3.5% (연간)

    @classmethod
    def calculate_all_metrics(
        cls,
        equity_curve: pd.Series,
        trades: List[Trade],
        initial_capital: float,
        benchmark: Optional[pd.Series] = None
    ) -> Dict[str, Any]:
        """모든 성과 지표 계산"""

        metrics = {}

        # 기본 수익률 지표
        returns = equity_curve.pct_change().dropna()
        total_days = len(equity_curve)

        if total_days == 0:
            return metrics

        # 수익률
        metrics['total_return'] = (equity_curve.iloc[-1] / initial_capital - 1) * 100
        years = total_days / cls.TRADING_DAYS_PER_YEAR
        metrics['annual_return'] = ((1 + metrics['total_return']/100) ** (1/years) - 1) * 100 if years > 0 else 0
        metrics['daily_return_avg'] = returns.mean() * 100
        metrics['daily_return_std'] = returns.std() * 100

        # 월별 수익률
        if len(equity_curve) > 20:
            monthly_equity = equity_curve.resample('ME').last()
            monthly_returns = monthly_equity.pct_change().dropna()
            metrics['monthly_return_avg'] = monthly_returns.mean() * 100
            metrics['positive_months'] = (monthly_returns > 0).sum()
            metrics['negative_months'] = (monthly_returns <= 0).sum()

        # 리스크 지표
        metrics['volatility'] = returns.std() * np.sqrt(cls.TRADING_DAYS_PER_YEAR) * 100

        # 낙폭 계산
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax * 100
        metrics['max_drawdown'] = drawdown.min()
        metrics['avg_drawdown'] = drawdown.mean()

        # MDD 지속 기간
        mdd_duration = cls._calculate_mdd_duration(drawdown)
        metrics['max_drawdown_duration'] = mdd_duration

        # 위험조정수익률
        daily_rf = (1 + cls.RISK_FREE_RATE) ** (1/cls.TRADING_DAYS_PER_YEAR) - 1
        excess_returns = returns - daily_rf

        # 샤프 비율
        metrics['sharpe_ratio'] = (
            np.sqrt(cls.TRADING_DAYS_PER_YEAR) * excess_returns.mean() / returns.std()
            if returns.std() != 0 else 0
        )

        # 소르티노 비율
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std()
        metrics['sortino_ratio'] = (
            np.sqrt(cls.TRADING_DAYS_PER_YEAR) * excess_returns.mean() / downside_std
            if downside_std != 0 else 0
        )

        # 칼마 비율
        metrics['calmar_ratio'] = (
            metrics['annual_return'] / abs(metrics['max_drawdown'])
            if metrics['max_drawdown'] != 0 else 0
        )

        # 정보 비율 (벤치마크 대비)
        if benchmark is not None and len(benchmark) == len(returns):
            tracking_error = (returns - benchmark.pct_change().dropna()).std()
            metrics['information_ratio'] = (
                (returns.mean() - benchmark.pct_change().dropna().mean()) / tracking_error
                if tracking_error != 0 else 0
            ) * np.sqrt(cls.TRADING_DAYS_PER_YEAR)
        else:
            metrics['information_ratio'] = 0

        # 거래 통계
        trade_metrics = cls._calculate_trade_metrics(trades)
        metrics.update(trade_metrics)

        # 고급 통계
        if len(returns) > 0:
            metrics['skewness'] = stats.skew(returns)
            metrics['kurtosis'] = stats.kurtosis(returns)
            metrics['var_95'] = np.percentile(returns, 5) * 100
            metrics['var_99'] = np.percentile(returns, 1) * 100

            # CVaR (Conditional VaR)
            var_95_threshold = np.percentile(returns, 5)
            var_99_threshold = np.percentile(returns, 1)
            metrics['cvar_95'] = returns[returns <= var_95_threshold].mean() * 100 if len(returns[returns <= var_95_threshold]) > 0 else 0
            metrics['cvar_99'] = returns[returns <= var_99_threshold].mean() * 100 if len(returns[returns <= var_99_threshold]) > 0 else 0

        return metrics

    @classmethod
    def _calculate_mdd_duration(cls, drawdown: pd.Series) -> int:
        """최대 낙폭 지속 기간 계산"""
        is_underwater = drawdown < 0
        if not is_underwater.any():
            return 0

        # 연속적인 underwater 구간 찾기
        shifted_series = is_underwater.shift(1)
        shifted = pd.Series(False, index=is_underwater.index)
        shifted.loc[shifted_series.notna()] = shifted_series.loc[shifted_series.notna()].astype(bool)
        underwater_starts = is_underwater & ~shifted
        underwater_ends = ~is_underwater & shifted

        starts = drawdown.index[underwater_starts].tolist()
        ends = drawdown.index[underwater_ends].tolist()

        if len(starts) == 0:
            return 0

        # 마지막 구간이 아직 underwater인 경우
        if len(ends) < len(starts):
            ends.append(drawdown.index[-1])

        max_duration = 0
        for start, end in zip(starts, ends):
            duration = (end - start).days if hasattr(end - start, 'days') else 1
            max_duration = max(max_duration, duration)

        return max_duration

    @classmethod
    def _calculate_trade_metrics(cls, trades: List[Trade]) -> Dict[str, Any]:
        """거래 통계 계산"""
        metrics = {}

        closed_trades = [t for t in trades if t.is_closed()]
        if not closed_trades:
            return {
                'total_trades': 0, 'winning_trades': 0, 'losing_trades': 0,
                'win_rate': 0, 'profit_factor': 0, 'payoff_ratio': 0,
                'avg_profit': 0, 'avg_loss': 0, 'largest_win': 0, 'largest_loss': 0,
                'consecutive_wins': 0, 'consecutive_losses': 0, 'avg_holding_days': 0
            }

        winners = [t for t in closed_trades if t.is_winner()]
        losers = [t for t in closed_trades if not t.is_winner()]

        metrics['total_trades'] = len(closed_trades)
        metrics['winning_trades'] = len(winners)
        metrics['losing_trades'] = len(losers)
        metrics['win_rate'] = len(winners) / len(closed_trades) * 100 if closed_trades else 0

        # 손익 통계
        total_profit = sum(t.net_pnl for t in winners) if winners else 0
        total_loss = abs(sum(t.net_pnl for t in losers)) if losers else 0

        metrics['profit_factor'] = total_profit / total_loss if total_loss > 0 else 0
        metrics['avg_profit'] = total_profit / len(winners) if winners else 0
        metrics['avg_loss'] = -total_loss / len(losers) if losers else 0
        metrics['payoff_ratio'] = abs(metrics['avg_profit'] / metrics['avg_loss']) if metrics['avg_loss'] != 0 else 0

        metrics['largest_win'] = max((t.net_pnl for t in winners), default=0)
        metrics['largest_loss'] = min((t.net_pnl for t in losers), default=0)

        # 연속 승패
        consecutive_wins, consecutive_losses = cls._calculate_consecutive(closed_trades)
        metrics['consecutive_wins'] = consecutive_wins
        metrics['consecutive_losses'] = consecutive_losses

        # 평균 보유 기간
        metrics['avg_holding_days'] = np.mean([t.holding_days for t in closed_trades]) if closed_trades else 0

        return metrics

    @classmethod
    def _calculate_consecutive(cls, trades: List[Trade]) -> tuple:
        """연속 승패 계산"""
        if not trades:
            return 0, 0

        max_wins = max_losses = 0
        current_wins = current_losses = 0

        for trade in trades:
            if trade.is_winner():
                current_wins += 1
                current_losses = 0
                max_wins = max(max_wins, current_wins)
            else:
                current_losses += 1
                current_wins = 0
                max_losses = max(max_losses, current_losses)

        return max_wins, max_losses
