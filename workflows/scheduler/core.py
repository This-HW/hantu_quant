"""
스케줄러 핵심 오케스트레이션 모듈

통합 스케줄러의 핵심 로직을 담당하며, 모든 서브모듈을 조합하여
스케줄링, 실행, 모니터링, 복구 등의 기능을 제공합니다.
"""

import asyncio
import schedule
import time
import threading
import signal
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List
from pathlib import Path

from core.utils.log_utils import get_logger

from .config import SchedulerConfig
from .notifications import NotificationService, get_notification_service
from .data import DataCollectionService
from .recovery import RecoveryManager
from .maintenance import MaintenanceService
from .monitoring import MonitoringService

logger = get_logger(__name__)


class SchedulerCore:
    """통합 스케줄러 핵심 클래스

    모든 서브모듈을 조합하여 통합 스케줄러를 구성합니다.
    의존성 주입 패턴을 사용하여 테스트 가능한 구조를 유지합니다.

    Features:
        - 스케줄 설정 및 실행
        - Phase 1/2/3/4 실행
        - 자동 복구 및 유지보수
        - 실시간 모니터링
        - 텔레그램 알림
        - 안전 종료
    """

    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        notification_service: Optional[NotificationService] = None,
        data_service: Optional[DataCollectionService] = None,
        recovery_manager: Optional[RecoveryManager] = None,
        maintenance_service: Optional[MaintenanceService] = None,
        monitoring_service: Optional[MonitoringService] = None,
    ):
        """초기화

        Args:
            config: 스케줄러 설정
            notification_service: 알림 서비스
            data_service: 데이터 수집 서비스
            recovery_manager: 복구 관리자
            maintenance_service: 유지보수 서비스
            monitoring_service: 모니터링 서비스
        """
        try:
            logger.info("=" * 50)
            logger.info("[초기화] SchedulerCore 초기화 시작")

            # 설정 초기화
            self.config = config or SchedulerConfig()

            # 설정 검증
            if not self.config.validate():
                raise ValueError("스케줄러 설정이 유효하지 않습니다")

            # 필요한 디렉토리 생성
            self.config.ensure_directories()

            # 서비스 초기화 (의존성 주입)
            self.notification_service = notification_service or get_notification_service()
            self.data_service = data_service or DataCollectionService(
                screening_dir=str(self.config.watchlist_dir),
                selection_file=self.config.latest_selection_file,
                ai_raw_data_dir=str(self.config.ai_raw_data_dir),
                ai_feedback_dir=str(self.config.ai_feedback_dir),
                max_file_size_mb=self.config.max_file_size_mb,
            )
            self.recovery_manager = recovery_manager or RecoveryManager(
                config=self.config,
                notification_service=self.notification_service,
            )
            self.maintenance_service = maintenance_service or MaintenanceService(
                config=self.config,
                notification_service=self.notification_service,
            )
            self.monitoring_service = monitoring_service or MonitoringService(
                config=self.config,
                notification_service=self.notification_service,
            )

            # 스케줄러 상태
            self._running = False
            self._scheduler_thread: Optional[threading.Thread] = None
            self._start_time: Optional[datetime] = None

            # 실행 기록
            self._last_screening: Optional[datetime] = None
            self._last_daily_update: Optional[datetime] = None

            logger.info(f"[초기화] 설정: {self.config.to_dict()}")
            logger.info("[초기화] SchedulerCore 초기화 완료")
            logger.info("=" * 50)

        except Exception as e:
            logger.error(f"SchedulerCore 초기화 실패: {e}", exc_info=True)
            raise

    def setup_schedule(self) -> None:
        """스케줄 설정

        schedule 라이브러리를 사용하여 모든 작업을 스케줄링합니다.
        """
        try:
            logger.info("[스케줄] 스케줄 설정 시작")
            schedule.clear()

            weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]

            # 캐시 초기화 (자정)
            schedule.every().day.at(self.config.cache_init_time).do(
                self.maintenance_service.clear_cache
            )

            # Phase 1: 일간 스크리닝 (평일 06:00)
            for day in weekdays:
                getattr(schedule.every(), day).at(self.config.phase1_schedule_time).do(
                    self.run_screening
                )

            # Phase 2: 분산 배치 실행 (07:00-08:25, 5분 간격, 평일)
            batch_times = self.config.get_batch_schedule_times()
            for batch_index, time_str in enumerate(batch_times):
                for day in weekdays:
                    getattr(schedule.every(), day).at(time_str).do(
                        self.run_batch, batch_index
                    )

            # Phase 3: 자동 매매 (평일)
            for day in weekdays:
                getattr(schedule.every(), day).at("09:00").do(self.start_trading)
                getattr(schedule.every(), day).at("15:30").do(self._stop_auto_trading)

            # 시장 마감 정리 (평일 16:00)
            for day in weekdays:
                getattr(schedule.every(), day).at("16:00").do(self.run_market_close)

            # Phase 4: AI 학습 데이터 연동 (매일 17:00)
            schedule.every().day.at(self.config.ai_data_schedule_time).do(
                self.send_ai_data
            )

            # 토요일 작업
            schedule.every().saturday.at("10:00").do(self._run_fundamental_data_collection)

            # 일요일 작업
            schedule.every().sunday.at("03:00").do(
                self.maintenance_service.run_auto_maintenance
            )

            logger.info(f"[스케줄] 총 {len(schedule.jobs)}개 작업 스케줄링 완료")

        except Exception as e:
            logger.error(f"스케줄 설정 실패: {e}", exc_info=True)
            raise

    def run(self) -> None:
        """메인 실행 루프

        스케줄러를 시작하고 메인 루프를 실행합니다.
        Ctrl+C 시그널을 받으면 안전하게 종료합니다.
        """
        try:
            # 스케줄 설정
            self.setup_schedule()

            # 상태 업데이트
            self._running = True
            self._start_time = datetime.now()

            # 시작 알림
            logger.info("=" * 50)
            logger.info("[시작] 통합 스케줄러 시작")
            logger.info(f"[시작] 시작 시간: {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("=" * 50)

            self._print_schedule_info()

            # 텔레그램 시작 알림
            self._send_start_notification()

            # 복구 작업 (재시작 시 누락된 작업 자동 실행)
            self._run_recovery()

            # 메인 루프 (별도 스레드)
            self._scheduler_thread = threading.Thread(
                target=self._run_scheduler_loop, daemon=True
            )
            self._scheduler_thread.start()

            # 시그널 핸들러 설정 (Ctrl+C)
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

            # 메인 스레드는 대기
            while self._running:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("[중단] Ctrl+C 감지 - 종료 중...")
            self.graceful_shutdown("Ctrl+C")
        except Exception as e:
            logger.error(f"스케줄러 실행 오류: {e}", exc_info=True)
            self.graceful_shutdown(f"오류: {str(e)}")
            raise

    def _run_scheduler_loop(self) -> None:
        """스케줄러 메인 루프 (내부 메서드)"""
        logger.info("[루프] 스케줄러 루프 시작")

        while self._running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                logger.error(f"스케줄러 루프 오류: {e}", exc_info=True)
                time.sleep(5)

        logger.info("[루프] 스케줄러 루프 종료")

    def _signal_handler(self, signum, frame) -> None:
        """시그널 핸들러 (Ctrl+C, SIGTERM)"""
        logger.info(f"[시그널] 시그널 수신: {signum}")
        self.graceful_shutdown("시그널")

    def _print_schedule_info(self) -> None:
        """스케줄 정보 출력"""
        print("\n" + "=" * 50)
        print("통합 스케줄러 시작!")
        print("=" * 50)
        print(f"├─ 캐시 초기화: 매일 {self.config.cache_init_time}")
        print(f"├─ 일간 스크리닝: 평일 {self.config.phase1_schedule_time}")
        print(f"├─ 일일 업데이트: 07:00-{self.config.get_batch_end_time()} "
              f"({self.config.batch_count}개 배치, {self.config.batch_interval_minutes}분 간격)")
        print("├─ 자동 매매 시작: 평일 09:00")
        print("├─ 자동 매매 중지: 평일 15:30")
        print("├─ 마감 후 정리: 평일 16:00")
        print(f"├─ AI 학습 연동: 매일 {self.config.ai_data_schedule_time}")
        print("├─ 재무 데이터 수집: 토요일 10:00")
        print("└─ 자동 유지보수: 일요일 03:00")
        print("=" * 50 + "\n")

    def _send_start_notification(self) -> None:
        """스케줄러 시작 알림 전송"""
        try:
            message = (
                f"🚀 *통합 스케줄러 시작*\n\n"
                f"시작 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"배치 수: {self.config.batch_count}개\n"
                f"배치 시간: 07:00-{self.config.get_batch_end_time()}"
            )
            self.notification_service.send_message(message, "normal")
        except Exception as e:
            logger.warning(f"시작 알림 전송 실패: {e}", exc_info=True)

    def _run_recovery(self) -> None:
        """재시작 시 누락된 작업 복구"""
        try:
            recovered = self.recovery_manager.check_and_recover_missed_tasks(
                run_screening_callback=self.run_screening,
                run_batch_callback=self.run_batch,
                start_trading_callback=self.start_trading,
                run_market_close_callback=self.run_market_close,
                run_performance_callback=self._run_daily_performance,
            )
            if recovered:
                logger.info(f"복구된 작업: {recovered}")
        except Exception as e:
            logger.warning(f"복구 작업 실패: {e}", exc_info=True)

    # ========================================
    # Phase 실행 메서드
    # ========================================

    def run_screening(self) -> bool:
        """Phase 1 스크리닝 실행

        Returns:
            성공 여부
        """
        try:
            logger.info("=" * 50)
            logger.info("[Phase 1] 일간 스크리닝 시작")
            print(f"\n[Phase 1] 일간 스크리닝 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 지연 import (순환 참조 방지)
            from workflows.phase1_watchlist import run_daily_screening

            result = run_daily_screening()
            success = result is not None and result.get("status") == "success"

            if success:
                self._last_screening = datetime.now()
                watchlist_count = result.get("watchlist_count", 0)
                logger.info(f"[Phase 1] 일간 스크리닝 완료 - {watchlist_count}개 종목")
                print(f"[Phase 1] 일간 스크리닝 완료! ({watchlist_count}개 종목)\n")

                self.notification_service.send_phase1_complete(watchlist_count)
            else:
                logger.error("[Phase 1] 일간 스크리닝 실패")
                print("[Phase 1] 일간 스크리닝 실패\n")
                self.notification_service.send_error("일간 스크리닝 실패", "Phase 1")

            return success

        except Exception as e:
            logger.error(f"일간 스크리닝 오류: {e}", exc_info=True)
            print(f"일간 스크리닝 오류: {e}\n")
            self.notification_service.send_error(str(e), "Phase 1 스크리닝")
            return False

    def run_batch(self, batch_index: int) -> bool:
        """Phase 2 배치 실행

        Args:
            batch_index: 배치 번호 (0-17)

        Returns:
            성공 여부
        """
        try:
            logger.info(f"[Phase 2] 배치 {batch_index}/{self.config.batch_count - 1} 시작")

            # 지연 import (순환 참조 방지)
            from core.daily_selection.daily_updater import DailyUpdater

            updater = DailyUpdater()
            result = updater.run_batch(batch_index)
            success = result is not None and result.get("status") == "success"

            if success:
                selected_count = result.get("selected_count", 0)
                logger.info(f"[Phase 2] 배치 {batch_index} 완료 - {selected_count}개 종목 선정")

                # 마지막 배치일 때 완료 알림
                if batch_index == self.config.batch_count - 1:
                    self._last_daily_update = datetime.now()
                    self.notification_service.send_phase2_batch_complete(
                        batch_index, selected_count
                    )
            else:
                logger.warning(f"[Phase 2] 배치 {batch_index} 실패")

            return success

        except Exception as e:
            logger.error(f"배치 {batch_index} 실행 오류: {e}", exc_info=True)
            return False

    def _run_async_safe(self, coro):
        """이벤트 루프 안전 실행 (스케줄러 스레드용)

        스케줄러 스레드에서 async 함수를 안전하게 실행하기 위해
        새로운 이벤트 루프를 생성하여 사용합니다.

        Args:
            coro: 실행할 코루틴

        Returns:
            코루틴 실행 결과 (에러 시 False)
        """
        try:
            # 새 이벤트 루프 생성 (기존 루프와 충돌 방지)
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"비동기 실행 실패: {e}", exc_info=True)
            return False

    def start_trading(self, from_recovery: bool = False) -> bool:
        """자동 매매 시작 (09:00)

        Args:
            from_recovery: 복구에서 호출되었는지 여부

        Returns:
            성공 여부
        """
        try:
            logger.info("=" * 50)
            logger.info("[Phase 3] 자동 매매 시작")
            print(f"\n[Phase 3] 자동 매매 시작 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 지연 import (순환 참조 방지)
            from core.trading.trading_engine import get_trading_engine

            engine = get_trading_engine()
            success = self._run_async_safe(engine.start_trading())

            if success:
                logger.info("[Phase 3] 자동 매매 시작 완료")
                print("[Phase 3] 자동 매매 시작 완료!\n")

                if not from_recovery:
                    self.notification_service.send_message(
                        f"📈 *자동 매매 시작*\n\n"
                        f"시간: `{datetime.now().strftime('%H:%M:%S')}`",
                        "normal"
                    )
            else:
                logger.warning("[Phase 3] 자동 매매 시작 실패 또는 이미 실행 중")
                print("[Phase 3] 자동 매매 시작 스킵됨\n")

            return success

        except Exception as e:
            logger.error(f"자동 매매 시작 오류: {e}", exc_info=True)
            print(f"자동 매매 시작 오류: {e}\n")
            return False

    def _stop_auto_trading(self) -> bool:
        """자동 매매 중지 (15:30)

        Returns:
            성공 여부
        """
        try:
            logger.info("=" * 50)
            logger.info("[Phase 3] 자동 매매 중지")
            print(f"\n[Phase 3] 자동 매매 중지 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 지연 import (순환 참조 방지)
            from core.trading.trading_engine import get_trading_engine

            engine = get_trading_engine()
            success = self._run_async_safe(engine.stop_trading(reason="스케줄러 자동 중지"))

            if success:
                logger.info("[Phase 3] 자동 매매 중지 완료")
                print("[Phase 3] 자동 매매 중지 완료!\n")

                self.notification_service.send_message(
                    f"📉 *자동 매매 중지*\n\n"
                    f"시간: `{datetime.now().strftime('%H:%M:%S')}`",
                    "normal"
                )
            else:
                logger.warning("[Phase 3] 자동 매매 중지 실패")
                print("[Phase 3] 자동 매매 중지 실패\n")

            return success

        except Exception as e:
            logger.error(f"자동 매매 중지 오류: {e}", exc_info=True)
            print(f"자동 매매 중지 오류: {e}\n")
            return False

    def run_market_close(self) -> bool:
        """시장 마감 정리 작업 (16:00)

        Returns:
            성공 여부
        """
        try:
            logger.info("=" * 50)
            logger.info("[정리] 시장 마감 후 정리 작업 시작")
            print(f"\n[정리] 시장 마감 후 정리 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 부분 성공 여부 추적
            journal_success = False
            summary_success = False

            # 매매일지 요약 생성 및 저장
            try:
                from core.trading.trade_journal import TradeJournal
                from core.learning.analysis.daily_performance import (
                    DailyPerformanceAnalyzer,
                )
                import os

                journal = TradeJournal()
                summary = journal.compute_daily_summary()
                logger.info(
                    f"시장 마감 요약 - 손익: {summary['realized_pnl']:,.0f}, "
                    f"거래: {summary['total_trades']}건, 승률: {summary['win_rate']*100:.1f}%"
                )
                journal_success = True

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
                    logger.warning(f"매매일지 요약 성과 반영 중 오류: {e}", exc_info=True)
            except Exception as e:
                logger.warning(f"매매일지 요약 생성 실패: {e}", exc_info=True)

            # TradingEngine 일일 요약 생성 및 텔레그램 전송
            try:
                from core.trading.trading_engine import get_trading_engine

                engine = get_trading_engine()
                summary_message = engine.generate_daily_summary()

                if summary_message:
                    logger.info("TradingEngine 일일 요약 생성 완료")
                    self.notification_service.send_message(summary_message, "normal")
                    print("일일 거래 요약 텔레그램 전송 완료")
                    summary_success = True
            except Exception as e:
                logger.warning(f"TradingEngine 일일 요약 생성 실패: {e}", exc_info=True)

            # 하나 이상의 작업이 성공해야 True 반환
            if journal_success or summary_success:
                logger.info("[정리] 시장 마감 정리 완료")
                print("[정리] 시장 마감 정리 완료!\n")
                return True
            else:
                logger.warning("[정리] 시장 마감 정리: 모든 작업 실패")
                print("[정리] 시장 마감 정리 실패 (모든 작업 실패)\n")
                return False

        except Exception as e:
            logger.error(f"시장 마감 정리 오류: {e}", exc_info=True)
            print(f"시장 마감 정리 오류: {e}\n")
            return False

    def send_ai_data(self) -> bool:
        """AI 학습 데이터 연동 (17:00)

        Returns:
            성공 여부
        """
        try:
            logger.info("=" * 50)
            logger.info("[Phase 4] AI 학습 데이터 연동 시작")
            print(f"\n[Phase 4] AI 학습 데이터 연동 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            success = self.data_service.send_ai_data()

            if success:
                logger.info("[Phase 4] AI 학습 데이터 연동 완료")
                print("[Phase 4] AI 학습 데이터 연동 완료!\n")

                # 통계 정보 가져오기
                latest_data = self.data_service.get_latest_ai_data()
                if latest_data:
                    screened = latest_data.get("phase1_screening", {}).get("total_screened_stocks", 0)
                    selected = latest_data.get("phase2_selection", {}).get("total_selected_stocks", 0)
                    self.notification_service.send_ai_data_complete(screened, selected)
            else:
                logger.warning("[Phase 4] AI 학습 데이터 연동 실패")
                print("[Phase 4] AI 학습 데이터 연동 실패\n")

            return success

        except Exception as e:
            logger.error(f"AI 학습 데이터 연동 오류: {e}", exc_info=True)
            print(f"AI 학습 데이터 연동 오류: {e}\n")
            return False

    def _run_fundamental_data_collection(self) -> bool:
        """재무 데이터 수집 (토요일 10:00)

        Returns:
            성공 여부
        """
        try:
            logger.info("=" * 50)
            logger.info("[데이터] 재무 데이터 수집 시작")

            # 지연 import (순환 참조 방지)
            from core.api.krx_client import KRXClient

            client = KRXClient()
            result = client.collect_market_fundamentals()
            success = result is not None and not result.empty

            if success:
                logger.info(f"[데이터] 재무 데이터 수집 완료 - {len(result)}개 종목")
                self.notification_service.send_message(
                    f"📊 *재무 데이터 수집 완료*\n\n"
                    f"종목 수: {len(result)}개\n"
                    f"시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
                    "normal"
                )
            else:
                logger.warning("[데이터] 재무 데이터 수집 실패")

            return success

        except Exception as e:
            logger.error(f"재무 데이터 수집 오류: {e}", exc_info=True)
            return False

    def _run_daily_performance(self) -> bool:
        """일일 성과 분석 (Phase 4)

        Returns:
            성공 여부
        """
        try:
            logger.info("=" * 50)
            logger.info("[성과] 일일 성과 분석 시작")
            print(f"\n[성과] 일일 성과 분석 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # 일일 성과 리포트 전송
            success = self.notification_service.send_daily_performance_report()
            if success:
                logger.info("일일 성과 리포트 전송 완료")
                print("일일 성과 리포트가 텔레그램으로 전송되었습니다!")
            else:
                logger.warning("일일 성과 리포트 전송 실패")
                print("일일 성과 리포트 전송 실패")

            # 추가 성과 분석 작업
            try:
                from core.performance.performance_metrics import get_performance_metrics
                import os
                import json

                metrics = get_performance_metrics()
                daily_perf = metrics.get_daily_performance()

                # 성과 데이터 저장
                os.makedirs("data/learning/performance", exist_ok=True)
                performance_file = f"data/learning/performance/daily_analysis_{datetime.now().strftime('%Y%m%d')}.json"

                with open(performance_file, "w", encoding="utf-8") as f:
                    json.dump(daily_perf, f, indent=2, ensure_ascii=False)

                logger.info(
                    f"일일 성과 분석 완료: 실현손익 {daily_perf.get('realized_pnl', 0):,.0f}원, "
                    f"평가손익 {daily_perf.get('unrealized_pnl', 0):,.0f}원"
                )
                print("[성과] 일일 성과 분석 완료!")
                print(f"   - 실현 손익: {daily_perf.get('realized_pnl', 0):,.0f}원")
                print(f"   - 평가 손익: {daily_perf.get('unrealized_pnl', 0):,.0f}원")
                print(f"   - 총 손익: {daily_perf.get('total_pnl', 0):,.0f}원")

            except ImportError as ie:
                logger.warning(f"성과 분석 모듈 로드 실패, 기본 분석 사용: {ie}", exc_info=True)
                print("성과 분석 모듈 로드 실패, 기본 분석으로 대체")

                # 기본 분석 (폴백)
                import os
                import json
                performance_data = {
                    "analysis_date": datetime.now().isoformat(),
                    "status": "fallback_mode",
                    "message": "성과 지표 모듈을 사용할 수 없어 기본 분석 모드로 실행됨",
                }

                os.makedirs("data/learning/performance", exist_ok=True)
                performance_file = f"data/learning/performance/daily_analysis_{datetime.now().strftime('%Y%m%d')}.json"

                with open(performance_file, "w", encoding="utf-8") as f:
                    json.dump(performance_data, f, indent=2, ensure_ascii=False)

            except Exception as analysis_error:
                logger.error(f"성과 분석 중 오류 발생: {analysis_error}", exc_info=True)
                print(f"성과 분석 중 오류: {analysis_error}")

            return True

        except Exception as e:
            logger.error(f"일일 성과 분석 오류: {e}", exc_info=True)
            print(f"일일 성과 분석 오류: {e}\n")
            return False

    # ========================================
    # 유틸리티 메서드
    # ========================================

    def get_status(self) -> Dict[str, Any]:
        """스케줄러 상태 조회

        Returns:
            상태 딕셔너리
        """
        return {
            "running": self._running,
            "start_time": (
                self._start_time.strftime("%Y-%m-%d %H:%M:%S")
                if self._start_time
                else None
            ),
            "last_screening": (
                self._last_screening.strftime("%Y-%m-%d %H:%M:%S")
                if self._last_screening
                else None
            ),
            "last_daily_update": (
                self._last_daily_update.strftime("%Y-%m-%d %H:%M:%S")
                if self._last_daily_update
                else None
            ),
            "total_jobs": len(schedule.jobs),
            "config": self.config.to_dict(),
        }

    def graceful_shutdown(self, reason: str = "사용자 요청") -> None:
        """안전 종료

        Args:
            reason: 종료 이유
        """
        try:
            logger.info("=" * 50)
            logger.info(f"[종료] 안전 종료 시작: {reason}")

            # 텔레그램 종료 알림
            self.notification_service.send_message(
                f"🛑 *스케줄러 종료*\n\n"
                f"사유: {reason}\n"
                f"시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
                "high"
            )

            # 스케줄러 중지
            self._running = False
            schedule.clear()

            # 스레드 종료 대기
            if self._scheduler_thread and self._scheduler_thread.is_alive():
                logger.info("[종료] 스케줄러 스레드 종료 대기 중...")
                self._scheduler_thread.join(timeout=5)

            logger.info(f"[종료] 통합 스케줄러 종료 완료: {reason}")
            logger.info("=" * 50)
            print(f"\n[종료] 통합 스케줄러 종료됨: {reason}\n")

        except Exception as e:
            logger.error(f"안전 종료 오류: {e}", exc_info=True)


# === 싱글톤 인스턴스 ===
_scheduler_core: Optional[SchedulerCore] = None
_core_lock = threading.Lock()


def get_scheduler_core() -> SchedulerCore:
    """SchedulerCore 싱글톤 인스턴스 반환

    Returns:
        SchedulerCore 인스턴스
    """
    global _scheduler_core

    if _scheduler_core is None:
        with _core_lock:
            if _scheduler_core is None:
                _scheduler_core = SchedulerCore()

    return _scheduler_core
