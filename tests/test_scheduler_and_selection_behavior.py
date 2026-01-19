from datetime import datetime

from core.watchlist.watchlist_manager import WatchlistManager
from core.daily_selection.daily_updater import DailyUpdater


def test_daily_selection_count_is_adaptive(tmp_path, monkeypatch):
    # 준비: 임시 watchlist 파일
    watchlist_file = tmp_path / "watchlist.json"
    wm = WatchlistManager(str(watchlist_file))

    # 1200개 활성 종목을 만들어 active_count≈1200으로 시뮬레이션
    for i in range(1200):
        wm.add_stock_legacy(
            p_stock_code=f"000{i:04d}",
            p_stock_name=f"STK{i:04d}",
            p_added_reason="스크리닝 통과",
            p_target_price=1000.0,
            p_stop_loss=900.0,
            p_sector="기타",
            p_screening_score=60.0,
            p_notes=""
        )

    updater = DailyUpdater(p_watchlist_file=str(watchlist_file))

    # 분석기/가격 조회 등을 간소화하기 위해 분석 결과 생성 로직을 minimal 하게 monkeypatch
    def fake_prepare(stock_entries):
        # 최소 요건을 충족하는 더미 데이터
        return [
            {
                "stock_code": s.stock_code,
                "stock_name": s.stock_name,
                "current_price": 1000.0,
                "sector": s.sector,
                "market_cap": 1e12,
                "volatility": 0.2,
                "sector_momentum": 0.0,
            }
            for s in stock_entries[:200]
        ]

    monkeypatch.setattr(updater, "_prepare_stock_data", fake_prepare)

    class DummyAnalyzer:
        def analyze_price_attractiveness(self, data):
            # 가격 매력도와 유동성 조건을 통과하도록 충분히 높은 점수 반환
            from core.interfaces.trading import PriceAttractiveness
            return PriceAttractiveness(
                stock_code=data["stock_code"],
                stock_name=data["stock_name"],
                analysis_date=datetime.now(),
                current_price=1000.0,
                total_score=80.0,
                technical_score=70.0,
                volume_score=70.0,
                pattern_score=60.0,
                technical_signals=[],
                entry_price=1000.0,
                target_price=1100.0,
                stop_loss=950.0,
                expected_return=0.1,
                risk_score=30.0,
                confidence=0.5,
                selection_reason="테스트",
                market_condition="neutral",
                sector_momentum=0.0,
                sector="기타",
            )

    updater._price_analyzer = DummyAnalyzer()

    # 섹터 제한으로 인해 과도하게 잘리지 않도록 조정. 총량 제한은 해제(0)
    def fake_adjust(criteria_market):
        from core.daily_selection.daily_updater import FilteringCriteria
        c = FilteringCriteria()
        c.sector_limit = 100  # 한 섹터 제한 완화
        c.total_limit = 0     # 총량 제한 해제
        updater._filtering_criteria = c

    monkeypatch.setattr(updater, "_adjust_criteria_by_market", fake_adjust)

    ok = updater.run_daily_update(p_force_run=True)
    assert ok

    latest = updater.get_latest_selection()
    assert latest is not None
    selected = latest["metadata"]["total_selected"]

    # 총량 제한 없음이므로 선택 수는 입력 데이터·필터에 의해 결정. 최소 몇십 개 이상 선정됨을 확인
    assert selected >= 50

