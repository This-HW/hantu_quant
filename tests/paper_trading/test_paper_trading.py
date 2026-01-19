"""
페이퍼 트레이딩 테스트

VirtualPortfolio, OrderExecutor, PositionTracker, PaperTrader를 테스트합니다.
"""


from core.paper_trading import (
    VirtualPortfolio,
    PortfolioConfig,
    PortfolioSnapshot,
    OrderExecutor,
    OrderType,
    OrderSide,
    OrderStatus,
    PositionTracker,
    PositionStatus,
    PaperTrader,
    PaperTradingConfig,
)


# =============================================================================
# VirtualPortfolio 테스트
# =============================================================================

class TestVirtualPortfolio:
    """가상 포트폴리오 테스트"""

    def test_init_default(self):
        """기본 초기화"""
        portfolio = VirtualPortfolio()
        assert portfolio.cash == 10_000_000
        assert portfolio.holdings_value == 0
        assert portfolio.total_value == 10_000_000

    def test_init_with_config(self):
        """설정으로 초기화"""
        config = PortfolioConfig(
            initial_capital=50_000_000,
            commission_rate=0.0003,
            slippage_pct=0.002,
        )
        portfolio = VirtualPortfolio(config)
        assert portfolio.cash == 50_000_000
        assert portfolio.config.commission_rate == 0.0003

    def test_buy_success(self):
        """매수 성공"""
        portfolio = VirtualPortfolio()
        result = portfolio.buy(
            stock_code="005930",
            stock_name="삼성전자",
            price=70000,
            quantity=10,
        )

        assert result['success'] is True
        assert result['quantity'] == 10
        assert portfolio.get_holding("005930") is not None
        assert portfolio.cash < 10_000_000

    def test_buy_insufficient_cash(self):
        """잔액 부족 매수"""
        config = PortfolioConfig(initial_capital=100_000)
        portfolio = VirtualPortfolio(config)

        result = portfolio.buy(
            stock_code="005930",
            stock_name="삼성전자",
            price=70000,
            quantity=10,
        )

        assert result['success'] is False
        assert 'insufficient' in result.get('error', '').lower()

    def test_sell_success(self):
        """매도 성공"""
        portfolio = VirtualPortfolio()

        # 먼저 매수
        portfolio.buy(
            stock_code="005930",
            stock_name="삼성전자",
            price=70000,
            quantity=10,
        )

        # 매도
        result = portfolio.sell(
            stock_code="005930",
            price=72000,
            quantity=5,
        )

        assert result['success'] is True
        assert result['realized_pnl'] > 0  # 수익

        holding = portfolio.get_holding("005930")
        assert holding.quantity == 5

    def test_sell_all(self):
        """전량 매도"""
        portfolio = VirtualPortfolio()

        portfolio.buy(
            stock_code="005930",
            stock_name="삼성전자",
            price=70000,
            quantity=10,
        )

        result = portfolio.sell(
            stock_code="005930",
            price=70000,
            quantity=10,
        )

        assert result['success'] is True
        assert portfolio.get_holding("005930") is None

    def test_sell_no_holding(self):
        """보유 없이 매도"""
        portfolio = VirtualPortfolio()

        result = portfolio.sell(
            stock_code="005930",
            price=70000,
            quantity=10,
        )

        assert result['success'] is False

    def test_update_prices(self):
        """가격 업데이트"""
        portfolio = VirtualPortfolio()

        portfolio.buy(
            stock_code="005930",
            stock_name="삼성전자",
            price=70000,
            quantity=10,
        )

        portfolio.update_prices({"005930": 75000})

        holding = portfolio.get_holding("005930")
        assert holding.current_price == 75000
        assert holding.unrealized_pnl > 0

    def test_snapshot(self):
        """스냅샷"""
        portfolio = VirtualPortfolio()

        portfolio.buy(
            stock_code="005930",
            stock_name="삼성전자",
            price=70000,
            quantity=10,
        )

        snapshot = portfolio.take_snapshot()

        assert isinstance(snapshot, PortfolioSnapshot)
        assert snapshot.total_value > 0
        assert snapshot.num_positions == 1

    def test_commission_calculation(self):
        """수수료 계산"""
        config = PortfolioConfig(
            initial_capital=10_000_000,
            commission_rate=0.001,  # 0.1%
            slippage_pct=0,  # 슬리피지 없음
        )
        portfolio = VirtualPortfolio(config)

        result = portfolio.buy(
            stock_code="005930",
            stock_name="삼성전자",
            price=100000,
            quantity=10,
        )

        # 100000 * 10 * 0.001 = 1000원 수수료
        assert result['commission'] == 1000

    def test_slippage_calculation(self):
        """슬리피지 계산"""
        config = PortfolioConfig(
            initial_capital=10_000_000,
            commission_rate=0,
            slippage_pct=0.001,  # 0.1%
        )
        portfolio = VirtualPortfolio(config)

        result = portfolio.buy(
            stock_code="005930",
            stock_name="삼성전자",
            price=100000,
            quantity=1,
        )

        # 슬리피지로 인해 실제 체결가는 100100원
        assert abs(result['price'] - 100100) < 1  # 부동소수점 허용


