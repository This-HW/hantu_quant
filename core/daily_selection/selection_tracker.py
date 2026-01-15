#!/usr/bin/env python3
"""
선정 추적 모듈 (Selection Tracker) - DB 기반

종목 선정 시의 점수를 DB에 저장하고, 거래 완료 후 결과와 매칭하여
adaptive_filter_tuner에 학습 데이터를 제공합니다.

데이터 흐름:
1. 종목 선정 시: record_selection() → DB(selection_history) 저장
2. 거래 완료 시: process_trade_results() → DB에서 매칭 → adaptive_filter_tuner로 전달
"""

from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from core.utils.log_utils import get_logger
from core.daily_selection.adaptive_filter_tuner import (
    get_adaptive_filter_tuner,
    TradeResult as FilterTradeResult
)

logger = get_logger(__name__)


def _get_db_session():
    """DB 세션 lazy import (순환 import 방지)"""
    try:
        from core.database.unified_db import get_session
        return get_session
    except ImportError:
        logger.warning("unified_db를 import할 수 없습니다")
        return None


def _get_selection_history_model():
    """SelectionHistory 모델 lazy import"""
    try:
        from core.database.models import SelectionHistory
        return SelectionHistory
    except ImportError:
        logger.warning("SelectionHistory 모델을 import할 수 없습니다")
        return None


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

    @classmethod
    def from_db_model(cls, model) -> 'SelectionRecord':
        """DB 모델에서 SelectionRecord 생성"""
        return cls(
            stock_code=model.stock_code,
            stock_name=model.stock_name or "",
            selection_date=model.selection_date.isoformat() if isinstance(model.selection_date, date) else str(model.selection_date),
            total_score=model.total_score or 0,
            technical_score=model.technical_score or 0,
            risk_score=0,  # DB 모델에 없으면 0
            confidence=model.confidence or 0,
            volume_score=model.volume_score or 0,
            composite_score=(model.confidence or 0) * 100,  # confidence를 composite로 변환
            market_condition="neutral",  # DB에서 가져오거나 기본값
            entry_price=model.entry_price,
            ranking=0
        )


