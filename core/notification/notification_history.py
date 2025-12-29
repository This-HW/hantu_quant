"""
알림 이력 저장 모듈

Feature 2.3: 알림 이력 저장 기능
- T-2.3.1: 알림 이력 저장 스키마 설계 (SQLite)
- T-2.3.2: NotificationManager에 이력 저장 기능 추가
- T-2.3.3: 알림 이력 조회 API
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from contextlib import contextmanager

from core.utils.log_utils import get_trace_id

logger = logging.getLogger(__name__)


@dataclass
class NotificationHistoryEntry:
    """알림 이력 항목"""
    id: Optional[int] = None
    alert_id: str = ""
    alert_type: str = ""
    level: str = ""
    title: str = ""
    message: str = ""
    channel: str = ""  # telegram, email, etc.
    recipient: str = ""
    status: str = ""  # sent, failed, filtered
    error_message: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    response_data: Optional[str] = None  # JSON 문자열

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        result = asdict(self)
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.sent_at:
            result["sent_at"] = self.sent_at.isoformat()
        return result


class NotificationHistoryDB:
    """
    알림 이력 데이터베이스

    SQLite 기반으로 알림 발송 이력을 저장하고 조회합니다.
    """

    def __init__(self, db_path: str = "data/notification_history.db"):
        """
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """데이터베이스 초기화"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT,
                    channel TEXT NOT NULL,
                    recipient TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    trace_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent_at TIMESTAMP,
                    response_data TEXT
                )
            """)

            # 인덱스 생성
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_alert_id
                ON notification_history(alert_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON notification_history(created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status
                ON notification_history(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trace_id
                ON notification_history(trace_id)
            """)

            # 통계 테이블
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notification_stats (
                    date TEXT PRIMARY KEY,
                    total_count INTEGER DEFAULT 0,
                    sent_count INTEGER DEFAULT 0,
                    failed_count INTEGER DEFAULT 0,
                    filtered_count INTEGER DEFAULT 0,
                    telegram_count INTEGER DEFAULT 0,
                    email_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """데이터베이스 연결 컨텍스트"""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def save(self, entry: NotificationHistoryEntry) -> int:
        """
        알림 이력 저장

        Args:
            entry: 알림 이력 항목

        Returns:
            저장된 ID
        """
        with self._get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO notification_history (
                    alert_id, alert_type, level, title, message,
                    channel, recipient, status, error_message,
                    trace_id, created_at, sent_at, response_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.alert_id,
                entry.alert_type,
                entry.level,
                entry.title,
                entry.message,
                entry.channel,
                entry.recipient,
                entry.status,
                entry.error_message,
                entry.trace_id or get_trace_id(),
                entry.created_at or datetime.now(),
                entry.sent_at,
                entry.response_data,
            ))

            # 통계 업데이트
            self._update_stats(conn, entry)

            conn.commit()
            return cursor.lastrowid

    def _update_stats(self, conn, entry: NotificationHistoryEntry) -> None:
        """통계 업데이트"""
        date_str = datetime.now().strftime("%Y-%m-%d")

        # UPSERT 패턴
        conn.execute("""
            INSERT INTO notification_stats (date, total_count)
            VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET
                total_count = total_count + 1,
                updated_at = CURRENT_TIMESTAMP
        """, (date_str,))

        if entry.status == "sent":
            conn.execute("""
                UPDATE notification_stats SET sent_count = sent_count + 1
                WHERE date = ?
            """, (date_str,))
        elif entry.status == "failed":
            conn.execute("""
                UPDATE notification_stats SET failed_count = failed_count + 1
                WHERE date = ?
            """, (date_str,))
        elif entry.status == "filtered":
            conn.execute("""
                UPDATE notification_stats SET filtered_count = filtered_count + 1
                WHERE date = ?
            """, (date_str,))

        if entry.channel == "telegram":
            conn.execute("""
                UPDATE notification_stats SET telegram_count = telegram_count + 1
                WHERE date = ?
            """, (date_str,))
        elif entry.channel == "email":
            conn.execute("""
                UPDATE notification_stats SET email_count = email_count + 1
                WHERE date = ?
            """, (date_str,))

    def get_by_id(self, history_id: int) -> Optional[NotificationHistoryEntry]:
        """ID로 조회"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM notification_history WHERE id = ?",
                (history_id,)
            ).fetchone()

            if row:
                return self._row_to_entry(row)
            return None

    def get_by_alert_id(self, alert_id: str) -> List[NotificationHistoryEntry]:
        """알림 ID로 조회"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notification_history WHERE alert_id = ? ORDER BY created_at DESC",
                (alert_id,)
            ).fetchall()

            return [self._row_to_entry(row) for row in rows]

    def get_by_trace_id(self, trace_id: str) -> List[NotificationHistoryEntry]:
        """trace_id로 조회"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM notification_history WHERE trace_id = ? ORDER BY created_at DESC",
                (trace_id,)
            ).fetchall()

            return [self._row_to_entry(row) for row in rows]

    def get_recent(
        self,
        limit: int = 100,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> List[NotificationHistoryEntry]:
        """
        최근 이력 조회

        Args:
            limit: 최대 개수
            status: 상태 필터
            channel: 채널 필터
            since: 시작 시간

        Returns:
            알림 이력 목록
        """
        query = "SELECT * FROM notification_history WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if channel:
            query += " AND channel = ?"
            params.append(channel)

        if since:
            query += " AND created_at >= ?"
            params.append(since.isoformat())

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_entry(row) for row in rows]

    def get_failed(self, limit: int = 50) -> List[NotificationHistoryEntry]:
        """실패한 알림 조회"""
        return self.get_recent(limit=limit, status="failed")

    def get_stats(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        통계 조회

        Args:
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)

        Returns:
            일별 통계 목록
        """
        query = "SELECT * FROM notification_stats WHERE 1=1"
        params = []

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_stats_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        통계 요약

        Args:
            days: 기간 (일)

        Returns:
            통계 요약
        """
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        with self._get_connection() as conn:
            row = conn.execute("""
                SELECT
                    SUM(total_count) as total,
                    SUM(sent_count) as sent,
                    SUM(failed_count) as failed,
                    SUM(filtered_count) as filtered,
                    SUM(telegram_count) as telegram,
                    SUM(email_count) as email
                FROM notification_stats
                WHERE date >= ?
            """, (start_date,)).fetchone()

            if row:
                total = row["total"] or 0
                sent = row["sent"] or 0
                return {
                    "period_days": days,
                    "total": total,
                    "sent": sent,
                    "failed": row["failed"] or 0,
                    "filtered": row["filtered"] or 0,
                    "telegram": row["telegram"] or 0,
                    "email": row["email"] or 0,
                    "success_rate": (sent / total * 100) if total > 0 else 0,
                }

            return {
                "period_days": days,
                "total": 0,
                "sent": 0,
                "failed": 0,
                "filtered": 0,
                "telegram": 0,
                "email": 0,
                "success_rate": 0,
            }

    def cleanup_old(self, days: int = 90) -> int:
        """
        오래된 이력 삭제

        Args:
            days: 보관 기간 (일)

        Returns:
            삭제된 레코드 수
        """
        cutoff = datetime.now() - timedelta(days=days)

        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM notification_history WHERE created_at < ?",
                (cutoff.isoformat(),)
            )
            conn.commit()
            return cursor.rowcount

    def _row_to_entry(self, row: sqlite3.Row) -> NotificationHistoryEntry:
        """Row를 Entry로 변환"""
        return NotificationHistoryEntry(
            id=row["id"],
            alert_id=row["alert_id"],
            alert_type=row["alert_type"],
            level=row["level"],
            title=row["title"],
            message=row["message"],
            channel=row["channel"],
            recipient=row["recipient"],
            status=row["status"],
            error_message=row["error_message"],
            trace_id=row["trace_id"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            sent_at=datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else None,
            response_data=row["response_data"],
        )


# 글로벌 인스턴스
_history_db: Optional[NotificationHistoryDB] = None


def get_notification_history_db(
    db_path: str = "data/notification_history.db"
) -> NotificationHistoryDB:
    """
    NotificationHistoryDB 싱글톤 인스턴스

    Args:
        db_path: 데이터베이스 경로

    Returns:
        NotificationHistoryDB 인스턴스
    """
    global _history_db
    if _history_db is None:
        _history_db = NotificationHistoryDB(db_path)
    return _history_db


def record_notification(
    alert_id: str,
    alert_type: str,
    level: str,
    title: str,
    message: str,
    channel: str,
    status: str,
    recipient: str = "",
    error_message: Optional[str] = None,
    response_data: Optional[Dict] = None,
) -> int:
    """
    알림 이력 기록 헬퍼 함수

    Args:
        alert_id: 알림 ID
        alert_type: 알림 타입
        level: 알림 레벨
        title: 제목
        message: 메시지
        channel: 채널
        status: 상태
        recipient: 수신자
        error_message: 에러 메시지
        response_data: 응답 데이터

    Returns:
        저장된 ID
    """
    db = get_notification_history_db()

    entry = NotificationHistoryEntry(
        alert_id=alert_id,
        alert_type=alert_type,
        level=level,
        title=title,
        message=message[:500] if message else "",  # 메시지 길이 제한
        channel=channel,
        recipient=recipient,
        status=status,
        error_message=error_message,
        trace_id=get_trace_id(),
        created_at=datetime.now(),
        sent_at=datetime.now() if status == "sent" else None,
        response_data=json.dumps(response_data) if response_data else None,
    )

    return db.save(entry)
