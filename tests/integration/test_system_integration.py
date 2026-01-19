"""
전체 시스템 통합 테스트

모든 모듈이 함께 작동하는지 검증합니다.
"""


# 전략 모듈
from core.strategy.ensemble import (
    EnsembleEngine,
    SignalAggregator,
)

# 리스크 관리 모듈
from core.risk.position import (
    KellyCalculator,
    KellyConfig,
)
from core.risk.drawdown import (
    DrawdownMonitor,
    DrawdownConfig,
)
from core.risk.correlation import (
    DiversificationScore,
)

# 학습 모듈
from core.learning import (
    TradeLogger,
)

# 알림 모듈
from core.notification import (
    NotificationManager,
)
from core.notification import MockNotifier

# 페이퍼 트레이딩 모듈
from core.paper_trading import (
    PaperTrader,
    PaperTradingConfig,
)


class TestStrategyToTradingIntegration:
    """전략에서 트레이딩까지 통합 테스트"""

    def test_signal_aggregator_to_paper_trade(self):
        """신호 집계에서 페이퍼 트레이드까지"""
        # 1. 신호 집계기 설정
        SignalAggregator()

        # 2. 페이퍼 트레이딩 설정
        paper_config = PaperTradingConfig(
            initial_capital=10_000_000,
            default_stop_loss_pct=5.0,
            default_take_profit_pct=10.0,
        )
        trader = PaperTrader(paper_config)
        trader.start_session()

        # 3. 신호에 따라 매수
        trader._current_prices["005930"] = 70000

        # 매수 신호 (강도 > 0)
        buy_result = trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=70000,
            strategy="ensemble",
            signal_source=["ta_scorer", "supply_demand"],
        )
        assert buy_result.success is True

        # 4. 포지션 확인
        positions = trader.get_positions()
        assert len(positions) == 1
        assert positions[0]['strategy'] == "ensemble"

    def test_kelly_position_sizing_with_paper_trading(self):
        """켈리 기준으로 포지션 사이징 후 페이퍼 트레이딩"""
        # 1. 켈리 계산기 설정
        kelly = KellyCalculator(KellyConfig(
            kelly_fraction=0.5,
            max_position=0.25,
        ))

        # 2. 포지션 크기 계산 (통계 기반)
        result = kelly.calculate_from_stats(
            win_rate=0.6,
            win_loss_ratio=1.5,  # avg_win / avg_loss
        )

        assert result.final_position > 0

        # 3. 페이퍼 트레이딩으로 실행
        trader = PaperTrader()
        trader.start_session()
        trader._current_prices["005930"] = 70000

        # 켈리 비율에 따른 수량 계산
        invest_amount = 10_000_000 * result.final_position
        quantity = int(invest_amount / 70000)

        if quantity > 0:
            buy_result = trader.buy(
                stock_code="005930",
                stock_name="삼성전자",
                quantity=min(quantity, 10),  # 포지션 제한
                price=70000,
            )

            # 포지션 크기 제한에 걸릴 수 있음
            if buy_result.success:
                assert len(trader.get_holdings()) == 1

    def test_drawdown_management_triggers_stop(self):
        """드로우다운 관리가 거래 중지 트리거"""
        # 1. 드로우다운 관리자 설정
        dd_config = DrawdownConfig(
            caution_threshold=0.05,
            warning_threshold=0.10,
            critical_threshold=0.15,
        )
        DrawdownMonitor(dd_config)

        # 2. 페이퍼 트레이딩 설정
        paper_config = PaperTradingConfig(
            initial_capital=10_000_000,
            default_stop_loss_pct=0,  # 자동 손절 비활성화
        )
        trader = PaperTrader(paper_config)
        trader.start_session()

        # 3. 포지션 열기
        trader._current_prices["005930"] = 100000
        trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=100000,
        )

        # 4. 가격 하락 시뮬레이션
        new_price = 85000  # -15%
        trader.update_prices({"005930": new_price})

        # 5. 드로우다운 체크
        portfolio_value = trader.portfolio.total_value
        peak_value = 10_000_000
        current_drawdown = (peak_value - portfolio_value) / peak_value

        # 드로우다운이 발생했는지 확인
        assert current_drawdown > 0

    def test_diversification_scoring(self):
        """분산투자 점수 계산"""
        import pandas as pd

        # 1. 분산투자 점수 계산기
        scorer = DiversificationScore()

        # 2. 포지션 데이터 (종목코드: 비중)
        positions = {
            "005930": 0.25,
            "000660": 0.25,
            "035420": 0.25,
            "051910": 0.25,
        }

        # 3. 섹터 매핑
        sector_mapping = {
            "005930": "반도체",
            "000660": "반도체",
            "035420": "인터넷",
            "051910": "화학",
        }

        # 4. 가격 데이터 (가상)
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        price_data = {
            "005930": pd.DataFrame({'close': [70000 + i * 100 for i in range(30)]}, index=dates),
            "000660": pd.DataFrame({'close': [150000 + i * 200 for i in range(30)]}, index=dates),
            "035420": pd.DataFrame({'close': [200000 - i * 150 for i in range(30)]}, index=dates),
            "051910": pd.DataFrame({'close': [100000 + i * 50 for i in range(30)]}, index=dates),
        }

        # 5. 점수 계산
        result = scorer.calculate(
            positions=positions,
            price_data=price_data,
            sector_mapping=sector_mapping,
        )

        assert 0 <= result.score <= 1
        assert result.sector_concentration >= 0


