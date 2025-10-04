#!/usr/bin/env python
"""
한투 퀀트 프로젝트 관리 스크립트
"""

import os
import sys
import argparse
import logging
from pathlib import Path
import subprocess
from datetime import datetime

# 프로젝트 루트 설정
ROOT_DIR = Path(__file__).parent.parent
os.chdir(ROOT_DIR)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('hantu-manager')

def setup_environment():
    """환경 설정 및 필요한 디렉토리 생성"""
    logger.info("환경 설정을 시작합니다...")
    
    # 필요한 디렉토리 생성
    dirs = [
        'data',
        'data/db',
        'data/stock',
        'data/token',
        'data/historical',
        'data/metadata',
        'logs'
    ]
    
    for dir_path in dirs:
        path = ROOT_DIR / dir_path
        if not path.exists():
            path.mkdir(parents=True)
            logger.info(f"디렉토리 생성: {path}")
    
    # .env 파일 확인
    env_file = ROOT_DIR / '.env'
    env_example = ROOT_DIR / '.env.example'
    
    if not env_file.exists() and env_example.exists():
        logger.warning(".env 파일이 없습니다. .env.example을 복사하여 생성하세요.")
        logger.warning("명령어: cp .env.example .env")
    
    logger.info("환경 설정이 완료되었습니다.")

def install_deps():
    """의존성 패키지 설치"""
    logger.info("의존성 패키지 설치를 시작합니다...")
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "./hantu_common"], check=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "./hantu_backtest"], check=True)
        logger.info("의존성 패키지 설치가 완료되었습니다.")
    except subprocess.CalledProcessError as e:
        logger.error(f"의존성 패키지 설치 중 오류 발생: {e}")
        sys.exit(1)

def backup_data():
    """데이터 백업"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT_DIR / 'backups' / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"데이터 백업을 시작합니다... 백업 위치: {backup_dir}")
    
    # 백업할 디렉토리
    dirs_to_backup = [
        'data/db',
        'data/token',
        'data/historical'
    ]
    
    for dir_path in dirs_to_backup:
        source_dir = ROOT_DIR / dir_path
        if source_dir.exists():
            target_dir = backup_dir / dir_path
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            
            # rsync 또는 cp 명령으로 복사
            try:
                if sys.platform == 'win32':
                    subprocess.run(["xcopy", str(source_dir), str(target_dir), "/E", "/I", "/H"], check=True)
                else:
                    subprocess.run(["cp", "-r", str(source_dir), str(target_dir)], check=True)
                logger.info(f"백업 완료: {dir_path}")
            except subprocess.CalledProcessError as e:
                logger.error(f"백업 중 오류 발생: {e}")
    
    logger.info(f"데이터 백업이 완료되었습니다: {backup_dir}")
    return backup_dir

def clean_logs():
    """로그 파일 정리"""
    logger.info("로그 파일 정리를 시작합니다...")
    
    log_dir = ROOT_DIR / 'logs'
    if not log_dir.exists():
        logger.info("로그 디렉토리가 없습니다.")
        return
    
    # 30일 이상 된 로그 파일 정리
    import time
    current_time = time.time()
    days_to_keep = 30
    seconds_to_keep = days_to_keep * 24 * 60 * 60
    
    count = 0
    for log_file in log_dir.glob('*.log'):
        if log_file.name == 'trading.log':
            continue  # 현재 트레이딩 로그는 보존
            
        file_mtime = log_file.stat().st_mtime
        if current_time - file_mtime > seconds_to_keep:
            log_file.unlink()
            count += 1
    
    logger.info(f"로그 파일 {count}개가 정리되었습니다.")

def reset_tokens():
    """토큰 파일 초기화"""
    logger.info("토큰 파일 초기화를 시작합니다...")
    
    token_dir = ROOT_DIR / 'data' / 'token'
    if not token_dir.exists():
        logger.info("토큰 디렉토리가 없습니다.")
        return
    
    # 토큰 파일 삭제
    count = 0
    for token_file in token_dir.glob('token_info_*.json'):
        token_file.unlink()
        count += 1
    
    logger.info(f"토큰 파일 {count}개가 초기화되었습니다.")

def run_tests():
    """테스트 실행"""
    logger.info("테스트 실행을 시작합니다...")
    
    try:
        result = subprocess.run([sys.executable, "-m", "pytest", "-v"], check=False)
        if result.returncode == 0:
            logger.info("모든 테스트가 성공적으로 완료되었습니다.")
        else:
            logger.error("일부 테스트가 실패했습니다.")
    except Exception as e:
        logger.error(f"테스트 실행 중 오류 발생: {e}")

def main():
    parser = argparse.ArgumentParser(description='한투 퀀트 프로젝트 관리 도구')
    
    subparsers = parser.add_subparsers(dest='command', help='실행할 명령')
    
    # 환경 설정
    subparsers.add_parser('setup', help='환경 설정 및 디렉토리 생성')
    
    # 의존성 설치
    subparsers.add_parser('install', help='의존성 패키지 설치')
    
    # 데이터 백업
    subparsers.add_parser('backup', help='데이터 백업')
    
    # 로그 정리
    subparsers.add_parser('clean-logs', help='로그 파일 정리')
    
    # 토큰 초기화
    subparsers.add_parser('reset-tokens', help='토큰 파일 초기화')
    
    # 테스트 실행
    subparsers.add_parser('test', help='테스트 실행')
    
    args = parser.parse_args()
    
    if args.command == 'setup':
        setup_environment()
    elif args.command == 'install':
        install_deps()
    elif args.command == 'backup':
        backup_data()
    elif args.command == 'clean-logs':
        clean_logs()
    elif args.command == 'reset-tokens':
        reset_tokens()
    elif args.command == 'test':
        run_tests()
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 