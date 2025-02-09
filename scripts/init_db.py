"""
데이터베이스 초기화 스크립트
"""

from core.database.session import DatabaseSession

def init_database():
    """데이터베이스 초기화 및 테이블 생성"""
    print("데이터베이스 초기화를 시작합니다...")
    db = DatabaseSession()
    print("데이터베이스 테이블이 생성되었습니다.")

if __name__ == "__main__":
    init_database() 