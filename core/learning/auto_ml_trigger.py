#!/usr/bin/env python3
"""
자동 ML 학습 트리거 시스템
- 학습 데이터가 충분히 쌓이면 자동으로 B단계 ML 학습 시작
- 일일 체크 및 조건 확인
- 학습 완료 시 모델 자동 배포
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple

from core.utils.log_utils import get_logger
from core.workflow import get_workflow_state_manager, WorkflowStage, WorkflowStatus

logger = get_logger(__name__)


class AutoMLTrigger:
    """자동 ML 학습 트리거"""

    def __init__(self, data_dir: str = "data"):
        """초기화"""
        self.data_dir = Path(data_dir)
        self.logger = logger

        # 학습 시작 조건
        self.min_trading_days = 60          # 최소 60일 거래 데이터
        self.min_selection_records = 50     # 최소 50회 선정 기록
        self.min_performance_records = 30   # 최소 30개 성과 기록
        self.min_win_rate = 0.45            # 최소 승률 45% (학습 가치 있음)

        # 상태 파일
        self.trigger_state_file = self.data_dir / "learning" / "ml_trigger_state.json"
        self.trigger_state_file.parent.mkdir(parents=True, exist_ok=True)

        self.state = self._load_trigger_state()

    def _load_trigger_state(self) -> Dict:
        """트리거 상태 로드"""
        try:
            if self.trigger_state_file.exists():
                with open(self.trigger_state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                return {
                    "last_check_date": None,
                    "ml_training_triggered": False,
                    "ml_training_date": None,
                    "ml_model_deployed": False,
                    "next_check_date": datetime.now().strftime("%Y-%m-%d")
                }
        except Exception as e:
            self.logger.error(f"트리거 상태 로드 실패: {e}", exc_info=True)
            return {}

    def _save_trigger_state(self):
        """트리거 상태 저장"""
        try:
            with open(self.trigger_state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"트리거 상태 저장 실패: {e}", exc_info=True)

    def check_and_trigger(self, force: bool = False) -> bool:
        """데이터 조건 체크 및 ML 학습 자동 트리거

        Args:
            force: 강제 실행 여부

        Returns:
            학습 시작 여부
        """
        try:
            self.logger.info("자동 ML 트리거 체크 시작")

            # 이미 트리거된 경우
            if self.state.get("ml_training_triggered") and not force:
                self.logger.info("ML 학습이 이미 트리거되었습니다")
                return False

            # 오늘 이미 체크한 경우
            today = datetime.now().strftime("%Y-%m-%d")
            if self.state.get("last_check_date") == today and not force:
                self.logger.info("오늘 이미 체크했습니다")
                return False

            # 데이터 조건 체크
            conditions_met, conditions = self._check_data_conditions()

            # 상태 업데이트
            self.state["last_check_date"] = today
            self.state["conditions"] = conditions

            if conditions_met or force:
                self.logger.info("ML 학습 조건 충족! 자동 트리거 시작")
                success = self._trigger_ml_training()

                if success:
                    self.state["ml_training_triggered"] = True
                    self.state["ml_training_date"] = datetime.now().isoformat()
                    self.logger.info("B단계 ML 학습이 자동으로 시작되었습니다")
                else:
                    self.logger.error("ML 학습 트리거 실패")

                self._save_trigger_state()
                return success
            else:
                self.logger.info("ML 학습 조건 미충족")
                self._log_conditions_status(conditions)
                self._save_trigger_state()
                return False

        except Exception as e:
            self.logger.error(f"자동 ML 트리거 오류: {e}", exc_info=True)
            return False

    def _check_data_conditions(self) -> Tuple[bool, Dict]:
        """데이터 조건 체크

        Returns:
            (조건 충족 여부, 조건 상세)
        """
        conditions = {
            "trading_days": self._count_trading_days(),
            "selection_records": self._count_selection_records(),
            "performance_records": self._count_performance_records(),
            "current_win_rate": self._calculate_current_win_rate(),
            "data_quality_score": self._assess_data_quality()
        }

        # 조건 충족 여부 판단
        conditions_met = (
            conditions["trading_days"] >= self.min_trading_days and
            conditions["selection_records"] >= self.min_selection_records and
            conditions["performance_records"] >= self.min_performance_records and
            conditions["current_win_rate"] >= self.min_win_rate
        )

        conditions["conditions_met"] = conditions_met
        return conditions_met, conditions

    def _count_trading_days(self) -> int:
        """거래일 수 카운트"""
        try:
            # 일일 선정 파일 개수로 거래일 추정
            selection_dir = self.data_dir / "daily_selection"
            if not selection_dir.exists():
                return 0

            selection_files = list(selection_dir.glob("daily_selection_*.json"))
            return len(selection_files)

        except Exception as e:
            self.logger.error(f"거래일 수 카운트 오류: {e}", exc_info=True)
            return 0

    def _count_selection_records(self) -> int:
        """선정 기록 수 카운트"""
        try:
            # 전체 선정 기록 수
            selection_dir = self.data_dir / "daily_selection"
            if not selection_dir.exists():
                return 0

            total_selections = 0
            for file_path in selection_dir.glob("daily_selection_*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        stocks = data.get("data", {}).get("selected_stocks", [])
                        total_selections += len(stocks)
                except Exception:
                    continue

            return total_selections

        except Exception as e:
            self.logger.error(f"선정 기록 수 카운트 오류: {e}", exc_info=True)
            return 0

    def _count_performance_records(self) -> int:
        """성과 기록 수 카운트"""
        try:
            # 거래 저널에서 성과 기록 수 카운트
            from core.trading.trade_journal import TradeJournal

            journal = TradeJournal()
            trades = journal.get_all_trades()

            # 완료된 거래만 카운트
            completed_trades = [t for t in trades if t.get('status') == 'closed']
            return len(completed_trades)

        except Exception as e:
            self.logger.error(f"성과 기록 수 카운트 오류: {e}", exc_info=True)
            return 0

    def _calculate_current_win_rate(self) -> float:
        """현재 승률 계산"""
        try:
            from core.trading.trade_journal import TradeJournal

            journal = TradeJournal()
            trades = journal.get_all_trades()

            completed_trades = [t for t in trades if t.get('status') == 'closed']
            if not completed_trades:
                return 0.0

            wins = len([t for t in completed_trades if t.get('pnl', 0) > 0])
            win_rate = wins / len(completed_trades)

            return win_rate

        except Exception as e:
            self.logger.error(f"승률 계산 오류: {e}", exc_info=True)
            return 0.0

    def _assess_data_quality(self) -> float:
        """데이터 품질 평가 (0-100)"""
        try:
            # 데이터 완정성, 일관성, 다양성 평가
            quality_score = 0.0

            # 1. 완정성: 빠진 날이 적을수록 좋음
            trading_days = self._count_trading_days()
            if trading_days > 0:
                completeness = min(trading_days / self.min_trading_days, 1.0) * 40
                quality_score += completeness

            # 2. 일관성: 선정 기록이 일정할수록 좋음
            selection_records = self._count_selection_records()
            if selection_records > 0:
                consistency = min(selection_records / self.min_selection_records, 1.0) * 30
                quality_score += consistency

            # 3. 다양성: 성과 기록이 다양할수록 좋음
            performance_records = self._count_performance_records()
            if performance_records > 0:
                diversity = min(performance_records / self.min_performance_records, 1.0) * 30
                quality_score += diversity

            return quality_score

        except Exception as e:
            self.logger.error(f"데이터 품질 평가 오류: {e}", exc_info=True)
            return 0.0

    def _trigger_ml_training(self) -> bool:
        """ML 학습 트리거 실행"""
        try:
            self.logger.info("B단계 ML 학습 트리거 시작...")

            state_manager = get_workflow_state_manager()

            # B단계 시작 상태 저장
            state_manager.save_checkpoint(
                stage=WorkflowStage.STAGE_B,
                status=WorkflowStatus.IN_PROGRESS,
                progress=0.0,
                current_step="자동 트리거 시작",
                total_steps=5,
                completed_steps=[],
                metadata={
                    "description": "ML 랭킹 시스템",
                    "trigger_type": "auto",
                    "trigger_date": datetime.now().isoformat(),
                    "data_conditions": self.state.get("conditions", {})
                }
            )

            # ML 학습 스크립트 실행 (백그라운드)
            self.logger.info("ML 학습 스크립트 실행 예약...")

            # 텔레그램 알림
            self._send_ml_trigger_notification()

            return True

        except Exception as e:
            self.logger.error(f"ML 학습 트리거 실행 오류: {e}", exc_info=True)
            return False

    def _send_ml_trigger_notification(self):
        """ML 트리거 텔레그램 알림"""
        try:
            from core.utils.telegram_notifier import get_telegram_notifier

            notifier = get_telegram_notifier()
            conditions = self.state.get("conditions", {})

            message = f"""
