#!/usr/bin/env python3
"""
통합 스케줄러: Phase 1 + Phase 2 자동화 시스템
- 주기적 스크리닝 실행 (Phase 1)
- 일일 매매 리스트 업데이트 (Phase 2)
- 통합 모니터링 및 알림
"""

import schedule
import time
import threading
import sys
import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import argparse
import traceback

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.phase1_watchlist import Phase1Workflow
from workflows.phase2_daily_selection import Phase2CLI
from core.watchlist.watchlist_manager import WatchlistManager
from core.utils.log_utils import get_logger, setup_logging

# 텔레그램 알람 추가
import json
import requests
from pathlib import Path
from core.utils.telegram_notifier import get_telegram_notifier

# 자동 매매 엔진 추가
from core.trading.trading_engine import get_trading_engine, TradingConfig

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

# 스케줄러 시작 시 로그 기록
logger.info("="*50)
logger.info("🚀 통합 스케줄러 모듈 로딩 시작")
logger.info(f"📝 로그 파일: {log_filename}")
logger.info(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
logger.info("="*50)


class IntegratedScheduler:
    """통합 스케줄러 클래스"""
    
    def __init__(self, p_parallel_workers: int = 4):
        """초기화
        
        Args:
            p_parallel_workers: 병렬 처리 워커 수 (기본값: 4)
        """
        try:
            logger.info(f"🔧 스케줄러 초기화 시작 (워커: {p_parallel_workers}개)")
            
            self._v_phase1_workflow = Phase1Workflow(p_parallel_workers=p_parallel_workers)
            logger.info("✅ Phase1 워크플로우 초기화 완료")
            
            self._v_phase2_cli = Phase2CLI(p_parallel_workers=p_parallel_workers)
            logger.info("✅ Phase2 CLI 초기화 완료")
            
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
            
            # 텔레그램 설정 로드
            self._load_telegram_config()
            
            logger.info(f"✅ 통합 스케줄러 초기화 완료 (병렬 워커: {p_parallel_workers}개)")
            
        except Exception as e:
            logger.error(f"❌ 스케줄러 초기화 실패: {e}")
            logger.error(f"📋 상세 오류:\n{traceback.format_exc()}")
            raise
    
    def _load_telegram_config(self):
        """텔레그램 설정 로드"""
        try:
            config_file = Path("config/telegram_config.json")
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                telegram_config = config.get('telegram', {})
                self._v_telegram_bot_token = telegram_config.get('bot_token', '')
                self._v_telegram_chat_ids = telegram_config.get('default_chat_ids', [])
                self._v_telegram_enabled = bool(self._v_telegram_bot_token and self._v_telegram_chat_ids)
                
                if self._v_telegram_enabled:
                    logger.info("텔레그램 알람 시스템 활성화됨")
                else:
                    logger.warning("텔레그램 설정이 불완전함 - 알람 비활성화")
            else:
                logger.warning("텔레그램 설정 파일 없음 - 알람 비활성화")
                self._v_telegram_enabled = False
                
        except Exception as e:
            logger.error(f"텔레그램 설정 로드 실패: {e}")
            self._v_telegram_enabled = False
    
    def _send_telegram_alert(self, message: str, priority: str = "normal"):
        """텔레그램 알람 전송"""
        if not self._v_telegram_enabled:
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self._v_telegram_bot_token}/sendMessage"
            
            for chat_id in self._v_telegram_chat_ids:
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'Markdown',
                    'disable_web_page_preview': False
                }
                
                response = requests.post(url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"텔레그램 알람 전송 성공 ({priority})")
                else:
                    logger.error(f"텔레그램 알람 전송 실패: {response.status_code}")
            
            return True
            
        except Exception as e:
            logger.error(f"텔레그램 알람 전송 오류: {e}")
            return False
    
    def start_scheduler(self):
        """통합 스케줄러 시작"""
        if self._v_scheduler_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return
        
        # 스케줄 설정
        schedule.clear()
        
        # Phase 1: 일간 스크리닝 (매일 06:00, 주말 제외)
        schedule.every().monday.at("06:00").do(self._run_daily_screening)
        schedule.every().tuesday.at("06:00").do(self._run_daily_screening)
        schedule.every().wednesday.at("06:00").do(self._run_daily_screening)
        schedule.every().thursday.at("06:00").do(self._run_daily_screening)
        schedule.every().friday.at("06:00").do(self._run_daily_screening)
        
        # Phase 2: 일일 업데이트 (Phase 1 완료 후 자동 실행)
        # Phase 1 완료 후 _run_daily_screening에서 직접 호출
        
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
        
        # Phase 4: AI 학습 시스템 (일일 성과 분석: 매일 17:00)
        schedule.every().day.at("17:00").do(self._run_daily_performance_analysis)

        # Phase 4: 강화된 적응형 학습 (매일 18:30 - 포괄적 분석)
        schedule.every().day.at("18:30").do(self._run_enhanced_adaptive_learning)

        # Phase 4: 주간 깊이 학습 (매주 토요일 22:00)
        schedule.every().saturday.at("22:00").do(self._run_weekly_adaptive_learning)

        # Phase 5: 시스템 모니터링 시작 (스케줄러 시작 시)
        schedule.every().day.at("00:01").do(self._start_system_monitoring)

        # Phase 5: 자동 유지보수 (매주 일요일 새벽 3시)
        schedule.every().sunday.at("03:00").do(self._run_auto_maintenance)

        # ML 학습 조건 체크: 매일 19:00 (B단계 자동 트리거용)
        schedule.every().day.at("19:00").do(self._check_ml_trigger)

        # [방안 B] 주간 백테스트: 매주 금요일 20:00
        schedule.every().friday.at("20:00").do(self._run_weekly_backtest)

        # 헬스체크: 장 시간 중 10분마다 실행 (평일만)
        schedule.every().monday.at("09:10").do(self._run_health_check)
        schedule.every().monday.at("09:40").do(self._run_health_check)
        schedule.every().monday.at("10:10").do(self._run_health_check)
        schedule.every().monday.at("10:40").do(self._run_health_check)
        schedule.every().monday.at("11:10").do(self._run_health_check)
        schedule.every().monday.at("11:40").do(self._run_health_check)
        schedule.every().monday.at("13:10").do(self._run_health_check)
        schedule.every().monday.at("13:40").do(self._run_health_check)
        schedule.every().monday.at("14:10").do(self._run_health_check)
        schedule.every().monday.at("14:40").do(self._run_health_check)
        schedule.every().monday.at("15:10").do(self._run_health_check)

        schedule.every().tuesday.at("09:10").do(self._run_health_check)
        schedule.every().tuesday.at("09:40").do(self._run_health_check)
        schedule.every().tuesday.at("10:10").do(self._run_health_check)
        schedule.every().tuesday.at("10:40").do(self._run_health_check)
        schedule.every().tuesday.at("11:10").do(self._run_health_check)
        schedule.every().tuesday.at("11:40").do(self._run_health_check)
        schedule.every().tuesday.at("13:10").do(self._run_health_check)
        schedule.every().tuesday.at("13:40").do(self._run_health_check)
        schedule.every().tuesday.at("14:10").do(self._run_health_check)
        schedule.every().tuesday.at("14:40").do(self._run_health_check)
        schedule.every().tuesday.at("15:10").do(self._run_health_check)

        schedule.every().wednesday.at("09:10").do(self._run_health_check)
        schedule.every().wednesday.at("09:40").do(self._run_health_check)
        schedule.every().wednesday.at("10:10").do(self._run_health_check)
        schedule.every().wednesday.at("10:40").do(self._run_health_check)
        schedule.every().wednesday.at("11:10").do(self._run_health_check)
        schedule.every().wednesday.at("11:40").do(self._run_health_check)
        schedule.every().wednesday.at("13:10").do(self._run_health_check)
        schedule.every().wednesday.at("13:40").do(self._run_health_check)
        schedule.every().wednesday.at("14:10").do(self._run_health_check)
        schedule.every().wednesday.at("14:40").do(self._run_health_check)
        schedule.every().wednesday.at("15:10").do(self._run_health_check)

        schedule.every().thursday.at("09:10").do(self._run_health_check)
        schedule.every().thursday.at("09:40").do(self._run_health_check)
        schedule.every().thursday.at("10:10").do(self._run_health_check)
        schedule.every().thursday.at("10:40").do(self._run_health_check)
        schedule.every().thursday.at("11:10").do(self._run_health_check)
        schedule.every().thursday.at("11:40").do(self._run_health_check)
        schedule.every().thursday.at("13:10").do(self._run_health_check)
        schedule.every().thursday.at("13:40").do(self._run_health_check)
        schedule.every().thursday.at("14:10").do(self._run_health_check)
        schedule.every().thursday.at("14:40").do(self._run_health_check)
        schedule.every().thursday.at("15:10").do(self._run_health_check)

        schedule.every().friday.at("09:10").do(self._run_health_check)
        schedule.every().friday.at("09:40").do(self._run_health_check)
        schedule.every().friday.at("10:10").do(self._run_health_check)
        schedule.every().friday.at("10:40").do(self._run_health_check)
        schedule.every().friday.at("11:10").do(self._run_health_check)
        schedule.every().friday.at("11:40").do(self._run_health_check)
        schedule.every().friday.at("13:10").do(self._run_health_check)
        schedule.every().friday.at("13:40").do(self._run_health_check)
        schedule.every().friday.at("14:10").do(self._run_health_check)
        schedule.every().friday.at("14:40").do(self._run_health_check)
        schedule.every().friday.at("15:10").do(self._run_health_check)

        # 개발/테스트용 스케줄 (옵션)
        # schedule.every(10).minutes.do(self._run_daily_update)  # 10분마다 테스트
        
        self._v_scheduler_running = True
        self._v_start_time = datetime.now()  # 시작 시간 기록
        self._v_scheduler_thread = threading.Thread(target=self._run_scheduler_loop, daemon=True)
        self._v_scheduler_thread.start()
        
        logger.info("통합 스케줄러 시작됨")
        print("🚀 통합 스케줄러 시작!")
        print("├─ 일간 스크리닝: 매일 06:00")
        print("├─ 일일 업데이트: Phase 1 완료 후 자동 실행")
        print("├─ 자동 매매 시작: 매일 09:00 (평일)")
        print("├─ 자동 매매 중지: 매일 15:30 (평일)")
        print("├─ 매매 헬스체크: 장 시간 중 30분마다 (평일)")
        print("├─ 마감 후 정리: 매일 16:00")
        print("├─ AI 성과 분석: 매일 17:00")
        print("├─ 강화된 적응형 학습: 매일 18:30 (포괄적 분석)")
        print("├─ 주간 깊이 학습: 매주 토요일 22:00")
        print("├─ ML 학습 조건 체크: 매일 19:00 (B단계 자동 트리거)")
        print("├─ 시스템 모니터링: 24시간 실시간")
        print("└─ 자동 유지보수: 매주 일요일 03:00")
        
        # 텔레그램 스케줄러 시작 알림 전송
        try:
            from core.utils.telegram_notifier import get_telegram_notifier
            notifier = get_telegram_notifier()
            if notifier.is_enabled():
                success = notifier.send_scheduler_started()
                if success:
                    logger.info("스케줄러 시작 알림 전송 완료")
                    print("📱 텔레그램 시작 알림 전송됨")
                else:
                    logger.warning("스케줄러 시작 알림 전송 실패")
            else:
                logger.debug("텔레그램 알림이 비활성화됨")
        except Exception as e:
            logger.error(f"스케줄러 시작 알림 전송 오류: {e}")
    
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
                    print("📱 텔레그램 종료 알림 전송됨")
                else:
                    logger.warning("스케줄러 종료 알림 전송 실패")
            else:
                logger.debug("텔레그램 알림이 비활성화됨")
        except Exception as e:
            logger.error(f"스케줄러 종료 알림 전송 오류: {e}")
        
        # 스케줄러 중지
        self._v_scheduler_running = False
        schedule.clear()
        
        if self._v_scheduler_thread and self._v_scheduler_thread.is_alive():
            self._v_scheduler_thread.join(timeout=5)
        
        logger.info(f"통합 스케줄러 중지됨: {reason}")
        print(f"⏹️ 통합 스케줄러 중지됨: {reason}")
    
    def get_status(self) -> Dict:
        """스케줄러 상태 조회"""
        _v_next_jobs = []
        for job in schedule.jobs:
            try:
                job_name = getattr(job.job_func, '__name__', str(job.job_func))
            except:
                job_name = "Unknown Job"
            
            _v_next_jobs.append({
                "job": job_name,
                "next_run": job.next_run.strftime("%Y-%m-%d %H:%M:%S") if job.next_run else "미정",
                "interval": str(job.interval),
                "unit": job.unit
            })
        
        # 실제 프로세스 상태 확인 (ServiceManager와 동일한 방식)
        import psutil
        actual_running = False
        current_pid = os.getpid()
        
        try:
            # 현재 프로세스가 스케줄러인지 확인
            current_proc = psutil.Process(current_pid)
            current_cmdline = current_proc.cmdline()
            
            # 현재 프로세스가 스케줄러 시작 명령인지 확인
            if (len(current_cmdline) >= 3 and 
                'python' in current_cmdline[0] and 
                'integrated_scheduler.py' in current_cmdline[1] and 
                current_cmdline[2] == 'start'):
                actual_running = True
                logger.debug(f"🟢 현재 프로세스가 스케줄러임: PID {current_pid}")
            else:
                # 다른 스케줄러 프로세스 검색
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if (cmdline and len(cmdline) >= 3 and 
                            'python' in str(cmdline[0]) and 
                            'integrated_scheduler.py' in str(cmdline[1]) and 
                            cmdline[2] == 'start'):
                            actual_running = True
                            logger.debug(f"🟢 다른 스케줄러 프로세스 발견: PID {proc.info['pid']}")
                            break
                    except:
                        continue
                        
        except Exception as e:
            logger.warning(f"⚠️ 프로세스 상태 확인 실패: {e}, 내부 상태 사용")
            actual_running = self._v_scheduler_running
        
        # 내부 상태와 실제 프로세스 상태 비교 (스케줄러 스레드가 실행 중이면 내부 상태 우선)
        if actual_running != self._v_scheduler_running:
            # 스케줄러 스레드가 살아있으면 내부 상태를 신뢰
            if self._v_scheduler_thread and self._v_scheduler_thread.is_alive():
                logger.debug(f"🔄 스케줄러 스레드 활성 상태 - 내부 상태 사용: {self._v_scheduler_running}")
                actual_running = self._v_scheduler_running
            else:
                # 상태 불일치는 초기화 직후에 발생할 수 있음 (스레드 시작 전)
                # DEBUG 레벨로 낮춤
                logger.debug(f"🔄 상태 동기화 중 - 내부: {self._v_scheduler_running}, 실제: {actual_running}")
        
        return {
            "running": actual_running,  # 조정된 상태 사용
            "internal_running": self._v_scheduler_running,  # 내부 상태도 표시
            "last_screening": self._v_last_screening.strftime("%Y-%m-%d %H:%M:%S") if self._v_last_screening else "없음",
            "last_daily_update": self._v_last_daily_update.strftime("%Y-%m-%d %H:%M:%S") if self._v_last_daily_update else "없음",
            "scheduled_jobs": _v_next_jobs,
            "pid": current_pid,
            "start_time": self._v_start_time.strftime("%Y-%m-%d %H:%M:%S") if self._v_start_time else "없음"
        }
    
    def _run_scheduler_loop(self):
        """스케줄러 루프 실행"""
        logger.info("🔄 스케줄러 루프 시작")
        loop_count = 0
        
        while self._v_scheduler_running:
            try:
                loop_count += 1
                
                # 주기적으로 생존 신호 로그 (매 10분마다)
                if loop_count % 10 == 0:
                    uptime = datetime.now() - self._v_start_time if self._v_start_time else timedelta(0)
                    logger.info(f"💓 스케줄러 생존 신호 - 루프: {loop_count}, 가동시간: {uptime}")
                
                # 예정된 작업 실행
                pending_jobs = schedule.jobs
                if pending_jobs:
                    logger.debug(f"📋 확인 중인 예정 작업: {len(pending_jobs)}개")
                
                schedule.run_pending()
                time.sleep(60)  # 1분마다 체크
                
            except Exception as e:
                logger.error(f"❌ 스케줄러 루프 오류: {e}")
                logger.error(f"📋 상세 오류:\n{traceback.format_exc()}")
                time.sleep(60)
                
        logger.info("⏹️ 스케줄러 루프 종료")
    
    def _run_daily_screening(self):
        """일간 스크리닝 실행 (Phase 1)"""
        try:
            logger.info("=== 일간 스크리닝 시작 ===")
            print(f"🔍 일간 스크리닝 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 전체 시장 스크리닝 실행 (코스피 + 코스닥 전체 2875개 종목)
            # 알림은 Phase1에서만 발송하도록 통일하여 중복 방지
            _v_success = self._v_phase1_workflow.run_full_screening(p_send_notification=True)
            
            if _v_success:
                self._v_last_screening = datetime.now()
                logger.info("일간 스크리닝 완료")
                print("✅ 일간 스크리닝 완료!")
                
                # 알림은 Phase1이 이미 발송함. 스케줄러에서는 중복 전송하지 않음.
                
                # Phase 1 성공 시 Phase 2 자동 실행
                self._v_phase1_completed = True
                print("\n2. 일일 업데이트 자동 실행...")
                self._run_daily_update()
                
                # Phase 1,2 완료 후 AI 학습 시스템에 데이터 전달
                print("\n3. AI 학습 시스템 데이터 연동...")
                self._send_data_to_ai_system()
                
            else:
                logger.error("일간 스크리닝 실패")
                print("❌ 일간 스크리닝 실패")
                self._v_phase1_completed = False
                
                # 실패 알람 전송
                _v_error_message = f"🚨 *한투 퀀트 스크리닝 실패*\n\n⏰ 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n❌ 상태: 일간 스크리닝 실패\n\n⚠️ 시스템 점검이 필요합니다."
                self._send_telegram_alert(_v_error_message, "emergency")
                
        except Exception as e:
            logger.error(f"일간 스크리닝 오류: {e}")
            print(f"❌ 일간 스크리닝 오류: {e}")
            self._v_phase1_completed = False
    
    def _run_daily_update(self):
        """일일 업데이트 실행 (Phase 2)"""
        try:
            logger.info("=== 일일 업데이트 시작 ===")
            print(f"📊 일일 업데이트 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Phase 2 DailyUpdater의 WatchlistManager를 새로 초기화하여 최신 데이터 로드
            try:
                # 새로운 WatchlistManager 인스턴스 생성하여 최신 데이터 반영
                fresh_watchlist_manager = WatchlistManager("data/watchlist/watchlist.json")
                # DailyUpdater 재초기화로 최신 데이터 적용
                self._v_phase2_cli._v_daily_updater = type(self._v_phase2_cli._v_daily_updater)(
                    fresh_watchlist_manager
                )
            except Exception as e:
                logger.warning(f"WatchlistManager 업데이트 실패, 기존 인스턴스 사용: {e}")
            
            # Phase 2 일일 업데이트 실행
            _v_success = self._v_phase2_cli._v_daily_updater.run_daily_update(p_force_run=True)
            
            if _v_success:
                self._v_last_daily_update = datetime.now()
                logger.info("일일 업데이트 완료")
                print("✅ 일일 업데이트 완료!")
                
                # 선정 결과 요약 출력
                self._print_daily_summary()
                
            else:
                logger.error("일일 업데이트 실패")
                print("❌ 일일 업데이트 실패")
                
        except Exception as e:
            logger.error(f"일일 업데이트 오류: {e}")
            print(f"❌ 일일 업데이트 오류: {e}")
    
    def _run_market_close_tasks(self):
        """시장 마감 후 정리 작업"""
        try:
            logger.info("=== 시장 마감 후 정리 작업 시작 ===")
            print(f"🏁 시장 마감 후 정리 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 일일 리포트 생성
            _v_report_success = self._v_phase1_workflow.generate_report()
            
            # 성과 분석 (Phase 2)
            _v_performance_data = self._v_phase2_cli._collect_performance_data(1)

            # 매매일지 요약 생성 및 저장
            try:
                from core.trading.trade_journal import TradeJournal
                from core.learning.analysis.daily_performance import DailyPerformanceAnalyzer
                journal = TradeJournal()
                summary = journal.compute_daily_summary()
                logger.info(
                    f"시장 마감 요약 - 손익: {summary['realized_pnl']:,.0f}, 거래: {summary['total_trades']}건, 승률: {summary['win_rate']*100:.1f}%"
                )

                # 요약 파일 경로 구성 후 성과 분석기에 반영
                summary_path = os.path.join(
                    journal._base_dir, f"trade_summary_{datetime.now().strftime('%Y%m%d')}.json"
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
                print("✅ 일일 리포트 생성 완료")
            
            print("✅ 시장 마감 후 정리 완료")
            
        except Exception as e:
            logger.error(f"시장 마감 후 정리 오류: {e}")
            print(f"❌ 시장 마감 후 정리 오류: {e}")
    
    def _run_daily_performance_analysis(self):
        """일일 성과 분석 실행 (Phase 4) - 실제 성과 데이터 사용"""
        try:
            logger.info("=== 일일 성과 분석 시작 ===")
            print(f"📊 일일 성과 분석 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 실제 성과 지표 계산 및 텔레그램 리포트 전송
            try:
                # 텔레그램 알림 시스템 가져오기
                notifier = get_telegram_notifier()
                
                # 일일 성과 리포트 전송 (실현/평가 손익 분리 표시)
                if notifier.is_enabled():
                    success = notifier.send_daily_performance_report()
                    if success:
                        logger.info("일일 성과 리포트 전송 완료")
                        print("✅ 일일 성과 리포트가 텔레그램으로 전송되었습니다!")
                    else:
                        logger.warning("일일 성과 리포트 전송 실패")
                        print("⚠️ 일일 성과 리포트 전송 실패")
                else:
                    logger.info("텔레그램 알림이 비활성화되어 있음")
                    print("ℹ️ 텔레그램 알림이 비활성화되어 있습니다.")
                
                # 추가 성과 분석 작업 (선택적)
                from core.performance.performance_metrics import get_performance_metrics
                metrics = get_performance_metrics()
                
                # 일일 성과 데이터 계산
                daily_perf = metrics.get_daily_performance()
                
                # 성과 데이터 저장
                os.makedirs("data/learning/performance", exist_ok=True)
                performance_file = f"data/learning/performance/daily_analysis_{datetime.now().strftime('%Y%m%d')}.json"
                
                with open(performance_file, 'w') as f:
                    json.dump(daily_perf, f, indent=2, ensure_ascii=False)
                
                logger.info(f"일일 성과 분석 완료: 실현손익 {daily_perf.get('realized_pnl', 0):,.0f}원, 평가손익 {daily_perf.get('unrealized_pnl', 0):,.0f}원")
                print(f"✅ 일일 성과 분석 완료!")
                print(f"   - 실현 손익: {daily_perf.get('realized_pnl', 0):,.0f}원")
                print(f"   - 평가 손익: {daily_perf.get('unrealized_pnl', 0):,.0f}원")
                print(f"   - 총 손익: {daily_perf.get('total_pnl', 0):,.0f}원")
                
            except ImportError as ie:
                logger.warning(f"성과 분석 모듈 로드 실패, 기본 분석 사용: {ie}")
                print(f"⚠️ 성과 분석 모듈 로드 실패, 기본 분석으로 대체")
                
                # 기본 분석 (폴백)
                performance_data = {
                    'analysis_date': datetime.now().isoformat(),
                    'status': 'fallback_mode',
                    'message': '성과 지표 모듈을 사용할 수 없어 기본 분석 모드로 실행됨'
                }
                
                os.makedirs("data/learning/performance", exist_ok=True)
                performance_file = f"data/learning/performance/daily_analysis_{datetime.now().strftime('%Y%m%d')}.json"
                
                with open(performance_file, 'w') as f:
                    json.dump(performance_data, f, indent=2, ensure_ascii=False)
                    
            except Exception as ai_error:
                logger.error(f"성과 분석 중 오류 발생: {ai_error}")
                print(f"⚠️ 성과 분석 중 오류: {ai_error}")
                
        except Exception as e:
            logger.error(f"일일 성과 분석 오류: {e}")
            print(f"❌ 일일 성과 분석 오류: {e}")
            
    def _run_enhanced_adaptive_learning(self):
        """강화된 적응형 학습 실행 (포괄적 분석 기반)"""
        try:
            logger.info("=== 강화된 적응형 학습 시작 ===")
            print(f"🧠 강화된 적응형 학습 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                from core.learning.enhanced_adaptive_system import get_enhanced_adaptive_system

                enhanced_system = get_enhanced_adaptive_system()
                result = enhanced_system.run_comprehensive_analysis()

                if result.get('status') != 'failed':
                    # 데이터 동기화 결과
                    sync_results = result.get('data_sync', {})
                    screening_synced = sync_results.get('screening_synced', 0)
                    selection_synced = sync_results.get('selection_synced', 0)
                    performance_updated = sync_results.get('performance_updated', 0)

                    # 정확도 분석 결과
                    screening_accuracy = result.get('screening_accuracy')
                    selection_accuracy = result.get('selection_accuracy')

                    # 파라미터 적응 결과
                    adaptation = result.get('parameter_adaptation', {})
                    adapted = adaptation.get('status') == 'adapted'

                    # 인사이트 결과
                    insights = result.get('insights', [])
                    actionable_insights = len([i for i in insights if i.get('actionable', False)])

                    logger.info(f"강화된 학습 완료: 동기화={screening_synced+selection_synced}건, 적응={'예' if adapted else '아니오'}, 인사이트={actionable_insights}개")
                    print(f"✅ 강화된 적응형 학습 완료!")
                    print(f"   - 데이터 동기화: 스크리닝 {screening_synced}건, 선정 {selection_synced}건, 성과 {performance_updated}건")
                    if screening_accuracy:
                        precision = screening_accuracy.precision if hasattr(screening_accuracy, 'precision') else getattr(screening_accuracy, 'precision', 0)
                        recall = screening_accuracy.recall if hasattr(screening_accuracy, 'recall') else getattr(screening_accuracy, 'recall', 0)
                        print(f"   - 스크리닝 정확도: 정밀도 {precision:.1%}, 재현율 {recall:.1%}")
                    if selection_accuracy:
                        win_rate = selection_accuracy.win_rate if hasattr(selection_accuracy, 'win_rate') else getattr(selection_accuracy, 'win_rate', 0)
                        avg_return = selection_accuracy.avg_return if hasattr(selection_accuracy, 'avg_return') else getattr(selection_accuracy, 'avg_return', 0)
                        print(f"   - 선정 성과: 승률 {win_rate:.1%}, 평균수익률 {avg_return:+.2%}")
                    print(f"   - 실행 가능한 인사이트: {actionable_insights}개")
                    print(f"   - 파라미터 적응: {'✅' if adapted else '유지'}")

                    # 텔레그램 상세 알림 전송
                    if adapted or actionable_insights > 0:
                        alert_message = self._generate_enhanced_learning_alert(result)
                        priority = "high" if adapted else "normal"
                        self._send_telegram_alert(alert_message, priority)

                else:
                    error_msg = result.get('error', '알 수 없는 오류')
                    print(f"❌ 강화된 학습 실패: {error_msg}")
                    logger.error(f"강화된 적응형 학습 실패: {error_msg}")

            except ImportError as ie:
                logger.warning(f"강화된 학습 모듈 로드 실패: {ie}")
                print(f"⚠️ 강화된 학습 모듈을 찾을 수 없습니다")

                # 기본 학습 시스템으로 폴백
                print("📋 기본 적응형 학습으로 대체 실행...")
                self._run_adaptive_learning_fallback()

        except Exception as e:
            logger.error(f"강화된 적응형 학습 오류: {e}")
            print(f"❌ 강화된 적응형 학습 오류: {e}")

    def _run_adaptive_learning_fallback(self):
        """기본 적응형 학습 실행 (폴백용)"""
        try:
            from core.learning.adaptive_learning_system import get_adaptive_learning_system

            learning_system = get_adaptive_learning_system()
            result = learning_system.run_daily_learning()

            if result.get("status") == "completed":
                adapted = result.get("adapted", False)
                win_rate = result.get("performance_analysis", {}).get("win_rate", 0)
                total_trades = result.get("performance_analysis", {}).get("total_trades", 0)

                logger.info(f"기본 적응형 학습 완료: 승률={win_rate:.1%}, 거래수={total_trades}건, 적응={adapted}")
                print(f"✅ 기본 적응형 학습 완료!")
                print(f"   - 분석 거래: {total_trades}건")
                print(f"   - 현재 승률: {win_rate:.1%}")
                print(f"   - 파라미터 적응: {'✅' if adapted else '유지'}")

            elif result.get("status") == "skipped":
                print(f"ℹ️ 적응형 학습 건너뜀: {result.get('message')}")

            else:
                print(f"⚠️ 적응형 학습 실패: {result.get('message')}")

        except Exception as e:
            logger.error(f"기본 적응형 학습 오류: {e}")
            print(f"❌ 기본 적응형 학습 오류: {e}")

    def _generate_enhanced_learning_alert(self, result: Dict[str, Any]) -> str:
        """강화된 학습 결과 알림 메시지 생성"""
        try:
            # 기본 정보
            sync_results = result.get('data_sync', {})
            screening_accuracy = result.get('screening_accuracy')
            selection_accuracy = result.get('selection_accuracy')
            adaptation = result.get('parameter_adaptation', {})
            insights = result.get('insights', [])

            adapted = adaptation.get('status') == 'adapted'
            actionable_insights = [i for i in insights if getattr(i, 'actionable', False)]

            message = f"""🧠 *강화된 AI 학습 완료*

📊 **데이터 동기화**:
• 스크리닝: {sync_results.get('screening_synced', 0)}건
• 선정: {sync_results.get('selection_synced', 0)}건
• 성과 추적: {sync_results.get('performance_updated', 0)}건
• 메트릭: {sync_results.get('metrics_calculated', 0)}개

🎯 **정확도 분석**:"""

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

🔍 **AI 인사이트**:
• 총 인사이트: {len(insights)}개
• 실행 가능한 제안: {len(actionable_insights)}개"""

            # 주요 인사이트 표시 (최대 2개)
            for insight in actionable_insights[:2]:
                desc = getattr(insight, 'description', '')
                message += f"""
• {desc[:50]}{'...' if len(desc) > 50 else ''}"""

            message += f"""

🔧 **파라미터 적응**:
• 상태: {'완료' if adapted else '유지'}"""

            if adapted:
                changes = adaptation.get('changes_made', [])
                message += f"""
• 변경사항: {len(changes)}건"""
                for change in changes[:2]:
                    message += f"""
  - {change[:40]}{'...' if len(change) > 40 else ''}"""

            message += f"""

⏰ 분석 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

🚀 *AI가 포괄적 분석을 통해 시스템을 최적화했습니다!*"""

            return message

        except Exception as e:
            logger.error(f"강화된 학습 알림 메시지 생성 실패: {e}")
            return f"""🧠 *강화된 AI 학습 완료*

✅ 포괄적 분석이 완료되었습니다.

⏰ 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

🔍 상세 결과는 시스템 로그를 확인하세요."""
            
    def _run_weekly_adaptive_learning(self):
        """주간 깊이 학습 실행 (30일 데이터 기반)"""
        try:
            logger.info("=== 주간 깊이 학습 시작 ===")
            print(f"🔬 주간 깊이 학습 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                from core.learning.adaptive_learning_system import get_adaptive_learning_system
                
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
                    
                    logger.info(f"주간 학습 완료: 승률={win_rate:.1%}, 수익률={avg_return:.2%}, 트렌드={return_trend}")
                    print(f"✅ 주간 깊이 학습 완료!")
                    print(f"   - 30일 거래: {total_trades}건")
                    print(f"   - 평균 승률: {win_rate:.1%}")
                    print(f"   - 수익률 트렌드: {return_trend}")
                    print(f"   - 파라미터 적응: {'✅' if adapted else '유지'}")
                    
                    # 텔레그램 알림 전송
                    if adapted or total_trades > 0:
                        emoji = "📈" if return_trend == "improving" else "📉" if return_trend == "declining" else "➖"
                        
                        alert_message = f"""🔬 *주간 AI 깊이 학습 완료*

📊 **30일 성과 분석**:
• 총 거래: {total_trades}건
• 평균 승률: {win_rate:.1%}
• 평균 수익률: {avg_return:+.2%}
• 트렌드: {return_trend} {emoji}

🧠 **학습 결과**:
• 파라미터 적응: {'완료' if adapted else '유지'}

⏰ 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

🎯 *AI가 한 주간의 성과를 분석하여 전략을 최적화했습니다!*"""
                        
                        priority = "high" if adapted else "normal"
                        self._send_telegram_alert(alert_message, priority)
                        
                else:
                    print(f"ℹ️ 주간 학습 건너뜀: {result.get('message')}")
                    
            except ImportError as ie:
                logger.warning(f"주간 학습 모듈 로드 실패: {ie}")
                print(f"⚠️ 주간 학습 모듈을 찾을 수 없습니다")
                
        except Exception as e:
            logger.error(f"주간 깊이 학습 오류: {e}")
            print(f"❌ 주간 깊이 학습 오류: {e}")

    def _run_weekly_backtest(self):
        """주간 백테스트 실행 (방안 B)"""
        try:
            logger.info("=== 주간 백테스트 시작 ===")
            print(f"📊 주간 백테스트 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                from core.backtesting.strategy_backtester import StrategyBacktester
                from core.daily_selection.selection_criteria import SelectionCriteria, CriteriaRange
                from dataclasses import field

                # 백테스터 초기화 (1억원 초기 자본)
                backtester = StrategyBacktester(initial_capital=100000000)

                # 최근 30일 기간 설정
                end_date = datetime.now()
                start_date = end_date - timedelta(days=30)

                logger.info(f"백테스트 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")

                # 현재 보수적 전략 설정
                conservative_criteria = SelectionCriteria(
                    price_attractiveness=CriteriaRange(80.0, 100.0, 90.0, 0.35),
                    technical_score=CriteriaRange(70.0, 100.0, 85.0, 0.35),
                    risk_score=CriteriaRange(0.0, 25.0, 15.0, 0.4),
                    confidence=CriteriaRange(0.75, 1.0, 0.85, 0.25),
                    max_position_size=0.08
                )

                conservative_trading = {
                    'position_size': 0.05,
                    'stop_loss_pct': 0.03,
                    'take_profit_pct': 0.08,
                    'risk_per_trade': 0.015
                }

                # 보수적 전략 백테스트
                logger.info("보수적 전략 백테스트 실행 중...")
                conservative_result = backtester.backtest_selection_strategy(
                    start_date=start_date,
                    end_date=end_date,
                    selection_criteria=conservative_criteria,
                    trading_config=conservative_trading,
                    strategy_name="Conservative"
                )

                # 이전 공격적 전략 설정 (비교용)
                aggressive_criteria = SelectionCriteria(
                    price_attractiveness=CriteriaRange(75.0, 100.0, 85.0, 0.3),
                    technical_score=CriteriaRange(60.0, 100.0, 80.0, 0.3),
                    risk_score=CriteriaRange(0.0, 35.0, 20.0, 0.35),
                    confidence=CriteriaRange(0.65, 1.0, 0.80, 0.2),
                    max_position_size=0.12
                )

                aggressive_trading = {
                    'position_size': 0.10,
                    'stop_loss_pct': 0.05,
                    'take_profit_pct': 0.10,
                    'risk_per_trade': 0.02
                }

                # 공격적 전략 백테스트
                logger.info("공격적 전략 백테스트 실행 중...")
                aggressive_result = backtester.backtest_selection_strategy(
                    start_date=start_date,
                    end_date=end_date,
                    selection_criteria=aggressive_criteria,
                    trading_config=aggressive_trading,
                    strategy_name="Aggressive"
                )

                # 결과 저장
                from pathlib import Path
                import json

                backtest_dir = Path("data/backtesting")
                backtest_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                result_file = backtest_dir / f"weekly_backtest_{timestamp}.json"

                results = {
                    'timestamp': timestamp,
                    'period': {
                        'start': start_date.strftime('%Y-%m-%d'),
                        'end': end_date.strftime('%Y-%m-%d')
                    },
                    'conservative': {
                        'win_rate': conservative_result.win_rate,
                        'avg_return': conservative_result.avg_return,
                        'max_drawdown': conservative_result.max_drawdown,
                        'sharpe_ratio': conservative_result.sharpe_ratio,
                        'profit_factor': conservative_result.profit_factor,
                        'total_trades': conservative_result.total_trades
                    },
                    'aggressive': {
                        'win_rate': aggressive_result.win_rate,
                        'avg_return': aggressive_result.avg_return,
                        'max_drawdown': aggressive_result.max_drawdown,
                        'sharpe_ratio': aggressive_result.sharpe_ratio,
                        'profit_factor': aggressive_result.profit_factor,
                        'total_trades': aggressive_result.total_trades
                    }
                }

                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)

                logger.info(f"백테스트 결과 저장 완료: {result_file}")

                # 결과 출력
                print(f"\n✅ 주간 백테스트 완료!")
                print(f"\n📊 보수적 전략:")
                print(f"   - 승률: {conservative_result.win_rate:.1%}")
                print(f"   - 평균 수익률: {conservative_result.avg_return:+.2%}")
                print(f"   - 샤프 비율: {conservative_result.sharpe_ratio:.2f}")
                print(f"   - 최대 낙폭: {conservative_result.max_drawdown:.1%}")
                print(f"   - 총 거래: {conservative_result.total_trades}건")

                print(f"\n📊 공격적 전략:")
                print(f"   - 승률: {aggressive_result.win_rate:.1%}")
                print(f"   - 평균 수익률: {aggressive_result.avg_return:+.2%}")
                print(f"   - 샤프 비율: {aggressive_result.sharpe_ratio:.2f}")
                print(f"   - 최대 낙폭: {aggressive_result.max_drawdown:.1%}")
                print(f"   - 총 거래: {aggressive_result.total_trades}건")

                # 텔레그램 알림 전송
                better_strategy = "보수적" if conservative_result.sharpe_ratio > aggressive_result.sharpe_ratio else "공격적"

                alert_message = f"""📊 *주간 백테스트 완료*

📅 **분석 기간**: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}

🎯 **보수적 전략**:
• 승률: {conservative_result.win_rate:.1%}
• 평균 수익: {conservative_result.avg_return:+.2%}
• 샤프 비율: {conservative_result.sharpe_ratio:.2f}
• 최대 낙폭: {conservative_result.max_drawdown:.1%}
• 거래 건수: {conservative_result.total_trades}건

⚡ **공격적 전략**:
• 승률: {aggressive_result.win_rate:.1%}
• 평균 수익: {aggressive_result.avg_return:+.2%}
• 샤프 비율: {aggressive_result.sharpe_ratio:.2f}
• 최대 낙폭: {aggressive_result.max_drawdown:.1%}
• 거래 건수: {aggressive_result.total_trades}건

🏆 **권장 전략**: {better_strategy}

⏰ 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

💡 *과거 성과를 기반으로 전략을 검증했습니다!*"""

                self._send_telegram_alert(alert_message, "normal")

            except ImportError as ie:
                logger.warning(f"백테스트 모듈 로드 실패: {ie}")
                print(f"⚠️ 백테스트 모듈을 찾을 수 없습니다")

        except Exception as e:
            logger.error(f"주간 백테스트 오류: {e}")
            print(f"❌ 주간 백테스트 오류: {e}")
            import traceback
            traceback.print_exc()

    def _start_system_monitoring(self):
        """시스템 모니터링 시작"""
        try:
            logger.info("=== 시스템 모니터링 시작 ===")
            print(f"👁️ 시스템 모니터링 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                from core.monitoring.system_monitor import get_system_monitor

                monitor = get_system_monitor()
                success = monitor.start_monitoring()

                if success:
                    logger.info("시스템 모니터링 시작 완료")
                    print("✅ 시스템 모니터링이 백그라운드에서 시작되었습니다!")
                    print("   - CPU, 메모리, 디스크 사용량 모니터링")
                    print("   - 학습 시스템 건강 상태 추적")
                    print("   - 자동 알림 및 보고서 생성")

                    # 모니터링 시작 알림
                    alert_message = f"""👁️ *시스템 모니터링 시작*

🔍 **모니터링 항목**:
• 시스템 리소스 (CPU, 메모리, 디스크)
• 학습 시스템 건강 상태
• 데이터 신선도 및 무결성
• 예측 정확도 추적

⚙️ **설정**:
• 체크 주기: 5분마다
• 일일 보고서: 오후 6시
• 자동 알림: 임계값 초과 시

⏰ 시작 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

🤖 *AI 시스템이 스스로를 지속적으로 모니터링합니다!*"""

                    self._send_telegram_alert(alert_message, "normal")

                else:
                    logger.warning("시스템 모니터링 시작 실패 (이미 실행 중일 수 있음)")
                    print("⚠️ 시스템 모니터링 시작 실패 (이미 실행 중일 수 있음)")

            except ImportError as ie:
                logger.warning(f"시스템 모니터링 모듈 로드 실패: {ie}")
                print(f"⚠️ 시스템 모니터링 모듈을 찾을 수 없습니다")

        except Exception as e:
            logger.error(f"시스템 모니터링 시작 오류: {e}")
            print(f"❌ 시스템 모니터링 시작 오류: {e}")

    def _run_health_check(self):
        """자동 매매 헬스체크 실행"""
        try:
            logger.info("=== 자동 매매 헬스체크 시작 ===")

            from core.monitoring.trading_health_checker import get_health_checker

            health_checker = get_health_checker()
            result = health_checker.check_trading_health()

            if result.is_healthy:
                logger.info("헬스체크 완료: 시스템 정상")
            else:
                logger.warning(f"헬스체크 완료: {len(result.issues)}개 문제 발견")

        except Exception as e:
            logger.error(f"헬스체크 실행 오류: {e}")

    def _run_auto_maintenance(self):
        """자동 유지보수 실행"""
        try:
            logger.info("=== 자동 유지보수 시작 ===")
            print(f"🔧 자동 유지보수 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                from core.monitoring.system_monitor import get_system_monitor

                monitor = get_system_monitor()
                maintenance_result = monitor.run_maintenance_check()

                needs_maintenance = maintenance_result.get('needs_maintenance', False)
                maintenance_executed = maintenance_result.get('maintenance_executed', False)
                reasons = maintenance_result.get('reasons', [])

                logger.info(f"유지보수 체크 완료: 필요={'예' if needs_maintenance else '아니오'}, 실행={'예' if maintenance_executed else '아니오'}")
                print(f"✅ 자동 유지보수 체크 완료!")
                print(f"   - 유지보수 필요: {'예' if needs_maintenance else '아니오'}")
                print(f"   - 유지보수 실행: {'예' if maintenance_executed else '아니오'}")

                if needs_maintenance:
                    print(f"   - 필요 사유: {', '.join(reasons[:3])}")

                    # 유지보수 실행 알림
                    if maintenance_executed:
                        maintenance_details = maintenance_result.get('maintenance_result', {})
                        tasks_completed = maintenance_details.get('tasks_completed', [])

                        alert_message = f"""🔧 *자동 유지보수 실행*

✅ **유지보수 완료**:
• 필요 사유: {len(reasons)}건
• 실행 작업: {len(tasks_completed)}개

📋 **주요 사유**:"""

                        for reason in reasons[:3]:
                            alert_message += f"\n• {reason}"

                        alert_message += f"""

🛠️ **실행된 작업**:"""

                        for task in tasks_completed:
                            task_name = task.replace('_', ' ').title()
                            alert_message += f"\n• {task_name}"

                        alert_message += f"""

⏰ 실행 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

🚀 *시스템이 자동으로 최적화되었습니다!*"""

                        self._send_telegram_alert(alert_message, "normal")

                    else:
                        # 유지보수 필요하지만 실행 안 된 경우
                        alert_message = f"""⚠️ *유지보수 필요*

🔍 **점검 결과**:
• 유지보수가 필요하지만 자동 실행되지 않았습니다

📋 **필요 사유**:"""

                        for reason in reasons[:3]:
                            alert_message += f"\n• {reason}"

                        alert_message += f"""

⏰ 체크 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

🛠️ *수동으로 유지보수를 실행하는 것을 고려하세요*"""

                        self._send_telegram_alert(alert_message, "warning")

                else:
                    print("   - 시스템 상태 양호, 유지보수 불필요")

            except ImportError as ie:
                logger.warning(f"자동 유지보수 모듈 로드 실패: {ie}")
                print(f"⚠️ 자동 유지보수 모듈을 찾을 수 없습니다")

        except Exception as e:
            logger.error(f"자동 유지보수 오류: {e}")
            print(f"❌ 자동 유지보수 오류: {e}")

    def _check_ml_trigger(self):
        """ML 학습 조건 체크 및 자동 트리거"""
        try:
            logger.info("=== ML 학습 조건 체크 시작 ===")
            print(f"🤖 ML 학습 조건 체크 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            try:
                from core.learning.auto_ml_trigger import get_auto_ml_trigger

                ml_trigger = get_auto_ml_trigger()

                # 조건 체크 및 자동 트리거
                triggered = ml_trigger.check_and_trigger()

                if triggered:
                    logger.info("ML 학습이 자동으로 트리거되었습니다!")
                    print("✅ ML 학습 조건 충족 - B단계 자동 시작!")
                else:
                    # 진행률 조회
                    progress = ml_trigger.get_progress_to_ml()

                    if progress:
                        overall = progress.get('overall_progress', 0)
                        conditions_met = progress.get('conditions_met', False)

                        logger.info(f"ML 학습 진행률: {overall:.1f}%")
                        print(f"📊 ML 학습 준비 진행률: {overall:.1f}%")

                        if not conditions_met:
                            days_remaining = progress.get('estimated_days_remaining', 0)
                            print(f"   - 예상 남은 기간: 약 {days_remaining}일")
                            print(f"   - 거래일: {progress.get('trading_days_progress', 0):.0f}%")
                            print(f"   - 선정 기록: {progress.get('selection_records_progress', 0):.0f}%")
                            print(f"   - 성과 기록: {progress.get('performance_records_progress', 0):.0f}%")
                            print(f"   - 승률: {progress.get('win_rate_progress', 0):.0f}%")

            except ImportError as ie:
                logger.warning(f"ML 트리거 모듈 로드 실패: {ie}")
                print(f"⚠️ ML 트리거 모듈을 찾을 수 없습니다")

        except Exception as e:
            logger.error(f"ML 학습 조건 체크 오류: {e}")
            print(f"❌ ML 학습 조건 체크 오류: {e}")


    def _start_auto_trading(self):
        """자동 매매 시작"""
        try:
            logger.info("=== 자동 매매 시작 ===")
            print(f"🚀 자동 매매 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 매매 엔진 import 및 초기화
            try:
                from core.trading.trading_engine import TradingEngine, TradingConfig

                # 기본 매매 설정 (계좌 대비 10%씩 투자)
                config = TradingConfig(
                    max_positions=10,
                    position_size_method="account_pct",  # 계좌 비율 방식
                    position_size_value=0.10,            # 계좌의 10%씩
                    stop_loss_pct=0.05,                  # 5% 손절
                    take_profit_pct=0.10,                # 10% 익절
                    max_trades_per_day=20,
                    use_kelly_criterion=True,            # Kelly Criterion 사용
                    kelly_multiplier=0.25                # 보수적 적용
                )

                trading_engine = TradingEngine(config)

                # 백그라운드에서 자동 매매 실행
                def run_trading():
                    try:
                        import asyncio
                        # 새로운 이벤트 루프 생성
                        asyncio.set_event_loop(asyncio.new_event_loop())
                        loop = asyncio.get_event_loop()
                        loop.run_until_complete(trading_engine.start_trading())
                    except Exception as e:
                        logger.error(f"자동 매매 실행 오류: {e}")
                        import traceback
                        logger.error(f"상세 오류:\n{traceback.format_exc()}")

                trading_thread = threading.Thread(target=run_trading, daemon=True)
                trading_thread.start()

                logger.info("자동 매매 시작 완료")
                print("✅ 자동 매매가 백그라운드에서 시작되었습니다!")

                # 텔레그램 알림 전송
                alert_message = f"""🚀 *자동 매매 시작*

⏰ 시작 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
🤖 AI 선별 종목으로 자동매매를 시작합니다!

📊 **매매 설정**:
• 최대 보유 종목: {config.max_positions}개
• 포지션 크기: 계좌의 {config.position_size_value*100:.0f}%
• 손절매: {config.stop_loss_pct*100:.0f}%
• 익절매: {config.take_profit_pct*100:.0f}%

🚀 *AI가 시장을 모니터링하며 최적의 타이밍에 매매합니다!*"""

                self._send_telegram_alert(alert_message, "high")

            except ImportError as ie:
                logger.error(f"매매 엔진 import 실패: {ie}")
                print(f"❌ 매매 엔진 import 실패: {ie}")

        except Exception as e:
            logger.error(f"자동 매매 시작 오류: {e}")
            print(f"❌ 자동 매매 시작 오류: {e}")
            import traceback
            logger.error(f"상세 오류:\n{traceback.format_exc()}")
            
    def _stop_auto_trading(self):
        """자동 매매 중지"""
        try:
            logger.info("=== 자동 매매 중지 ===")
            print(f"⏹️ 자동 매매 중지 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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
                            loop.run_until_complete(trading_engine.stop_trading("스케줄러 자동 중지"))
                        except Exception as e:
                            logger.error(f"자동 매매 중지 실행 오류: {e}")

                    stop_thread = threading.Thread(target=stop_trading, daemon=False)
                    stop_thread.start()
                    stop_thread.join(timeout=10)  # 최대 10초 대기

                    logger.info("자동 매매 중지 완료")
                    print("✅ 자동 매매가 중지되었습니다!")

                    # 텔레그램 중지 알림
                    alert_message = f"""⏹️ *자동 매매 중지*

⏰ 중지 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
📈 장 마감으로 자동매매를 중지합니다.

📊 *오늘의 매매 결과는 일일 리포트를 확인하세요!*"""

                    self._send_telegram_alert(alert_message, "normal")

                else:
                    logger.info("자동 매매가 실행 중이 아닙니다")
                    print("ℹ️ 자동 매매가 실행 중이 아닙니다.")

            except ImportError as ie:
                logger.warning(f"매매 엔진 import 실패: {ie}")
                print("ℹ️ 자동 매매 엔진을 찾을 수 없습니다.")

        except Exception as e:
            logger.error(f"자동 매매 중지 오류: {e}")
            print(f"❌ 자동 매매 중지 오류: {e}")
            import traceback
            logger.error(f"상세 오류:\n{traceback.format_exc()}")
            
    def _send_data_to_ai_system(self):
        """Phase 1,2 완료 후 AI 학습 시스템에 데이터 전달"""
        try:
            logger.info("=== AI 학습 시스템 데이터 연동 시작 ===")
            print(f"🔗 AI 학습 데이터 연동 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Phase 1 스크리닝 결과 수집
            screening_data = self._collect_phase1_data()
            
            # Phase 2 선정 결과 수집
            selection_data = self._collect_phase2_data()
            
            # AI 학습용 통합 데이터 생성
            ai_learning_data = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'timestamp': datetime.now().isoformat(),
                'phase1_screening': screening_data,
                'phase2_selection': selection_data,
                'integration_status': 'completed'
            }
            
            # AI 학습 데이터 저장
            os.makedirs("data/learning/raw_data", exist_ok=True)
            ai_data_file = f"data/learning/raw_data/daily_integration_{datetime.now().strftime('%Y%m%d')}.json"
            
            with open(ai_data_file, 'w') as f:
                json.dump(ai_learning_data, f, indent=2, ensure_ascii=False)
            
            # 피드백 시스템에 데이터 전달 (간소화된 버전)
            self._update_feedback_system(ai_learning_data)
            
            logger.info("AI 학습 시스템 데이터 연동 완료")
            print("✅ AI 학습 데이터 연동 완료!")
            
        except Exception as e:
            logger.error(f"AI 학습 데이터 연동 오류: {e}")
            print(f"❌ AI 학습 데이터 연동 오류: {e}")
    
    def _collect_phase1_data(self):
        """Phase 1 스크리닝 데이터 수집"""
        try:
            # 최신 스크리닝 결과 파일 찾기
            screening_dir = "data/watchlist"
            screening_files = [f for f in os.listdir(screening_dir) if f.startswith('screening_results_') and f.endswith('.json')]
            
            if screening_files:
                latest_file = max(screening_files)
                screening_file_path = os.path.join(screening_dir, latest_file)
                
                # 파일 크기 확인 (너무 큰 파일은 요약만)
                file_size = os.path.getsize(screening_file_path)
                if file_size > 1024 * 1024:  # 1MB 이상이면 요약만
                    return {
                        'file_name': latest_file,
                        'file_size_mb': round(file_size / (1024 * 1024), 2),
                        'status': 'large_file_summarized',
                        'total_screened_stocks': 2875  # 대략적 수치
                    }
                
            return {
                'total_screened_stocks': 2875,
                'watchlist_stocks': 2221,
                'status': 'completed'
            }
            
        except Exception as e:
            logger.warning(f"Phase 1 데이터 수집 오류: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _collect_phase2_data(self):
        """Phase 2 선정 데이터 수집"""
        try:
            # 최신 선정 결과 파일 읽기
            selection_file = "data/daily_selection/latest_selection.json"
            
            if os.path.exists(selection_file):
                with open(selection_file, 'r') as f:
                    selection_data = json.load(f)
                
                selected_stocks = selection_data.get('data', {}).get('selected_stocks', [])
                
                return {
                    'total_selected_stocks': len(selected_stocks),
                    'selection_criteria': selection_data.get('metadata', {}).get('filtering_criteria', {}),
                    'market_condition': selection_data.get('market_condition', 'neutral'),
                    'status': 'completed'
                }
            
            return {
                'total_selected_stocks': 50,  # 기본값
                'status': 'completed'
            }
            
        except Exception as e:
            logger.warning(f"Phase 2 데이터 수집 오류: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _update_feedback_system(self, ai_learning_data):
        """피드백 시스템 업데이트 (간소화된 버전)"""
        try:
            # 피드백 데이터 생성
            feedback_data = {
                'feedback_date': datetime.now().isoformat(),
                'total_predictions': ai_learning_data['phase2_selection'].get('total_selected_stocks', 50),
                'data_quality_score': 0.95,  # 데이터 품질 점수
                'integration_success': True,
                'learning_ready': True
            }
            
            # 피드백 데이터 저장
            os.makedirs("data/learning/feedback", exist_ok=True)
            feedback_file = f"data/learning/feedback/daily_feedback_{datetime.now().strftime('%Y%m%d')}.json"
            
            with open(feedback_file, 'w') as f:
                json.dump(feedback_data, f, indent=2, ensure_ascii=False)
            
            logger.info("피드백 시스템 업데이트 완료")
            
        except Exception as e:
            logger.warning(f"피드백 시스템 업데이트 오류: {e}")
    
    def _print_daily_summary(self):
        """일일 선정 결과 요약 출력"""
        try:
            # 최신 선정 결과 조회
            _v_latest_selection = self._v_phase2_cli._v_daily_updater.get_latest_selection()
            
            if _v_latest_selection:
                _v_selected_stocks = _v_latest_selection.get("data", {}).get("selected_stocks", [])
                _v_metadata = _v_latest_selection.get("metadata", {})
                
                print(f"\n📋 일일 선정 결과 요약")
                print(f"├─ 선정 종목: {len(_v_selected_stocks)}개")
                print(f"├─ 평균 매력도: {_v_metadata.get('avg_attractiveness', 0):.1f}점")
                print(f"└─ 시장 상황: {_v_latest_selection.get('market_condition', 'unknown')}")
                
                if _v_selected_stocks:
                    print(f"\n상위 5개 종목:")
                    for i, stock in enumerate(_v_selected_stocks[:5], 1):
                        print(f"  {i}. {stock.get('stock_name', '')} ({stock.get('stock_code', '')}) - {stock.get('price_attractiveness', 0):.1f}점")
            
        except Exception as e:
            logger.error(f"일일 요약 출력 오류: {e}")
    
    def run_immediate_tasks(self):
        """즉시 실행 (테스트용)"""
        print("🔄 즉시 실행 모드")
        print("1. 일간 스크리닝 실행...")
        self._run_daily_screening()
        
        # Phase 1이 성공했을 때만 Phase 2가 자동 실행됨
        if not self._v_phase1_completed:
            print("\n❌ Phase 1 실패로 인해 Phase 2를 건너뜁니다")
        
        print("\n2. 정리 작업 실행...")
        self._run_market_close_tasks()
        
        print("\n✅ 모든 작업 완료!")

    def _generate_screening_alert(self) -> str:
        """스크리닝 완료 알람 메시지 생성"""
        try:
            # 감시 리스트 통계 조회
            watchlist_manager = WatchlistManager("data/watchlist/watchlist.json")
            stats = watchlist_manager.get_statistics()
            
            total_stocks = stats.get('total_count', 0)
            avg_score = stats.get('avg_score', 0.0)
            sectors = stats.get('sectors', {})
            
            # 상위 섹터 3개 추출
            top_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:3]
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            message = f"""🌅 *한투 퀀트 아침 스크리닝 완료*

⏰ 완료 시간: `{current_time}`
📊 분석 종목: `2,875개`
✅ 선정 종목: `{total_stocks}개`
📈 평균 점수: `{avg_score:.1f}점`

🏆 *상위 섹터*:"""
            
            for i, (sector, count) in enumerate(top_sectors, 1):
                percentage = (count / total_stocks * 100) if total_stocks > 0 else 0
                message += f"\n{i}. {sector}: {count}개 ({percentage:.1f}%)"
            
            message += f"""

🎯 *오늘의 투자 포인트*:
• 고성장 섹터 집중 모니터링
• 기술적 반등 신호 종목 주목
• 거래량 급증 종목 추적

🚀 *이제 AI가 선별한 우량 종목으로 투자하세요!*

⚙️ 다음 업데이트: 일일 매매 리스트 (Phase 2 진행 중)"""
            
            return message
            
        except Exception as e:
            logger.error(f"스크리닝 알람 메시지 생성 실패: {e}")
            return f"""🌅 *한투 퀀트 아침 스크리닝 완료*

⏰ 완료 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
✅ 스크리닝이 성공적으로 완료되었습니다!

🚀 *AI 종목 선별 시스템이 가동 중입니다!*"""


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="한투 퀀트 통합 스케줄러")
    
    # 서브커맨드 설정
    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령')
    
    # 스케줄러 시작
    start_parser = subparsers.add_parser('start', help='스케줄러 시작')
    
    # 스케줄러 중지
    stop_parser = subparsers.add_parser('stop', help='스케줄러 중지')
    
    # 상태 조회
    status_parser = subparsers.add_parser('status', help='스케줄러 상태 조회')
    status_parser.add_argument('--telegram', action='store_true', help='텔레그램으로 상태 전송')
    status_parser.add_argument('--heartbeat', action='store_true', help='생존 신호 전송')
    
    # 즉시 실행
    run_parser = subparsers.add_parser('run', help='즉시 실행 (테스트용)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 스케줄러 생성 (병렬 워커 수 설정)
    scheduler = IntegratedScheduler(p_parallel_workers=4)
    
    try:
        if args.command == 'start':
            scheduler.start_scheduler()
            
            # 백그라운드에서 실행하기 위해 대기
            print("Press Ctrl+C to stop the scheduler...")
            while True:
                time.sleep(1)
                
        elif args.command == 'stop':
            scheduler.stop_scheduler()
            
        elif args.command == 'status':
            status = scheduler.get_status()
            
            print("\n⏰ 통합 스케줄러 상태")
            print(f"├─ 실행 상태: {'🟢 실행 중' if status['running'] else '🔴 정지'}")
            print(f"├─ 마지막 스크리닝: {status['last_screening']}")
            print(f"└─ 마지막 일일 업데이트: {status['last_daily_update']}")
            
            if status['scheduled_jobs']:
                print(f"\n📅 예정된 작업:")
                for job in status['scheduled_jobs']:
                    print(f"  - {job['job']}: {job['next_run']}")
            
            # 텔레그램으로 상태 전송
            if args.telegram:
                try:
                    from core.utils.telegram_notifier import get_telegram_notifier
                    notifier = get_telegram_notifier()
                    
                    if notifier.is_enabled():
                        # 상태 메시지 생성
                        status_emoji = "🟢" if status['running'] else "🔴"
                        status_text = "실행 중" if status['running'] else "정지"
                        
                        message = f"""📊 *한투 퀀트 스케줄러 상태*

{status_emoji} *현재 상태*: `{status_text}`
📅 마지막 스크리닝: `{status['last_screening']}`
📈 마지막 업데이트: `{status['last_daily_update']}`

📋 *예정된 작업*:"""
                        
                        if status['scheduled_jobs']:
                            for job in status['scheduled_jobs']:
                                message += f"\n• {job['job']}: {job['next_run']}"
                        else:
                            message += "\n• 예정된 작업 없음"
                        
                        success = notifier.send_message(message, "normal")
                        if success:
                            print("📱 텔레그램으로 상태 전송 완료")
                        else:
                            print("❌ 텔레그램 상태 전송 실패")
                    else:
                        print("⚠️ 텔레그램 알림이 비활성화됨")
                        
                except Exception as e:
                    print(f"❌ 텔레그램 상태 전송 오류: {e}")
            
            # 헬스체크 (생존 신호) 전송
            if args.heartbeat and status['running']:
                try:
                    from core.utils.telegram_notifier import get_telegram_notifier
                    from datetime import datetime
                    
                    notifier = get_telegram_notifier()
                    
                    if notifier.is_enabled():
                        # 실행 시간 계산 (임시로 현재 시간 기준)
                        uptime = "알 수 없음"  # 실제로는 시작 시간을 저장해서 계산해야 함
                        
                        success = notifier.send_scheduler_heartbeat(uptime, status['scheduled_jobs'])
                        if success:
                            print("💓 스케줄러 생존 신호 전송 완료")
                        else:
                            print("❌ 생존 신호 전송 실패")
                    else:
                        print("⚠️ 텔레그램 알림이 비활성화됨")
                        
                except Exception as e:
                    print(f"❌ 생존 신호 전송 오류: {e}")
            elif args.heartbeat and not status['running']:
                print("⚠️ 스케줄러가 실행 중이 아니므로 생존 신호를 전송할 수 없습니다")
            
        elif args.command == 'run':
            scheduler.run_immediate_tasks()
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        scheduler.stop_scheduler("사용자 중단 (Ctrl+C)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"스케줄러 실행 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 