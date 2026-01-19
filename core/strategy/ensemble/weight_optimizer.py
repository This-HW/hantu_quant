"""
가중치 최적화 모듈

전략별 성과를 분석하여 앙상블 가중치를 동적으로 조정합니다.
"""

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import logging

from .signal import SignalSource, SignalType

logger = logging.getLogger(__name__)


@dataclass
class PerformanceRecord:
    """전략 성과 기록"""
    source: SignalSource
    signal_type: SignalType
    timestamp: datetime
    entry_price: float
    exit_price: float = 0.0
    return_pct: float = 0.0
    holding_days: int = 0
    is_closed: bool = False

    @property
    def is_profitable(self) -> bool:
        """수익 여부"""
        return self.return_pct > 0


@dataclass
class OptimizerConfig:
    """가중치 최적화 설정"""
    # 가중치 범위
    min_weight: float = 0.1  # 최소 가중치
    max_weight: float = 0.5  # 최대 가중치

    # 변화 제한
    max_change_per_update: float = 0.05  # 업데이트당 최대 변화량

    # 성과 평가 기간
    lookback_days: int = 30  # 평가 기간 (일)
    min_samples: int = 10    # 최소 샘플 수

    # 성과 지표 가중치
    win_rate_weight: float = 0.4
    avg_return_weight: float = 0.3
    risk_adjusted_weight: float = 0.3

    # 스무딩
    ema_alpha: float = 0.3  # EMA 평활 계수


