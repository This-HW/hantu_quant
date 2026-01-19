"""
학습 시스템 테스트

Phase C 학습 시스템의 모든 구성 요소를 테스트합니다.
"""

import pytest
from datetime import datetime, timedelta
import numpy as np

# Trade Logger
from core.learning.trade_logger import (
    TradeLogger,
    Trade,
    TradeContext,
    EntryContext,
    ExitContext,
    TradeLog,
    TradeLabels,
)

# Performance Pattern Analyzer
from core.learning.performance_pattern_analyzer import (
    PerformancePatternAnalyzer,
    PatternAnalysis,
)

# Failure Analyzer
from core.learning.failure_analyzer import (
    FailureAnalyzer,
    FailureAnalysis,
)

# LSTM Learner
from core.learning.lstm_learner import (
    LSTMContinuousLearner,
    LearnerConfig,
    RetrainDecision,
    RetrainUrgency,
)

# Scheduler
from core.learning.scheduler import (
    LearningScheduler,
    TaskPriority,
    TaskStatus,
)

# Tracker
from core.learning.tracker import (
    LearningTracker,
    LearningType,
)

# Safety
from core.learning.safety import (
    OverfitPrevention,
    ModelRollback,
    LearningSafetyManager,
    LearningResult,
)


class TestTradeLogger:
    """거래 로거 테스트"""

    def test_logger_creation(self):
        """로거 생성"""
        logger = TradeLogger()
        assert logger is not None
        assert len(logger._logs) == 0

    def test_record_entry(self):
        """진입 기록"""
        logger = TradeLogger()
        context = TradeContext(
            entry_indicators={"rsi": 45.0, "macd": 0.5},
            signal_source=["LSTM", "TA"],
            signal_confidence=0.75,
            agreement_count=2,
        )

        trade = logger.record_entry(
            trade_id="T001",
            stock_code="005930",
            direction="buy",
            entry_price=70000,
            quantity=10,
            context=context,
        )

        assert trade.id == "T001"
        assert trade.stock_code == "005930"
        assert trade.entry_price == 70000

    def test_record_exit(self):
        """청산 기록"""
        logger = TradeLogger()
        context = TradeContext(
            entry_indicators={"rsi": 45.0},
            signal_source=["LSTM"],
            signal_confidence=0.75,
            agreement_count=2,
            max_profit_during=5.0,
            max_loss_during=-2.0,
        )

        # 진입
        logger.record_entry(
            trade_id="T001",
            stock_code="005930",
            direction="buy",
            entry_price=70000,
            quantity=10,
            context=context,
        )

        # 청산
        exit_context = TradeContext(
            exit_indicators={"rsi": 65.0},
            exit_market_regime="bull",
            max_profit_during=5.0,
        )

        log = logger.record_exit(
            trade_id="T001",
            exit_price=73500,
            exit_reason="signal",
            context=exit_context,
            stock_name="삼성전자",
        )

        assert log is not None
        assert log.pnl_pct == pytest.approx(5.0, rel=0.01)
        assert log.labels.is_winner is True

    def test_log_trade(self):
        """거래 로그"""
        logger = TradeLogger()

        trade = Trade(
            id="T002",
            stock_code="000660",
            direction="buy",
            entry_price=100000,
            exit_price=106000,  # 6% 수익 (> 5%)
            quantity=5,
            pnl=30000,
            pnl_pct=6.0,  # 5% 초과해야 is_big_winner
            holding_days=3,
            exit_reason="take_profit",
            is_closed=True,
        )

        context = TradeContext(
            entry_indicators={"rsi": 40.0, "macd": 0.3},
            signal_source=["TA", "SD"],
            signal_confidence=0.8,
            agreement_count=2,
            market_regime="bull",
            daily_trend="up",
            weekly_trend="up",
        )

        log = logger.log_trade(trade, context, "SK하이닉스")

        assert log.trade_id == "T002"
        assert log.stock_name == "SK하이닉스"
        assert log.labels.is_winner is True
        assert log.labels.is_big_winner is True

    def test_get_logs(self):
        """로그 조회"""
        logger = TradeLogger()

        # 여러 거래 기록
        for i in range(5):
            trade = Trade(
                id=f"T{i:03d}",
                stock_code="005930" if i % 2 == 0 else "000660",
                direction="buy",
                entry_price=70000,
                exit_price=71000 if i % 3 == 0 else 69000,
                pnl=1000 if i % 3 == 0 else -1000,
                pnl_pct=1.43 if i % 3 == 0 else -1.43,
                is_closed=True,
            )
            logger.log_trade(trade, TradeContext())

        # 전체 조회
        all_logs = logger.get_logs()
        assert len(all_logs) == 5

        # 종목 필터
        filtered = logger.get_logs(stock_code="005930")
        assert len(filtered) == 3

        # 수익 거래만
        winners = logger.get_logs(winners_only=True)
        assert len(winners) == 2

    def test_get_stats(self):
        """통계 조회"""
        logger = TradeLogger()

        # 거래 기록
        for i in range(10):
            trade = Trade(
                id=f"T{i:03d}",
                stock_code="005930",
                direction="buy",
                entry_price=70000,
                exit_price=72000 if i < 6 else 68000,
                pnl=2000 if i < 6 else -2000,
                pnl_pct=2.86 if i < 6 else -2.86,
                is_closed=True,
            )
            logger.log_trade(trade, TradeContext())

        stats = logger.get_stats()
        assert stats["total_trades"] == 10
        assert stats["winners"] == 6
        assert stats["losers"] == 4
        assert stats["win_rate"] == pytest.approx(0.6, rel=0.01)