class SelectionTracker:
    """
    선정 추적기 (DB 기반)

    종목 선정과 거래 결과를 DB에서 연결하여 학습 데이터를 생성합니다.
    """

    def __init__(self):
        # 메모리 캐시 (빠른 조회용)
        self._pending_cache: Dict[str, SelectionRecord] = {}
        self._cache_loaded = False

        logger.info("SelectionTracker 초기화 (DB 기반)")

    def _ensure_cache_loaded(self):
        """캐시 로드 확인"""
        if self._cache_loaded:
            return

        try:
            get_session = _get_db_session()
            SelectionHistory = _get_selection_history_model()

            if get_session is None or SelectionHistory is None:
                logger.warning("DB 연결 불가 - 메모리 캐시만 사용")
                self._cache_loaded = True
                return

            # 최근 14일간 미처리 선정 기록 로드
            cutoff_date = date.today() - timedelta(days=14)

            with get_session() as session:
                records = session.query(SelectionHistory).filter(
                    SelectionHistory.selection_date >= cutoff_date,
                    SelectionHistory.is_success.is_(None)  # 아직 결과가 없는 것
                ).all()

                for record in records:
                    selection = SelectionRecord.from_db_model(record)
                    key = f"{selection.stock_code}_{selection.selection_date}"
                    self._pending_cache[key] = selection

                logger.info(f"DB에서 대기 중인 선정 {len(self._pending_cache)}건 로드")

        except Exception as e:
            logger.error(f"캐시 로드 실패: {e}", exc_info=True)

        self._cache_loaded = True

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
        종목 선정 기록 (DB + 캐시)

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
            selection_date = date.today()
            selection_date_str = selection_date.isoformat()

            # SelectionRecord 생성
            record = SelectionRecord(
                stock_code=stock_code,
                stock_name=stock_name,
                selection_date=selection_date_str,
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

            # 1. DB에 저장
            db_saved = self._save_to_db(record, selection_date)

            # 2. 캐시에 저장
            key = f"{stock_code}_{selection_date_str}"
            self._pending_cache[key] = record

            logger.info(
                f"선정 기록: {stock_code} ({stock_name}) - "
                f"종합: {record.total_score:.1f}, 신뢰도: {record.confidence:.2f}, "
                f"DB저장: {'✓' if db_saved else '✗'}"
            )

            return True

        except Exception as e:
            logger.error(f"선정 기록 실패: {e}", exc_info=True)
            return False

    def _save_to_db(self, record: SelectionRecord, selection_date: date) -> bool:
        """DB에 선정 기록 저장"""
        try:
            get_session = _get_db_session()
            SelectionHistory = _get_selection_history_model()

            if get_session is None or SelectionHistory is None:
                return False

            with get_session() as session:
                # 기존 기록 확인 (같은 날 같은 종목)
                existing = session.query(SelectionHistory).filter(
                    SelectionHistory.selection_date == selection_date,
                    SelectionHistory.stock_code == record.stock_code
                ).first()

                if existing:
                    # 업데이트
                    existing.stock_name = record.stock_name
                    existing.total_score = record.total_score
                    existing.technical_score = record.technical_score
                    existing.volume_score = record.volume_score
                    existing.entry_price = record.entry_price
                    existing.confidence = record.confidence
                    existing.signal = 'buy'
                    existing.updated_at = datetime.now()
                else:
                    # 신규 생성
                    new_record = SelectionHistory(
                        selection_date=selection_date,
                        stock_code=record.stock_code,
                        stock_name=record.stock_name,
                        total_score=record.total_score,
                        technical_score=record.technical_score,
                        volume_score=record.volume_score,
                        entry_price=record.entry_price,
                        target_price=record.entry_price * 1.1 if record.entry_price else None,
                        stop_loss=record.entry_price * 0.95 if record.entry_price else None,
                        expected_return=0.1,
                        confidence=record.confidence,
                        signal='buy'
                    )
                    session.add(new_record)

                return True

        except Exception as e:
            logger.error(f"DB 저장 실패: {e}", exc_info=True)
            return False

    def process_trade_results(self, trade_summary: Dict[str, Any]) -> int:
        """
        거래 결과 처리 - 선정 기록과 매칭하여 학습 데이터 생성

        Args:
            trade_summary: trade_journal의 compute_daily_summary() 결과

        Returns:
            처리된 거래 수
        """
        self._ensure_cache_loaded()
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

                # DB 업데이트 (실제 수익률)
                self._update_db_result(stock_code, selection.selection_date, profit_rate)

                # 캐시에서 제거
                key = f"{stock_code}_{selection.selection_date}"
                if key in self._pending_cache:
                    del self._pending_cache[key]

                processed += 1

                logger.info(
                    f"학습 데이터 기록: {stock_code} - "
                    f"수익률: {profit_rate:.2%}, 성공: {profit_rate > 0}"
                )

            except Exception as e:
                logger.error(f"거래 결과 처리 실패 ({detail.get('stock_code', 'unknown')}): {e}", exc_info=True)

        if processed > 0:
            logger.info(f"거래 결과 처리 완료: {processed}건 → 학습 데이터 생성")

        return processed

    def _update_db_result(self, stock_code: str, selection_date_str: str, profit_rate: float) -> bool:
        """DB에 실제 결과 업데이트"""
        try:
            get_session = _get_db_session()
            SelectionHistory = _get_selection_history_model()

            if get_session is None or SelectionHistory is None:
                return False

            # 문자열을 date로 변환
            if isinstance(selection_date_str, str):
                selection_date = datetime.strptime(selection_date_str, "%Y-%m-%d").date()
            else:
                selection_date = selection_date_str

            with get_session() as session:
                record = session.query(SelectionHistory).filter(
                    SelectionHistory.selection_date == selection_date,
                    SelectionHistory.stock_code == stock_code
                ).first()

                if record:
                    record.actual_return_7d = profit_rate
                    record.is_success = 1 if profit_rate > 0 else 0
                    record.updated_at = datetime.now()
                    return True

            return False

        except Exception as e:
            logger.error(f"DB 결과 업데이트 실패: {e}", exc_info=True)
            return False

    def _find_matching_selection(
        self,
        stock_code: str,
        buy_time: str
    ) -> Optional[SelectionRecord]:
        """매칭되는 선정 기록 찾기 (캐시 → DB)"""
        self._ensure_cache_loaded()

        # 매수 시간에서 날짜 추출
        if buy_time:
            try:
                buy_date = buy_time[:10]  # "2024-01-15T..."에서 날짜만
            except Exception:
                buy_date = datetime.now().strftime("%Y-%m-%d")
        else:
            buy_date = datetime.now().strftime("%Y-%m-%d")

        # 1. 캐시에서 검색 (정확한 매칭)
        key = f"{stock_code}_{buy_date}"
        if key in self._pending_cache:
            return self._pending_cache[key]

        # 2. 캐시에서 검색 (최근 7일)
        for days_back in range(1, 8):
            check_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            key = f"{stock_code}_{check_date}"
            if key in self._pending_cache:
                return self._pending_cache[key]

        # 3. DB에서 검색
        return self._find_in_db(stock_code, buy_date)

    def _find_in_db(self, stock_code: str, buy_date_str: str) -> Optional[SelectionRecord]:
        """DB에서 선정 기록 검색"""
        try:
            get_session = _get_db_session()
            SelectionHistory = _get_selection_history_model()

            if get_session is None or SelectionHistory is None:
                return None

            # 최근 14일 범위에서 검색
            if isinstance(buy_date_str, str):
                buy_date = datetime.strptime(buy_date_str, "%Y-%m-%d").date()
            else:
                buy_date = buy_date_str

            start_date = buy_date - timedelta(days=14)

            with get_session() as session:
                record = session.query(SelectionHistory).filter(
                    SelectionHistory.stock_code == stock_code,
                    SelectionHistory.selection_date >= start_date,
                    SelectionHistory.selection_date <= buy_date
                ).order_by(SelectionHistory.selection_date.desc()).first()

                if record:
                    return SelectionRecord.from_db_model(record)

            return None

        except Exception as e:
            logger.error(f"DB 검색 실패: {e}", exc_info=True)
            return None

    def get_selection_for_stock(self, stock_code: str) -> Optional[SelectionRecord]:
        """특정 종목의 최근 선정 기록 조회"""
        self._ensure_cache_loaded()

        for key, selection in self._pending_cache.items():
            if selection.stock_code == stock_code:
                return selection

        # DB에서 검색
        return self._find_in_db(stock_code, datetime.now().strftime("%Y-%m-%d"))

    def get_stats(self) -> Dict[str, Any]:
        """통계 정보"""
        self._ensure_cache_loaded()

        stats = {
            "pending_selections": len(self._pending_cache),
            "oldest_pending": None,
            "newest_pending": None,
            "db_connected": _get_db_session() is not None
        }

        if self._pending_cache:
            dates = [s.selection_date for s in self._pending_cache.values()]
            stats["oldest_pending"] = min(dates)
            stats["newest_pending"] = max(dates)

        return stats

    def cleanup_old_selections(self, days: int = 30):
        """오래된 선정 기록 정리"""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        to_remove = [
            key for key, s in self._pending_cache.items()
            if s.selection_date < cutoff
        ]

        for key in to_remove:
            del self._pending_cache[key]

        if to_remove:
            logger.info(f"오래된 선정 기록 정리: {len(to_remove)}건 제거")


# 싱글톤 인스턴스
_tracker_instance: Optional[SelectionTracker] = None


def get_selection_tracker() -> SelectionTracker:
    """SelectionTracker 싱글톤 인스턴스 반환"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = SelectionTracker()
    return _tracker_instance
