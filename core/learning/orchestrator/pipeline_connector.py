"""
파이프라인 연결기

Task D.2.1: 워크플로우 연결
Task D.2.2: MultiFactorScorer 통합
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from datetime import datetime

from core.learning.weights.weight_provider import (
    WeightProvider,
    HybridWeightProvider,
    get_hybrid_weight_provider
)
from core.learning.regime.regime_detector import RegimeDetector, get_regime_detector
from core.learning.regime.regime_strategy_mapper import RegimeStrategyMapper, get_regime_strategy_mapper
from core.learning.models.feedback_system import FeedbackSystem, get_feedback_system
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineState:
    """파이프라인 상태"""
    is_connected: bool = False
    last_update: Optional[str] = None
    current_weights: Optional[Dict[str, float]] = None
    current_regime: Optional[str] = None
    error: Optional[str] = None


class PipelineConnector:
    """
    파이프라인 연결기 (D.2.1, D.2.2)

    학습 시스템과 기존 파이프라인(워크플로우, MultiFactorScorer)을 연결합니다.
    """

    def __init__(self):
        """초기화"""
        self._weight_provider: Optional[WeightProvider] = None
        self._regime_detector: Optional[RegimeDetector] = None
        self._strategy_mapper: Optional[RegimeStrategyMapper] = None
        self._feedback_system: Optional[FeedbackSystem] = None

        self._state = PipelineState()
        self._connected_scorers: List[Any] = []
        self._hooks: Dict[str, List[Callable]] = {
            'pre_scoring': [],
            'post_scoring': [],
            'on_selection': [],
            'on_trade_result': [],
        }

        logger.info("PipelineConnector 초기화")

    def connect(self) -> bool:
        """
        파이프라인 연결 (D.2.1)

        Returns:
            연결 성공 여부
        """
        try:
            # 구성 요소 초기화
            self._weight_provider = get_hybrid_weight_provider()
            self._regime_detector = get_regime_detector()
            self._strategy_mapper = get_regime_strategy_mapper()
            self._feedback_system = get_feedback_system()

            # 연결 상태 업데이트
            self._state.is_connected = True
            self._state.last_update = datetime.now().isoformat()
            self._state.current_weights = self._weight_provider.get_weights()

            logger.info("파이프라인 연결 완료")
            return True

        except Exception as e:
            self._state.is_connected = False
            self._state.error = str(e)
            logger.error(f"파이프라인 연결 실패: {e}")
            return False

    def disconnect(self):
        """파이프라인 연결 해제"""
        self._state.is_connected = False
        self._connected_scorers.clear()
        logger.info("파이프라인 연결 해제")

    def integrate_multi_factor_scorer(self, scorer: Any) -> bool:
        """
        MultiFactorScorer 통합 (D.2.2)

        Args:
            scorer: MultiFactorScorer 인스턴스

        Returns:
            통합 성공 여부
        """
        if not self._state.is_connected:
            logger.warning("파이프라인이 연결되지 않았습니다")
            return False

        try:
            # WeightProvider 설정
            if hasattr(scorer, 'set_weight_provider'):
                scorer.set_weight_provider(self._weight_provider)
                logger.info("MultiFactorScorer에 WeightProvider 연결")

            # 동적 가중치 활성화
            if hasattr(scorer, 'enable_dynamic_weights'):
                scorer.enable_dynamic_weights(True)
                logger.info("MultiFactorScorer 동적 가중치 활성화")

            # 연결된 스코어러 목록에 추가
            self._connected_scorers.append(scorer)

            return True

        except Exception as e:
            logger.error(f"MultiFactorScorer 통합 실패: {e}")
            return False

    def get_current_weights(self) -> Dict[str, float]:
        """
        현재 가중치 반환 (D.2.2)

        Returns:
            현재 팩터 가중치
        """
        if not self._state.is_connected or not self._weight_provider:
            # 기본 가중치 반환
            return {
                'momentum': 0.15,
                'value': 0.15,
                'quality': 0.15,
                'volume': 0.15,
                'volatility': 0.10,
                'technical': 0.15,
                'market_strength': 0.15
            }

        return self._weight_provider.get_weights()

    def update_regime(self) -> Optional[str]:
        """
        레짐 업데이트 및 가중치 조정

        Returns:
            현재 레짐 (없으면 None)
        """
        if not self._state.is_connected:
            return None

        try:
            # 레짐 탐지
            regime_result = self._regime_detector.detect()

            # 전략 매퍼에 반영
            new_weights = self._strategy_mapper.update_regime(regime_result)

            # 상태 업데이트
            self._state.current_regime = regime_result.regime.value
            self._state.current_weights = new_weights
            self._state.last_update = datetime.now().isoformat()

            # 연결된 스코어러들 가중치 업데이트
            self._notify_scorers_weight_update(new_weights)

            return regime_result.regime.value

        except Exception as e:
            logger.error(f"레짐 업데이트 오류: {e}")
            return None

    def _notify_scorers_weight_update(self, weights: Dict[str, float]):
        """스코어러들에게 가중치 업데이트 알림"""
        for scorer in self._connected_scorers:
            try:
                if hasattr(scorer, 'update_weights'):
                    scorer.update_weights(weights)
            except Exception as e:
                logger.warning(f"스코어러 가중치 업데이트 실패: {e}")

    def record_selection(self,
                        stock_code: str,
                        score: float,
                        factor_scores: Dict[str, float],
                        ranking: int,
                        metadata: Optional[Dict] = None) -> str:
        """
        종목 선정 기록 (피드백 수집용)

        Args:
            stock_code: 종목 코드
            score: 총점
            factor_scores: 팩터별 점수
            ranking: 순위
            metadata: 추가 메타데이터

        Returns:
            피드백 ID
        """
        if not self._state.is_connected or not self._feedback_system:
            return ""

        try:
            # 피드백 기록
            feedback_id = self._feedback_system.record_prediction(
                stock_code=stock_code,
                predicted_return=score / 100,  # 점수를 수익률로 변환
                confidence=min(score / 100, 1.0),
                model_version="multi_factor_v1",
                factor_scores=factor_scores,
                metadata={
                    **(metadata or {}),
                    'ranking': ranking,
                    'regime': self._state.current_regime,
                    'weights_used': self._state.current_weights
                }
            )

            # 훅 호출
            self._trigger_hooks('on_selection', {
                'stock_code': stock_code,
                'score': score,
                'feedback_id': feedback_id
            })

            return feedback_id

        except Exception as e:
            logger.error(f"선정 기록 실패: {e}")
            return ""

    def record_trade_result(self,
                           feedback_id: str,
                           actual_return: float,
                           trade_metadata: Optional[Dict] = None) -> bool:
        """
        거래 결과 기록

        Args:
            feedback_id: 피드백 ID
            actual_return: 실제 수익률
            trade_metadata: 거래 메타데이터

        Returns:
            성공 여부
        """
        if not self._state.is_connected or not self._feedback_system:
            return False

        try:
            success = self._feedback_system.update_actual_result(
                feedback_id=feedback_id,
                actual_return=actual_return,
                exit_reason="trade_closed"
            )

            if success:
                self._trigger_hooks('on_trade_result', {
                    'feedback_id': feedback_id,
                    'actual_return': actual_return
                })

            return success

        except Exception as e:
            logger.error(f"거래 결과 기록 실패: {e}")
            return False

    def register_hook(self, event: str, callback: Callable):
        """훅 등록"""
        if event in self._hooks:
            self._hooks[event].append(callback)

    def _trigger_hooks(self, event: str, data: Any):
        """훅 트리거"""
        for hook in self._hooks.get(event, []):
            try:
                hook(data)
            except Exception as e:
                logger.warning(f"훅 실행 오류: {e}")

    def get_state(self) -> Dict[str, Any]:
        """상태 정보"""
        return {
            'is_connected': self._state.is_connected,
            'last_update': self._state.last_update,
            'current_regime': self._state.current_regime,
            'current_weights': self._state.current_weights,
            'connected_scorers_count': len(self._connected_scorers),
            'error': self._state.error
        }

    def is_ready(self) -> bool:
        """사용 준비 상태 확인"""
        return (
            self._state.is_connected and
            self._weight_provider is not None and
            self._weight_provider.is_available()
        )


# 싱글톤 인스턴스
_connector_instance: Optional[PipelineConnector] = None


def get_pipeline_connector() -> PipelineConnector:
    """PipelineConnector 싱글톤 인스턴스 반환"""
    global _connector_instance
    if _connector_instance is None:
        _connector_instance = PipelineConnector()
    return _connector_instance


def connect_learning_pipeline(scorer: Any = None) -> PipelineConnector:
    """
    학습 파이프라인 연결 헬퍼 함수

    Args:
        scorer: 연결할 MultiFactorScorer (옵션)

    Returns:
        연결된 PipelineConnector
    """
    connector = get_pipeline_connector()

    if not connector._state.is_connected:
        connector.connect()

    if scorer:
        connector.integrate_multi_factor_scorer(scorer)

    return connector
