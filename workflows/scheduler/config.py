"""
스케줄러 설정 모듈

통합 스케줄러의 모든 설정과 상수를 중앙 집중식으로 관리합니다.
"""

import os
from typing import Dict, Any
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SchedulerConfig:
    """스케줄러 설정 클래스

    모든 하드코딩된 상수와 설정값을 여기서 관리합니다.
    """

    # === Phase 2 배치 설정 ===
    batch_count: int = 18
    batch_interval_minutes: int = 5
    batch_start_hour: int = 7
    batch_start_minute: int = 0

    # === Phase 1 스케줄 ===
    phase1_schedule_time: str = "06:00"

    # === 캐시 초기화 ===
    cache_init_time: str = "00:00"

    # === AI 학습 데이터 연동 ===
    ai_data_schedule_time: str = "17:00"

    # === 병렬 처리 설정 ===
    parallel_workers: int = 4

    # === 데이터 디렉토리 ===
    data_root: Path = field(default_factory=lambda: Path("data"))
    watchlist_dir: Path = field(default_factory=lambda: Path("data/watchlist"))
    daily_selection_dir: Path = field(default_factory=lambda: Path("data/daily_selection"))
    learning_dir: Path = field(default_factory=lambda: Path("data/learning"))

    # === 파일 경로 ===
    watchlist_file: str = "data/watchlist/watchlist.json"
    latest_selection_file: str = "data/daily_selection/latest_selection.json"

    # === AI 학습 데이터 ===
    ai_raw_data_dir: Path = field(default_factory=lambda: Path("data/learning/raw_data"))
    ai_feedback_dir: Path = field(default_factory=lambda: Path("data/learning/feedback"))

    # === 로그 설정 ===
    log_dir: Path = field(default_factory=lambda: Path("logs"))

    # === 파일 크기 제한 ===
    max_file_size_mb: float = 1.0  # AI 데이터 수집 시 파일 크기 제한

    # === Phase 2 배치 시간 계산 ===
    def get_batch_schedule_times(self) -> list[str]:
        """배치별 실행 시간 계산

        Returns:
            배치 실행 시간 리스트 (예: ["07:00", "07:05", "07:10", ...])
        """
        times = []
        hour = self.batch_start_hour
        minute = self.batch_start_minute

        for i in range(self.batch_count):
            times.append(f"{hour:02d}:{minute:02d}")
            minute += self.batch_interval_minutes
            if minute >= 60:
                hour += 1
                minute -= 60

        return times

    def get_batch_end_time(self) -> str:
        """배치 종료 시간 계산

        Returns:
            마지막 배치 실행 시간 (예: "08:25")
        """
        times = self.get_batch_schedule_times()
        return times[-1] if times else "08:25"

    # === 디렉토리 초기화 ===
    def ensure_directories(self) -> None:
        """필요한 모든 디렉토리를 생성합니다."""
        directories = [
            self.data_root,
            self.watchlist_dir,
            self.daily_selection_dir,
            self.learning_dir,
            self.ai_raw_data_dir,
            self.ai_feedback_dir,
            self.log_dir,
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    # === 설정 검증 ===
    def validate(self) -> bool:
        """설정 값의 유효성을 검증합니다.

        Returns:
            유효하면 True, 아니면 False
        """
        if self.batch_count <= 0:
            return False
        if self.batch_interval_minutes <= 0:
            return False
        if not (0 <= self.batch_start_hour < 24):
            return False
        if not (0 <= self.batch_start_minute < 60):
            return False
        if self.parallel_workers <= 0:
            return False

        return True

    # === 설정 정보 출력 ===
    def to_dict(self) -> Dict[str, Any]:
        """설정을 딕셔너리로 변환합니다."""
        return {
            "batch_count": self.batch_count,
            "batch_interval_minutes": self.batch_interval_minutes,
            "batch_start_time": f"{self.batch_start_hour:02d}:{self.batch_start_minute:02d}",
            "batch_end_time": self.get_batch_end_time(),
            "phase1_schedule_time": self.phase1_schedule_time,
            "cache_init_time": self.cache_init_time,
            "ai_data_schedule_time": self.ai_data_schedule_time,
            "parallel_workers": self.parallel_workers,
            "watchlist_file": self.watchlist_file,
            "max_file_size_mb": self.max_file_size_mb,
        }


# === 기본 설정 인스턴스 ===
default_config = SchedulerConfig()
