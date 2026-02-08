from __future__ import annotations

import os
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.utils.log_utils import get_logger
from sqlalchemy import text


logger = get_logger(__name__)


def _get_selection_tracker():
    """SelectionTracker lazy import (순환 import 방지)"""
    try:
        from core.daily_selection.selection_tracker import get_selection_tracker
        return get_selection_tracker()
    except ImportError:
        logger.warning("selection_tracker를 import할 수 없습니다", exc_info=True)
        return None


def _get_db_session():
    """DB 세션 lazy import (순환 import 방지)"""
    try:
        from core.database.unified_db import get_session
        return get_session
    except ImportError:
        logger.warning("unified_db를 import할 수 없습니다", exc_info=True)
        return None


def _get_trade_history_model():
    """TradeHistory 모델 lazy import"""
    try:
        from core.database.models import TradeHistory, Stock
        return TradeHistory, Stock
    except ImportError:
        logger.warning("TradeHistory 모델을 import할 수 없습니다", exc_info=True)
        return None, None


@dataclass
class TradeEvent:
    timestamp: str
    stock_code: str
    stock_name: Optional[str]
    event_type: str  # signal|order
    side: Optional[str] = None  # buy|sell
    price: Optional[float] = None
    quantity: Optional[int] = None
    reason: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class TradeJournal:
    """일별 매매일지 관리 클래스

    - 시그널 기록 (signal)
    - 체결 기록 (order)
    - 일별 요약 계산 (realized PnL, win rate 등)
    - DB 우선 저장, JSON 백업 병행
    """

    def __init__(self, base_dir: str = "data/trades") -> None:
        self._base_dir = base_dir
        os.makedirs(self._base_dir, exist_ok=True)
        self._today = datetime.now().strftime("%Y%m%d")
        self._journal_path = os.path.join(self._base_dir, f"trade_journal_{self._today}.json")
        self._events: List[TradeEvent] = self._load_events()
        self._db_connected = False
        self._check_db_connection()

    def _check_db_connection(self) -> None:
        """DB 연결 상태 확인"""
        get_session = _get_db_session()
        TradeHistory, _ = _get_trade_history_model()
        if get_session and TradeHistory:
            try:
                with get_session() as session:
                    session.execute(text("SELECT 1"))
                self._db_connected = True
                logger.info("TradeJournal DB 연결 확인 완료")
            except Exception as e:
                logger.warning(f"TradeJournal DB 연결 실패, JSON 폴백 사용: {e}")
                self._db_connected = False

    def _load_events(self) -> List[TradeEvent]:
        """이벤트 로드 (DB 우선, JSON 폴백)"""
        events = []

        # 1. DB에서 로드 시도
        events = self._load_from_db()
        if events:
            return events

        # 2. JSON 파일에서 로드 (폴백)
        if os.path.exists(self._journal_path):
            try:
                with open(self._journal_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                return [TradeEvent(**e) for e in raw]
            except Exception as e:
                logger.warning(f"매매일지 JSON 로드 실패: {e}")
        return []

    def _load_from_db(self) -> List[TradeEvent]:
        """DB에서 당일 이벤트 로드"""
        get_session = _get_db_session()
        TradeHistory, _ = _get_trade_history_model()

        if not get_session or not TradeHistory:
            return []

        try:
            from datetime import datetime
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)

            with get_session() as session:
                records = session.query(TradeHistory).filter(
                    TradeHistory.order_datetime >= today_start,
                    TradeHistory.order_datetime <= today_end
                ).all()

                events = []
                for r in records:
                    event = TradeEvent(
                        timestamp=r.order_datetime.isoformat() if r.order_datetime else "",
                        stock_code=str(r.stock_id),  # stock_id를 임시로 사용
                        stock_name=None,
                        event_type="order" if r.filled_quantity else "signal",
                        side=r.side,
                        price=r.filled_price or r.price,
                        quantity=r.filled_quantity or r.quantity,
                        reason=r.signal_source,
                        meta={"order_id": r.order_id, "status": r.status}
                    )
                    events.append(event)
                return events
        except Exception as e:
            logger.warning(f"DB 이벤트 로드 실패: {e}", exc_info=True)
            return []

    def _save(self) -> None:
        """이벤트 저장 (DB + JSON 병행)"""
        # JSON 파일 저장 (백업용)
        try:
            with open(self._journal_path, "w", encoding="utf-8") as f:
                json.dump([asdict(e) for e in self._events], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"매매일지 JSON 저장 실패: {e}", exc_info=True)

    def _save_event_to_db(self, event: TradeEvent) -> bool:
        """단일 이벤트를 DB에 저장"""
        get_session = _get_db_session()
        TradeHistory, Stock = _get_trade_history_model()

        if not get_session or not TradeHistory:
            return False

        try:
            with get_session() as session:
                # Stock 테이블에서 stock_id 조회 (없으면 생성)
                stock = session.query(Stock).filter(Stock.code == event.stock_code).first()
                if not stock:
                    stock = Stock(
                        code=event.stock_code,
                        name=event.stock_name or event.stock_code,
                        market="KOSPI"  # 기본값
                    )
                    session.add(stock)
                    session.flush()

                # TradeHistory 레코드 생성
                order_id = f"{event.stock_code}_{event.timestamp}_{event.event_type}"

                trade_record = TradeHistory(
                    stock_id=stock.id,
                    order_id=order_id,
                    order_datetime=datetime.fromisoformat(event.timestamp) if event.timestamp else datetime.now(),
                    order_type="market",
                    side=event.side or "buy",
                    quantity=event.quantity or 0,
                    filled_quantity=event.quantity if event.event_type == "order" else 0,
                    price=event.price,
                    filled_price=event.price if event.event_type == "order" else None,
                    amount=(event.price or 0) * (event.quantity or 0),
                    strategy="daily_selection",
                    signal_source=event.reason,
                    status="filled" if event.event_type == "order" else "signal"
                )
                session.add(trade_record)
                session.commit()
                return True
        except Exception as e:
            logger.error(f"DB 이벤트 저장 실패: {e}", exc_info=True)
            return False

    def log_signal(
        self,
        stock_code: str,
        stock_name: Optional[str],
        side: str,
        reason: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            stock_code=stock_code,
            stock_name=stock_name,
            event_type="signal",
            side=side,
            reason=reason,
            meta=meta or {},
        )
        self._events.append(event)
        self._save()

        # DB 저장 (비동기적으로 실패해도 진행)
        if self._db_connected:
            self._save_event_to_db(event)

        logger.info(f"[Journal] 시그널 기록: {stock_code} {side} - {reason}")

    def log_order(
        self,
        stock_code: str,
        stock_name: Optional[str],
        side: str,
        price: float,
        quantity: int,
        reason: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        event = TradeEvent(
            timestamp=datetime.now().isoformat(),
            stock_code=stock_code,
            stock_name=stock_name,
            event_type="order",
            side=side,
            price=price,
            quantity=quantity,
            reason=reason,
            meta=meta or {},
        )
        self._events.append(event)
        self._save()

        # DB 저장 (비동기적으로 실패해도 진행)
        if self._db_connected:
            self._save_event_to_db(event)

        logger.info(f"[Journal] 주문 기록: {stock_code} {side} {quantity}주 @ {price:,.0f}")

    def compute_daily_summary(self) -> Dict[str, Any]:
        """단순 FIFO로 buy→sell 짝지어 실현손익 계산"""
        from collections import defaultdict, deque

        buys: Dict[str, deque] = defaultdict(deque)
        realized_pnl = 0.0
        total_trades = 0
        wins = 0
        trade_details: List[Dict[str, Any]] = []

        for e in self._events:
            if e.event_type != "order" or e.quantity is None or e.price is None or e.side is None:
                continue
            if e.side == "buy":
                buys[e.stock_code].append({"qty": e.quantity, "price": e.price, "ts": e.timestamp, "name": e.stock_name})
            elif e.side == "sell":
                qty_to_match = e.quantity
                while qty_to_match > 0 and buys[e.stock_code]:
                    lot = buys[e.stock_code][0]
                    matched = min(qty_to_match, lot["qty"])
                    pnl = (e.price - lot["price"]) * matched
                    realized_pnl += pnl
                    total_trades += 1
                    wins += 1 if pnl > 0 else 0
                    trade_details.append(
                        {
                            "stock_code": e.stock_code,
                            "stock_name": lot.get("name"),
                            "buy_price": lot["price"],
                            "sell_price": e.price,
                            "quantity": matched,
                            "pnl": pnl,
                            "buy_time": lot["ts"],
                            "sell_time": e.timestamp,
                        }
                    )
                    qty_to_match -= matched
                    lot["qty"] -= matched
                    if lot["qty"] == 0:
                        buys[e.stock_code].popleft()

        win_rate = (wins / total_trades) if total_trades > 0 else 0.0
        summary = {
            "date": self._today,
            "realized_pnl": realized_pnl,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "details": trade_details,
        }

        # 빈 포지션/예수금 정보 합산(향후 잔고 API와 결합 가능)

        # 요약 저장
        out_path = os.path.join(self._base_dir, f"trade_summary_{self._today}.json")
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"매매 요약 저장 실패: {e}", exc_info=True)

        logger.info(
            f"[Journal] 일일 요약: 손익 {realized_pnl:,.0f}, 거래 {total_trades}건, 승률 {win_rate*100:.1f}%"
        )

        # 학습 데이터 생성: 거래 결과를 selection_tracker로 전달
        if trade_details:
            try:
                tracker = _get_selection_tracker()
                if tracker:
                    processed = tracker.process_trade_results(summary)
                    if processed > 0:
                        logger.info(f"[Journal] 학습 데이터 생성: {processed}건 → adaptive_filter_tuner")
            except Exception as e:
                logger.warning(f"학습 데이터 생성 실패: {e}")

        return summary

    def get_all_trades(self, days: int = 365) -> List[Dict[str, Any]]:
        """전체 거래 내역 조회 (DB 우선, JSON 폴백)

        Args:
            days: 조회할 일 수 (기본 365일)

        Returns:
            거래 내역 리스트 (각 거래는 dict 형태)
        """
        # 1. DB에서 조회 시도
        db_trades = self._get_all_trades_from_db(days)
        if db_trades:
            return db_trades

        # 2. JSON 파일에서 조회 (폴백)
        return self._get_all_trades_from_json(days)

    def _get_all_trades_from_db(self, days: int) -> List[Dict[str, Any]]:
        """DB에서 전체 거래 내역 조회"""
        get_session = _get_db_session()
        TradeHistory, Stock = _get_trade_history_model()

        if not get_session or not TradeHistory:
            return []

        try:
            from datetime import timedelta
            start_date = datetime.now() - timedelta(days=days)

            with get_session() as session:
                records = session.query(TradeHistory, Stock).join(
                    Stock, TradeHistory.stock_id == Stock.id, isouter=True
                ).filter(
                    TradeHistory.order_datetime >= start_date,
                    TradeHistory.status == "filled"
                ).order_by(TradeHistory.order_datetime.desc()).all()

                all_trades = []
                for trade, stock in records:
                    trade_dict = {
                        'stock_code': stock.code if stock else str(trade.stock_id),
                        'stock_name': stock.name if stock else None,
                        'buy_price': trade.entry_price or trade.price,
                        'sell_price': trade.filled_price,
                        'quantity': trade.filled_quantity or trade.quantity,
                        'pnl': ((trade.filled_price or 0) - (trade.entry_price or trade.price or 0)) * (trade.filled_quantity or 0) if trade.side == "sell" else 0,
                        'buy_time': trade.order_datetime.isoformat() if trade.side == "buy" and trade.order_datetime else None,
                        'sell_time': trade.order_datetime.isoformat() if trade.side == "sell" and trade.order_datetime else None,
                        'status': trade.status,
                        'timestamp': trade.order_datetime.isoformat() if trade.order_datetime else None,
                        'side': trade.side,
                        'strategy': trade.strategy,
                    }
                    all_trades.append(trade_dict)

                logger.debug(f"DB에서 {len(all_trades)}건 거래 내역 조회")
                return all_trades

        except Exception as e:
            logger.debug(f"DB 거래 내역 조회 실패: {e}")
            return []

    def _get_all_trades_from_json(self, days: int) -> List[Dict[str, Any]]:
        """JSON 파일에서 전체 거래 내역 조회 (폴백)"""
        all_trades = []

        try:
            # data/trades 디렉토리의 모든 trade_summary 파일 읽기
            if not os.path.exists(self._base_dir):
                return []

            summary_files = [f for f in os.listdir(self._base_dir) if f.startswith('trade_summary_') and f.endswith('.json')]

            for summary_file in summary_files:
                try:
                    summary_path = os.path.join(self._base_dir, summary_file)
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        summary = json.load(f)

                    # summary의 details를 각각 거래로 변환
                    for detail in summary.get('details', []):
                        trade = {
                            'stock_code': detail.get('stock_code'),
                            'stock_name': detail.get('stock_name'),
                            'buy_price': detail.get('buy_price'),
                            'sell_price': detail.get('sell_price'),
                            'quantity': detail.get('quantity'),
                            'pnl': detail.get('pnl', 0),
                            'buy_time': detail.get('buy_time'),
                            'sell_time': detail.get('sell_time'),
                            'status': 'closed',  # summary에 있는 거래는 모두 완료된 거래
                            'timestamp': detail.get('sell_time', detail.get('buy_time'))
                        }
                        all_trades.append(trade)

                except Exception as e:
                    logger.warning(f"거래 요약 파일 로드 실패 ({summary_file}): {e}")
                    continue

            # 시간순 정렬
            all_trades.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

        except Exception as e:
            logger.error(f"전체 거래 내역 조회 실패: {e}", exc_info=True)

        return all_trades

