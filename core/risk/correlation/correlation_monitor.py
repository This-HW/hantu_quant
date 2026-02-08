#!/usr/bin/env python3
"""
상관관계 기반 포지션 모니터링
고상관 종목 동시 보유 방지
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import pandas as pd

from core.utils.log_utils import get_logger
from core.risk.correlation.correlation_matrix import CorrelationMatrix

logger = get_logger(__name__)


@dataclass
class CorrelationCheckResult:
    """상관관계 체크 결과"""
    allowed: bool
    max_correlation: float
    high_corr_stocks: List[str]  # 높은 상관관계 종목 리스트
    reason: str


class CorrelationMonitor:
    """상관관계 모니터"""

    def __init__(
        self,
        correlation_threshold: float = 0.7,
        max_high_corr_pairs: int = 2
    ):
        """
        Args:
            correlation_threshold: 높은 상관관계 임계값 (기본 0.7)
            max_high_corr_pairs: 허용 가능한 고상관 쌍 개수 (기본 2)
        """
        # 입력 검증
        if not (0.0 <= correlation_threshold <= 1.0):
            raise ValueError(
                f"correlation_threshold must be in [0, 1], got {correlation_threshold}"
            )
        if max_high_corr_pairs < 0:
            raise ValueError(
                f"max_high_corr_pairs must be >= 0, got {max_high_corr_pairs}"
            )

        self.correlation_threshold = correlation_threshold
        self.max_high_corr_pairs = max_high_corr_pairs
        self.correlation_matrix = CorrelationMatrix(
            high_correlation_threshold=correlation_threshold
        )

        logger.info(
            f"CorrelationMonitor 초기화: threshold={correlation_threshold}, "
            f"max_pairs={max_high_corr_pairs}"
        )

    def check_new_position(
        self,
        new_stock_code: str,
        existing_positions: Dict[str, Any],
        price_data: Dict[str, pd.DataFrame],
    ) -> CorrelationCheckResult:
        """새 포지션 추가 시 상관관계 체크

        Args:
            new_stock_code: 신규 종목 코드
            existing_positions: 기존 포지션 {stock_code: position_info}
            price_data: 가격 데이터 {stock_code: OHLCV DataFrame}

        Returns:
            CorrelationCheckResult: 체크 결과
        """
        if not existing_positions:
            return CorrelationCheckResult(
                allowed=True,
                max_correlation=0.0,
                high_corr_stocks=[],
                reason="기존 포지션 없음"
            )

        try:
            # 1. 신규 종목 데이터 확인
            if new_stock_code not in price_data:
                logger.warning(f"신규 종목 가격 데이터 없음: {new_stock_code}")
                return CorrelationCheckResult(
                    allowed=True,
                    max_correlation=0.0,
                    high_corr_stocks=[],
                    reason="신규 종목 가격 데이터 부족"
                )

            # 2. 기존 포지션 종목 코드 추출
            existing_codes = list(existing_positions.keys())

            # 3. 신규 종목과 기존 종목들 간 상관계수 계산
            high_corr_stocks = []
            max_corr = 0.0

            for existing_code in existing_codes:
                if existing_code not in price_data:
                    logger.warning(f"기존 종목 가격 데이터 없음: {existing_code}")
                    continue

                # 두 종목 간 상관계수 계산
                corr_value = self.correlation_matrix.get_pairwise_correlation(
                    price_data, new_stock_code, existing_code
                )

                max_corr = max(max_corr, abs(corr_value))
                if abs(corr_value) >= self.correlation_threshold:
                    high_corr_stocks.append(
                        f"{existing_code}({corr_value:.2f})"
                    )

            # 4. 허용 여부 판단
            if not high_corr_stocks:
                return CorrelationCheckResult(
                    allowed=True,
                    max_correlation=max_corr,
                    high_corr_stocks=[],
                    reason=f"모든 종목과 상관계수 < {self.correlation_threshold}"
                )

            # 5. 기존 포지션 간 고상관 쌍 개수 확인
            current_high_corr_pairs = self._count_high_corr_pairs(
                existing_codes, price_data
            )

            if current_high_corr_pairs >= self.max_high_corr_pairs:
                return CorrelationCheckResult(
                    allowed=False,
                    max_correlation=max_corr,
                    high_corr_stocks=high_corr_stocks,
                    reason=(
                        f"고상관 쌍 한도 초과 "
                        f"(현재 {current_high_corr_pairs}쌍, "
                        f"최대 {self.max_high_corr_pairs}쌍)"
                    )
                )

            # 6. 신규 종목 추가 시 고상관 쌍 개수 증가 예측
            new_high_corr_pairs = current_high_corr_pairs + len(high_corr_stocks)

            if new_high_corr_pairs > self.max_high_corr_pairs:
                return CorrelationCheckResult(
                    allowed=False,
                    max_correlation=max_corr,
                    high_corr_stocks=high_corr_stocks,
                    reason=(
                        f"추가 시 고상관 쌍 {new_high_corr_pairs}개 초과 "
                        f"(최대 {self.max_high_corr_pairs}쌍)"
                    )
                )

            return CorrelationCheckResult(
                allowed=True,
                max_correlation=max_corr,
                high_corr_stocks=high_corr_stocks,
                reason=(
                    f"고상관 쌍 허용 범위 내 "
                    f"({new_high_corr_pairs}/{self.max_high_corr_pairs}쌍)"
                )
            )

        except Exception as e:
            logger.error(
                f"상관관계 체크 실패: {new_stock_code} - {e}",
                exc_info=True
            )
            return CorrelationCheckResult(
                allowed=True,  # 에러 시 허용 (보수적)
                max_correlation=0.0,
                high_corr_stocks=[],
                reason=f"상관관계 체크 오류: {e}"
            )

    def _count_high_corr_pairs(
        self,
        stock_codes: List[str],
        price_data: Dict[str, pd.DataFrame]
    ) -> int:
        """기존 포지션 간 고상관 쌍 개수 계산"""
        high_corr_pairs = 0

        for i, code1 in enumerate(stock_codes):
            for code2 in stock_codes[i+1:]:
                if code1 not in price_data or code2 not in price_data:
                    continue

                corr_value = self.correlation_matrix.get_pairwise_correlation(
                    price_data, code1, code2
                )
                if abs(corr_value) >= self.correlation_threshold:
                    high_corr_pairs += 1

        return high_corr_pairs
