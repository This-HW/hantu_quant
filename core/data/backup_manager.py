"""
데이터 백업 및 복구 시스템

중요한 데이터를 자동으로 백업하고 필요시 복구하는 시스템
"""

import os
import shutil
import gzip
import sqlite3
import json
import threading
import time
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import hashlib
import zipfile

from ..utils.logging import get_logger

logger = get_logger(__name__)

class BackupType(Enum):
    """백업 유형"""
    FULL = "full"           # 전체 백업
    INCREMENTAL = "incremental"  # 증분 백업
    DIFFERENTIAL = "differential"  # 차등 백업
    SNAPSHOT = "snapshot"   # 스냅샷

class BackupStatus(Enum):
    """백업 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class RestoreStatus(Enum):
    """복구 상태"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class BackupConfig:
    """백업 설정"""
    name: str
    source_paths: List[str]
    backup_dir: str
    backup_type: BackupType
    
    # 스케줄 설정
    schedule_enabled: bool = True
    schedule_time: str = "02:00"  # 새벽 2시
    schedule_days: List[str] = None  # ['monday', 'wednesday', 'friday']
    
    # 보존 정책
    retention_days: int = 30
    max_backups: int = 10
    
    # 압축 설정
    compression_enabled: bool = True
    compression_level: int = 6
    
    # 검증 설정
    verify_backup: bool = True
    checksum_enabled: bool = True
    
    def __post_init__(self):
        if self.schedule_days is None:
            self.schedule_days = ['daily']

@dataclass
class BackupRecord:
    """백업 기록"""
    backup_id: str
    config_name: str
    backup_type: BackupType
    start_time: datetime
    end_time: Optional[datetime]
    status: BackupStatus
    
    # 백업 정보
    backup_path: str
    file_count: int
    backup_size: int  # bytes
    compressed_size: int  # bytes
    
    # 검증 정보
    checksum: Optional[str] = None
    verified: bool = False
    
    # 에러 정보
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['backup_type'] = self.backup_type.value
        result['status'] = self.status.value
        result['start_time'] = self.start_time.isoformat()
        if self.end_time:
            result['end_time'] = self.end_time.isoformat()
        return result

@dataclass
class RestoreRecord:
    """복구 기록"""
    restore_id: str
    backup_id: str
    restore_path: str
    start_time: datetime
    end_time: Optional[datetime]
    status: RestoreStatus
    
    # 복구 정보
    restored_files: int
    total_size: int
    
    # 에러 정보
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        result = asdict(self)
        result['status'] = self.status.value
        result['start_time'] = self.start_time.isoformat()
        if self.end_time:
            result['end_time'] = self.end_time.isoformat()
        return result

