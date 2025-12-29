"""
동적 가중치 계산기

Task B.1.1: DynamicWeightCalculator 클래스 생성
Task B.1.2: 팩터별 기여도 분석 로직
Task B.1.3: 가중치 최적화 알고리즘 (EMA)
"""

import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field

from core.utils.log_utils import get_logger
from .weight_safety import WeightSafety, get_weight_safety

logger = get_logger(__name__)


@dataclass
class FactorContribution:
    """팩터 기여도 분석 결과"""
    factor_name: str
    contribution_score: float        # 성과 기여도 점수 (-1 ~ 1)
    win_rate_contribution: float     # 승률 기여도
    return_contribution: float       # 수익률 기여도
    sample_count: int                # 분석에 사용된 샘플 수
    confidence: float                # 분석 신뢰도 (0 ~ 1)


@dataclass
class WeightUpdateResult:
    """가중치 업데이트 결과"""
    previous_weights: Dict[str, float]
    new_weights: Dict[str, float]
    contributions: Dict[str, FactorContribution]
    update_reason: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result['contributions'] = {k: asdict(v) for k, v in self.contributions.items()}
        return result


class DynamicWeightCalculator:
    """동적 가중치 계산기"""

    # 기본 팩터 키 목록
    FACTOR_KEYS = [
        'momentum', 'value', 'quality', 'volume',
        'volatility', 'technical', 'market_strength'
    ]

    def __init__(self,
                 ema_alpha: float = 0.3,
                 min_samples_for_update: int = 30,
                 weight_safety: Optional[WeightSafety] = None,
                 data_dir: str = "data/learning/weights"):
        """
        초기화

        Args:
            ema_alpha: EMA 평활 계수 (0 < alpha <= 1, 클수록 최근 데이터 중시)
            min_samples_for_update: 업데이트에 필요한 최소 샘플 수
            weight_safety: 가중치 안전장치 인스턴스
            data_dir: 데이터 저장 디렉토리
        """
        if not 0 < ema_alpha <= 1:
            raise ValueError("ema_alpha는 0 초과 1 이하여야 함")

        self._ema_alpha = ema_alpha
        self._min_samples = min_samples_for_update
        self._weight_safety = weight_safety or get_weight_safety()
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # 현재 가중치 로드 또는 초기화
        self._current_weights = self._load_weights()
        self._contribution_history: List[Dict[str, FactorContribution]] = []

        logger.info(f"DynamicWeightCalculator 초기화 - EMA alpha={ema_alpha}")

    @property
    def current_weights(self) -> Dict[str, float]:
        """현재 가중치 반환"""
        return self._current_weights.copy()

    def analyze_factor_contributions(self,
                                    performance_data: List[Dict[str, Any]],
                                    factor_scores: List[Dict[str, float]]) -> Dict[str, FactorContribution]:
        """
        팩터별 기여도 분석 (B.1.2)

        각 팩터가 최종 성과에 얼마나 기여했는지 분석

        Args:
            performance_data: 성과 데이터 리스트
                - 각 항목: {'stock_code': str, 'return': float, 'is_win': bool, ...}
            factor_scores: 해당 시점의 팩터 점수 리스트
                - 각 항목: {'momentum': float, 'value': float, ...}

        Returns:
            팩터별 기여도 분석 결과
        """
        if len(performance_data) != len(factor_scores):
            raise ValueError("performance_data와 factor_scores 길이가 일치해야 함")

        if len(performance_data) < self._min_samples:
            logger.warning(f"샘플 수 부족: {len(performance_data)} < {self._min_samples}")
            return self._get_neutral_contributions()

        contributions = {}

        for factor in self.FACTOR_KEYS:
            contribution = self._calculate_single_factor_contribution(
                factor, performance_data, factor_scores
            )
            contributions[factor] = contribution

        # 기여도 히스토리에 추가
        self._contribution_history.append(contributions)
        if len(self._contribution_history) > 100:
            self._contribution_history.pop(0)

        return contributions

    def _calculate_single_factor_contribution(self,
                                              factor_name: str,
                                              performance_data: List[Dict[str, Any]],
                                              factor_scores: List[Dict[str, float]]) -> FactorContribution:
        """단일 팩터의 기여도 계산"""
        # 팩터 점수 추출
        scores = []
        returns = []
        wins = []

        for i, (perf, factors) in enumerate(zip(performance_data, factor_scores)):
            score = factors.get(factor_name, 0.5)  # 기본값 0.5 (중립)
            ret = perf.get('return', 0.0)
            is_win = perf.get('is_win', ret > 0)

            scores.append(score)
            returns.append(ret)
            wins.append(1 if is_win else 0)

        scores = np.array(scores)
        returns = np.array(returns)
        wins = np.array(wins)

        # 상관관계 기반 기여도 계산
        # 1. 수익률과의 상관관계
        if np.std(scores) > 1e-6 and np.std(returns) > 1e-6:
            return_corr = np.corrcoef(scores, returns)[0, 1]
            if np.isnan(return_corr):
                return_corr = 0.0
        else:
            return_corr = 0.0

        # 2. 승률과의 상관관계
        if np.std(scores) > 1e-6 and np.std(wins) > 1e-6:
            win_corr = np.corrcoef(scores, wins)[0, 1]
            if np.isnan(win_corr):
                win_corr = 0.0
        else:
            win_corr = 0.0

        # 3. 상위/하위 그룹 비교
        # 팩터 점수 상위 30%와 하위 30%의 성과 차이
        n = len(scores)
        top_n = max(1, int(n * 0.3))
        sorted_indices = np.argsort(scores)

        top_indices = sorted_indices[-top_n:]
        bottom_indices = sorted_indices[:top_n]

        top_return = np.mean(returns[top_indices])
        bottom_return = np.mean(returns[bottom_indices])
        return_spread = top_return - bottom_return

        # 종합 기여도 점수 계산 (-1 ~ 1)
        # 수익률 상관 40%, 승률 상관 30%, 상/하위 스프레드 30%
        contribution_score = (
            return_corr * 0.4 +
            win_corr * 0.3 +
            np.clip(return_spread * 10, -1, 1) * 0.3  # 스프레드 정규화
        )
        contribution_score = np.clip(contribution_score, -1, 1)

        # 신뢰도 계산 (샘플 수 기반)
        confidence = min(1.0, len(scores) / 100)

        return FactorContribution(
            factor_name=factor_name,
            contribution_score=float(contribution_score),
            win_rate_contribution=float(win_corr),
            return_contribution=float(return_corr),
            sample_count=len(scores),
            confidence=float(confidence)
        )

    def _get_neutral_contributions(self) -> Dict[str, FactorContribution]:
        """중립적 기여도 반환 (데이터 부족 시)"""
        return {
            factor: FactorContribution(
                factor_name=factor,
                contribution_score=0.0,
                win_rate_contribution=0.0,
                return_contribution=0.0,
                sample_count=0,
                confidence=0.0
            )
            for factor in self.FACTOR_KEYS
        }

    def calculate_optimal_weights(self,
                                  contributions: Dict[str, FactorContribution]) -> Dict[str, float]:
        """
        기여도 기반 최적 가중치 계산 (B.1.3)

        기여도가 높은 팩터에 더 높은 가중치 부여

        Args:
            contributions: 팩터별 기여도

        Returns:
            계산된 최적 가중치
        """
        # 기여도 점수를 양수로 변환 (최소 0.1)
        raw_weights = {}
        for factor, contrib in contributions.items():
            # -1 ~ 1 범위를 0.1 ~ 1.0 범위로 변환
            # 기여도가 음수여도 최소 가중치는 유지
            weight = 0.55 + contrib.contribution_score * 0.45
            weight = max(0.1, weight)

            # 신뢰도가 낮으면 중립 가중치에 가깝게
            if contrib.confidence < 0.5:
                neutral_weight = 1.0 / len(self.FACTOR_KEYS)
                blend_factor = contrib.confidence * 2  # 0 ~ 1
                weight = weight * blend_factor + neutral_weight * (1 - blend_factor)

            raw_weights[factor] = weight

        # 정규화 및 안전장치 적용
        return self._weight_safety.normalize_weights(raw_weights)

    def update_weights_ema(self,
                          new_weights: Dict[str, float],
                          reason: str = "periodic_update") -> WeightUpdateResult:
        """
        EMA 기반 가중치 업데이트 (B.1.3)

        현재 가중치와 새 가중치를 EMA로 혼합

        Args:
            new_weights: 새로 계산된 가중치
            reason: 업데이트 사유

        Returns:
            업데이트 결과
        """
        previous_weights = self._current_weights.copy()

        # EMA 적용: new = alpha * proposed + (1 - alpha) * current
        blended_weights = {}
        for factor in self.FACTOR_KEYS:
            current = self._current_weights.get(factor, 1.0 / len(self.FACTOR_KEYS))
            proposed = new_weights.get(factor, current)
            blended = self._ema_alpha * proposed + (1 - self._ema_alpha) * current
            blended_weights[factor] = blended

        # 변경률 제한 적용
        limited_weights = self._weight_safety.apply_change_limit(
            self._current_weights, blended_weights
        )

        # 현재 가중치 업데이트
        self._current_weights = limited_weights

        # 변경 기록
        self._weight_safety.record_change(
            previous_weights=previous_weights,
            new_weights=limited_weights,
            reason=reason,
            change_type='update'
        )

        # 파일에 저장
        self._save_weights()

        # 최근 기여도 가져오기
        recent_contributions = (
            self._contribution_history[-1]
            if self._contribution_history
            else self._get_neutral_contributions()
        )

        result = WeightUpdateResult(
            previous_weights=previous_weights,
            new_weights=limited_weights,
            contributions=recent_contributions,
            update_reason=reason
        )

        logger.info(f"가중치 업데이트 완료: {reason}")
        self._log_weight_changes(previous_weights, limited_weights)

        return result

    def update_from_performance(self,
                               performance_data: List[Dict[str, Any]],
                               factor_scores: List[Dict[str, float]],
                               reason: str = "performance_based") -> Optional[WeightUpdateResult]:
        """
        성과 데이터 기반 가중치 업데이트 (B.1.1 ~ B.1.3 통합)

        Args:
            performance_data: 성과 데이터
            factor_scores: 팩터 점수
            reason: 업데이트 사유

        Returns:
            업데이트 결과 (데이터 부족 시 None)
        """
        if len(performance_data) < self._min_samples:
            logger.info(f"가중치 업데이트 스킵: 샘플 부족 ({len(performance_data)} < {self._min_samples})")
            return None

        # 1. 기여도 분석
        contributions = self.analyze_factor_contributions(performance_data, factor_scores)

        # 2. 최적 가중치 계산
        optimal_weights = self.calculate_optimal_weights(contributions)

        # 3. EMA 업데이트
        return self.update_weights_ema(optimal_weights, reason)

    def get_weight_summary(self) -> Dict[str, Any]:
        """가중치 요약 정보 조회"""
        history = self._weight_safety.get_history(limit=5)

        return {
            'current_weights': self._current_weights,
            'ema_alpha': self._ema_alpha,
            'min_samples': self._min_samples,
            'recent_changes': [h.to_dict() for h in history],
            'contribution_history_size': len(self._contribution_history)
        }

    def reset_to_default(self) -> Dict[str, float]:
        """가중치를 기본값으로 리셋"""
        previous = self._current_weights.copy()
        self._current_weights = self._weight_safety.get_safe_default_weights()

        self._weight_safety.record_change(
            previous_weights=previous,
            new_weights=self._current_weights,
            reason="manual_reset",
            change_type='reset'
        )

        self._save_weights()
        logger.info("가중치 기본값으로 리셋")

        return self._current_weights

    def rollback(self, steps: int = 1) -> Optional[Dict[str, float]]:
        """이전 가중치로 롤백"""
        rollback_weights = self._weight_safety.rollback(steps)

        if rollback_weights:
            previous = self._current_weights.copy()
            self._current_weights = rollback_weights

            self._weight_safety.record_change(
                previous_weights=previous,
                new_weights=rollback_weights,
                reason=f"rollback_{steps}_steps",
                change_type='rollback'
            )

            self._save_weights()
            logger.info(f"{steps}단계 롤백 완료")

        return rollback_weights

    def _log_weight_changes(self,
                           previous: Dict[str, float],
                           current: Dict[str, float]):
        """가중치 변경 로그"""
        changes = []
        for factor in self.FACTOR_KEYS:
            prev = previous.get(factor, 0)
            curr = current.get(factor, 0)
            diff = curr - prev
            if abs(diff) > 0.001:
                changes.append(f"{factor}: {prev:.3f} → {curr:.3f} ({diff:+.3f})")

        if changes:
            logger.debug("가중치 변경 상세:\n  " + "\n  ".join(changes))

    def _load_weights(self) -> Dict[str, float]:
        """가중치 파일 로드"""
        weight_file = self._data_dir / "current_weights.json"

        try:
            if weight_file.exists():
                with open(weight_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    weights = data.get('weights', {})

                    # 검증
                    is_valid, errors = self._weight_safety.validate_weights(weights)
                    if is_valid:
                        logger.debug("가중치 파일 로드 성공")
                        return weights
                    else:
                        logger.warning(f"저장된 가중치 유효하지 않음: {errors}")
        except Exception as e:
            logger.error(f"가중치 로드 실패: {e}")

        # 기본 가중치 반환
        return self._weight_safety.get_safe_default_weights()

    def _save_weights(self):
        """가중치 파일 저장"""
        weight_file = self._data_dir / "current_weights.json"

        try:
            data = {
                'weights': self._current_weights,
                'updated_at': datetime.now().isoformat(),
                'ema_alpha': self._ema_alpha
            }
            with open(weight_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"가중치 저장 실패: {e}")


# 싱글톤 인스턴스
_calculator_instance: Optional[DynamicWeightCalculator] = None


def get_dynamic_weight_calculator() -> DynamicWeightCalculator:
    """DynamicWeightCalculator 싱글톤 인스턴스 반환"""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = DynamicWeightCalculator()
    return _calculator_instance
