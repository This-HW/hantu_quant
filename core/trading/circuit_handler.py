"""
서킷 브레이커 대응 핸들러

서킷 브레이커 발동 시 TradingEngine과 연동하여 적절한 조치를 취합니다.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from core.risk.drawdown.circuit_breaker import CircuitBreaker, BreakerStatus, BreakerState
from core.notification.notification_manager import NotificationManager
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class CircuitResponse:
    """서킷 브레이커 대응 결과"""
    action: str  # REDUCE, HALT, RECOVER
    position_limit: float  # 0.0 ~ 1.0
    affected_positions: List[str]  # 영향받는 포지션 목록
    message: str
    timestamp: datetime


class CircuitHandler:
    """
    서킷 브레이커 대응 핸들러

    서킷 브레이커 발동 시 TradingEngine과 연동하여 적절한 조치를 취합니다.
    """

    def __init__(
        self,
        trading_engine: Optional[Any] = None,
        notification_manager: Optional[NotificationManager] = None
    ):
        """
        초기화

        Args:
            trading_engine: TradingEngine 인스턴스 (순환 참조 방지를 위해 Optional)
            notification_manager: 알림 관리자
        """
        self.trading_engine = trading_engine
        self.notification_manager = notification_manager

        # 최근 대응 이력
        self._response_history: List[CircuitResponse] = []

        logger.info("서킷 브레이커 핸들러 초기화 완료")

    def set_trading_engine(self, trading_engine: Any):
        """TradingEngine 설정 (지연 초기화)"""
        self.trading_engine = trading_engine
        logger.info("TradingEngine 연동 완료")

    def handle_circuit_event(self, breaker_status: BreakerStatus) -> CircuitResponse:
        """
        서킷 브레이커 이벤트 처리

        Args:
            breaker_status: 브레이커 상태

        Returns:
            CircuitResponse: 대응 결과
        """
        try:
            now = datetime.now()

            # 상태별 처리
            if breaker_status.state == BreakerState.ACTIVE:
                return self._handle_normal_state(breaker_status, now)

            elif breaker_status.state in [BreakerState.TRIGGERED, BreakerState.COOLDOWN]:
                return self._handle_triggered_state(breaker_status, now)

            else:
                logger.warning(f"알 수 없는 브레이커 상태: {breaker_status.state}")
                return CircuitResponse(
                    action="NONE",
                    position_limit=1.0,
                    affected_positions=[],
                    message=f"알 수 없는 상태: {breaker_status.state}",
                    timestamp=now
                )

        except Exception as e:
            logger.error(f"서킷 브레이커 이벤트 처리 실패: {e}", exc_info=True)
            return CircuitResponse(
                action="ERROR",
                position_limit=0.0,
                affected_positions=[],
                message=f"처리 실패: {e}",
                timestamp=datetime.now()
            )

    def _handle_normal_state(
        self,
        breaker_status: BreakerStatus,
        now: datetime
    ) -> CircuitResponse:
        """정상 상태 처리"""
        response = CircuitResponse(
            action="RECOVER",
            position_limit=1.0,
            affected_positions=[],
            message="정상 거래 재개",
            timestamp=now
        )

        self._record_response(response)

        # 정상 복구 알림
        if self.notification_manager:
            self.notify_circuit_status(breaker_status)

        logger.info("서킷 브레이커 정상 상태 - 거래 제한 없음")

        return response

    def _handle_triggered_state(
        self,
        breaker_status: BreakerStatus,
        now: datetime
    ) -> CircuitResponse:
        """발동/쿨다운 상태 처리"""
        stage = breaker_status.current_stage

        # Stage별 조치
        if stage == 1:
            return self._handle_stage1(breaker_status, now)
        elif stage == 2:
            return self._handle_stage2(breaker_status, now)
        elif stage >= 3:
            return self._handle_stage3(breaker_status, now)
        else:
            logger.warning(f"알 수 없는 Stage: {stage}")
            return CircuitResponse(
                action="NONE",
                position_limit=1.0,
                affected_positions=[],
                message=f"알 수 없는 Stage: {stage}",
                timestamp=now
            )

    def _handle_stage1(
        self,
        breaker_status: BreakerStatus,
        now: datetime
    ) -> CircuitResponse:
        """Stage 1: 신규 매수 50% 제한"""
        position_limit = 0.50  # 50% 제한
        affected = []

        # TradingEngine이 설정되어 있으면 포지션 정보 수집
        if self.trading_engine:
            try:
                affected = self._get_current_positions()
            except Exception as e:
                logger.warning(f"포지션 정보 조회 실패: {e}", exc_info=True)

        response = CircuitResponse(
            action="REDUCE",
            position_limit=position_limit,
            affected_positions=affected,
            message=f"Stage 1 발동 - 신규 매수 {position_limit:.0%} 제한",
            timestamp=now
        )

        self._record_response(response)

        # 알림 발송
        if self.notification_manager:
            self.notify_circuit_status(breaker_status)

        logger.warning(
            f"서킷 브레이커 Stage 1 - 신규 매수 {position_limit:.0%} 제한, "
            f"사유: {breaker_status.trigger_reason}"
        )

        return response

    def _handle_stage2(
        self,
        breaker_status: BreakerStatus,
        now: datetime
    ) -> CircuitResponse:
        """Stage 2: 신규 매수 75% 제한"""
        position_limit = 0.25  # 75% 제한 (25%만 가능)
        affected = []

        if self.trading_engine:
            try:
                affected = self._get_current_positions()
            except Exception as e:
                logger.warning(f"포지션 정보 조회 실패: {e}", exc_info=True)

        response = CircuitResponse(
            action="REDUCE",
            position_limit=position_limit,
            affected_positions=affected,
            message=f"Stage 2 발동 - 신규 매수 {1-position_limit:.0%} 제한",
            timestamp=now
        )

        self._record_response(response)

        # 알림 발송
        if self.notification_manager:
            self.notify_circuit_status(breaker_status)

        logger.warning(
            f"서킷 브레이커 Stage 2 - 신규 매수 {1-position_limit:.0%} 제한, "
            f"사유: {breaker_status.trigger_reason}"
        )

        return response

    def _handle_stage3(
        self,
        breaker_status: BreakerStatus,
        now: datetime
    ) -> CircuitResponse:
        """Stage 3: 신규 매수 금지 + 기존 포지션 리스크 관리"""
        position_limit = 0.0  # 전면 금지
        affected = []

        if self.trading_engine:
            try:
                affected = self._get_current_positions()
            except Exception as e:
                logger.warning(f"포지션 정보 조회 실패: {e}", exc_info=True)

        response = CircuitResponse(
            action="HALT",
            position_limit=position_limit,
            affected_positions=affected,
            message="Stage 3 발동 - 신규 매수 금지",
            timestamp=now
        )

        self._record_response(response)

        # 긴급 알림 발송
        if self.notification_manager:
            self.notify_circuit_status(breaker_status)

        logger.error(
            f"서킷 브레이커 Stage 3 - 신규 매수 전면 금지, "
            f"사유: {breaker_status.trigger_reason}"
        )

        return response

    def apply_position_reduction(self, reduction_rate: float) -> List[str]:
        """
        포지션 축소 적용

        Args:
            reduction_rate: 축소 비율 (0.0 ~ 1.0)

        Returns:
            List[str]: 축소된 포지션 종목 코드 목록
        """
        if not self.trading_engine:
            logger.warning("TradingEngine이 설정되지 않아 포지션 축소 불가")
            return []

        try:
            # TradingEngine의 포지션 정보 조회
            positions = self._get_current_positions()

            if not positions:
                logger.info("축소할 포지션이 없습니다")
                return []

            reduced = []

            # TODO: 실제 포지션 축소 로직 구현
            # 현재는 로깅만 수행 (Phase 3 구현 시 실제 매도 실행)
            logger.warning(
                f"포지션 축소 요청: {reduction_rate:.0%} - "
                f"대상: {len(positions)}개 종목"
            )

            for stock_code in positions:
                logger.info(f"축소 대상: {stock_code}")
                reduced.append(stock_code)

            return reduced

        except Exception as e:
            logger.error(f"포지션 축소 실패: {e}", exc_info=True)
            return []

    def notify_circuit_status(self, status: BreakerStatus) -> bool:
        """
        서킷 브레이커 상태 알림

        Args:
            status: 브레이커 상태

        Returns:
            bool: 알림 성공 여부
        """
        if not self.notification_manager:
            logger.debug("NotificationManager가 설정되지 않음")
            return False

        try:
            self.notification_manager.notify_circuit_breaker(
                reason=status.trigger_reason or "서킷 브레이커 상태 변경",
                triggered_at=status.triggered_at or datetime.now(),
                cooldown_until=status.cooldown_until
            )

            logger.info("서킷 브레이커 알림 발송 완료")
            return True

        except Exception as e:
            logger.error(f"서킷 브레이커 알림 발송 실패: {e}", exc_info=True)
            return False

    def get_current_restrictions(self) -> Dict[str, Any]:
        """
        현재 거래 제한 정보 조회

        Returns:
            Dict: 제한 정보
        """
        if not self._response_history:
            return {
                "active": False,
                "action": "NONE",
                "position_limit": 1.0,
                "message": "제한 없음"
            }

        latest = self._response_history[-1]

        return {
            "active": latest.action in ["REDUCE", "HALT"],
            "action": latest.action,
            "position_limit": latest.position_limit,
            "message": latest.message,
            "timestamp": latest.timestamp.isoformat(),
            "affected_positions_count": len(latest.affected_positions)
        }

    def _get_current_positions(self) -> List[str]:
        """현재 보유 포지션 종목 코드 목록 조회"""
        if not self.trading_engine:
            return []

        try:
            # TradingEngine의 positions 속성 접근
            if hasattr(self.trading_engine, 'positions'):
                return list(self.trading_engine.positions.keys())
            else:
                logger.warning("TradingEngine에 positions 속성이 없습니다")
                return []

        except Exception as e:
            logger.error(f"포지션 조회 실패: {e}", exc_info=True)
            return []

    def _record_response(self, response: CircuitResponse):
        """대응 이력 기록"""
        self._response_history.append(response)

        # 최근 100개만 유지
        if len(self._response_history) > 100:
            self._response_history = self._response_history[-100:]

    def get_response_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        대응 이력 조회

        Args:
            limit: 조회 개수

        Returns:
            List[Dict]: 이력 목록
        """
        recent = self._response_history[-limit:]

        return [
            {
                "action": r.action,
                "position_limit": r.position_limit,
                "affected_positions_count": len(r.affected_positions),
                "message": r.message,
                "timestamp": r.timestamp.isoformat()
            }
            for r in recent
        ]
