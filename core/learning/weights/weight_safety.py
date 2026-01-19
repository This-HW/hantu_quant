"""
가중치 안전장치 시스템

Task B.1.4: 가중치 범위 제한 및 정규화
Task B.3.1: 가중치 변경 이력 관리
Task B.3.2: 가중치 롤백 기능
Task B.3.3: 급격한 변동 방지 (변경률 제한)
"""

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from collections import deque

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class WeightConstraints:
    """가중치 제약 조건 설정"""
    min_weight: float = 0.05          # 최소 가중치 (5%)
    max_weight: float = 0.40          # 최대 가중치 (40%)
    max_change_rate: float = 0.05     # 1회 최대 변경률 (5%)
    total_sum: float = 1.0            # 합계 목표값
    sum_tolerance: float = 1e-6       # 합계 허용 오차

    def validate(self) -> bool:
        """제약 조건 유효성 검증"""
        if self.min_weight < 0 or self.max_weight > 1:
            return False
        if self.min_weight >= self.max_weight:
            return False
        if self.max_change_rate <= 0 or self.max_change_rate > 0.5:
            return False
        return True


@dataclass
class WeightChangeRecord:
    """가중치 변경 기록"""
    timestamp: str
    previous_weights: Dict[str, float]
    new_weights: Dict[str, float]
    change_reason: str
    change_type: str  # 'update', 'rollback', 'reset'
    validation_passed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeightChangeRecord':
        return cls(**data)


