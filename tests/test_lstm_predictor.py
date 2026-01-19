"""
LSTM 가격 예측 모델 테스트 (P3-1)

테스트 항목:
1. 데이터 클래스
2. 데이터셋 처리
3. 모델 구조 (PyTorch 있을 때만)
4. 예측 로직
5. 신호 생성
"""

import pytest
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import tempfile

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.learning.models.lstm_predictor import (
    LSTMConfig,
    PricePrediction,
    StockDataset,
    create_sample_data,
    TORCH_AVAILABLE,
)

# PyTorch 있을 때만 import
if TORCH_AVAILABLE:
    from core.learning.models.lstm_predictor import (
        LSTMPredictor,
        LSTMModel,
        TorchStockDataset,
    )
    import torch


class TestLSTMConfig:
    """LSTMConfig 테스트"""

    def test_default_values(self):
        """기본값 확인"""
        config = LSTMConfig()

        assert config.input_size == 5
        assert config.hidden_size == 128
        assert config.num_layers == 2
        assert config.output_size == 1
        assert config.dropout == 0.2
        assert config.sequence_length == 60
        assert config.batch_size == 32
        assert config.learning_rate == 0.001
        assert config.epochs == 100
        assert config.early_stopping_patience == 10

    def test_custom_values(self):
        """사용자 설정값"""
        config = LSTMConfig(
            hidden_size=256,
            num_layers=3,
            sequence_length=30
        )

        assert config.hidden_size == 256
        assert config.num_layers == 3
        assert config.sequence_length == 30


class TestPricePrediction:
    """PricePrediction 테스트"""

    def test_create_prediction(self):
        """예측 결과 생성"""
        pred = PricePrediction(
            stock_code="005930",
            current_price=70000.0,
            predicted_price=72000.0,
            change_rate=2.86,
            signal="buy",
            confidence=0.8
        )

        assert pred.stock_code == "005930"
        assert pred.current_price == 70000.0
        assert pred.predicted_price == 72000.0
        assert pred.signal == "buy"
        assert pred.confidence == 0.8

    def test_to_dict(self):
        """딕셔너리 변환"""
        pred = PricePrediction(
            stock_code="005930",
            current_price=70000.0,
            predicted_price=72000.0,
            change_rate=2.86,
            signal="buy",
            confidence=0.8
        )

        d = pred.to_dict()

        assert d["stock_code"] == "005930"
        assert d["signal"] == "buy"
        assert "prediction_date" in d

    def test_has_prediction_date(self):
        """예측 일자 자동 생성"""
        pred = PricePrediction(
            stock_code="005930",
            current_price=70000.0,
            predicted_price=72000.0,
            change_rate=2.86,
            signal="buy",
            confidence=0.8
        )

        assert pred.prediction_date is not None
        assert "T" in pred.prediction_date  # ISO 형식


class TestStockDataset:
    """StockDataset 테스트"""

    def test_create_dataset(self):
        """데이터셋 생성"""
        data = create_sample_data(days=100)
        dataset = StockDataset(data, sequence_length=20)

        assert len(dataset) == 80  # 100 - 20

    def test_normalization(self):
        """데이터 정규화"""
        data = create_sample_data(days=100)
        dataset = StockDataset(data, sequence_length=20)

        # 정규화된 값은 0-1 범위
        assert dataset.data['close'].min() >= 0
        assert dataset.data['close'].max() <= 1

    def test_scaler_params(self):
        """스케일러 파라미터 저장"""
        data = create_sample_data(days=100)
        dataset = StockDataset(data, sequence_length=20)

        assert 'close' in dataset.scaler_params
        assert 'min' in dataset.scaler_params['close']
        assert 'max' in dataset.scaler_params['close']

    def test_denormalize(self):
        """역정규화"""
        data = create_sample_data(days=100)
        original_close = data['close'].iloc[-1]

        dataset = StockDataset(data, sequence_length=20)
        normalized = dataset.data['close'].iloc[-1]
        denormalized = dataset.denormalize_price(normalized)

        assert abs(denormalized - original_close) < 1  # 오차 1원 이내

    def test_getitem(self):
        """데이터 항목 조회"""
        data = create_sample_data(days=100)
        dataset = StockDataset(data, sequence_length=20)

        features, target = dataset[0]

        assert features.shape == (20, 5)  # (sequence_length, features)
        assert isinstance(target, np.floating)


