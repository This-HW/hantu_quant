"""
전략별 성과 비교 리포트 자동 생성 시스템

다양한 투자 전략의 성과를 비교하고 자동으로 리포트를 생성
"""

import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
import sqlite3
import json
import threading
import schedule
from pathlib import Path

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class StrategyPerformance:
    """전략 성과 데이터"""

    strategy_name: str
    period_start: str
    period_end: str

    # 기본 성과 지표
    total_return: float  # 총 수익률 (%)
    annualized_return: float  # 연간 수익률 (%)
    volatility: float  # 변동성 (%)
    sharpe_ratio: float  # 샤프 비율
    max_drawdown: float  # 최대 낙폭 (%)

    # 승률 관련
    win_rate: float  # 승률 (%)
    avg_win: float  # 평균 수익 (%)
    avg_loss: float  # 평균 손실 (%)
    profit_factor: float  # 손익비

    # 거래 관련
    total_trades: int  # 총 거래 횟수
    profitable_trades: int  # 수익 거래 횟수
    losing_trades: int  # 손실 거래 횟수

    # 리스크 조정 수익률
    calmar_ratio: float  # 칼마 비율
    sortino_ratio: float  # 소르티노 비율

    # 추가 지표
    market_correlation: float  # 시장 상관계수
    alpha: float  # 알파
    beta: float  # 베타
    information_ratio: float  # 정보 비율

    # 월별/분기별 성과
    monthly_returns: List[float] = field(default_factory=list)
    quarterly_returns: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class StrategyComparison:
    """전략 간 비교 분석"""

    comparison_date: str
    period_days: int
    strategies: List[str]

    # 상대 성과 분석
    best_performer: str
    worst_performer: str
    performance_spread: float  # 최고-최저 성과 차이

    # 리스크 조정 순위
    risk_adjusted_ranking: List[Tuple[str, float]]  # (전략명, 샤프비율)

    # 상관관계 분석
    correlation_matrix: Dict[str, Dict[str, float]]

    # 통계적 유의성
    statistical_significance: Dict[str, bool]  # 성과 차이가 통계적으로 유의한지

    # 시장 환경별 성과
    bull_market_performance: Dict[str, float]
    bear_market_performance: Dict[str, float]
    sideways_market_performance: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return asdict(self)


@dataclass
class MarketRegime:
    """시장 환경 분류"""

    date: str
    regime_type: str  # 'bull', 'bear', 'sideways'
    market_return: float
    volatility: float
    confidence: float  # 분류 신뢰도 (0-1)


