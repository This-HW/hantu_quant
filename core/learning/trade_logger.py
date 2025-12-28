"""
거래 로그 수집 모듈

모든 거래의 상세 정보를 기록하여 학습에 활용합니다.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ExitReason(Enum):
    """청산 사유"""
    SIGNAL = "signal"          # 신호에 의한 청산
    STOP_LOSS = "stop_loss"    # 손절
    TAKE_PROFIT = "take_profit"  # 익절
    TRAILING = "trailing"      # 트레일링 스탑
    TIMEOUT = "timeout"        # 보유 기간 만료
    MANUAL = "manual"          # 수동 청산
    CIRCUIT_BREAKER = "circuit_breaker"  # 서킷 브레이커


class MarketRegime(Enum):
    """시장 레짐"""
    BULL = "bull"
    BEAR = "bear"
    RANGE = "range"
    HIGH_VOL = "high_vol"


@dataclass
class EntryContext:
    """진입 시점 상태"""
    # 기술적 지표
    rsi: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    bb_position: float = 0.5  # 0-1 (하단-상단)
    ma_trend: str = "neutral"  # up, down, neutral
    volume_ratio: float = 1.0

    # 신호 정보
    signal_source: List[str] = field(default_factory=list)
    signal_strength: float = 0.0
    signal_confidence: float = 0.0
    agreement_count: int = 0

    # 시장 상황
    market_regime: str = "range"
    sector_rank: int = 0
    vix_level: float = 20.0

    # MTF 상태
    daily_trend: str = "neutral"
    weekly_trend: str = "neutral"
    monthly_trend: str = "neutral"

    def to_dict(self) -> Dict:
        return {
            'rsi': self.rsi,
            'macd': self.macd,
            'macd_signal': self.macd_signal,
            'bb_position': self.bb_position,
            'ma_trend': self.ma_trend,
            'volume_ratio': self.volume_ratio,
            'signal_source': self.signal_source,
            'signal_strength': self.signal_strength,
            'signal_confidence': self.signal_confidence,
            'agreement_count': self.agreement_count,
            'market_regime': self.market_regime,
            'sector_rank': self.sector_rank,
            'vix_level': self.vix_level,
            'daily_trend': self.daily_trend,
            'weekly_trend': self.weekly_trend,
            'monthly_trend': self.monthly_trend,
        }


@dataclass
class ExitContext:
    """청산 시점 상태"""
    exit_reason: str = "signal"
    indicators_at_exit: Dict[str, float] = field(default_factory=dict)
    market_regime_at_exit: str = "range"
    max_profit_during: float = 0.0  # 보유 기간 중 최대 수익률
    max_loss_during: float = 0.0    # 보유 기간 중 최대 손실률

    def to_dict(self) -> Dict:
        return {
            'exit_reason': self.exit_reason,
            'indicators_at_exit': self.indicators_at_exit,
            'market_regime_at_exit': self.market_regime_at_exit,
            'max_profit_during': self.max_profit_during,
            'max_loss_during': self.max_loss_during,
        }


@dataclass
class TradeLabels:
    """학습용 레이블"""
    is_winner: bool = False
    is_big_winner: bool = False  # 5% 이상 수익
    is_big_loser: bool = False   # 3% 이상 손실
    exit_optimal: str = "neutral"  # optimal, early, late, neutral
    entry_optimal: str = "neutral"

    def to_dict(self) -> Dict:
        return {
            'is_winner': self.is_winner,
            'is_big_winner': self.is_big_winner,
            'is_big_loser': self.is_big_loser,
            'exit_optimal': self.exit_optimal,
            'entry_optimal': self.entry_optimal,
        }


@dataclass
class TradeLog:
    """거래 로그"""
    trade_id: str
    timestamp: datetime

    # 기본 정보
    stock_code: str
    stock_name: str = ""
    direction: str = "buy"  # buy, sell
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0

    # 컨텍스트
    entry_context: EntryContext = field(default_factory=EntryContext)
    exit_context: ExitContext = field(default_factory=ExitContext)
    labels: TradeLabels = field(default_factory=TradeLabels)

    # 추가 메타데이터
    strategy_name: str = ""
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            'trade_id': self.trade_id,
            'timestamp': self.timestamp.isoformat(),
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'exit_price': self.exit_price,
            'quantity': self.quantity,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
            'holding_days': self.holding_days,
            'entry_context': self.entry_context.to_dict(),
            'exit_context': self.exit_context.to_dict(),
            'labels': self.labels.to_dict(),
            'strategy_name': self.strategy_name,
            'notes': self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TradeLog':
        """딕셔너리에서 TradeLog 생성"""
        entry_ctx = EntryContext(**data.get('entry_context', {}))
        exit_ctx = ExitContext(**data.get('exit_context', {}))
        labels = TradeLabels(**data.get('labels', {}))

        return cls(
            trade_id=data['trade_id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            stock_code=data['stock_code'],
            stock_name=data.get('stock_name', ''),
            direction=data.get('direction', 'buy'),
            entry_price=data.get('entry_price', 0.0),
            exit_price=data.get('exit_price', 0.0),
            quantity=data.get('quantity', 0),
            pnl=data.get('pnl', 0.0),
            pnl_pct=data.get('pnl_pct', 0.0),
            holding_days=data.get('holding_days', 0),
            entry_context=entry_ctx,
            exit_context=exit_ctx,
            labels=labels,
            strategy_name=data.get('strategy_name', ''),
            notes=data.get('notes', ''),
        )


@dataclass
class Trade:
    """거래 정보"""
    id: str
    stock_code: str
    direction: str
    entry_price: float
    exit_price: float = 0.0
    quantity: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0
    exit_reason: str = ""
    is_closed: bool = False


@dataclass
class TradeContext:
    """거래 컨텍스트"""
    entry_indicators: Dict[str, float] = field(default_factory=dict)
    exit_indicators: Dict[str, float] = field(default_factory=dict)
    signal_source: List[str] = field(default_factory=list)
    signal_strength: float = 0.0
    signal_confidence: float = 0.0
    agreement_count: int = 0
    market_regime: str = "range"
    exit_market_regime: str = "range"
    sector_rank: int = 0
    vix_level: float = 20.0
    daily_trend: str = "neutral"
    weekly_trend: str = "neutral"
    monthly_trend: str = "neutral"
    max_profit_during: float = 0.0
    max_loss_during: float = 0.0


class TradeLogger:
    """
    거래 로그 수집기

    모든 거래의 상세 정보를 기록하여 학습에 활용합니다.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Args:
            storage_path: 로그 저장 경로 (None이면 메모리에만 저장)
        """
        self.storage_path = storage_path
        self._logs: List[TradeLog] = []
        self._open_trades: Dict[str, Trade] = {}

    def log_trade(
        self,
        trade: Trade,
        context: TradeContext,
        stock_name: str = ""
    ) -> TradeLog:
        """
        거래 상세 로그 생성

        Args:
            trade: 거래 정보
            context: 거래 컨텍스트
            stock_name: 종목명

        Returns:
            TradeLog: 생성된 로그
        """
        # 진입 컨텍스트
        entry_context = EntryContext(
            rsi=context.entry_indicators.get('rsi', 50.0),
            macd=context.entry_indicators.get('macd', 0.0),
            macd_signal=context.entry_indicators.get('macd_signal', 0.0),
            bb_position=context.entry_indicators.get('bb_position', 0.5),
            ma_trend=context.entry_indicators.get('ma_trend', 'neutral'),
            volume_ratio=context.entry_indicators.get('volume_ratio', 1.0),
            signal_source=context.signal_source,
            signal_strength=context.signal_strength,
            signal_confidence=context.signal_confidence,
            agreement_count=context.agreement_count,
            market_regime=context.market_regime,
            sector_rank=context.sector_rank,
            vix_level=context.vix_level,
            daily_trend=context.daily_trend,
            weekly_trend=context.weekly_trend,
            monthly_trend=context.monthly_trend,
        )

        # 청산 컨텍스트
        exit_context = ExitContext(
            exit_reason=trade.exit_reason,
            indicators_at_exit=context.exit_indicators,
            market_regime_at_exit=context.exit_market_regime,
            max_profit_during=context.max_profit_during,
            max_loss_during=context.max_loss_during,
        )

        # 레이블 생성
        labels = TradeLabels(
            is_winner=trade.pnl > 0,
            is_big_winner=trade.pnl_pct > 5.0,
            is_big_loser=trade.pnl_pct < -3.0,
            exit_optimal=self._evaluate_exit_timing(trade, context),
            entry_optimal=self._evaluate_entry_timing(trade, context),
        )

        # 로그 생성
        log = TradeLog(
            trade_id=trade.id,
            timestamp=datetime.now(),
            stock_code=trade.stock_code,
            stock_name=stock_name,
            direction=trade.direction,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            pnl=trade.pnl,
            pnl_pct=trade.pnl_pct,
            holding_days=trade.holding_days,
            entry_context=entry_context,
            exit_context=exit_context,
            labels=labels,
        )

        # 저장
        self._logs.append(log)
        self._save_log(log)

        logger.info(f"Trade logged: {trade.id} - {trade.stock_code} "
                   f"PnL: {trade.pnl_pct:.2%}")

        return log

    def record_entry(
        self,
        trade_id: str,
        stock_code: str,
        direction: str,
        entry_price: float,
        quantity: int,
        context: TradeContext
    ) -> Trade:
        """
        진입 기록

        Args:
            trade_id: 거래 ID
            stock_code: 종목 코드
            direction: 방향
            entry_price: 진입 가격
            quantity: 수량
            context: 컨텍스트

        Returns:
            Trade: 생성된 거래
        """
        trade = Trade(
            id=trade_id,
            stock_code=stock_code,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
        )

        self._open_trades[trade_id] = trade

        logger.debug(f"Entry recorded: {trade_id} - {stock_code} @ {entry_price}")

        return trade

    def record_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str,
        context: TradeContext,
        stock_name: str = ""
    ) -> Optional[TradeLog]:
        """
        청산 기록

        Args:
            trade_id: 거래 ID
            exit_price: 청산 가격
            exit_reason: 청산 사유
            context: 컨텍스트
            stock_name: 종목명

        Returns:
            TradeLog: 생성된 로그 (없으면 None)
        """
        if trade_id not in self._open_trades:
            logger.warning(f"Trade not found: {trade_id}")
            return None

        trade = self._open_trades.pop(trade_id)
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.is_closed = True

        # PnL 계산
        if trade.direction == "buy":
            trade.pnl = (exit_price - trade.entry_price) * trade.quantity
            trade.pnl_pct = (exit_price - trade.entry_price) / trade.entry_price * 100
        else:
            trade.pnl = (trade.entry_price - exit_price) * trade.quantity
            trade.pnl_pct = (trade.entry_price - exit_price) / trade.entry_price * 100

        return self.log_trade(trade, context, stock_name)

    def _evaluate_exit_timing(self, trade: Trade, context: TradeContext) -> str:
        """
        청산 타이밍 평가

        Returns:
            str: optimal, early, late, neutral
        """
        if trade.pnl > 0:  # 수익 거래
            if context.max_profit_during == 0:
                return "neutral"

            peak_to_exit = (context.max_profit_during - trade.pnl_pct) / context.max_profit_during

            if peak_to_exit < 0.1:  # 최고점 대비 10% 이내
                return "optimal"
            elif peak_to_exit > 0.5:  # 최고점 대비 50% 이상 반납
                return "late"
            else:
                return "neutral"
        else:  # 손실 거래
            if trade.exit_reason == "stop_loss":
                return "neutral"
            elif context.max_loss_during < trade.pnl_pct:
                return "optimal"
            else:
                return "late"

    def _evaluate_entry_timing(self, trade: Trade, context: TradeContext) -> str:
        """
        진입 타이밍 평가

        Returns:
            str: optimal, early, late, neutral
        """
        # MTF 정렬 체크
        mtf_aligned = (
            context.daily_trend == context.weekly_trend
        )

        # 신호 일치도 체크
        strong_signal = context.agreement_count >= 2 and context.signal_confidence >= 0.7

        if trade.pnl > 0:
            if mtf_aligned and strong_signal:
                return "optimal"
            else:
                return "neutral"
        else:
            if not mtf_aligned:
                return "early"  # 추세 정렬 전에 진입
            elif context.signal_confidence < 0.5:
                return "early"  # 신호가 약한 상태에서 진입
            else:
                return "neutral"

    def _save_log(self, log: TradeLog) -> None:
        """로그 저장"""
        if not self.storage_path:
            return

        try:
            import os
            os.makedirs(self.storage_path, exist_ok=True)

            file_path = os.path.join(
                self.storage_path,
                f"trades_{datetime.now().strftime('%Y%m')}.jsonl"
            )

            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log.to_dict(), ensure_ascii=False) + '\n')

        except Exception as e:
            logger.error(f"Failed to save trade log: {e}")

    def get_logs(
        self,
        stock_code: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        winners_only: bool = False
    ) -> List[TradeLog]:
        """
        로그 조회

        Args:
            stock_code: 종목 필터
            start_date: 시작일
            end_date: 종료일
            winners_only: 수익 거래만

        Returns:
            List[TradeLog]: 필터링된 로그
        """
        logs = self._logs

        if stock_code:
            logs = [l for l in logs if l.stock_code == stock_code]

        if start_date:
            logs = [l for l in logs if l.timestamp >= start_date]

        if end_date:
            logs = [l for l in logs if l.timestamp <= end_date]

        if winners_only:
            logs = [l for l in logs if l.labels.is_winner]

        return logs

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        if not self._logs:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_pnl_pct': 0.0,
            }

        winners = [l for l in self._logs if l.labels.is_winner]
        losers = [l for l in self._logs if not l.labels.is_winner]

        return {
            'total_trades': len(self._logs),
            'winners': len(winners),
            'losers': len(losers),
            'win_rate': len(winners) / len(self._logs) if self._logs else 0.0,
            'avg_pnl_pct': sum(l.pnl_pct for l in self._logs) / len(self._logs),
            'avg_winner_pnl': sum(l.pnl_pct for l in winners) / len(winners) if winners else 0.0,
            'avg_loser_pnl': sum(l.pnl_pct for l in losers) / len(losers) if losers else 0.0,
            'big_winners': len([l for l in self._logs if l.labels.is_big_winner]),
            'big_losers': len([l for l in self._logs if l.labels.is_big_loser]),
            'open_trades': len(self._open_trades),
        }

    def load_logs(self, file_path: str) -> int:
        """
        파일에서 로그 로드

        Args:
            file_path: 로그 파일 경로

        Returns:
            int: 로드된 로그 수
        """
        loaded = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    log = TradeLog.from_dict(data)
                    self._logs.append(log)
                    loaded += 1

            logger.info(f"Loaded {loaded} trade logs from {file_path}")

        except Exception as e:
            logger.error(f"Failed to load trade logs: {e}")

        return loaded
