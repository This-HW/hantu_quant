#!/usr/bin/env python3
"""
워크플로우 상태 관리 시스템
- 작업 진행 상태 저장/복원
- 중단된 작업 이어서 진행
- 작업 이력 추적
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class WorkflowStage(Enum):
    """워크플로우 단계"""
    STAGE_A = "stage_a"  # 선정 기준 강화
    STAGE_D = "stage_d"  # 포트폴리오 최적화
    STAGE_C = "stage_c"  # 멀티 팩터 앙상블
    STAGE_B = "stage_b"  # ML 랭킹 시스템


class WorkflowStatus(Enum):
    """작업 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class WorkflowCheckpoint:
    """워크플로우 체크포인트"""
    stage: str
    status: str
    timestamp: str
    progress_percentage: float
    current_step: str
    total_steps: int
    completed_steps: List[str]
    metadata: Dict[str, Any]
    error_message: Optional[str] = None


class WorkflowStateManager:
    """워크플로우 상태 관리자"""

    def __init__(self, state_dir: str = "data/workflow_state"):
        """초기화"""
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.state_dir / "workflow_state.json"
        self.history_file = self.state_dir / "workflow_history.json"

        self.current_state = self._load_current_state()
        logger.info("WorkflowStateManager 초기화 완료")

    def _load_current_state(self) -> Dict[str, WorkflowCheckpoint]:
        """현재 상태 로드"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                state = {}
                for stage_name, checkpoint_data in data.items():
                    state[stage_name] = WorkflowCheckpoint(**checkpoint_data)

                logger.info(f"워크플로우 상태 로드 완료: {len(state)}개 단계")
                return state
            else:
                logger.info("새로운 워크플로우 상태 생성")
                return {}

        except Exception as e:
            logger.error(f"워크플로우 상태 로드 실패: {e}", exc_info=True)
            return {}

    def save_checkpoint(self, stage: WorkflowStage, status: WorkflowStatus,
                       progress: float, current_step: str, total_steps: int,
                       completed_steps: List[str], metadata: Dict[str, Any],
                       error_message: Optional[str] = None):
        """체크포인트 저장"""
        try:
            checkpoint = WorkflowCheckpoint(
                stage=stage.value,
                status=status.value,
                timestamp=datetime.now().isoformat(),
                progress_percentage=progress,
                current_step=current_step,
                total_steps=total_steps,
                completed_steps=completed_steps,
                metadata=metadata,
                error_message=error_message
            )

            self.current_state[stage.value] = checkpoint

            # 파일 저장
            state_data = {
                stage_name: asdict(checkpoint)
                for stage_name, checkpoint in self.current_state.items()
            }

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)

            logger.info(f"체크포인트 저장: {stage.value} - {status.value} ({progress:.1f}%)")

            # 히스토리에도 기록
            self._append_to_history(checkpoint)

        except Exception as e:
            logger.error(f"체크포인트 저장 실패: {e}", exc_info=True)

    def _append_to_history(self, checkpoint: WorkflowCheckpoint):
        """히스토리에 기록 추가"""
        try:
            history = []
            if self.history_file.exists():
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)

            history.append(asdict(checkpoint))

            # 최근 100개만 유지
            history = history[-100:]

            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"히스토리 기록 실패: {e}", exc_info=True)

    def get_checkpoint(self, stage: WorkflowStage) -> Optional[WorkflowCheckpoint]:
        """특정 단계의 체크포인트 조회"""
        return self.current_state.get(stage.value)

    def get_next_pending_stage(self) -> Optional[WorkflowStage]:
        """다음 대기 중인 단계 조회"""
        stage_order = [
            WorkflowStage.STAGE_A,
            WorkflowStage.STAGE_D,
            WorkflowStage.STAGE_C,
            WorkflowStage.STAGE_B
        ]

        for stage in stage_order:
            checkpoint = self.get_checkpoint(stage)
            if checkpoint is None or checkpoint.status in [WorkflowStatus.PENDING.value, WorkflowStatus.PAUSED.value]:
                return stage

        return None

    def get_incomplete_stages(self) -> List[WorkflowStage]:
        """미완료 단계 목록 조회"""
        incomplete = []

        for stage in WorkflowStage:
            checkpoint = self.get_checkpoint(stage)
            if checkpoint is None or checkpoint.status != WorkflowStatus.COMPLETED.value:
                incomplete.append(stage)

        return incomplete

    def is_stage_completed(self, stage: WorkflowStage) -> bool:
        """단계 완료 여부 확인"""
        checkpoint = self.get_checkpoint(stage)
        return checkpoint is not None and checkpoint.status == WorkflowStatus.COMPLETED.value

    def get_progress_summary(self) -> Dict[str, Any]:
        """전체 진행 상황 요약"""
        total_stages = len(WorkflowStage)
        completed_stages = sum(1 for stage in WorkflowStage if self.is_stage_completed(stage))

        stages_status = {}
        for stage in WorkflowStage:
            checkpoint = self.get_checkpoint(stage)
            if checkpoint:
                stages_status[stage.value] = {
                    "status": checkpoint.status,
                    "progress": checkpoint.progress_percentage,
                    "current_step": checkpoint.current_step,
                    "completed_steps": len(checkpoint.completed_steps),
                    "total_steps": checkpoint.total_steps
                }
            else:
                stages_status[stage.value] = {
                    "status": WorkflowStatus.PENDING.value,
                    "progress": 0.0,
                    "current_step": "Not started",
                    "completed_steps": 0,
                    "total_steps": 0
                }

        return {
            "total_stages": total_stages,
            "completed_stages": completed_stages,
            "overall_progress": (completed_stages / total_stages) * 100,
            "stages": stages_status,
            "next_stage": self.get_next_pending_stage().value if self.get_next_pending_stage() else None
        }

    def reset_stage(self, stage: WorkflowStage):
        """특정 단계 초기화"""
        if stage.value in self.current_state:
            del self.current_state[stage.value]
            self._save_state()
            logger.info(f"단계 초기화: {stage.value}")

    def reset_all(self):
        """전체 상태 초기화"""
        self.current_state = {}
        self._save_state()
        logger.info("전체 워크플로우 상태 초기화")

    def _save_state(self):
        """상태 파일 저장"""
        try:
            state_data = {
                stage_name: asdict(checkpoint)
                for stage_name, checkpoint in self.current_state.items()
            }

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"상태 저장 실패: {e}", exc_info=True)

    def print_progress(self):
        """진행 상황 출력"""
        summary = self.get_progress_summary()

        print("\n" + "=" * 80)
        print("📊 알고리즘 업그레이드 진행 상황")
        print("=" * 80)
        print(f"전체 진행률: {summary['overall_progress']:.1f}% ({summary['completed_stages']}/{summary['total_stages']} 완료)")
        print()

        for stage_name, stage_info in summary['stages'].items():
            status_icon = {
                "completed": "✅",
                "in_progress": "⏳",
                "failed": "❌",
                "pending": "⏸️",
                "paused": "⏸️"
            }.get(stage_info['status'], "❓")

            print(f"{status_icon} {stage_name.upper()}: {stage_info['status']}")
            print(f"   진행률: {stage_info['progress']:.1f}%")
            print(f"   현재 단계: {stage_info['current_step']}")
            print(f"   완료 단계: {stage_info['completed_steps']}/{stage_info['total_steps']}")
            print()

        if summary['next_stage']:
            print(f"다음 작업: {summary['next_stage'].upper()}")
        else:
            print("🎉 모든 단계 완료!")

        print("=" * 80)


def get_workflow_state_manager() -> WorkflowStateManager:
    """싱글톤 WorkflowStateManager 인스턴스 반환"""
    if not hasattr(get_workflow_state_manager, '_instance'):
        get_workflow_state_manager._instance = WorkflowStateManager()
    return get_workflow_state_manager._instance