class StrategyReporter:
    """전략별 성과 리포트 생성기"""

    def __init__(
        self, db_path: str = "data/strategy_performance.db", use_unified_db: bool = True
    ):
        """초기화

        Args:
            db_path: 성과 데이터베이스 경로 (SQLite 폴백용)
            use_unified_db: 통합 DB 사용 여부 (기본값: True)
        """
        self._logger = logger
        self._db_path = db_path
        self._running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._unified_db_available = False

        # 통합 DB 초기화 시도
        if use_unified_db:
            try:
                from core.database.unified_db import ensure_tables_exist

                ensure_tables_exist()
                self._unified_db_available = True
                self._logger.info("StrategyReporter: 통합 DB 사용")
            except Exception as e:
                self._logger.warning(f"통합 DB 초기화 실패, SQLite 폴백 사용: {e}")
                self._unified_db_available = False

        # 전략 목록
        self._strategies = [
            "momentum_strategy",
            "value_strategy",
            "growth_strategy",
            "dividend_strategy",
            "technical_strategy",
            "fundamental_strategy",
        ]

        # 벤치마크 (KOSPI, KOSDAQ)
        self._benchmarks = ["KOSPI", "KOSDAQ"]

        # 시장 환경 분류를 위한 임계값
        self._regime_thresholds = {
            "bull_threshold": 0.05,  # 월간 5% 이상 상승
            "bear_threshold": -0.05,  # 월간 5% 이상 하락
            "volatility_threshold": 0.2,  # 변동성 20% 이상
        }

        # SQLite 데이터베이스 초기화 (폴백용)
        if not self._unified_db_available:
            self._init_database()

        # 스케줄러 설정
        self._setup_scheduler()

        self._logger.info("StrategyReporter 초기화 완료")

    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self._db_path) as conn:
                # 전략 성과 테이블
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS strategy_performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        strategy_name TEXT NOT NULL,
                        date TEXT NOT NULL,
                        period_start TEXT NOT NULL,
                        period_end TEXT NOT NULL,
                        total_return REAL,
                        annualized_return REAL,
                        volatility REAL,
                        sharpe_ratio REAL,
                        max_drawdown REAL,
                        win_rate REAL,
                        avg_win REAL,
                        avg_loss REAL,
                        profit_factor REAL,
                        total_trades INTEGER,
                        profitable_trades INTEGER,
                        losing_trades INTEGER,
                        calmar_ratio REAL,
                        sortino_ratio REAL,
                        market_correlation REAL,
                        alpha REAL,
                        beta REAL,
                        information_ratio REAL,
                        monthly_returns TEXT,  -- JSON
                        quarterly_returns TEXT,  -- JSON
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(strategy_name, date, period_start, period_end)
                    )
                """
                )

                # 전략 비교 테이블
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS strategy_comparisons (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        comparison_date TEXT NOT NULL,
                        period_days INTEGER,
                        strategies TEXT,  -- JSON
                        best_performer TEXT,
                        worst_performer TEXT,
                        performance_spread REAL,
                        risk_adjusted_ranking TEXT,  -- JSON
                        correlation_matrix TEXT,  -- JSON
                        statistical_significance TEXT,  -- JSON
                        bull_market_performance TEXT,  -- JSON
                        bear_market_performance TEXT,  -- JSON
                        sideways_market_performance TEXT,  -- JSON
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 시장 환경 테이블
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS market_regimes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL UNIQUE,
                        regime_type TEXT NOT NULL,
                        market_return REAL,
                        volatility REAL,
                        confidence REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # 일별 전략 수익률 테이블
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS daily_strategy_returns (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        strategy_name TEXT NOT NULL,
                        date TEXT NOT NULL,
                        daily_return REAL,
                        cumulative_return REAL,
                        portfolio_value REAL,
                        benchmark_return REAL,
                        active_return REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(strategy_name, date)
                    )
                """
                )

                conn.commit()
                self._logger.info("전략 성과 데이터베이스 초기화 완료")

        except Exception as e:
            self._logger.error(f"데이터베이스 초기화 중 오류: {e}", exc_info=True)

    def _setup_scheduler(self):
        """스케줄러 설정"""
        # 매일 오후 8시에 일일 리포트 생성
        schedule.every().day.at("20:00").do(self._generate_daily_report)

        # 매주 월요일 오전 9시에 주간 리포트 생성
        schedule.every().monday.at("09:00").do(self._generate_weekly_report)

        # 매월 1일 오전 10시에 월간 리포트 생성
        schedule.every().month.do(self._generate_monthly_report)

    def record_daily_strategy_return(
        self,
        strategy_name: str,
        date: str,
        daily_return: float,
        cumulative_return: float,
        portfolio_value: float,
        benchmark_return: float,
    ):
        """일별 전략 수익률 기록

        Args:
            strategy_name: 전략명
            date: 날짜 (YYYY-MM-DD)
            daily_return: 일일 수익률 (%)
            cumulative_return: 누적 수익률 (%)
            portfolio_value: 포트폴리오 가치
            benchmark_return: 벤치마크 수익률 (%)
        """
        if self._unified_db_available:
            self._record_daily_strategy_return_unified(
                strategy_name,
                date,
                daily_return,
                cumulative_return,
                portfolio_value,
                benchmark_return,
            )
        else:
            self._record_daily_strategy_return_sqlite(
                strategy_name,
                date,
                daily_return,
                cumulative_return,
                portfolio_value,
                benchmark_return,
            )

    def _record_daily_strategy_return_unified(
        self,
        strategy_name: str,
        date: str,
        daily_return: float,
        cumulative_return: float,
        portfolio_value: float,
        benchmark_return: float,
    ):
        """통합 DB에 일별 전략 수익률 기록"""
        try:
            from core.database.unified_db import get_session
            from core.database.models import DailyStrategyReturn
            from datetime import datetime

            active_return = daily_return - benchmark_return

            with get_session() as session:
                ret = DailyStrategyReturn(
                    strategy_name=strategy_name,
                    date=datetime.strptime(date, "%Y-%m-%d").date(),
                    daily_return=daily_return,
                    cumulative_return=cumulative_return,
                    portfolio_value=portfolio_value,
                    benchmark_return=benchmark_return,
                    active_return=active_return,
                )
                session.merge(ret)

            self._logger.debug(
                f"일별 전략 수익률 기록 (통합 DB): {strategy_name} - {date}"
            )

        except Exception as e:
            self._logger.error(
                f"일별 전략 수익률 기록 중 오류 (통합 DB): {e}", exc_info=True
            )

    def _record_daily_strategy_return_sqlite(
        self,
        strategy_name: str,
        date: str,
        daily_return: float,
        cumulative_return: float,
        portfolio_value: float,
        benchmark_return: float,
    ):
        """SQLite에 일별 전략 수익률 기록"""
        try:
            active_return = daily_return - benchmark_return

            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO daily_strategy_returns
                    (strategy_name, date, daily_return, cumulative_return,
                     portfolio_value, benchmark_return, active_return)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        strategy_name,
                        date,
                        daily_return,
                        cumulative_return,
                        portfolio_value,
                        benchmark_return,
                        active_return,
                    ),
                )

                conn.commit()
                self._logger.debug(f"일별 전략 수익률 기록: {strategy_name} - {date}")

        except Exception as e:
            self._logger.error(f"일별 전략 수익률 기록 중 오류: {e}", exc_info=True)

    def _calculate_strategy_performance(
        self, strategy_name: str, start_date: str, end_date: str
    ) -> Optional[StrategyPerformance]:
        """전략 성과 계산

        Args:
            strategy_name: 전략명
            start_date: 시작 날짜
            end_date: 종료 날짜

        Returns:
            StrategyPerformance 객체
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                # 일별 수익률 데이터 조회
                query = """
                    SELECT date, daily_return, cumulative_return, active_return
                    FROM daily_strategy_returns
                    WHERE strategy_name = ? AND date >= ? AND date <= ?
                    ORDER BY date
                """

                df = pd.read_sql_query(
                    query, conn, params=[strategy_name, start_date, end_date]
                )

                if df.empty:
                    return None

                # 기본 통계 계산
                daily_returns = df["daily_return"].values / 100  # 퍼센트를 소수로 변환
                total_return = df["cumulative_return"].iloc[-1]

                # 연간 수익률
                trading_days = len(daily_returns)
                annualized_return = (
                    (1 + total_return / 100) ** (252 / trading_days) - 1
                ) * 100

                # 변동성 (연간)
                volatility = np.std(daily_returns) * np.sqrt(252) * 100

                # 샤프 비율 (무위험 수익률 3% 가정)
                risk_free_rate = 0.03
                excess_returns = daily_returns - risk_free_rate / 252
                sharpe_ratio = (
                    np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
                    if np.std(excess_returns) > 0
                    else 0
                )

                # 최대 낙폭
                cumulative_returns = (1 + daily_returns).cumprod()
                rolling_max = cumulative_returns.expanding().max()
                drawdowns = (cumulative_returns - rolling_max) / rolling_max
                max_drawdown = drawdowns.min() * 100

                # 승률 계산
                winning_days = (daily_returns > 0).sum()
                losing_days = (daily_returns < 0).sum()
                total_trades = winning_days + losing_days
                win_rate = (
                    (winning_days / total_trades * 100) if total_trades > 0 else 0
                )

                # 평균 수익/손실
                avg_win = (
                    daily_returns[daily_returns > 0].mean() * 100
                    if (daily_returns > 0).any()
                    else 0
                )
                avg_loss = (
                    daily_returns[daily_returns < 0].mean() * 100
                    if (daily_returns < 0).any()
                    else 0
                )

                # 손익비
                profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0

                # 칼마 비율
                calmar_ratio = (
                    annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
                )

                # 소르티노 비율
                downside_returns = daily_returns[daily_returns < 0]
                downside_deviation = (
                    np.std(downside_returns) * np.sqrt(252)
                    if len(downside_returns) > 0
                    else 0
                )
                sortino_ratio = (
                    (annualized_return - risk_free_rate * 100) / downside_deviation
                    if downside_deviation > 0
                    else 0
                )

                # 시장 상관계수, 알파, 베타 (벤치마크 대비)
                active_returns = df["active_return"].values / 100
                market_correlation = (
                    np.corrcoef(daily_returns, daily_returns - active_returns)[0, 1]
                    if len(daily_returns) > 1
                    else 0
                )

                if len(active_returns) > 1:
                    benchmark_returns = daily_returns - active_returns
                    beta = (
                        np.cov(daily_returns, benchmark_returns)[0, 1]
                        / np.var(benchmark_returns)
                        if np.var(benchmark_returns) > 0
                        else 0
                    )
                    alpha = (annualized_return - risk_free_rate * 100) - beta * (
                        np.mean(benchmark_returns) * 252 * 100 - risk_free_rate * 100
                    )
                else:
                    beta = 0
                    alpha = 0

                # 정보 비율
                information_ratio = (
                    (np.mean(active_returns) / np.std(active_returns) * np.sqrt(252))
                    if np.std(active_returns) > 0
                    else 0
                )

                # 월별 수익률
                df["date"] = pd.to_datetime(df["date"])
                monthly_data = (
                    df.set_index("date").resample("M")["daily_return"].sum().tolist()
                )

                # 분기별 수익률
                quarterly_data = (
                    df.set_index("date").resample("Q")["daily_return"].sum().tolist()
                )

                return StrategyPerformance(
                    strategy_name=strategy_name,
                    period_start=start_date,
                    period_end=end_date,
                    total_return=total_return,
                    annualized_return=annualized_return,
                    volatility=volatility,
                    sharpe_ratio=sharpe_ratio,
                    max_drawdown=max_drawdown,
                    win_rate=win_rate,
                    avg_win=avg_win,
                    avg_loss=avg_loss,
                    profit_factor=profit_factor,
                    total_trades=total_trades,
                    profitable_trades=winning_days,
                    losing_trades=losing_days,
                    calmar_ratio=calmar_ratio,
                    sortino_ratio=sortino_ratio,
                    market_correlation=market_correlation,
                    alpha=alpha,
                    beta=beta,
                    information_ratio=information_ratio,
                    monthly_returns=monthly_data,
                    quarterly_returns=quarterly_data,
                )

        except Exception as e:
            self._logger.error(f"전략 성과 계산 중 오류: {e}", exc_info=True)
            return None

    def _classify_market_regime(self, date: str) -> MarketRegime:
        """시장 환경 분류

        Args:
            date: 분류할 날짜

        Returns:
            MarketRegime 객체
        """
        # 임시 구현 - 실제로는 시장 지수 데이터를 사용해야 함
        # 여기서는 랜덤하게 분류
        import random

        regimes = ["bull", "bear", "sideways"]
        regime_type = random.choice(regimes)
        market_return = random.uniform(-0.1, 0.1)  # -10% ~ 10%
        volatility = random.uniform(0.1, 0.4)  # 10% ~ 40%
        confidence = random.uniform(0.7, 1.0)  # 70% ~ 100%

        return MarketRegime(
            date=date,
            regime_type=regime_type,
            market_return=market_return,
            volatility=volatility,
            confidence=confidence,
        )

    def _compare_strategies(self, period_days: int) -> StrategyComparison:
        """전략 간 비교 분석

        Args:
            period_days: 비교 기간 (일수)

        Returns:
            StrategyComparison 객체
        """
        try:
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=period_days)).strftime(
                "%Y-%m-%d"
            )

            strategy_performances = {}

            # 각 전략별 성과 계산
            for strategy in self._strategies:
                performance = self._calculate_strategy_performance(
                    strategy, start_date, end_date
                )
                if performance:
                    strategy_performances[strategy] = performance

            if not strategy_performances:
                return None

            # 최고/최악 성과자 찾기
            returns = {
                name: perf.total_return for name, perf in strategy_performances.items()
            }
            best_performer = max(returns, key=returns.get)
            worst_performer = min(returns, key=returns.get)
            performance_spread = returns[best_performer] - returns[worst_performer]

            # 리스크 조정 순위 (샤프 비율 기준)
            sharpe_ratios = {
                name: perf.sharpe_ratio for name, perf in strategy_performances.items()
            }
            risk_adjusted_ranking = sorted(
                sharpe_ratios.items(), key=lambda x: x[1], reverse=True
            )

            # 상관관계 행렬 계산
            correlation_matrix = {}
            strategy_names = list(strategy_performances.keys())

            for i, strategy1 in enumerate(strategy_names):
                correlation_matrix[strategy1] = {}
                for j, strategy2 in enumerate(strategy_names):
                    if i == j:
                        correlation_matrix[strategy1][strategy2] = 1.0
                    else:
                        # 실제 구현에서는 일별 수익률 데이터로 상관계수 계산
                        # 여기서는 임시값 사용
                        import random

                        correlation_matrix[strategy1][strategy2] = random.uniform(-1, 1)

            # 통계적 유의성 (임시값)
            statistical_significance = {
                strategy: random.choice([True, False]) for strategy in strategy_names
            }

            # 시장 환경별 성과 (임시값)
            bull_market_performance = {
                strategy: perf.total_return * random.uniform(1.1, 1.5)
                for strategy, perf in strategy_performances.items()
            }

            bear_market_performance = {
                strategy: perf.total_return * random.uniform(0.5, 0.9)
                for strategy, perf in strategy_performances.items()
            }

            sideways_market_performance = {
                strategy: perf.total_return * random.uniform(0.8, 1.2)
                for strategy, perf in strategy_performances.items()
            }

            return StrategyComparison(
                comparison_date=end_date,
                period_days=period_days,
                strategies=strategy_names,
                best_performer=best_performer,
                worst_performer=worst_performer,
                performance_spread=performance_spread,
                risk_adjusted_ranking=risk_adjusted_ranking,
                correlation_matrix=correlation_matrix,
                statistical_significance=statistical_significance,
                bull_market_performance=bull_market_performance,
                bear_market_performance=bear_market_performance,
                sideways_market_performance=sideways_market_performance,
            )

        except Exception as e:
            self._logger.error(f"전략 비교 분석 중 오류: {e}", exc_info=True)
            return None

    def _save_strategy_performance(self, performance: StrategyPerformance):
        """전략 성과 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO strategy_performance
                    (strategy_name, date, period_start, period_end, total_return,
                     annualized_return, volatility, sharpe_ratio, max_drawdown,
                     win_rate, avg_win, avg_loss, profit_factor, total_trades,
                     profitable_trades, losing_trades, calmar_ratio, sortino_ratio,
                     market_correlation, alpha, beta, information_ratio,
                     monthly_returns, quarterly_returns)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        performance.strategy_name,
                        datetime.now().strftime("%Y-%m-%d"),
                        performance.period_start,
                        performance.period_end,
                        performance.total_return,
                        performance.annualized_return,
                        performance.volatility,
                        performance.sharpe_ratio,
                        performance.max_drawdown,
                        performance.win_rate,
                        performance.avg_win,
                        performance.avg_loss,
                        performance.profit_factor,
                        performance.total_trades,
                        performance.profitable_trades,
                        performance.losing_trades,
                        performance.calmar_ratio,
                        performance.sortino_ratio,
                        performance.market_correlation,
                        performance.alpha,
                        performance.beta,
                        performance.information_ratio,
                        json.dumps(performance.monthly_returns),
                        json.dumps(performance.quarterly_returns),
                    ),
                )

                conn.commit()
                self._logger.debug(f"전략 성과 저장: {performance.strategy_name}")

        except Exception as e:
            self._logger.error(f"전략 성과 저장 중 오류: {e}", exc_info=True)

    def _save_strategy_comparison(self, comparison: StrategyComparison):
        """전략 비교 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO strategy_comparisons
                    (comparison_date, period_days, strategies, best_performer,
                     worst_performer, performance_spread, risk_adjusted_ranking,
                     correlation_matrix, statistical_significance,
                     bull_market_performance, bear_market_performance,
                     sideways_market_performance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        comparison.comparison_date,
                        comparison.period_days,
                        json.dumps(comparison.strategies),
                        comparison.best_performer,
                        comparison.worst_performer,
                        comparison.performance_spread,
                        json.dumps(comparison.risk_adjusted_ranking),
                        json.dumps(comparison.correlation_matrix),
                        json.dumps(comparison.statistical_significance),
                        json.dumps(comparison.bull_market_performance),
                        json.dumps(comparison.bear_market_performance),
                        json.dumps(comparison.sideways_market_performance),
                    ),
                )

                conn.commit()
                self._logger.info(f"전략 비교 저장: {comparison.comparison_date}")

        except Exception as e:
            self._logger.error(f"전략 비교 저장 중 오류: {e}", exc_info=True)

    def _generate_daily_report(self):
        """일일 리포트 생성"""
        try:
            # 1일 성과 비교
            comparison = self._compare_strategies(1)
            if comparison:
                self._save_strategy_comparison(comparison)

            self._logger.info("일일 전략 리포트 생성 완료")

        except Exception as e:
            self._logger.error(f"일일 리포트 생성 중 오류: {e}", exc_info=True)

    def _generate_weekly_report(self):
        """주간 리포트 생성"""
        try:
            # 7일 성과 비교
            comparison = self._compare_strategies(7)
            if comparison:
                self._save_strategy_comparison(comparison)

            self._logger.info("주간 전략 리포트 생성 완료")

        except Exception as e:
            self._logger.error(f"주간 리포트 생성 중 오류: {e}", exc_info=True)

    def _generate_monthly_report(self):
        """월간 리포트 생성"""
        try:
            # 30일 성과 비교
            comparison = self._compare_strategies(30)
            if comparison:
                self._save_strategy_comparison(comparison)

            # 각 전략별 월간 성과 계산 및 저장
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

            for strategy in self._strategies:
                performance = self._calculate_strategy_performance(
                    strategy, start_date, end_date
                )
                if performance:
                    self._save_strategy_performance(performance)

            self._logger.info("월간 전략 리포트 생성 완료")

        except Exception as e:
            self._logger.error(f"월간 리포트 생성 중 오류: {e}", exc_info=True)

    def get_strategy_performance_history(
        self, strategy_name: str, days: int = 30
    ) -> List[StrategyPerformance]:
        """전략 성과 이력 조회"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                query = """
                    SELECT * FROM strategy_performance
                    WHERE strategy_name = ? AND date >= date('now', '-{} days')
                    ORDER BY date DESC
                """.format(
                    days
                )

                cursor = conn.execute(query, [strategy_name])
                performances = []

                for row in cursor.fetchall():
                    performance = StrategyPerformance(
                        strategy_name=row[1],
                        period_start=row[3],
                        period_end=row[4],
                        total_return=row[5],
                        annualized_return=row[6],
                        volatility=row[7],
                        sharpe_ratio=row[8],
                        max_drawdown=row[9],
                        win_rate=row[10],
                        avg_win=row[11],
                        avg_loss=row[12],
                        profit_factor=row[13],
                        total_trades=row[14],
                        profitable_trades=row[15],
                        losing_trades=row[16],
                        calmar_ratio=row[17],
                        sortino_ratio=row[18],
                        market_correlation=row[19],
                        alpha=row[20],
                        beta=row[21],
                        information_ratio=row[22],
                        monthly_returns=json.loads(row[23]) if row[23] else [],
                        quarterly_returns=json.loads(row[24]) if row[24] else [],
                    )
                    performances.append(performance)

                return performances

        except Exception as e:
            self._logger.error(f"전략 성과 이력 조회 중 오류: {e}", exc_info=True)
            return []

    def export_comprehensive_report(self, file_path: str = "strategy_report.json"):
        """종합 전략 리포트 내보내기"""
        try:
            # 최근 30일 비교 분석
            comparison = self._compare_strategies(30)

            # 각 전략별 성과
            strategy_performances = {}
            for strategy in self._strategies:
                performances = self.get_strategy_performance_history(strategy, 30)
                if performances:
                    strategy_performances[strategy] = [
                        p.to_dict() for p in performances
                    ]

            report = {
                "generated_at": datetime.now().isoformat(),
                "comparison_analysis": comparison.to_dict() if comparison else None,
                "individual_performances": strategy_performances,
                "summary": {
                    "total_strategies": len(self._strategies),
                    "best_performer": comparison.best_performer if comparison else None,
                    "performance_spread": (
                        comparison.performance_spread if comparison else None
                    ),
                },
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)

            self._logger.info(f"종합 전략 리포트를 {file_path}에 저장했습니다.")

        except Exception as e:
            self._logger.error(f"종합 리포트 내보내기 중 오류: {e}", exc_info=True)

    def start_auto_reporting(self):
        """자동 리포트 생성 시작"""
        if self._running:
            self._logger.warning("자동 리포트 생성이 이미 실행 중입니다.")
            return

        self._running = True

        def scheduler_loop():
            while self._running:
                schedule.run_pending()
                time.sleep(60)

        self._scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        self._scheduler_thread.start()

        self._logger.info("전략 리포트 자동 생성 시작")

    def stop_auto_reporting(self):
        """자동 리포트 생성 중지"""
        if not self._running:
            return

        self._running = False
        schedule.clear()

        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)

        self._logger.info("전략 리포트 자동 생성 중지")


# 글로벌 인스턴스
_strategy_reporter_instance: Optional[StrategyReporter] = None


def get_strategy_reporter() -> StrategyReporter:
    """전략 리포터 인스턴스 반환 (싱글톤)"""
    global _strategy_reporter_instance
    if _strategy_reporter_instance is None:
        _strategy_reporter_instance = StrategyReporter()
    return _strategy_reporter_instance