class TestCreateSampleData:
    """샘플 데이터 생성 테스트"""

    def test_sample_data_shape(self):
        """데이터 형태"""
        data = create_sample_data(days=500)

        assert len(data) == 500
        assert 'open' in data.columns
        assert 'high' in data.columns
        assert 'low' in data.columns
        assert 'close' in data.columns
        assert 'volume' in data.columns

    def test_sample_data_values(self):
        """데이터 값 범위"""
        data = create_sample_data(days=100)

        assert data['close'].min() > 0
        assert data['volume'].min() >= 100000

    def test_sample_data_reproducible(self):
        """재현 가능성 (seed 고정)"""
        data1 = create_sample_data(days=100)
        data2 = create_sample_data(days=100)

        # 인덱스는 datetime.now() 사용으로 다를 수 있음
        # 수치 데이터만 비교
        pd.testing.assert_frame_equal(
            data1.reset_index(drop=True),
            data2.reset_index(drop=True)
        )


class TestSignalThresholds:
    """신호 임계값 테스트"""

    def test_buy_signal_threshold(self):
        """매수 신호 임계값"""
        # +2% 이상이면 buy
        change_rate = 0.025
        threshold = 0.02

        if change_rate > threshold:
            signal = 'buy'
        else:
            signal = 'hold'

        assert signal == 'buy'

    def test_sell_signal_threshold(self):
        """매도 신호 임계값"""
        # -2% 이하면 sell
        change_rate = -0.03
        threshold = -0.02

        if change_rate < threshold:
            signal = 'sell'
        else:
            signal = 'hold'

        assert signal == 'sell'

    def test_hold_signal(self):
        """홀드 신호"""
        # -2% ~ +2% 사이면 hold
        change_rate = 0.01

        if change_rate > 0.02:
            signal = 'buy'
        elif change_rate < -0.02:
            signal = 'sell'
        else:
            signal = 'hold'

        assert signal == 'hold'


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
class TestLSTMModel:
    """LSTMModel 테스트 (PyTorch 필요)"""

    def test_model_creation(self):
        """모델 생성"""
        config = LSTMConfig()
        model = LSTMModel(config)

        assert model is not None
        assert hasattr(model, 'lstm')
        assert hasattr(model, 'fc')

    def test_model_forward(self):
        """순전파"""
        config = LSTMConfig(
            sequence_length=20,
            batch_size=4
        )
        model = LSTMModel(config)

        # 입력 텐서 (batch, sequence, features)
        x = torch.randn(4, 20, 5)
        output = model(x)

        assert output.shape == (4, 1)  # (batch, output_size)

    def test_model_parameters(self):
        """모델 파라미터"""
        config = LSTMConfig()
        model = LSTMModel(config)

        param_count = sum(p.numel() for p in model.parameters())
        assert param_count > 0


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
class TestTorchStockDataset:
    """TorchStockDataset 테스트"""

    def test_torch_dataset(self):
        """Torch 데이터셋 래퍼"""
        data = create_sample_data(days=100)
        base_dataset = StockDataset(data, sequence_length=20)
        torch_dataset = TorchStockDataset(base_dataset)

        assert len(torch_dataset) == len(base_dataset)

    def test_torch_dataset_item(self):
        """Torch 데이터셋 항목"""
        data = create_sample_data(days=100)
        base_dataset = StockDataset(data, sequence_length=20)
        torch_dataset = TorchStockDataset(base_dataset)

        features, target = torch_dataset[0]

        assert isinstance(features, torch.Tensor)
        assert isinstance(target, torch.Tensor)
        assert features.shape == (20, 5)
        assert target.shape == (1,)


