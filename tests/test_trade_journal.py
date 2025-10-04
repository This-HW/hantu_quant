import os
import json
from core.trading.trade_journal import TradeJournal


def test_trade_journal_logs_and_summary(tmp_path):
    base_dir = tmp_path / "trades"
    journal = TradeJournal(base_dir=str(base_dir))

    # Log signals
    journal.log_signal("005930", "삼성전자", "buy", "test_buy_signal")
    journal.log_signal("005930", "삼성전자", "sell", "test_sell_signal")

    # Log orders: buy then sell with profit
    journal.log_order("005930", "삼성전자", "buy", price=70000, quantity=10, reason="unit_test")
    journal.log_order("005930", "삼성전자", "sell", price=77000, quantity=10, reason="unit_test")

    summary = journal.compute_daily_summary()

    assert summary["total_trades"] == 1
    assert summary["realized_pnl"] == 7000 * 10
    assert summary["win_rate"] == 1.0

    # Summary file exists
    out_files = list((tmp_path / "trades").glob("trade_summary_*.json"))
    assert out_files, "summary file should be written"
    with open(out_files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["total_trades"] == 1
        assert data["realized_pnl"] == 70000

