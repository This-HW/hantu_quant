"""
Database session management module.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session
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
    """데이터베이스 세션 관리"""
    
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
            # 데이터베이스 디렉토리 생성
            db_dir = os.path.dirname(settings.DB_PATH)
            Path(db_dir).mkdir(parents=True, exist_ok=True)
            
            # 데이터베이스 엔진 생성
            self.engine = create_engine(
                f'sqlite:///{settings.DB_PATH}',
                connect_args={'check_same_thread': False}
            )
            
            # 테이블 생성
            Base.metadata.create_all(self.engine)
            logger.info(f"데이터베이스 연결 완료 - {settings.DB_PATH}")
            
        except SQLAlchemyError as e:
            logger.error(f"데이터베이스 오류 발생: {str(e)}")
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
            logger.error(f"테이블 재생성 중 오류 발생: {str(e)}")
            raise 