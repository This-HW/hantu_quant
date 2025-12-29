"""
적응형 학습 시스템 통합 테스트

Features A, B, C, D 전체 통합 테스트
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Feature A: 자동 재학습 파이프라인
from core.learning.retrain.retrain_trigger import RetrainTrigger, RetrainReason
from core.learning.retrain.model_retrainer import ModelRetrainer
from core.learning.retrain.model_swapper import ModelSwapper
from core.learning.retrain.retrain_history import RetrainHistory, RetrainRecord

# Feature B: 동적 가중치 시스템
from core.learning.weights.weight_safety import WeightSafety
from core.learning.weights.dynamic_weight_calculator import DynamicWeightCalculator
from core.learning.weights.weight_storage import WeightStorage
from core.learning.weights.weight_provider import HybridWeightProvider

# Feature C: 시장 레짐 탐지
from core.learning.regime.market_indicator_collector import MarketIndicatorCollector, MarketIndicators
from core.learning.regime.regime_detector import RegimeDetector
from core.daily_selection.selection_criteria import MarketCondition
from core.learning.regime.regime_strategy_mapper import RegimeStrategyMapper

# 호환성을 위한 별칭
MarketRegime = MarketCondition

# Feature D: 전체 통합
from core.learning.orchestrator.learning_orchestrator import LearningOrchestrator, LearningTaskType
from core.learning.orchestrator.pipeline_connector import PipelineConnector
from core.learning.orchestrator.learning_reporter import LearningReporter


class TestAdaptiveLearningIntegration:
    """적응형 학습 시스템 통합 테스트"""

    @pytest.fixture
    def weight_safety(self):
        return WeightSafety()

    @pytest.fixture
    def weight_calculator(self):
        return DynamicWeightCalculator()

    @pytest.fixture
    def regime_detector(self):
        return RegimeDetector()

    @pytest.fixture
    def strategy_mapper(self):
        return RegimeStrategyMapper()

    @pytest.fixture
    def pipeline_connector(self):
        return PipelineConnector()

    # =========================================
    # Feature A + B 통합: 재학습 → 가중치 업데이트
    # =========================================

    def test_retrain_updates_weights(self, weight_calculator, weight_safety):
        """재학습 후 가중치 업데이트 흐름"""
        # 1. 성과 데이터 준비
        performance_data = [
            {'stock_code': 'A001', 'pnl_ratio': 0.05, 'return': 0.05},
            {'stock_code': 'A002', 'pnl_ratio': -0.02, 'return': -0.02},
            {'stock_code': 'A003', 'pnl_ratio': 0.03, 'return': 0.03},
        ]

        factor_scores = [
            {'momentum': 80, 'value': 60, 'quality': 70, 'volume': 50,
             'volatility': 40, 'technical': 65, 'market_strength': 55},
            {'momentum': 40, 'value': 70, 'quality': 60, 'volume': 45,
             'volatility': 60, 'technical': 50, 'market_strength': 50},
            {'momentum': 70, 'value': 55, 'quality': 75, 'volume': 60,
             'volatility': 35, 'technical': 70, 'market_strength': 60},
        ]

        # 2. 가중치 계산
        result = weight_calculator.update_from_performance(
            performance_data=performance_data,
            factor_scores=factor_scores,
            reason="integration_test"
        )

        # 3. 새 가중치가 안전 제약 조건 만족 확인
        if result:
            is_valid, _ = weight_safety.validate_weights(result.new_weights)
            assert is_valid

    # =========================================
    # Feature B + C 통합: 레짐 → 가중치 조정
    # =========================================

    def test_regime_affects_weights(self, regime_detector, strategy_mapper):
        """시장 레짐에 따른 가중치 자동 조정"""
        # 상승장 지표
        bull_indicators = MarketIndicators(
            kospi_price=2800.0,
            kospi_change=0.02,
            kospi_20d_return=0.08,
            advance_decline_ratio=1.8,
            above_ma200_ratio=0.75,
            market_volatility=12.0,
            fear_greed_score=75.0
        )

        with patch.object(regime_detector._indicator_collector, 'collect', return_value=bull_indicators):
            # 1. 레짐 탐지
            regime_result = regime_detector.detect()

            # 2. 전략 매퍼에 반영
            weights = strategy_mapper.update_regime(regime_result)

            # 3. 상승장에서는 모멘텀 가중치가 높아야 함
            if regime_result.regime == MarketRegime.BULL_MARKET:
                assert weights.get('momentum', 0) >= 0.15

    def test_regime_transition_smooth(self, strategy_mapper):
        """레짐 전환 시 부드러운 가중치 변화"""
        # 초기 레짐 설정
        bull_result = MagicMock()
        bull_result.regime = MarketRegime.BULL_MARKET
        bull_result.confidence = 0.8
        bull_result.regime_changed = False

        strategy_mapper.update_regime(bull_result)
        bull_weights = strategy_mapper.get_current_weights()

        # 하락장으로 전환
        bear_result = MagicMock()
        bear_result.regime = MarketRegime.BEAR_MARKET
        bear_result.confidence = 0.7
        bear_result.regime_changed = True

        new_weights = strategy_mapper.update_regime(bear_result)

        # 변화량이 제한됨
        for factor in bull_weights:
            change = abs(new_weights.get(factor, 0) - bull_weights.get(factor, 0))
            # 부드러운 전환이므로 급격한 변화 없음
            assert change <= 0.3  # 30% 이내 변화

    # =========================================
    # Feature C + D 통합: 레짐 → 오케스트레이터
    # =========================================

    @patch('core.learning.orchestrator.learning_orchestrator.get_feedback_system')
    @patch('core.learning.orchestrator.learning_orchestrator.get_regime_detector')
    def test_orchestrator_responds_to_regime_change(
        self, mock_detector, mock_feedback
    ):
        """오케스트레이터가 레짐 변화에 반응"""
        # Mock 설정
        mock_fs = MagicMock()
        mock_fs.get_stats.return_value = {'total_count': 50}
        mock_fs.get_recent_feedback.return_value = []
        mock_feedback.return_value = mock_fs

        mock_rd = MagicMock()
        mock_rd.detect.return_value = MagicMock(
            regime=MagicMock(value='volatile'),
            confidence=0.8,
            regime_changed=True
        )
        mock_detector.return_value = mock_rd

        orchestrator = LearningOrchestrator(enable_auto_schedule=False)

        # 레짐 체크 태스크 실행
        orchestrator.enqueue_task(LearningTaskType.REGIME_CHECK)
        results = orchestrator.process_queue()

        assert len(results) == 1

    # =========================================
    # Feature D: 파이프라인 통합
    # =========================================

    def test_pipeline_connector_integration(self, pipeline_connector):
        """파이프라인 연결기 통합"""
        # 연결
        success = pipeline_connector.connect()
        assert success

        # 상태 확인
        state = pipeline_connector.get_state()
        assert state['is_connected']

        # 가중치 조회
        weights = pipeline_connector.get_current_weights()
        assert len(weights) == 7
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_end_to_end_weight_flow(self):
        """가중치 흐름 전체 테스트"""
        # 1. 안전 장치
        safety = WeightSafety()

        # 2. 초기 가중치
        initial_weights = {
            'momentum': 0.20,
            'value': 0.15,
            'quality': 0.20,
            'volume': 0.15,
            'volatility': 0.10,
            'technical': 0.15,
            'market_strength': 0.05
        }

        # 3. 정규화
        normalized = safety.normalize_weights(initial_weights)
        assert abs(sum(normalized.values()) - 1.0) < 0.001

        # 4. 변경 시도
        proposed = {
            'momentum': 0.50,  # 큰 변화
            'value': 0.10,
            'quality': 0.10,
            'volume': 0.10,
            'volatility': 0.05,
            'technical': 0.10,
            'market_strength': 0.05
        }

        # 5. 변경률 제한 적용
        limited = safety.apply_change_limit(initial_weights, proposed)

        # 6. 제한된 변경 확인
        max_change = max(
            abs(limited[f] - initial_weights[f])
            for f in initial_weights
        )
        assert max_change <= safety._constraints.max_change_rate + 0.001

    # =========================================
    # 리포팅 통합 테스트
    # =========================================

    def test_reporter_generates_metrics(self):
        """리포터 메트릭 생성"""
        reporter = LearningReporter()

        metrics = reporter.get_dashboard_metrics()

        assert metrics.timestamp is not None
        assert 0.0 <= metrics.regime_confidence <= 1.0


class TestMultiFactorScorerIntegration:
    """MultiFactorScorer 통합 테스트"""

    def test_scorer_with_weight_provider(self):
        """스코어러와 WeightProvider 통합"""
        from core.scoring.multi_factor_scorer import MultiFactorScorer
        from core.learning.weights.weight_provider import DynamicWeightProvider

        # Provider 생성
        provider = DynamicWeightProvider()

        # 스코어러에 연결
        scorer = MultiFactorScorer()
        scorer.set_weight_provider(provider)

        # 동적 가중치 활성화 확인
        status = scorer.get_weight_status()
        assert status['provider_connected']
        assert status['dynamic_enabled']

    def test_scorer_weight_update(self):
        """스코어러 가중치 업데이트"""
        from core.scoring.multi_factor_scorer import MultiFactorScorer

        scorer = MultiFactorScorer()

        new_weights = {
            'momentum': 0.25,
            'value': 0.15,
            'quality': 0.15,
            'volume': 0.15,
            'volatility': 0.10,
            'technical': 0.15,
            'market_strength': 0.05
        }

        scorer.update_weights(new_weights)

        current = scorer.get_current_weights()
        assert current['momentum'] == 0.25

    def test_scorer_calculates_with_dynamic_weights(self):
        """동적 가중치로 점수 계산"""
        from core.scoring.multi_factor_scorer import MultiFactorScorer

        scorer = MultiFactorScorer()

        # 테스트 데이터
        stock_data = [
            {
                'stock_code': 'TEST001',
                'stock_name': '테스트종목',
                'expected_return': 0.10,
                'price_attractiveness': 70.0,
                'confidence': 0.7,
                'volume_score': 60.0,
                'risk_score': 30.0,
                'technical_signals': ['buy', 'oversold'],
                'sector_momentum': 0.05
            }
        ]

        # 점수 계산
        results = scorer.calculate_multi_factor_scores(stock_data)

        assert len(results) == 1
        assert 0 <= results[0].composite_score <= 100


class TestFeedbackLoopIntegration:
    """피드백 루프 통합 테스트"""

    @patch('core.learning.feedback_system.get_feedback_system')
    def test_feedback_to_retrain_loop(self, mock_feedback_system):
        """피드백 → 재학습 루프"""
        # Mock 피드백 시스템
        mock_fs = MagicMock()
        mock_fs.get_stats.return_value = {
            'total_count': 150,
            'recent_count': 100,
            'accuracy': 0.65
        }
        mock_feedback_system.return_value = mock_fs

        # 재학습 트리거 확인
        trigger = RetrainTrigger()
        result = trigger.should_retrain(
            feedback_stats=mock_fs.get_stats(),
            model_performance={'accuracy': 0.60}
        )

        # 충분한 피드백으로 재학습 트리거
        assert result.should_retrain
        assert RetrainReason.SUFFICIENT_FEEDBACK in result.reasons