class TestPerformancePatternAnalyzer:
    """성과 패턴 분석기 테스트"""

    def _create_sample_logs(self) -> list:
        """샘플 로그 생성"""
        logs = []
        for i in range(30):
            is_winner = i % 3 != 2  # 2/3 승률
            log = TradeLog(
                trade_id=f"T{i:03d}",
                timestamp=datetime.now() - timedelta(days=30 - i),
                stock_code="005930",
                direction="buy",
                entry_price=70000,
                exit_price=72000 if is_winner else 68000,
                pnl=2000 if is_winner else -2000,
                pnl_pct=2.86 if is_winner else -2.86,
                holding_days=i % 10 + 1,
                entry_context=EntryContext(
                    rsi=40 + i % 20,
                    agreement_count=2 if is_winner else 1,
                    signal_confidence=0.7 if is_winner else 0.5,
                    signal_source=["LSTM", "TA"] if is_winner else ["TA"],
                    market_regime="bull" if is_winner else "range",
                    daily_trend="up" if is_winner else "down",
                    weekly_trend="up" if is_winner else "down",
                ),
                labels=TradeLabels(
                    is_winner=is_winner,
                    is_big_winner=is_winner and i % 5 == 0,
                ),
            )
            logs.append(log)
        return logs

    def test_analyzer_creation(self):
        """분석기 생성"""
        analyzer = PerformancePatternAnalyzer()
        assert analyzer is not None
        assert analyzer.min_samples == 20

    def test_analyze_patterns(self):
        """패턴 분석"""
        analyzer = PerformancePatternAnalyzer(min_samples=5)
        logs = self._create_sample_logs()

        analysis = analyzer.analyze_patterns(logs)

        assert isinstance(analysis, PatternAnalysis)
        assert analysis.winning_conditions.total_winners == 20
        assert analysis.losing_conditions.total_losers == 10

    def test_winning_conditions(self):
        """승리 조건 분석"""
        analyzer = PerformancePatternAnalyzer(min_samples=5)
        logs = self._create_sample_logs()

        analysis = analyzer.analyze_patterns(logs)

        assert analysis.winning_conditions.min_agreement >= 1
        assert 0 <= analysis.winning_conditions.mtf_alignment_rate <= 1

    def test_performance_by_regime(self):
        """레짐별 성과 분석"""
        analyzer = PerformancePatternAnalyzer(min_samples=3)
        logs = self._create_sample_logs()

        analysis = analyzer.analyze_patterns(logs)

        assert (
            "bull" in analysis.performance_by_regime
            or "range" in analysis.performance_by_regime
        )

    def test_get_recommendations(self):
        """권고 생성"""
        analyzer = PerformancePatternAnalyzer(min_samples=5)
        logs = self._create_sample_logs()

        analysis = analyzer.analyze_patterns(logs)
        recommendations = analyzer.get_recommendations(analysis)

        assert isinstance(recommendations, list)
        # 권고사항이 있으면 category 필드가 있어야 함
        if recommendations:
            assert "category" in recommendations[0]


