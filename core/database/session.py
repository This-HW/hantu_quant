"""
Database session management module.
Supports both SQLite (local development) and PostgreSQL (production).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError
from contextlib import contextmanager
import os
from pathlib import Path

from core.config import settings
from core.utils import get_logger
from .models import Base

logger = get_logger(__name__)

class DatabaseSession:
    """데이터베이스 세션 관리 (SQLite/PostgreSQL 지원)"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """초기화"""
        self._init_database()
        self.session = self._create_session()

    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            database_url = settings.DATABASE_URL

            # SQLite인 경우 디렉토리 생성
            if settings.DB_TYPE == 'sqlite':
                db_dir = os.path.dirname(settings.DB_PATH)
                Path(db_dir).mkdir(parents=True, exist_ok=True)

                # SQLite 엔진 생성
                self.engine = create_engine(
                    database_url,
                    connect_args={'check_same_thread': False}
                )
                logger.info(f"SQLite 데이터베이스 연결 완료 - {settings.DB_PATH}")
            else:
                # PostgreSQL 엔진 생성 (커넥션 풀 사용)
                self.engine = create_engine(
                    database_url,
                    poolclass=QueuePool,
                    pool_size=settings.DB_POOL_SIZE,
                    max_overflow=settings.DB_MAX_OVERFLOW,
                    pool_timeout=settings.DB_POOL_TIMEOUT,
                    pool_recycle=settings.DB_POOL_RECYCLE,
                    pool_pre_ping=True  # 연결 상태 확인
                )
                logger.info("PostgreSQL 데이터베이스 연결 완료")

            # 테이블 생성
            Base.metadata.create_all(self.engine)

        except SQLAlchemyError as e:
            logger.error(f"데이터베이스 오류 발생: {str(e)}", exc_info=True)
            raise
    
    def _create_session(self) -> Session:
        """
        세션 생성

        Returns:
            Session: SQLAlchemy 세션
        """
        Session = sessionmaker(bind=self.engine)
        return Session()
    
    @contextmanager
    def get_session(self) -> Session:
        """
        세션 컨텍스트 매니저

        Yields:
            Session: SQLAlchemy 세션
        """
        session = self._create_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            logger.error(f"DB 세션 에러: {e}", exc_info=True)
            session.rollback()
            raise
        finally:
            session.close()
    
    def close(self):
        """세션 종료"""
        if hasattr(self, 'session'):
            self.session.close()
        logger.info("데이터베이스 연결 종료")
    
    def dispose(self):
        """데이터베이스 연결 종료"""
        if hasattr(self, 'engine'):
            self.engine.dispose()
            logger.info("데이터베이스 연결 종료")
            
    def recreate_tables(self):
        """데이터베이스 테이블 재생성"""
        try:
            Base.metadata.drop_all(self.engine)
            Base.metadata.create_all(self.engine)
            logger.info("데이터베이스 테이블 재생성 완료")
        except SQLAlchemyError as e:
            logger.error(f"테이블 재생성 중 오류 발생: {str(e)}", exc_info=True)
            raise 