"""
재학습 이력 관리

Task A.3.1: 재학습 이력 저장 구조
Task A.3.2: 재학습 알림 (Telegram 연동)
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class RetrainRecord:
    """재학습 기록"""
    record_id: str
    started_at: str
    completed_at: Optional[str]
    status: str  # 'success', 'failed', 'in_progress'

    # 학습 정보
    model_version: str
    previous_version: Optional[str]
    training_samples: int
    training_time_seconds: float

    # 성능 지표
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    improvement: float = 0.0

    # 트리거 정보
    trigger_reasons: List[str] = field(default_factory=list)

    # 기타 메타데이터
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RetrainRecord':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class RetrainHistory:
    """재학습 이력 관리자"""

    def __init__(self, history_dir: str = "data/learning/retrain_history"):
        """
        초기화

        Args:
            history_dir: 이력 저장 디렉토리
        """
        self._history_dir = Path(history_dir)
        self._history_dir.mkdir(parents=True, exist_ok=True)

        self._records: Dict[str, RetrainRecord] = {}
        self._load_all_records()

        logger.info(f"RetrainHistory 초기화 - {len(self._records)}개 기록 로드")

    def add_record(self, record: RetrainRecord) -> str:
        """
        재학습 기록 추가 (A.3.1)

        Args:
            record: 재학습 기록

        Returns:
            기록 ID
        """
        self._records[record.record_id] = record
        self._save_record(record)
        self._save_index()

        logger.info(f"재학습 기록 추가: {record.record_id}")
        return record.record_id

    def update_record(self, record_id: str, **updates) -> bool:
        """
        재학습 기록 업데이트

        Args:
            record_id: 기록 ID
            **updates: 업데이트할 필드들

        Returns:
            성공 여부
        """
        if record_id not in self._records:
            return False

        record = self._records[record_id]

        for key, value in updates.items():
            if hasattr(record, key):
                setattr(record, key, value)

        self._save_record(record)
        return True

    def get_record(self, record_id: str) -> Optional[RetrainRecord]:
        """기록 조회"""
        return self._records.get(record_id)

    def get_latest_records(self, limit: int = 10) -> List[RetrainRecord]:
        """
        최근 기록 조회

        Args:
            limit: 최대 조회 개수

        Returns:
            최근 기록 목록 (최신 순)
        """
        sorted_records = sorted(
            self._records.values(),
            key=lambda r: r.started_at,
            reverse=True
        )
        return sorted_records[:limit]

    def get_success_rate(self, days: int = 30) -> float:
        """
        재학습 성공률 조회

        Args:
            days: 조회 기간 (일)

        Returns:
            성공률 (0.0 ~ 1.0)
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        recent_records = [
            r for r in self._records.values()
            if r.started_at >= cutoff and r.status != 'in_progress'
        ]

        if not recent_records:
            return 0.0

        success_count = sum(1 for r in recent_records if r.status == 'success')
        return success_count / len(recent_records)

    def get_average_improvement(self, days: int = 30) -> float:
        """
        평균 개선율 조회

        Args:
            days: 조회 기간 (일)

        Returns:
            평균 개선율
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        recent_records = [
            r for r in self._records.values()
            if r.started_at >= cutoff and r.status == 'success'
        ]

        if not recent_records:
            return 0.0

        return sum(r.improvement for r in recent_records) / len(recent_records)

    def get_summary(self) -> Dict[str, Any]:
        """이력 요약 정보"""
        total = len(self._records)
        success = sum(1 for r in self._records.values() if r.status == 'success')
        failed = sum(1 for r in self._records.values() if r.status == 'failed')

        latest = self.get_latest_records(1)
        latest_record = latest[0] if latest else None

        return {
            'total_retrains': total,
            'successful_retrains': success,
            'failed_retrains': failed,
            'success_rate': success / total if total > 0 else 0.0,
            'success_rate_30d': self.get_success_rate(30),
            'average_improvement_30d': self.get_average_improvement(30),
            'latest_retrain': latest_record.to_dict() if latest_record else None
        }

    def notify_retrain_complete(self, record: RetrainRecord):
        """
        재학습 완료 알림 발송 (A.3.2)

        Args:
            record: 재학습 기록
        """
        try:
            from core.utils.telegram_notifier import get_telegram_notifier

            notifier = get_telegram_notifier()

            if record.status == 'success':
                emoji = "✅"
                status_text = "성공"
            else:
                emoji = "❌"
                status_text = "실패"

            message = f"""
{emoji} 모델 재학습 {status_text}

📌 버전: {record.model_version}
📊 정확도: {record.accuracy:.2%}
📈 개선율: {record.improvement:+.2%}
⏱️ 소요시간: {record.training_time_seconds:.1f}초
📦 학습 샘플: {record.training_samples:,}개

🔄 이전 버전: {record.previous_version or 'N/A'}
📋 트리거: {', '.join(record.trigger_reasons) or 'N/A'}
"""

            if record.error_message:
                message += f"\n⚠️ 오류: {record.error_message}"

            notifier.send_message(message, priority="high" if record.status == 'failed' else "normal")
            logger.info("재학습 완료 알림 발송")

        except Exception as e:
            logger.warning(f"재학습 알림 발송 실패: {e}")

    def notify_retrain_started(self, record: RetrainRecord):
        """재학습 시작 알림"""
        try:
            from core.utils.telegram_notifier import get_telegram_notifier

            notifier = get_telegram_notifier()

            message = f"""
🔄 모델 재학습 시작

📋 트리거 사유: {', '.join(record.trigger_reasons) or 'N/A'}
📦 학습 샘플: {record.training_samples:,}개
🔄 이전 버전: {record.previous_version or 'N/A'}
⏰ 시작 시간: {record.started_at[:19]}
"""

            notifier.send_message(message, priority="normal")

        except Exception as e:
            logger.warning(f"재학습 시작 알림 발송 실패: {e}")

    def _save_record(self, record: RetrainRecord):
        """기록 파일 저장"""
        record_file = self._history_dir / f"{record.record_id}.json"

        try:
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"기록 저장 실패: {e}")

    def _save_index(self):
        """인덱스 파일 저장"""
        index_file = self._history_dir / "index.json"

        try:
            index = {
                'records': list(self._records.keys()),
                'updated_at': datetime.now().isoformat()
            }
            with open(index_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"인덱스 저장 실패: {e}")

    def _load_all_records(self):
        """모든 기록 로드"""
        for record_file in self._history_dir.glob("retrain_*.json"):
            try:
                with open(record_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    record = RetrainRecord.from_dict(data)
                    self._records[record.record_id] = record
            except Exception as e:
                logger.warning(f"기록 로드 실패 {record_file}: {e}")

    def cleanup_old_records(self, keep_days: int = 90):
        """오래된 기록 정리"""
        cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()

        to_delete = [
            rid for rid, record in self._records.items()
            if record.started_at < cutoff
        ]

        for rid in to_delete:
            record_file = self._history_dir / f"{rid}.json"
            try:
                if record_file.exists():
                    record_file.unlink()
                del self._records[rid]
            except Exception as e:
                logger.warning(f"기록 삭제 실패 {rid}: {e}")

        if to_delete:
            self._save_index()
            logger.info(f"오래된 기록 {len(to_delete)}개 정리")


# 싱글톤 인스턴스
_history_instance: Optional[RetrainHistory] = None


def get_retrain_history() -> RetrainHistory:
    """RetrainHistory 싱글톤 인스턴스 반환"""
    global _history_instance
    if _history_instance is None:
        _history_instance = RetrainHistory()
    return _history_instance
