"""
자동화된 데이터 파이프라인: JSON 파일들을 DB에 동기화
스크리닝 결과, 종목 선정, 거래 기록 등을 통합 관리

PostgreSQL 통합 DB 지원 (T-001): use_unified_db=True로 SQLAlchemy 기반 통합 DB 사용
SQLite 폴백: 통합 DB 연결 실패 시 기존 SQLite 사용
"""

import json
import sqlite3
import os
import glob
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError

from ..utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ScreeningResult:
    """스크리닝 결과 데이터"""

    stock_code: str
    stock_name: str
    sector: str
    screening_date: str
    overall_score: float
    fundamental_score: float
    technical_score: float
    passed: bool
    roe: Optional[float] = None
    per: Optional[float] = None
    pbr: Optional[float] = None


@dataclass
class SelectionResult:
    """종목 선정 결과 데이터"""

    stock_code: str
    stock_name: str
    selection_date: str
    final_score: float
    predicted_direction: str
    confidence: float
    reason: str
    entry_price: Optional[float] = None


@dataclass
class PerformanceTracking:
    """성과 추적 데이터"""

    stock_code: str
    tracking_date: str
    entry_price: float
    current_price: float
    price_change_pct: float
    days_tracked: int
    max_gain: float
    max_loss: float
    is_active: bool


