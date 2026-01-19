"""
실시간 피드백 시스템
거래 결과를 즉시 반영하여 파라미터 동적 조정

핵심 원리:
1. 거래 종료 즉시 피드백
2. Rolling 윈도우 기반 성과 추적
3. 파라미터 자동 조정
4. 다음 선정에 즉시 반영
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import deque
import threading

from core.utils.log_utils import get_logger
from core.selection.quant_config import (
    get_quant_config, QuantConfig
)

logger = get_logger(__name__)


@dataclass
class TradeResult:
    """거래 결과"""
    stock_code: str
    stock_name: str
    entry_price: float
    exit_price: float
    entry_time: str
    exit_time: str
    pnl: float                      # 손익 금액
    pnl_pct: float                  # 손익률 (%)
    is_winner: bool                 # 수익 거래 여부
    exit_reason: str                # 청산 이유 (target, stop_loss, manual, etc.)

    # 선정 시 정보 (학습용)
    momentum_score: float = 0.0
    position_weight: float = 0.0
    sector: str = ""


@dataclass
class PerformanceStats:
    """성과 통계"""
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_return: float
    total_return: float
    profit_factor: float            # 총수익 / 총손실
    avg_winner: float               # 평균 수익 거래 수익률
    avg_loser: float                # 평균 손실 거래 손실률
    largest_winner: float
    largest_loser: float
    consecutive_winners: int
    consecutive_losers: int
    sharpe_estimate: float          # 샤프 비율 추정치


@dataclass
class ParameterAdjustment:
    """파라미터 조정 내역"""
    timestamp: str
    parameter_name: str
    old_value: float
    new_value: float
    reason: str
    performance_snapshot: Dict


class RollingPerformanceTracker:
    """
    Rolling 윈도우 기반 성과 추적기

    최근 N거래의 성과를 추적하여 실시간 통계 제공
    """

    def __init__(self, window_size: int = 20):
        """
        초기화

        Args:
            window_size: Rolling 윈도우 크기 (기본 20거래)
        """
        self.window_size = window_size
        self.trades: deque = deque(maxlen=window_size)
        self.logger = logger

        # 연속 승/패 추적
        self._consecutive_wins = 0
        self._consecutive_losses = 0
        self._max_consecutive_wins = 0
        self._max_consecutive_losses = 0

    def add_trade(self, trade: TradeResult):
        """거래 결과 추가"""
        self.trades.append(trade)

        # 연속 승/패 업데이트
        if trade.is_winner:
            self._consecutive_wins += 1
            self._consecutive_losses = 0
            self._max_consecutive_wins = max(self._max_consecutive_wins, self._consecutive_wins)
        else:
            self._consecutive_losses += 1
            self._consecutive_wins = 0
            self._max_consecutive_losses = max(self._max_consecutive_losses, self._consecutive_losses)

    def get_stats(self) -> PerformanceStats:
        """현재 성과 통계 계산"""
        if not self.trades:
            return self._empty_stats()

        trades_list = list(self.trades)
        total = len(trades_list)
        winners = [t for t in trades_list if t.is_winner]
        losers = [t for t in trades_list if not t.is_winner]

        win_rate = len(winners) / total if total > 0 else 0
        returns = [t.pnl_pct for t in trades_list]

        # 수익/손실 평균
        winner_returns = [t.pnl_pct for t in winners]
        loser_returns = [t.pnl_pct for t in losers]

        avg_winner = sum(winner_returns) / len(winner_returns) if winner_returns else 0
        avg_loser = sum(loser_returns) / len(loser_returns) if loser_returns else 0

        # Profit Factor
        total_profit = sum(r for r in returns if r > 0)
        total_loss = abs(sum(r for r in returns if r < 0))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')

        # Sharpe 추정 (일별 수익률 기준)
        import numpy as np
        if len(returns) > 1:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0

        return PerformanceStats(
            total_trades=total,
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate=round(win_rate, 3),
            avg_return=round(sum(returns) / total, 2) if total > 0 else 0,
            total_return=round(sum(returns), 2),
            profit_factor=round(profit_factor, 2),
            avg_winner=round(avg_winner, 2),
            avg_loser=round(avg_loser, 2),
            largest_winner=round(max(returns), 2) if returns else 0,
            largest_loser=round(min(returns), 2) if returns else 0,
            consecutive_winners=self._consecutive_wins,
            consecutive_losers=self._consecutive_losses,
            sharpe_estimate=round(sharpe, 2)
        )

    def _empty_stats(self) -> PerformanceStats:
        """빈 통계"""
        return PerformanceStats(
            total_trades=0, winning_trades=0, losing_trades=0,
            win_rate=0, avg_return=0, total_return=0,
            profit_factor=0, avg_winner=0, avg_loser=0,
            largest_winner=0, largest_loser=0,
            consecutive_winners=0, consecutive_losers=0,
            sharpe_estimate=0
        )


class AdaptiveParameterStore:
    """
    적응형 파라미터 저장소

    파라미터를 저장하고 조정하며 다음 선정에 반영
    """

    def __init__(self, db_path: str = "data/learning/adaptive_params.db"):
        """초기화"""
        self.db_path = db_path
        self.logger = logger
        self.config = get_quant_config()

        # 메모리 캐시
        self._params: Dict[str, float] = {}
        self._adjustment_history: List[ParameterAdjustment] = []

        # 락 (스레드 안전)
        self._lock = threading.Lock()

        # DB 초기화
        self._init_db()
        self._load_params()

    def _init_db(self):
        """데이터베이스 초기화"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS parameters (
                    param_name TEXT PRIMARY KEY,
                    param_value REAL,
                    updated_at TEXT,
                    update_reason TEXT
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS adjustment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    param_name TEXT,
                    old_value REAL,
                    new_value REAL,
                    reason TEXT,
                    performance_snapshot TEXT
                )
            """)

            conn.commit()

    def _load_params(self):
        """파라미터 로드"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT param_name, param_value FROM parameters")
                for row in cursor:
                    self._params[row[0]] = row[1]
        except Exception as e:
            self.logger.warning(f"파라미터 로드 실패: {e}")

    def get(self, param_name: str, default: float = None) -> float:
        """파라미터 조회"""
        with self._lock:
            return self._params.get(param_name, default)

    def set(self, param_name: str, value: float, reason: str = ""):
        """파라미터 설정"""
        with self._lock:
            self._params.get(param_name, 0)
            self._params[param_name] = value

            # DB 저장
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO parameters
                        (param_name, param_value, updated_at, update_reason)
                        VALUES (?, ?, ?, ?)
                    """, (param_name, value, datetime.now().isoformat(), reason))
                    conn.commit()
            except Exception as e:
                self.logger.error(f"파라미터 저장 실패: {e}", exc_info=True)

    def record_adjustment(self, adjustment: ParameterAdjustment):
        """조정 내역 기록"""
        self._adjustment_history.append(adjustment)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO adjustment_history
                    (timestamp, param_name, old_value, new_value, reason, performance_snapshot)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    adjustment.timestamp,
                    adjustment.parameter_name,
                    adjustment.old_value,
                    adjustment.new_value,
                    adjustment.reason,
                    json.dumps(adjustment.performance_snapshot)
                ))
                conn.commit()
        except Exception as e:
            self.logger.error(f"조정 내역 기록 실패: {e}", exc_info=True)

    def tighten_selection(self):
        """선정 기준 강화 (승률 낮을 때)"""
        # 모멘텀 상위 % 축소
        current = self.get('top_percentile', 0.10)
        new_value = max(0.05, current - 0.02)  # 최소 5%
        self.set('top_percentile', new_value, "승률 저조로 기준 강화")

        # 최대 종목 수 축소
        current_max = self.get('max_stocks', 15)
        new_max = max(8, current_max - 2)
        self.set('max_stocks', new_max, "승률 저조로 종목 수 축소")

        self.logger.info(f"선정 기준 강화: top_percentile={new_value}, max_stocks={new_max}")

    def loosen_selection(self):
        """선정 기준 완화 (승률 높을 때)"""
        # 모멘텀 상위 % 확대
        current = self.get('top_percentile', 0.10)
        new_value = min(0.15, current + 0.01)  # 최대 15%
        self.set('top_percentile', new_value, "성과 우수로 기준 완화")

        # 최대 종목 수 확대
        current_max = self.get('max_stocks', 15)
        new_max = min(20, current_max + 1)
        self.set('max_stocks', new_max, "성과 우수로 종목 수 확대")

        self.logger.info(f"선정 기준 완화: top_percentile={new_value}, max_stocks={new_max}")

    def get_all_params(self) -> Dict[str, float]:
        """모든 파라미터 조회"""
        with self._lock:
            return self._params.copy()


class RealtimeFeedbackLoop:
    """
    실시간 피드백 루프

    거래 결과를 즉시 반영하여 파라미터 자동 조정
    다음 선정에 즉시 적용
    """

    def __init__(self, config: Optional[QuantConfig] = None):
        """초기화"""
        self.config = config or get_quant_config()
        self.fb_config = self.config.feedback
        self.logger = logger

        # 성과 추적기
        self.performance_tracker = RollingPerformanceTracker(
            window_size=self.fb_config.rolling_window
        )

        # 파라미터 저장소
        self.param_store = AdaptiveParameterStore()

        # 기존 학습 시스템 연동 (optional)
        self._selection_tracker = None
        self._adaptive_tuner = None

    def on_trade_closed(self, trade: TradeResult):
        """
        거래 종료 시 즉시 호출

        1. 성과 기록
        2. 통계 업데이트
        3. 파라미터 조정 판단
        4. 즉시 저장
        """
        try:
            # 1. 성과 기록
            self.performance_tracker.add_trade(trade)

            # 2. 현재 통계
            stats = self.performance_tracker.get_stats()

            self.logger.info(
                f"거래 완료: {trade.stock_code} "
                f"{'✅' if trade.is_winner else '❌'} "
                f"{trade.pnl_pct:+.2f}% | "
                f"누적 승률: {stats.win_rate:.1%}"
            )

            # 3. 파라미터 조정 판단
            self._check_and_adjust_params(stats)

            # 4. 기존 학습 시스템에도 기록 (호환성)
            self._record_to_legacy_system(trade)

        except Exception as e:
            self.logger.error(f"피드백 처리 실패: {e}", exc_info=True)

    def _check_and_adjust_params(self, stats: PerformanceStats):
        """파라미터 조정 필요 여부 판단 및 조정"""
        # 최소 거래 수 확인
        if stats.total_trades < 10:
            return

        win_rate = stats.win_rate

        # 승률이 너무 낮음 → 기준 강화
        if win_rate < self.fb_config.win_rate_tighten:
            self.param_store.tighten_selection()

            adjustment = ParameterAdjustment(
                timestamp=datetime.now().isoformat(),
                parameter_name="selection_criteria",
                old_value=win_rate,
                new_value=self.fb_config.win_rate_tighten,
                reason="승률 저조로 기준 강화",
                performance_snapshot=asdict(stats)
            )
            self.param_store.record_adjustment(adjustment)

        # 승률이 높음 → 기준 완화
        elif win_rate > self.fb_config.win_rate_loosen:
            self.param_store.loosen_selection()

            adjustment = ParameterAdjustment(
                timestamp=datetime.now().isoformat(),
                parameter_name="selection_criteria",
                old_value=win_rate,
                new_value=self.fb_config.win_rate_loosen,
                reason="성과 우수로 기준 완화",
                performance_snapshot=asdict(stats)
            )
            self.param_store.record_adjustment(adjustment)

        # 연속 손실 체크
        if stats.consecutive_losers >= 5:
            self.logger.warning(f"연속 {stats.consecutive_losers}회 손실 - 긴급 점검 필요")
            self.param_store.set('emergency_mode', 1, "연속 손실")

    def _record_to_legacy_system(self, trade: TradeResult):
        """기존 학습 시스템에 기록 (호환성)"""
        try:
            # SelectionTracker 연동
            if self._selection_tracker is None:
                try:
                    from core.daily_selection.selection_tracker import SelectionTracker
                    self._selection_tracker = SelectionTracker()
                except ImportError:
                    pass

            # AdaptiveFilterTuner 연동
            if self._adaptive_tuner is None:
                try:
                    from core.daily_selection.adaptive_filter_tuner import AdaptiveFilterTuner
                    self._adaptive_tuner = AdaptiveFilterTuner()
                except ImportError:
                    pass

            # 기록
            if self._adaptive_tuner:
                from core.daily_selection.adaptive_filter_tuner import FilterTradeResult

                # holding_days 계산 (entry_time, exit_time에서)
                try:
                    entry_dt = datetime.fromisoformat(trade.entry_time[:19])
                    exit_dt = datetime.fromisoformat(trade.exit_time[:19])
                    holding_days = max(1, (exit_dt - entry_dt).days)
                except (ValueError, TypeError):
                    holding_days = 1

                filter_result = FilterTradeResult(
                    stock_code=trade.stock_code,
                    entry_date=trade.entry_time[:10],
                    exit_date=trade.exit_time[:10],
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    profit_pct=trade.pnl_pct,
                    is_winner=trade.is_winner,
                    holding_days=holding_days,
                    entry_scores={
                        'momentum_score': trade.momentum_score,
                        'technical_score': 50,
                        'volume_score': 50,
                    }
                )
                self._adaptive_tuner.record_trade(filter_result)

        except Exception as e:
            self.logger.debug(f"기존 시스템 기록 실패 (무시): {e}")

    def on_market_close(self):
        """
        장 마감 후 일일 리뷰

        1. 오늘 성과 집계
        2. 팩터별 기여도 분석
        3. 가중치 조정
        4. 시장 레짐 업데이트
        """
        try:
            stats = self.performance_tracker.get_stats()

            self.logger.info(
                f"=== 일일 성과 리뷰 ===\n"
                f"총 거래: {stats.total_trades}건\n"
                f"승률: {stats.win_rate:.1%}\n"
                f"총 수익률: {stats.total_return:+.2f}%\n"
                f"Profit Factor: {stats.profit_factor:.2f}\n"
                f"샤프 추정: {stats.sharpe_estimate:.2f}"
            )

            # 일일 성과 저장
            self._save_daily_stats(stats)

        except Exception as e:
            self.logger.error(f"일일 리뷰 실패: {e}", exc_info=True)

    def _save_daily_stats(self, stats: PerformanceStats):
        """일일 성과 저장"""
        try:
            db_path = "data/learning/daily_performance.db"
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS daily_stats (
                        date TEXT PRIMARY KEY,
                        total_trades INTEGER,
                        win_rate REAL,
                        total_return REAL,
                        profit_factor REAL,
                        sharpe_estimate REAL,
                        stats_json TEXT
                    )
                """)

                conn.execute("""
                    INSERT OR REPLACE INTO daily_stats
                    (date, total_trades, win_rate, total_return, profit_factor, sharpe_estimate, stats_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().strftime("%Y-%m-%d"),
                    stats.total_trades,
                    stats.win_rate,
                    stats.total_return,
                    stats.profit_factor,
                    stats.sharpe_estimate,
                    json.dumps(asdict(stats))
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"일일 성과 저장 실패: {e}", exc_info=True)

    def get_current_stats(self) -> PerformanceStats:
        """현재 성과 통계 조회"""
        return self.performance_tracker.get_stats()

    def get_adjusted_params(self) -> Dict[str, float]:
        """조정된 파라미터 조회 (선정 시 사용)"""
        return self.param_store.get_all_params()


# 싱글톤 인스턴스 (스레드 안전)
_feedback_loop: Optional[RealtimeFeedbackLoop] = None
_feedback_loop_lock = threading.Lock()


def get_feedback_loop() -> RealtimeFeedbackLoop:
    """피드백 루프 싱글톤 인스턴스 (스레드 안전)"""
    global _feedback_loop
    if _feedback_loop is None:
        with _feedback_loop_lock:
            # Double-checked locking
            if _feedback_loop is None:
                _feedback_loop = RealtimeFeedbackLoop()
    return _feedback_loop
