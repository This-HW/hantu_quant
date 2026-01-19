"""
Tests for PostgreSQL migration models (Feature 3: F-PG-003).
Tests T-015 ~ T-021 model definitions.
"""
import json
import pytest
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database.models import (
    Base,
    # T-015
    APICall,
    # T-016
    ErrorEvent,
    # T-017
    RecoveryRule,
    # T-018
    StrategyPerformance,
    # T-019
    MarketRegime,
    # T-020
    BacktestPrediction,
    # T-021
    ActualPerformance,
    # Related models
    DailyStrategyReturn,
    PerformanceAlert,
    NotificationStats,
    ScreeningHistory,
    SelectionHistory,
    LearningMetrics,
    ModelPerformance,
)


@pytest.fixture
def engine():
    """In-memory SQLite engine for testing."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Database session for testing."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestAPICall:
    """T-015: APICall 모델 테스트"""

    def test_create_api_call(self, session):
        """APICall 생성 테스트"""
        api_call = APICall(
            timestamp=datetime.now(),
            endpoint='/api/v1/stocks',
            method='GET',
            response_time=150.5,
            status_code=200,
            success=1,
        )
        session.add(api_call)
        session.commit()

        assert api_call.id is not None
        assert api_call.endpoint == '/api/v1/stocks'
        assert api_call.method == 'GET'
        assert api_call.response_time == 150.5

    def test_api_call_to_dict(self, session):
        """APICall to_dict() 테스트"""
        api_call = APICall(
            timestamp=datetime(2026, 1, 11, 10, 0, 0),
            endpoint='/api/v1/orders',
            method='POST',
            response_time=200.0,
            status_code=201,
            success=1,
        )
        session.add(api_call)
        session.commit()

        result = api_call.to_dict()
        assert result['endpoint'] == '/api/v1/orders'
        assert result['method'] == 'POST'
        assert result['success'] is True

    def test_api_call_with_error(self, session):
        """APICall 에러 케이스 테스트"""
        api_call = APICall(
            timestamp=datetime.now(),
            endpoint='/api/v1/invalid',
            method='GET',
            response_time=5000.0,
            status_code=500,
            success=0,
            error_message='Internal Server Error',
        )
        session.add(api_call)
        session.commit()

        assert api_call.success == 0
        assert api_call.error_message == 'Internal Server Error'


class TestErrorEvent:
    """T-016: ErrorEvent 모델 테스트"""

    def test_create_error_event(self, session):
        """ErrorEvent 생성 테스트"""
        event = ErrorEvent(
            timestamp=datetime.now(),
            error_type='ConnectionError',
            severity='high',
            component='api_client',
            message='Failed to connect to KIS API',
        )
        session.add(event)
        session.commit()

        assert event.id is not None
        assert event.error_type == 'ConnectionError'
        assert event.severity == 'high'

    def test_error_event_with_recovery(self, session):
        """ErrorEvent 복구 정보 테스트"""
        event = ErrorEvent(
            timestamp=datetime.now(),
            error_type='TimeoutError',
            severity='medium',
            component='trading_engine',
            message='Request timeout',
            recovery_attempted=1,
            recovery_action='retry',
            recovery_success=1,
            recovery_time=2.5,
        )
        session.add(event)
        session.commit()

        result = event.to_dict()
        assert result['recovery_attempted'] is True
        assert result['recovery_success'] is True
        assert result['recovery_time'] == 2.5


class TestRecoveryRule:
    """T-017: RecoveryRule 모델 테스트"""

    def test_create_recovery_rule(self, session):
        """RecoveryRule 생성 테스트"""
        rule = RecoveryRule(
            name='api_timeout_recovery',
            error_pattern='TimeoutError|ConnectionTimeout',
            severity_threshold='medium',
            recovery_actions=json.dumps(['retry', 'notify']),
            max_attempts=5,
            cooldown_seconds=60,
        )
        session.add(rule)
        session.commit()

        assert rule.id is not None
        assert rule.name == 'api_timeout_recovery'
        assert rule.max_attempts == 5

    def test_recovery_rule_unique_name(self, session):
        """RecoveryRule 이름 유일성 테스트"""
        rule1 = RecoveryRule(
            name='unique_rule',
            error_pattern='.*',
            severity_threshold='low',
            recovery_actions='[]',
        )
        session.add(rule1)
        session.commit()

        rule2 = RecoveryRule(
            name='unique_rule',  # Duplicate name
            error_pattern='.*',
            severity_threshold='high',
            recovery_actions='[]',
        )
        session.add(rule2)

        with pytest.raises(Exception):
            session.commit()


class TestStrategyPerformance:
    """T-018: StrategyPerformance 모델 테스트"""

    def test_create_strategy_performance(self, session):
        """StrategyPerformance 생성 테스트"""
        perf = StrategyPerformance(
            strategy_name='momentum_strategy',
            date=date(2026, 1, 11),
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            total_return=15.5,
            annualized_return=12.3,
            sharpe_ratio=1.5,
            max_drawdown=-8.2,
            win_rate=58.5,
        )
        session.add(perf)
        session.commit()

        assert perf.id is not None
        assert perf.strategy_name == 'momentum_strategy'
        assert perf.total_return == 15.5

    def test_strategy_performance_json_fields(self, session):
        """StrategyPerformance JSON 필드 테스트"""
        monthly = json.dumps({'2025-01': 2.1, '2025-02': -0.5, '2025-03': 3.2})
        quarterly = json.dumps({'Q1': 4.8, 'Q2': 3.5, 'Q3': 2.1, 'Q4': 5.1})

        perf = StrategyPerformance(
            strategy_name='value_strategy',
            date=date(2026, 1, 11),
            period_start=date(2025, 1, 1),
            period_end=date(2025, 12, 31),
            monthly_returns=monthly,
            quarterly_returns=quarterly,
        )
        session.add(perf)
        session.commit()

        result = perf.to_dict()
        assert 'monthly_returns' in result
        parsed = json.loads(result['monthly_returns'])
        assert parsed['2025-01'] == 2.1


class TestMarketRegime:
    """T-019: MarketRegime 모델 테스트"""

    def test_create_market_regime(self, session):
        """MarketRegime 생성 테스트"""
        regime = MarketRegime(
            date=date(2026, 1, 11),
            regime_type='bull',
            market_return=0.5,
            volatility=12.5,
            confidence=0.85,
        )
        session.add(regime)
        session.commit()

        assert regime.id is not None
        assert regime.regime_type == 'bull'

    def test_market_regime_to_dict(self, session):
        """MarketRegime to_dict() 테스트"""
        regime = MarketRegime(
            date=date(2026, 1, 10),
            regime_type='sideways',
            market_return=0.1,
            volatility=8.5,
            confidence=0.72,
        )
        session.add(regime)
        session.commit()

        result = regime.to_dict()
        assert result['date'] == '2026-01-10'
        assert result['regime_type'] == 'sideways'
        assert result['confidence'] == 0.72


class TestBacktestPrediction:
    """T-020: BacktestPrediction 모델 테스트"""

    def test_create_backtest_prediction(self, session):
        """BacktestPrediction 생성 테스트"""
        pred = BacktestPrediction(
            prediction_id='PRED-2026-001',
            strategy_name='ml_ensemble',
            prediction_date=date(2026, 1, 11),
            target_stocks=json.dumps(['005930', '000660', '035420']),
            predicted_returns=json.dumps({'005930': 5.2, '000660': 3.1, '035420': 4.5}),
            predicted_weights=json.dumps({'005930': 0.4, '000660': 0.35, '035420': 0.25}),
            expected_return=4.2,
            model_confidence=0.78,
        )
        session.add(pred)
        session.commit()

        assert pred.id is not None
        assert pred.prediction_id == 'PRED-2026-001'

    def test_backtest_prediction_unique_id(self, session):
        """BacktestPrediction ID 유일성 테스트"""
        pred1 = BacktestPrediction(
            prediction_id='UNIQUE-001',
            strategy_name='test',
            prediction_date=date(2026, 1, 11),
            target_stocks='[]',
            predicted_returns='{}',
            predicted_weights='{}',
        )
        session.add(pred1)
        session.commit()

        pred2 = BacktestPrediction(
            prediction_id='UNIQUE-001',  # Duplicate
            strategy_name='test2',
            prediction_date=date(2026, 1, 12),
            target_stocks='[]',
            predicted_returns='{}',
            predicted_weights='{}',
        )
        session.add(pred2)

        with pytest.raises(Exception):
            session.commit()


class TestActualPerformance:
    """T-021: ActualPerformance 모델 테스트"""

    def test_create_actual_performance(self, session):
        """ActualPerformance 생성 테스트"""
        # First create backtest prediction
        pred = BacktestPrediction(
            prediction_id='PRED-FOR-ACTUAL-001',
            strategy_name='test_strategy',
            prediction_date=date(2026, 1, 5),
            target_stocks=json.dumps(['005930']),
            predicted_returns=json.dumps({'005930': 3.0}),
            predicted_weights=json.dumps({'005930': 1.0}),
        )
        session.add(pred)
        session.commit()

        # Then create actual performance
        actual = ActualPerformance(
            performance_id='PERF-001',
            prediction_id='PRED-FOR-ACTUAL-001',
            execution_date=date(2026, 1, 6),
            completion_date=date(2026, 1, 11),
            executed_stocks=json.dumps(['005930']),
            actual_returns=json.dumps({'005930': 2.8}),
            actual_weights=json.dumps({'005930': 1.0}),
            actual_return=2.8,
            status='completed',
        )
        session.add(actual)
        session.commit()

        assert actual.id is not None
        assert actual.prediction_id == 'PRED-FOR-ACTUAL-001'
        assert actual.status == 'completed'

    def test_actual_performance_relationship(self, session):
        """ActualPerformance 외래키 관계 테스트"""
        pred = BacktestPrediction(
            prediction_id='PRED-REL-001',
            strategy_name='relationship_test',
            prediction_date=date(2026, 1, 5),
            target_stocks='[]',
            predicted_returns='{}',
            predicted_weights='{}',
        )
        session.add(pred)
        session.commit()

        actual = ActualPerformance(
            performance_id='PERF-REL-001',
            prediction_id='PRED-REL-001',
            execution_date=date(2026, 1, 6),
            completion_date=date(2026, 1, 11),
            executed_stocks='[]',
            actual_returns='{}',
            actual_weights='{}',
            status='completed',
        )
        session.add(actual)
        session.commit()

        # Test relationship
        assert actual.backtest_prediction is not None
        assert actual.backtest_prediction.prediction_id == 'PRED-REL-001'


class TestRelatedModels:
    """관련 모델 테스트 (DataSynchronizer, Tracker 등용)"""

    def test_screening_history(self, session):
        """ScreeningHistory 테스트"""
        history = ScreeningHistory(
            screening_date=date(2026, 1, 11),
            stock_code='005930',
            stock_name='삼성전자',
            total_score=85.5,
            passed=1,
        )
        session.add(history)
        session.commit()
        assert history.id is not None

    def test_selection_history(self, session):
        """SelectionHistory 테스트"""
        history = SelectionHistory(
            selection_date=date(2026, 1, 11),
            stock_code='005930',
            stock_name='삼성전자',
            total_score=78.2,
            signal='buy',
            confidence=0.82,
        )
        session.add(history)
        session.commit()
        assert history.id is not None

    def test_learning_metrics(self, session):
        """LearningMetrics 테스트"""
        metrics = LearningMetrics(
            metric_date=date(2026, 1, 11),
            metric_type='screening_accuracy',
            model_name='ensemble_v1',
            value=0.72,
            sample_count=100,
        )
        session.add(metrics)
        session.commit()
        assert metrics.id is not None

    def test_daily_strategy_return(self, session):
        """DailyStrategyReturn 테스트"""
        ret = DailyStrategyReturn(
            strategy_name='momentum',
            date=date(2026, 1, 11),
            daily_return=0.5,
            cumulative_return=15.2,
        )
        session.add(ret)
        session.commit()
        assert ret.id is not None

    def test_model_performance(self, session):
        """ModelPerformance 테스트"""
        perf = ModelPerformance(
            model_name='lstm_predictor',
            evaluation_date=date(2026, 1, 11),
            accuracy=0.68,
            precision_score=0.65,
            recall_score=0.72,
            f1_score=0.68,
        )
        session.add(perf)
        session.commit()
        assert perf.id is not None

    def test_performance_alert(self, session):
        """PerformanceAlert 테스트"""
        alert = PerformanceAlert(
            model_name='ensemble_v1',
            alert_type='accuracy_drop',
            severity='warning',
            message='Model accuracy dropped below threshold',
            metric_name='accuracy',
            current_value=0.55,
            baseline_value=0.68,
            threshold=0.60,
        )
        session.add(alert)
        session.commit()
        assert alert.id is not None

    def test_notification_stats(self, session):
        """NotificationStats 테스트"""
        stats = NotificationStats(
            date=date(2026, 1, 11),
            channel='telegram',
            total_sent=50,
            total_failed=2,
        )
        session.add(stats)
        session.commit()
        assert stats.id is not None


class TestModelIntegrity:
    """모델 무결성 테스트"""

    def test_all_tables_created(self, engine):
        """모든 테이블 생성 확인"""
        tables = Base.metadata.tables.keys()

        expected_tables = [
            'api_calls', 'error_events', 'recovery_rules',
            'strategy_performance', 'market_regimes',
            'backtest_predictions', 'actual_performance',
            'performance_comparisons', 'daily_strategy_returns',
            'strategy_comparisons', 'model_baselines',
            'performance_alerts', 'notification_stats',
            'alert_settings', 'alert_statistics',
            'screening_history', 'selection_history',
            'learning_metrics', 'daily_tracking',
            'daily_accuracy', 'model_performance',
        ]

        for table in expected_tables:
            assert table in tables, f"Missing table: {table}"

    def test_indexes_created(self, engine):
        """인덱스 생성 확인"""
        from sqlalchemy import inspect
        inspector = inspect(engine)

        # Check api_calls indexes
        api_call_indexes = inspector.get_indexes('api_calls')
        index_names = [idx['name'] for idx in api_call_indexes]
        assert any('timestamp' in name for name in index_names)
        assert any('endpoint' in name for name in index_names)