class DataSynchronizer:
    """데이터 동기화 시스템

    PostgreSQL 통합 DB 지원 (T-001):
    - use_unified_db=True: SQLAlchemy 기반 통합 DB 사용
    - 통합 DB 연결 실패 시 자동으로 SQLite 폴백
    """

    def __init__(
        self,
        db_path: str = "data/learning/learning_data.db",
        use_unified_db: bool = True,
    ):
        self.db_path = db_path
        self.logger = logger
        self._unified_db_available = False

        # 통합 DB 사용 시도
        if use_unified_db:
            try:
                from ..database.unified_db import ensure_tables_exist

                ensure_tables_exist()
                self._unified_db_available = True
                self.logger.info("통합 DB 연결 성공 (PostgreSQL/SQLAlchemy)")
            except Exception as e:
                self.logger.warning(f"통합 DB 연결 실패, SQLite 폴백 사용: {e}")
                self._unified_db_available = False

        # SQLite 폴백용 스키마 준비
        if not self._unified_db_available:
            self._ensure_db_schema()

    def _ensure_db_schema(self):
        """DB 스키마 확인 및 업데이트"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 새로운 테이블 생성
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS screening_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_code TEXT NOT NULL,
                        stock_name TEXT NOT NULL,
                        sector TEXT,
                        screening_date TEXT NOT NULL,
                        overall_score REAL,
                        fundamental_score REAL,
                        technical_score REAL,
                        passed BOOLEAN,
                        roe REAL,
                        per REAL,
                        pbr REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(stock_code, screening_date)
                    )
                """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS selection_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_code TEXT NOT NULL,
                        stock_name TEXT NOT NULL,
                        selection_date TEXT NOT NULL,
                        final_score REAL,
                        predicted_direction TEXT,
                        confidence REAL,
                        reason TEXT,
                        entry_price REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(stock_code, selection_date)
                    )
                """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS performance_tracking (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stock_code TEXT NOT NULL,
                        tracking_date TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        current_price REAL NOT NULL,
                        price_change_pct REAL NOT NULL,
                        days_tracked INTEGER NOT NULL,
                        max_gain REAL DEFAULT 0,
                        max_loss REAL DEFAULT 0,
                        is_active BOOLEAN DEFAULT 1,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(stock_code, tracking_date)
                    )
                """
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS learning_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        value REAL NOT NULL,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                conn.commit()
                self.logger.info("데이터베이스 스키마 확인/업데이트 완료")

        except Exception as e:
            self.logger.error(f"DB 스키마 초기화 실패: {e}", exc_info=True)
            raise

    def sync_screening_results(self, days_back: int = 30) -> int:
        """스크리닝 결과 동기화

        통합 DB 사용 시 SQLAlchemy, 아니면 SQLite 사용
        """
        if self._unified_db_available:
            return self._sync_screening_results_unified(days_back)
        return self._sync_screening_results_sqlite(days_back)

    def _sync_screening_results_unified(self, days_back: int = 30) -> int:
        """통합 DB로 스크리닝 결과 동기화 (SQLAlchemy)"""
        try:
            from ..database.unified_db import get_session
            from ..database.models import ScreeningHistory as DBScreeningHistory

            synced_count = 0
            recent_files = self._get_recent_screening_files(days_back)
            self.logger.info(
                f"최근 {days_back}일 스크리닝 파일 {len(recent_files)}개 처리 시작 (통합 DB)"
            )

            with get_session() as session:
                for file_path, date_str in recent_files:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        results = data.get("results", [])
                        screening_date = datetime.strptime(date_str, "%Y%m%d").date()

                        for result in results:
                            try:
                                # 기존 레코드 확인
                                existing = (
                                    session.query(DBScreeningHistory)
                                    .filter(
                                        DBScreeningHistory.screening_date
                                        == screening_date,
                                        DBScreeningHistory.stock_code
                                        == result["stock_code"],
                                    )
                                    .first()
                                )

                                if existing:
                                    # 업데이트
                                    existing.stock_name = result["stock_name"]
                                    existing.total_score = result.get(
                                        "overall_score", 0
                                    )
                                    existing.fundamental_score = result.get(
                                        "fundamental", {}
                                    ).get("score", 0)
                                    existing.technical_score = result.get(
                                        "technical", {}
                                    ).get("score", 0)
                                    existing.passed = (
                                        1 if result.get("overall_passed", False) else 0
                                    )
                                    existing.roe = self._extract_fundamental_value(
                                        result, "roe"
                                    )
                                    existing.per = self._extract_fundamental_value(
                                        result, "per"
                                    )
                                    existing.pbr = self._extract_fundamental_value(
                                        result, "pbr"
                                    )
                                else:
                                    # 신규 생성
                                    new_record = DBScreeningHistory(
                                        screening_date=screening_date,
                                        stock_code=result["stock_code"],
                                        stock_name=result["stock_name"],
                                        total_score=result.get("overall_score", 0),
                                        fundamental_score=result.get(
                                            "fundamental", {}
                                        ).get("score", 0),
                                        technical_score=result.get("technical", {}).get(
                                            "score", 0
                                        ),
                                        passed=(
                                            1
                                            if result.get("overall_passed", False)
                                            else 0
                                        ),
                                        roe=self._extract_fundamental_value(
                                            result, "roe"
                                        ),
                                        per=self._extract_fundamental_value(
                                            result, "per"
                                        ),
                                        pbr=self._extract_fundamental_value(
                                            result, "pbr"
                                        ),
                                        reason=result.get("sector", ""),
                                    )
                                    session.add(new_record)

                                synced_count += 1

                            except Exception as e:
                                self.logger.warning(
                                    f"개별 스크리닝 결과 처리 실패: {e}"
                                )
                                continue

                    except Exception as e:
                        self.logger.warning(f"스크리닝 파일 처리 실패 {file_path}: {e}")
                        continue

            self.logger.info(f"스크리닝 결과 동기화 완료 (통합 DB): {synced_count}건")
            return synced_count

        except SQLAlchemyError as e:
            self.logger.error(
                f"스크리닝 결과 동기화 실패 (통합 DB): {e}", exc_info=True
            )
            return 0

    def _sync_screening_results_sqlite(self, days_back: int = 30) -> int:
        """SQLite로 스크리닝 결과 동기화 (폴백)"""
        try:
            synced_count = 0
            recent_files = self._get_recent_screening_files(days_back)
            self.logger.info(
                f"최근 {days_back}일 스크리닝 파일 {len(recent_files)}개 처리 시작 (SQLite)"
            )

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for file_path, date_str in recent_files:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        results = data.get("results", [])

                        for result in results:
                            try:
                                screening_result = ScreeningResult(
                                    stock_code=result["stock_code"],
                                    stock_name=result["stock_name"],
                                    sector=result.get("sector", ""),
                                    screening_date=date_str,
                                    overall_score=result.get("overall_score", 0),
                                    fundamental_score=result.get("fundamental", {}).get(
                                        "score", 0
                                    ),
                                    technical_score=result.get("technical", {}).get(
                                        "score", 0
                                    ),
                                    passed=result.get("overall_passed", False),
                                    roe=self._extract_fundamental_value(result, "roe"),
                                    per=self._extract_fundamental_value(result, "per"),
                                    pbr=self._extract_fundamental_value(result, "pbr"),
                                )

                                cursor.execute(
                                    """
                                    INSERT OR REPLACE INTO screening_history
                                    (stock_code, stock_name, sector, screening_date, overall_score,
                                     fundamental_score, technical_score, passed, roe, per, pbr)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                    (
                                        screening_result.stock_code,
                                        screening_result.stock_name,
                                        screening_result.sector,
                                        screening_result.screening_date,
                                        screening_result.overall_score,
                                        screening_result.fundamental_score,
                                        screening_result.technical_score,
                                        screening_result.passed,
                                        screening_result.roe,
                                        screening_result.per,
                                        screening_result.pbr,
                                    ),
                                )

                                synced_count += 1

                            except Exception as e:
                                self.logger.warning(
                                    f"개별 스크리닝 결과 처리 실패: {e}"
                                )
                                continue

                    except Exception as e:
                        self.logger.warning(f"스크리닝 파일 처리 실패 {file_path}: {e}")
                        continue

                conn.commit()

            self.logger.info(f"스크리닝 결과 동기화 완료 (SQLite): {synced_count}건")
            return synced_count

        except Exception as e:
            self.logger.error(f"스크리닝 결과 동기화 실패 (SQLite): {e}", exc_info=True)
            return 0

    def _get_recent_screening_files(self, days_back: int) -> List[Tuple[str, str]]:
        """최근 스크리닝 파일 목록 반환"""
        screening_files = glob.glob("data/watchlist/screening_results_*.json")
        recent_files = []
        cutoff_date = datetime.now() - timedelta(days=days_back)

        for file_path in screening_files:
            try:
                filename = os.path.basename(file_path)
                date_part = filename.split("_")[2]  # 20250911
                file_date = datetime.strptime(date_part, "%Y%m%d")

                if file_date >= cutoff_date:
                    recent_files.append((file_path, date_part))
            except Exception:
                continue

        return recent_files

    def _extract_fundamental_value(self, result: Dict, key: str) -> Optional[float]:
        """스크리닝 결과에서 기본적 분석 값 추출"""
        try:
            fundamental = result.get("fundamental", {})
            details = fundamental.get("details", {})
            return details.get(key, {}).get("value")
        except Exception:
            return None

    def sync_selection_results(self, days_back: int = 30) -> int:
        """종목 선정 결과 동기화

        통합 DB 사용 시 SQLAlchemy, 아니면 SQLite 사용
        """
        if self._unified_db_available:
            return self._sync_selection_results_unified(days_back)
        return self._sync_selection_results_sqlite(days_back)

    def _sync_selection_results_unified(self, days_back: int = 30) -> int:
        """통합 DB로 종목 선정 결과 동기화 (SQLAlchemy)"""
        try:
            from ..database.unified_db import get_session
            from ..database.models import SelectionHistory as DBSelectionHistory

            synced_count = 0
            recent_files = self._get_recent_selection_files(days_back)
            self.logger.info(
                f"최근 {days_back}일 선정 파일 {len(recent_files)}개 처리 시작 (통합 DB)"
            )

            with get_session() as session:
                for file_path, date_str in recent_files:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        selections = data.get("selected_stocks", [])
                        selection_date = datetime.strptime(date_str, "%Y%m%d").date()

                        for selection in selections:
                            try:
                                # 기존 레코드 확인
                                existing = (
                                    session.query(DBSelectionHistory)
                                    .filter(
                                        DBSelectionHistory.selection_date
                                        == selection_date,
                                        DBSelectionHistory.stock_code
                                        == selection["stock_code"],
                                    )
                                    .first()
                                )

                                if existing:
                                    # 업데이트
                                    existing.stock_name = selection.get(
                                        "stock_name", ""
                                    )
                                    existing.total_score = selection.get(
                                        "final_score", 0
                                    )
                                    existing.signal = selection.get(
                                        "predicted_direction", "unknown"
                                    )
                                    existing.confidence = selection.get("confidence", 0)
                                    existing.entry_price = selection.get(
                                        "current_price"
                                    )
                                    existing.target_price = selection.get(
                                        "target_price"
                                    )
                                    existing.stop_loss = selection.get("stop_loss")
                                    existing.expected_return = selection.get(
                                        "expected_return", 0
                                    )
                                else:
                                    # 신규 생성
                                    new_record = DBSelectionHistory(
                                        selection_date=selection_date,
                                        stock_code=selection["stock_code"],
                                        stock_name=selection.get("stock_name", ""),
                                        total_score=selection.get("final_score", 0),
                                        signal=selection.get(
                                            "predicted_direction", "unknown"
                                        ),
                                        confidence=selection.get("confidence", 0),
                                        entry_price=selection.get("current_price"),
                                        target_price=selection.get("target_price"),
                                        stop_loss=selection.get("stop_loss"),
                                        expected_return=selection.get(
                                            "expected_return", 0
                                        ),
                                    )
                                    session.add(new_record)

                                synced_count += 1

                            except Exception as e:
                                self.logger.warning(f"개별 선정 결과 처리 실패: {e}")
                                continue

                    except Exception as e:
                        self.logger.warning(f"선정 파일 처리 실패 {file_path}: {e}")
                        continue

            self.logger.info(f"종목 선정 결과 동기화 완료 (통합 DB): {synced_count}건")
            return synced_count

        except SQLAlchemyError as e:
            self.logger.error(
                f"종목 선정 결과 동기화 실패 (통합 DB): {e}", exc_info=True
            )
            return 0

    def _sync_selection_results_sqlite(self, days_back: int = 30) -> int:
        """SQLite로 종목 선정 결과 동기화 (폴백)"""
        try:
            synced_count = 0
            recent_files = self._get_recent_selection_files(days_back)
            self.logger.info(
                f"최근 {days_back}일 선정 파일 {len(recent_files)}개 처리 시작 (SQLite)"
            )

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                for file_path, date_str in recent_files:
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        selections = data.get("selected_stocks", [])

                        for selection in selections:
                            try:
                                selection_result = SelectionResult(
                                    stock_code=selection["stock_code"],
                                    stock_name=selection.get("stock_name", ""),
                                    selection_date=date_str,
                                    final_score=selection.get("final_score", 0),
                                    predicted_direction=selection.get(
                                        "predicted_direction", "unknown"
                                    ),
                                    confidence=selection.get("confidence", 0),
                                    reason=selection.get("reason", ""),
                                    entry_price=selection.get("current_price"),
                                )

                                cursor.execute(
                                    """
                                    INSERT OR REPLACE INTO selection_history
                                    (stock_code, stock_name, selection_date, final_score,
                                     predicted_direction, confidence, reason, entry_price)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                    (
                                        selection_result.stock_code,
                                        selection_result.stock_name,
                                        selection_result.selection_date,
                                        selection_result.final_score,
                                        selection_result.predicted_direction,
                                        selection_result.confidence,
                                        selection_result.reason,
                                        selection_result.entry_price,
                                    ),
                                )

                                synced_count += 1

                            except Exception as e:
                                self.logger.warning(f"개별 선정 결과 처리 실패: {e}")
                                continue

                    except Exception as e:
                        self.logger.warning(f"선정 파일 처리 실패 {file_path}: {e}")
                        continue

                conn.commit()

            self.logger.info(f"종목 선정 결과 동기화 완료 (SQLite): {synced_count}건")
            return synced_count

        except Exception as e:
            self.logger.error(
                f"종목 선정 결과 동기화 실패 (SQLite): {e}", exc_info=True
            )
            return 0

    def _get_recent_selection_files(self, days_back: int) -> List[Tuple[str, str]]:
        """최근 선정 파일 목록 반환"""
        selection_files = glob.glob("data/daily_selection/daily_selection_*.json")
        recent_files = []
        cutoff_date = datetime.now() - timedelta(days=days_back)

        for file_path in selection_files:
            try:
                filename = os.path.basename(file_path)
                date_part = filename.split("_")[2].split(".")[
                    0
                ]  # daily_selection_20250911.json
                file_date = datetime.strptime(date_part, "%Y%m%d")

                if file_date >= cutoff_date:
                    recent_files.append((file_path, date_part))
            except Exception:
                continue

        return recent_files

    def update_performance_tracking(self, max_days_back: int = 30) -> int:
        """선정 종목들의 성과 추적 업데이트

        통합 DB 사용 시 SQLAlchemy, 아니면 SQLite 사용
        """
        if self._unified_db_available:
            return self._update_performance_tracking_unified(max_days_back)
        return self._update_performance_tracking_sqlite(max_days_back)

    def _update_performance_tracking_unified(self, max_days_back: int = 30) -> int:
        """통합 DB로 성과 추적 업데이트 (SQLAlchemy)"""
        try:
            from ..database.unified_db import get_session
            from ..database.models import SelectionHistory as DBSelectionHistory
            from ..database.models import DailyTracking
            import random

            updated_count = 0
            cutoff_date = (datetime.now() - timedelta(days=max_days_back)).date()

            with get_session() as session:
                # 추적 대상 종목들 조회
                selections = (
                    session.query(DBSelectionHistory)
                    .filter(
                        DBSelectionHistory.selection_date >= cutoff_date,
                        DBSelectionHistory.entry_price.isnot(None),
                    )
                    .order_by(DBSelectionHistory.selection_date.desc())
                    .all()
                )

                self.logger.info(f"성과 추적 대상 종목: {len(selections)}개 (통합 DB)")

                for sel in selections:
                    try:
                        entry_price = sel.entry_price
                        if not entry_price or entry_price <= 0:
                            continue

                        # 현재 주가 조회 (테스트용 더미 데이터)
                        price_change = random.uniform(-0.1, 0.1)
                        current_price = entry_price * (1 + price_change)

                        # 수익률 계산
                        price_change_pct = (
                            (current_price - entry_price) / entry_price * 100
                        )
                        (datetime.now().date() - sel.selection_date).days

                        # 기존 추적 데이터 확인
                        existing = (
                            session.query(DailyTracking)
                            .filter(
                                DailyTracking.tracking_date == sel.selection_date,
                                DailyTracking.strategy_name == sel.stock_code,
                            )
                            .first()
                        )

                        if existing:
                            existing.predicted_return = sel.expected_return
                            existing.actual_return = price_change_pct
                            existing.prediction_error = (
                                sel.expected_return or 0
                            ) - price_change_pct
                            existing.direction_correct = (
                                1
                                if ((sel.expected_return or 0) > 0)
                                == (price_change_pct > 0)
                                else 0
                            )
                        else:
                            new_tracking = DailyTracking(
                                tracking_date=sel.selection_date,
                                strategy_name=sel.stock_code,
                                predicted_return=sel.expected_return,
                                actual_return=price_change_pct,
                                prediction_error=(sel.expected_return or 0)
                                - price_change_pct,
                                direction_correct=(
                                    1
                                    if ((sel.expected_return or 0) > 0)
                                    == (price_change_pct > 0)
                                    else 0
                                ),
                            )
                            session.add(new_tracking)

                        updated_count += 1

                    except Exception as e:
                        self.logger.warning(
                            f"종목 {sel.stock_code} 성과 추적 실패: {e}"
                        )
                        continue

            self.logger.info(f"성과 추적 업데이트 완료 (통합 DB): {updated_count}건")
            return updated_count

        except SQLAlchemyError as e:
            self.logger.error(f"성과 추적 업데이트 실패 (통합 DB): {e}", exc_info=True)
            return 0

    def _update_performance_tracking_sqlite(self, max_days_back: int = 30) -> int:
        """SQLite로 성과 추적 업데이트 (폴백)"""
        try:
            import random

            updated_count = 0

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cutoff_date = (datetime.now() - timedelta(days=max_days_back)).strftime(
                    "%Y%m%d"
                )

                cursor.execute(
                    """
                    SELECT DISTINCT stock_code, stock_name, selection_date, entry_price
                    FROM selection_history
                    WHERE selection_date >= ? AND entry_price IS NOT NULL
                    ORDER BY selection_date DESC
                """,
                    (cutoff_date,),
                )

                selections = cursor.fetchall()
                self.logger.info(f"성과 추적 대상 종목: {len(selections)}개 (SQLite)")

                for stock_code, stock_name, selection_date, entry_price in selections:
                    try:
                        # 테스트용 더미 현재가
                        price_change = random.uniform(-0.1, 0.1)
                        current_price = entry_price * (1 + price_change)

                        if current_price and current_price > 0:
                            price_change_pct = (
                                (current_price - entry_price) / entry_price * 100
                            )
                            selection_dt = datetime.strptime(selection_date, "%Y%m%d")
                            days_tracked = (datetime.now() - selection_dt).days

                            cursor.execute(
                                """
                                SELECT max_gain, max_loss FROM performance_tracking
                                WHERE stock_code = ? AND tracking_date = ?
                            """,
                                (stock_code, selection_date),
                            )

                            existing = cursor.fetchone()
                            if existing:
                                max_gain = max(existing[0], price_change_pct)
                                max_loss = min(existing[1], price_change_pct)
                            else:
                                max_gain = max(0, price_change_pct)
                                max_loss = min(0, price_change_pct)

                            cursor.execute(
                                """
                                INSERT OR REPLACE INTO performance_tracking
                                (stock_code, tracking_date, entry_price, current_price,
                                 price_change_pct, days_tracked, max_gain, max_loss, is_active)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                (
                                    stock_code,
                                    selection_date,
                                    entry_price,
                                    current_price,
                                    price_change_pct,
                                    days_tracked,
                                    max_gain,
                                    max_loss,
                                    days_tracked <= max_days_back,
                                ),
                            )

                            updated_count += 1

                    except Exception as e:
                        self.logger.warning(f"종목 {stock_code} 성과 추적 실패: {e}")
                        continue

                conn.commit()

            self.logger.info(f"성과 추적 업데이트 완료 (SQLite): {updated_count}건")
            return updated_count

        except Exception as e:
            self.logger.error(f"성과 추적 업데이트 실패 (SQLite): {e}", exc_info=True)
            return 0

    def calculate_learning_metrics(self) -> Dict[str, float]:
        """학습용 메트릭 계산

        통합 DB 사용 시 SQLAlchemy, 아니면 SQLite 사용
        """
        if self._unified_db_available:
            return self._calculate_learning_metrics_unified()
        return self._calculate_learning_metrics_sqlite()

    def _calculate_learning_metrics_unified(self) -> Dict[str, float]:
        """통합 DB로 학습용 메트릭 계산 (SQLAlchemy)"""
        try:
            from sqlalchemy import func, case
            from ..database.unified_db import get_session
            from ..database.models import (
                ScreeningHistory as DBScreeningHistory,
                DailyTracking,
                LearningMetrics as DBLearningMetrics,
            )

            metrics = {}

            with get_session() as session:
                # 선정 종목들의 성과 (DailyTracking 기반)
                tracking_stats = session.query(
                    func.avg(DailyTracking.actual_return).label("avg_return"),
                    func.count(DailyTracking.id).label("count"),
                    func.sum(case((DailyTracking.actual_return > 0, 1), else_=0)).label(
                        "win_count"
                    ),
                ).first()

                if tracking_stats and tracking_stats.count and tracking_stats.count > 0:
                    metrics["selection_avg_performance"] = float(
                        tracking_stats.avg_return or 0
                    )
                    metrics["selection_win_rate"] = (
                        float(tracking_stats.win_count or 0)
                        / tracking_stats.count
                        * 100
                    )
                    metrics["selection_sample_count"] = tracking_stats.count

                # 스크리닝 통과 종목 통계
                screening_stats = session.query(
                    func.count(DBScreeningHistory.id).label("total"),
                    func.sum(case((DBScreeningHistory.passed == 1, 1), else_=0)).label(
                        "passed"
                    ),
                ).first()

                if (
                    screening_stats
                    and screening_stats.total
                    and screening_stats.total > 0
                ):
                    metrics["screening_total_count"] = screening_stats.total
                    metrics["screening_pass_rate"] = (
                        float(screening_stats.passed or 0) / screening_stats.total * 100
                    )

                # 방향 예측 정확도
                direction_stats = (
                    session.query(
                        func.count(DailyTracking.id).label("total"),
                        func.sum(
                            case((DailyTracking.direction_correct == 1, 1), else_=0)
                        ).label("correct"),
                    )
                    .filter(DailyTracking.direction_correct.isnot(None))
                    .first()
                )

                if (
                    direction_stats
                    and direction_stats.total
                    and direction_stats.total > 0
                ):
                    metrics["direction_accuracy"] = (
                        float(direction_stats.correct or 0)
                        / direction_stats.total
                        * 100
                    )

                # 메트릭 저장
                today = datetime.now().date()
                for metric_name, value in metrics.items():
                    if isinstance(value, (int, float)):
                        existing = (
                            session.query(DBLearningMetrics)
                            .filter(
                                DBLearningMetrics.metric_date == today,
                                DBLearningMetrics.metric_type == "performance",
                                DBLearningMetrics.model_name == metric_name,
                            )
                            .first()
                        )

                        if existing:
                            existing.value = float(value)
                        else:
                            new_metric = DBLearningMetrics(
                                metric_date=today,
                                metric_type="performance",
                                model_name=metric_name,
                                value=float(value),
                            )
                            session.add(new_metric)

            self.logger.info(f"학습 메트릭 계산 완료 (통합 DB): {len(metrics)}개")
            return metrics

        except SQLAlchemyError as e:
            self.logger.error(f"학습 메트릭 계산 실패 (통합 DB): {e}", exc_info=True)
            return {}

    def _calculate_learning_metrics_sqlite(self) -> Dict[str, float]:
        """SQLite로 학습용 메트릭 계산 (폴백)"""
        try:
            metrics = {}

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 스크리닝 정확도
                cursor.execute(
                    """
                    SELECT AVG(pt.price_change_pct) as avg_performance,
                           COUNT(*) as count,
                           SUM(CASE WHEN pt.price_change_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
                    FROM screening_history sh
                    JOIN performance_tracking pt ON sh.stock_code = pt.stock_code AND sh.screening_date = pt.tracking_date
                    WHERE sh.passed = 1 AND pt.is_active = 1
                """
                )

                screening_perf = cursor.fetchone()
                if screening_perf and screening_perf[1] > 0:
                    metrics["screening_avg_performance"] = screening_perf[0] or 0
                    metrics["screening_win_rate"] = screening_perf[2] or 0
                    metrics["screening_sample_count"] = screening_perf[1]

                # 선정 종목들의 성과
                cursor.execute(
                    """
                    SELECT AVG(price_change_pct) as avg_performance,
                           COUNT(*) as count,
                           SUM(CASE WHEN price_change_pct > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate,
                           AVG(max_gain) as avg_max_gain,
                           AVG(max_loss) as avg_max_loss
                    FROM performance_tracking
                    WHERE is_active = 1
                """
                )

                selection_perf = cursor.fetchone()
                if selection_perf and selection_perf[1] > 0:
                    metrics["selection_avg_performance"] = selection_perf[0] or 0
                    metrics["selection_win_rate"] = selection_perf[2] or 0
                    metrics["selection_sample_count"] = selection_perf[1]
                    metrics["avg_max_gain"] = selection_perf[3] or 0
                    metrics["avg_max_loss"] = selection_perf[4] or 0

                # 섹터별 성과
                cursor.execute(
                    """
                    SELECT sh.sector, AVG(pt.price_change_pct) as avg_perf
                    FROM screening_history sh
                    JOIN performance_tracking pt ON sh.stock_code = pt.stock_code AND sh.screening_date = pt.tracking_date
                    WHERE pt.is_active = 1 AND sh.sector IS NOT NULL
                    GROUP BY sh.sector
                    HAVING COUNT(*) >= 3
                    ORDER BY avg_perf DESC
                """
                )

                sector_data = cursor.fetchall()
                if sector_data:
                    metrics["best_sector"] = sector_data[0][0]
                    metrics["best_sector_performance"] = sector_data[0][1]
                    if len(sector_data) > 1:
                        metrics["worst_sector"] = sector_data[-1][0]
                        metrics["worst_sector_performance"] = sector_data[-1][1]

                # 메트릭 저장
                today = datetime.now().strftime("%Y%m%d")
                for metric_name, value in metrics.items():
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO learning_metrics
                        (date, metric_type, metric_name, value)
                        VALUES (?, 'performance', ?, ?)
                    """,
                        (today, metric_name, value),
                    )

                conn.commit()

            self.logger.info(f"학습 메트릭 계산 완료 (SQLite): {len(metrics)}개")
            return metrics

        except Exception as e:
            self.logger.error(f"학습 메트릭 계산 실패 (SQLite): {e}", exc_info=True)
            return {}

    def run_full_sync(self) -> Dict[str, int]:
        """전체 데이터 동기화 실행"""
        try:
            self.logger.info("=== 전체 데이터 동기화 시작 ===")

            results = {
                "screening_synced": self.sync_screening_results(),
                "selection_synced": self.sync_selection_results(),
                "performance_updated": self.update_performance_tracking(),
            }

            # 학습 메트릭 계산
            metrics = self.calculate_learning_metrics()
            results["metrics_calculated"] = len(metrics)

            self.logger.info(f"전체 동기화 완료: {results}")
            return results

        except Exception as e:
            self.logger.error(f"전체 데이터 동기화 실패: {e}", exc_info=True)
            return {"error": str(e)}


# 싱글톤 인스턴스
_data_synchronizer = None


def get_data_synchronizer() -> DataSynchronizer:
    """데이터 동기화 시스템 싱글톤 인스턴스 반환"""
    global _data_synchronizer
    if _data_synchronizer is None:
        _data_synchronizer = DataSynchronizer()
    return _data_synchronizer
