"""
LSTM 가격 예측 모델 (P3-1)

기능:
- PyTorch 기반 LSTM 모델
- 60일 시퀀스 → 다음날 종가 예측
- 학습/추론 파이프라인
- 예측 기반 매매 신호 생성

요구사항:
- torch>=2.0.0
- 최소 3년 일봉 데이터 (학습용)
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import json

import numpy as np
import pandas as pd

# PyTorch는 선택적 의존성
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None

logger = logging.getLogger(__name__)


@dataclass
class LSTMConfig:
    """LSTM 모델 설정"""
    input_size: int = 5  # OHLCV 특성
    hidden_size: int = 128
    num_layers: int = 2
    output_size: int = 1  # 다음날 종가
    dropout: float = 0.2
    sequence_length: int = 60  # 60일 시퀀스
    batch_size: int = 32
    learning_rate: float = 0.001
    epochs: int = 100
    early_stopping_patience: int = 10


@dataclass
class PricePrediction:
    """가격 예측 결과"""
    stock_code: str
    current_price: float
    predicted_price: float
    change_rate: float  # 예측 변동률 (%)
    signal: str  # 'buy', 'hold', 'sell'
    confidence: float  # 신뢰도 (0-1)
    prediction_date: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StockDataset:
    """주식 시퀀스 데이터셋 (PyTorch Dataset 호환)"""

    def __init__(
        self,
        data: pd.DataFrame,
        sequence_length: int = 60,
        target_col: str = 'close'
    ):
        """초기화

        Args:
            data: OHLCV 데이터프레임
            sequence_length: 시퀀스 길이
            target_col: 예측 대상 컬럼
        """
        self.sequence_length = sequence_length
        self.target_col = target_col

        # 데이터 정규화
        self.data, self.scaler_params = self._normalize(data)
        self.features = ['open', 'high', 'low', 'close', 'volume']

    def _normalize(self, data: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """Min-Max 정규화"""
        scaler_params = {}
        normalized = data.copy()

        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in normalized.columns:
                min_val = normalized[col].min()
                max_val = normalized[col].max()
                if max_val > min_val:
                    normalized[col] = (normalized[col] - min_val) / (max_val - min_val)
                else:
                    normalized[col] = 0.0
                scaler_params[col] = {'min': min_val, 'max': max_val}

        return normalized, scaler_params

    def denormalize_price(self, normalized_price: float) -> float:
        """정규화된 가격을 원래 스케일로 변환"""
        params = self.scaler_params.get('close', {'min': 0, 'max': 1})
        return normalized_price * (params['max'] - params['min']) + params['min']

    def __len__(self) -> int:
        return len(self.data) - self.sequence_length

    def __getitem__(self, idx: int) -> Tuple[np.ndarray, float]:
        """시퀀스와 타겟 반환"""
        seq_data = self.data.iloc[idx:idx + self.sequence_length]
        target = self.data.iloc[idx + self.sequence_length][self.target_col]

        # 특성 추출
        features = seq_data[self.features].values
        return features.astype(np.float32), np.float32(target)


def create_sample_data(days: int = 500) -> pd.DataFrame:
    """샘플 OHLCV 데이터 생성 (테스트용)"""
    np.random.seed(42)

    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')

    # 랜덤 워크 가격 생성
    price = 50000
    prices = []
    for _ in range(days):
        price *= (1 + np.random.randn() * 0.02)
        prices.append(price)

    prices = np.array(prices)

    return pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.randn(days) * 0.005),
        'high': prices * (1 + np.abs(np.random.randn(days)) * 0.01),
        'low': prices * (1 - np.abs(np.random.randn(days)) * 0.01),
        'close': prices,
        'volume': np.random.randint(100000, 10000000, days)
    }).set_index('date')


# PyTorch 의존 클래스들 (torch 설치 시에만 정의)
if TORCH_AVAILABLE:
    class TorchStockDataset(Dataset):
        """PyTorch Dataset 래퍼"""

        def __init__(self, stock_dataset: StockDataset):
            self.dataset = stock_dataset

        def __len__(self):
            return len(self.dataset)

        def __getitem__(self, idx):
            features, target = self.dataset[idx]
            return torch.FloatTensor(features), torch.FloatTensor([target])


    class LSTMModel(nn.Module):
        """LSTM 가격 예측 모델"""

        def __init__(self, config: LSTMConfig):
            super().__init__()
            self.config = config

            self.lstm = nn.LSTM(
                input_size=config.input_size,
                hidden_size=config.hidden_size,
                num_layers=config.num_layers,
                batch_first=True,
                dropout=config.dropout if config.num_layers > 1 else 0
            )

            self.fc = nn.Sequential(
                nn.Linear(config.hidden_size, 64),
                nn.ReLU(),
                nn.Dropout(config.dropout),
                nn.Linear(64, config.output_size)
            )

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            # x shape: (batch, sequence_length, input_size)
            lstm_out, _ = self.lstm(x)

            # 마지막 타임스텝의 출력만 사용
            last_out = lstm_out[:, -1, :]

            # 가격 예측
            return self.fc(last_out)


    class LSTMPredictor:
        """LSTM 가격 예측기

        Usage:
            predictor = LSTMPredictor()

            # 학습
            history = predictor.train(df, epochs=100)

            # 예측
            prediction = predictor.predict(df_recent)

            # 모델 저장/로드
            predictor.save('models/lstm_005930.pt')
            predictor.load('models/lstm_005930.pt')
        """

        def __init__(
            self,
            config: Optional[LSTMConfig] = None,
            model_dir: str = "data/models/lstm"
        ):
            """초기화

            Args:
                config: LSTM 설정
                model_dir: 모델 저장 디렉토리
            """
            self.config = config or LSTMConfig()
            self.model_dir = Path(model_dir)
            self.model_dir.mkdir(parents=True, exist_ok=True)

            self.model: Optional[LSTMModel] = None
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.scaler_params: Dict = {}

            # 시그널 임계값
            self.signal_thresholds = {
                'buy': 0.02,   # +2% 이상 상승 예측
                'sell': -0.02  # -2% 이상 하락 예측
            }

            logger.info(f"LSTMPredictor 초기화: device={self.device}")

        def _create_model(self) -> LSTMModel:
            """모델 생성"""
            model = LSTMModel(self.config)
            return model.to(self.device)

        def train(
            self,
            data: pd.DataFrame,
            validation_split: float = 0.2,
            verbose: bool = True
        ) -> Dict[str, List[float]]:
            """모델 학습

            Args:
                data: OHLCV 데이터프레임 (columns: open, high, low, close, volume)
                validation_split: 검증 데이터 비율
                verbose: 학습 로그 출력

            Returns:
                학습 히스토리 (train_loss, val_loss)
            """
            # 데이터셋 생성
            dataset = StockDataset(data, self.config.sequence_length)
            self.scaler_params = dataset.scaler_params

            # 학습/검증 분할
            total_len = len(dataset)
            val_len = int(total_len * validation_split)
            train_len = total_len - val_len

            train_data = TorchStockDataset(dataset)

            # 인덱스 기반 분할
            train_indices = list(range(train_len))
            val_indices = list(range(train_len, total_len))

            train_subset = torch.utils.data.Subset(train_data, train_indices)
            val_subset = torch.utils.data.Subset(train_data, val_indices)

            train_loader = DataLoader(
                train_subset,
                batch_size=self.config.batch_size,
                shuffle=True
            )
            val_loader = DataLoader(
                val_subset,
                batch_size=self.config.batch_size,
                shuffle=False
            )

            # 모델 생성
            self.model = self._create_model()

            # 손실 함수 및 옵티마이저
            criterion = nn.MSELoss()
            optimizer = torch.optim.Adam(
                self.model.parameters(),
                lr=self.config.learning_rate
            )

            # 학습 히스토리
            history = {
                'train_loss': [],
                'val_loss': []
            }

            # Early Stopping
            best_val_loss = float('inf')
            patience_counter = 0

            logger.info(f"학습 시작: {train_len} train, {val_len} val samples")

            for epoch in range(self.config.epochs):
                # 학습
                self.model.train()
                train_loss = 0.0
                for batch_x, batch_y in train_loader:
                    batch_x = batch_x.to(self.device)
                    batch_y = batch_y.to(self.device)

                    optimizer.zero_grad()
                    outputs = self.model(batch_x)
                    loss = criterion(outputs, batch_y)
                    loss.backward()
                    optimizer.step()

                    train_loss += loss.item()

                train_loss /= len(train_loader)
                history['train_loss'].append(train_loss)

                # 검증
                self.model.eval()
                val_loss = 0.0
                with torch.no_grad():
                    for batch_x, batch_y in val_loader:
                        batch_x = batch_x.to(self.device)
                        batch_y = batch_y.to(self.device)
                        outputs = self.model(batch_x)
                        loss = criterion(outputs, batch_y)
                        val_loss += loss.item()

                val_loss /= len(val_loader)
                history['val_loss'].append(val_loss)

                if verbose and (epoch + 1) % 10 == 0:
                    logger.info(
                        f"Epoch {epoch+1}/{self.config.epochs}: "
                        f"train_loss={train_loss:.6f}, val_loss={val_loss:.6f}"
                    )

                # Early Stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= self.config.early_stopping_patience:
                        logger.info(f"Early stopping at epoch {epoch+1}")
                        break

            logger.info(f"학습 완료: best_val_loss={best_val_loss:.6f}")
            return history

        def predict(
            self,
            data: pd.DataFrame,
            stock_code: str = "000000"
        ) -> PricePrediction:
            """가격 예측

            Args:
                data: 최근 OHLCV 데이터 (최소 sequence_length 행)
                stock_code: 종목코드

            Returns:
                PricePrediction: 예측 결과
            """
            if self.model is None:
                raise RuntimeError("모델이 학습되지 않았습니다. train()을 먼저 호출하세요.")

            if len(data) < self.config.sequence_length:
                raise ValueError(
                    f"데이터가 부족합니다. 최소 {self.config.sequence_length}행 필요"
                )

            # 데이터 준비
            dataset = StockDataset(data, self.config.sequence_length)
            # 마지막 시퀀스 사용
            last_idx = len(dataset) - 1
            features, _ = dataset[last_idx]

            # 예측
            self.model.eval()
            with torch.no_grad():
                x = torch.FloatTensor(features).unsqueeze(0).to(self.device)
                pred_normalized = self.model(x).item()

            # 역정규화
            predicted_price = dataset.denormalize_price(pred_normalized)
            current_price = data['close'].iloc[-1]

            # 변동률 계산
            change_rate = (predicted_price - current_price) / current_price

            # 신호 생성
            if change_rate > self.signal_thresholds['buy']:
                signal = 'buy'
                confidence = min(change_rate / 0.05, 1.0)  # 5% 기준 신뢰도
            elif change_rate < self.signal_thresholds['sell']:
                signal = 'sell'
                confidence = min(abs(change_rate) / 0.05, 1.0)
            else:
                signal = 'hold'
                confidence = 1.0 - abs(change_rate) / 0.02

            return PricePrediction(
                stock_code=stock_code,
                current_price=current_price,
                predicted_price=predicted_price,
                change_rate=change_rate * 100,
                signal=signal,
                confidence=max(0, min(1, confidence))
            )

        def predict_batch(
            self,
            data_dict: Dict[str, pd.DataFrame]
        ) -> Dict[str, PricePrediction]:
            """여러 종목 배치 예측

            Args:
                data_dict: {종목코드: OHLCV 데이터프레임}

            Returns:
                {종목코드: PricePrediction}
            """
            results = {}
            for stock_code, data in data_dict.items():
                try:
                    results[stock_code] = self.predict(data, stock_code)
                except Exception as e:
                    logger.warning(f"예측 실패 ({stock_code}): {e}")
            return results

        def save(self, filepath: Optional[str] = None) -> str:
            """모델 저장

            Args:
                filepath: 저장 경로 (None이면 기본 경로)

            Returns:
                저장된 파일 경로
            """
            if self.model is None:
                raise RuntimeError("저장할 모델이 없습니다.")

            if filepath is None:
                filepath = self.model_dir / f"lstm_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pt"
            else:
                filepath = Path(filepath)

            torch.save({
                'model_state_dict': self.model.state_dict(),
                'config': asdict(self.config),
                'scaler_params': self.scaler_params
            }, filepath)

            logger.info(f"모델 저장: {filepath}")
            return str(filepath)

        def load(self, filepath: str) -> None:
            """모델 로드

            Args:
                filepath: 모델 파일 경로
            """
            checkpoint = torch.load(filepath, map_location=self.device)

            # 설정 복원
            self.config = LSTMConfig(**checkpoint['config'])
            self.scaler_params = checkpoint['scaler_params']

            # 모델 복원
            self.model = self._create_model()
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.eval()

            logger.info(f"모델 로드: {filepath}")

        def evaluate(
            self,
            data: pd.DataFrame,
            test_size: int = 30
        ) -> Dict[str, float]:
            """모델 평가

            Args:
                data: 전체 OHLCV 데이터
                test_size: 테스트 기간 (일)

            Returns:
                평가 메트릭 (MAE, RMSE, 방향 정확도)
            """
            if self.model is None:
                raise RuntimeError("모델이 학습되지 않았습니다.")

            # 테스트 데이터 분리
            train_data = data.iloc[:-test_size]
            test_data = data.iloc[-test_size-self.config.sequence_length:]

            dataset = StockDataset(test_data, self.config.sequence_length)

            predictions = []
            actuals = []

            self.model.eval()
            with torch.no_grad():
                for i in range(len(dataset)):
                    features, actual = dataset[i]
                    x = torch.FloatTensor(features).unsqueeze(0).to(self.device)
                    pred = self.model(x).item()

                    predictions.append(dataset.denormalize_price(pred))
                    actuals.append(dataset.denormalize_price(actual))

            predictions = np.array(predictions)
            actuals = np.array(actuals)

            # 메트릭 계산
            mae = np.mean(np.abs(predictions - actuals))
            rmse = np.sqrt(np.mean((predictions - actuals) ** 2))

            # 방향 정확도
            pred_direction = np.sign(predictions[1:] - predictions[:-1])
            actual_direction = np.sign(actuals[1:] - actuals[:-1])
            direction_accuracy = np.mean(pred_direction == actual_direction)

            return {
                'mae': float(mae),
                'rmse': float(rmse),
                'direction_accuracy': float(direction_accuracy),
                'test_size': test_size
            }

else:
    # PyTorch가 없을 때 더미 클래스 정의
    class TorchStockDataset:
        """TorchStockDataset 더미 (PyTorch 필요)"""
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch가 설치되어 있지 않습니다.")

    class LSTMModel:
        """LSTMModel 더미 (PyTorch 필요)"""
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch가 설치되어 있지 않습니다.")

    class LSTMPredictor:
        """LSTMPredictor 더미 (PyTorch 필요)"""
        def __init__(self, *args, **kwargs):
            raise ImportError("PyTorch가 설치되어 있지 않습니다.")