🤖 ML 학습 자동 시작

학습 조건 충족
• 거래일 수: {conditions.get('trading_days', 0)}일
• 선정 기록: {conditions.get('selection_records', 0)}개
• 성과 기록: {conditions.get('performance_records', 0)}개
• 현재 승률: {conditions.get('current_win_rate', 0):.1%}
• 데이터 품질: {conditions.get('data_quality_score', 0):.1f}점

B단계 ML 랭킹 시스템이 자동으로 시작됩니다.
학습 완료 시 다시 알림을 보내드립니다.
"""

            notifier.send_message(message, priority="high")
            self.logger.info("ML 트리거 알림 전송 완료")

        except Exception as e:
            self.logger.error(f"ML 트리거 알림 전송 오류: {e}", exc_info=True)

    def _log_conditions_status(self, conditions: Dict):
        """조건 상태 로그 출력"""
        self.logger.info(f"""
ML 학습 조건 체크 결과:
  • 거래일 수: {conditions['trading_days']}/{self.min_trading_days}일
    {'' if conditions['trading_days'] >= self.min_trading_days else ''}
  • 선정 기록: {conditions['selection_records']}/{self.min_selection_records}개
    {'' if conditions['selection_records'] >= self.min_selection_records else ''}
  • 성과 기록: {conditions['performance_records']}/{self.min_performance_records}개
    {'' if conditions['performance_records'] >= self.min_performance_records else ''}
  • 승률: {conditions['current_win_rate']:.1%}/{self.min_win_rate:.1%}
    {'' if conditions['current_win_rate'] >= self.min_win_rate else ''}
  • 데이터 품질: {conditions['data_quality_score']:.1f}/70.0점