@pytest.mark.skipif(not TORCH_AVAILABLE, reason="PyTorch not installed")
class TestLSTMPredictor:
    """LSTMPredictor 테스트"""

    def test_predictor_init(self):
        """예측기 초기화"""
        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = LSTMPredictor(model_dir=tmpdir)

            assert predictor.config is not None
            assert predictor.model is None

    def test_predictor_custom_config(self):
        """사용자 설정"""
        config = LSTMConfig(hidden_size=64, num_layers=1)

        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = LSTMPredictor(config=config, model_dir=tmpdir)

            assert predictor.config.hidden_size == 64
            assert predictor.config.num_layers == 1

    def test_train_minimal(self):
        """최소 학습 테스트"""
        config = LSTMConfig(
            hidden_size=32,
            num_layers=1,
            sequence_length=10,
            epochs=2,
            batch_size=8
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = LSTMPredictor(config=config, model_dir=tmpdir)

            data = create_sample_data(days=100)
            history = predictor.train(data, validation_split=0.2, verbose=False)

            assert 'train_loss' in history
            assert 'val_loss' in history
            assert len(history['train_loss']) > 0

    def test_predict_after_train(self):
        """학습 후 예측"""
        config = LSTMConfig(
            hidden_size=32,
            num_layers=1,
            sequence_length=10,
            epochs=2,
            batch_size=8
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = LSTMPredictor(config=config, model_dir=tmpdir)

            data = create_sample_data(days=100)
            predictor.train(data, verbose=False)

            prediction = predictor.predict(data, stock_code="005930")

            assert isinstance(prediction, PricePrediction)
            assert prediction.stock_code == "005930"
            assert prediction.signal in ['buy', 'hold', 'sell']

    def test_predict_without_train(self):
        """학습 없이 예측 시 에러"""
        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = LSTMPredictor(model_dir=tmpdir)
            data = create_sample_data(days=100)

            with pytest.raises(RuntimeError, match="모델이 학습되지 않았습니다"):
                predictor.predict(data)

    def test_predict_insufficient_data(self):
        """데이터 부족 시 에러"""
        config = LSTMConfig(sequence_length=60)

        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = LSTMPredictor(config=config, model_dir=tmpdir)

            # 학습 (충분한 데이터)
            data = create_sample_data(days=200)
            predictor.train(data, verbose=False)

            # 예측 (부족한 데이터)
            short_data = create_sample_data(days=30)

            with pytest.raises(ValueError, match="데이터가 부족합니다"):
                predictor.predict(short_data)

    def test_save_and_load(self):
        """모델 저장 및 로드"""
        config = LSTMConfig(
            hidden_size=32,
            num_layers=1,
            sequence_length=10,
            epochs=2,
            batch_size=8
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # 학습 및 저장
            predictor1 = LSTMPredictor(config=config, model_dir=tmpdir)
            data = create_sample_data(days=100)
            predictor1.train(data, verbose=False)

            model_path = predictor1.save()
            assert Path(model_path).exists()

            # 로드
            predictor2 = LSTMPredictor(model_dir=tmpdir)
            predictor2.load(model_path)

            # 예측 비교
            pred1 = predictor1.predict(data, "005930")
            pred2 = predictor2.predict(data, "005930")

            assert abs(pred1.predicted_price - pred2.predicted_price) < 1

    def test_evaluate(self):
        """모델 평가"""
        config = LSTMConfig(
            hidden_size=32,
            num_layers=1,
            sequence_length=10,
            epochs=2,
            batch_size=8
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = LSTMPredictor(config=config, model_dir=tmpdir)

            data = create_sample_data(days=100)
            predictor.train(data, verbose=False)

            metrics = predictor.evaluate(data, test_size=10)

            assert 'mae' in metrics
            assert 'rmse' in metrics
            assert 'direction_accuracy' in metrics
            assert metrics['test_size'] == 10

    def test_predict_batch(self):
        """배치 예측"""
        config = LSTMConfig(
            hidden_size=32,
            num_layers=1,
            sequence_length=10,
            epochs=2,
            batch_size=8
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            predictor = LSTMPredictor(config=config, model_dir=tmpdir)

            data1 = create_sample_data(days=100)
            data2 = create_sample_data(days=100)
            predictor.train(data1, verbose=False)

            results = predictor.predict_batch({
                "005930": data1,
                "000660": data2
            })

            assert "005930" in results
            assert "000660" in results


class TestTorchAvailability:
    """PyTorch 가용성 테스트"""

    def test_torch_available_flag(self):
        """TORCH_AVAILABLE 플래그"""
        assert isinstance(TORCH_AVAILABLE, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