class TestFailureAnalyzer:
    """실패 분석기 테스트"""

    def _create_loser_logs(self) -> list:
        """손실 거래 로그 생성"""
        logs = []
        failure_types = [
            ("trend_against", {"daily_trend": "up", "weekly_trend": "down"}),
            ("weak_signal", {"signal_confidence": 0.4}),
            ("low_agreement", {"agreement_count": 1}),
            ("other", {}),
        ]

        for i in range(20):
            ftype, attrs = failure_types[i % len(failure_types)]
            ctx = EntryContext(
                rsi=50,
                signal_confidence=attrs.get("signal_confidence", 0.7),
                agreement_count=attrs.get("agreement_count", 2),
                daily_trend=attrs.get("daily_trend", "up"),
                weekly_trend=attrs.get("weekly_trend", "up"),
            )

            log = TradeLog(
                trade_id=f"L{i:03d}",
                timestamp=datetime.now() - timedelta(days=20 - i),
                stock_code="005930",
                direction="buy",
                entry_price=70000,
                exit_price=67000,
                pnl=-3000,
                pnl_pct=-4.29,
                entry_context=ctx,
                exit_context=ExitContext(exit_reason="stop_loss"),
                labels=TradeLabels(is_winner=False, is_big_loser=True),
            )
            logs.append(log)
        return logs

    def test_analyzer_creation(self):
        """분석기 생성"""
        analyzer = FailureAnalyzer()
        assert analyzer is not None

    def test_analyze_failures(self):
        """실패 분석"""
        analyzer = FailureAnalyzer(min_samples=3)
        losers = self._create_loser_logs()

        analysis = analyzer.analyze_failures(losers)

        assert isinstance(analysis, FailureAnalysis)
        assert analysis.total_losers == 20
        assert analysis.total_loss < 0

    def test_failure_classification(self):
        """실패 유형 분류"""
        analyzer = FailureAnalyzer(min_samples=3)
        losers = self._create_loser_logs()

        analysis = analyzer.analyze_failures(losers)

        # 실패 분포 확인
        assert len(analysis.failure_distribution) > 0

    def test_improvement_suggestions(self):
        """개선 제안"""
        analyzer = FailureAnalyzer(min_samples=3)
        losers = self._create_loser_logs()

        analysis = analyzer.analyze_failures(losers)

        # 개선 제안이 있을 수 있음
        if analysis.improvement_suggestions:
            assert "priority" in analysis.improvement_suggestions[0].to_dict()

    def test_get_summary(self):
        """요약 생성"""
        analyzer = FailureAnalyzer(min_samples=3)
        losers = self._create_loser_logs()

        analysis = analyzer.analyze_failures(losers)
        summary = analyzer.get_summary(analysis)

        assert isinstance(summary, str)
        assert "실패 거래 분석 요약" in summary


class TestLSTMContinuousLearner:
    """LSTM 지속 학습기 테스트"""

    def test_learner_creation(self):
        """학습기 생성"""
        learner = LSTMContinuousLearner()
        assert learner is not None
        assert learner.model_version == "v0"

    def test_learner_with_config(self):
        """설정과 함께 생성"""
        config = LearnerConfig(
            retrain_period="daily",
            min_new_samples=50,
            performance_threshold=0.6,
        )
        learner = LSTMContinuousLearner(config)

        assert learner.config.retrain_period == "daily"
        assert learner.config.min_new_samples == 50

    def test_should_retrain_scheduled(self):
        """정기 재학습 판단"""
        learner = LSTMContinuousLearner()

        decision = learner.should_retrain({"recent_accuracy": 0.6})

        assert isinstance(decision, RetrainDecision)
        # 첫 번째 호출이므로 scheduled 가 있어야 함
        assert "scheduled" in decision.reasons

    def test_should_retrain_low_performance(self):
        """성과 저하 시 재학습"""
        learner = LSTMContinuousLearner()
        learner._last_retrain = datetime.now()  # 최근 학습 완료

        decision = learner.should_retrain(
            {
                "recent_accuracy": 0.45,  # 임계값 미만
            }
        )

        assert decision.should_retrain is True
        assert any("low_performance" in r for r in decision.reasons)
        assert decision.urgency == RetrainUrgency.HIGH

    def test_record_sample(self):
        """샘플 기록"""
        learner = LSTMContinuousLearner()

        for _ in range(10):
            learner.record_sample()

        assert learner._new_samples_count == 10

    def test_retrain_with_data(self):
        """데이터로 재학습"""
        learner = LSTMContinuousLearner()

        # 충분한 학습 데이터
        training_data = {
            "prices": [100 + i * 0.5 + np.random.randn() for i in range(300)],
            "volumes": [1000 + np.random.randint(-100, 100) for _ in range(300)],
            "indicators": {
                "rsi": [50 + np.random.randn() * 10 for _ in range(300)],
            },
        }

        result = learner.retrain(training_data)

        assert result.success is True
        assert result.training_samples > 0

    def test_get_stats(self):
        """통계 조회"""
        learner = LSTMContinuousLearner()

        stats = learner.get_stats()

        assert "model_version" in stats
        assert "config" in stats