class BackupEngine:
    """백업 엔진"""
    
    def __init__(self):
        """초기화"""
        self._logger = logger
        self._running_backups: Dict[str, threading.Thread] = {}
        
    def create_backup(self, config: BackupConfig) -> BackupRecord:
        """백업 생성
        
        Args:
            config: 백업 설정
            
        Returns:
            백업 기록
        """
        backup_id = f"{config.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        record = BackupRecord(
            backup_id=backup_id,
            config_name=config.name,
            backup_type=config.backup_type,
            start_time=datetime.now(),
            end_time=None,
            status=BackupStatus.PENDING,
            backup_path="",
            file_count=0,
            backup_size=0,
            compressed_size=0
        )
        
        try:
            record.status = BackupStatus.RUNNING
            self._logger.info(f"백업 시작: {backup_id}")
            
            # 백업 경로 생성
            backup_path = self._create_backup_path(config, backup_id)
            record.backup_path = backup_path
            
            # 백업 유형에 따른 처리
            if config.backup_type == BackupType.FULL:
                self._create_full_backup(config, record)
            elif config.backup_type == BackupType.INCREMENTAL:
                self._create_incremental_backup(config, record)
            elif config.backup_type == BackupType.DIFFERENTIAL:
                self._create_differential_backup(config, record)
            elif config.backup_type == BackupType.SNAPSHOT:
                self._create_snapshot_backup(config, record)
            
            # 압축 처리
            if config.compression_enabled:
                self._compress_backup(record, config.compression_level)
            
            # 검증 처리
            if config.verify_backup:
                self._verify_backup(record, config)
            
            record.status = BackupStatus.COMPLETED
            record.end_time = datetime.now()
            
            self._logger.info(f"백업 완료: {backup_id} ({record.file_count}개 파일, {record.backup_size / 1024 / 1024:.1f}MB)")
            
        except Exception as e:
            record.status = BackupStatus.FAILED
            record.error_message = str(e)
            record.end_time = datetime.now()
            self._logger.error(f"백업 실패: {backup_id} - {e}")
        
        return record
    
    def _create_backup_path(self, config: BackupConfig, backup_id: str) -> str:
        """백업 경로 생성"""
        backup_dir = Path(config.backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        return str(backup_dir / backup_id)
    
    def _create_full_backup(self, config: BackupConfig, record: BackupRecord):
        """전체 백업 생성"""
        backup_path = Path(record.backup_path)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        total_size = 0
        file_count = 0
        
        for source_path in config.source_paths:
            source = Path(source_path)
            
            if source.is_file():
                # 단일 파일 백업
                dest_file = backup_path / source.name
                shutil.copy2(source, dest_file)
                total_size += source.stat().st_size
                file_count += 1
                
            elif source.is_dir():
                # 디렉토리 백업
                dest_dir = backup_path / source.name
                
                for root, dirs, files in os.walk(source):
                    root_path = Path(root)
                    rel_path = root_path.relative_to(source.parent)
                    dest_root = backup_path / rel_path
                    dest_root.mkdir(parents=True, exist_ok=True)
                    
                    for file in files:
                        src_file = root_path / file
                        dest_file = dest_root / file
                        
                        try:
                            shutil.copy2(src_file, dest_file)
                            total_size += src_file.stat().st_size
                            file_count += 1
                        except Exception as e:
                            self._logger.warning(f"파일 복사 실패: {src_file} - {e}")
        
        record.backup_size = total_size
        record.file_count = file_count
    
    def _create_incremental_backup(self, config: BackupConfig, record: BackupRecord):
        """증분 백업 생성"""
        # 마지막 백업 시간 확인
        last_backup_time = self._get_last_backup_time(config.name)
        
        if not last_backup_time:
            # 첫 백업인 경우 전체 백업 수행
            self._create_full_backup(config, record)
            return
        
        backup_path = Path(record.backup_path)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        total_size = 0
        file_count = 0
        
        for source_path in config.source_paths:
            source = Path(source_path)
            
            if source.is_file():
                # 파일 수정 시간 확인
                if source.stat().st_mtime > last_backup_time.timestamp():
                    dest_file = backup_path / source.name
                    shutil.copy2(source, dest_file)
                    total_size += source.stat().st_size
                    file_count += 1
                    
            elif source.is_dir():
                for root, dirs, files in os.walk(source):
                    root_path = Path(root)
                    
                    for file in files:
                        src_file = root_path / file
                        
                        if src_file.stat().st_mtime > last_backup_time.timestamp():
                            rel_path = src_file.relative_to(source.parent)
                            dest_file = backup_path / rel_path
                            dest_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            try:
                                shutil.copy2(src_file, dest_file)
                                total_size += src_file.stat().st_size
                                file_count += 1
                            except Exception as e:
                                self._logger.warning(f"파일 복사 실패: {src_file} - {e}")
        
        record.backup_size = total_size
        record.file_count = file_count
    
    def _create_differential_backup(self, config: BackupConfig, record: BackupRecord):
        """차등 백업 생성"""
        # 마지막 전체 백업 시간 확인
        last_full_backup_time = self._get_last_full_backup_time(config.name)
        
        if not last_full_backup_time:
            # 전체 백업이 없으면 전체 백업 수행
            self._create_full_backup(config, record)
            return
        
        backup_path = Path(record.backup_path)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        total_size = 0
        file_count = 0
        
        for source_path in config.source_paths:
            source = Path(source_path)
            
            if source.is_file():
                if source.stat().st_mtime > last_full_backup_time.timestamp():
                    dest_file = backup_path / source.name
                    shutil.copy2(source, dest_file)
                    total_size += source.stat().st_size
                    file_count += 1
                    
            elif source.is_dir():
                for root, dirs, files in os.walk(source):
                    root_path = Path(root)
                    
                    for file in files:
                        src_file = root_path / file
                        
                        if src_file.stat().st_mtime > last_full_backup_time.timestamp():
                            rel_path = src_file.relative_to(source.parent)
                            dest_file = backup_path / rel_path
                            dest_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            try:
                                shutil.copy2(src_file, dest_file)
                                total_size += src_file.stat().st_size
                                file_count += 1
                            except Exception as e:
                                self._logger.warning(f"파일 복사 실패: {src_file} - {e}")
        
        record.backup_size = total_size
        record.file_count = file_count
    
    def _create_snapshot_backup(self, config: BackupConfig, record: BackupRecord):
        """스냅샷 백업 생성"""
        # 스냅샷은 전체 백업과 동일하지만 압축 없이 빠른 복사
        self._create_full_backup(config, record)
    
    def _compress_backup(self, record: BackupRecord, compression_level: int):
        """백업 압축"""
        try:
            backup_path = Path(record.backup_path)
            compressed_path = backup_path.with_suffix('.zip')
            
            with zipfile.ZipFile(compressed_path, 'w', 
                               compression=zipfile.ZIP_DEFLATED,
                               compresslevel=compression_level) as zipf:
                
                for root, dirs, files in os.walk(backup_path):
                    for file in files:
                        file_path = Path(root) / file
                        arc_name = file_path.relative_to(backup_path)
                        zipf.write(file_path, arc_name)
            
            # 원본 디렉토리 삭제
            shutil.rmtree(backup_path)
            
            # 압축된 크기 기록
            record.compressed_size = compressed_path.stat().st_size
            record.backup_path = str(compressed_path)
            
            self._logger.debug(f"백업 압축 완료: {record.backup_size} -> {record.compressed_size} bytes")
            
        except Exception as e:
            self._logger.error(f"백업 압축 중 오류: {e}")
            raise
    
    def _verify_backup(self, record: BackupRecord, config: BackupConfig):
        """백업 검증"""
        try:
            backup_path = Path(record.backup_path)
            
            if backup_path.suffix == '.zip':
                # 압축 파일 검증
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    # ZIP 파일 무결성 검사
                    bad_files = zipf.testzip()
                    if bad_files:
                        raise Exception(f"압축 파일 손상: {bad_files}")
            
            # 체크섬 계산
            if config.checksum_enabled:
                checksum = self._calculate_checksum(backup_path)
                record.checksum = checksum
            
            record.verified = True
            self._logger.debug(f"백업 검증 완료: {record.backup_id}")
            
        except Exception as e:
            self._logger.error(f"백업 검증 중 오류: {e}")
            record.verified = False
            raise
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """파일 체크섬 계산"""
        hash_md5 = hashlib.md5()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return hash_md5.hexdigest()
    
    def _get_last_backup_time(self, config_name: str) -> Optional[datetime]:
        """마지막 백업 시간 조회"""
        # 실제 구현에서는 데이터베이스에서 조회
        return None
    
    def _get_last_full_backup_time(self, config_name: str) -> Optional[datetime]:
        """마지막 전체 백업 시간 조회"""
        # 실제 구현에서는 데이터베이스에서 조회
        return None

class RestoreEngine:
    """복구 엔진"""
    
    def __init__(self):
        """초기화"""
        self._logger = logger
    
    def restore_backup(self, backup_path: str, restore_path: str, 
                      backup_id: str = None) -> RestoreRecord:
        """백업 복구
        
        Args:
            backup_path: 백업 파일 경로
            restore_path: 복구 대상 경로
            backup_id: 백업 ID
            
        Returns:
            복구 기록
        """
        restore_id = f"restore_{int(time.time())}"
        
        record = RestoreRecord(
            restore_id=restore_id,
            backup_id=backup_id or "unknown",
            restore_path=restore_path,
            start_time=datetime.now(),
            end_time=None,
            status=RestoreStatus.PENDING,
            restored_files=0,
            total_size=0
        )
        
        try:
            record.status = RestoreStatus.RUNNING
            self._logger.info(f"복구 시작: {restore_id}")
            
            backup_file = Path(backup_path)
            restore_dir = Path(restore_path)
            restore_dir.mkdir(parents=True, exist_ok=True)
            
            if backup_file.suffix == '.zip':
                # 압축 파일 복구
                self._restore_from_zip(backup_file, restore_dir, record)
            else:
                # 디렉토리 복구
                self._restore_from_directory(backup_file, restore_dir, record)
            
            record.status = RestoreStatus.COMPLETED
            record.end_time = datetime.now()
            
            self._logger.info(f"복구 완료: {restore_id} ({record.restored_files}개 파일)")
            
        except Exception as e:
            record.status = RestoreStatus.FAILED
            record.error_message = str(e)
            record.end_time = datetime.now()
            self._logger.error(f"복구 실패: {restore_id} - {e}")
        
        return record
    
    def _restore_from_zip(self, backup_file: Path, restore_dir: Path, record: RestoreRecord):
        """ZIP 파일에서 복구"""
        with zipfile.ZipFile(backup_file, 'r') as zipf:
            members = zipf.infolist()
            
            for member in members:
                if not member.is_dir():
                    try:
                        zipf.extract(member, restore_dir)
                        record.restored_files += 1
                        record.total_size += member.file_size
                    except Exception as e:
                        self._logger.warning(f"파일 복구 실패: {member.filename} - {e}")
    
    def _restore_from_directory(self, backup_dir: Path, restore_dir: Path, record: RestoreRecord):
        """디렉토리에서 복구"""
        for root, dirs, files in os.walk(backup_dir):
            root_path = Path(root)
            rel_path = root_path.relative_to(backup_dir)
            dest_root = restore_dir / rel_path
            dest_root.mkdir(parents=True, exist_ok=True)
            
            for file in files:
                src_file = root_path / file
                dest_file = dest_root / file
                
                try:
                    shutil.copy2(src_file, dest_file)
                    record.restored_files += 1
                    record.total_size += src_file.stat().st_size
                except Exception as e:
                    self._logger.warning(f"파일 복구 실패: {src_file} - {e}")

class BackupManager:
    """백업 관리자"""
    
    def __init__(self, db_path: str = "data/backup_manager.db"):
        """초기화
        
        Args:
            db_path: 백업 관리 데이터베이스 경로
        """
        self._logger = logger
        self._db_path = db_path
        
        # 엔진 초기화
        self._backup_engine = BackupEngine()
        self._restore_engine = RestoreEngine()
        
        # 백업 설정
        self._backup_configs: Dict[str, BackupConfig] = {}
        
        # 스케줄러 상태
        self._scheduler_running = False
        self._scheduler_thread: Optional[threading.Thread] = None
        
        # 데이터베이스 초기화
        self._init_database()
        
        # 기본 백업 설정
        self._setup_default_configs()
        
        self._logger.info("BackupManager 초기화 완료")
    
    def _init_database(self):
        """데이터베이스 초기화"""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self._db_path) as conn:
                # 백업 기록 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS backup_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        backup_id TEXT NOT NULL UNIQUE,
                        config_name TEXT NOT NULL,
                        backup_type TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        status TEXT NOT NULL,
                        backup_path TEXT NOT NULL,
                        file_count INTEGER,
                        backup_size INTEGER,
                        compressed_size INTEGER,
                        checksum TEXT,
                        verified INTEGER DEFAULT 0,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 복구 기록 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS restore_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        restore_id TEXT NOT NULL UNIQUE,
                        backup_id TEXT NOT NULL,
                        restore_path TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        status TEXT NOT NULL,
                        restored_files INTEGER,
                        total_size INTEGER,
                        error_message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # 백업 설정 테이블
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS backup_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        source_paths TEXT NOT NULL,  -- JSON
                        backup_dir TEXT NOT NULL,
                        backup_type TEXT NOT NULL,
                        schedule_enabled INTEGER DEFAULT 1,
                        schedule_time TEXT DEFAULT '02:00',
                        schedule_days TEXT,  -- JSON
                        retention_days INTEGER DEFAULT 30,
                        max_backups INTEGER DEFAULT 10,
                        compression_enabled INTEGER DEFAULT 1,
                        compression_level INTEGER DEFAULT 6,
                        verify_backup INTEGER DEFAULT 1,
                        checksum_enabled INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.commit()
                self._logger.info("백업 관리 데이터베이스 초기화 완료")
                
        except Exception as e:
            self._logger.error(f"데이터베이스 초기화 중 오류: {e}")
    
    def _setup_default_configs(self):
        """기본 백업 설정"""
        default_configs = [
            BackupConfig(
                name="database_backup",
                source_paths=["data/"],
                backup_dir="backups/database",
                backup_type=BackupType.FULL,
                schedule_time="02:00",
                retention_days=30
            ),
            BackupConfig(
                name="config_backup",
                source_paths=["config/", ".env"],
                backup_dir="backups/config",
                backup_type=BackupType.INCREMENTAL,
                schedule_time="03:00",
                retention_days=7
            ),
            BackupConfig(
                name="logs_backup",
                source_paths=["logs/"],
                backup_dir="backups/logs",
                backup_type=BackupType.DIFFERENTIAL,
                schedule_time="04:00",
                retention_days=14
            )
        ]
        
        for config in default_configs:
            self.add_backup_config(config)
    
    def add_backup_config(self, config: BackupConfig):
        """백업 설정 추가
        
        Args:
            config: 백업 설정
        """
        try:
            self._backup_configs[config.name] = config
            self._save_backup_config(config)
            self._logger.info(f"백업 설정 추가: {config.name}")
            
        except Exception as e:
            self._logger.error(f"백업 설정 추가 중 오류: {e}")
    
    def _save_backup_config(self, config: BackupConfig):
        """백업 설정 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO backup_configs
                    (name, source_paths, backup_dir, backup_type, schedule_enabled,
                     schedule_time, schedule_days, retention_days, max_backups,
                     compression_enabled, compression_level, verify_backup,
                     checksum_enabled, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    config.name, json.dumps(config.source_paths), config.backup_dir,
                    config.backup_type.value, 1 if config.schedule_enabled else 0,
                    config.schedule_time, json.dumps(config.schedule_days),
                    config.retention_days, config.max_backups,
                    1 if config.compression_enabled else 0, config.compression_level,
                    1 if config.verify_backup else 0, 1 if config.checksum_enabled else 0
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"백업 설정 저장 중 오류: {e}")
    
    def create_backup(self, config_name: str) -> Optional[BackupRecord]:
        """백업 생성
        
        Args:
            config_name: 백업 설정명
            
        Returns:
            백업 기록
        """
        if config_name not in self._backup_configs:
            self._logger.error(f"백업 설정을 찾을 수 없음: {config_name}")
            return None
        
        config = self._backup_configs[config_name]
        record = self._backup_engine.create_backup(config)
        
        # 데이터베이스 저장
        self._save_backup_record(record)
        
        # 보존 정책 적용
        self._apply_retention_policy(config)
        
        return record
    
    def _save_backup_record(self, record: BackupRecord):
        """백업 기록 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO backup_records
                    (backup_id, config_name, backup_type, start_time, end_time,
                     status, backup_path, file_count, backup_size, compressed_size,
                     checksum, verified, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.backup_id, record.config_name, record.backup_type.value,
                    record.start_time.isoformat(),
                    record.end_time.isoformat() if record.end_time else None,
                    record.status.value, record.backup_path, record.file_count,
                    record.backup_size, record.compressed_size, record.checksum,
                    1 if record.verified else 0, record.error_message
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"백업 기록 저장 중 오류: {e}")
    
    def _apply_retention_policy(self, config: BackupConfig):
        """보존 정책 적용"""
        try:
            cutoff_date = datetime.now() - timedelta(days=config.retention_days)
            
            with sqlite3.connect(self._db_path) as conn:
                # 오래된 백업 조회
                cursor = conn.execute('''
                    SELECT backup_id, backup_path FROM backup_records
                    WHERE config_name = ? AND start_time < ? AND status = 'completed'
                    ORDER BY start_time ASC
                ''', (config.name, cutoff_date.isoformat()))
                
                old_backups = cursor.fetchall()
                
                # 최대 개수 초과 백업 조회
                cursor = conn.execute('''
                    SELECT backup_id, backup_path FROM backup_records
                    WHERE config_name = ? AND status = 'completed'
                    ORDER BY start_time DESC
                    LIMIT -1 OFFSET ?
                ''', (config.name, config.max_backups))
                
                excess_backups = cursor.fetchall()
                
                # 삭제할 백업 목록
                backups_to_delete = old_backups + excess_backups
                
                for backup_id, backup_path in backups_to_delete:
                    # 파일 삭제
                    try:
                        if os.path.exists(backup_path):
                            if os.path.isfile(backup_path):
                                os.remove(backup_path)
                            else:
                                shutil.rmtree(backup_path)
                    except Exception as e:
                        self._logger.warning(f"백업 파일 삭제 실패: {backup_path} - {e}")
                    
                    # 데이터베이스에서 삭제
                    conn.execute('DELETE FROM backup_records WHERE backup_id = ?', (backup_id,))
                
                conn.commit()
                
                if backups_to_delete:
                    self._logger.info(f"보존 정책 적용: {len(backups_to_delete)}개 백업 삭제")
                
        except Exception as e:
            self._logger.error(f"보존 정책 적용 중 오류: {e}")
    
    def restore_backup(self, backup_id: str, restore_path: str) -> Optional[RestoreRecord]:
        """백업 복구
        
        Args:
            backup_id: 백업 ID
            restore_path: 복구 경로
            
        Returns:
            복구 기록
        """
        try:
            # 백업 정보 조회
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.execute(
                    'SELECT backup_path FROM backup_records WHERE backup_id = ?',
                    (backup_id,)
                )
                result = cursor.fetchone()
                
                if not result:
                    self._logger.error(f"백업을 찾을 수 없음: {backup_id}")
                    return None
                
                backup_path = result[0]
            
            # 복구 실행
            record = self._restore_engine.restore_backup(backup_path, restore_path, backup_id)
            
            # 복구 기록 저장
            self._save_restore_record(record)
            
            return record
            
        except Exception as e:
            self._logger.error(f"백업 복구 중 오류: {e}")
            return None
    
    def _save_restore_record(self, record: RestoreRecord):
        """복구 기록 저장"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO restore_records
                    (restore_id, backup_id, restore_path, start_time, end_time,
                     status, restored_files, total_size, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.restore_id, record.backup_id, record.restore_path,
                    record.start_time.isoformat(),
                    record.end_time.isoformat() if record.end_time else None,
                    record.status.value, record.restored_files, record.total_size,
                    record.error_message
                ))
                conn.commit()
                
        except Exception as e:
            self._logger.error(f"복구 기록 저장 중 오류: {e}")
    
    def start_scheduler(self):
        """스케줄러 시작"""
        if self._scheduler_running:
            self._logger.warning("스케줄러가 이미 실행 중입니다.")
            return
        
        # 스케줄 설정
        for config in self._backup_configs.values():
            if config.schedule_enabled:
                if 'daily' in config.schedule_days:
                    schedule.every().day.at(config.schedule_time).do(
                        self.create_backup, config.name
                    )
                else:
                    for day in config.schedule_days:
                        getattr(schedule.every(), day).at(config.schedule_time).do(
                            self.create_backup, config.name
                        )
        
        self._scheduler_running = True
        
        def scheduler_loop():
            while self._scheduler_running:
                schedule.run_pending()
                time.sleep(60)
        
        self._scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        
        self._logger.info("백업 스케줄러 시작")
    
    def stop_scheduler(self):
        """스케줄러 중지"""
        if not self._scheduler_running:
            return
        
        self._scheduler_running = False
        schedule.clear()
        
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)
        
        self._logger.info("백업 스케줄러 중지")
    
    def get_backup_statistics(self, days: int = 30) -> Dict[str, Any]:
        """백업 통계 조회"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            with sqlite3.connect(self._db_path) as conn:
                # 전체 통계
                cursor = conn.execute('''
                    SELECT 
                        COUNT(*) as total_backups,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_backups,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_backups,
                        SUM(backup_size) as total_size,
                        SUM(compressed_size) as total_compressed_size
                    FROM backup_records
                    WHERE start_time >= ?
                ''', (cutoff_date,))
                
                stats = cursor.fetchone()
                
                # 설정별 통계
                cursor = conn.execute('''
                    SELECT config_name, COUNT(*), AVG(backup_size)
                    FROM backup_records
                    WHERE start_time >= ? AND status = 'completed'
                    GROUP BY config_name
                ''', (cutoff_date,))
                
                config_stats = dict(cursor.fetchall())
                
                return {
                    'period_days': days,
                    'total_backups': stats[0] or 0,
                    'successful_backups': stats[1] or 0,
                    'failed_backups': stats[2] or 0,
                    'success_rate': (stats[1] / stats[0] * 100) if stats[0] > 0 else 0,
                    'total_size_mb': (stats[3] or 0) / 1024 / 1024,
                    'total_compressed_size_mb': (stats[4] or 0) / 1024 / 1024,
                    'compression_ratio': (stats[4] / stats[3] * 100) if stats[3] > 0 else 0,
                    'config_statistics': config_stats
                }
                
        except Exception as e:
            self._logger.error(f"백업 통계 조회 중 오류: {e}")
            return {}

# 글로벌 인스턴스
_backup_manager: Optional[BackupManager] = None

def get_backup_manager() -> BackupManager:
    """백업 관리자 인스턴스 반환 (싱글톤)"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = BackupManager()
    return _backup_manager 