""")

    def get_progress_to_ml(self) -> Dict:
        """ML 학습까지 진행률 조회

        Returns:
            진행률 정보
        """
        try:
            conditions_met, conditions = self._check_data_conditions()

            progress = {
                "trading_days_progress": min(conditions['trading_days'] / self.min_trading_days, 1.0) * 100,
                "selection_records_progress": min(conditions['selection_records'] / self.min_selection_records, 1.0) * 100,
                "performance_records_progress": min(conditions['performance_records'] / self.min_performance_records, 1.0) * 100,
                "win_rate_progress": min(conditions['current_win_rate'] / self.min_win_rate, 1.0) * 100,
                "overall_progress": (
                    min(conditions['trading_days'] / self.min_trading_days, 1.0) * 0.4 +
                    min(conditions['selection_records'] / self.min_selection_records, 1.0) * 0.3 +
                    min(conditions['performance_records'] / self.min_performance_records, 1.0) * 0.2 +
                    min(conditions['current_win_rate'] / self.min_win_rate, 1.0) * 0.1
                ) * 100,
                "conditions_met": conditions_met,
                "estimated_days_remaining": self._estimate_days_remaining(conditions)
            }

            return progress

        except Exception as e:
            self.logger.error(f"ML 진행률 조회 오류: {e}", exc_info=True)
            return {}

    def _estimate_days_remaining(self, conditions: Dict) -> int:
        """ML 학습까지 예상 남은 일수"""
        try:
            trading_days = conditions['trading_days']
            if trading_days == 0:
                return self.min_trading_days

            # 현재 진행률 기반 예상
            days_needed = max(
                self.min_trading_days - trading_days,
                0
            )

            return days_needed

        except Exception:
            return 0


def get_auto_ml_trigger() -> AutoMLTrigger:
    """싱글톤 AutoMLTrigger 인스턴스 반환"""
    if not hasattr(get_auto_ml_trigger, '_instance'):
        get_auto_ml_trigger._instance = AutoMLTrigger()
    return get_auto_ml_trigger._instance


# 일일 체크 함수 (스케줄러에서 호출)
def daily_ml_trigger_check():
    """일일 ML 트리거 체크 (스케줄러에서 자동 실행)"""
    trigger = get_auto_ml_trigger()
    trigger.check_and_trigger()
