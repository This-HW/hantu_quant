"""
자동 복구 시스템
- 일반적인 문제를 자동으로 감지하고 복구
- 복구 가능한 문제와 불가능한 문제 구분
- 복구 시도 이력 및 결과 기록
"""

import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

from ..utils.log_utils import get_logger
from ..utils.telegram_notifier import get_telegram_notifier

logger = get_logger(__name__)


@dataclass
class RecoveryAction:
    """복구 액션"""
    issue_type: str
    action_name: str
    description: str
    timestamp: str
    success: bool
    error_message: Optional[str] = None


class AutoRecoverySystem:
    """자동 복구 시스템"""

    def __init__(self):
        self.logger = logger
        self.notifier = get_telegram_notifier()
        self.data_dir = Path("data/recovery")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 복구 시도 제한
        self.max_recovery_attempts = 3  # 동일 문제에 대해 최대 3회까지만 시도
        self.recovery_history = {}

        self.logger.info("AutoRecoverySystem 초기화 완료")

    def attempt_recovery(self, issues: List[str]) -> Dict[str, any]:
        """문제 복구 시도"""
        recovery_results = {
            'attempted': 0,
            'succeeded': 0,
            'failed': 0,
            'actions': [],
            'unrecoverable': []
        }

        for issue in issues:
            # 복구 가능한 문제인지 확인
            recovery_func = self._get_recovery_function(issue)

            if not recovery_func:
                recovery_results['unrecoverable'].append(issue)
                self.logger.info(f"복구 불가능한 문제: {issue}")
                continue

            # 이미 너무 많이 시도했는지 확인
            if self._is_max_attempts_reached(issue):
                self.logger.warning(f"최대 복구 시도 횟수 초과: {issue}")
                recovery_results['unrecoverable'].append(f"{issue} (최대 시도 초과)")
                continue

            # 복구 시도
            recovery_results['attempted'] += 1
            self.logger.info(f"복구 시도 시작: {issue}")

            try:
                success, action = recovery_func(issue)

                if success:
                    recovery_results['succeeded'] += 1
                    self.logger.info(f"복구 성공: {issue}")
                else:
                    recovery_results['failed'] += 1
                    self.logger.warning(f"복구 실패: {issue}")

                recovery_results['actions'].append(action)
                self._record_recovery_attempt(issue, action)

            except Exception as e:
                self.logger.error(f"복구 시도 중 오류 ({issue}): {e}", exc_info=True)
                recovery_results['failed'] += 1

                action = RecoveryAction(
                    issue_type=self._classify_issue(issue),
                    action_name="recovery_error",
                    description=f"복구 시도 중 오류 발생: {e}",
                    timestamp=datetime.now().isoformat(),
                    success=False,
                    error_message=str(e)
                )
                recovery_results['actions'].append(action)

        return recovery_results

    def _get_recovery_function(self, issue: str):
        """문제 유형에 따른 복구 함수 반환"""
        issue_lower = issue.lower()

        # 매매 엔진 문제
        if "매매 엔진" in issue and "실행" in issue:
            return self._recover_trading_engine

        # API 연결 문제
        if "api" in issue_lower and ("연결" in issue or "실패" in issue):
            return self._recover_api_connection

        # 일일 선정 파일 문제
        if "일일 선정" in issue and "파일" in issue:
            return self._recover_daily_selection

        # 토큰 만료 문제
        if "토큰" in issue_lower and "만료" in issue_lower:
            return self._recover_expired_token

        # 메모리 부족 문제
        if "메모리" in issue or "memory" in issue_lower:
            return self._recover_memory_issue

        # 복구 불가능
        return None

    def _recover_trading_engine(self, issue: str) -> Tuple[bool, RecoveryAction]:
        """매매 엔진 복구"""
        try:
            self.logger.info("매매 엔진 재시작 시도")

            from ..trading.trading_engine import get_trading_engine, TradingConfig

            # 기본 설정 (싱글톤 최초 생성 시에만 적용)
            config = TradingConfig(
                max_positions=10,
                position_size_method="account_pct",
                position_size_value=0.10,
                stop_loss_pct=0.05,
                take_profit_pct=0.10,
                max_trades_per_day=20
            )

            # 싱글톤 엔진 가져오기 (설정은 최초 생성 시에만 적용)
            engine = get_trading_engine(config)

            # 엔진이 실행 중이 아니면 시작
            if not engine.is_running:

                # 비동기 함수를 동기로 실행
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                except:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # 백그라운드에서 실행
                def start_engine():
                    asyncio.set_event_loop(asyncio.new_event_loop())
                    asyncio.get_event_loop().run_until_complete(engine.start_trading())

                import threading
                thread = threading.Thread(target=start_engine, daemon=True)
                thread.start()

                # 3초 대기 후 상태 확인
                import time
                time.sleep(3)

                if engine.is_running:
                    return True, RecoveryAction(
                        issue_type="trading_engine",
                        action_name="restart_engine",
                        description="매매 엔진을 재시작했습니다",
                        timestamp=datetime.now().isoformat(),
                        success=True
                    )
                else:
                    return False, RecoveryAction(
                        issue_type="trading_engine",
                        action_name="restart_engine",
                        description="매매 엔진 재시작 실패 - 엔진이 시작되지 않음",
                        timestamp=datetime.now().isoformat(),
                        success=False,
                        error_message="Engine did not start"
                    )

            return True, RecoveryAction(
                issue_type="trading_engine",
                action_name="check_engine",
                description="매매 엔진이 이미 실행 중입니다",
                timestamp=datetime.now().isoformat(),
                success=True
            )

        except Exception as e:
            return False, RecoveryAction(
                issue_type="trading_engine",
                action_name="restart_engine",
                description=f"매매 엔진 복구 실패: {e}",
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )

    def _recover_api_connection(self, issue: str) -> Tuple[bool, RecoveryAction]:
        """API 연결 복구"""
        try:
            self.logger.info("API 연결 복구 시도")

            from ..config.api_config import APIConfig

            config = APIConfig()

            # 토큰 갱신 시도
            success = config.ensure_valid_token()

            if success:
                return True, RecoveryAction(
                    issue_type="api_connection",
                    action_name="refresh_token",
                    description="API 토큰을 갱신했습니다",
                    timestamp=datetime.now().isoformat(),
                    success=True
                )
            else:
                return False, RecoveryAction(
                    issue_type="api_connection",
                    action_name="refresh_token",
                    description="API 토큰 갱신 실패",
                    timestamp=datetime.now().isoformat(),
                    success=False,
                    error_message="Token refresh failed"
                )

        except Exception as e:
            return False, RecoveryAction(
                issue_type="api_connection",
                action_name="refresh_token",
                description=f"API 연결 복구 실패: {e}",
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )

    def _recover_daily_selection(self, issue: str) -> Tuple[bool, RecoveryAction]:
        """일일 선정 복구 (DB 우선 확인)"""
        try:
            self.logger.info("일일 선정 복구 시도")

            today = datetime.now().strftime("%Y%m%d")
            today_date = datetime.now().date()

            # === 1. DB에 이미 데이터가 있는지 확인 ===
            try:
                from core.database.session import DatabaseSession
                from core.database.models import SelectionResult

                db = DatabaseSession()
                with db.get_session() as session:
                    count = session.query(SelectionResult).filter(
                        SelectionResult.selection_date == today_date
                    ).count()

                    if count > 0:
                        self.logger.info(f"DB에 오늘 선정 데이터 존재: {count}건 - 복구 불필요")
                        return True, RecoveryAction(
                            issue_type="daily_selection",
                            action_name="db_data_exists",
                            description=f"DB에 오늘 선정 데이터가 이미 존재합니다 ({count}건)",
                            timestamp=datetime.now().isoformat(),
                            success=True
                        )

            except Exception as e:
                self.logger.warning(f"DB 확인 실패: {e}")

            # === 2. JSON 파일 기반 복구 (DB 실패 시 폴백) ===
            today_file = Path(f"data/daily_selection/daily_selection_{today}.json")
            latest_file = Path("data/daily_selection/latest_selection.json")

            # 최신 파일이 있으면 복사
            if latest_file.exists() and not today_file.exists():
                import shutil
                shutil.copy(latest_file, today_file)

                return True, RecoveryAction(
                    issue_type="daily_selection",
                    action_name="copy_latest_selection",
                    description=f"최신 선정 파일을 {today} 파일로 복사했습니다",
                    timestamp=datetime.now().isoformat(),
                    success=True
                )

            # Phase 1 + Phase 2 재실행 시도
            self.logger.info("Phase 1 + Phase 2 재실행 시도")

            # Phase 1 실행 (백그라운드)
            result = subprocess.run(
                ["python3", "phase1_watchlist.py", "screen"],
                cwd=os.getcwd(),
                capture_output=True,
                timeout=300
            )

            if result.returncode == 0:
                # Phase 2 실행
                result2 = subprocess.run(
                    ["python3", "phase2_daily_selection.py", "update"],
                    cwd=os.getcwd(),
                    capture_output=True,
                    timeout=300
                )

                if result2.returncode == 0 and today_file.exists():
                    return True, RecoveryAction(
                        issue_type="daily_selection",
                        action_name="run_phase1_phase2",
                        description="Phase 1 + Phase 2를 재실행하여 일일 선정 파일을 생성했습니다",
                        timestamp=datetime.now().isoformat(),
                        success=True
                    )

            return False, RecoveryAction(
                issue_type="daily_selection",
                action_name="run_phase1_phase2",
                description="Phase 1 + Phase 2 재실행 실패",
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message="Phase execution failed"
            )

        except Exception as e:
            return False, RecoveryAction(
                issue_type="daily_selection",
                action_name="recover_selection_file",
                description=f"일일 선정 파일 복구 실패: {e}",
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )

    def _recover_expired_token(self, issue: str) -> Tuple[bool, RecoveryAction]:
        """만료된 토큰 복구"""
        return self._recover_api_connection(issue)

    def _recover_memory_issue(self, issue: str) -> Tuple[bool, RecoveryAction]:
        """메모리 문제 복구"""
        try:
            self.logger.info("메모리 정리 시도")

            import gc
            gc.collect()

            # 메모리 사용률 확인
            import psutil
            memory = psutil.virtual_memory()

            if memory.percent < 85:
                return True, RecoveryAction(
                    issue_type="memory",
                    action_name="garbage_collection",
                    description=f"메모리 가비지 컬렉션 실행 (현재 사용률: {memory.percent:.1f}%)",
                    timestamp=datetime.now().isoformat(),
                    success=True
                )
            else:
                return False, RecoveryAction(
                    issue_type="memory",
                    action_name="garbage_collection",
                    description=f"메모리 정리 후에도 사용률이 높음 (현재: {memory.percent:.1f}%)",
                    timestamp=datetime.now().isoformat(),
                    success=False,
                    error_message=f"Memory still high: {memory.percent}%"
                )

        except Exception as e:
            return False, RecoveryAction(
                issue_type="memory",
                action_name="garbage_collection",
                description=f"메모리 정리 실패: {e}",
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )

    def _classify_issue(self, issue: str) -> str:
        """문제 분류"""
        issue_lower = issue.lower()

        if "매매 엔진" in issue:
            return "trading_engine"
        elif "api" in issue_lower:
            return "api_connection"
        elif "일일 선정" in issue:
            return "daily_selection"
        elif "토큰" in issue_lower:
            return "token"
        elif "메모리" in issue:
            return "memory"
        else:
            return "unknown"

    def _is_max_attempts_reached(self, issue: str) -> bool:
        """최대 시도 횟수 도달 여부"""
        issue_key = self._classify_issue(issue)
        today = datetime.now().strftime("%Y%m%d")
        key = f"{today}_{issue_key}"

        return self.recovery_history.get(key, 0) >= self.max_recovery_attempts

    def _record_recovery_attempt(self, issue: str, action: RecoveryAction):
        """복구 시도 기록"""
        issue_key = self._classify_issue(issue)
        today = datetime.now().strftime("%Y%m%d")
        key = f"{today}_{issue_key}"

        # 메모리에 기록
        self.recovery_history[key] = self.recovery_history.get(key, 0) + 1

        # 파일에 기록
        try:
            recovery_file = self.data_dir / f"recovery_{today}.json"

            if recovery_file.exists():
                with open(recovery_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = []

            data.append({
                'issue': issue,
                'action': asdict(action),
                'attempt_count': self.recovery_history[key]
            })

            with open(recovery_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            self.logger.error(f"복구 시도 기록 실패: {e}", exc_info=True)

    def send_recovery_report(self, recovery_results: Dict, priority: str = "normal"):
        """복구 결과 리포트 전송"""
        try:
            if not self.notifier.is_enabled():
                return

            # 복구 시도가 없으면 전송하지 않음
            if recovery_results['attempted'] == 0:
                return

            # 메시지 작성
            message = f"""🔧 *자동 복구 시스템 실행*

⏰ 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`

📊 **복구 결과**:
• 시도: {recovery_results['attempted']}건
• 성공: {recovery_results['succeeded']}건
• 실패: {recovery_results['failed']}건
"""

            # 성공한 복구 액션
            successful_actions = [a for a in recovery_results['actions'] if a.success]
            if successful_actions:
                message += "\n✅ **복구 성공**:\n"
                for action in successful_actions:
                    message += f"• {action.description}\n"

            # 실패한 복구 액션
            failed_actions = [a for a in recovery_results['actions'] if not a.success]
            if failed_actions:
                message += "\n❌ **복구 실패**:\n"
                for action in failed_actions[:3]:  # 최대 3개만
                    message += f"• {action.description}\n"

            # 복구 불가능한 문제
            if recovery_results['unrecoverable']:
                message += "\n⚠️ **복구 불가능한 문제**:\n"
                for issue in recovery_results['unrecoverable'][:3]:
                    message += f"• {issue}\n"

            # 우선순위 결정
            if recovery_results['failed'] > recovery_results['succeeded']:
                priority = "high"
            elif recovery_results['succeeded'] == recovery_results['attempted']:
                priority = "normal"

            self.notifier.send_message(message, priority)
            self.logger.info("복구 리포트 전송 완료")

        except Exception as e:
            self.logger.error(f"복구 리포트 전송 실패: {e}", exc_info=True)


# 싱글톤 인스턴스
_recovery_system = None

def get_recovery_system() -> AutoRecoverySystem:
    """자동 복구 시스템 싱글톤 인스턴스 반환"""
    global _recovery_system
    if _recovery_system is None:
        _recovery_system = AutoRecoverySystem()
    return _recovery_system