class WeightSafety:
    """가중치 안전장치 시스템"""

    # 기본 팩터 키 (순서 고정)
    DEFAULT_FACTOR_KEYS = [
        'momentum', 'value', 'quality', 'volume',
        'volatility', 'technical', 'market_strength'
    ]

    def __init__(self,
                 constraints: Optional[WeightConstraints] = None,
                 history_dir: str = "data/learning/weight_history",
                 max_history_size: int = 100):
        """
        초기화

        Args:
            constraints: 가중치 제약 조건
            history_dir: 이력 저장 디렉토리
            max_history_size: 최대 이력 보관 수
        """
        self._constraints = constraints or WeightConstraints()
        if not self._constraints.validate():
            raise ValueError("유효하지 않은 가중치 제약 조건")

        self._history_dir = Path(history_dir)
        self._history_dir.mkdir(parents=True, exist_ok=True)
        self._max_history_size = max_history_size

        # 메모리 내 최근 이력 (빠른 롤백용)
        self._recent_history: deque = deque(maxlen=max_history_size)

        # 이력 파일에서 로드
        self._load_history()

        logger.info(f"WeightSafety 초기화 완료 - 제약조건: min={self._constraints.min_weight}, "
                   f"max={self._constraints.max_weight}, max_change={self._constraints.max_change_rate}")

    def validate_weights(self, weights: Dict[str, float]) -> Tuple[bool, List[str]]:
        """
        가중치 유효성 검증 (B.1.4)

        Args:
            weights: 검증할 가중치 딕셔너리

        Returns:
            (유효 여부, 오류 메시지 리스트)
        """
        errors = []

        # 1. 빈 딕셔너리 체크
        if not weights:
            errors.append("가중치 딕셔너리가 비어있음")
            return False, errors

        # 2. 값 유효성 체크 (NaN, Inf 방지)
        for key, value in weights.items():
            if not isinstance(value, (int, float)):
                errors.append(f"'{key}': 숫자가 아닌 값 ({type(value).__name__})")
                continue
            if math.isnan(value):
                errors.append(f"'{key}': NaN 값 감지")
            if math.isinf(value):
                errors.append(f"'{key}': 무한대 값 감지")
            if value < 0:
                errors.append(f"'{key}': 음수 값 ({value})")

        if errors:
            return False, errors

        # 3. 범위 체크
        for key, value in weights.items():
            if value < self._constraints.min_weight:
                errors.append(f"'{key}': 최소값 미달 ({value:.4f} < {self._constraints.min_weight})")
            if value > self._constraints.max_weight:
                errors.append(f"'{key}': 최대값 초과 ({value:.4f} > {self._constraints.max_weight})")

        # 4. 합계 체크
        total = sum(weights.values())
        if abs(total - self._constraints.total_sum) > self._constraints.sum_tolerance:
            errors.append(f"합계 불일치: {total:.6f} != {self._constraints.total_sum}")

        return len(errors) == 0, errors

    def normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        가중치 정규화 (B.1.4)

        - 범위 제한 적용 (min_weight ~ max_weight)
        - 합계 1.0 정규화

        Args:
            weights: 정규화할 가중치

        Returns:
            정규화된 가중치
        """
        if not weights:
            raise ValueError("가중치 딕셔너리가 비어있음")

        # 1. NaN/Inf 값 기본값으로 대체
        cleaned = {}
        default_value = 1.0 / len(weights)

        for key, value in weights.items():
            if not isinstance(value, (int, float)) or math.isnan(value) or math.isinf(value):
                logger.warning(f"'{key}'의 잘못된 값 {value}을 기본값 {default_value}로 대체")
                cleaned[key] = default_value
            else:
                cleaned[key] = max(0, float(value))  # 음수 방지

        # 2. 범위 제한 (클램핑)
        clamped = {}
        for key, value in cleaned.items():
            clamped[key] = max(self._constraints.min_weight,
                              min(self._constraints.max_weight, value))

        # 3. 합계 정규화
        total = sum(clamped.values())
        if total == 0:
            # 모든 값이 0인 경우 균등 분배
            equal_weight = 1.0 / len(clamped)
            return {k: equal_weight for k in clamped}

        normalized = {k: v / total for k, v in clamped.items()}

        # 4. 정규화 후 다시 범위 체크 및 조정
        # (정규화로 인해 범위를 벗어날 수 있음)
        normalized = self._iterative_normalize(normalized)

        return normalized

    def _iterative_normalize(self, weights: Dict[str, float], max_iterations: int = 10) -> Dict[str, float]:
        """
        반복적 정규화 (범위 제한과 합계 1.0 동시 만족)

        Args:
            weights: 정규화할 가중치
            max_iterations: 최대 반복 횟수

        Returns:
            정규화된 가중치
        """
        result = weights.copy()

        for _ in range(max_iterations):
            # 범위 제한
            clamped = False
            for key in result:
                if result[key] < self._constraints.min_weight:
                    result[key] = self._constraints.min_weight
                    clamped = True
                elif result[key] > self._constraints.max_weight:
                    result[key] = self._constraints.max_weight
                    clamped = True

            # 합계 조정
            total = sum(result.values())
            if abs(total - 1.0) < self._constraints.sum_tolerance:
                break

            if not clamped:
                # 클램핑 없이 정규화만 필요
                result = {k: v / total for k, v in result.items()}
            else:
                # 클램핑된 값 제외하고 나머지 조정
                fixed_keys = [k for k, v in result.items()
                             if v == self._constraints.min_weight or v == self._constraints.max_weight]
                adjustable_keys = [k for k in result if k not in fixed_keys]

                if not adjustable_keys:
                    # 모든 값이 경계에 있으면 균등 조정
                    adjustment = (1.0 - total) / len(result)
                    result = {k: v + adjustment for k, v in result.items()}
                else:
                    fixed_sum = sum(result[k] for k in fixed_keys)
                    adjustable_sum = sum(result[k] for k in adjustable_keys)
                    target_adjustable = 1.0 - fixed_sum

                    if adjustable_sum > 0:
                        scale = target_adjustable / adjustable_sum
                        for k in adjustable_keys:
                            result[k] *= scale

        # 최종 합계 보정 (부동소수점 오차)
        total = sum(result.values())
        if total != 1.0:
            # 가장 큰 가중치에서 차이 조정
            max_key = max(result, key=result.get)
            result[max_key] += (1.0 - total)

        return result

    def apply_change_limit(self,
                           current_weights: Dict[str, float],
                           proposed_weights: Dict[str, float]) -> Dict[str, float]:
        """
        변경률 제한 적용 (B.3.3)

        Args:
            current_weights: 현재 가중치
            proposed_weights: 제안된 새 가중치

        Returns:
            변경률이 제한된 가중치
        """
        if not current_weights:
            # 현재 가중치가 없으면 제안된 가중치 그대로 사용 (정규화만)
            return self.normalize_weights(proposed_weights)

        limited = {}
        max_rate = self._constraints.max_change_rate

        for key in proposed_weights:
            current = current_weights.get(key, proposed_weights[key])
            proposed = proposed_weights[key]

            # 변경량 계산
            change = proposed - current

            # 변경률 제한
            if abs(change) > max_rate:
                if change > 0:
                    limited[key] = current + max_rate
                else:
                    limited[key] = current - max_rate
                logger.debug(f"'{key}' 변경률 제한: {current:.4f} → {proposed:.4f} "
                           f"→ {limited[key]:.4f} (max_rate={max_rate})")
            else:
                limited[key] = proposed

        # 새로 추가된 키 처리
        for key in proposed_weights:
            if key not in limited:
                limited[key] = proposed_weights[key]

        # 정규화 적용
        return self.normalize_weights(limited)

    def record_change(self,
                     previous_weights: Dict[str, float],
                     new_weights: Dict[str, float],
                     reason: str,
                     change_type: str = 'update') -> WeightChangeRecord:
        """
        가중치 변경 기록 (B.3.1)

        Args:
            previous_weights: 이전 가중치
            new_weights: 새 가중치
            reason: 변경 사유
            change_type: 변경 유형 ('update', 'rollback', 'reset')

        Returns:
            생성된 변경 기록
        """
        is_valid, _ = self.validate_weights(new_weights)

        record = WeightChangeRecord(
            timestamp=datetime.now().isoformat(),
            previous_weights=previous_weights.copy(),
            new_weights=new_weights.copy(),
            change_reason=reason,
            change_type=change_type,
            validation_passed=is_valid
        )

        # 메모리에 저장
        self._recent_history.append(record)

        # 파일에 저장
        self._save_history()

        logger.info(f"가중치 변경 기록: {change_type} - {reason}")
        return record

    def get_history(self, limit: int = 10) -> List[WeightChangeRecord]:
        """
        최근 변경 이력 조회 (B.3.1)

        Args:
            limit: 조회할 최대 개수

        Returns:
            변경 기록 리스트 (최신 순)
        """
        history = list(self._recent_history)
        history.reverse()  # 최신 순
        return history[:limit]

    def rollback(self, steps: int = 1) -> Optional[Dict[str, float]]:
        """
        이전 가중치로 롤백 (B.3.2)

        Args:
            steps: 롤백할 단계 수

        Returns:
            롤백된 가중치 (실패 시 None)
        """
        if len(self._recent_history) < steps:
            logger.warning(f"롤백 실패: 이력 부족 (요청: {steps}, 보유: {len(self._recent_history)})")
            return None

        # steps 단계 이전의 가중치 찾기
        history = list(self._recent_history)
        if steps > len(history):
            return None

        target_record = history[-(steps)]
        rollback_weights = target_record.previous_weights

        logger.info(f"{steps}단계 롤백: {target_record.timestamp} 시점으로")
        return rollback_weights.copy()

    def get_safe_default_weights(self) -> Dict[str, float]:
        """
        안전한 기본 가중치 반환

        Returns:
            기본 가중치 (균등 분배, 제약 조건 만족)
        """
        num_factors = len(self.DEFAULT_FACTOR_KEYS)
        equal_weight = 1.0 / num_factors

        weights = {key: equal_weight for key in self.DEFAULT_FACTOR_KEYS}
        return self.normalize_weights(weights)

    def _load_history(self):
        """파일에서 이력 로드"""
        history_file = self._history_dir / "weight_change_history.json"

        try:
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for record_dict in data:
                        record = WeightChangeRecord.from_dict(record_dict)
                        self._recent_history.append(record)
                logger.debug(f"가중치 이력 로드: {len(self._recent_history)}개")
        except Exception as e:
            logger.error(f"가중치 이력 로드 실패: {e}", exc_info=True)

    def _save_history(self):
        """파일에 이력 저장"""
        history_file = self._history_dir / "weight_change_history.json"

        try:
            data = [record.to_dict() for record in self._recent_history]
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"가중치 이력 저장 실패: {e}", exc_info=True)


# 싱글톤 인스턴스
_weight_safety_instance: Optional[WeightSafety] = None


def get_weight_safety() -> WeightSafety:
    """WeightSafety 싱글톤 인스턴스 반환"""
    global _weight_safety_instance
    if _weight_safety_instance is None:
        _weight_safety_instance = WeightSafety()
    return _weight_safety_instance
