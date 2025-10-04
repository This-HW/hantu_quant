"""
Pytest configuration file.
"""

import os
import sys
import pytest
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 테스트용 데이터베이스 설정
@pytest.fixture(autouse=True)
def test_db():
    """테스트용 데이터베이스 설정"""
    # 테스트용 데이터베이스 경로 설정
    os.environ['DB_PATH'] = str(project_root / 'tests' / 'test.db')
    
    # 테스트 실행 후 데이터베이스 파일 삭제
    yield
    db_path = Path(os.environ['DB_PATH'])
    if db_path.exists():
        db_path.unlink()

# 테스트용 로깅 설정
@pytest.fixture(autouse=True)
def test_logging():
    """테스트용 로깅 설정"""
    os.environ['LOG_LEVEL'] = 'DEBUG'
    os.environ['LOG_DIR'] = str(project_root / 'tests' / 'logs')
    
    # 로그 디렉토리 생성
    log_dir = Path(os.environ['LOG_DIR'])
    log_dir.mkdir(parents=True, exist_ok=True) 