class TestLearningScheduler:
    """학습 스케줄러 테스트"""

    def test_scheduler_creation(self):
        """스케줄러 생성"""
        scheduler = LearningScheduler()
        assert scheduler is not None
        assert len(scheduler._tasks) == 0

    def test_register_task(self):
        """작업 등록"""
        scheduler = LearningScheduler()

        scheduler.register_task(
            name="test_task",
            task_func=lambda: "done",
            schedule_type="daily",
            trigger="16:00",
            priority=TaskPriority.HIGH,
        )

        assert "test_task" in scheduler._tasks
        assert scheduler._tasks["test_task"].priority == TaskPriority.HIGH

    def test_run_task(self):
        """작업 실행"""
        scheduler = LearningScheduler()
        executed = []

        def task_func():
            executed.append(1)
            return "success"

        scheduler.register_task(
            name="test_task",
            task_func=task_func,
            schedule_type="daily",
        )

        result = scheduler.run_task("test_task")

        assert result.status == TaskStatus.COMPLETED
        assert len(executed) == 1

    def test_run_task_failure(self):
        """작업 실패 처리"""
        scheduler = LearningScheduler()

        def failing_task():
            raise ValueError("Test error")

        scheduler.register_task(
            name="failing_task",
            task_func=failing_task,
            schedule_type="daily",
        )

        result = scheduler.run_task("failing_task")

        assert result.status == TaskStatus.FAILED
        assert "Test error" in result.error

    def test_get_pending_tasks(self):
        """대기 작업 조회"""
        scheduler = LearningScheduler()

        scheduler.register_task(
            name="task1",
            task_func=lambda: None,
            schedule_type="daily",
            trigger="16:00",
        )
        scheduler.register_task(
            name="task2",
            task_func=lambda: None,
            schedule_type="weekly",
            trigger="friday 17:00",
        )

        pending = scheduler.get_pending_tasks()

        assert len(pending) == 2
        assert all("next_run" in p for p in pending)

    def test_get_stats(self):
        """통계 조회"""
        scheduler = LearningScheduler()

        scheduler.register_task("t1", lambda: None, "daily")
        scheduler.register_task("t2", lambda: None, "weekly")

        stats = scheduler.get_stats()

        assert stats["total_tasks"] == 2
        assert stats["enabled_tasks"] == 2


class TestLearningTracker:
    """학습 추적기 테스트"""

    def test_tracker_creation(self):
        """추적기 생성"""
        tracker = LearningTracker()
        assert tracker is not None
        assert len(tracker._records) == 0

    def test_log_learning_result(self):
        """학습 결과 기록"""
        tracker = LearningTracker()

        record = tracker.log_learning_result(
            learning_type=LearningType.MODEL_RETRAIN,
            before_state={"version": "v1"},
            after_state={"version": "v2"},
            before_performance={"accuracy": 0.55},
            after_performance={"accuracy": 0.60},
            training_samples=1000,
            validation_score=0.58,
            notes="Test retrain",
        )

        assert record.id.startswith("LR")
        assert record.improvement == pytest.approx(0.05, rel=0.01)

    def test_get_learning_history(self):
        """학습 이력 조회"""
        tracker = LearningTracker()

        # 여러 기록 추가
        for i in range(5):
            tracker.log_learning_result(
                learning_type=(
                    LearningType.WEIGHT_ADJUST
                    if i % 2 == 0
                    else LearningType.MODEL_RETRAIN
                ),
                before_state={},
                after_state={},
                before_performance={"accuracy": 0.5 + i * 0.01},
                after_performance={"accuracy": 0.52 + i * 0.01},
            )

        # 전체 조회
        history = tracker.get_learning_history(days=30)
        assert len(history) == 5

        # 유형별 조회
        weight_history = tracker.get_learning_history(
            learning_type=LearningType.WEIGHT_ADJUST, days=30
        )
        assert len(weight_history) == 3

    def test_analyze_effectiveness(self):
        """학습 효과 분석"""
        tracker = LearningTracker()

        # 기록 추가
        for i in range(10):
            tracker.log_learning_result(
                learning_type=LearningType.MODEL_RETRAIN,
                before_state={},
                after_state={},
                before_performance={"accuracy": 0.5},
                after_performance={"accuracy": 0.52 if i < 7 else 0.48},
            )

        report = tracker.analyze_learning_effectiveness(days=30)

        assert report.overall_improvement != 0
        assert LearningType.MODEL_RETRAIN.value in report.effectiveness_by_type

    def test_get_stats(self):
        """통계 조회"""
        tracker = LearningTracker()

        tracker.log_learning_result(
            learning_type=LearningType.PARAM_OPTIMIZE,
            before_state={},
            after_state={},
            before_performance={"accuracy": 0.5},
            after_performance={"accuracy": 0.55},
        )

        stats = tracker.get_stats()

        assert stats["total_records"] == 1
        assert stats["positive_rate"] == 1.0