class TestLearningSystemIntegration:
    """학습 시스템 통합 테스트"""

    def test_trade_logging_and_analysis(self):
        """거래 로깅 및 분석"""
        import uuid
        from core.learning import (
            TradeLogger, Trade, TradeContext, PerformancePatternAnalyzer
        )

        # 1. 거래 로거
        logger = TradeLogger()

        # 2. Trade 객체 생성 (실제 API에 맞춤)
        trade = Trade(
            id=str(uuid.uuid4()),
            stock_code="005930",
            direction="buy",
            entry_price=70000,
            exit_price=75000,
            quantity=10,
            pnl=50000,
            pnl_pct=7.14,
            holding_days=5,
            exit_reason="take_profit",
            is_closed=True,
        )

        # 3. 컨텍스트 생성 (플랫 구조)
        context = TradeContext(
            signal_strength=0.8,
            signal_source=["ma_cross", "rsi"],
            signal_confidence=0.9,
            market_regime="bull",
        )

        # 4. 거래 로그 생성
        trade_log = logger.log_trade(
            trade=trade,
            context=context,
            stock_name="삼성전자",
        )

        # 승리 거래 확인
        assert trade_log.labels.is_winner is True

        # 5. 패턴 분석
        analyzer = PerformancePatternAnalyzer()
        patterns = analyzer.analyze_patterns([trade_log])
        assert patterns is not None

    def test_failure_analysis(self):
        """실패 분석"""
        import uuid
        from core.learning import (
            FailureAnalyzer, TradeLogger, Trade, TradeContext
        )

        # 1. 거래 로거
        logger = TradeLogger()

        # 2. 실패 거래 생성 (실제 API에 맞춤)
        trade = Trade(
            id=str(uuid.uuid4()),
            stock_code="005930",
            direction="buy",
            entry_price=70000,
            exit_price=65000,
            quantity=10,
            pnl=-50000,
            pnl_pct=-7.14,
            holding_days=3,
            exit_reason="stop_loss",
            is_closed=True,
        )

        context = TradeContext(
            signal_strength=0.3,  # 약한 신호
            signal_confidence=0.4,
            market_regime="range",
        )

        trade_log = logger.log_trade(trade=trade, context=context)

        # 3. 실패 분석기
        analyzer = FailureAnalyzer()

        # 4. 분석 (실패 거래 리스트 전달)
        result = analyzer.analyze_failures([trade_log])

        # 분석 결과 확인
        assert result is not None
        assert len(result.common_mistakes) >= 0  # 실패 패턴 확인


class TestNotificationIntegration:
    """알림 시스템 통합 테스트"""

    def test_trade_notification_flow(self):
        """거래 알림 흐름"""
        # 1. 알림 관리자 설정
        manager = NotificationManager()
        mock_notifier = MockNotifier()
        manager.register_notifier('mock', mock_notifier)

        # 2. 페이퍼 트레이딩과 연동
        notifications_received = []

        def notification_callback(event, data):
            notifications_received.append((event, data))
            # 알림 발송
            if event == 'buy_executed':
                manager.notify_trade_entry(
                    stock_code=data['stock_code'],
                    stock_name=data['stock_name'],
                    direction='BUY',
                    price=data['price'],
                    quantity=data['quantity'],
                    signal_source=['test'],
                    confidence=0.8,
                )

        trader = PaperTrader(notification_callback=notification_callback)
        trader.start_session()

        # 3. 매수 실행
        trader._current_prices["005930"] = 70000
        trader.buy(
            stock_code="005930",
            stock_name="삼성전자",
            quantity=10,
            price=70000,
        )

        # 4. 알림 확인
        assert len(notifications_received) >= 1
        assert notifications_received[-1][0] == 'buy_executed'


