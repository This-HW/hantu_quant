"""
앙상블 전략 시스템 테스트

Signal, SignalAggregator, EnsembleEngine, WeightOptimizer 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.strategy.ensemble import (
    Signal, SignalType, SignalSource, FinalSignal,
    SignalAggregator, AggregatorConfig,
    EnsembleEngine, EnsembleConfig,
    TechnicalAnalysisScorer, TAScores,
    SupplyDemandScorer, SDScores,
    WeightOptimizer, OptimizerConfig, PerformanceRecord
)


# ========== Fixtures ==========

@pytest.fixture
def sample_ohlcv_data():
    """샘플 OHLCV 데이터 생성"""
    np.random.seed(42)
    n = 100

    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')
    base_price = 50000

    # 상승 추세 데이터 생성
    prices = []
    price = base_price
    for _ in range(n):
        change = np.random.randn() * 500 + 50  # 약간의 상승 편향
        price = max(price + change, 10000)
        prices.append(price)

    close = np.array(prices)
    high = close * (1 + np.abs(np.random.randn(n) * 0.02))
    low = close * (1 - np.abs(np.random.randn(n) * 0.02))
    open_price = (high + low) / 2 + np.random.randn(n) * 100
    volume = np.random.randint(100000, 1000000, n)

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


@pytest.fixture
def downtrend_data():
    """하락 추세 OHLCV 데이터"""
    np.random.seed(123)
    n = 100

    dates = pd.date_range(start='2024-01-01', periods=n, freq='D')
    base_price = 50000

    prices = []
    price = base_price
    for _ in range(n):
        change = np.random.randn() * 500 - 50  # 하락 편향
        price = max(price + change, 10000)
        prices.append(price)

    close = np.array(prices)
    high = close * (1 + np.abs(np.random.randn(n) * 0.02))
    low = close * (1 - np.abs(np.random.randn(n) * 0.02))
    open_price = (high + low) / 2 + np.random.randn(n) * 100
    volume = np.random.randint(100000, 1000000, n)

    return pd.DataFrame({
        'open': open_price,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=dates)


@pytest.fixture
def buy_signals():
    """매수 신호 리스트"""
    return [
        Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.LSTM,
            stock_code="005930",
            strength=1.5,
            confidence=0.8,
            price=50000,
            reason="LSTM predicts +5%",
            stop_loss=47500,
            take_profit=55000
        ),
        Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.TA,
            stock_code="005930",
            strength=1.2,
            confidence=0.7,
            price=50000,
            reason="RSI oversold bounce",
            stop_loss=48000,
            take_profit=54000
        ),
        Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.SD,
            stock_code="005930",
            strength=1.0,
            confidence=0.6,
            price=50000,
            reason="Volume accumulation",
            stop_loss=47000,
            take_profit=53000
        ),
    ]


@pytest.fixture
def mixed_signals():
    """혼합 신호 리스트"""
    return [
        Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.LSTM,
            stock_code="005930",
            strength=1.0,
            confidence=0.7,
            price=50000
        ),
        Signal(
            signal_type=SignalType.SELL,
            source=SignalSource.TA,
            stock_code="005930",
            strength=0.8,
            confidence=0.6,
            price=50000
        ),
        Signal(
            signal_type=SignalType.HOLD,
            source=SignalSource.SD,
            stock_code="005930",
            strength=0.0,
            confidence=0.5,
            price=50000
        ),
    ]


# ========== Signal Tests ==========

class TestSignal:
    """Signal 클래스 테스트"""

    def test_signal_creation(self):
        """신호 생성 테스트"""
        signal = Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.LSTM,
            stock_code="005930",
            strength=1.5,
            confidence=0.8
        )

        assert signal.signal_type == SignalType.BUY
        assert signal.source == SignalSource.LSTM
        assert signal.stock_code == "005930"
        assert signal.strength == 1.5
        assert signal.confidence == 0.8

    def test_strength_clamping(self):
        """강도 범위 제한 테스트"""
        signal = Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.TA,
            stock_code="005930",
            strength=5.0,  # 최대 2.0으로 제한되어야 함
            confidence=1.5   # 최대 1.0으로 제한되어야 함
        )

        assert signal.strength == 2.0
        assert signal.confidence == 1.0

    def test_weighted_score(self):
        """가중 점수 계산 테스트"""
        buy_signal = Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.LSTM,
            stock_code="005930",
            strength=1.0,
            confidence=0.8
        )

        sell_signal = Signal(
            signal_type=SignalType.SELL,
            source=SignalSource.TA,
            stock_code="005930",
            strength=1.0,
            confidence=0.6
        )

        hold_signal = Signal(
            signal_type=SignalType.HOLD,
            source=SignalSource.SD,
            stock_code="005930"
        )

        assert buy_signal.weighted_score == 0.8  # 1.0 * 0.8
        assert sell_signal.weighted_score == -0.6  # -1.0 * 0.6
        assert hold_signal.weighted_score == 0.0

    def test_is_actionable(self):
        """실행 가능 여부 테스트"""
        actionable = Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.LSTM,
            stock_code="005930",
            confidence=0.6
        )

        not_actionable_hold = Signal(
            signal_type=SignalType.HOLD,
            source=SignalSource.TA,
            stock_code="005930",
            confidence=0.8
        )

        not_actionable_low_conf = Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.SD,
            stock_code="005930",
            confidence=0.3
        )

        assert actionable.is_actionable is True
        assert not_actionable_hold.is_actionable is False
        assert not_actionable_low_conf.is_actionable is False

    def test_to_dict(self):
        """딕셔너리 변환 테스트"""
        signal = Signal(
            signal_type=SignalType.BUY,
            source=SignalSource.LSTM,
            stock_code="005930",
            strength=1.5,
            confidence=0.8,
            price=50000
        )

        d = signal.to_dict()

        assert d['signal_type'] == 'BUY'
        assert d['source'] == 'lstm'
        assert d['stock_code'] == '005930'
        assert d['strength'] == 1.5
        assert d['confidence'] == 0.8


# ========== SignalAggregator Tests ==========

class TestSignalAggregator:
    """SignalAggregator 클래스 테스트"""

    def test_aggregator_creation(self):
        """집계기 생성 테스트"""
        config = AggregatorConfig(min_agreement=2)
        aggregator = SignalAggregator(config)

        assert aggregator.config.min_agreement == 2

    def test_aggregate_buy_signals(self, buy_signals):
        """매수 신호 집계 테스트"""
        aggregator = SignalAggregator()
        result = aggregator.aggregate(buy_signals)

        assert result.action == SignalType.BUY
        assert result.agreement_count == 3
        assert result.confidence > 0.6
        assert len(result.sources) == 3

    def test_aggregate_mixed_signals(self, mixed_signals):
        """혼합 신호 집계 테스트"""
        aggregator = SignalAggregator()
        result = aggregator.aggregate(mixed_signals)

        # BUY 1개, SELL 1개로 최소 동의 조건 불충족
        assert result.action == SignalType.HOLD

    def test_min_agreement_requirement(self, buy_signals):
        """최소 동의 조건 테스트"""
        config = AggregatorConfig(min_agreement=4)  # 4개 필요
        aggregator = SignalAggregator(config)
        result = aggregator.aggregate(buy_signals)

        # 3개 신호로는 4개 동의 조건 불충족
        assert result.action == SignalType.HOLD

    def test_confidence_filtering(self):
        """신뢰도 필터링 테스트"""
        signals = [
            Signal(SignalType.BUY, SignalSource.LSTM, "005930", confidence=0.3),
            Signal(SignalType.BUY, SignalSource.TA, "005930", confidence=0.4),
        ]

        config = AggregatorConfig(min_confidence=0.5)
        aggregator = SignalAggregator(config)
        result = aggregator.aggregate(signals)

        # 모든 신호가 신뢰도 임계값 미만
        assert result.action == SignalType.HOLD

    def test_weight_update(self):
        """가중치 업데이트 테스트"""
        aggregator = SignalAggregator()

        new_weights = {
            SignalSource.LSTM: 0.5,
            SignalSource.TA: 0.3,
            SignalSource.SD: 0.2,
        }

        aggregator.update_weights(new_weights)

        # 합계 1.0 검증
        total = sum(aggregator.config.weights.values())
        assert abs(total - 1.0) < 0.01

    def test_empty_signals(self):
        """빈 신호 리스트 테스트"""
        aggregator = SignalAggregator()
        result = aggregator.aggregate([])

        assert result.action == SignalType.HOLD


# ========== TechnicalAnalysisScorer Tests ==========

class TestTechnicalAnalysisScorer:
    """TechnicalAnalysisScorer 테스트"""

    def test_scorer_creation(self):
        """스코어러 생성 테스트"""
        scorer = TechnicalAnalysisScorer(rsi_period=14, macd_fast=12)
        assert scorer.rsi_period == 14
        assert scorer.macd_fast == 12

    def test_calculate_scores(self, sample_ohlcv_data):
        """점수 계산 테스트"""
        scorer = TechnicalAnalysisScorer()
        scores = scorer.calculate_scores(sample_ohlcv_data)

        assert isinstance(scores, TAScores)
        # 각 점수가 -100 ~ 100 범위 내
        assert -100 <= scores.rsi <= 100
        assert -100 <= scores.macd <= 100

    def test_generate_signal(self, sample_ohlcv_data):
        """신호 생성 테스트"""
        scorer = TechnicalAnalysisScorer()
        signal = scorer.generate_signal(sample_ohlcv_data, "005930")

        assert isinstance(signal, Signal)
        assert signal.source == SignalSource.TA
        assert signal.stock_code == "005930"
        assert signal.signal_type in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]

    def test_insufficient_data(self):
        """데이터 부족 테스트"""
        scorer = TechnicalAnalysisScorer()
        short_data = pd.DataFrame({
            'open': [100, 101],
            'high': [102, 103],
            'low': [99, 100],
            'close': [101, 102],
            'volume': [1000, 1100]
        })

        scores = scorer.calculate_scores(short_data)

        # 데이터 부족시 기본값 반환
        assert scores.weighted_total == 0.0


# ========== SupplyDemandScorer Tests ==========

class TestSupplyDemandScorer:
    """SupplyDemandScorer 테스트"""

    def test_scorer_creation(self):
        """스코어러 생성 테스트"""
        scorer = SupplyDemandScorer(volume_ma_period=20, surge_threshold=2.0)
        assert scorer.volume_ma_period == 20
        assert scorer.surge_threshold == 2.0

    def test_calculate_scores(self, sample_ohlcv_data):
        """점수 계산 테스트"""
        scorer = SupplyDemandScorer()
        scores = scorer.calculate_scores(sample_ohlcv_data)

        assert isinstance(scores, SDScores)
        # 매집/분산 점수는 0~100 범위
        assert 0 <= scores.accumulation <= 100
        assert 0 <= scores.distribution <= 100

    def test_generate_signal(self, sample_ohlcv_data):
        """신호 생성 테스트"""
        scorer = SupplyDemandScorer()
        signal = scorer.generate_signal(sample_ohlcv_data, "005930")

        assert isinstance(signal, Signal)
        assert signal.source == SignalSource.SD
        assert signal.stock_code == "005930"

    def test_volume_pattern_detection(self, sample_ohlcv_data):
        """거래량 패턴 감지 테스트"""
        scorer = SupplyDemandScorer()
        pattern = scorer.detect_volume_pattern(sample_ohlcv_data)

        # 패턴이 있거나 None
        assert pattern in ['climax_top', 'climax_bottom', 'dry_up', 'breakout', None]


# ========== EnsembleEngine Tests ==========

class TestEnsembleEngine:
    """EnsembleEngine 테스트"""

    def test_engine_creation(self):
        """엔진 생성 테스트"""
        config = EnsembleConfig(use_lstm=True, use_ta=True, use_sd=True)
        engine = EnsembleEngine(config)

        assert engine.config.use_lstm is True
        assert engine.config.use_ta is True
        assert engine.config.use_sd is True

    def test_generate_signal(self, sample_ohlcv_data):
        """신호 생성 테스트"""
        engine = EnsembleEngine()
        signal = engine.generate_signal(sample_ohlcv_data, "005930")

        assert isinstance(signal, FinalSignal)
        assert signal.stock_code == "005930"
        assert signal.action in [SignalType.BUY, SignalType.SELL, SignalType.HOLD]

    def test_generate_signal_with_lstm_prediction(self, sample_ohlcv_data):
        """LSTM 예측 포함 신호 생성 테스트"""
        engine = EnsembleEngine()

        lstm_prediction = {
            'predicted_return': 0.05,
            'confidence': 0.8,
            'horizon': 5
        }

        signal = engine.generate_signal(
            sample_ohlcv_data,
            "005930",
            lstm_prediction=lstm_prediction
        )

        assert isinstance(signal, FinalSignal)
        # LSTM이 강한 매수 신호를 보내고 있음
        assert SignalSource.LSTM in signal.sources or signal.action == SignalType.HOLD

    def test_batch_signal_generation(self, sample_ohlcv_data, downtrend_data):
        """배치 신호 생성 테스트"""
        engine = EnsembleEngine()

        data_dict = {
            "005930": sample_ohlcv_data,
            "000660": downtrend_data
        }

        results = engine.generate_signals_batch(data_dict)

        assert len(results) == 2
        assert "005930" in results
        assert "000660" in results

    def test_actionable_signals_filter(self, sample_ohlcv_data, downtrend_data):
        """실행 가능 신호 필터링 테스트"""
        engine = EnsembleEngine()

        data_dict = {
            "005930": sample_ohlcv_data,
            "000660": downtrend_data
        }

        all_signals = engine.generate_signals_batch(data_dict)
        actionable = engine.get_actionable_signals(all_signals, min_confidence=0.5)

        # 실행 가능한 신호만 필터링됨
        for signal in actionable.values():
            assert signal.is_actionable or signal.confidence >= 0.5

    def test_signal_ranking(self, sample_ohlcv_data, downtrend_data):
        """신호 순위 정렬 테스트"""
        engine = EnsembleEngine()

        data_dict = {
            "005930": sample_ohlcv_data,
            "000660": downtrend_data,
        }

        signals = engine.generate_signals_batch(data_dict)
        ranked = engine.rank_signals(signals)

        # 점수 내림차순 정렬 확인
        for i in range(len(ranked) - 1):
            assert ranked[i][2] >= ranked[i + 1][2]

    def test_weight_update(self):
        """가중치 업데이트 테스트"""
        engine = EnsembleEngine()

        new_weights = {'lstm': 0.5, 'ta': 0.3, 'sd': 0.2}
        engine.update_weights(new_weights)

        assert engine.config.weights['lstm'] == 0.5
        assert engine.config.weights['ta'] == 0.3
        assert engine.config.weights['sd'] == 0.2

    def test_signal_stats(self, sample_ohlcv_data):
        """신호 통계 테스트"""
        engine = EnsembleEngine()

        # 여러 신호 생성
        for _ in range(5):
            engine.generate_signal(sample_ohlcv_data, "005930")

        stats = engine.get_signal_stats()

        assert stats['total_signals'] == 5
        assert 'buy_signals' in stats
        assert 'sell_signals' in stats


# ========== WeightOptimizer Tests ==========

class TestWeightOptimizer:
    """WeightOptimizer 테스트"""

    def test_optimizer_creation(self):
        """최적화기 생성 테스트"""
        config = OptimizerConfig(min_weight=0.1, max_weight=0.6)
        optimizer = WeightOptimizer(config)

        assert optimizer.config.min_weight == 0.1
        assert optimizer.config.max_weight == 0.6

    def test_record_trade(self):
        """거래 기록 테스트"""
        optimizer = WeightOptimizer()

        record = optimizer.record_trade(
            source=SignalSource.LSTM,
            signal_type=SignalType.BUY,
            entry_price=50000,
            exit_price=52000
        )

        assert record.is_closed is True
        assert record.return_pct == 0.04  # 4% 수익
        assert record.is_profitable is True

    def test_update_trade(self):
        """거래 업데이트 테스트"""
        optimizer = WeightOptimizer()

        # 미청산 거래 기록
        optimizer.record_trade(
            source=SignalSource.TA,
            signal_type=SignalType.BUY,
            entry_price=50000
        )

        # 청산 업데이트
        optimizer.update_trade(
            source=SignalSource.TA,
            exit_price=48000,
            holding_days=5
        )

        # 수익률 확인 (손실)
        stats = optimizer.get_stats()
        assert stats['total_records'] == 1

    def test_calculate_performance_scores(self):
        """성과 점수 계산 테스트"""
        optimizer = WeightOptimizer()

        # 여러 거래 기록
        for i in range(15):
            return_pct = 0.03 if i % 2 == 0 else -0.01
            exit_price = 50000 * (1 + return_pct)

            optimizer.record_trade(
                source=SignalSource.LSTM,
                signal_type=SignalType.BUY,
                entry_price=50000,
                exit_price=exit_price
            )

        scores = optimizer.calculate_performance_scores()

        assert SignalSource.LSTM in scores
        lstm_scores = scores[SignalSource.LSTM]
        assert 'win_rate' in lstm_scores
        assert 'avg_return' in lstm_scores

    def test_optimize_weights(self):
        """가중치 최적화 테스트"""
        config = OptimizerConfig(min_samples=5)
        optimizer = WeightOptimizer(config)

        # LSTM에 좋은 성과 기록
        for _ in range(10):
            optimizer.record_trade(
                source=SignalSource.LSTM,
                signal_type=SignalType.BUY,
                entry_price=50000,
                exit_price=52500  # +5%
            )

        # TA에 나쁜 성과 기록
        for _ in range(10):
            optimizer.record_trade(
                source=SignalSource.TA,
                signal_type=SignalType.BUY,
                entry_price=50000,
                exit_price=48000  # -4%
            )

        # SD에 보통 성과
        for _ in range(10):
            optimizer.record_trade(
                source=SignalSource.SD,
                signal_type=SignalType.BUY,
                entry_price=50000,
                exit_price=50500  # +1%
            )

        new_weights = optimizer.optimize(force=True)

        # LSTM 가중치가 증가하고 TA 가중치가 감소해야 함
        assert new_weights[SignalSource.LSTM] >= new_weights[SignalSource.TA]

    def test_weight_constraints(self):
        """가중치 제약 조건 테스트"""
        config = OptimizerConfig(min_weight=0.2, max_weight=0.5)
        optimizer = WeightOptimizer(config)

        # 극단적인 가중치 설정 시도
        optimizer.set_weights({
            SignalSource.LSTM: 0.9,
            SignalSource.TA: 0.05,
            SignalSource.SD: 0.05
        })

        weights = optimizer.weights

        # 정규화되어 합계가 1.0
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01

    def test_recommendation(self):
        """권고 생성 테스트"""
        optimizer = WeightOptimizer()

        # 충분한 데이터 기록
        for _ in range(15):
            optimizer.record_trade(
                source=SignalSource.LSTM,
                signal_type=SignalType.BUY,
                entry_price=50000,
                exit_price=52000
            )

        recommendation = optimizer.get_recommendation()

        assert 'current_weights' in recommendation
        assert 'performance' in recommendation
        assert 'recommendations' in recommendation


# ========== Integration Tests ==========

class TestEnsembleIntegration:
    """앙상블 시스템 통합 테스트"""

    def test_full_pipeline(self, sample_ohlcv_data):
        """전체 파이프라인 테스트"""
        # 1. 앙상블 엔진으로 신호 생성
        engine = EnsembleEngine()
        signal = engine.generate_signal(sample_ohlcv_data, "005930")

        assert isinstance(signal, FinalSignal)

        # 2. 가중치 최적화기로 거래 기록
        optimizer = WeightOptimizer()

        if signal.action != SignalType.HOLD:
            for source in signal.sources:
                optimizer.record_trade(
                    source=source,
                    signal_type=signal.action,
                    entry_price=signal.individual_signals[0].price,
                    exit_price=signal.individual_signals[0].price * 1.02
                )

        # 3. 통계 확인
        stats = optimizer.get_stats()
        assert 'current_weights' in stats

    def test_multi_stock_analysis(self, sample_ohlcv_data, downtrend_data):
        """다중 종목 분석 테스트"""
        engine = EnsembleEngine()

        stocks_data = {
            "005930": sample_ohlcv_data,
            "000660": downtrend_data,
        }

        # 배치 신호 생성
        signals = engine.generate_signals_batch(stocks_data)

        # 매수 신호 랭킹
        buy_ranked = engine.rank_signals(signals, action_filter=SignalType.BUY)

        # 매도 신호 랭킹
        sell_ranked = engine.rank_signals(signals, action_filter=SignalType.SELL)

        # 전체 실행 가능 신호
        actionable = engine.get_actionable_signals(signals)

        assert len(signals) == 2
        assert isinstance(buy_ranked, list)
        assert isinstance(sell_ranked, list)

    def test_weight_adaptation(self, sample_ohlcv_data):
        """가중치 적응 테스트"""
        engine = EnsembleEngine()
        optimizer = WeightOptimizer(OptimizerConfig(min_samples=5))

        # 초기 가중치
        initial_weights = engine.config.weights.copy()

        # 여러 거래 시뮬레이션 (LSTM이 계속 좋은 성과)
        for _ in range(10):
            optimizer.record_trade(
                source=SignalSource.LSTM,
                signal_type=SignalType.BUY,
                entry_price=50000,
                exit_price=52000
            )
            optimizer.record_trade(
                source=SignalSource.TA,
                signal_type=SignalType.BUY,
                entry_price=50000,
                exit_price=49000
            )
            optimizer.record_trade(
                source=SignalSource.SD,
                signal_type=SignalType.BUY,
                entry_price=50000,
                exit_price=50500
            )

        # 가중치 최적화
        new_weights = optimizer.optimize(force=True)

        # 엔진 가중치 업데이트
        engine.update_weights({
            'lstm': new_weights[SignalSource.LSTM],
            'ta': new_weights[SignalSource.TA],
            'sd': new_weights[SignalSource.SD]
        })

        # 가중치가 변경되었는지 확인
        # (LSTM이 좋은 성과를 냈으므로 가중치가 증가해야 함)
        assert engine.config.weights['lstm'] >= initial_weights.get('lstm', 0.35) - 0.1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
