from __future__ import annotations

import os
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.utils.log_utils import get_logger


logger = get_logger(__name__)


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
    """

    def __init__(self, base_dir: str = "data/trades") -> None:
        self._base_dir = base_dir
        os.makedirs(self._base_dir, exist_ok=True)
        self._today = datetime.now().strftime("%Y%m%d")
        self._journal_path = os.path.join(self._base_dir, f"trade_journal_{self._today}.json")
        self._events: List[TradeEvent] = self._load_events()

    def _load_events(self) -> List[TradeEvent]:
        if os.path.exists(self._journal_path):
            try:
                with open(self._journal_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                return [TradeEvent(**e) for e in raw]
            except Exception as e:
                logger.warning(f"매매일지 로드 실패: {e}")
        return []

    def _save(self) -> None:
        try:
            with open(self._journal_path, "w", encoding="utf-8") as f:
                json.dump([asdict(e) for e in self._events], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"매매일지 저장 실패: {e}", exc_info=True)

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
        return summary

    def get_all_trades(self, days: int = 365) -> List[Dict[str, Any]]:
        """전체 거래 내역 조회 (여러 날 통합)

        Args:
            days: 조회할 일 수 (기본 365일)

        Returns:
            거래 내역 리스트 (각 거래는 dict 형태)
        """
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

