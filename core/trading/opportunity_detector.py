"""
추가 매수 기회 감지 모듈 (물타기 전략)

기존 포지션의 추가 매수(평균 단가 낮추기) 기회를 감지합니다.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

from core.utils.log_utils import get_logger
from core.daily_selection.price_analyzer import TechnicalIndicators

logger = get_logger(__name__)


@dataclass
class OpportunityConfig:
    """추가 매수 감지 설정"""

    # 하락률 조건
    min_drop_rate: float = 0.05  # 평균 단가 대비 최소 하락률 (5%)
    max_drop_rate: float = 0.20  # 최대 하락률 (20%, 이상 하락 시 문제 있는 종목으로 판단)

    # RSI 조건
    rsi_threshold: float = 30.0  # RSI 과매도 임계값

    # 추가 매수 제한
    max_additional_buys: int = 2  # 최대 추가 매수 횟수
    first_add_ratio: float = 0.50  # 1차 추가: 원래 포지션의 50%
    second_add_ratio: float = 0.25  # 2차 추가: 원래 포지션의 25%

    # 안전 장치
    min_hold_days: int = 1  # 최소 보유 일수 (당일 매수 후 추가 매수 금지)
    cooldown_hours: int = 24  # 추가 매수 후 재추가 대기 시간 (시간)


@dataclass
class AdditionalBuyOpportunity:
    """추가 매수 기회 정보"""

    stock_code: str
    stock_name: str
    current_price: float
    average_price: float
    drop_rate: float  # 하락률 (예: 0.07 = 7% 하락)
    rsi: Optional[float]  # RSI 값 (있을 경우)
    buy_count: int  # 현재 추가 매수 횟수 (0, 1, 2)
    recommended_quantity: int  # 권장 추가 매수 수량
    recommended_amount: float  # 권장 추가 매수 금액
    reason: str  # 추가 매수 이유
    confidence: float  # 신뢰도 (0.0 ~ 1.0)

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "current_price": self.current_price,
            "average_price": self.average_price,
            "drop_rate": self.drop_rate,
            "rsi": self.rsi,
            "buy_count": self.buy_count,
            "recommended_quantity": self.recommended_quantity,
            "recommended_amount": self.recommended_amount,
            "reason": self.reason,
            "confidence": self.confidence,
        }


class OpportunityDetector:
    """추가 매수 기회 감지기"""

    def __init__(self, p_config: Optional[OpportunityConfig] = None):
        """초기화

        Args:
            p_config: 추가 매수 감지 설정 (None이면 기본값 사용)
        """
        self.config = p_config or OpportunityConfig()
        self.logger = logger

        # 추가 매수 이력 (stock_code -> 추가 매수 횟수)
        self._buy_history: Dict[str, int] = {}

        # 마지막 추가 매수 시간 (stock_code -> datetime)
        self._last_buy_time: Dict[str, datetime] = {}

        self.logger.info("OpportunityDetector 초기화 완료")

    def detect_additional_buy(
        self,
        p_position: Dict,
        p_current_price: float,
        p_rsi: Optional[float] = None,
    ) -> Optional[AdditionalBuyOpportunity]:
        """단일 포지션에 대한 추가 매수 기회 감지

        Args:
            p_position: 포지션 정보 (stock_code, stock_name, quantity, avg_price, entry_time 등)
            p_current_price: 현재가
            p_rsi: RSI 값 (선택)

        Returns:
            AdditionalBuyOpportunity 또는 None (추가 매수 기회 없음)
        """
        try:
            stock_code = p_position.get("stock_code", "")
            stock_name = p_position.get("stock_name", stock_code)
            avg_price = p_position.get("avg_price", 0.0)
            quantity = p_position.get("quantity", 0)
            entry_time = p_position.get("entry_time", None)

            # === 1. 기본 검증 ===
            if avg_price <= 0 or p_current_price <= 0:
                self.logger.debug(
                    f"{stock_code}: 가격 정보 부족 (avg={avg_price}, current={p_current_price})"
                )
                return None

            # === 2. 하락률 계산 ===
            drop_rate = (avg_price - p_current_price) / avg_price

            # 하락률이 최소 조건 미달
            if drop_rate < self.config.min_drop_rate:
                self.logger.debug(
                    f"{stock_code}: 하락률 부족 ({drop_rate:.2%} < {self.config.min_drop_rate:.2%})"
                )
                return None

            # 하락률이 너무 높음 (문제 있는 종목)
            if drop_rate > self.config.max_drop_rate:
                self.logger.warning(
                    f"{stock_code}: 하락률 초과 ({drop_rate:.2%} > {self.config.max_drop_rate:.2%}). "
                    "문제가 있는 종목일 수 있음"
                )
                return None

            # === 3. RSI 조건 확인 (선택) ===
            if p_rsi is not None and p_rsi >= self.config.rsi_threshold:
                self.logger.debug(
                    f"{stock_code}: RSI 과매도 아님 (RSI={p_rsi:.1f} >= {self.config.rsi_threshold})"
                )
                return None

            # === 4. 추가 매수 횟수 제한 ===
            buy_count = self._buy_history.get(stock_code, 0)
            if buy_count >= self.config.max_additional_buys:
                self.logger.debug(
                    f"{stock_code}: 최대 추가 매수 횟수 초과 ({buy_count}/{self.config.max_additional_buys})"
                )
                return None

            # === 5. 보유 일수 확인 ===
            if entry_time:
                try:
                    entry_dt = (
                        datetime.fromisoformat(entry_time)
                        if isinstance(entry_time, str)
                        else entry_time
                    )
                    hold_days = (datetime.now() - entry_dt).days

                    if hold_days < self.config.min_hold_days:
                        self.logger.debug(
                            f"{stock_code}: 최소 보유 일수 미달 ({hold_days}일 < {self.config.min_hold_days}일)"
                        )
                        return None
                except Exception as e:
                    self.logger.warning(
                        f"{stock_code}: entry_time 파싱 실패: {e}", exc_info=True
                    )

            # === 6. 쿨다운 확인 (마지막 추가 매수 후 대기 시간) ===
            last_buy_time = self._last_buy_time.get(stock_code)
            if last_buy_time:
                hours_since_last_buy = (
                    datetime.now() - last_buy_time
                ).total_seconds() / 3600
                if hours_since_last_buy < self.config.cooldown_hours:
                    self.logger.debug(
                        f"{stock_code}: 쿨다운 중 ({hours_since_last_buy:.1f}시간 < {self.config.cooldown_hours}시간)"
                    )
                    return None

            # === 7. 추가 매수 수량 및 금액 계산 ===
            if buy_count == 0:
                # 1차 추가 매수: 원래 포지션의 50%
                add_quantity = int(quantity * self.config.first_add_ratio)
            elif buy_count == 1:
                # 2차 추가 매수: 원래 포지션의 25%
                add_quantity = int(quantity * self.config.second_add_ratio)
            else:
                # 이 경우는 발생하지 않아야 함 (위에서 제한)
                add_quantity = 0

            # 최소 1주는 매수
            add_quantity = max(1, add_quantity)
            add_amount = add_quantity * p_current_price

            # === 8. 추가 매수 이유 생성 ===
            reason_parts = [
                f"평균가 대비 {drop_rate:.1%} 하락",
            ]
            if p_rsi is not None:
                reason_parts.append(f"RSI {p_rsi:.1f} 과매도")
            reason_parts.append(f"{buy_count + 1}차 추가 매수")
            reason = " + ".join(reason_parts)

            # === 9. 신뢰도 계산 ===
            confidence = self._calculate_confidence(drop_rate, p_rsi)

            # === 10. 결과 반환 ===
            opportunity = AdditionalBuyOpportunity(
                stock_code=stock_code,
                stock_name=stock_name,
                current_price=p_current_price,
                average_price=avg_price,
                drop_rate=drop_rate,
                rsi=p_rsi,
                buy_count=buy_count,
                recommended_quantity=add_quantity,
                recommended_amount=add_amount,
                reason=reason,
                confidence=confidence,
            )

            self.logger.info(
                f"추가 매수 기회 감지: {stock_code} - {reason} (신뢰도: {confidence:.2f})"
            )

            return opportunity

        except Exception as e:
            self.logger.error(
                f"추가 매수 기회 감지 실패: {p_position.get('stock_code', 'Unknown')}: {e}",
                exc_info=True,
            )
            return None

    def get_opportunities(
        self, p_positions: List[Dict], p_price_data: Dict[str, float]
    ) -> List[AdditionalBuyOpportunity]:
        """여러 포지션에 대한 추가 매수 기회 목록 조회

        Args:
            p_positions: 포지션 목록 (각 포지션은 Dict 형태)
            p_price_data: 현재가 데이터 (stock_code -> current_price)

        Returns:
            추가 매수 기회 목록 (신뢰도 순으로 정렬)
        """
        opportunities = []

        for position in p_positions:
            try:
                stock_code = position.get("stock_code", "")
                current_price = p_price_data.get(stock_code, 0.0)

                if current_price <= 0:
                    self.logger.warning(f"{stock_code}: 현재가 정보 없음")
                    continue

                # RSI 계산 (recent_close_prices가 있으면)
                rsi = None
                recent_prices = position.get("recent_close_prices", [])
                if recent_prices and len(recent_prices) >= 15:
                    try:
                        rsi = TechnicalIndicators.calculate_rsi(recent_prices)
                    except Exception as e:
                        self.logger.debug(
                            f"{stock_code}: RSI 계산 실패: {e}", exc_info=True
                        )

                # 추가 매수 기회 감지
                opportunity = self.detect_additional_buy(
                    p_position=position, p_current_price=current_price, p_rsi=rsi
                )

                if opportunity:
                    opportunities.append(opportunity)

            except Exception as e:
                self.logger.error(
                    f"포지션 처리 실패: {position.get('stock_code', 'Unknown')}: {e}",
                    exc_info=True,
                )
                continue

        # 신뢰도 순으로 정렬
        opportunities.sort(key=lambda x: x.confidence, reverse=True)

        self.logger.info(
            f"추가 매수 기회 총 {len(opportunities)}건 감지 (포지션: {len(p_positions)}개)"
        )

        return opportunities

    def record_additional_buy(self, p_stock_code: str) -> None:
        """추가 매수 실행 기록

        Args:
            p_stock_code: 종목 코드
        """
        try:
            # 추가 매수 횟수 증가
            current_count = self._buy_history.get(p_stock_code, 0)
            self._buy_history[p_stock_code] = current_count + 1

            # 마지막 추가 매수 시간 기록
            self._last_buy_time[p_stock_code] = datetime.now()

            self.logger.info(
                f"추가 매수 기록: {p_stock_code} - {self._buy_history[p_stock_code]}차"
            )

        except Exception as e:
            self.logger.error(
                f"추가 매수 기록 실패: {p_stock_code}: {e}", exc_info=True
            )

    def reset_buy_history(self, p_stock_code: Optional[str] = None) -> None:
        """추가 매수 이력 초기화

        Args:
            p_stock_code: 종목 코드 (None이면 전체 초기화)
        """
        try:
            if p_stock_code:
                # 특정 종목 초기화
                if p_stock_code in self._buy_history:
                    del self._buy_history[p_stock_code]
                if p_stock_code in self._last_buy_time:
                    del self._last_buy_time[p_stock_code]
                self.logger.info(f"추가 매수 이력 초기화: {p_stock_code}")
            else:
                # 전체 초기화
                self._buy_history.clear()
                self._last_buy_time.clear()
                self.logger.info("전체 추가 매수 이력 초기화")

        except Exception as e:
            self.logger.error(f"추가 매수 이력 초기화 실패: {e}", exc_info=True)

    def _calculate_confidence(
        self, p_drop_rate: float, p_rsi: Optional[float]
    ) -> float:
        """신뢰도 계산

        Args:
            p_drop_rate: 하락률
            p_rsi: RSI 값

        Returns:
            신뢰도 (0.0 ~ 1.0)
        """
        try:
            # 기본 신뢰도: 하락률이 클수록 높음 (5% ~ 20% 범위)
            drop_confidence = min(
                (p_drop_rate - self.config.min_drop_rate)
                / (self.config.max_drop_rate - self.config.min_drop_rate),
                1.0,
            )

            # RSI 신뢰도: RSI가 낮을수록 높음
            if p_rsi is not None:
                rsi_confidence = max(0.0, (self.config.rsi_threshold - p_rsi) / 30.0)
                # 가중 평균 (하락률 60%, RSI 40%)
                confidence = drop_confidence * 0.6 + rsi_confidence * 0.4
            else:
                # RSI 없으면 하락률만 사용
                confidence = drop_confidence

            return max(0.0, min(1.0, confidence))

        except Exception as e:
            self.logger.error(f"신뢰도 계산 실패: {e}", exc_info=True)
            return 0.5  # 기본값

    def get_buy_history(self, p_stock_code: str) -> int:
        """추가 매수 이력 조회

        Args:
            p_stock_code: 종목 코드

        Returns:
            추가 매수 횟수
        """
        return self._buy_history.get(p_stock_code, 0)
