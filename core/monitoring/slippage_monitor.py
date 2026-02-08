#!/usr/bin/env python3
"""
슬리페이지 모니터링 시스템
예상 가격 vs 실제 체결 가격 차이 추적
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
import json
import os
from pathlib import Path

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class SlippageRecord:
    """슬리페이지 기록"""
    stock_code: str
    stock_name: str
    order_type: str  # "buy" or "sell"
    expected_price: float
    executed_price: float
    quantity: int
    timestamp: str
    order_id: Optional[str] = None

    @property
    def slippage_rate(self) -> float:
        """슬리페이지 비율 (음수: 불리, 양수: 유리)"""
        if self.expected_price <= 0:
            logger.warning(
                f"비정상 예상가격: {self.expected_price}, "
                f"종목={self.stock_code}, 주문={self.order_type}"
            )
            return 0.0

        # 매수: 실제 < 예상 = 유리(양수), 실제 > 예상 = 불리(음수)
        # 매도: 실제 > 예상 = 유리(양수), 실제 < 예상 = 불리(음수)
        diff = self.executed_price - self.expected_price

        if self.order_type == "buy":
            return -diff / self.expected_price  # 반전 (낮게 사면 유리)
        else:  # sell
            return diff / self.expected_price

    @property
    def slippage_amount(self) -> float:
        """슬리페이지 금액"""
        return abs(self.executed_price - self.expected_price) * self.quantity


class SlippageMonitor:
    """슬리페이지 모니터"""

    def __init__(self, save_path: str = "data/monitoring/slippage_records.json"):
        """
        Args:
            save_path: 슬리페이지 기록 저장 경로 (프로젝트 루트 기준 상대 경로 또는 절대 경로)
        """
        # 프로젝트 루트 기준 경로 설정
        project_root = Path(__file__).parent.parent.parent
        allowed_base = project_root / "data" / "monitoring"

        # 경로 정규화 및 검증
        if Path(save_path).is_absolute():
            # 절대 경로: allowed_base 하위인지 검증
            self.save_path = Path(save_path).resolve()
            try:
                # Python 3.9+: is_relative_to
                if not self.save_path.is_relative_to(allowed_base.resolve()):
                    raise ValueError(
                        f"Invalid save path (outside allowed directory): {save_path}"
                    )
            except AttributeError:
                # Python 3.8 fallback: commonpath 사용
                try:
                    common = Path(os.path.commonpath([
                        str(self.save_path),
                        str(allowed_base.resolve())
                    ]))
                    if common != allowed_base.resolve():
                        raise ValueError(
                            f"Invalid save path (outside allowed directory): {save_path}"
                        )
                except ValueError:
                    raise ValueError(
                        f"Invalid save path (outside allowed directory): {save_path}"
                    )
        else:
            # 상대 경로: 프로젝트 루트 기준으로 해석
            self.save_path = (project_root / save_path).resolve()
            # 결과가 allowed_base 하위인지 검증 (보안)
            try:
                if not self.save_path.is_relative_to(allowed_base.resolve()):
                    logger.warning(
                        f"Relative path resolved outside monitoring dir: {self.save_path}"
                    )
            except AttributeError:
                pass  # Python 3.8에서는 경고만

        self.records: List[SlippageRecord] = []

        # 저장 디렉토리 생성
        self.save_path.parent.mkdir(parents=True, exist_ok=True)

        # 기존 기록 로드
        self._load_records()

        logger.info(f"SlippageMonitor 초기화: {len(self.records)}개 기록 로드")

    def record_slippage(
        self,
        stock_code: str,
        stock_name: str,
        order_type: str,
        expected_price: float,
        executed_price: float,
        quantity: int,
        order_id: Optional[str] = None
    ) -> SlippageRecord:
        """슬리페이지 기록

        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            order_type: "buy" or "sell"
            expected_price: 예상 체결가 (주문 시점 호가)
            executed_price: 실제 체결가
            quantity: 수량
            order_id: 주문 ID (선택)

        Returns:
            SlippageRecord: 기록된 슬리페이지
        """
        # 입력 검증
        if order_type not in ("buy", "sell"):
            raise ValueError(f"order_type must be 'buy' or 'sell', got '{order_type}'")
        if quantity <= 0:
            raise ValueError(f"quantity must be > 0, got {quantity}")
        if expected_price < 0 or executed_price < 0:
            raise ValueError(
                f"Prices must be >= 0, got expected={expected_price}, executed={executed_price}"
            )

        record = SlippageRecord(
            stock_code=stock_code,
            stock_name=stock_name,
            order_type=order_type,
            expected_price=expected_price,
            executed_price=executed_price,
            quantity=quantity,
            timestamp=datetime.now().isoformat(),
            order_id=order_id
        )

        self.records.append(record)

        # 로그 기록
        logger.info(
            f"슬리페이지 기록: {stock_name}({stock_code}) {order_type.upper()} - "
            f"예상={expected_price:,.0f}원, 실제={executed_price:,.0f}원, "
            f"슬리페이지={record.slippage_rate:+.2%}, "
            f"금액={record.slippage_amount:,.0f}원"
        )

        # 파일 저장
        self._save_records()

        return record

    def get_statistics(
        self,
        last_n: Optional[int] = None,
        order_type: Optional[str] = None
    ) -> Dict[str, float]:
        """슬리페이지 통계 조회

        Args:
            last_n: 최근 N개 기록만 분석 (None: 전체)
            order_type: 주문 유형 필터 ("buy", "sell", None: 전체)

        Returns:
            Dict: 통계 정보
        """
        # 필터링
        filtered_records = self.records

        if last_n is not None:
            filtered_records = filtered_records[-last_n:]

        if order_type is not None:
            filtered_records = [
                r for r in filtered_records if r.order_type == order_type
            ]

        if not filtered_records:
            logger.warning("슬리페이지 기록 없음")
            return {
                'total_count': 0,
                'avg_slippage_rate': 0.0,
                'avg_slippage_amount': 0.0,
                'favorable_count': 0,
                'unfavorable_count': 0,
                'favorable_rate': 0.0
            }

        # 통계 계산
        slippage_rates = [r.slippage_rate for r in filtered_records]
        slippage_amounts = [r.slippage_amount for r in filtered_records]

        favorable_count = sum(1 for r in slippage_rates if r > 0)
        unfavorable_count = sum(1 for r in slippage_rates if r < 0)

        stats = {
            'total_count': len(filtered_records),
            'avg_slippage_rate': sum(slippage_rates) / len(slippage_rates),
            'avg_slippage_amount': sum(slippage_amounts) / len(slippage_amounts),
            'favorable_count': favorable_count,
            'unfavorable_count': unfavorable_count,
            'favorable_rate': favorable_count / len(filtered_records),
            'max_slippage_rate': max(slippage_rates, key=abs),
            'min_slippage_rate': min(slippage_rates, key=abs)
        }

        logger.debug(
            f"슬리페이지 통계 (N={stats['total_count']}): "
            f"평균={stats['avg_slippage_rate']:+.2%}, "
            f"유리={stats['favorable_rate']:.1%}"
        )

        return stats

    def _save_records(self):
        """기록 파일 저장"""
        try:
            data = [
                {
                    'stock_code': r.stock_code,
                    'stock_name': r.stock_name,
                    'order_type': r.order_type,
                    'expected_price': r.expected_price,
                    'executed_price': r.executed_price,
                    'quantity': r.quantity,
                    'timestamp': r.timestamp,
                    'order_id': r.order_id,
                    'slippage_rate': r.slippage_rate,
                    'slippage_amount': r.slippage_amount
                }
                for r in self.records
            ]

            with open(self.save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"슬리페이지 기록 저장 실패: {e}", exc_info=True)

    def _load_records(self):
        """기존 기록 로드"""
        if not self.save_path.exists():
            return

        try:
            with open(self.save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.records = [
                SlippageRecord(
                    stock_code=item['stock_code'],
                    stock_name=item['stock_name'],
                    order_type=item['order_type'],
                    expected_price=item['expected_price'],
                    executed_price=item['executed_price'],
                    quantity=item['quantity'],
                    timestamp=item['timestamp'],
                    order_id=item.get('order_id')
                )
                for item in data
            ]

            logger.info(f"슬리페이지 기록 로드: {len(self.records)}개")

        except Exception as e:
            logger.error(f"슬리페이지 기록 로드 실패: {e}", exc_info=True)
            self.records = []