class TestOverfitPrevention:
    """과적합 방지 테스트"""

    def test_prevention_creation(self):
        """과적합 방지 생성"""
        prevention = OverfitPrevention()
        assert prevention is not None

    def test_validate_good_result(self):
        """정상 결과 검증"""
        prevention = OverfitPrevention()

        result = LearningResult(
            success=True,
            training_samples=200,
            training_score=0.65,
            validation_score=0.62,
            out_of_sample_score=0.60,
            improvement=0.05,
        )

        validation = prevention.validate_learning_result(result)

        assert validation.passed is True
        assert validation.recommendation == "apply"

    def test_validate_overfit_result(self):
        """과적합 결과 검증"""
        prevention = OverfitPrevention()

        result = LearningResult(
            success=True,
            training_samples=200,
            training_score=0.85,  # 높은 학습 점수
            validation_score=0.55,  # 낮은 검증 점수
            out_of_sample_score=0.50,
            improvement=0.05,
        )

        validation = prevention.validate_learning_result(result)

        # 과적합 징후가 감지되어야 함
        overfit_checks = [
            c for c in validation.checks if c.check_type.value == "overfit_gap"
        ]
        assert len(overfit_checks) == 1
        assert overfit_checks[0].passed is False

    def test_validate_insufficient_samples(self):
        """샘플 부족 검증"""
        prevention = OverfitPrevention()

        result = LearningResult(
            success=True,
            training_samples=50,  # 부족
            training_score=0.65,
            validation_score=0.62,
        )

        validation = prevention.validate_learning_result(result)

        min_samples_checks = [
            c for c in validation.checks if c.check_type.value == "min_samples"
        ]
        assert len(min_samples_checks) == 1
        assert min_samples_checks[0].passed is False


class TestModelRollback:
    """모델 롤백 테스트"""

    def test_rollback_creation(self):
        """롤백 메커니즘 생성"""
        rollback = ModelRollback()
        assert rollback is not None
        assert rollback.current_version == "v0"

    def test_save_model_state(self):
        """모델 상태 저장"""
        rollback = ModelRollback()

        rollback.save_model_state(
            model_state={"weights": [1, 2, 3]},
            version="v1",
            performance={"accuracy": 0.6},
        )

        assert rollback.current_version == "v1"
        assert len(rollback._model_history) == 1

    def test_should_rollback_performance_drop(self):
        """성과 하락 시 롤백"""
        rollback = ModelRollback()

        decision = rollback.should_rollback(
            current_performance=0.35,  # 크게 하락
            previous_performance=0.60,
        )

        assert decision.should_rollback is True
        assert "성과 급락" in decision.reason

    def test_should_rollback_consecutive_losses(self):
        """연속 손실 시 롤백"""
        rollback = ModelRollback()

        # 연속 손실 기록
        for _ in range(6):
            rollback.record_trade_result(is_win=False, pnl=-1000)

        decision = rollback.should_rollback(
            current_performance=0.55,
            previous_performance=0.55,
        )

        assert decision.should_rollback is True
        assert "연속" in decision.reason

    def test_rollback_execution(self):
        """롤백 실행"""
        rollback = ModelRollback()

        # 버전 저장
        rollback.save_model_state({"v": 1}, "v1", {"accuracy": 0.5})
        rollback.save_model_state({"v": 2}, "v2", {"accuracy": 0.4})

        # v1으로 롤백
        state = rollback.rollback("v1")

        assert state == {"v": 1}
        assert rollback.current_version == "v1"


