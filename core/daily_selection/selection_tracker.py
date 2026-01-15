#!/usr/bin/env python3
"""
선정 추적 모듈 (Selection Tracker)

종목 선정 시의 점수를 저장하고, 거래 완료 후 결과와 매칭하여
adaptive_filter_tuner에 학습 데이터를 제공합니다.

데이터 흐름:
1. 종목 선정 시: record_selection() → selection metrics 저장
2. 거래 완료 시: process_trade_results() → 결과와 매칭 → adaptive_filter_tuner로 전달
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from core.utils.log_utils import get_logger
from core.daily_selection.adaptive_filter_tuner import (
    get_adaptive_filter_tuner,
    TradeResult as FilterTradeResult
)

logger = get_logger(__name__)


@dataclass
class SelectionRecord:
    """종목 선정 기록"""
    stock_code: str
    stock_name: str
    selection_date: str

    # 선정 당시 점수들 (adaptive_filter_tuner의 TradeResult와 매칭)
    total_score: float          # 종합 점수 (price_attractiveness)
    technical_score: float      # 기술적 점수
    risk_score: float           # 리스크 점수
    confidence: float           # 신뢰도
    volume_score: float         # 거래량 점수
    composite_score: float      # 통합 점수

    # 시장 상황
    market_condition: str       # bull_market, bear_market, etc.

    # 추가 정보
    entry_price: Optional[float] = None
    ranking: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'SelectionRecord':
        return cls(**data)


class SelectionTracker:
    """
    선정 추적기

    종목 선정과 거래 결과를 연결하여 학습 데이터를 생성합니다.
    """

    def __init__(self, data_dir: str = "data/selection"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

        # 미처리 선정 기록 (아직 거래 결과가 없는 것들)
        self._pending_selections: Dict[str, SelectionRecord] = {}
        self._load_pending_selections()

        logger.info(f"SelectionTracker 초기화 - 대기 중인 선정: {len(self._pending_selections)}건")

    def _get_pending_file(self) -> str:
        return os.path.join(self.data_dir, "pending_selections.json")

    def _load_pending_selections(self):
        """대기 중인 선정 기록 로드"""
        try:
            pending_file = self._get_pending_file()
            if os.path.exists(pending_file):
                with open(pending_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for record in data.get("selections", []):
                        selection = SelectionRecord.from_dict(record)
                        key = f"{selection.stock_code}_{selection.selection_date}"
                        self._pending_selections[key] = selection
        except Exception as e:
            logger.error(f"선정 기록 로드 실패: {e}", exc_info=True)

    def _save_pending_selections(self):
        """대기 중인 선정 기록 저장"""
        try:
            pending_file = self._get_pending_file()
            data = {
                "updated_at": datetime.now().isoformat(),
                "count": len(self._pending_selections),
                "selections": [s.to_dict() for s in self._pending_selections.values()]
            }
            with open(pending_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"선정 기록 저장 실패: {e}", exc_info=True)

    def record_selection(
        self,
        stock_code: str,
        stock_name: str,
        metrics: Dict[str, Any],
        market_condition: str,
        entry_price: Optional[float] = None,
        ranking: int = 0
    ) -> bool:
        """
        종목 선정 기록

        Args:
            stock_code: 종목 코드
            stock_name: 종목명
            metrics: 선정 지표 딕셔너리
            market_condition: 시장 상황
            entry_price: 진입 가격 (있으면)
            ranking: 선정 순위

        Returns:
            기록 성공 여부
        """
        try:
            selection_date = datetime.now().strftime("%Y-%m-%d")

            record = SelectionRecord(
                stock_code=stock_code,
                stock_name=stock_name,
                selection_date=selection_date,
                total_score=metrics.get("total_score", 0),
                technical_score=metrics.get("technical_score", 0),
                risk_score=metrics.get("risk_score", 0),
                confidence=metrics.get("confidence", 0),
                volume_score=metrics.get("volume_score", 0),
                composite_score=metrics.get("composite_score", 0) * 100,  # 0-1 → 0-100
                market_condition=market_condition,
                entry_price=entry_price,
                ranking=ranking
            )

            key = f"{stock_code}_{selection_date}"
            self._pending_selections[key] = record
            self._save_pending_selections()

            # 일별 선정 기록도 별도 저장
            self._save_daily_selection(record)

            logger.info(
                f"선정 기록: {stock_code} ({stock_name}) - "
                f"종합: {record.total_score:.1f}, 신뢰도: {record.confidence:.2f}, "
                f"통합점수: {record.composite_score:.1f}"
            )

            return True

        except Exception as e:
            logger.error(f"선정 기록 실패: {e}", exc_info=True)
            return False

    def _save_daily_selection(self, record: SelectionRecord):
        """일별 선정 기록 저장"""
        try:
            date_str = record.selection_date.replace("-", "")
            daily_file = os.path.join(self.data_dir, f"selections_{date_str}.json")

            # 기존 데이터 로드
            existing = []
            if os.path.exists(daily_file):
                with open(daily_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    existing = data.get("selections", [])

            # 새 기록 추가 (중복 제거)
            existing = [s for s in existing if s.get("stock_code") != record.stock_code]
            existing.append(record.to_dict())

            # 저장
            with open(daily_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "date": record.selection_date,
                    "market_condition": record.market_condition,
                    "selections": existing
                }, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"일별 선정 기록 저장 실패: {e}", exc_info=True)

    def process_trade_results(self, trade_summary: Dict[str, Any]) -> int:
        """
        거래 결과 처리 - 선정 기록과 매칭하여 학습 데이터 생성

        Args:
            trade_summary: trade_journal의 compute_daily_summary() 결과

        Returns:
            처리된 거래 수
        """
        processed = 0
        tuner = get_adaptive_filter_tuner()

        for detail in trade_summary.get("details", []):
            try:
                stock_code = detail.get("stock_code")
                sell_time = detail.get("sell_time", "")
                buy_time = detail.get("buy_time", "")

                # 매칭되는 선정 기록 찾기
                selection = self._find_matching_selection(stock_code, buy_time)

                if selection is None:
                    logger.debug(f"선정 기록 없음: {stock_code}")
                    continue

                # 수익률 계산
                buy_price = detail.get("buy_price", 0)
                sell_price = detail.get("sell_price", 0)
                pnl = detail.get("pnl", 0)

                if buy_price > 0:
                    profit_rate = (sell_price - buy_price) / buy_price
                else:
                    profit_rate = 0

                # adaptive_filter_tuner에 거래 결과 기록
                trade_result = FilterTradeResult(
                    stock_code=stock_code,
                    stock_name=selection.stock_name,
                    entry_date=selection.selection_date,
                    exit_date=sell_time[:10] if sell_time else datetime.now().strftime("%Y-%m-%d"),
                    entry_price=buy_price,
                    exit_price=sell_price,
                    profit_rate=profit_rate,
                    is_success=profit_rate > 0,
                    total_score=selection.total_score,
                    technical_score=selection.technical_score,
                    risk_score=selection.risk_score,
                    confidence=selection.confidence,
                    volume_score=selection.volume_score,
                    composite_score=selection.composite_score,
                    market_condition=selection.market_condition
                )

                tuner.record_trade(trade_result)

                # 처리 완료된 선정 기록 제거
                key = f"{stock_code}_{selection.selection_date}"
                if key in self._pending_selections:
                    del self._pending_selections[key]

                processed += 1

                logger.info(
                    f"학습 데이터 기록: {stock_code} - "
                    f"수익률: {profit_rate:.2%}, 성공: {profit_rate > 0}"
                )

            except Exception as e:
                logger.error(f"거래 결과 처리 실패 ({stock_code}): {e}", exc_info=True)

        # 변경사항 저장
        self._save_pending_selections()

        if processed > 0:
            logger.info(f"거래 결과 처리 완료: {processed}건 → 학습 데이터 생성")

        return processed

    def _find_matching_selection(
        self,
        stock_code: str,
        buy_time: str
    ) -> Optional[SelectionRecord]:
        """매칭되는 선정 기록 찾기"""

        # 매수 시간에서 날짜 추출
        if buy_time:
            try:
                buy_date = buy_time[:10]  # "2024-01-15T..."에서 날짜만
            except Exception:
                buy_date = datetime.now().strftime("%Y-%m-%d")
        else:
            buy_date = datetime.now().strftime("%Y-%m-%d")

        # 정확한 매칭 시도
        key = f"{stock_code}_{buy_date}"
        if key in self._pending_selections:
            return self._pending_selections[key]

        # 최근 7일 내 선정 기록에서 검색
        for days_back in range(1, 8):
            check_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            key = f"{stock_code}_{check_date}"
            if key in self._pending_selections:
                return self._pending_selections[key]

        # 일별 파일에서 검색
        for days_back in range(0, 14):
            check_date = (datetime.now() - timedelta(days=days_back))
            date_str = check_date.strftime("%Y%m%d")
            daily_file = os.path.join(self.data_dir, f"selections_{date_str}.json")

            if os.path.exists(daily_file):
                try:
                    with open(daily_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for s in data.get("selections", []):
                            if s.get("stock_code") == stock_code:
                                return SelectionRecord.from_dict(s)
                except Exception:
                    continue

        return None

    def get_selection_for_stock(self, stock_code: str) -> Optional[SelectionRecord]:
        """특정 종목의 최근 선정 기록 조회"""
        for key, selection in self._pending_selections.items():
            if selection.stock_code == stock_code:
                return selection
        return None

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        return {
            "pending_selections": len(self._pending_selections),
            "oldest_pending": min(
                (s.selection_date for s in self._pending_selections.values()),
                default=None
            ),
            "newest_pending": max(
                (s.selection_date for s in self._pending_selections.values()),
                default=None
            )
        }

    def cleanup_old_selections(self, days: int = 30):
        """오래된 선정 기록 정리"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        to_remove = [
            key for key, s in self._pending_selections.items()
            if s.selection_date < cutoff
        ]

        for key in to_remove:
            del self._pending_selections[key]

        if to_remove:
            self._save_pending_selections()
            logger.info(f"오래된 선정 기록 정리: {len(to_remove)}건 제거")


# 싱글톤 인스턴스
_tracker_instance: Optional[SelectionTracker] = None


def get_selection_tracker() -> SelectionTracker:
    """SelectionTracker 싱글톤 인스턴스 반환"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = SelectionTracker()
    return _tracker_instance
