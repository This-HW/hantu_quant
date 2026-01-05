"""
PostgreSQL 에러 로그 핸들러

에러/크리티컬 레벨 로그를 PostgreSQL error_logs 테이블에 저장합니다.
파일 로깅과 병행하여 중요 에러를 중앙에서 추적할 수 있습니다.
"""

import logging
import traceback
import json
from datetime import datetime
from typing import Optional, Dict, Any
from threading import Lock
from queue import Queue, Empty
import threading

# SQLAlchemy import (lazy)
_engine = None
_session_factory = None
_init_lock = Lock()


def _get_db_connection():
    """데이터베이스 연결 가져오기 (싱글톤)"""
    global _engine, _session_factory

    if _engine is None:
        with _init_lock:
            if _engine is None:
                try:
                    from sqlalchemy import create_engine
                    from sqlalchemy.orm import sessionmaker
                    from core.config import settings

                    if settings.DB_TYPE == 'postgresql':
                        _engine = create_engine(
                            settings.DATABASE_URL,
                            pool_size=2,
                            max_overflow=3,
                            pool_timeout=10,
                            pool_pre_ping=True
                        )
                    else:
                        _engine = create_engine(
                            settings.DATABASE_URL,
                            connect_args={'check_same_thread': False}
                        )

                    _session_factory = sessionmaker(bind=_engine)
                except Exception:
                    return None, None

    return _engine, _session_factory


class PostgreSQLErrorHandler(logging.Handler):
    """
    PostgreSQL 에러 로그 핸들러

    ERROR 이상 레벨의 로그를 PostgreSQL error_logs 테이블에 저장합니다.
    비동기 큐를 사용하여 로깅 성능에 영향을 최소화합니다.
    """

    def __init__(
        self,
        service_name: str = "hantu_quant",
        level: int = logging.ERROR,
        batch_size: int = 10,
        flush_interval: float = 5.0
    ):
        """
        초기화

        Args:
            service_name: 서비스 이름 (api-server, scheduler 등)
            level: 최소 로그 레벨 (기본 ERROR)
            batch_size: 배치 저장 크기
            flush_interval: 자동 플러시 간격 (초)
        """
        super().__init__(level)
        self.service_name = service_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # 비동기 처리를 위한 큐
        self._queue: Queue = Queue()
        self._shutdown = False

        # 백그라운드 스레드 시작
        self._worker = threading.Thread(target=self._process_queue, daemon=True)
        self._worker.start()

    def emit(self, record: logging.LogRecord):
        """로그 레코드 처리"""
        try:
            log_entry = self._format_record(record)
            self._queue.put(log_entry)
        except Exception:
            self.handleError(record)

    def _format_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        """로그 레코드를 딕셔너리로 변환"""
        # 스택 트레이스 추출
        stack_trace = None
        if record.exc_info:
            stack_trace = ''.join(traceback.format_exception(*record.exc_info))

        # 컨텍스트 정보 추출
        context = {}
        if hasattr(record, 'context_data'):
            context = record.context_data
        if hasattr(record, 'data'):
            context.update(record.data)

        return {
            'timestamp': datetime.now(),
            'level': record.levelname,
            'service': self.service_name,
            'module': record.module,
            'function': record.funcName,
            'message': record.getMessage(),
            'error_type': record.exc_info[0].__name__ if record.exc_info else None,
            'stack_trace': stack_trace,
            'context': json.dumps(context) if context else None,
        }

    def _process_queue(self):
        """백그라운드에서 큐 처리"""
        batch = []
        last_flush = datetime.now()

        while not self._shutdown:
            try:
                # 타임아웃과 함께 큐에서 가져오기
                try:
                    entry = self._queue.get(timeout=1.0)
                    batch.append(entry)
                except Empty:
                    pass

                # 배치 크기 도달 또는 플러시 간격 초과 시 저장
                elapsed = (datetime.now() - last_flush).total_seconds()
                if len(batch) >= self.batch_size or (batch and elapsed >= self.flush_interval):
                    self._flush_batch(batch)
                    batch = []
                    last_flush = datetime.now()

            except Exception:
                # 에러 발생 시 배치 초기화
                batch = []

        # 종료 시 남은 배치 플러시
        if batch:
            self._flush_batch(batch)

    def _flush_batch(self, batch: list):
        """배치를 데이터베이스에 저장"""
        if not batch:
            return

        _, session_factory = _get_db_connection()
        if session_factory is None:
            return

        try:
            from core.database.models import ErrorLog

            session = session_factory()
            try:
                for entry in batch:
                    error_log = ErrorLog(
                        timestamp=entry['timestamp'],
                        level=entry['level'],
                        service=entry['service'],
                        module=entry['module'],
                        function=entry['function'],
                        message=entry['message'],
                        error_type=entry['error_type'],
                        stack_trace=entry['stack_trace'],
                        context=entry['context'],
                    )
                    session.add(error_log)

                session.commit()
            except Exception:
                session.rollback()
            finally:
                session.close()
        except Exception:
            pass  # DB 저장 실패는 무시 (로깅 시스템 자체가 실패하면 안됨)

    def close(self):
        """핸들러 종료"""
        self._shutdown = True
        if self._worker.is_alive():
            self._worker.join(timeout=5.0)
        super().close()