class TestLearningSafetyManager:
    """학습 안전 관리자 테스트"""

    def test_manager_creation(self):
        """관리자 생성"""
        manager = LearningSafetyManager()
        assert manager is not None

    def test_validate_and_apply_good(self):
        """정상 결과 적용"""
        manager = LearningSafetyManager()

        result = LearningResult(
            success=True,
            training_samples=200,
            training_score=0.65,
            validation_score=0.62,
            out_of_sample_score=0.60,
            improvement=0.05,
        )

        apply_result = manager.validate_and_apply(result, {"model": "test"})

        assert apply_result["applied"] is True
        assert "version" in apply_result

    def test_validate_and_apply_reject(self):
        """거부 결과 처리"""
        manager = LearningSafetyManager()

        result = LearningResult(
            success=True,
            training_samples=20,  # 부족
            training_score=0.90,
            validation_score=0.50,  # 과적합
            improvement=0.5,  # 급격한 변화
        )

        apply_result = manager.validate_and_apply(result, {"model": "test"})

        assert apply_result["applied"] is False

    def test_check_and_rollback(self):
        """체크 및 롤백"""
        manager = LearningSafetyManager()

        # 모델 상태 저장
        manager.model_rollback.save_model_state({"v": 1}, "v1", {"accuracy": 0.6})

        # 성과 급락 체크
        result = manager.check_and_rollback(
            current_performance=0.30,
            previous_performance=0.60,
        )

        assert result["rolled_back"] is True

    def test_get_status(self):
        """상태 조회"""
        manager = LearningSafetyManager()

        status = manager.get_status()

        assert "current_version" in status
        assert "consecutive_losses" in status


class TestLearningIntegration:
    """학습 시스템 통합 테스트"""

    def test_full_learning_pipeline(self):
        """전체 학습 파이프라인"""
        # 1. 거래 로거 설정
        trade_logger = TradeLogger()

        # 2. 거래 기록
        for i in range(20):
            trade = Trade(
                id=f"T{i:03d}",
                stock_code="005930",
                direction="buy",
                entry_price=70000,
                exit_price=72000 if i < 12 else 68000,
                pnl=2000 if i < 12 else -2000,
                pnl_pct=2.86 if i < 12 else -2.86,
                is_closed=True,
            )
            context = TradeContext(
                signal_source=["LSTM", "TA"],
                signal_confidence=0.7 if i < 12 else 0.5,
                agreement_count=2 if i < 12 else 1,
            )
            trade_logger.log_trade(trade, context)

        # 3. 성과 분석
        analyzer = PerformancePatternAnalyzer(min_samples=5)
        logs = trade_logger.get_logs()
        analysis = analyzer.analyze_patterns(logs)

        assert analysis.winning_conditions.total_winners == 12

        # 4. 실패 분석
        failure_analyzer = FailureAnalyzer(min_samples=3)
        losers = [log for log in logs if not log.labels.is_winner]
        failure_analysis = failure_analyzer.analyze_failures(losers)

        assert failure_analysis.total_losers == 8

        # 5. 학습 결과 추적
        tracker = LearningTracker()
        tracker.log_learning_result(
            learning_type=LearningType.MODEL_RETRAIN,
            before_state={"version": "v1"},
            after_state={"version": "v2"},
            before_performance={"win_rate": 0.5},
            after_performance={"win_rate": 0.6},
        )

        stats = tracker.get_stats()
        assert stats["total_records"] == 1

    def test_safety_with_scheduler(self):
        """스케줄러와 안전장치 통합"""
        scheduler = LearningScheduler()
        safety_manager = LearningSafetyManager()

        # 안전 체크 작업 등록
        def safety_check_task():
            return safety_manager.get_status()

        scheduler.register_task(
            name="safety_check",
            task_func=safety_check_task,
            schedule_type="daily",
            trigger="09:00",
        )

        # 작업 실행
        result = scheduler.run_task("safety_check")

        assert result.status == TaskStatus.COMPLETED
        assert "current_version" in result.result
