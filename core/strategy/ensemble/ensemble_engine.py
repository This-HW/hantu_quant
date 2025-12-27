"""
앙상블 엔진 모듈

LSTM, 기술적 분석, 수급 분석 신호를 통합하여
최종 거래 결정을 생성합니다.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import logging

from .signal import Signal, SignalType, SignalSource, FinalSignal
from .signal_aggregator import SignalAggregator, AggregatorConfig
from .ta_scorer import TechnicalAnalysisScorer
from .supply_demand_scorer import SupplyDemandScorer

logger = logging.getLogger(__name__)


@dataclass
class EnsembleConfig:
    """앙상블 엔진 설정"""
    # 전략별 활성화 여부
    use_lstm: bool = True
    use_ta: bool = True
    use_sd: bool = True

    # 전략별 가중치
    weights: Dict[str, float] = field(default_factory=lambda: {
        'lstm': 0.35,
        'ta': 0.35,
        'sd': 0.30,
    })

    # 집계 설정
    min_agreement: int = 2
    min_confidence: float = 0.5

    # TA 설정
    ta_rsi_period: int = 14
    ta_macd_fast: int = 12
    ta_macd_slow: int = 26
    ta_bb_period: int = 20

    # SD 설정
    sd_volume_ma: int = 20
    sd_surge_threshold: float = 2.0


class LSTMSignalGenerator:
    """
    LSTM 신호 생성기

    기존 LSTM 모델의 예측을 신호로 변환합니다.
    """

    def __init__(self, model=None, confidence_threshold: float = 0.6):
        """
        Args:
            model: 학습된 LSTM 모델 (None일 경우 더미 신호 생성)
            confidence_threshold: 신뢰도 임계값
        """
        self.model = model
        self.confidence_threshold = confidence_threshold

    def generate_signal(
        self,
        data: pd.DataFrame,
        stock_code: str,
        prediction: Optional[Dict[str, Any]] = None
    ) -> Signal:
        """
        LSTM 예측을 기반으로 신호 생성

        Args:
            data: OHLCV 데이터
            stock_code: 종목 코드
            prediction: 외부 LSTM 예측 결과 (선택적)

        Returns:
            Signal: LSTM 기반 신호
        """
        current_price = data['close'].iloc[-1]

        # 외부 예측 결과가 있으면 사용
        if prediction:
            return self._from_prediction(prediction, stock_code, current_price)

        # 모델이 있으면 직접 예측
        if self.model is not None:
            return self._predict_with_model(data, stock_code, current_price)

        # 모델 없으면 중립 신호
        return Signal(
            signal_type=SignalType.HOLD,
            source=SignalSource.LSTM,
            stock_code=stock_code,
            strength=0.0,
            confidence=0.0,
            price=current_price,
            reason="LSTM model not available"
        )

    def _from_prediction(
        self,
        prediction: Dict[str, Any],
        stock_code: str,
        current_price: float
    ) -> Signal:
        """외부 예측 결과를 신호로 변환"""
        # 예측 결과 구조:
        # {
        #     'predicted_return': float,  # 예측 수익률
        #     'confidence': float,        # 예측 신뢰도
        #     'horizon': int,             # 예측 기간 (일)
        # }
        predicted_return = prediction.get('predicted_return', 0.0)
        confidence = prediction.get('confidence', 0.5)
        horizon = prediction.get('horizon', 5)

        # 예측 수익률에 따른 신호 결정
        if predicted_return > 0.03 and confidence >= self.confidence_threshold:
            signal_type = SignalType.BUY
            strength = min(2.0, predicted_return * 20)  # 5% -> strength 1.0
            stop_loss = current_price * 0.95
            take_profit = current_price * (1 + predicted_return)
            reason = f"LSTM predicts +{predicted_return:.1%} in {horizon} days"

        elif predicted_return < -0.03 and confidence >= self.confidence_threshold:
            signal_type = SignalType.SELL
            strength = min(2.0, abs(predicted_return) * 20)
            stop_loss = current_price * 1.05
            take_profit = current_price * (1 + predicted_return)
            reason = f"LSTM predicts {predicted_return:.1%} in {horizon} days"

        else:
            signal_type = SignalType.HOLD
            strength = 0.0
            stop_loss = None
            take_profit = None
            reason = f"LSTM prediction neutral ({predicted_return:+.1%})"

        return Signal(
            signal_type=signal_type,
            source=SignalSource.LSTM,
            stock_code=stock_code,
            strength=strength,
            confidence=confidence,
            price=current_price,
            reason=reason,
            stop_loss=stop_loss,
            take_profit=take_profit,
            metadata={'prediction': prediction}
        )

    def _predict_with_model(
        self,
        data: pd.DataFrame,
        stock_code: str,
        current_price: float
    ) -> Signal:
        """모델로 직접 예측"""
        try:
            # 피처 준비 및 예측 (실제 구현은 모델 구조에 따라 달라짐)
            features = self._prepare_features(data)
            predicted_return, confidence = self.model.predict(features)

            return self._from_prediction(
                {
                    'predicted_return': predicted_return,
                    'confidence': confidence,
                    'horizon': 5
                },
                stock_code,
                current_price
            )
        except Exception as e:
            logger.error(f"LSTM prediction error: {e}")
            return Signal(
                signal_type=SignalType.HOLD,
                source=SignalSource.LSTM,
                stock_code=stock_code,
                strength=0.0,
                confidence=0.0,
                price=current_price,
                reason=f"LSTM prediction error: {str(e)}"
            )

    def _prepare_features(self, data: pd.DataFrame) -> np.ndarray:
        """LSTM 입력 피처 준비"""
        # 실제 구현은 학습된 모델의 피처에 맞춰야 함
        # 기본적인 피처 예시
        features = []

        # 수익률
        returns = data['close'].pct_change().dropna()
        features.extend(returns.tail(20).values)

        # 정규화된 거래량
        volume_norm = data['volume'] / data['volume'].rolling(20).mean()
        features.extend(volume_norm.tail(20).values)

        # 가격 위치 (20일 범위 대비)
        high_20 = data['high'].rolling(20).max()
        low_20 = data['low'].rolling(20).min()
        price_position = (data['close'] - low_20) / (high_20 - low_20 + 1e-10)
        features.extend(price_position.tail(20).values)

        return np.array(features).reshape(1, -1)


class EnsembleEngine:
    """
    앙상블 엔진

    여러 전략의 신호를 통합하여 최종 거래 결정을 생성합니다.
    """

    def __init__(
        self,
        config: Optional[EnsembleConfig] = None,
        lstm_model=None
    ):
        """
        Args:
            config: 앙상블 설정
            lstm_model: LSTM 모델 (선택적)
        """
        self.config = config or EnsembleConfig()

        # 신호 생성기 초기화
        self.lstm_generator = LSTMSignalGenerator(
            model=lstm_model,
            confidence_threshold=self.config.min_confidence
        )

        self.ta_scorer = TechnicalAnalysisScorer(
            rsi_period=self.config.ta_rsi_period,
            macd_fast=self.config.ta_macd_fast,
            macd_slow=self.config.ta_macd_slow,
            bb_period=self.config.ta_bb_period
        )

        self.sd_scorer = SupplyDemandScorer(
            volume_ma_period=self.config.sd_volume_ma,
            surge_threshold=self.config.sd_surge_threshold
        )

        # 신호 집계기 초기화
        aggregator_config = AggregatorConfig(
            weights={
                SignalSource.LSTM: self.config.weights.get('lstm', 0.35),
                SignalSource.TA: self.config.weights.get('ta', 0.35),
                SignalSource.SD: self.config.weights.get('sd', 0.30),
            },
            min_agreement=self.config.min_agreement,
            min_confidence=self.config.min_confidence
        )
        self.aggregator = SignalAggregator(aggregator_config)

        # 성과 추적
        self._signal_history: List[Dict[str, Any]] = []

    def generate_signal(
        self,
        data: pd.DataFrame,
        stock_code: str,
        lstm_prediction: Optional[Dict[str, Any]] = None
    ) -> FinalSignal:
        """
        앙상블 신호 생성

        Args:
            data: OHLCV 데이터
            stock_code: 종목 코드
            lstm_prediction: 외부 LSTM 예측 결과 (선택적)

        Returns:
            FinalSignal: 최종 앙상블 신호
        """
        signals = []

        # LSTM 신호
        if self.config.use_lstm:
            lstm_signal = self.lstm_generator.generate_signal(
                data, stock_code, lstm_prediction
            )
            signals.append(lstm_signal)
            logger.debug(f"LSTM Signal: {lstm_signal.signal_type.name}, "
                        f"conf={lstm_signal.confidence:.2f}")

        # TA 신호
        if self.config.use_ta:
            ta_signal = self.ta_scorer.generate_signal(data, stock_code)
            signals.append(ta_signal)
            logger.debug(f"TA Signal: {ta_signal.signal_type.name}, "
                        f"conf={ta_signal.confidence:.2f}")

        # SD 신호
        if self.config.use_sd:
            sd_signal = self.sd_scorer.generate_signal(data, stock_code)
            signals.append(sd_signal)
            logger.debug(f"SD Signal: {sd_signal.signal_type.name}, "
                        f"conf={sd_signal.confidence:.2f}")

        # 신호 집계
        final_signal = self.aggregator.aggregate(signals)

        # 히스토리 저장
        self._record_signal(final_signal, signals)

        logger.info(f"Ensemble Signal for {stock_code}: {final_signal}")

        return final_signal

    def generate_signals_batch(
        self,
        data_dict: Dict[str, pd.DataFrame],
        lstm_predictions: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> Dict[str, FinalSignal]:
        """
        배치 신호 생성

        Args:
            data_dict: {종목코드: OHLCV 데이터} 딕셔너리
            lstm_predictions: {종목코드: LSTM 예측} 딕셔너리

        Returns:
            {종목코드: 최종 신호} 딕셔너리
        """
        results = {}
        lstm_predictions = lstm_predictions or {}

        for stock_code, data in data_dict.items():
            prediction = lstm_predictions.get(stock_code)
            results[stock_code] = self.generate_signal(data, stock_code, prediction)

        return results

    def get_actionable_signals(
        self,
        signals: Dict[str, FinalSignal],
        min_confidence: Optional[float] = None
    ) -> Dict[str, FinalSignal]:
        """
        실행 가능한 신호만 필터링

        Args:
            signals: 신호 딕셔너리
            min_confidence: 최소 신뢰도 (None이면 설정값 사용)

        Returns:
            실행 가능한 신호만 포함된 딕셔너리
        """
        threshold = min_confidence or self.config.min_confidence

        return {
            code: signal
            for code, signal in signals.items()
            if signal.is_actionable and signal.confidence >= threshold
        }

    def rank_signals(
        self,
        signals: Dict[str, FinalSignal],
        action_filter: Optional[SignalType] = None
    ) -> List[tuple]:
        """
        신호 순위 정렬

        Args:
            signals: 신호 딕셔너리
            action_filter: 특정 액션만 필터링 (BUY/SELL)

        Returns:
            [(종목코드, 신호, 점수)] 리스트 (점수 내림차순)
        """
        ranked = []

        for code, signal in signals.items():
            if action_filter and signal.action != action_filter:
                continue

            # 점수 계산: 신뢰도 × 강도 × 동의수 가중치
            score = signal.confidence * signal.strength * (1 + signal.agreement_count * 0.1)
            ranked.append((code, signal, score))

        return sorted(ranked, key=lambda x: x[2], reverse=True)

    def update_weights(self, new_weights: Dict[str, float]):
        """전략 가중치 업데이트"""
        self.config.weights.update(new_weights)

        # 집계기 가중치도 업데이트
        source_weights = {
            SignalSource.LSTM: new_weights.get('lstm', 0.35),
            SignalSource.TA: new_weights.get('ta', 0.35),
            SignalSource.SD: new_weights.get('sd', 0.30),
        }
        self.aggregator.update_weights(source_weights)

    def _record_signal(self, final_signal: FinalSignal, individual_signals: List[Signal]):
        """신호 히스토리 기록"""
        record = {
            'timestamp': datetime.now(),
            'stock_code': final_signal.stock_code,
            'action': final_signal.action.name,
            'confidence': final_signal.confidence,
            'strength': final_signal.strength,
            'agreement': final_signal.agreement_count,
            'individual_signals': [
                {
                    'source': s.source.value,
                    'type': s.signal_type.name,
                    'confidence': s.confidence
                }
                for s in individual_signals
            ]
        }
        self._signal_history.append(record)

        # 히스토리 크기 제한 (최근 1000개)
        if len(self._signal_history) > 1000:
            self._signal_history = self._signal_history[-1000:]

    def get_signal_stats(self) -> Dict[str, Any]:
        """신호 통계"""
        if not self._signal_history:
            return {}

        total = len(self._signal_history)
        buy_count = sum(1 for r in self._signal_history if r['action'] == 'BUY')
        sell_count = sum(1 for r in self._signal_history if r['action'] == 'SELL')
        hold_count = total - buy_count - sell_count

        avg_confidence = np.mean([r['confidence'] for r in self._signal_history])
        avg_agreement = np.mean([r['agreement'] for r in self._signal_history])

        return {
            'total_signals': total,
            'buy_signals': buy_count,
            'sell_signals': sell_count,
            'hold_signals': hold_count,
            'buy_ratio': buy_count / total if total > 0 else 0,
            'sell_ratio': sell_count / total if total > 0 else 0,
            'avg_confidence': avg_confidence,
            'avg_agreement': avg_agreement
        }

    def get_source_performance(self) -> Dict[str, Dict[str, float]]:
        """전략별 성과 분석 (동의율 기준)"""
        if not self._signal_history:
            return {}

        source_stats = {
            'lstm': {'agree': 0, 'disagree': 0},
            'ta': {'agree': 0, 'disagree': 0},
            'sd': {'agree': 0, 'disagree': 0}
        }

        for record in self._signal_history:
            final_action = record['action']
            if final_action == 'HOLD':
                continue

            for sig in record['individual_signals']:
                source = sig['source']
                if source in source_stats:
                    if sig['type'] == final_action:
                        source_stats[source]['agree'] += 1
                    else:
                        source_stats[source]['disagree'] += 1

        # 동의율 계산
        result = {}
        for source, stats in source_stats.items():
            total = stats['agree'] + stats['disagree']
            result[source] = {
                'agreement_rate': stats['agree'] / total if total > 0 else 0,
                'total_signals': total
            }

        return result