class WeightOptimizer:
    """
    앙상블 가중치 최적화기

    전략별 성과를 추적하고 가중치를 동적으로 조정합니다.
    """

    def __init__(self, config: Optional[OptimizerConfig] = None):
        self.config = config or OptimizerConfig()

        # 현재 가중치
        self._weights: Dict[SignalSource, float] = {
            SignalSource.LSTM: 0.35,
            SignalSource.TA: 0.35,
            SignalSource.SD: 0.30,
        }

        # 성과 기록 (소스별)
        self._performance: Dict[SignalSource, deque] = {
            source: deque(maxlen=500)
            for source in [SignalSource.LSTM, SignalSource.TA, SignalSource.SD]
        }

        # EMA 성과 점수
        self._ema_scores: Dict[SignalSource, float] = {
            source: 0.5 for source in self._weights
        }

        # 최근 업데이트 시각
        self._last_update: Optional[datetime] = None

    @property
    def weights(self) -> Dict[SignalSource, float]:
        """현재 가중치 반환"""
        return self._weights.copy()

    @property
    def weights_dict(self) -> Dict[str, float]:
        """문자열 키 가중치 반환"""
        return {source.value: weight for source, weight in self._weights.items()}

    def record_trade(
        self,
        source: SignalSource,
        signal_type: SignalType,
        entry_price: float,
        exit_price: float = 0.0,
        timestamp: Optional[datetime] = None
    ) -> PerformanceRecord:
        """
        거래 결과 기록

        Args:
            source: 신호 소스
            signal_type: 신호 유형
            entry_price: 진입 가격
            exit_price: 청산 가격 (0이면 미청산)
            timestamp: 타임스탬프

        Returns:
            PerformanceRecord: 성과 기록
        """
        record = PerformanceRecord(
            source=source,
            signal_type=signal_type,
            timestamp=timestamp or datetime.now(),
            entry_price=entry_price,
            exit_price=exit_price
        )

        if exit_price > 0:
            record.is_closed = True
            if signal_type == SignalType.BUY:
                record.return_pct = (exit_price - entry_price) / entry_price
            else:  # SELL
                record.return_pct = (entry_price - exit_price) / entry_price

        if source in self._performance:
            self._performance[source].append(record)

        return record

    def update_trade(
        self,
        source: SignalSource,
        exit_price: float,
        holding_days: int = 0
    ):
        """
        미청산 거래 업데이트

        가장 최근의 미청산 거래를 찾아 청산 처리
        """
        if source not in self._performance:
            return

        # 최근 미청산 거래 찾기
        for record in reversed(self._performance[source]):
            if not record.is_closed:
                record.exit_price = exit_price
                record.holding_days = holding_days
                record.is_closed = True

                if record.signal_type == SignalType.BUY:
                    record.return_pct = (exit_price - record.entry_price) / record.entry_price
                else:
                    record.return_pct = (record.entry_price - exit_price) / record.entry_price
                break

    def calculate_performance_scores(self) -> Dict[SignalSource, Dict[str, float]]:
        """
        전략별 성과 점수 계산

        Returns:
            {소스: {지표: 값}} 딕셔너리
        """
        cutoff_date = datetime.now() - timedelta(days=self.config.lookback_days)
        scores = {}

        for source, records in self._performance.items():
            # 기간 내 청산된 거래만 필터링
            recent_trades = [
                r for r in records
                if r.is_closed and r.timestamp >= cutoff_date
            ]

            if len(recent_trades) < self.config.min_samples:
                scores[source] = {
                    'win_rate': 0.5,
                    'avg_return': 0.0,
                    'sharpe_proxy': 0.0,
                    'sample_count': len(recent_trades),
                    'composite_score': 0.5
                }
                continue

            # 승률
            wins = sum(1 for t in recent_trades if t.is_profitable)
            win_rate = wins / len(recent_trades)

            # 평균 수익률
            returns = [t.return_pct for t in recent_trades]
            avg_return = np.mean(returns)
            std_return = np.std(returns) + 1e-10

            # 샤프 비율 대용 (연율화 없음)
            sharpe_proxy = avg_return / std_return

            # 복합 점수 (0~1 정규화)
            win_score = win_rate  # 이미 0~1
            return_score = np.clip((avg_return + 0.1) / 0.2, 0, 1)  # -10%~+10% → 0~1
            sharpe_score = np.clip((sharpe_proxy + 1) / 2, 0, 1)  # -1~+1 → 0~1

            composite_score = (
                self.config.win_rate_weight * win_score +
                self.config.avg_return_weight * return_score +
                self.config.risk_adjusted_weight * sharpe_score
            )

            scores[source] = {
                'win_rate': win_rate,
                'avg_return': avg_return,
                'sharpe_proxy': sharpe_proxy,
                'sample_count': len(recent_trades),
                'composite_score': composite_score
            }

        return scores

    def optimize(self, force: bool = False) -> Dict[SignalSource, float]:
        """
        가중치 최적화 실행

        Args:
            force: 강제 업데이트 여부

        Returns:
            업데이트된 가중치
        """
        # 최소 업데이트 간격 체크 (하루)
        if not force and self._last_update:
            if datetime.now() - self._last_update < timedelta(hours=24):
                logger.debug("Skipping optimization: too recent")
                return self._weights

        performance_scores = self.calculate_performance_scores()

        # 충분한 데이터가 없으면 기존 가중치 유지
        sufficient_data = all(
            scores['sample_count'] >= self.config.min_samples
            for scores in performance_scores.values()
        )

        if not sufficient_data:
            logger.info("Insufficient data for weight optimization")
            return self._weights

        # EMA 점수 업데이트
        alpha = self.config.ema_alpha
        for source, scores in performance_scores.items():
            self._ema_scores[source] = (
                alpha * scores['composite_score'] +
                (1 - alpha) * self._ema_scores[source]
            )

        # 새 가중치 계산
        new_weights = self._calculate_new_weights()

        # 변화 제한 적용
        new_weights = self._apply_change_limits(new_weights)

        # 범위 제한 및 정규화
        new_weights = self._normalize_weights(new_weights)

        # 업데이트
        self._weights = new_weights
        self._last_update = datetime.now()

        logger.info(f"Weights updated: {self.weights_dict}")

        return self._weights

    def _calculate_new_weights(self) -> Dict[SignalSource, float]:
        """EMA 점수 기반 새 가중치 계산"""
        total_score = sum(self._ema_scores.values())

        if total_score == 0:
            # 균등 배분
            return {source: 1.0 / len(self._weights) for source in self._weights}

        return {
            source: score / total_score
            for source, score in self._ema_scores.items()
        }

    def _apply_change_limits(
        self,
        new_weights: Dict[SignalSource, float]
    ) -> Dict[SignalSource, float]:
        """변화량 제한 적용"""
        limited_weights = {}
        max_change = self.config.max_change_per_update

        for source, new_weight in new_weights.items():
            current_weight = self._weights.get(source, new_weight)
            change = new_weight - current_weight

            if abs(change) > max_change:
                limited_weights[source] = current_weight + max_change * np.sign(change)
            else:
                limited_weights[source] = new_weight

        return limited_weights

    def _normalize_weights(
        self,
        weights: Dict[SignalSource, float]
    ) -> Dict[SignalSource, float]:
        """가중치 범위 제한 및 정규화"""
        # 범위 제한
        clipped = {
            source: np.clip(weight, self.config.min_weight, self.config.max_weight)
            for source, weight in weights.items()
        }

        # 합계 1.0으로 정규화
        total = sum(clipped.values())
        return {source: weight / total for source, weight in clipped.items()}

    def set_weights(self, weights: Dict[SignalSource, float]):
        """가중치 직접 설정"""
        total = sum(weights.values())
        self._weights = {source: w / total for source, w in weights.items()}

    def get_recommendation(self) -> Dict[str, any]:
        """가중치 조정 권고 생성"""
        performance = self.calculate_performance_scores()

        recommendations = []

        for source, scores in performance.items():
            current_weight = self._weights.get(source, 0)

            if scores['sample_count'] < self.config.min_samples:
                recommendations.append({
                    'source': source.value,
                    'action': 'INSUFFICIENT_DATA',
                    'reason': f"Only {scores['sample_count']} samples"
                })
                continue

            # 성과 기반 권고
            composite = scores['composite_score']

            if composite > 0.6 and current_weight < self.config.max_weight:
                recommendations.append({
                    'source': source.value,
                    'action': 'INCREASE',
                    'reason': f"Strong performance (score: {composite:.2f})",
                    'current_weight': current_weight,
                    'suggested_change': min(0.05, self.config.max_weight - current_weight)
                })
            elif composite < 0.4 and current_weight > self.config.min_weight:
                recommendations.append({
                    'source': source.value,
                    'action': 'DECREASE',
                    'reason': f"Weak performance (score: {composite:.2f})",
                    'current_weight': current_weight,
                    'suggested_change': -min(0.05, current_weight - self.config.min_weight)
                })
            else:
                recommendations.append({
                    'source': source.value,
                    'action': 'MAINTAIN',
                    'reason': f"Stable performance (score: {composite:.2f})",
                    'current_weight': current_weight
                })

        return {
            'current_weights': self.weights_dict,
            'performance': {s.value: p for s, p in performance.items()},
            'recommendations': recommendations
        }

    def get_stats(self) -> Dict[str, any]:
        """통계 정보"""
        performance = self.calculate_performance_scores()

        return {
            'current_weights': self.weights_dict,
            'ema_scores': {s.value: score for s, score in self._ema_scores.items()},
            'performance': {s.value: p for s, p in performance.items()},
            'last_update': self._last_update.isoformat() if self._last_update else None,
            'total_records': sum(len(records) for records in self._performance.values())
        }

    def simulate_optimization(
        self,
        trade_history: List[Dict],
        initial_weights: Optional[Dict[SignalSource, float]] = None
    ) -> List[Dict[str, float]]:
        """
        과거 거래 데이터로 최적화 시뮬레이션

        Args:
            trade_history: 거래 기록 리스트
            initial_weights: 초기 가중치

        Returns:
            기간별 가중치 변화 리스트
        """
        if initial_weights:
            self.set_weights(initial_weights)

        weight_history = [self.weights_dict.copy()]

        for trade in trade_history:
            source = SignalSource(trade['source'])
            signal_type = SignalType[trade['signal_type']]

            self.record_trade(
                source=source,
                signal_type=signal_type,
                entry_price=trade['entry_price'],
                exit_price=trade['exit_price'],
                timestamp=trade.get('timestamp', datetime.now())
            )

            # 주기적 최적화 (매 10건)
            total_records = sum(len(r) for r in self._performance.values())
            if total_records % 10 == 0:
                self.optimize(force=True)
                weight_history.append(self.weights_dict.copy())

        return weight_history