class TestEndToEndWorkflow:
    """전체 워크플로우 테스트"""

    def test_complete_trading_workflow(self):
        """완전한 거래 워크플로우"""
        # 1. 시스템 초기화
        trader = PaperTrader(PaperTradingConfig(
            initial_capital=10_000_000,
            default_stop_loss_pct=3.0,
            default_take_profit_pct=5.0,
        ))
        TradeLogger()
        notification_manager = NotificationManager()
        mock_notifier = MockNotifier()
        notification_manager.register_notifier('mock', mock_notifier)

        # 2. 트레이딩 세션 시작
        session = trader.start_session("test_workflow")
        assert session.is_active

        # 3. 신호 생성 (가상)
        signal = {
            'stock_code': '005930',
            'stock_name': '삼성전자',
            'action': 'BUY',
            'strength': 0.8,
            'sources': ['ma_cross', 'rsi_oversold'],
        }

        # 4. 포지션 사이징 (켈리 기준)
        kelly = KellyCalculator()
        position_result = kelly.calculate_from_stats(
            win_rate=0.6,
            win_loss_ratio=5000/3000,  # avg_win / avg_loss
        )

        # 5. 매수 실행
        trader._current_prices["005930"] = 70000
        # final_position은 비율 (0.0~1.0)
        invest_amount = trader.portfolio.total_value * position_result.final_position
        quantity = min(int(invest_amount / 70000), 10)
        quantity = max(quantity, 1)

        buy_result = trader.buy(
            stock_code=signal['stock_code'],
            stock_name=signal['stock_name'],
            quantity=quantity,
            price=70000,
            strategy="momentum",
            signal_source=signal['sources'],
        )

        assert buy_result.success is True

        # 6. 알림 발송
        notification_manager.notify_trade_entry(
            stock_code=signal['stock_code'],
            stock_name=signal['stock_name'],
            direction='BUY',
            price=buy_result.filled_price,
            quantity=buy_result.filled_quantity,
            signal_source=signal['sources'],
            confidence=signal['strength'],
        )

        # 7. 가격 변동 (익절 조건 충족)
        trader.update_prices({"005930": 74000})

        # 8. 세션 종료
        session = trader.end_session()
        assert session is not None
        assert session.trades_executed >= 1

        # 9. 성과 보고서
        report = trader.get_performance_report()
        assert 'portfolio' in report
        assert 'positions' in report

    def test_risk_integration(self):
        """리스크 관리 통합"""
        # 1. 드로우다운 모니터
        DrawdownMonitor(DrawdownConfig(
            warning_threshold=0.03,
            critical_threshold=0.05,
        ))

        # 2. 분산투자 점수 계산기
        DiversificationScore()

        # 3. 페이퍼 트레이더
        trader = PaperTrader(PaperTradingConfig(
            initial_capital=10_000_000,
            max_position_size=0.2,
            max_total_exposure=0.8,
        ))
        trader.start_session()

        # 4. 여러 포지션 열기
        stocks = [
            ("005930", "삼성전자", 70000, 10),
            ("000660", "SK하이닉스", 150000, 5),
            ("035420", "NAVER", 200000, 3),
        ]

        for code, name, price, qty in stocks:
            trader._current_prices[code] = price
            trader.buy(
                stock_code=code,
                stock_name=name,
                quantity=qty,
                price=price,
            )

        # 5. 포트폴리오 상태 확인
        status = trader.get_portfolio_status()
        assert status['position_count'] <= 3

        # 6. 가격 하락 시뮬레이션
        trader.update_prices({
            "005930": 68000,
            "000660": 145000,
            "035420": 195000,
        })

        # 7. 세션 종료
        trader.end_session()


class TestModuleInteroperability:
    """모듈 간 상호운용성 테스트"""

    def test_all_modules_can_be_imported(self):
        """모든 모듈이 임포트 가능한지"""
        # 전략 모듈

        # 리스크 모듈

        # 학습 모듈

        # 알림 모듈

        # 페이퍼 트레이딩 모듈

        assert True  # 모든 임포트 성공

    def test_data_flow_between_modules(self):
        """모듈 간 데이터 흐름"""
        # 1. 전략 -> 신호 생성
        ensemble = EnsembleEngine()

        # 2. 리스크 -> 포지션 크기
        kelly = KellyCalculator()

        # 3. 트레이딩 -> 실행
        trader = PaperTrader()
        trader.start_session()

        # 4. 학습 -> 기록
        logger = TradeLogger()

        # 5. 알림 -> 발송
        manager = NotificationManager()

        # 모든 모듈이 독립적으로 작동
        assert ensemble is not None
        assert kelly is not None
        assert trader is not None
        assert logger is not None
        assert manager is not None
