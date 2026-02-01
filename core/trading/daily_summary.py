"""
일일 성과 요약 모듈

매매 세션 종료 후 일일 성과를 집계하고 요약 리포트를 생성합니다.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class TradeSummary:
    """일일 거래 요약"""

    date: datetime
    total_trades: int = 0
    buy_count: int = 0
    sell_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    max_profit_trade: Optional[Dict] = None
    max_loss_trade: Optional[Dict] = None


@dataclass
class PositionSummary:
    """포지션 현황 요약"""

    total_positions: int = 0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    avg_holding_days: float = 0.0
    top_winners: List[Dict] = field(default_factory=list)
    top_losers: List[Dict] = field(default_factory=list)


@dataclass
class DailySummaryReport:
    """일일 종합 리포트"""

    date: datetime
    trade_summary: TradeSummary
    position_summary: PositionSummary
    risk_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_telegram_message(self) -> str:
        """텔레그램 메시지 생성 (마크다운 형식, 4096자 제한)"""
        ts = self.trade_summary
        ps = self.position_summary

        # 이모지 선택
        pnl_emoji = "💰" if ts.total_pnl > 0 else "📉" if ts.total_pnl < 0 else "➖"
        win_rate_emoji = "🎯" if ts.win_rate >= 0.6 else "📊" if ts.win_rate >= 0.5 else "⚠️"

        lines = [
            f"{pnl_emoji} *일일 매매 요약* ({self.date.strftime('%Y-%m-%d')})",
            "",
            "📊 *거래 통계*",
            f"• 총 거래: {ts.total_trades}건 (매수 {ts.buy_count} / 매도 {ts.sell_count})",
            f"• {win_rate_emoji} 승률: {ts.win_rate*100:.1f}% (승 {ts.win_count} / 패 {ts.loss_count})",
            "",
            "💵 *손익 현황*",
            f"• 실현손익: {ts.total_pnl:+,.0f}원",
            f"• 수익률: {ts.total_pnl_pct:+.2f}%",
        ]

        # 최대 수익/손실 거래
        if ts.max_profit_trade:
            lines.append("")
            lines.append("🏆 *최대 수익 거래*")
            lines.append(
                f"• {ts.max_profit_trade['stock_name']}: {ts.max_profit_trade['pnl']:+,.0f}원 ({ts.max_profit_trade['pnl_pct']:+.2f}%)"
            )

        if ts.max_loss_trade:
            lines.append("")
            lines.append("🔻 *최대 손실 거래*")
            lines.append(
                f"• {ts.max_loss_trade['stock_name']}: {ts.max_loss_trade['pnl']:+,.0f}원 ({ts.max_loss_trade['pnl_pct']:+.2f}%)"
            )

        # 포지션 현황
        if ps.total_positions > 0:
            lines.append("")
            lines.append("📋 *보유 포지션*")
            lines.append(f"• 보유 종목: {ps.total_positions}개")
            lines.append(f"• 미실현손익: {ps.unrealized_pnl:+,.0f}원 ({ps.unrealized_pnl_pct:+.2f}%)")
            lines.append(f"• 평균 보유일: {ps.avg_holding_days:.1f}일")

            # 상위 수익/손실 종목
            if ps.top_winners:
                lines.append("")
                lines.append("📈 *상위 수익 종목*")
                for winner in ps.top_winners[:3]:
                    lines.append(
                        f"• {winner['stock_name']}: {winner['unrealized_pnl']:+,.0f}원 ({winner['unrealized_return']:+.2f}%)"
                    )

            if ps.top_losers:
                lines.append("")
                lines.append("📉 *상위 손실 종목*")
                for loser in ps.top_losers[:3]:
                    lines.append(
                        f"• {loser['stock_name']}: {loser['unrealized_pnl']:+,.0f}원 ({loser['unrealized_return']:+.2f}%)"
                    )

        # 리스크 지표
        if self.risk_metrics:
            lines.append("")
            lines.append("⚠️ *리스크 지표*")

            if "max_drawdown" in self.risk_metrics:
                dd = self.risk_metrics["max_drawdown"]
                lines.append(f"• 최대 낙폭: {dd:.2%}")

            if "circuit_breaker_triggered" in self.risk_metrics:
                if self.risk_metrics["circuit_breaker_triggered"]:
                    lines.append("• 🚨 서킷 브레이커 발동됨")

            if "var_status" in self.risk_metrics:
                var_status = self.risk_metrics["var_status"]
                lines.append(f"• VaR 현황: {var_status}")

        message = "\n".join(lines)

        # 4096자 제한 (텔레그램 제한)
        if len(message) > 4096:
            message = message[:4093] + "..."

        return message

    def to_dict(self) -> Dict:
        """딕셔너리 변환 (JSON 저장용)"""
        return {
            "date": self.date.isoformat(),
            "trade_summary": asdict(self.trade_summary),
            "position_summary": asdict(self.position_summary),
            "risk_metrics": self.risk_metrics,
        }


class DailySummaryGenerator:
    """일일 성과 요약 생성기"""

    def __init__(self, trading_engine=None):
        """초기화

        Args:
            trading_engine: TradingEngine 인스턴스 (선택)
        """
        self.trading_engine = trading_engine
        self.logger = logger
        self.data_dir = Path("data/daily_summary")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def generate_summary(
        self, date: Optional[datetime] = None
    ) -> Optional[DailySummaryReport]:
        """일일 성과 요약 생성

        Args:
            date: 요약 날짜 (기본값: 오늘)

        Returns:
            DailySummaryReport 또는 None (데이터 없을 시)
        """
        try:
            if date is None:
                date = datetime.now()

            self.logger.info(f"일일 성과 요약 생성 시작: {date.strftime('%Y-%m-%d')}")

            # 1. 거래 내역 조회
            trade_history = self.get_trade_history(date)

            # 2. 거래 요약 계산
            trade_summary = self._calculate_trade_summary(date, trade_history)

            # 3. 포지션 현황 요약
            position_summary = self._calculate_position_summary(date)

            # 4. 리스크 지표 수집
            risk_metrics = self._collect_risk_metrics(date)

            # 5. 리포트 생성
            report = DailySummaryReport(
                date=date,
                trade_summary=trade_summary,
                position_summary=position_summary,
                risk_metrics=risk_metrics,
            )

            self.logger.info(
                f"일일 성과 요약 생성 완료: 거래 {trade_summary.total_trades}건, 손익 {trade_summary.total_pnl:+,.0f}원"
            )

            return report

        except Exception as e:
            self.logger.error(f"일일 성과 요약 생성 실패: {e}", exc_info=True)
            return None

    def get_trade_history(self, date: datetime) -> List[Dict]:
        """거래 내역 조회 (TradeJournal 기반)

        Args:
            date: 조회 날짜

        Returns:
            거래 내역 리스트
        """
        try:
            # TradeJournal에서 거래 내역 로드
            from core.trading.trade_journal import TradeJournal

            journal = TradeJournal()
            summary = journal.compute_daily_summary()

            # summary['details']에서 거래 내역 추출
            trade_history = summary.get("details", [])

            self.logger.debug(f"거래 내역 조회: {len(trade_history)}건")
            return trade_history

        except Exception as e:
            self.logger.error(f"거래 내역 조회 실패: {e}", exc_info=True)
            return []

    def _calculate_trade_summary(
        self, date: datetime, trade_history: List[Dict]
    ) -> TradeSummary:
        """거래 요약 계산

        Args:
            date: 날짜
            trade_history: 거래 내역

        Returns:
            TradeSummary
        """
        try:
            total_trades = len(trade_history)
            buy_count = 0
            sell_count = 0
            win_count = 0
            loss_count = 0
            total_pnl = 0.0
            max_profit_trade = None
            max_loss_trade = None
            max_profit = float("-inf")
            max_loss = float("inf")

            for trade in trade_history:
                pnl = trade.get("pnl", 0)
                total_pnl += pnl

                # 매수/매도 카운트
                if trade.get("buy_price"):
                    buy_count += 1
                if trade.get("sell_price"):
                    sell_count += 1

                # 승/패 카운트
                if pnl > 0:
                    win_count += 1
                elif pnl < 0:
                    loss_count += 1

                # 최대 수익/손실 거래 추적
                if pnl > max_profit:
                    max_profit = pnl
                    buy_price = trade.get("buy_price", 0)
                    sell_price = trade.get("sell_price", 0)
                    pnl_pct = (
                        ((sell_price - buy_price) / buy_price * 100)
                        if buy_price > 0
                        else 0
                    )
                    max_profit_trade = {
                        "stock_code": trade.get("stock_code"),
                        "stock_name": trade.get("stock_name", trade.get("stock_code")),
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "quantity": trade.get("quantity", 0),
                    }

                if pnl < max_loss:
                    max_loss = pnl
                    buy_price = trade.get("buy_price", 0)
                    sell_price = trade.get("sell_price", 0)
                    pnl_pct = (
                        ((sell_price - buy_price) / buy_price * 100)
                        if buy_price > 0
                        else 0
                    )
                    max_loss_trade = {
                        "stock_code": trade.get("stock_code"),
                        "stock_name": trade.get("stock_name", trade.get("stock_code")),
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "buy_price": buy_price,
                        "sell_price": sell_price,
                        "quantity": trade.get("quantity", 0),
                    }

            # 승률 계산
            closed_trades = win_count + loss_count
            win_rate = (win_count / closed_trades) if closed_trades > 0 else 0.0

            # 총 수익률 계산 (초기 자본 대비)
            # TODO: 실제 초기 자본 또는 평균 투자금으로 대체 필요
            total_pnl_pct = 0.0

            return TradeSummary(
                date=date,
                total_trades=total_trades,
                buy_count=buy_count,
                sell_count=sell_count,
                win_count=win_count,
                loss_count=loss_count,
                win_rate=win_rate,
                total_pnl=total_pnl,
                total_pnl_pct=total_pnl_pct,
                max_profit_trade=max_profit_trade,
                max_loss_trade=max_loss_trade,
            )

        except Exception as e:
            self.logger.error(f"거래 요약 계산 실패: {e}", exc_info=True)
            return TradeSummary(date=date)

    def _calculate_position_summary(self, date: datetime) -> PositionSummary:
        """포지션 현황 요약 계산

        Args:
            date: 날짜

        Returns:
            PositionSummary
        """
        try:
            # TradingEngine에서 포지션 정보 가져오기
            if not self.trading_engine:
                # 엔진이 없으면 빈 요약 반환
                return PositionSummary()

            positions = self.trading_engine.positions
            total_positions = len(positions)

            if total_positions == 0:
                return PositionSummary()

            # 미실현 손익 합계
            total_unrealized_pnl = sum(pos.unrealized_pnl for pos in positions.values())

            # 총 투자금 계산
            total_investment = sum(
                pos.avg_price * pos.quantity for pos in positions.values()
            )
            unrealized_pnl_pct = (
                (total_unrealized_pnl / total_investment * 100)
                if total_investment > 0
                else 0.0
            )

            # 평균 보유 기간 계산
            holding_days = []
            for pos in positions.values():
                entry_time = datetime.fromisoformat(pos.entry_time)
                holding_days.append((date - entry_time).days)
            avg_holding_days = sum(holding_days) / len(holding_days) if holding_days else 0.0

            # 상위 수익/손실 종목
            position_list = [
                {
                    "stock_code": pos.stock_code,
                    "stock_name": pos.stock_name,
                    "unrealized_pnl": pos.unrealized_pnl,
                    "unrealized_return": pos.unrealized_return * 100,
                    "quantity": pos.quantity,
                    "avg_price": pos.avg_price,
                    "current_price": pos.current_price,
                }
                for pos in positions.values()
            ]

            # 수익률 기준 정렬
            sorted_by_pnl = sorted(
                position_list, key=lambda x: x["unrealized_pnl"], reverse=True
            )
            top_winners = [p for p in sorted_by_pnl if p["unrealized_pnl"] > 0][:3]
            top_losers = [p for p in sorted_by_pnl if p["unrealized_pnl"] < 0][:3]

            return PositionSummary(
                total_positions=total_positions,
                unrealized_pnl=total_unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
                avg_holding_days=avg_holding_days,
                top_winners=top_winners,
                top_losers=top_losers,
            )

        except Exception as e:
            self.logger.error(f"포지션 요약 계산 실패: {e}", exc_info=True)
            return PositionSummary()

    def _collect_risk_metrics(self, date: datetime) -> Dict[str, Any]:
        """리스크 지표 수집

        Args:
            date: 날짜

        Returns:
            리스크 지표 딕셔너리
        """
        risk_metrics = {}

        try:
            # 1. DrawdownMonitor에서 최대 낙폭 조회
            try:
                from core.risk.drawdown.drawdown_monitor import DrawdownMonitor

                # TODO: DrawdownMonitor 인스턴스를 전달받거나 전역으로 관리 필요
                # 현재는 파일에서 읽기로 우회
                dd_file = Path(f"data/risk/drawdown_{date.strftime('%Y%m%d')}.json")
                if dd_file.exists():
                    with open(dd_file, "r", encoding="utf-8") as f:
                        dd_data = json.load(f)
                    risk_metrics["max_drawdown"] = dd_data.get("max_drawdown", 0.0)
                    risk_metrics["current_drawdown"] = dd_data.get(
                        "current_drawdown", 0.0
                    )
            except Exception as e:
                self.logger.debug(f"드로다운 지표 수집 실패: {e}")

            # 2. 서킷 브레이커 발동 여부
            # TODO: 서킷 브레이커 상태를 어딘가에 저장하고 읽어오기
            risk_metrics["circuit_breaker_triggered"] = False

            # 3. VaR 현황
            # TODO: VaR 계산 결과 조회
            risk_metrics["var_status"] = "정상"

        except Exception as e:
            self.logger.error(f"리스크 지표 수집 실패: {e}", exc_info=True)

        return risk_metrics

    def save_summary(
        self, report: DailySummaryReport, filepath: Optional[str] = None
    ) -> bool:
        """요약 리포트 저장

        Args:
            report: DailySummaryReport
            filepath: 저장 경로 (기본값: data/daily_summary/summary_YYYYMMDD.json)

        Returns:
            성공 여부
        """
        try:
            if filepath is None:
                filepath = self.data_dir / f"summary_{report.date.strftime('%Y%m%d')}.json"
            else:
                filepath = Path(filepath)

            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, ensure_ascii=False, indent=2)

            self.logger.info(f"일일 요약 저장 완료: {filepath}")
            return True

        except Exception as e:
            self.logger.error(f"일일 요약 저장 실패: {e}", exc_info=True)
            return False
