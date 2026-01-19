"""
신호 집계기 모듈

여러 전략의 신호를 집계하여 최종 거래 신호를 생성합니다.
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .signal import Signal, SignalType, SignalSource, FinalSignal


@dataclass
class AggregatorConfig:
    """신호 집계기 설정"""
    # 전략별 가중치 (합계 1.0)
    weights: Dict[SignalSource, float] = field(default_factory=lambda: {
        SignalSource.LSTM: 0.35,
        SignalSource.TA: 0.35,
        SignalSource.SD: 0.30,
    })

    # 최소 일치 조건
    min_agreement: int = 2  # 최소 N개 전략 동의 필요

    # 신뢰도 임계값
    min_confidence: float = 0.5  # 개별 신호 최소 신뢰도
    final_min_confidence: float = 0.6  # 최종 신호 최소 신뢰도

    # 포지션 크기 결정 임계값
    strength_thresholds: Tuple[float, float] = (0.6, 0.8)  # strength 1, 2, 3 경계

    # 손절/익절 설정
    use_tightest_stop: bool = True  # 가장 타이트한 손절가 사용
    risk_reward_minimum: float = 1.5  # 최소 손익비


class SignalAggregator:
    """
    신호 집계기

    여러 전략의 신호를 가중 투표 방식으로 집계하여
    최종 거래 결정을 생성합니다.
    """

    def __init__(self, config: Optional[AggregatorConfig] = None):
        self.config = config or AggregatorConfig()
        self._validate_weights()

    def _validate_weights(self):
        """가중치 합계 검증 및 정규화"""
        total = sum(self.config.weights.values())
        if abs(total - 1.0) > 0.01:
            # 정규화
            for source in self.config.weights:
                self.config.weights[source] /= total

    def aggregate(self, signals: List[Signal]) -> FinalSignal:
        """
        신호 집계

        Args:
            signals: 개별 전략 신호 리스트

        Returns:
            FinalSignal: 최종 집계 신호
        """
        if not signals:
            return self._create_hold_signal("No signals received")

        stock_code = signals[0].stock_code

        # 신뢰도 필터링
        filtered_signals = self._filter_by_confidence(signals)

        if not filtered_signals:
            return self._create_hold_signal(
                "All signals below confidence threshold",
                stock_code=stock_code,
                signals=signals
            )

        # 가중 투표
        buy_score, sell_score, buy_signals, sell_signals = self._weighted_vote(filtered_signals)

        # 최소 일치 조건 체크
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)

        # 결정
        if buy_score > sell_score and buy_count >= self.config.min_agreement:
            return self._create_buy_signal(buy_signals, buy_score, filtered_signals)
        elif sell_score > buy_score and sell_count >= self.config.min_agreement:
            return self._create_sell_signal(sell_signals, sell_score, filtered_signals)
        else:
            return self._create_hold_signal(
                self._get_hold_reason(buy_score, sell_score, buy_count, sell_count),
                stock_code=stock_code,
                signals=filtered_signals
            )

    def _filter_by_confidence(self, signals: List[Signal]) -> List[Signal]:
        """신뢰도 기준 필터링"""
        return [s for s in signals if s.confidence >= self.config.min_confidence]

    def _weighted_vote(self, signals: List[Signal]) -> Tuple[float, float, List[Signal], List[Signal]]:
        """
        가중 투표 계산

        Returns:
            (buy_score, sell_score, buy_signals, sell_signals)
        """
        buy_score = 0.0
        sell_score = 0.0
        buy_signals = []
        sell_signals = []

        for signal in signals:
            weight = self.config.weights.get(signal.source, 0.1)
            weighted_score = weight * signal.strength * signal.confidence

            if signal.signal_type == SignalType.BUY:
                buy_score += weighted_score
                buy_signals.append(signal)
            elif signal.signal_type == SignalType.SELL:
                sell_score += weighted_score
                sell_signals.append(signal)

        return buy_score, sell_score, buy_signals, sell_signals

    def _create_buy_signal(
        self,
        buy_signals: List[Signal],
        score: float,
        all_signals: List[Signal]
    ) -> FinalSignal:
        """매수 신호 생성"""
        stock_code = buy_signals[0].stock_code

        # 신뢰도 계산 (평균 가중 신뢰도)
        confidence = self._calculate_aggregate_confidence(buy_signals)

        # 강도 결정
        strength = self._determine_strength(score, confidence, len(buy_signals))

        # 손절/익절 계산
        stop_loss, take_profit = self._calculate_risk_levels(buy_signals, SignalType.BUY)

        # 포지션 크기 배수
        position_multiplier = self._calculate_position_multiplier(
            confidence, strength, len(buy_signals)
        )

        # 이유 생성
        sources = [s.source for s in buy_signals]
        reasons = [s.reason for s in buy_signals if s.reason]
        reason = f"Buy signal from {len(buy_signals)} strategies: " + "; ".join(reasons[:3])

        return FinalSignal(
            action=SignalType.BUY,
            stock_code=stock_code,
            confidence=confidence,
            strength=strength,
            agreement_count=len(buy_signals),
            sources=sources,
            reason=reason,
            individual_signals=all_signals,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_multiplier=position_multiplier
        )

    def _create_sell_signal(
        self,
        sell_signals: List[Signal],
        score: float,
        all_signals: List[Signal]
    ) -> FinalSignal:
        """매도 신호 생성"""
        stock_code = sell_signals[0].stock_code

        confidence = self._calculate_aggregate_confidence(sell_signals)
        strength = self._determine_strength(score, confidence, len(sell_signals))
        stop_loss, take_profit = self._calculate_risk_levels(sell_signals, SignalType.SELL)
        position_multiplier = self._calculate_position_multiplier(
            confidence, strength, len(sell_signals)
        )

        sources = [s.source for s in sell_signals]
        reasons = [s.reason for s in sell_signals if s.reason]
        reason = f"Sell signal from {len(sell_signals)} strategies: " + "; ".join(reasons[:3])

        return FinalSignal(
            action=SignalType.SELL,
            stock_code=stock_code,
            confidence=confidence,
            strength=strength,
            agreement_count=len(sell_signals),
            sources=sources,
            reason=reason,
            individual_signals=all_signals,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_multiplier=position_multiplier
        )

    def _create_hold_signal(
        self,
        reason: str,
        stock_code: str = "",
        signals: Optional[List[Signal]] = None
    ) -> FinalSignal:
        """HOLD 신호 생성"""
        return FinalSignal(
            action=SignalType.HOLD,
            stock_code=stock_code,
            confidence=0.0,
            strength=0,
            agreement_count=0,
            sources=[],
            reason=reason,
            individual_signals=signals or []
        )

    def _calculate_aggregate_confidence(self, signals: List[Signal]) -> float:
        """집계 신뢰도 계산"""
        if not signals:
            return 0.0

        # 가중 평균 신뢰도
        total_weight = 0.0
        weighted_confidence = 0.0

        for signal in signals:
            weight = self.config.weights.get(signal.source, 0.1)
            weighted_confidence += signal.confidence * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        base_confidence = weighted_confidence / total_weight

        # 동의 전략 수에 따른 보너스 (최대 10%)
        agreement_bonus = min(0.1, (len(signals) - 1) * 0.05)

        return min(1.0, base_confidence + agreement_bonus)

    def _determine_strength(self, score: float, confidence: float, agreement: int) -> int:
        """강도 결정 (1, 2, 3 단계)"""
        combined_score = score * confidence

        low_threshold, high_threshold = self.config.strength_thresholds

        if combined_score >= high_threshold and agreement >= 3:
            return 3  # 강한 신호
        elif combined_score >= low_threshold and agreement >= 2:
            return 2  # 보통 신호
        else:
            return 1  # 약한 신호

    def _calculate_risk_levels(
        self,
        signals: List[Signal],
        action: SignalType
    ) -> Tuple[Optional[float], Optional[float]]:
        """손절/익절 레벨 계산"""
        stop_losses = [s.stop_loss for s in signals if s.stop_loss is not None]
        take_profits = [s.take_profit for s in signals if s.take_profit is not None]

        if not stop_losses or not take_profits:
            return None, None

        if action == SignalType.BUY:
            # 매수: 가장 높은 손절가 (타이트하게) 또는 가장 낮은 (여유있게)
            if self.config.use_tightest_stop:
                stop_loss = max(stop_losses)
            else:
                stop_loss = min(stop_losses)
            # 익절은 평균
            take_profit = np.mean(take_profits)
        else:
            # 매도: 가장 낮은 손절가 (타이트하게)
            if self.config.use_tightest_stop:
                stop_loss = min(stop_losses)
            else:
                stop_loss = max(stop_losses)
            take_profit = np.mean(take_profits)

        return stop_loss, take_profit

    def _calculate_position_multiplier(
        self,
        confidence: float,
        strength: int,
        agreement: int
    ) -> float:
        """포지션 크기 배수 계산"""
        # 기본 배수
        base_multiplier = 1.0

        # 신뢰도에 따른 조정
        confidence_factor = confidence  # 0.5 ~ 1.0

        # 강도에 따른 조정
        strength_factor = {1: 0.5, 2: 1.0, 3: 1.5}.get(strength, 1.0)

        # 동의 수에 따른 조정
        agreement_factor = min(1.5, 1.0 + (agreement - 2) * 0.25)

        return base_multiplier * confidence_factor * strength_factor * agreement_factor

    def _get_hold_reason(
        self,
        buy_score: float,
        sell_score: float,
        buy_count: int,
        sell_count: int
    ) -> str:
        """HOLD 이유 생성"""
        if buy_count < self.config.min_agreement and sell_count < self.config.min_agreement:
            return f"Insufficient agreement (buy: {buy_count}, sell: {sell_count}, min: {self.config.min_agreement})"
        elif abs(buy_score - sell_score) < 0.1:
            return f"Conflicting signals (buy: {buy_score:.2f}, sell: {sell_score:.2f})"
        else:
            return "No clear direction"

    def update_weights(self, new_weights: Dict[SignalSource, float]):
        """가중치 업데이트"""
        self.config.weights.update(new_weights)
        self._validate_weights()

    def get_source_contribution(self, final_signal: FinalSignal) -> Dict[SignalSource, float]:
        """각 소스의 기여도 계산"""
        contributions = {}

        if not final_signal.individual_signals:
            return contributions

        total_contribution = 0.0

        for signal in final_signal.individual_signals:
            if signal.signal_type == final_signal.action:
                weight = self.config.weights.get(signal.source, 0.1)
                contribution = weight * signal.strength * signal.confidence
                contributions[signal.source] = contribution
                total_contribution += contribution

        # 정규화
        if total_contribution > 0:
            for source in contributions:
                contributions[source] /= total_contribution

        return contributions
