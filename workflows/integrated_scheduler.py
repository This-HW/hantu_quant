#!/usr/bin/env python3
"""
통합 스케줄러: Phase 1 + Phase 2 자동화 시스템
- 주기적 스크리닝 실행 (Phase 1)
- 일일 매매 리스트 업데이트 (Phase 2)
- 통합 모니터링 및 알림
"""

import sys
import os
import argparse

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# 환경 체크 (import 전 실행하여 불필요한 DB 연결 방지)
# ============================================================================
def check_environment_early():
    """
    스크립트 실행 환경을 조기에 체크합니다.
    start 명령 시 로컬 환경에서는 차단됩니다.
    """
    # argparse로 명령 확인
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('command', nargs='?', default=None)
    parser.add_argument('--force-local', action='store_true')
    args, _ = parser.parse_known_args()

    # start 명령이 아니면 환경 체크 생략
    if args.command != 'start':
        return

    # 환경 체크 (최소한의 import만 사용)
    from core.utils.env_utils import can_run_scheduler, get_environment

    force_local = args.force_local
    can_run, message = can_run_scheduler(force_local=force_local)

    if not can_run:
        print(message)
        sys.exit(1)

    # 경고 메시지 출력 (로컬 강제 실행 시)
    env = get_environment()
    if env == "local" and force_local:
        print(message, flush=True)
        print(flush=True)


# 환경 체크 실행
check_environment_early()


# ============================================================================
# 이제 안전하게 모든 모듈 import 가능
# ============================================================================
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any
import traceback

from workflows.phase1_watchlist import Phase1Workflow
from workflows.phase2_daily_selection import Phase2CLI
from core.watchlist.watchlist_manager import WatchlistManager
from core.utils.log_utils import get_logger, setup_logging

# 텔레그램 알람 추가
import json
import requests
from pathlib import Path
from core.utils.telegram_notifier import get_telegram_notifier

# Redis 캐시 및 DailyUpdater 추가
from core.api.redis_client import cache
from core.daily_selection.daily_updater import DailyUpdater

# === 새 모듈화된 스케줄러 컴포넌트 ===
# 향후 IntegratedScheduler는 이 모듈들로 점진적으로 마이그레이션될 예정입니다.
# 현재는 하위 호환성을 위해 기존 코드를 유지하면서 새 모듈도 함께 사용합니다.
from workflows.scheduler import (
    SchedulerConfig,
    NotificationService,
    DataCollectionService,
    RecoveryManager,
    MaintenanceService,
    MonitoringService,
    SchedulerCore,
    get_scheduler_core,
    get_notification_service,
)

# 자동 매매 엔진 추가

# 강화된 로깅 설정
log_filename = f"logs/{datetime.now().strftime('%Y%m%d')}.log"
setup_logging(log_filename, add_sensitive_filter=True)
logger = get_logger(__name__)

# DB 에러 로깅 설정 (PostgreSQL에 에러 저장)
try:
    from core.utils.db_error_handler import setup_db_error_logging

    db_error_handler = setup_db_error_logging(service_name="scheduler")
    if db_error_handler:
        logger.info("DB 에러 로깅 활성화됨 (PostgreSQL)")
except Exception as e:
    logger.warning(f"DB 에러 로깅 설정 실패: {e}")

# 자동 에러 복구 시스템 설정
try:
    from core.resilience.error_recovery import get_error_recovery_system

    error_recovery_system = get_error_recovery_system()
    # 자동 모니터링 시작 (30분 간격)
    error_recovery_system.start_monitoring(interval_seconds=1800)
    logger.info("자동 에러 복구 시스템 활성화됨 (모니터링 간격: 30분)")
except Exception as e:
    logger.warning(f"자동 에러 복구 시스템 설정 실패: {e}")