def setup_db_error_logging(
    service_name: str,
    logger_name: str = "",
    level: int = logging.ERROR
) -> Optional[PostgreSQLErrorHandler]:
    """
    DB 에러 로깅 설정

    Args:
        service_name: 서비스 이름
        logger_name: 로거 이름 (빈 문자열이면 루트 로거)
        level: 최소 로그 레벨

    Returns:
        설정된 핸들러 또는 None (DB 사용 불가 시)
    """
    # DB 연결 확인
    engine, _ = _get_db_connection()
    if engine is None:
        return None

    # 핸들러 생성 및 추가
    handler = PostgreSQLErrorHandler(service_name=service_name, level=level)

    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)

    return handler


def get_recent_errors(
    service: Optional[str] = None,
    level: Optional[str] = None,
    limit: int = 50
) -> list:
    """
    최근 에러 조회

    Args:
        service: 서비스 필터
        level: 레벨 필터
        limit: 최대 조회 수

    Returns:
        에러 로그 목록
    """
    _, session_factory = _get_db_connection()
    if session_factory is None:
        return []

    try:
        from core.database.models import ErrorLog
        from sqlalchemy import desc

        session = session_factory()
        try:
            query = session.query(ErrorLog)

            if service:
                query = query.filter(ErrorLog.service == service)
            if level:
                query = query.filter(ErrorLog.level == level)

            results = (
                query
                .order_by(desc(ErrorLog.timestamp))
                .limit(limit)
                .all()
            )

            return [
                {
                    'id': e.id,
                    'timestamp': e.timestamp.isoformat() if e.timestamp else None,
                    'level': e.level,
                    'service': e.service,
                    'module': e.module,
                    'function': e.function,
                    'message': e.message,
                    'error_type': e.error_type,
                    'stack_trace': e.stack_trace,
                    'context': e.context,
                    'resolved': e.resolved.isoformat() if e.resolved else None,
                }
                for e in results
            ]
        finally:
            session.close()
    except Exception:
        return []


def mark_error_resolved(error_id: int, resolution_note: str) -> bool:
    """
    에러를 해결됨으로 표시

    Args:
        error_id: 에러 ID
        resolution_note: 해결 방법 메모

    Returns:
        성공 여부
    """
    _, session_factory = _get_db_connection()
    if session_factory is None:
        return False

    try:
        from core.database.models import ErrorLog

        session = session_factory()
        try:
            error = session.query(ErrorLog).filter(ErrorLog.id == error_id).first()
            if error:
                error.resolved = datetime.now()
                error.resolution_note = resolution_note
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
    except Exception:
        return False