# =============================================================================
# OrderExecutor 테스트
# =============================================================================

class TestOrderExecutor:
    """주문 실행기 테스트"""

    def test_create_order(self):
        """주문 생성"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )

        assert order.id is not None
        assert order.stock_code == "005930"
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.PENDING

    def test_submit_order(self):
        """주문 제출"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )

        result = executor.submit_order(order.id)

        assert result.success is True
        assert result.status == OrderStatus.SUBMITTED

    def test_execute_market_order_buy(self):
        """시장가 매수 주문 실행"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )

        executor.submit_order(order.id)
        result = executor.execute_market_order(order.id, 70000)

        assert result.success is True
        assert result.status == OrderStatus.FILLED
        assert result.filled_quantity == 10

    def test_execute_market_order_sell(self):
        """시장가 매도 주문 실행"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        # 먼저 매수
        buy_order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        executor.submit_order(buy_order.id)
        executor.execute_market_order(buy_order.id, 70000)

        # 매도
        sell_order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.SELL,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        executor.submit_order(sell_order.id)
        result = executor.execute_market_order(sell_order.id, 72000)

        assert result.success is True
        assert result.pnl > 0

    def test_limit_order_not_triggered(self):
        """지정가 주문 미체결"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            price=65000,  # 65000원에 매수 희망
        )

        executor.submit_order(order.id)

        # 현재가 70000 - 지정가 65000보다 높음
        results = executor.check_pending_orders({"005930": 70000})

        assert len(results) == 0  # 체결 안됨

    def test_limit_order_triggered(self):
        """지정가 주문 체결"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            price=65000,
        )

        executor.submit_order(order.id)

        # 현재가 64000 - 지정가 65000 이하
        results = executor.check_pending_orders({"005930": 64000})

        assert len(results) == 1
        assert results[0].success is True

    def test_stop_order_triggered(self):
        """스탑 주문 체결"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        # 먼저 매수
        buy_order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )
        executor.submit_order(buy_order.id)
        executor.execute_market_order(buy_order.id, 70000)

        # 스탑 손절 주문
        stop_order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.SELL,
            quantity=10,
            order_type=OrderType.STOP,
            stop_price=68000,  # 68000 이하로 떨어지면 매도
        )

        executor.submit_order(stop_order.id)

        # 가격이 67000으로 하락
        results = executor.check_pending_orders({"005930": 67000})

        assert len(results) == 1
        assert results[0].success is True

    def test_cancel_order(self):
        """주문 취소"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            price=65000,
        )

        executor.submit_order(order.id)
        result = executor.cancel_order(order.id)

        assert result.success is True
        assert result.status == OrderStatus.CANCELLED

    def test_cancel_all_pending(self):
        """모든 대기 주문 취소"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        for i in range(3):
            order = executor.create_order(
                stock_code=f"00593{i}",
                stock_name=f"종목{i}",
                side=OrderSide.BUY,
                quantity=10,
                order_type=OrderType.LIMIT,
                price=65000,
            )
            executor.submit_order(order.id)

        count = executor.cancel_all_pending()
        assert count == 3

    def test_order_stats(self):
        """주문 통계"""
        portfolio = VirtualPortfolio()
        executor = OrderExecutor(portfolio)

        order = executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.MARKET,
        )

        executor.submit_order(order.id)
        executor.execute_market_order(order.id, 70000)

        stats = executor.get_stats()
        assert stats['total_orders'] == 1
        assert stats['filled_orders'] == 1


# =============================================================================
# PositionTracker 테스트
# =============================================================================

class TestPositionTracker:
    """포지션 추적기 테스트"""

    def test_open_position(self):
        """포지션 열기"""
        tracker = PositionTracker()

        position = tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
            strategy="momentum",
        )

        assert position.stock_code == "005930"
        assert position.entry_price == 70000
        assert position.current_quantity == 10
        assert position.status == PositionStatus.OPEN

    def test_close_position(self):
        """포지션 청산"""
        tracker = PositionTracker()

        tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
        )

        result = tracker.close_position(
            stock_code="005930",
            exit_price=75000,
            reason="take_profit",
        )

        assert result is not None
        assert result['pnl'] == 50000  # (75000 - 70000) * 10
        assert result['pnl_pct'] > 0

    def test_partial_close(self):
        """부분 청산"""
        tracker = PositionTracker()

        tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
        )

        result = tracker.close_position(
            stock_code="005930",
            exit_price=75000,
            quantity=5,
        )

        position = tracker.get_position("005930")

        assert result['quantity'] == 5
        assert position is not None
        assert position.current_quantity == 5
        assert position.status == PositionStatus.PARTIAL

    def test_add_to_position(self):
        """포지션 추가"""
        tracker = PositionTracker()

        tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
        )

        # 추가 매수
        position = tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=68000,
            quantity=10,
        )

        # 평균 단가: (70000*10 + 68000*10) / 20 = 69000
        assert position.current_quantity == 20
        assert position.entry_price == 69000

    def test_stop_loss_check(self):
        """손절 체크"""
        tracker = PositionTracker()

        tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
            stop_loss=67000,
        )

        triggered = tracker.check_stop_conditions({"005930": 66000})

        assert len(triggered) == 1
        assert triggered[0]['reason'] == 'stop_loss'

    def test_take_profit_check(self):
        """익절 체크"""
        tracker = PositionTracker()

        tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
            take_profit=75000,
        )

        triggered = tracker.check_stop_conditions({"005930": 76000})

        assert len(triggered) == 1
        assert triggered[0]['reason'] == 'take_profit'

    def test_trailing_stop_update(self):
        """트레일링 스탑 업데이트"""
        tracker = PositionTracker()

        tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
            stop_loss=68000,
            trailing_stop=3.0,  # 3%
        )

        # 가격 상승 시 스탑도 상승
        tracker.update_trailing_stops({"005930": 75000})

        position = tracker.get_position("005930")
        # 75000 * (1 - 0.03) = 72750
        assert position.stop_loss > 68000

    def test_position_summary(self):
        """포지션 요약"""
        tracker = PositionTracker()

        tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
        )

        tracker.open_position(
            stock_code="000660",
            stock_name="SK하이닉스",
            entry_price=150000,
            quantity=5,
        )

        tracker.update_prices({"005930": 72000, "000660": 145000})

        summary = tracker.get_summary()

        assert summary.open_positions == 2
        assert summary.total_market_value > 0

    def test_risk_exposure(self):
        """리스크 노출"""
        tracker = PositionTracker()

        tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
            strategy="momentum",
        )

        tracker.update_prices({"005930": 72000})

        exposure = tracker.get_risk_exposure()

        assert exposure['position_count'] == 1
        assert 'by_strategy' in exposure

    def test_position_unrealized_pnl(self):
        """미실현 손익"""
        tracker = PositionTracker()

        tracker.open_position(
            stock_code="005930",
            stock_name="삼성전자",
            entry_price=70000,
            quantity=10,
        )

        tracker.update_prices({"005930": 75000})
        position = tracker.get_position("005930")

        # (75000 - 70000) * 10 = 50000
        assert position.unrealized_pnl == 50000
        assert position.unrealized_pnl_pct > 0


# =============================================================================
# PaperTrader 테스트
# =============================================================================

class TestPaperTrader:
    """페이퍼 트레이더 테스트"""

    def test_init_default(self):
        """기본 초기화"""
        trader = PaperTrader()

        assert trader.portfolio is not None
        assert trader.executor is not None
        assert trader.tracker is not None

    def test_init_with_config(self):
        """설정으로 초기화"""
        config = PaperTradingConfig(
            initial_capital=50_000_000,
            max_position_size=0.1,
        )
        trader = PaperTrader(config)

        assert trader.config.initial_capital == 50_000_000
        assert trader.portfolio.cash == 50_000_000

    def test_start_session(self):
        """세션 시작"""
        trader = PaperTrader()
        session = trader.start_session("test_session")

        assert session.session_id == "test_session"
        assert session.is_active is True

    def test_end_session(self):
        """세션 종료"""
        trader = PaperTrader()
        trader.start_session()
        session = trader.end_session()

        assert session is not None
        assert session.is_active is False

    def test_buy(self):
        """매수"""
        trader = PaperTrader()
        trader.start_session()

        trader._current_prices["005930"] = 70000

        result = trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=70000,
        )

        assert result.success is True
        assert len(trader.get_holdings()) == 1

    def test_sell(self):
        """매도"""
        trader = PaperTrader()
        trader.start_session()

        trader._current_prices["005930"] = 70000
        trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=70000,
        )

        trader._current_prices["005930"] = 72000
        result = trader.sell(stock_code="005930")

        assert result.success is True
        assert len(trader.get_holdings()) == 0

    def test_update_prices(self):
        """가격 업데이트"""
        trader = PaperTrader()
        trader.start_session()

        trader._current_prices["005930"] = 70000
        trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=70000,
        )

        results = trader.update_prices({"005930": 75000})

        status = trader.get_portfolio_status()
        assert status['total_value'] > 10_000_000

    def test_stop_loss_triggered(self):
        """손절 트리거"""
        config = PaperTradingConfig(
            default_stop_loss_pct=3.0,  # 3%
        )
        trader = PaperTrader(config)
        trader.start_session()

        trader._current_prices["005930"] = 70000
        trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=70000,
        )

        # 가격이 3% 이상 하락하면 손절
        results = trader.update_prices({"005930": 67000})

        # 손절 실행됨
        assert len(trader.get_holdings()) == 0

    def test_position_size_limit(self):
        """포지션 크기 제한"""
        config = PaperTradingConfig(
            initial_capital=10_000_000,
            max_position_size=0.1,  # 10%
        )
        trader = PaperTrader(config)
        trader.start_session()

        trader._current_prices["005930"] = 100000

        # 10% 초과 매수 시도 (100000 * 15 = 1,500,000 > 10%)
        result = trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=15,
            price=100000,
        )

        assert result.success is False
        assert 'position size' in result.message.lower()

    def test_daily_loss_limit(self):
        """일일 손실 한도"""
        config = PaperTradingConfig(
            initial_capital=10_000_000,
            daily_loss_limit=0.02,  # 2%
            max_position_size=0.3,  # 30%로 증가
            default_stop_loss_pct=0,  # 자동 손절 비활성화
        )
        trader = PaperTrader(config)
        trader.start_session()

        # 큰 손실 발생
        trader._current_prices["005930"] = 100000
        buy_result = trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=25,  # 25 * 100000 = 2,500,000 (25%)
            price=100000,
        )
        assert buy_result.success is True

        # 손실로 청산 (가격 10% 하락 = 250,000원 손실 = 2.5%)
        trader._current_prices["005930"] = 90000
        sell_result = trader.sell(stock_code="005930")
        assert sell_result.success is True

        # 거래 일시 중지됨 (2.5% > 2%)
        assert trader._trading_paused is True

    def test_pause_resume_trading(self):
        """거래 일시 중지/재개"""
        trader = PaperTrader()
        trader.start_session()

        trader.pause_trading("test pause")
        assert trader._trading_paused is True

        trader.resume_trading()
        assert trader._trading_paused is False

    def test_close_all_positions(self):
        """전체 포지션 청산"""
        trader = PaperTrader()
        trader.start_session()

        trader._current_prices = {
            "005930": 70000,
            "000660": 150000,
        }

        trader.buy(stock_code="005930", stock_name="삼성전자", quantity=10, price=70000)
        trader.buy(stock_code="000660", stock_name="SK하이닉스", quantity=5, price=150000)

        results = trader.close_all_positions()

        assert len(results) == 2
        assert len(trader.get_holdings()) == 0

    def test_portfolio_status(self):
        """포트폴리오 상태"""
        trader = PaperTrader()
        trader.start_session()

        status = trader.get_portfolio_status()

        assert 'cash' in status
        assert 'total_value' in status
        assert 'position_count' in status

    def test_performance_report(self):
        """성과 보고서"""
        trader = PaperTrader()
        trader.start_session()

        trader._current_prices["005930"] = 70000
        trader.buy(stock_code="005930", stock_name="삼성전자", quantity=10, price=70000)

        trader._current_prices["005930"] = 72000
        trader.sell(stock_code="005930")

        trader.end_session()

        report = trader.get_performance_report()

        assert 'portfolio' in report
        assert 'positions' in report
        assert 'sessions' in report
        assert 'trading' in report

    def test_export_state(self):
        """상태 내보내기"""
        trader = PaperTrader()
        trader.start_session()

        state = trader.export_state()

        assert 'timestamp' in state
        assert 'config' in state
        assert 'portfolio' in state
        assert 'positions' in state

    def test_notification_callback(self):
        """알림 콜백"""
        notifications = []

        def callback(event, data):
            notifications.append((event, data))

        trader = PaperTrader(notification_callback=callback)
        trader.start_session()

        trader._current_prices["005930"] = 70000
        trader.buy(stock_code="005930", stock_name="삼성전자", quantity=10, price=70000)

        # 세션 시작, 매수 실행 알림
        assert len(notifications) >= 2
        events = [n[0] for n in notifications]
        assert 'session_start' in events
        assert 'buy_executed' in events

    def test_session_history(self):
        """세션 이력"""
        trader = PaperTrader()

        trader.start_session("session1")
        trader.end_session()

        trader.start_session("session2")
        trader.end_session()

        history = trader.get_session_history()

        assert len(history) == 2

    def test_cancel_order(self):
        """주문 취소"""
        trader = PaperTrader()
        trader.start_session()

        # 지정가 주문 생성
        order = trader.executor.create_order(
            stock_code="005930",
            stock_name="삼성전자",
            side=OrderSide.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            price=65000,
        )
        trader.executor.submit_order(order.id)

        result = trader.cancel_order(order.id)

        assert result.success is True

    def test_insufficient_cash(self):
        """잔액 부족"""
        config = PaperTradingConfig(initial_capital=100_000)
        trader = PaperTrader(config)
        trader.start_session()

        trader._current_prices["005930"] = 70000

        result = trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=70000,
        )

        assert result.success is False
        assert 'cash' in result.message.lower()


# =============================================================================
# 통합 테스트
# =============================================================================

class TestIntegration:
    """통합 테스트"""

    def test_full_trading_cycle(self):
        """전체 거래 사이클"""
        # 스탑/익절 비활성화
        config = PaperTradingConfig(
            default_stop_loss_pct=0,
            default_take_profit_pct=0,
        )
        trader = PaperTrader(config)
        session = trader.start_session()

        # 초기 가격
        prices = {"005930": 70000, "000660": 150000}
        trader._current_prices = prices

        # 매수
        trader.buy(stock_code="005930", stock_name="삼성전자", quantity=10, price=70000)
        trader.buy(stock_code="000660", stock_name="SK하이닉스", quantity=5, price=150000)

        assert len(trader.get_holdings()) == 2
        assert len(trader.get_positions()) == 2

        # 가격 변동 (스탑 트리거 안되는 범위)
        trader.update_prices({"005930": 72000, "000660": 148000})

        status = trader.get_portfolio_status()
        assert status['unrealized_pnl'] != 0

        # 부분 청산
        trader.sell(stock_code="005930", quantity=5)

        # 전량 청산
        trader.sell(stock_code="005930")
        trader.sell(stock_code="000660")

        assert len(trader.get_holdings()) == 0

        # 세션 종료
        session = trader.end_session()

        assert session.trades_executed == 5  # 2 buy + 3 sell
        assert session.realized_pnl != 0

    def test_risk_management_flow(self):
        """리스크 관리 흐름"""
        config = PaperTradingConfig(
            initial_capital=10_000_000,
            default_stop_loss_pct=5.0,
            default_take_profit_pct=10.0,
        )
        trader = PaperTrader(config)
        trader.start_session()

        trader._current_prices["005930"] = 70000
        trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=70000,
        )

        # 손절가 체크
        position = trader.tracker.get_position("005930")
        assert position.stop_loss is not None
        assert position.take_profit is not None

        # 익절 트리거
        trader.update_prices({"005930": 78000})  # +11.4%

        # 익절로 청산됨
        assert len(trader.get_holdings()) == 0

    def test_multiple_strategies(self):
        """다중 전략"""
        trader = PaperTrader()
        trader.start_session()

        prices = {"005930": 70000, "000660": 150000}
        trader._current_prices = prices

        # 전략별 매수
        trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=70000,
            strategy="momentum",
        )

        trader.buy(
            stock_code="000660",
            stock_name="SK하이닉스",
            quantity=5,
            price=150000,
            strategy="value",
        )

        # 전략별 포지션 조회
        momentum_positions = trader.tracker.get_positions_by_strategy("momentum")
        value_positions = trader.tracker.get_positions_by_strategy("value")

        assert len(momentum_positions) == 1
        assert len(value_positions) == 1
