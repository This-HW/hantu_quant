"""
레짐 기반 전략 매퍼

Task C.3.1: 레짐별 팩터 가중치 프리셋
Task C.3.2: 레짐 전환 시 가중치 자동 조정
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from core.daily_selection.selection_criteria import MarketCondition
from core.learning.regime.regime_detector import RegimeResult

# MarketCondition 별칭 (호환성)
MarketRegime = MarketCondition
from core.learning.weights.weight_safety import WeightSafety  # noqa: E402
from core.utils.log_utils import get_logger  # noqa: E402

logger = get_logger(__name__)


# 기본 팩터 목록
DEFAULT_FACTORS = [
    'momentum',
    'value',
    'quality',
    'volume',
    'volatility',
    'technical',
    'market_strength'
]


@dataclass
class RegimeWeightPreset:
    """레짐별 가중치 프리셋 (C.3.1)"""
    regime: MarketRegime
    weights: Dict[str, float]
    description: str = ""
    confidence_threshold: float = 0.6  # 이 프리셋 적용을 위한 최소 신뢰도

    def validate(self) -> bool:
        """프리셋 유효성 검증"""
        if not self.weights:
            return False

        total = sum(self.weights.values())
        return 0.99 <= total <= 1.01  # 합계 1 검증


@dataclass
class TransitionRule:
    """레짐 전환 규칙"""
    from_regime: MarketRegime
    to_regime: MarketRegime
    transition_speed: float = 0.3  # 전환 속도 (0.1=느림, 1.0=즉시)
    min_confidence: float = 0.5    # 전환을 위한 최소 신뢰도
    cooldown_hours: int = 24       # 재전환 대기 시간


class RegimeStrategyMapper:
    """
    레짐 기반 전략 매퍼

    시장 레짐에 따라 팩터 가중치를 자동으로 조정합니다.
    """

    def __init__(self,
                 factors: Optional[List[str]] = None,
                 enable_smooth_transition: bool = True,
                 transition_speed: float = 0.3):
        """
        초기화

        Args:
            factors: 팩터 목록
            enable_smooth_transition: 부드러운 전환 활성화
            transition_speed: 전환 속도 (0.1~1.0)
        """
        self._factors = factors or DEFAULT_FACTORS
        self._enable_smooth_transition = enable_smooth_transition
        self._transition_speed = max(0.1, min(1.0, transition_speed))

        self._weight_safety = WeightSafety()
        self._presets: Dict[MarketRegime, RegimeWeightPreset] = {}
        self._transition_rules: Dict[tuple, TransitionRule] = {}

        self._current_regime: Optional[MarketRegime] = None
        self._current_weights: Dict[str, float] = {}
        self._transition_progress: float = 1.0  # 1.0 = 전환 완료
        self._target_weights: Dict[str, float] = {}

        # 기본 프리셋 초기화
        self._init_default_presets()
        self._init_default_transition_rules()

        logger.info(f"RegimeStrategyMapper 초기화 - {len(self._factors)}개 팩터")

    def _init_default_presets(self):
        """기본 레짐별 프리셋 초기화 (C.3.1)"""

        # 상승장 프리셋: 모멘텀, 기술적 강조
        self._presets[MarketRegime.BULL_MARKET] = RegimeWeightPreset(
            regime=MarketRegime.BULL_MARKET,
            weights={
                'momentum': 0.25,      # 상승장에서 모멘텀 중요
                'value': 0.10,         # 가치 덜 중요
                'quality': 0.15,
                'volume': 0.15,
                'volatility': 0.05,    # 변동성 덜 중요
                'technical': 0.20,     # 기술적 분석 중요
                'market_strength': 0.10
            },
            description="상승장: 모멘텀과 기술적 지표 강조",
            confidence_threshold=0.6
        )

        # 하락장 프리셋: 가치, 퀄리티 강조
        self._presets[MarketRegime.BEAR_MARKET] = RegimeWeightPreset(
            regime=MarketRegime.BEAR_MARKET,
            weights={
                'momentum': 0.05,      # 하락장에서 모멘텀 위험
                'value': 0.25,         # 가치주 선호
                'quality': 0.25,       # 퀄리티 중요
                'volume': 0.10,
                'volatility': 0.15,    # 변동성 관리 중요
                'technical': 0.10,
                'market_strength': 0.10
            },
            description="하락장: 가치와 퀄리티 강조, 방어적 전략",
            confidence_threshold=0.6
        )

        # 횡보장 프리셋: 균형 잡힌 접근
        self._presets[MarketRegime.SIDEWAYS] = RegimeWeightPreset(
            regime=MarketRegime.SIDEWAYS,
            weights={
                'momentum': 0.10,
                'value': 0.20,
                'quality': 0.20,
                'volume': 0.15,
                'volatility': 0.10,
                'technical': 0.15,
                'market_strength': 0.10
            },
            description="횡보장: 균형 잡힌 다팩터 접근",
            confidence_threshold=0.5
        )

        # 고변동성 프리셋: 변동성과 퀄리티 강조
        self._presets[MarketRegime.VOLATILE] = RegimeWeightPreset(
            regime=MarketRegime.VOLATILE,
            weights={
                'momentum': 0.05,
                'value': 0.15,
                'quality': 0.25,       # 안정적 기업 선호
                'volume': 0.10,
                'volatility': 0.25,    # 변동성 관리 매우 중요
                'technical': 0.10,
                'market_strength': 0.10
            },
            description="고변동성: 리스크 관리와 안정성 강조",
            confidence_threshold=0.7
        )

        # 회복장 프리셋: 모멘텀 + 가치 조합
        self._presets[MarketRegime.RECOVERY] = RegimeWeightPreset(
            regime=MarketRegime.RECOVERY,
            weights={
                'momentum': 0.20,      # 회복 모멘텀 포착
                'value': 0.20,         # 저평가 종목 기회
                'quality': 0.15,
                'volume': 0.15,        # 거래량 확인 중요
                'volatility': 0.10,
                'technical': 0.10,
                'market_strength': 0.10
            },
            description="회복장: 모멘텀과 가치 균형, 거래량 확인",
            confidence_threshold=0.6
        )

        logger.info(f"기본 레짐 프리셋 {len(self._presets)}개 초기화")

    def _init_default_transition_rules(self):
        """기본 전환 규칙 초기화"""

        # 급격한 전환 (빠르게 대응)
        rapid_transitions = [
            (MarketRegime.BULL_MARKET, MarketRegime.VOLATILE),
            (MarketRegime.SIDEWAYS, MarketRegime.VOLATILE),
            (MarketRegime.RECOVERY, MarketRegime.BEAR_MARKET),
        ]

        for from_r, to_r in rapid_transitions:
            self._transition_rules[(from_r, to_r)] = TransitionRule(
                from_regime=from_r,
                to_regime=to_r,
                transition_speed=0.6,  # 빠른 전환
                min_confidence=0.7,
                cooldown_hours=12
            )

        # 점진적 전환 (천천히 대응)
        gradual_transitions = [
            (MarketRegime.BEAR_MARKET, MarketRegime.RECOVERY),
            (MarketRegime.RECOVERY, MarketRegime.BULL_MARKET),
            (MarketRegime.VOLATILE, MarketRegime.SIDEWAYS),
        ]

        for from_r, to_r in gradual_transitions:
            self._transition_rules[(from_r, to_r)] = TransitionRule(
                from_regime=from_r,
                to_regime=to_r,
                transition_speed=0.2,  # 느린 전환
                min_confidence=0.6,
                cooldown_hours=48
            )

    def get_weights_for_regime(self, regime: MarketRegime) -> Dict[str, float]:
        """
        특정 레짐에 대한 가중치 반환 (C.3.1)

        Args:
            regime: 시장 레짐

        Returns:
            팩터 가중치
        """
        if regime in self._presets:
            return self._presets[regime].weights.copy()

        # 프리셋이 없으면 균등 가중치
        return {f: 1.0 / len(self._factors) for f in self._factors}

    def update_regime(self,
                     regime_result: RegimeResult,
                     force_immediate: bool = False) -> Dict[str, float]:
        """
        레짐 변경에 따른 가중치 업데이트 (C.3.2)

        Args:
            regime_result: 레짐 탐지 결과
            force_immediate: 즉시 전환 강제

        Returns:
            업데이트된 가중치
        """
        new_regime = regime_result.regime
        confidence = regime_result.confidence

        # 첫 번째 레짐 설정
        if self._current_regime is None:
            self._current_regime = new_regime
            self._current_weights = self.get_weights_for_regime(new_regime)
            self._transition_progress = 1.0
            logger.info(f"초기 레짐 설정: {new_regime.value}")
            return self._current_weights.copy()

        # 레짐 변경 없음
        if new_regime == self._current_regime:
            # 진행 중인 전환이 있으면 계속
            if self._transition_progress < 1.0:
                return self._continue_transition()
            return self._current_weights.copy()

        # 레짐 변경 감지
        logger.info(f"레짐 변경 감지: {self._current_regime.value} → {new_regime.value}")

        # 전환 규칙 확인
        transition_key = (self._current_regime, new_regime)
        rule = self._transition_rules.get(transition_key)

        # 신뢰도 검증
        min_confidence = rule.min_confidence if rule else 0.5
        if confidence < min_confidence and not force_immediate:
            logger.info(f"신뢰도 부족으로 전환 보류: {confidence:.2f} < {min_confidence}")
            return self._current_weights.copy()

        # 목표 가중치 설정
        self._target_weights = self.get_weights_for_regime(new_regime)

        # 즉시 전환 또는 점진적 전환
        if force_immediate or not self._enable_smooth_transition:
            self._apply_immediate_transition(new_regime)
        else:
            self._start_gradual_transition(new_regime, rule)

        return self._current_weights.copy()

    def _apply_immediate_transition(self, new_regime: MarketRegime):
        """즉시 전환 적용"""
        # 안전 장치 적용
        safe_weights = self._weight_safety.normalize_weights(self._target_weights)

        # 변경률 제한 적용
        if self._current_weights:
            safe_weights = self._weight_safety.apply_change_limit(
                self._current_weights,
                safe_weights
            )

        self._current_weights = safe_weights
        self._current_regime = new_regime
        self._transition_progress = 1.0

        logger.info(f"레짐 즉시 전환 완료: {new_regime.value}")

    def _start_gradual_transition(self,
                                  new_regime: MarketRegime,
                                  rule: Optional[TransitionRule]):
        """점진적 전환 시작"""
        speed = rule.transition_speed if rule else self._transition_speed

        self._transition_progress = 0.0
        self._pending_regime = new_regime
        self._current_transition_speed = speed

        logger.info(f"점진적 전환 시작: {self._current_regime.value} → {new_regime.value}, 속도: {speed}")

        # 첫 스텝 적용
        self._continue_transition()

    def _continue_transition(self) -> Dict[str, float]:
        """전환 계속 진행"""
        if self._transition_progress >= 1.0:
            return self._current_weights.copy()

        # 진행률 업데이트
        speed = getattr(self, '_current_transition_speed', self._transition_speed)
        self._transition_progress = min(1.0, self._transition_progress + speed)

        # 가중치 보간
        interpolated = {}
        for factor in self._factors:
            current = self._current_weights.get(factor, 0.0)
            target = self._target_weights.get(factor, 0.0)
            interpolated[factor] = current + (target - current) * self._transition_progress

        # 안전 장치 적용
        safe_weights = self._weight_safety.normalize_weights(interpolated)
        self._current_weights = safe_weights

        # 전환 완료 체크
        if self._transition_progress >= 1.0:
            self._current_regime = getattr(self, '_pending_regime', self._current_regime)
            logger.info(f"레짐 전환 완료: {self._current_regime.value}")
        else:
            logger.debug(f"레짐 전환 진행: {self._transition_progress:.0%}")

        return self._current_weights.copy()

    def get_current_weights(self) -> Dict[str, float]:
        """현재 가중치 반환"""
        if not self._current_weights:
            # 기본값: 균등 가중치
            return {f: 1.0 / len(self._factors) for f in self._factors}
        return self._current_weights.copy()

    def get_current_regime(self) -> Optional[MarketRegime]:
        """현재 레짐 반환"""
        return self._current_regime

    def is_transitioning(self) -> bool:
        """전환 중인지 여부"""
        return self._transition_progress < 1.0

    def get_transition_progress(self) -> float:
        """전환 진행률 반환"""
        return self._transition_progress

    def set_custom_preset(self,
                         regime: MarketRegime,
                         weights: Dict[str, float],
                         description: str = "") -> bool:
        """
        커스텀 프리셋 설정

        Args:
            regime: 레짐
            weights: 가중치
            description: 설명

        Returns:
            성공 여부
        """
        # 유효성 검증
        normalized = self._weight_safety.normalize_weights(weights)

        preset = RegimeWeightPreset(
            regime=regime,
            weights=normalized,
            description=description or f"Custom preset for {regime.value}"
        )

        if not preset.validate():
            logger.warning(f"잘못된 프리셋: {regime.value}")
            return False

        self._presets[regime] = preset
        logger.info(f"커스텀 프리셋 설정: {regime.value}")
        return True

    def get_preset_summary(self) -> Dict[str, Any]:
        """프리셋 요약 정보"""
        return {
            regime.value: {
                'weights': preset.weights,
                'description': preset.description,
                'confidence_threshold': preset.confidence_threshold
            }
            for regime, preset in self._presets.items()
        }

    def get_status(self) -> Dict[str, Any]:
        """현재 상태 정보"""
        return {
            'current_regime': self._current_regime.value if self._current_regime else None,
            'current_weights': self._current_weights,
            'is_transitioning': self.is_transitioning(),
            'transition_progress': self._transition_progress,
            'target_weights': self._target_weights if self.is_transitioning() else None,
            'available_presets': list(p.value for p in self._presets.keys()),
            'smooth_transition_enabled': self._enable_smooth_transition,
            'transition_speed': self._transition_speed
        }


# 싱글톤 인스턴스
_mapper_instance: Optional[RegimeStrategyMapper] = None


def get_regime_strategy_mapper() -> RegimeStrategyMapper:
    """RegimeStrategyMapper 싱글톤 인스턴스 반환"""
    global _mapper_instance
    if _mapper_instance is None:
        _mapper_instance = RegimeStrategyMapper()
    return _mapper_instance