# 스케줄러 시작 시 로그 기록
logger.info("=" * 50)
logger.info("통합 스케줄러 모듈 로딩 시작")
logger.info(f"[로그] 로그 파일: {log_filename}")
logger.info(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info("=" * 50)


class IntegratedScheduler:
    """통합 스케줄러 클래스"""

    def __init__(self, p_parallel_workers: int = 4):
        """초기화

        Args:
            p_parallel_workers: 병렬 처리 워커 수 (기본값: 4)
        """
        try:
            logger.info(f"[초기화] 스케줄러 초기화 시작 (워커: {p_parallel_workers}개)")

            # 텔레그램 notifier 캐시 (싱글톤 패턴 활용)
            self._v_telegram_notifier = None

            self._v_phase1_workflow = Phase1Workflow(
                p_parallel_workers=p_parallel_workers
            )
            logger.info("Phase1 워크플로우 초기화 완료")

            self._v_phase2_cli = Phase2CLI(p_parallel_workers=p_parallel_workers)
            logger.info("Phase2 CLI 초기화 완료")

            # DailyUpdater 초기화 (분산 모드 지원)
            self._v_daily_updater = DailyUpdater(
                p_watchlist_file="data/watchlist/watchlist.json",
                p_output_dir="data/daily_selection"
            )
            logger.info("DailyUpdater 초기화 완료")

            self._v_parallel_workers = p_parallel_workers

            # 스케줄러 상태
            self._v_scheduler_running = False
            self._v_scheduler_thread = None
            self._v_start_time = None

            # 실행 기록
            self._v_last_screening = None
            self._v_last_daily_update = None

            # Phase 1 완료 후 Phase 2 자동 실행을 위한 플래그
            self._v_phase1_completed = False

            logger.info(
                f"통합 스케줄러 초기화 완료 (병렬 워커: {p_parallel_workers}개)"
            )

        except Exception as e:
            logger.error(f"스케줄러 초기화 실패: {e}", exc_info=True)
            logger.error(f"[상세] 상세 오류:\n{traceback.format_exc()}", exc_info=True)
            raise

    def _get_notifier(self):
        """텔레그램 notifier 반환 (지연 초기화, 캐시)

        Returns:
            TelegramNotifier 인스턴스 또는 None (비활성화/오류 시)
        """
        if self._v_telegram_notifier is None:
            try:
                self._v_telegram_notifier = get_telegram_notifier()
            except Exception as e:
                logger.warning(f"텔레그램 notifier 초기화 실패: {e}")
                return None
        return self._v_telegram_notifier

    def _safe_send_telegram(self, message: str, priority: str = "normal") -> bool:
        """텔레그램 알림을 안전하게 전송 (예외 처리 포함)

        Args:
            message: 전송할 메시지
            priority: 우선순위 (normal, high, emergency 등)

        Returns:
            전송 성공 여부
        """
        try:
            notifier = self._get_notifier()
            if notifier and notifier.is_enabled():
                return notifier.send_message(message, priority)
            return False
        except Exception as e:
            logger.warning(f"텔레그램 알림 전송 실패: {e}")
            return False

    def _run_cache_initialization(self):
        """자정 캐시 초기화 (00:00 실행)

        목적:
        - 전날 캐시 데이터 삭제
        - Redis 연결 상태 확인
        - 당일 시작 준비

        처리:
        1. Redis 연결 확인
        2. hantu:* 패턴 키 삭제
        3. 텔레그램 알림 (삭제된 키 개수)
        4. 에러 시 경고 로그 (서비스 지속)
        """
        try:
            logger.info("=" * 50)
            logger.info("[캐시] 캐시 초기화 시작")

            # Redis 클라이언트 확인
            if not hasattr(cache, 'client') or cache.client is None:
                logger.warning("Redis 클라이언트가 초기화되지 않음 - 캐시 초기화 스킵")
                return False

            # Redis SCAN으로 hantu:* 패턴 키 찾기 (KEYS * 대신 SCAN 사용)
            deleted_count = 0
            cursor = 0
            pattern = "hantu:*"

            while True:
                cursor, keys = cache.client.scan(cursor=cursor, match=pattern, count=100)
                if keys:
                    # 키 삭제
                    cache.client.delete(*keys)
                    deleted_count += len(keys)
                    logger.info(f"캐시 삭제 중: {len(keys)}개 키 삭제 (총 {deleted_count}개)")

                if cursor == 0:
                    break

            logger.info(f"캐시 초기화 완료: {deleted_count}개 키 삭제")

            # 텔레그램 알림
            self._safe_send_telegram(
                f"[캐시] *캐시 초기화 완료*\n\n"
                f"• 삭제된 키: {deleted_count}개\n"
                f"• 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
                "normal"
            )

            return True

        except Exception as e:
            logger.warning(f"캐시 초기화 실패: {e} - 서비스 계속", exc_info=True)
            return False

    def _run_distributed_batch(self, batch_index: int):
        """Phase 2 분산 배치 실행 (07:00-08:30, 5분 간격)

        Args:
            batch_index: 배치 번호 (0-17)

        처리 흐름:
        1. 배치 시작 로깅
        2. DailyUpdater.run_daily_update(distributed_mode=True, batch_index=batch_index)
        3. 성공/실패 로깅
        4. 에러 시 텔레그램 알림 (부분 실패는 다음 배치 진행)

        특수 처리:
        - batch_index == 0: "Phase 2 시작" 텔레그램 알림
        - batch_index == 17: "Phase 2 완료" 텔레그램 알림 (총 선정 종목 수 포함)
        """
        try:
            logger.info(f"[배치] 배치 {batch_index}/17 시작")

            # 첫 번째 배치: Phase 2 시작 알림
            if batch_index == 0:
                logger.info("=" * 50)
                logger.info("[배치] Phase 2 분산 배치 실행 시작")
                self._safe_send_telegram(
                    f"[배치] *Phase 2 시작*\n\n"
                    f"• 총 배치: 18개\n"
                    f"• 예상 완료: 08:30",
                    "normal"
                )

            # 배치 실행
            success = self._v_daily_updater.run_daily_update(
                distributed_mode=True,
                batch_index=batch_index
            )

            if success:
                logger.info(f"배치 {batch_index}/17 완료")

                # 마지막 배치: Phase 2 완료 알림
                if batch_index == 17:
                    logger.info("=" * 50)
                    logger.info("Phase 2 분산 배치 실행 완료")

                    # 선정 결과 파일 확인
                    today_str = datetime.now().strftime("%Y%m%d")
                    selection_file = Path(f"data/daily_selection/daily_selection_{today_str}.json")

                    total_selected = 0
                    if selection_file.exists():
                        try:
                            with open(selection_file, "r", encoding="utf-8") as f:
                                selection_data = json.load(f)
                                total_selected = len(selection_data.get("selected_stocks", []))
                        except Exception as e:
                            logger.warning(f"선정 결과 파일 읽기 실패: {e}")

                    self._safe_send_telegram(
                        f"*Phase 2 완료*\n\n"
                        f"• 총 선정 종목: {total_selected}개\n"
                        f"• 소요 시간: 90분\n"
                        f"• 저장: DB (`selection_results` 테이블)",
                        "normal"
                    )
            else:
                logger.error(f"배치 {batch_index}/17 실패")

                # 배치 실패 알림
                self._safe_send_telegram(
                    f"*배치 {batch_index} 실패*\n\n"
                    f"• 에러: 배치 실행 실패\n"
                    f"• 다음 배치 진행 중...",
                    "high"
                )

        except Exception as e:
            logger.error(f"배치 {batch_index}/17 실행 오류: {e}", exc_info=True)

            # 에러 알림
            self._safe_send_telegram(
                f"*배치 {batch_index} 실패*\n\n"
                f"• 에러: {str(e)[:50]}...\n"
                f"• 다음 배치 진행 중...",
                "high"
            )

    def start_scheduler(self):
        """통합 스케줄러 시작"""
        if self._v_scheduler_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return

        # 스케줄 설정
        schedule.clear()

        # ========================================
        # 캐시 초기화 (자정)
        # ========================================
        schedule.every().day.at("00:00").do(self._run_cache_initialization)

        # ========================================
        # Phase 1: 일간 스크리닝 (매일 06:00, 주말 제외)
        # ========================================
        schedule.every().monday.at("06:00").do(self._run_daily_screening)
        schedule.every().tuesday.at("06:00").do(self._run_daily_screening)
        schedule.every().wednesday.at("06:00").do(self._run_daily_screening)
        schedule.every().thursday.at("06:00").do(self._run_daily_screening)
        schedule.every().friday.at("06:00").do(self._run_daily_screening)

        # ========================================
        # Phase 2: 분산 배치 실행 (07:00-08:30, 5분 간격, 평일만)
        # ========================================
        # 18개 배치를 5분 간격으로 스케줄링
        batch_times = [
            "07:00", "07:05", "07:10", "07:15", "07:20", "07:25", "07:30", "07:35", "07:40",
            "07:45", "07:50", "07:55", "08:00", "08:05", "08:10", "08:15", "08:20", "08:25"
        ]

        for batch_index, time_str in enumerate(batch_times):
            # 평일에만 실행
            schedule.every().monday.at(time_str).do(self._run_distributed_batch, batch_index)
            schedule.every().tuesday.at(time_str).do(self._run_distributed_batch, batch_index)
            schedule.every().wednesday.at(time_str).do(self._run_distributed_batch, batch_index)
            schedule.every().thursday.at(time_str).do(self._run_distributed_batch, batch_index)
            schedule.every().friday.at(time_str).do(self._run_distributed_batch, batch_index)

        # Phase 3: 자동 매매 시작 (장 시작 시간, 주말 제외)
        schedule.every().monday.at("09:00").do(self._start_auto_trading)
        schedule.every().tuesday.at("09:00").do(self._start_auto_trading)
        schedule.every().wednesday.at("09:00").do(self._start_auto_trading)
        schedule.every().thursday.at("09:00").do(self._start_auto_trading)
        schedule.every().friday.at("09:00").do(self._start_auto_trading)

        # Phase 3: 자동 매매 중지 (장 마감 시간, 주말 제외)
        schedule.every().monday.at("15:30").do(self._stop_auto_trading)
        schedule.every().tuesday.at("15:30").do(self._stop_auto_trading)
        schedule.every().wednesday.at("15:30").do(self._stop_auto_trading)
        schedule.every().thursday.at("15:30").do(self._stop_auto_trading)
        schedule.every().friday.at("15:30").do(self._stop_auto_trading)

        # 시장 마감 후 정리 작업 (매일 16:00, 주말 제외)
        schedule.every().monday.at("16:00").do(self._run_market_close_tasks)
        schedule.every().tuesday.at("16:00").do(self._run_market_close_tasks)
        schedule.every().wednesday.at("16:00").do(self._run_market_close_tasks)
        schedule.every().thursday.at("16:00").do(self._run_market_close_tasks)
        schedule.every().friday.at("16:00").do(self._run_market_close_tasks)

        # 장 마감 후 자동 유지보수 (매일 16:30, 평일만)
        schedule.every().monday.at("16:30").do(self._run_auto_maintenance)
        schedule.every().tuesday.at("16:30").do(self._run_auto_maintenance)
        schedule.every().wednesday.at("16:30").do(self._run_auto_maintenance)
        schedule.every().thursday.at("16:30").do(self._run_auto_maintenance)
        schedule.every().friday.at("16:30").do(self._run_auto_maintenance)

        # Phase 4: AI 학습 시스템 (일일 성과 분석: 매일 17:00)
        schedule.every().day.at("17:00").do(self._run_daily_performance_analysis)

        # 재무 데이터 수집 배치 (주말 1회, 토요일 10:00)
        # 재무 데이터는 분기/연간 단위로 변경되므로 주 1회 수집으로 충분
        # 평일에는 DB에 저장된 최신 데이터를 재사용
        schedule.every().saturday.at("10:00").do(self._run_fundamental_data_collection)

        # 재무 데이터 수집 후 자동 유지보수 (토요일 11:00)
        schedule.every().saturday.at("11:00").do(self._run_auto_maintenance)

        # Phase 4: 강화된 적응형 학습 (주말 - 대량 데이터 분석)
        # 토요일 20:00에 실행하여 주간 데이터 기반 포괄적 분석
        schedule.every().saturday.at("20:00").do(self._run_enhanced_adaptive_learning)

        # 강화된 적응형 학습 후 자동 유지보수 (토요일 21:00)
        schedule.every().saturday.at("21:00").do(self._run_auto_maintenance)

        # Phase 4: 주간 깊이 학습 (매주 토요일 22:00)
        schedule.every().saturday.at("22:00").do(self._run_weekly_adaptive_learning)

        # 주간 깊이 학습 후 자동 유지보수 (토요일 23:30)
        schedule.every().saturday.at("23:30").do(self._run_auto_maintenance)

        # Phase 5: 시스템 모니터링 시작 (스케줄러 시작 시)
        schedule.every().day.at("00:01").do(self._start_system_monitoring)

        # Phase 5: 자동 유지보수 (매주 일요일 새벽 3시)
        schedule.every().sunday.at("03:00").do(self._run_auto_maintenance)

        # ML 학습 조건 체크: 주말에만 실행 (B단계 자동 트리거용)
        # 일요일 10:00에 실행하여 주간 데이터 축적 후 ML 학습 조건 체크
        schedule.every().sunday.at("10:00").do(self._check_ml_trigger)

        # ML 학습 조건 체크 후 자동 유지보수 (일요일 11:00)
        schedule.every().sunday.at("11:00").do(self._run_auto_maintenance)

        # [방안 B] 주간 백테스트: 매주 금요일 16:00
        # Note: 백테스트 결과는 17:00 가중치 조정(scheduler.py)에 반영됨
        schedule.every().friday.at("16:00").do(self._run_weekly_backtest)

        # 헬스체크: 장 시간 중 30분마다 실행 (평일만)
        # 09:10, 09:40, 10:10, 10:40, 11:10, 11:40, 13:10, 13:40, 14:10, 14:40, 15:10
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        health_check_times = [
            "09:10", "09:40", "10:10", "10:40", "11:10", "11:40",
            "13:10", "13:40", "14:10", "14:40", "15:10"
        ]
        for day in weekdays:
            day_scheduler = getattr(schedule.every(), day)
            for time in health_check_times:
                day_scheduler.at(time).do(self._run_health_check)

        # 개발/테스트용 스케줄 (옵션)
        # schedule.every(10).minutes.do(self._run_daily_update)  # 10분마다 테스트

        self._v_scheduler_running = True
        self._v_start_time = datetime.now()  # 시작 시간 기록
        self._v_scheduler_thread = threading.Thread(
            target=self._run_scheduler_loop, daemon=True
        )
        self._v_scheduler_thread.start()

        logger.info("통합 스케줄러 시작됨")
        print("통합 스케줄러 시작!")
        print("├─ 캐시 초기화: 매일 00:00")
        print("├─ 일간 스크리닝: 매일 06:00")
        print("├─ 일일 업데이트: 07:00-08:30 (18개 배치, 5분 간격)")
        print("├─ 자동 매매 시작: 매일 09:00 (평일)")
        print("├─ 자동 매매 중지: 매일 15:30 (평일)")
        print("├─ 매매 헬스체크: 장 시간 중 30분마다 (평일)")
        print("│  └─ 문제 발견 시: 텔레그램 알람 + 자동 유지보수 트리거")
        print("├─ 마감 후 정리: 매일 16:00")
        print("├─ 자동 유지보수: 매일 16:30 (평일, 장 마감 후)")
        print("├─ AI 성과 분석: 매일 17:00")
        print("├─ 재무 데이터 수집: 매주 토요일 10:00")
        print("│  └─ 자동 유지보수: 토요일 11:00 (데이터 수집 후)")
        print("├─ 강화된 적응형 학습: 매주 토요일 20:00 (대량 데이터 분석)")
        print("│  └─ 자동 유지보수: 토요일 21:00 (학습 후)")
        print("├─ 주간 깊이 학습: 매주 토요일 22:00")
        print("│  └─ 자동 유지보수: 토요일 23:30 (학습 후)")
        print("├─ 자동 유지보수: 매주 일요일 03:00 (정기)")
        print("├─ ML 학습 조건 체크: 매주 일요일 10:00 (B단계 자동 트리거)")
        print("│  └─ 자동 유지보수: 일요일 11:00 (체크 후)")
        print("└─ 시스템 모니터링: 24시간 실시간")

        # 텔레그램 스케줄러 시작 알림 전송
        try:
            from core.utils.telegram_notifier import get_telegram_notifier

            notifier = get_telegram_notifier()
            if notifier.is_enabled():
                success = notifier.send_scheduler_started()
                if success:
                    logger.info("스케줄러 시작 알림 전송 완료")
                    print("[알림] 텔레그램 시작 알림 전송됨")
                else:
                    logger.warning("스케줄러 시작 알림 전송 실패")
            else:
                logger.debug("텔레그램 알림이 비활성화됨")
        except Exception as e:
            logger.error(f"스케줄러 시작 알림 전송 오류: {e}", exc_info=True)

        # 장 시간 중 재시작 시 누락된 작업 자동 실행
        self._check_and_recover_missed_tasks()

    def _check_and_recover_missed_tasks(self):
        """스케줄러 재시작 시 누락된 작업 자동 실행

        복구 시나리오 (평일만):
        - 06:00~07:00: Phase 1 실행
        - 07:00~09:00: Phase 2 미완료 배치 실행
        - 09:00~15:30: 매매 실행
        - 15:30~16:00: 시장 마감 정리 실행
        - 16:00~17:00: 시장 마감 정리 + 일일 성과 분석 실행
        - 17:00 이후: 모든 정리 작업 실행

        Note: 재무 데이터는 주말(토요일 10:00)에 수집하며, 평일에는 DB 데이터 재사용
        """
        try:
            now = datetime.now()

            # 주말 제외
            if now.weekday() >= 5:
                logger.info("주말 - 복구 작업 스킵")
                return

            # 시간대 정의
            screening_time = now.replace(hour=6, minute=0, second=0, microsecond=0)
            phase2_start = now.replace(hour=7, minute=0, second=0, microsecond=0)
            phase2_end = now.replace(hour=8, minute=30, second=0, microsecond=0)
            market_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            cleanup_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
            performance_time = now.replace(hour=17, minute=0, second=0, microsecond=0)

            # 오늘 날짜 파일 확인
            today_str = now.strftime("%Y%m%d")
            selection_file = Path(
                f"data/daily_selection/daily_selection_{today_str}.json"
            )

            recovered_tasks = []

            # === 06:00 이전: 복구 불필요 ===
            if now < screening_time:
                logger.info("스크리닝 시간(06:00) 전 - 복구 작업 스킵")
                return

            # === 06:00~17:00+: 시간대별 복구 로직 ===
            logger.info(f"재시작 감지 - 복구 작업 시작 ({now.strftime('%H:%M')})")
            print(
                f"\n[갱신] 스케줄러 재시작 감지 ({now.strftime('%H:%M')}) - 복구 작업 시작..."
            )

            notifier = get_telegram_notifier()

            # 재무 데이터는 주말(토요일)에 수집하므로, 평일에는 DB 데이터 확인만 수행
            try:
                from core.api.krx_client import KRXClient

                krx_client = KRXClient()
                fundamentals_df = krx_client.load_market_fundamentals()
                if fundamentals_df.empty:
                    logger.warning("재무 데이터 없음 - 토요일 수집 후 사용 가능")
                    print("재무 데이터 없음 (토요일에 자동 수집됩니다)")
                else:
                    logger.info(f"재무 데이터 확인 완료: {len(fundamentals_df)}개 종목")
            except Exception as e:
                logger.warning(f"재무 데이터 확인 실패: {e}")

            # 1. Phase 1/2 스크리닝 (06:00 이후)
            # DB에서 오늘 선정 결과가 있는지 확인 (파일보다 DB 우선)
            screening_needed = False
            if now >= screening_time:
                db_has_selection = self._check_today_selection_in_db(now.date())
                if db_has_selection:
                    logger.info("DB에 오늘 선정 결과 있음 - 스크리닝 스킵")
                elif selection_file.exists():
                    # DB에 없지만 파일이 있으면 파일 시간 확인
                    file_mtime = datetime.fromtimestamp(selection_file.stat().st_mtime)
                    if file_mtime >= screening_time:
                        logger.info(
                            f"파일 정상 (생성: {file_mtime.strftime('%Y-%m-%d %H:%M')}) - 스크리닝 스킵"
                        )
                    else:
                        screening_needed = True
                        logger.info(
                            f"파일이 오래됨 (생성: {file_mtime.strftime('%Y-%m-%d %H:%M')}) - 스크리닝 필요"
                        )
                else:
                    screening_needed = True
                    logger.info("DB/파일 모두 없음 - 스크리닝 필요")

            if screening_needed:
                print("[상세] 일간 스크리닝 실행...")
                self._run_daily_screening()
                recovered_tasks.append("일간 스크리닝")

            # 2. Phase 2 미완료 배치 복구 (07:00~08:30 시간대 재시작)
            if phase2_start <= now < market_open:
                # 현재 시간 기준으로 미완료 배치 계산
                elapsed_minutes = (now.hour - 7) * 60 + now.minute
                completed_batches = elapsed_minutes // 5

                if completed_batches < 18:
                    logger.info(f"Phase 2 시간대 재시작 감지 - 배치 {completed_batches}-17 복구 실행 시작")
                    print(f"[배치] Phase 2 복구: 배치 {completed_batches}-17 실행...")

                    for i in range(completed_batches, 18):
                        self._run_distributed_batch(i)

                    recovered_tasks.append(f"Phase 2 배치 {completed_batches}-17")

            # 3. 자동 매매 (09:00~15:30 장중이면 시작)
            if now >= market_open and now < market_close:
                print("[자동] 자동 매매 시작...")
                trading_started = self._start_auto_trading(from_recovery=True)
                if trading_started:
                    recovered_tasks.append("자동 매매 시작")
                else:
                    logger.info("자동 매매 시작 스킵됨 (이미 실행 중이거나 실패)")
            elif now >= market_close and selection_file.exists():
                # 장 마감 후지만 선정 파일 있으면 정리 작업 가능
                pass

            # 4. 시장 마감 정리 (16:00 이후)
            if now >= cleanup_time:
                print("[종료] 시장 마감 정리 실행...")
                self._run_market_close_tasks()
                recovered_tasks.append("시장 마감 정리")

            # 5. 일일 성과 분석 (17:00 이후)
            if now >= performance_time:
                print("일일 성과 분석 실행...")
                self._run_daily_performance_analysis()
                recovered_tasks.append("일일 성과 분석")

            # 복구 결과 알림 (작업 유무와 관계없이 재시작 알림)
            try:
                if notifier.is_enabled():
                    if recovered_tasks:
                        task_list = "\n• ".join(recovered_tasks)
                        success = notifier.send_message(
                            f"[갱신] *스케줄러 재시작 복구*\n"
                            f"`{now.strftime('%H:%M')}` 재시작\n\n"
                            f"*복구된 작업:*\n• {task_list}",
                            "high",
                        )
                        if not success:
                            logger.warning("복구 알림 전송 실패")
                    else:
                        # 복구 작업이 없어도 재시작 알림 전송
                        success = notifier.send_message(
                            f"[갱신] *스케줄러 재시작*\n"
                            f"`{now.strftime('%H:%M')}` 재시작\n\n"
                            f"모든 작업이 이미 완료되어 추가 복구 불필요",
                            "normal",
                        )
                        if not success:
                            logger.warning("재시작 알림 전송 실패")
                else:
                    logger.warning("텔레그램 알림이 비활성화되어 있음")
            except Exception as notify_error:
                logger.error(f"복구 알림 전송 중 오류: {notify_error}", exc_info=True)

            if recovered_tasks:
                print(f"복구 작업 완료: {', '.join(recovered_tasks)}\n")
            else:
                print("복구 필요 없음 - 모든 작업 이미 완료됨\n")

            logger.info(
                f"복구 작업 완료: {recovered_tasks if recovered_tasks else '없음'}"
            )

        except Exception as e:
            logger.error(f"복구 작업 실패: {e}", exc_info=True)
            logger.error(traceback.format_exc())
            print(f"복구 작업 실패: {e}")

    def _check_today_selection_in_db(self, target_date) -> bool:
        """DB에서 오늘 선정 결과가 있는지 확인

        Args:
            target_date: 확인할 날짜

        Returns:
            선정 결과 존재 여부
        """
        try:
            from core.database.session import DatabaseSession
            from core.database.models import SelectionResult

            db = DatabaseSession()
            with db.get_session() as session:
                count = (
                    session.query(SelectionResult)
                    .filter(SelectionResult.selection_date == target_date)
                    .count()
                )
                return count > 0
        except Exception as e:
            logger.warning(f"DB 선정 결과 확인 실패: {e}")
            return False

    def stop_scheduler(self, reason: str = "사용자 요청"):
        """통합 스케줄러 중지"""
        if not self._v_scheduler_running:
            logger.warning("스케줄러가 이미 중지되어 있습니다")
            return

        # 텔레그램 스케줄러 종료 알림 전송 (중지 전에 전송)
        try:
            from core.utils.telegram_notifier import get_telegram_notifier

            notifier = get_telegram_notifier()
            if notifier.is_enabled():
                success = notifier.send_scheduler_stopped(reason)
                if success:
                    logger.info(f"스케줄러 종료 알림 전송 완료: {reason}")
                    print("[알림] 텔레그램 종료 알림 전송됨")
                else:
                    logger.warning("스케줄러 종료 알림 전송 실패")
            else:
                logger.debug("텔레그램 알림이 비활성화됨")
        except Exception as e:
            logger.error(f"스케줄러 종료 알림 전송 오류: {e}", exc_info=True)

        # 스케줄러 중지
        self._v_scheduler_running = False
        schedule.clear()

        if self._v_scheduler_thread and self._v_scheduler_thread.is_alive():
            self._v_scheduler_thread.join(timeout=5)

        logger.info(f"통합 스케줄러 중지됨: {reason}")
        print(f"[중지] 통합 스케줄러 중지됨: {reason}")

    def get_status(self) -> Dict:
        """스케줄러 상태 조회"""
        _v_next_jobs = []
        for job in schedule.jobs:
            try:
                job_name = getattr(job.job_func, "__name__", str(job.job_func))
            except Exception:
                job_name = "Unknown Job"

            _v_next_jobs.append(
                {
                    "job": job_name,
                    "next_run": (
                        job.next_run.strftime("%Y-%m-%d %H:%M:%S")
                        if job.next_run
                        else "미정"
                    ),
                    "interval": str(job.interval),
                    "unit": job.unit,
                }
            )

        # 실제 프로세스 상태 확인 (ServiceManager와 동일한 방식)
        import psutil

        actual_running = False
        current_pid = os.getpid()

        try:
            # 현재 프로세스가 스케줄러인지 확인
            current_proc = psutil.Process(current_pid)
            current_cmdline = current_proc.cmdline()

            # 현재 프로세스가 스케줄러 시작 명령인지 확인
            if (
                len(current_cmdline) >= 3
                and "python" in current_cmdline[0]
                and "integrated_scheduler.py" in current_cmdline[1]
                and current_cmdline[2] == "start"
            ):
                actual_running = True
                logger.debug(f"[실행중] 현재 프로세스가 스케줄러임: PID {current_pid}")
            else:
                # 다른 스케줄러 프로세스 검색
                for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                    try:
                        cmdline = proc.info.get("cmdline", [])
                        if (
                            cmdline
                            and len(cmdline) >= 3
                            and "python" in str(cmdline[0])
                            and "integrated_scheduler.py" in str(cmdline[1])
                            and cmdline[2] == "start"
                        ):
                            actual_running = True
                            logger.debug(
                                f"[실행중] 다른 스케줄러 프로세스 발견: PID {proc.info['pid']}"
                            )
                            break
                    except Exception:
                        continue

        except Exception as e:
            logger.warning(f"프로세스 상태 확인 실패: {e}, 내부 상태 사용")
            actual_running = self._v_scheduler_running

        # 내부 상태와 실제 프로세스 상태 비교 (스케줄러 스레드가 실행 중이면 내부 상태 우선)
        if actual_running != self._v_scheduler_running:
            # 스케줄러 스레드가 살아있으면 내부 상태를 신뢰
            if self._v_scheduler_thread and self._v_scheduler_thread.is_alive():
                logger.debug(
                    f"[갱신] 스케줄러 스레드 활성 상태 - 내부 상태 사용: {self._v_scheduler_running}"
                )
                actual_running = self._v_scheduler_running
            else:
                # 상태 불일치는 초기화 직후에 발생할 수 있음 (스레드 시작 전)
                # DEBUG 레벨로 낮춤
                logger.debug(
                    f"[갱신] 상태 동기화 중 - 내부: {self._v_scheduler_running}, 실제: {actual_running}"
                )

        return {
            "running": actual_running,  # 조정된 상태 사용
            "internal_running": self._v_scheduler_running,  # 내부 상태도 표시
            "last_screening": (
                self._v_last_screening.strftime("%Y-%m-%d %H:%M:%S")
                if self._v_last_screening
                else "없음"
            ),
            "last_daily_update": (
                self._v_last_daily_update.strftime("%Y-%m-%d %H:%M:%S")
                if self._v_last_daily_update
                else "없음"
            ),
            "scheduled_jobs": _v_next_jobs,
            "pid": current_pid,
            "start_time": (
                self._v_start_time.strftime("%Y-%m-%d %H:%M:%S")
                if self._v_start_time
                else "없음"
            ),
        }

    def _run_scheduler_loop(self):
        """스케줄러 루프 실행"""
        logger.info("[갱신] 스케줄러 루프 시작")
        loop_count = 0

        while self._v_scheduler_running:
            try:
                loop_count += 1

                # 주기적으로 생존 신호 로그 (매 10분마다)
                if loop_count % 10 == 0:
                    uptime = (
                        datetime.now() - self._v_start_time
                        if self._v_start_time
                        else timedelta(0)
                    )
                    logger.info(
                        f"[신호] 스케줄러 생존 신호 - 루프: {loop_count}, 가동시간: {uptime}"
                    )

                # 예정된 작업 실행
                pending_jobs = schedule.jobs
                if pending_jobs:
                    logger.debug(f"[상세] 확인 중인 예정 작업: {len(pending_jobs)}개")

                schedule.run_pending()
                time.sleep(60)  # 1분마다 체크

            except Exception as e:
                logger.error(f"스케줄러 루프 오류: {e}", exc_info=True)
                logger.error(f"[상세] 상세 오류:\n{traceback.format_exc()}", exc_info=True)
                time.sleep(60)

        logger.info("[중지] 스케줄러 루프 종료")

    def _run_daily_screening(self):
        """일간 스크리닝 실행 (Phase 1)"""
        try:
            logger.info("=== 일간 스크리닝 시작 ===")
            print(
                f"일간 스크리닝 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # 전체 시장 스크리닝 실행 (코스피 + 코스닥 전체 2875개 종목)
            # 알림은 Phase1에서만 발송하도록 통일하여 중복 방지
            _v_success = self._v_phase1_workflow.run_full_screening(
                p_send_notification=True
            )

            if _v_success:
                self._v_last_screening = datetime.now()
                logger.info("일간 스크리닝 완료")
                print("일간 스크리닝 완료!")

                # 알림은 Phase1이 이미 발송함. 스케줄러에서는 중복 전송하지 않음.
                # Phase 2는 분산 스케줄로 07:00-08:30에 자동 실행됨

            else:
                logger.error("일간 스크리닝 실패")
                print("일간 스크리닝 실패")

                # 실패 알람 전송
                try:
                    notifier = get_telegram_notifier()
                    _v_error_message = f"*한투 퀀트 스크리닝 실패*\n\n시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n상태: 일간 스크리닝 실패\n\n시스템 점검이 필요합니다."
                    notifier.send_message(_v_error_message, "emergency")
                except Exception as e:
                    logger.error(f"텔레그램 알림 전송 실패: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"일간 스크리닝 오류: {e}", exc_info=True)
            print(f"일간 스크리닝 오류: {e}")
            self._v_phase1_completed = False

    def _run_daily_update(self):
        """일일 업데이트 실행 (Phase 2)"""
        try:
            logger.info("=== 일일 업데이트 시작 ===")
            print(
                f"일일 업데이트 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Phase 2 DailyUpdater의 WatchlistManager를 새로 초기화하여 최신 데이터 로드
            try:
                # 새로운 WatchlistManager 인스턴스 생성하여 최신 데이터 반영
                fresh_watchlist_manager = WatchlistManager(
                    "data/watchlist/watchlist.json"
                )
                # DailyUpdater 재초기화로 최신 데이터 적용
                self._v_phase2_cli._v_daily_updater = type(
                    self._v_phase2_cli._v_daily_updater
                )(fresh_watchlist_manager)
            except Exception as e:
                logger.warning(
                    f"WatchlistManager 업데이트 실패, 기존 인스턴스 사용: {e}"
                )

            # Phase 2 일일 업데이트 실행
            _v_success = self._v_phase2_cli._v_daily_updater.run_daily_update(
                p_force_run=True
            )

            if _v_success:
                self._v_last_daily_update = datetime.now()
                logger.info("일일 업데이트 완료")
                print("일일 업데이트 완료!")

                # 선정 결과 요약 출력
                self._print_daily_summary()

            else:
                logger.error("일일 업데이트 실패")
                print("일일 업데이트 실패")

        except Exception as e:
            logger.error(f"일일 업데이트 오류: {e}", exc_info=True)
            print(f"일일 업데이트 오류: {e}")

    def _run_market_close_tasks(self):
        """시장 마감 후 정리 작업"""
        try:
            logger.info("=== 시장 마감 후 정리 작업 시작 ===")
            print(
                f"[종료] 시장 마감 후 정리 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # 일일 리포트 생성
            _v_report_success = self._v_phase1_workflow.generate_report()

            # 성과 분석 (Phase 2)
            _v_performance_data = self._v_phase2_cli._collect_performance_data(1)

            # 매매일지 요약 생성 및 저장
            try:
                from core.trading.trade_journal import TradeJournal
                from core.learning.analysis.daily_performance import (
                    DailyPerformanceAnalyzer,
                )

                journal = TradeJournal()
                summary = journal.compute_daily_summary()
                logger.info(
                    f"시장 마감 요약 - 손익: {summary['realized_pnl']:,.0f}, 거래: {summary['total_trades']}건, 승률: {summary['win_rate']*100:.1f}%"
                )

                # 요약 파일 경로 구성 후 성과 분석기에 반영
                summary_path = os.path.join(
                    journal._base_dir,
                    f"trade_summary_{datetime.now().strftime('%Y%m%d')}.json",
                )
                try:
                    analyzer = DailyPerformanceAnalyzer()
                    if analyzer.ingest_trade_summary(summary_path):
                        logger.info("매매일지 요약 성과 기록 반영 완료")
                    else:
                        logger.warning("매매일지 요약 성과 반영 실패")
                except Exception as e:
                    logger.warning(f"매매일지 요약 성과 반영 중 오류: {e}")
            except Exception as e:
                logger.warning(f"매매일지 요약 생성 실패: {e}")

            if _v_report_success:
                print("일일 리포트 생성 완료")

            # Batch 4-3: TradingEngine 일일 요약 생성 및 텔레그램 전송
            try:
                from core.trading.trading_engine import get_trading_engine

                engine = get_trading_engine()
                summary_message = engine.generate_daily_summary()

                if summary_message:
                    logger.info("TradingEngine 일일 요약 생성 완료")
                    self._safe_send_telegram(summary_message)
                    print("일일 거래 요약 텔레그램 전송 완료")
            except Exception as e:
                logger.warning(f"TradingEngine 일일 요약 생성 실패: {e}")

            print("시장 마감 후 정리 완료")

        except Exception as e:
            logger.error(f"시장 마감 후 정리 오류: {e}", exc_info=True)
            print(f"시장 마감 후 정리 오류: {e}")

    def _run_fundamental_data_collection(self):
        """재무 데이터 수집 배치 (KIS API 사용, Phase 1 스크리닝 전 실행)"""
        try:
            logger.info("=== 재무 데이터 수집 배치 시작 ===")
            print(
                f"재무 데이터 수집 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            from core.api.krx_client import KRXClient

            krx_client = KRXClient()

            # 전체 종목 재무 데이터 수집 및 저장
            saved_count = krx_client.save_market_fundamentals()

            if saved_count > 0:
                logger.info(f"재무 데이터 수집 완료: {saved_count}개 종목")
                print(f"재무 데이터 수집 완료: {saved_count}개 종목")

                # 텔레그램 알림 (선택)
                try:
                    notifier = get_telegram_notifier()
                    if notifier.is_enabled():
                        notifier.send_message(
                            f"재무 데이터 수집 완료\n"
                            f"- 종목 수: {saved_count}개\n"
                            f"- 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                except Exception as e:
                    logger.warning(f"텔레그램 알림 실패: {e}")
            else:
                logger.warning("재무 데이터 수집 실패: 저장된 종목 없음")
                print("재무 데이터 수집 실패")

        except Exception as e:
            logger.error(f"재무 데이터 수집 오류: {e}", exc_info=True)
            print(f"재무 데이터 수집 오류: {e}")

    def _run_daily_performance_analysis(self):
        """일일 성과 분석 실행 (Phase 4) - 실제 성과 데이터 사용"""
        try:
            logger.info("=== 일일 성과 분석 시작 ===")
            print(
                f"일일 성과 분석 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # 실제 성과 지표 계산 및 텔레그램 리포트 전송
            try:
                # 텔레그램 알림 시스템 가져오기
                notifier = get_telegram_notifier()

                # 일일 성과 리포트 전송 (실현/평가 손익 분리 표시)
                if notifier.is_enabled():
                    success = notifier.send_daily_performance_report()
                    if success:
                        logger.info("일일 성과 리포트 전송 완료")
                        print("일일 성과 리포트가 텔레그램으로 전송되었습니다!")
                    else:
                        logger.warning("일일 성과 리포트 전송 실패")
                        print("일일 성과 리포트 전송 실패")
                else:
                    logger.info("텔레그램 알림이 비활성화되어 있음")
                    print("[정보] 텔레그램 알림이 비활성화되어 있습니다.")

                # 추가 성과 분석 작업 (선택적)
                from core.performance.performance_metrics import get_performance_metrics

                metrics = get_performance_metrics()

                # 일일 성과 데이터 계산
                daily_perf = metrics.get_daily_performance()

                # 성과 데이터 저장
                os.makedirs("data/learning/performance", exist_ok=True)
                performance_file = f"data/learning/performance/daily_analysis_{datetime.now().strftime('%Y%m%d')}.json"

                with open(performance_file, "w") as f:
                    json.dump(daily_perf, f, indent=2, ensure_ascii=False)

                logger.info(
                    f"일일 성과 분석 완료: 실현손익 {daily_perf.get('realized_pnl', 0):,.0f}원, 평가손익 {daily_perf.get('unrealized_pnl', 0):,.0f}원"
                )
                print("일일 성과 분석 완료!")
                print(f"   - 실현 손익: {daily_perf.get('realized_pnl', 0):,.0f}원")
                print(f"   - 평가 손익: {daily_perf.get('unrealized_pnl', 0):,.0f}원")
                print(f"   - 총 손익: {daily_perf.get('total_pnl', 0):,.0f}원")

            except ImportError as ie:
                logger.warning(f"성과 분석 모듈 로드 실패, 기본 분석 사용: {ie}")
                print("성과 분석 모듈 로드 실패, 기본 분석으로 대체")

                # 기본 분석 (폴백)
                performance_data = {
                    "analysis_date": datetime.now().isoformat(),
                    "status": "fallback_mode",
                    "message": "성과 지표 모듈을 사용할 수 없어 기본 분석 모드로 실행됨",
                }

                os.makedirs("data/learning/performance", exist_ok=True)
                performance_file = f"data/learning/performance/daily_analysis_{datetime.now().strftime('%Y%m%d')}.json"

                with open(performance_file, "w") as f:
                    json.dump(performance_data, f, indent=2, ensure_ascii=False)

            except Exception as ai_error:
                logger.error(f"성과 분석 중 오류 발생: {ai_error}", exc_info=True)
                print(f"성과 분석 중 오류: {ai_error}")

        except Exception as e:
            logger.error(f"일일 성과 분석 오류: {e}", exc_info=True)
            print(f"일일 성과 분석 오류: {e}")

    def _run_enhanced_adaptive_learning(self):
        """강화된 적응형 학습 실행 (포괄적 분석 기반)"""
        try:
            logger.info("=== 강화된 적응형 학습 시작 ===")
            print(
                f"[AI] 강화된 적응형 학습 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            try:
                from core.learning.enhanced_adaptive_system import (
                    get_enhanced_adaptive_system,
                )

                enhanced_system = get_enhanced_adaptive_system()
                result = enhanced_system.run_comprehensive_analysis()

                if result.get("status") != "failed":
                    # 데이터 동기화 결과
                    sync_results = result.get("data_sync", {})
                    screening_synced = sync_results.get("screening_synced", 0)
                    selection_synced = sync_results.get("selection_synced", 0)
                    performance_updated = sync_results.get("performance_updated", 0)

                    # 정확도 분석 결과
                    screening_accuracy = result.get("screening_accuracy")
                    selection_accuracy = result.get("selection_accuracy")

                    # 파라미터 적응 결과
                    adaptation = result.get("parameter_adaptation", {})
                    adapted = adaptation.get("status") == "adapted"

                    # 인사이트 결과
                    insights = result.get("insights", [])
                    actionable_insights = len(
                        [i for i in insights if i.get("actionable", False)]
                    )

                    logger.info(
                        f"강화된 학습 완료: 동기화={screening_synced+selection_synced}건, 적응={'예' if adapted else '아니오'}, 인사이트={actionable_insights}개"
                    )
                    print("강화된 적응형 학습 완료!")
                    print(
                        f"   - 데이터 동기화: 스크리닝 {screening_synced}건, 선정 {selection_synced}건, 성과 {performance_updated}건"
                    )
                    if screening_accuracy:
                        precision = (
                            screening_accuracy.precision
                            if hasattr(screening_accuracy, "precision")
                            else getattr(screening_accuracy, "precision", 0)
                        )
                        recall = (
                            screening_accuracy.recall
                            if hasattr(screening_accuracy, "recall")
                            else getattr(screening_accuracy, "recall", 0)
                        )
                        print(
                            f"   - 스크리닝 정확도: 정밀도 {precision:.1%}, 재현율 {recall:.1%}"
                        )
                    if selection_accuracy:
                        win_rate = (
                            selection_accuracy.win_rate
                            if hasattr(selection_accuracy, "win_rate")
                            else getattr(selection_accuracy, "win_rate", 0)
                        )
                        avg_return = (
                            selection_accuracy.avg_return
                            if hasattr(selection_accuracy, "avg_return")
                            else getattr(selection_accuracy, "avg_return", 0)
                        )
                        print(
                            f"   - 선정 성과: 승률 {win_rate:.1%}, 평균수익률 {avg_return:+.2%}"
                        )
                    print(f"   - 실행 가능한 인사이트: {actionable_insights}개")
                    print(f"   - 파라미터 적응: {'' if adapted else '유지'}")

                    # 텔레그램 상세 알림 전송
                    if adapted or actionable_insights > 0:
                        try:
                            notifier = get_telegram_notifier()
                            alert_message = self._generate_enhanced_learning_alert(result)
                            priority = "high" if adapted else "normal"
                            notifier.send_message(alert_message, priority)
                        except Exception as e:
                            logger.error(f"텔레그램 알림 전송 실패: {e}", exc_info=True)

                else:
                    error_msg = result.get("error", "알 수 없는 오류")
                    print(f"강화된 학습 실패: {error_msg}")
                    logger.error(f"강화된 적응형 학습 실패: {error_msg}", exc_info=True)

            except ImportError as ie:
                logger.warning(f"강화된 학습 모듈 로드 실패: {ie}")
                print("강화된 학습 모듈을 찾을 수 없습니다")

                # 기본 학습 시스템으로 폴백
                print("[상세] 기본 적응형 학습으로 대체 실행...")
                self._run_adaptive_learning_fallback()

        except Exception as e:
            logger.error(f"강화된 적응형 학습 오류: {e}", exc_info=True)
            print(f"강화된 적응형 학습 오류: {e}")

    def _run_adaptive_learning_fallback(self):
        """기본 적응형 학습 실행 (폴백용)"""
        try:
            from core.learning.adaptive_learning_system import (
                get_adaptive_learning_system,
            )

            learning_system = get_adaptive_learning_system()
            result = learning_system.run_daily_learning()

            if result.get("status") == "completed":
                adapted = result.get("adapted", False)
                win_rate = result.get("performance_analysis", {}).get("win_rate", 0)
                total_trades = result.get("performance_analysis", {}).get(
                    "total_trades", 0
                )

                logger.info(
                    f"기본 적응형 학습 완료: 승률={win_rate:.1%}, 거래수={total_trades}건, 적응={adapted}"
                )
                print("기본 적응형 학습 완료!")
                print(f"   - 분석 거래: {total_trades}건")
                print(f"   - 현재 승률: {win_rate:.1%}")
                print(f"   - 파라미터 적응: {'' if adapted else '유지'}")

            elif result.get("status") == "skipped":
                print(f"ℹ️ 적응형 학습 건너뜀: {result.get('message')}")

            else:
                print(f"적응형 학습 실패: {result.get('message')}")

        except Exception as e:
            logger.error(f"기본 적응형 학습 오류: {e}", exc_info=True)
            print(f"기본 적응형 학습 오류: {e}")

    def _generate_enhanced_learning_alert(self, result: Dict[str, Any]) -> str:
        """강화된 학습 결과 알림 메시지 생성"""
        try:
            # 기본 정보
            sync_results = result.get("data_sync", {})
            screening_accuracy = result.get("screening_accuracy")
            selection_accuracy = result.get("selection_accuracy")
            adaptation = result.get("parameter_adaptation", {})
            insights = result.get("insights", [])

            adapted = adaptation.get("status") == "adapted"
            actionable_insights = [
                i for i in insights if getattr(i, "actionable", False)
            ]

            message = f"""[AI] *강화된 AI 학습 완료*

**데이터 동기화**:
• 스크리닝: {sync_results.get('screening_synced', 0)}건
• 선정: {sync_results.get('selection_synced', 0)}건
• 성과 추적: {sync_results.get('performance_updated', 0)}건
• 메트릭: {sync_results.get('metrics_calculated', 0)}개

[목표] **정확도 분석**:"""

            if screening_accuracy:
                message += f"""
• 스크리닝 정밀도: {screening_accuracy.precision:.1%}
• 스크리닝 재현율: {screening_accuracy.recall:.1%}
• F1 점수: {screening_accuracy.f1_score:.2f}"""

            if selection_accuracy:
                message += f"""
• 선정 승률: {selection_accuracy.win_rate:.1%}
• 평균 수익률: {selection_accuracy.avg_return:+.2%}
• 샤프 비율: {selection_accuracy.sharpe_ratio:.2f}"""

            message += f"""

**AI 인사이트**:
• 총 인사이트: {len(insights)}개
• 실행 가능한 제안: {len(actionable_insights)}개"""

            # 주요 인사이트 표시 (최대 2개)
            for insight in actionable_insights[:2]:
                desc = getattr(insight, "description", "")
                message += f"""
• {desc[:50]}{'...' if len(desc) > 50 else ''}"""

            message += f"""

[초기화] **파라미터 적응**:
• 상태: {'완료' if adapted else '유지'}"""

            if adapted:
                changes = adaptation.get("changes_made", [])
                message += f"""
• 변경사항: {len(changes)}건"""
                for change in changes[:2]:
                    message += f"""
  - {change[:40]}{'...' if len(change) > 40 else ''}"""

            message += f"""

분석 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

*AI가 포괄적 분석을 통해 시스템을 최적화했습니다!*"""

            return message

        except Exception as e:
            # 상세 에러 정보 로깅
            logger.error(
                f"강화된 학습 알림 메시지 생성 실패: {e}",
                exc_info=True,
                extra={
                    "error_type": type(e).__name__,
                    "result_keys": (
                        list(result.keys()) if isinstance(result, dict) else "N/A"
                    ),
                    "screening_accuracy_type": (
                        type(result.get("screening_accuracy")).__name__
                        if isinstance(result, dict)
                        else "N/A"
                    ),
                    "selection_accuracy_type": (
                        type(result.get("selection_accuracy")).__name__
                        if isinstance(result, dict)
                        else "N/A"
                    ),
                },
            )
            return f"""[AI] *강화된 AI 학습 완료*

포괄적 분석이 완료되었습니다.

시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

상세 결과는 시스템 로그를 확인하세요."""

    def _run_weekly_adaptive_learning(self):
        """주간 깊이 학습 실행 (30일 데이터 기반)"""
        try:
            logger.info("=== 주간 깊이 학습 시작 ===")
            print(
                f"[분석] 주간 깊이 학습 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            try:
                from core.learning.adaptive_learning_system import (
                    get_adaptive_learning_system,
                )

                learning_system = get_adaptive_learning_system()
                result = learning_system.run_weekly_learning()

                if result.get("status") == "completed":
                    adapted = result.get("adapted", False)
                    perf_data = result.get("performance_analysis", {})
                    trend_data = result.get("trend_analysis", {})

                    win_rate = perf_data.get("win_rate", 0)
                    total_trades = perf_data.get("total_trades", 0)
                    avg_return = perf_data.get("avg_return", 0)
                    return_trend = trend_data.get("return_trend", "unknown")

                    logger.info(
                        f"주간 학습 완료: 승률={win_rate:.1%}, 수익률={avg_return:.2%}, 트렌드={return_trend}"
                    )
                    print("주간 깊이 학습 완료!")
                    print(f"   - 30일 거래: {total_trades}건")
                    print(f"   - 평균 승률: {win_rate:.1%}")
                    print(f"   - 수익률 트렌드: {return_trend}")
                    print(f"   - 파라미터 적응: {'' if adapted else '유지'}")

                    # 텔레그램 알림 전송
                    if adapted or total_trades > 0:
                        emoji = (
                            ""
                            if return_trend == "improving"
                            else "" if return_trend == "declining" else ""
                        )

                        alert_message = f"""[분석] *주간 AI 깊이 학습 완료*

**30일 성과 분석**:
• 총 거래: {total_trades}건
• 평균 승률: {win_rate:.1%}
• 평균 수익률: {avg_return:+.2%}
• 트렌드: {return_trend} {emoji}

[AI] **학습 결과**:
• 파라미터 적응: {'완료' if adapted else '유지'}

시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

[목표] *AI가 한 주간의 성과를 분석하여 전략을 최적화했습니다!*"""

                        try:
                            notifier = get_telegram_notifier()
                            priority = "high" if adapted else "normal"
                            notifier.send_message(alert_message, priority)
                        except Exception as e:
                            logger.error(f"텔레그램 알림 전송 실패: {e}", exc_info=True)

                else:
                    print(f"ℹ️ 주간 학습 건너뜀: {result.get('message')}")

            except ImportError as ie:
                logger.warning(f"주간 학습 모듈 로드 실패: {ie}")
                print("주간 학습 모듈을 찾을 수 없습니다")

        except Exception as e:
            logger.error(f"주간 깊이 학습 오류: {e}", exc_info=True)
            print(f"주간 깊이 학습 오류: {e}")

    def _run_weekly_backtest(self):
        """주간 백테스트 실행 (방안 B)"""
        try:
            logger.info("=== 주간 백테스트 시작 ===")
            print(
                f"주간 백테스트 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            try:
                from core.backtesting.strategy_backtester import StrategyBacktester
                from core.daily_selection.selection_criteria import (
                    SelectionCriteria,
                    CriteriaRange,
                    MarketCondition,
                )

                # 백테스터 초기화 (1억원 초기 자본)
                backtester = StrategyBacktester(initial_capital=100000000)

                # 최근 30일 기간 설정
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)

                logger.info(
                    f"백테스트 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}"
                )

                # 현재 보수적 전략 설정
                conservative_criteria = SelectionCriteria(
                    name="Conservative Strategy",
                    description="보수적 전략 - 낮은 리스크, 높은 신뢰도",
                    market_condition=MarketCondition.SIDEWAYS,
                    created_date=datetime.now().strftime("%Y-%m-%d"),
                    price_attractiveness=CriteriaRange(80.0, 100.0, 90.0, 0.35),
                    technical_score=CriteriaRange(70.0, 100.0, 85.0, 0.35),
                    risk_score=CriteriaRange(0.0, 25.0, 15.0, 0.4),
                    confidence=CriteriaRange(0.75, 1.0, 0.85, 0.25),
                    max_position_size=0.08,
                )

                conservative_trading = {
                    "position_size": 0.05,
                    "stop_loss_pct": 0.03,
                    "take_profit_pct": 0.08,
                    "risk_per_trade": 0.015,
                }

                # 보수적 전략 백테스트
                logger.info("보수적 전략 백테스트 실행 중...")
                conservative_result = backtester.backtest_selection_strategy(
                    start_date=start_date,
                    end_date=end_date,
                    selection_criteria=conservative_criteria,
                    trading_config=conservative_trading,
                    strategy_name="Conservative",
                )

                # 이전 공격적 전략 설정 (비교용)
                aggressive_criteria = SelectionCriteria(
                    name="Aggressive Strategy",
                    description="공격적 전략 - 높은 리스크, 높은 수익 추구",
                    market_condition=MarketCondition.BULL_MARKET,
                    created_date=datetime.now().strftime("%Y-%m-%d"),
                    price_attractiveness=CriteriaRange(75.0, 100.0, 85.0, 0.3),
                    technical_score=CriteriaRange(60.0, 100.0, 80.0, 0.3),
                    risk_score=CriteriaRange(0.0, 35.0, 20.0, 0.35),
                    confidence=CriteriaRange(0.65, 1.0, 0.80, 0.2),
                    max_position_size=0.12,
                )

                aggressive_trading = {
                    "position_size": 0.10,
                    "stop_loss_pct": 0.05,
                    "take_profit_pct": 0.10,
                    "risk_per_trade": 0.02,
                }

                # 공격적 전략 백테스트
                logger.info("공격적 전략 백테스트 실행 중...")
                aggressive_result = backtester.backtest_selection_strategy(
                    start_date=start_date,
                    end_date=end_date,
                    selection_criteria=aggressive_criteria,
                    trading_config=aggressive_trading,
                    strategy_name="Aggressive",
                )

                # 결과 저장
                from pathlib import Path
                import json

                backtest_dir = Path("data/backtesting")
                backtest_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result_file = backtest_dir / f"weekly_backtest_{timestamp}.json"

                results = {
                    "timestamp": timestamp,
                    "period": {
                        "start": start_date.strftime("%Y-%m-%d"),
                        "end": end_date.strftime("%Y-%m-%d"),
                    },
                    "conservative": {
                        "win_rate": conservative_result.win_rate,
                        "avg_return": conservative_result.avg_return,
                        "max_drawdown": conservative_result.max_drawdown,
                        "sharpe_ratio": conservative_result.sharpe_ratio,
                        "profit_factor": conservative_result.profit_factor,
                        "total_trades": conservative_result.total_trades,
                    },
                    "aggressive": {
                        "win_rate": aggressive_result.win_rate,
                        "avg_return": aggressive_result.avg_return,
                        "max_drawdown": aggressive_result.max_drawdown,
                        "sharpe_ratio": aggressive_result.sharpe_ratio,
                        "profit_factor": aggressive_result.profit_factor,
                        "total_trades": aggressive_result.total_trades,
                    },
                }

                with open(result_file, "w", encoding="utf-8") as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)

                logger.info(f"백테스트 결과 저장 완료: {result_file}")

                # 결과 출력
                print("\n주간 백테스트 완료!")
                print("\n보수적 전략:")
                print(f"   - 승률: {conservative_result.win_rate:.1%}")
                print(f"   - 평균 수익률: {conservative_result.avg_return:+.2%}")
                print(f"   - 샤프 비율: {conservative_result.sharpe_ratio:.2f}")
                print(f"   - 최대 낙폭: {conservative_result.max_drawdown:.1%}")
                print(f"   - 총 거래: {conservative_result.total_trades}건")

                print("\n공격적 전략:")
                print(f"   - 승률: {aggressive_result.win_rate:.1%}")
                print(f"   - 평균 수익률: {aggressive_result.avg_return:+.2%}")
                print(f"   - 샤프 비율: {aggressive_result.sharpe_ratio:.2f}")
                print(f"   - 최대 낙폭: {aggressive_result.max_drawdown:.1%}")
                print(f"   - 총 거래: {aggressive_result.total_trades}건")

                # 텔레그램 알림 전송
                better_strategy = (
                    "보수적"
                    if conservative_result.sharpe_ratio > aggressive_result.sharpe_ratio
                    else "공격적"
                )

                alert_message = f"""*주간 백테스트 완료*

[날짜] **분석 기간**: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}

[목표] **보수적 전략**:
• 승률: {conservative_result.win_rate:.1%}
• 평균 수익: {conservative_result.avg_return:+.2%}
• 샤프 비율: {conservative_result.sharpe_ratio:.2f}
• 최대 낙폭: {conservative_result.max_drawdown:.1%}
• 거래 건수: {conservative_result.total_trades}건

[빠름] **공격적 전략**:
• 승률: {aggressive_result.win_rate:.1%}
• 평균 수익: {aggressive_result.avg_return:+.2%}
• 샤프 비율: {aggressive_result.sharpe_ratio:.2f}
• 최대 낙폭: {aggressive_result.max_drawdown:.1%}
• 거래 건수: {aggressive_result.total_trades}건

[우수] **권장 전략**: {better_strategy}

시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

[제안] *과거 성과를 기반으로 전략을 검증했습니다!*"""

                try:
                    notifier = get_telegram_notifier()
                    notifier.send_message(alert_message, "normal")
                except Exception as e:
                    logger.error(f"텔레그램 알림 전송 실패: {e}", exc_info=True)

            except ImportError as ie:
                logger.warning(f"백테스트 모듈 로드 실패: {ie}")
                print("백테스트 모듈을 찾을 수 없습니다")

        except Exception as e:
            logger.error(f"주간 백테스트 오류: {e}", exc_info=True)
            print(f"주간 백테스트 오류: {e}")
            import traceback

            traceback.print_exc()

    def _start_system_monitoring(self):
        """시스템 모니터링 시작"""
        try:
            logger.info("=== 시스템 모니터링 시작 ===")
            print(
                f"[모니터] 시스템 모니터링 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            try:
                from core.monitoring.system_monitor import get_system_monitor

                monitor = get_system_monitor()
                success = monitor.start_monitoring()

                if success:
                    logger.info("시스템 모니터링 시작 완료")
                    print("시스템 모니터링이 백그라운드에서 시작되었습니다!")
                    print("   - CPU, 메모리, 디스크 사용량 모니터링")
                    print("   - 학습 시스템 건강 상태 추적")
                    print("   - 자동 알림 및 보고서 생성")

                    # 모니터링 시작 알림
                    alert_message = f"""[모니터] *시스템 모니터링 시작*

**모니터링 항목**:
• 시스템 리소스 (CPU, 메모리, 디스크)
• 학습 시스템 건강 상태
• 데이터 신선도 및 무결성
• 예측 정확도 추적

[설정] **설정**:
• 체크 주기: 5분마다
• 일일 보고서: 오후 6시
• 자동 알림: 임계값 초과 시

시작 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

[자동] *AI 시스템이 스스로를 지속적으로 모니터링합니다!*"""

                    try:
                        notifier = get_telegram_notifier()
                        notifier.send_message(alert_message, "normal")
                    except Exception as e:
                        logger.error(f"텔레그램 알림 전송 실패: {e}", exc_info=True)

                else:
                    logger.warning("시스템 모니터링 시작 실패 (이미 실행 중일 수 있음)")
                    print("시스템 모니터링 시작 실패 (이미 실행 중일 수 있음)")

            except ImportError as ie:
                logger.warning(f"시스템 모니터링 모듈 로드 실패: {ie}")
                print("시스템 모니터링 모듈을 찾을 수 없습니다")

        except Exception as e:
            logger.error(f"시스템 모니터링 시작 오류: {e}", exc_info=True)
            print(f"시스템 모니터링 시작 오류: {e}")

    def _run_health_check(self):
        """자동 매매 헬스체크 실행 (문제 발견 시 알람 + 자동 수정)"""
        try:
            logger.info("=== 자동 매매 헬스체크 시작 ===")

            from core.monitoring.trading_health_checker import get_health_checker
            from core.utils.telegram_notifier import get_telegram_notifier

            health_checker = get_health_checker()
            result = health_checker.check_trading_health()

            if result.is_healthy:
                logger.info("헬스체크 완료: 시스템 정상")
            else:
                # 문제 발견 시 처리
                issue_count = len(result.issues)
                logger.warning(f"헬스체크 완료: {issue_count}개 문제 발견")

                # 1. 텔레그램 알람 전송
                try:
                    notifier = get_telegram_notifier()
                    if notifier.is_enabled():
                        issues_text = "\n".join([f"• {issue}" for issue in result.issues[:5]])  # 최대 5개만
                        message = (
                            f"🚨 장중 헬스체크 문제 발견\n\n"
                            f"발견 시각: {datetime.now().strftime('%H:%M:%S')}\n"
                            f"문제 수: {issue_count}개\n\n"
                            f"주요 문제:\n{issues_text}"
                        )
                        if issue_count > 5:
                            message += f"\n... 외 {issue_count - 5}개"

                        notifier.send_message(message, level="warning")
                        logger.info("헬스체크 알람 전송 완료")
                except Exception as e:
                    logger.error(f"헬스체크 알람 전송 실패: {e}", exc_info=True)

                # 2. 심각한 문제 시 자동 유지보수 트리거
                critical_issues = [issue for issue in result.issues if "critical" in issue.lower() or "심각" in issue.lower()]
                if critical_issues:
                    logger.warning(f"심각한 문제 {len(critical_issues)}개 발견 - 자동 유지보수 트리거")
                    try:
                        notifier = get_telegram_notifier()
                        if notifier.is_enabled():
                            notifier.send_message(
                                "⚠️ 심각한 문제 발견 - 자동 유지보수 시작",
                                level="high"
                            )
                        self._run_auto_maintenance()
                    except Exception as e:
                        logger.error(f"자동 유지보수 트리거 실패: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"헬스체크 실행 오류: {e}", exc_info=True)
            # 헬스체크 자체가 실패하면 알람
            try:
                from core.utils.telegram_notifier import get_telegram_notifier
                notifier = get_telegram_notifier()
                if notifier.is_enabled():
                    notifier.send_message(
                        f"❌ 헬스체크 실행 실패\n\n오류: {str(e)}",
                        level="high"
                    )
            except Exception:
                pass  # 알람 실패는 무시

    def _run_auto_maintenance(self):
        """자동 유지보수 실행"""
        try:
            logger.info("=== 자동 유지보수 시작 ===")
            print(
                f"[초기화] 자동 유지보수 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            try:
                from core.monitoring.system_monitor import get_system_monitor

                monitor = get_system_monitor()
                maintenance_result = monitor.run_maintenance_check()

                needs_maintenance = maintenance_result.get("needs_maintenance", False)
                maintenance_executed = maintenance_result.get(
                    "maintenance_executed", False
                )
                reasons = maintenance_result.get("reasons", [])

                logger.info(
                    f"유지보수 체크 완료: 필요={'예' if needs_maintenance else '아니오'}, 실행={'예' if maintenance_executed else '아니오'}"
                )
                print("자동 유지보수 체크 완료!")
                print(f"   - 유지보수 필요: {'예' if needs_maintenance else '아니오'}")
                print(
                    f"   - 유지보수 실행: {'예' if maintenance_executed else '아니오'}"
                )

                if needs_maintenance:
                    print(f"   - 필요 사유: {', '.join(reasons[:3])}")

                    # 유지보수 실행 알림
                    if maintenance_executed:
                        maintenance_details = maintenance_result.get(
                            "maintenance_result", {}
                        )
                        tasks_completed = maintenance_details.get("tasks_completed", [])

                        alert_message = f"""[초기화] *자동 유지보수 실행*

**유지보수 완료**:
• 필요 사유: {len(reasons)}건
• 실행 작업: {len(tasks_completed)}개

[상세] **주요 사유**:"""

                        for reason in reasons[:3]:
                            alert_message += f"\n• {reason}"

                        alert_message += """

[작업] **실행된 작업**:"""

                        for task in tasks_completed:
                            task_name = task.replace("_", " ").title()
                            alert_message += f"\n• {task_name}"

                        alert_message += f"""

실행 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

*시스템이 자동으로 최적화되었습니다!*"""

                        try:
                            notifier = get_telegram_notifier()
                            notifier.send_message(alert_message, "normal")
                        except Exception as e:
                            logger.error(f"텔레그램 알림 전송 실패: {e}", exc_info=True)

                    else:
                        # 유지보수 필요하지만 실행 안 된 경우
                        alert_message = """*유지보수 필요*

**점검 결과**:
• 유지보수가 필요하지만 자동 실행되지 않았습니다

[상세] **필요 사유**:"""

                        for reason in reasons[:3]:
                            alert_message += f"\n• {reason}"

                        alert_message += f"""

체크 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

[작업] *수동으로 유지보수를 실행하는 것을 고려하세요*"""

                        try:
                            notifier = get_telegram_notifier()
                            notifier.send_message(alert_message, "warning")
                        except Exception as e:
                            logger.error(f"텔레그램 알림 전송 실패: {e}", exc_info=True)

                else:
                    print("   - 시스템 상태 양호, 유지보수 불필요")

            except ImportError as ie:
                logger.warning(f"자동 유지보수 모듈 로드 실패: {ie}")
                print("자동 유지보수 모듈을 찾을 수 없습니다")

        except Exception as e:
            logger.error(f"자동 유지보수 오류: {e}", exc_info=True)
            print(f"자동 유지보수 오류: {e}")

    def _check_ml_trigger(self):
        """ML 학습 조건 체크 및 자동 트리거"""
        try:
            logger.info("=== ML 학습 조건 체크 시작 ===")
            print(
                f"[자동] ML 학습 조건 체크 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            try:
                from core.learning.auto_ml_trigger import get_auto_ml_trigger

                ml_trigger = get_auto_ml_trigger()

                # 조건 체크 및 자동 트리거
                triggered = ml_trigger.check_and_trigger()

                if triggered:
                    logger.info("ML 학습이 자동으로 트리거되었습니다!")
                    print("ML 학습 조건 충족 - B단계 자동 시작!")
                else:
                    # 진행률 조회
                    progress = ml_trigger.get_progress_to_ml()

                    if progress:
                        overall = progress.get("overall_progress", 0)
                        conditions_met = progress.get("conditions_met", False)

                        logger.info(f"ML 학습 진행률: {overall:.1f}%")
                        print(f"ML 학습 준비 진행률: {overall:.1f}%")

                        if not conditions_met:
                            days_remaining = progress.get("estimated_days_remaining", 0)
                            print(f"   - 예상 남은 기간: 약 {days_remaining}일")
                            print(
                                f"   - 거래일: {progress.get('trading_days_progress', 0):.0f}%"
                            )
                            print(
                                f"   - 선정 기록: {progress.get('selection_records_progress', 0):.0f}%"
                            )
                            print(
                                f"   - 성과 기록: {progress.get('performance_records_progress', 0):.0f}%"
                            )
                            print(
                                f"   - 승률: {progress.get('win_rate_progress', 0):.0f}%"
                            )

            except ImportError as ie:
                logger.warning(f"ML 트리거 모듈 로드 실패: {ie}")
                print("ML 트리거 모듈을 찾을 수 없습니다")

        except Exception as e:
            logger.error(f"ML 학습 조건 체크 오류: {e}", exc_info=True)
            print(f"ML 학습 조건 체크 오류: {e}")

    def _start_auto_trading(self, from_recovery: bool = False) -> bool:
        """자동 매매 시작 (싱글톤 사용으로 중복 실행 방지)

        Args:
            from_recovery: 복구 작업에서 호출되었는지 여부

        Returns:
            bool: 실제로 자동 매매가 시작되었는지 여부
        """
        try:
            logger.info("=== 자동 매매 시작 ===")
            print(f"자동 매매 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 매매 엔진 import 및 초기화
            try:
                from core.trading.trading_engine import (
                    get_trading_engine,
                    TradingConfig,
                )

                # 기본 매매 설정 (계좌 대비 10%씩 투자)
                config = TradingConfig(
                    max_positions=10,
                    position_size_method="account_pct",  # 계좌 비율 방식
                    position_size_value=0.10,  # 계좌의 10%씩
                    stop_loss_pct=0.05,  # 5% 손절
                    take_profit_pct=0.10,  # 10% 익절
                    max_trades_per_day=20,
                    use_kelly_criterion=True,  # Kelly Criterion 사용
                    kelly_multiplier=0.25,  # 보수적 적용
                )

                # 싱글톤 패턴으로 매매 엔진 가져오기 (중복 생성 방지)
                trading_engine = get_trading_engine(config)

                # 이미 실행 중이면 스킵
                if trading_engine.is_running:
                    logger.info("자동 매매가 이미 실행 중입니다. 중복 시작 방지.")
                    print("ℹ️ 자동 매매가 이미 실행 중입니다.")
                    return False

                # Batch 4-2: 서킷 브레이커 상태 확인
                can_trade, circuit_msg = trading_engine.check_circuit_breaker()
                if not can_trade:
                    logger.warning(f"서킷브레이커로 인해 자동매매 시작 불가: {circuit_msg}")
                    print(f"⚠️ 서킷브레이커 발동: {circuit_msg}")
                    self._safe_send_telegram(f"⚠️ 서킷브레이커 발동\n{circuit_msg}")
                    return False
                else:
                    logger.info(f"서킷브레이커 상태: {circuit_msg}")

                # 백그라운드에서 자동 매매 실행
                def run_trading():
                    try:
                        import asyncio

                        # 새로운 이벤트 루프 생성
                        asyncio.set_event_loop(asyncio.new_event_loop())
                        loop = asyncio.get_event_loop()
                        loop.run_until_complete(trading_engine.start_trading())
                    except Exception as e:
                        logger.error(f"자동 매매 실행 오류: {e}", exc_info=True)
                        import traceback

                        logger.error(
                            f"상세 오류:\n{traceback.format_exc()}", exc_info=True
                        )

                trading_thread = threading.Thread(target=run_trading, daemon=True)
                trading_thread.start()

                logger.info("자동 매매 시작 완료")
                print("자동 매매가 백그라운드에서 시작되었습니다!")

                # 복구 시에는 스케줄러에서 알림 전송 (trading_engine.start_trading() 내부 알림과 별개)
                if from_recovery:
                    try:
                        notifier = get_telegram_notifier()
                        if notifier.is_enabled():
                            notifier.send_message(
                                f"[갱신] *자동 매매 복구 시작*\n\n"
                                f"시간: `{datetime.now().strftime('%H:%M:%S')}`\n"
                                f"[상세] CI/CD 배포 후 스케줄러 재시작으로 자동 매매를 복구합니다.",
                                "high",
                            )
                    except Exception as e:
                        logger.warning(f"복구 알림 전송 실패: {e}")

                return True

            except ImportError as ie:
                logger.error(f"매매 엔진 import 실패: {ie}", exc_info=True)
                print(f"매매 엔진 import 실패: {ie}")
                return False

        except Exception as e:
            logger.error(f"자동 매매 시작 오류: {e}", exc_info=True)
            print(f"자동 매매 시작 오류: {e}")
            import traceback

            logger.error(f"상세 오류:\n{traceback.format_exc()}", exc_info=True)
            return False

    def _stop_auto_trading(self):
        """자동 매매 중지"""
        try:
            logger.info("=== 자동 매매 중지 ===")
            print(f"[중지] 자동 매매 중지 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                # 글로벌 매매 엔진 인스턴스가 있다면 가져오기
                from core.trading.trading_engine import get_trading_engine

                trading_engine = get_trading_engine()

                # 매매 중지
                if trading_engine and trading_engine.is_running:

                    def stop_trading():
                        try:
                            import asyncio

                            asyncio.set_event_loop(asyncio.new_event_loop())
                            loop = asyncio.get_event_loop()
                            loop.run_until_complete(
                                trading_engine.stop_trading("스케줄러 자동 중지")
                            )
                        except Exception as e:
                            logger.error(
                                f"자동 매매 중지 실행 오류: {e}", exc_info=True
                            )

                    stop_thread = threading.Thread(target=stop_trading, daemon=False)
                    stop_thread.start()
                    stop_thread.join(timeout=10)  # 최대 10초 대기

                    logger.info("자동 매매 중지 완료")
                    print("자동 매매가 중지되었습니다!")

                    # 텔레그램 중지 알림
                    try:
                        notifier = get_telegram_notifier()
                        alert_message = f"""[중지] *자동 매매 중지*

중지 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
장 마감으로 자동매매를 중지합니다.

*오늘의 매매 결과는 일일 리포트를 확인하세요!*"""
                        notifier.send_message(alert_message, "normal")
                    except Exception as e:
                        logger.error(f"텔레그램 알림 전송 실패: {e}", exc_info=True)

                else:
                    logger.info("자동 매매가 실행 중이 아닙니다")
                    print("ℹ️ 자동 매매가 실행 중이 아닙니다.")

            except ImportError as ie:
                logger.warning(f"매매 엔진 import 실패: {ie}")
                print("ℹ️ 자동 매매 엔진을 찾을 수 없습니다.")

        except Exception as e:
            logger.error(f"자동 매매 중지 오류: {e}", exc_info=True)
            print(f"자동 매매 중지 오류: {e}")
            import traceback

            logger.error(f"상세 오류:\n{traceback.format_exc()}", exc_info=True)

    def _send_data_to_ai_system(self):
        """Phase 1,2 완료 후 AI 학습 시스템에 데이터 전달"""
        try:
            logger.info("=== AI 학습 시스템 데이터 연동 시작 ===")
            print(
                f"[연동] AI 학습 데이터 연동 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Phase 1 스크리닝 결과 수집
            screening_data = self._collect_phase1_data()

            # Phase 2 선정 결과 수집
            selection_data = self._collect_phase2_data()

            # AI 학습용 통합 데이터 생성
            ai_learning_data = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "timestamp": datetime.now().isoformat(),
                "phase1_screening": screening_data,
                "phase2_selection": selection_data,
                "integration_status": "completed",
            }

            # AI 학습 데이터 저장
            os.makedirs("data/learning/raw_data", exist_ok=True)
            ai_data_file = f"data/learning/raw_data/daily_integration_{datetime.now().strftime('%Y%m%d')}.json"

            with open(ai_data_file, "w") as f:
                json.dump(ai_learning_data, f, indent=2, ensure_ascii=False)

            # 피드백 시스템에 데이터 전달 (간소화된 버전)
            self._update_feedback_system(ai_learning_data)

            logger.info("AI 학습 시스템 데이터 연동 완료")
            print("AI 학습 데이터 연동 완료!")

        except Exception as e:
            logger.error(f"AI 학습 데이터 연동 오류: {e}", exc_info=True)
            print(f"AI 학습 데이터 연동 오류: {e}")

    def _collect_phase1_data(self):
        """Phase 1 스크리닝 데이터 수집"""
        try:
            # 최신 스크리닝 결과 파일 찾기
            screening_dir = "data/watchlist"
            screening_files = [
                f
                for f in os.listdir(screening_dir)
                if f.startswith("screening_results_") and f.endswith(".json")
            ]

            if screening_files:
                latest_file = max(screening_files)
                screening_file_path = os.path.join(screening_dir, latest_file)

                # 파일 크기 확인 (너무 큰 파일은 요약만)
                file_size = os.path.getsize(screening_file_path)
                if file_size > 1024 * 1024:  # 1MB 이상이면 요약만
                    return {
                        "file_name": latest_file,
                        "file_size_mb": round(file_size / (1024 * 1024), 2),
                        "status": "large_file_summarized",
                        "total_screened_stocks": 2875,  # 대략적 수치
                    }

            return {
                "total_screened_stocks": 2875,
                "watchlist_stocks": 2221,
                "status": "completed",
            }

        except Exception as e:
            logger.warning(f"Phase 1 데이터 수집 오류: {e}")
            return {"status": "error", "error": str(e)}

    def _collect_phase2_data(self):
        """Phase 2 선정 데이터 수집"""
        try:
            # 최신 선정 결과 파일 읽기
            selection_file = "data/daily_selection/latest_selection.json"

            if os.path.exists(selection_file):
                with open(selection_file, "r") as f:
                    selection_data = json.load(f)

                # 다양한 데이터 형식 지원 (list, dict with data.selected_stocks, dict with stocks)
                if isinstance(selection_data, list):
                    selected_stocks = selection_data
                    filtering_criteria = {}
                    market_condition = "neutral"
                elif isinstance(selection_data, dict):
                    selected_stocks = selection_data.get("data", {}).get("selected_stocks", []) or selection_data.get("stocks", [])
                    filtering_criteria = selection_data.get("metadata", {}).get("filtering_criteria", {})
                    market_condition = selection_data.get("market_condition", "neutral")
                else:
                    selected_stocks = []
                    filtering_criteria = {}
                    market_condition = "neutral"

                return {
                    "total_selected_stocks": len(selected_stocks),
                    "selection_criteria": filtering_criteria,
                    "market_condition": market_condition,
                    "status": "completed",
                }

            return {"total_selected_stocks": 50, "status": "completed"}  # 기본값

        except Exception as e:
            logger.warning(f"Phase 2 데이터 수집 오류: {e}")
            return {"status": "error", "error": str(e)}

    def _update_feedback_system(self, ai_learning_data):
        """피드백 시스템 업데이트 (간소화된 버전)"""
        try:
            # 피드백 데이터 생성
            feedback_data = {
                "feedback_date": datetime.now().isoformat(),
                "total_predictions": ai_learning_data["phase2_selection"].get(
                    "total_selected_stocks", 50
                ),
                "data_quality_score": 0.95,  # 데이터 품질 점수
                "integration_success": True,
                "learning_ready": True,
            }

            # 피드백 데이터 저장
            os.makedirs("data/learning/feedback", exist_ok=True)
            feedback_file = f"data/learning/feedback/daily_feedback_{datetime.now().strftime('%Y%m%d')}.json"

            with open(feedback_file, "w") as f:
                json.dump(feedback_data, f, indent=2, ensure_ascii=False)

            logger.info("피드백 시스템 업데이트 완료")

        except Exception as e:
            logger.warning(f"피드백 시스템 업데이트 오류: {e}")

    def _print_daily_summary(self):
        """일일 선정 결과 요약 출력"""
        try:
            # 최신 선정 결과 조회
            _v_latest_selection = (
                self._v_phase2_cli._v_daily_updater.get_latest_selection()
            )

            if _v_latest_selection:
                # 다양한 데이터 형식 지원 (list, dict with data.selected_stocks, dict with stocks)
                if isinstance(_v_latest_selection, list):
                    _v_selected_stocks = _v_latest_selection
                    _v_metadata = {}
                elif isinstance(_v_latest_selection, dict):
                    _v_selected_stocks = _v_latest_selection.get("data", {}).get("selected_stocks", []) or _v_latest_selection.get("stocks", [])
                    _v_metadata = _v_latest_selection.get("metadata", {})
                else:
                    _v_selected_stocks = []
                    _v_metadata = {}

                print("\n[상세] 일일 선정 결과 요약")
                print(f"├─ 선정 종목: {len(_v_selected_stocks)}개")
                print(
                    f"├─ 평균 매력도: {_v_metadata.get('avg_attractiveness', 0):.1f}점"
                )
                print(
                    f"└─ 시장 상황: {_v_latest_selection.get('market_condition', 'unknown')}"
                )

                if _v_selected_stocks:
                    print("\n상위 5개 종목:")
                    for i, stock in enumerate(_v_selected_stocks[:5], 1):
                        print(
                            f"  {i}. {stock.get('stock_name', '')} ({stock.get('stock_code', '')}) - {stock.get('price_attractiveness', 0):.1f}점"
                        )

        except Exception as e:
            logger.error(f"일일 요약 출력 오류: {e}", exc_info=True)

    def run_immediate_tasks(self):
        """즉시 실행 (테스트용)"""
        print("[갱신] 즉시 실행 모드")
        print("1. 일간 스크리닝 실행...")
        self._run_daily_screening()

        # Phase 1이 성공했을 때만 Phase 2가 자동 실행됨
        if not self._v_phase1_completed:
            print("\nPhase 1 실패로 인해 Phase 2를 건너뜁니다")

        print("\n2. 정리 작업 실행...")
        self._run_market_close_tasks()

        print("\n모든 작업 완료!")

    def _generate_screening_alert(self) -> str:
        """스크리닝 완료 알람 메시지 생성"""
        try:
            # 감시 리스트 통계 조회
            watchlist_manager = WatchlistManager("data/watchlist/watchlist.json")
            stats = watchlist_manager.get_statistics()

            total_stocks = stats.get("total_count", 0)
            avg_score = stats.get("avg_score", 0.0)
            sectors = stats.get("sectors", {})

            # 상위 섹터 3개 추출
            top_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:3]

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            message = f"""[아침] *한투 퀀트 아침 스크리닝 완료*

완료 시간: `{current_time}`
분석 종목: `2,875개`
선정 종목: `{total_stocks}개`
평균 점수: `{avg_score:.1f}점`

[우수] *상위 섹터*:"""

            for i, (sector, count) in enumerate(top_sectors, 1):
                percentage = (count / total_stocks * 100) if total_stocks > 0 else 0
                message += f"\n{i}. {sector}: {count}개 ({percentage:.1f}%)"

            message += """

[목표] *오늘의 투자 포인트*:
• 고성장 섹터 집중 모니터링
• 기술적 반등 신호 종목 주목
• 거래량 급증 종목 추적

*이제 AI가 선별한 우량 종목으로 투자하세요!*

[설정] 다음 업데이트: 일일 매매 리스트 (Phase 2 진행 중)"""

            return message

        except Exception as e:
            logger.error(f"스크리닝 알람 메시지 생성 실패: {e}", exc_info=True)
            return f"""[아침] *한투 퀀트 아침 스크리닝 완료*

완료 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
스크리닝이 성공적으로 완료되었습니다!

*AI 종목 선별 시스템이 가동 중입니다!*"""


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="한투 퀀트 통합 스케줄러")

    # 서브커맨드 설정
    subparsers = parser.add_subparsers(dest="command", help="사용 가능한 명령")

    # 스케줄러 시작
    start_parser = subparsers.add_parser("start", help="스케줄러 시작")
    start_parser.add_argument(
        "--force-local",
        action="store_true",
        help="로컬 환경에서 강제 실행 (디버깅 전용, SSH 터널 필요)"
    )

    # 스케줄러 중지
    subparsers.add_parser("stop", help="스케줄러 중지")

    # 상태 조회
    status_parser = subparsers.add_parser("status", help="스케줄러 상태 조회")
    status_parser.add_argument(
        "--telegram", action="store_true", help="텔레그램으로 상태 전송"
    )
    status_parser.add_argument(
        "--heartbeat", action="store_true", help="생존 신호 전송"
    )

    # 즉시 실행
    subparsers.add_parser("run", help="즉시 실행 (테스트용)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 환경 체크는 이미 check_environment_early()에서 수행됨
    # 스케줄러 생성 (병렬 워커 수 설정)
    scheduler = IntegratedScheduler(p_parallel_workers=4)

    try:
        if args.command == "start":
            scheduler.start_scheduler()

            # 백그라운드에서 실행하기 위해 대기
            print("Press Ctrl+C to stop the scheduler...")
            while True:
                time.sleep(1)

        elif args.command == "stop":
            scheduler.stop_scheduler()

        elif args.command == "status":
            status = scheduler.get_status()

            print("\n통합 스케줄러 상태")
            print(f"├─ 실행 상태: {'[실행중] 실행 중' if status['running'] else '[중지됨] 정지'}")
            print(f"├─ 마지막 스크리닝: {status['last_screening']}")
            print(f"└─ 마지막 일일 업데이트: {status['last_daily_update']}")

            if status["scheduled_jobs"]:
                print("\n[날짜] 예정된 작업:")
                for job in status["scheduled_jobs"]:
                    print(f"  - {job['job']}: {job['next_run']}")

            # 텔레그램으로 상태 전송
            if args.telegram:
                try:
                    from core.utils.telegram_notifier import get_telegram_notifier

                    notifier = get_telegram_notifier()

                    if notifier.is_enabled():
                        # 상태 메시지 생성
                        status_emoji = "[실행중]" if status["running"] else "[중지됨]"
                        status_text = "실행 중" if status["running"] else "정지"

                        message = f"""*한투 퀀트 스케줄러 상태*

{status_emoji} *현재 상태*: `{status_text}`
[날짜] 마지막 스크리닝: `{status['last_screening']}`
마지막 업데이트: `{status['last_daily_update']}`

[상세] *예정된 작업*:"""

                        if status["scheduled_jobs"]:
                            for job in status["scheduled_jobs"]:
                                message += f"\n• {job['job']}: {job['next_run']}"
                        else:
                            message += "\n• 예정된 작업 없음"

                        success = notifier.send_message(message, "normal")
                        if success:
                            print("[알림] 텔레그램으로 상태 전송 완료")
                        else:
                            print("텔레그램 상태 전송 실패")
                    else:
                        print("텔레그램 알림이 비활성화됨")

                except Exception as e:
                    print(f"텔레그램 상태 전송 오류: {e}")

            # 헬스체크 (생존 신호) 전송
            if args.heartbeat and status["running"]:
                try:
                    from core.utils.telegram_notifier import get_telegram_notifier

                    notifier = get_telegram_notifier()

                    if notifier.is_enabled():
                        # 실행 시간 계산 (임시로 현재 시간 기준)
                        uptime = (
                            "알 수 없음"  # 실제로는 시작 시간을 저장해서 계산해야 함
                        )

                        success = notifier.send_scheduler_heartbeat(
                            uptime, status["scheduled_jobs"]
                        )
                        if success:
                            print("[신호] 스케줄러 생존 신호 전송 완료")
                        else:
                            print("생존 신호 전송 실패")
                    else:
                        print("텔레그램 알림이 비활성화됨")

                except Exception as e:
                    print(f"생존 신호 전송 오류: {e}")
            elif args.heartbeat and not status["running"]:
                print("스케줄러가 실행 중이 아니므로 생존 신호를 전송할 수 없습니다")

        elif args.command == "run":
            scheduler.run_immediate_tasks()

    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        scheduler.stop_scheduler("사용자 중단 (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"스케줄러 실행 오류: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
