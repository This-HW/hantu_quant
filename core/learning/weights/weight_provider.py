"""
가중치 제공자 인터페이스

Task B.2.3: MultiFactorScorer 동적 가중치 적용을 위한 인터페이스
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
from datetime import datetime

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class WeightProvider(ABC):
    """가중치 제공자 추상 클래스"""

    @abstractmethod
    def get_weights(self) -> Dict[str, float]:
        """
        현재 가중치 반환

        Returns:
            팩터별 가중치 딕셔너리
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        가중치 제공 가능 여부

        Returns:
            제공 가능 여부
        """
        pass


class StaticWeightProvider(WeightProvider):
    """정적 가중치 제공자 (기존 방식 호환)"""

    DEFAULT_WEIGHTS = {
        'momentum': 0.20,
        'value': 0.15,
        'quality': 0.20,
        'volume': 0.15,
        'volatility': 0.10,
        'technical': 0.15,
        'market_strength': 0.05
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self._weights = weights or self.DEFAULT_WEIGHTS.copy()

    def get_weights(self) -> Dict[str, float]:
        return self._weights.copy()

    def is_available(self) -> bool:
        return True


class DynamicWeightProvider(WeightProvider):
    """동적 가중치 제공자"""

    def __init__(self):
        self._calculator = None
        self._initialized = False

    def _ensure_initialized(self):
        """지연 초기화 (순환 참조 방지)"""
        if not self._initialized:
            try:
                from .dynamic_weight_calculator import get_dynamic_weight_calculator
                self._calculator = get_dynamic_weight_calculator()
                self._initialized = True
            except Exception as e:
                logger.warning(f"DynamicWeightCalculator 초기화 실패: {e}")
                self._initialized = False

    def get_weights(self) -> Dict[str, float]:
        self._ensure_initialized()

        if self._calculator:
            return self._calculator.current_weights
        else:
            # 폴백: 기본 가중치
            return StaticWeightProvider.DEFAULT_WEIGHTS.copy()

    def is_available(self) -> bool:
        self._ensure_initialized()
        return self._calculator is not None


class RegimeAwareWeightProvider(WeightProvider):
    """레짐 인식 가중치 제공자"""

    # 레짐별 가중치 프리셋
    REGIME_PRESETS = {
        'bull_market': {
            'momentum': 0.25,
            'value': 0.10,
            'quality': 0.15,
            'volume': 0.15,
            'volatility': 0.10,
            'technical': 0.20,
            'market_strength': 0.05
        },
        'bear_market': {
            'momentum': 0.10,
            'value': 0.25,
            'quality': 0.25,
            'volume': 0.10,
            'volatility': 0.15,
            'technical': 0.10,
            'market_strength': 0.05
        },
        'sideways': {
            'momentum': 0.15,
            'value': 0.20,
            'quality': 0.20,
            'volume': 0.15,
            'volatility': 0.10,
            'technical': 0.15,
            'market_strength': 0.05
        },
        'volatile': {
            'momentum': 0.10,
            'value': 0.15,
            'quality': 0.25,
            'volume': 0.10,
            'volatility': 0.20,
            'technical': 0.15,
            'market_strength': 0.05
        },
        'recovery': {
            'momentum': 0.25,
            'value': 0.15,
            'quality': 0.15,
            'volume': 0.20,
            'volatility': 0.05,
            'technical': 0.15,
            'market_strength': 0.05
        }
    }

    def __init__(self):
        self._regime_detector = None
        self._current_regime = 'sideways'
        self._initialized = False

    def _ensure_initialized(self):
        """지연 초기화"""
        if not self._initialized:
            try:
                from core.learning.regime.regime_detector import get_regime_detector
                self._regime_detector = get_regime_detector()
                self._initialized = True
            except Exception as e:
                logger.warning(f"RegimeDetector 초기화 실패: {e}")

    def get_weights(self) -> Dict[str, float]:
        self._ensure_initialized()

        # 현재 레짐 확인
        if self._regime_detector:
            regime = self._regime_detector.get_current_regime()
            if regime:
                self._current_regime = regime.value

        # 레짐에 맞는 가중치 반환
        return self.REGIME_PRESETS.get(
            self._current_regime,
            self.REGIME_PRESETS['sideways']
        ).copy()

    def is_available(self) -> bool:
        self._ensure_initialized()
        return True


class HybridWeightProvider(WeightProvider):
    """하이브리드 가중치 제공자 (동적 + 레짐 인식)"""

    def __init__(self, dynamic_weight: float = 0.6, regime_weight: float = 0.4):
        """
        초기화

        Args:
            dynamic_weight: 동적 가중치 비중
            regime_weight: 레짐 가중치 비중
        """
        if abs(dynamic_weight + regime_weight - 1.0) > 0.01:
            raise ValueError("dynamic_weight + regime_weight must equal 1.0")

        self._dynamic_weight = dynamic_weight
        self._regime_weight = regime_weight

        self._dynamic_provider = DynamicWeightProvider()
        self._regime_provider = RegimeAwareWeightProvider()

    def get_weights(self) -> Dict[str, float]:
        dynamic_weights = self._dynamic_provider.get_weights()
        regime_weights = self._regime_provider.get_weights()

        # 가중 평균
        combined = {}
        all_keys = set(dynamic_weights.keys()) | set(regime_weights.keys())

        for key in all_keys:
            dw = dynamic_weights.get(key, 0)
            rw = regime_weights.get(key, 0)
            combined[key] = dw * self._dynamic_weight + rw * self._regime_weight

        # 합계 정규화
        total = sum(combined.values())
        if total > 0:
            combined = {k: v / total for k, v in combined.items()}

        return combined

    def is_available(self) -> bool:
        return (self._dynamic_provider.is_available() or
                self._regime_provider.is_available())


# 전역 인스턴스 관리
_default_provider: Optional[WeightProvider] = None


def get_weight_provider(provider_type: str = "dynamic") -> WeightProvider:
    """
    가중치 제공자 인스턴스 반환

    Args:
        provider_type: "static", "dynamic", "regime", "hybrid"

    Returns:
        WeightProvider 인스턴스
    """
    if provider_type == "static":
        return StaticWeightProvider()
    elif provider_type == "dynamic":
        return DynamicWeightProvider()
    elif provider_type == "regime":
        return RegimeAwareWeightProvider()
    elif provider_type == "hybrid":
        return HybridWeightProvider()
    else:
        logger.warning(f"알 수 없는 provider_type: {provider_type}, dynamic 사용")
        return DynamicWeightProvider()


def get_default_weight_provider() -> WeightProvider:
    """기본 가중치 제공자 반환"""
    global _default_provider
    if _default_provider is None:
        _default_provider = HybridWeightProvider()
    return _default_provider


def set_default_weight_provider(provider: WeightProvider):
    """기본 가중치 제공자 설정"""
    global _default_provider
    _default_provider = provider


def get_hybrid_weight_provider() -> HybridWeightProvider:
    """HybridWeightProvider 인스턴스 반환"""
    return HybridWeightProvider()
