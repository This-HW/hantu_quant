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
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import argparse

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.phase1_watchlist import Phase1Workflow
from workflows.phase2_daily_selection import Phase2CLI
from core.watchlist.watchlist_manager import WatchlistManager
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class IntegratedScheduler:
    """통합 스케줄러 클래스"""
    
    def __init__(self, p_parallel_workers: int = 4):
        """초기화
        
        Args:
            p_parallel_workers: 병렬 처리 워커 수 (기본값: 4)
        """
        self._v_phase1_workflow = Phase1Workflow(p_parallel_workers=p_parallel_workers)
        self._v_phase2_cli = Phase2CLI(p_parallel_workers=p_parallel_workers)
        self._v_parallel_workers = p_parallel_workers
        
        # 스케줄러 상태
        self._v_scheduler_running = False
        self._v_scheduler_thread = None
        
        # 실행 기록
        self._v_last_screening = None
        self._v_last_daily_update = None
        
        # Phase 1 완료 후 Phase 2 자동 실행을 위한 플래그
        self._v_phase1_completed = False
        
        logger.info(f"통합 스케줄러 초기화 완료 (병렬 워커: {p_parallel_workers}개)")
    
    def start_scheduler(self):
        """통합 스케줄러 시작"""
        if self._v_scheduler_running:
            logger.warning("스케줄러가 이미 실행 중입니다")
            return
        
        # 스케줄 설정
        schedule.clear()
        
        # Phase 1: 일간 스크리닝 (매일 06:00)
        schedule.every().day.at("06:00").do(self._run_daily_screening)
        
        # Phase 2: 일일 업데이트 (Phase 1 완료 후 자동 실행)
        # Phase 1 완료 후 _run_daily_screening에서 직접 호출
        
        # 시장 마감 후 정리 작업 (매일 16:00)
        schedule.every().day.at("16:00").do(self._run_market_close_tasks)
        
        # 개발/테스트용 스케줄 (옵션)
        # schedule.every(10).minutes.do(self._run_daily_update)  # 10분마다 테스트
        
        self._v_scheduler_running = True
        self._v_scheduler_thread = threading.Thread(target=self._run_scheduler_loop, daemon=True)
        self._v_scheduler_thread.start()
        
        logger.info("통합 스케줄러 시작됨")
        print("🚀 통합 스케줄러 시작!")
        print("├─ 일간 스크리닝: 매일 06:00")
        print("├─ 일일 업데이트: Phase 1 완료 후 자동 실행")
        print("└─ 마감 후 정리: 매일 16:00")
    
    def stop_scheduler(self):
        """통합 스케줄러 중지"""
        self._v_scheduler_running = False
        schedule.clear()
        
        if self._v_scheduler_thread and self._v_scheduler_thread.is_alive():
            self._v_scheduler_thread.join(timeout=5)
        
        logger.info("통합 스케줄러 중지됨")
        print("⏹️ 통합 스케줄러 중지됨")
    
    def get_status(self) -> Dict:
        """스케줄러 상태 조회"""
        _v_next_jobs = []
        for job in schedule.jobs:
            _v_next_jobs.append({
                "job": str(job.job_func.__name__),
                "next_run": job.next_run.strftime("%Y-%m-%d %H:%M:%S") if job.next_run else "미정",
                "interval": str(job.interval),
                "unit": job.unit
            })
        
        return {
            "running": self._v_scheduler_running,
            "last_screening": self._v_last_screening.strftime("%Y-%m-%d %H:%M:%S") if self._v_last_screening else "없음",
            "last_daily_update": self._v_last_daily_update.strftime("%Y-%m-%d %H:%M:%S") if self._v_last_daily_update else "없음",
            "scheduled_jobs": _v_next_jobs
        }
    
    def _run_scheduler_loop(self):
        """스케줄러 루프 실행"""
        while self._v_scheduler_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 1분마다 체크
            except Exception as e:
                logger.error(f"스케줄러 루프 오류: {e}")
                time.sleep(60)
    
    def _run_daily_screening(self):
        """일간 스크리닝 실행 (Phase 1)"""
        try:
            logger.info("=== 일간 스크리닝 시작 ===")
            print(f"🔍 일간 스크리닝 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 전체 시장 스크리닝 실행 (코스피 + 코스닥 전체 2875개 종목)
            _v_success = self._v_phase1_workflow.run_full_screening()
            
            if _v_success:
                self._v_last_screening = datetime.now()
                self._v_phase1_completed = True
                logger.info("일간 스크리닝 완료")
                print("✅ 일간 스크리닝 완료!")
                
                # 감시 리스트 통계 출력
                self._v_phase1_workflow.list_watchlist()
                
                # Phase 1 완료 후 즉시 Phase 2 실행
                print("\n🔄 Phase 1 완료 - Phase 2 자동 실행 시작...")
                time.sleep(2)  # 2초 대기
                self._run_daily_update()
                
            else:
                logger.error("일간 스크리닝 실패")
                print("❌ 일간 스크리닝 실패")
                self._v_phase1_completed = False
                
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
            self._v_phase2_cli._v_daily_updater._v_watchlist_manager = WatchlistManager("data/watchlist/watchlist.json")
            
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
            
            if _v_report_success:
                print("✅ 일일 리포트 생성 완료")
            
            print("✅ 시장 마감 후 정리 완료")
            
        except Exception as e:
            logger.error(f"시장 마감 후 정리 오류: {e}")
            print(f"❌ 시장 마감 후 정리 오류: {e}")
    
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
            
        elif args.command == 'run':
            scheduler.run_immediate_tasks()
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        scheduler.stop_scheduler()
        sys.exit(0)
    except Exception as e:
        logger.error(f"스케줄러 실행 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 