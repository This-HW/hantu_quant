"""
가중치 저장소

Task B.2.1: 가중치 버전 관리 시스템
Task B.2.2: 가중치 파일 무결성 검증 (체크섬)
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class WeightVersion:
    """가중치 버전 정보"""
    version_id: str
    weights: Dict[str, float]
    checksum: str
    created_at: str
    description: str = ""
    is_active: bool = False
    performance_metrics: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeightVersion':
        return cls(**data)


class WeightStorage:
    """가중치 저장소"""

    CHECKSUM_ALGORITHM = 'sha256'

    def __init__(self, storage_dir: str = "data/learning/weights"):
        """
        초기화

        Args:
            storage_dir: 저장 디렉토리
        """
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._versions: Dict[str, WeightVersion] = {}
        self._load_all_versions()

        logger.info(f"WeightStorage 초기화 - {len(self._versions)}개 버전 로드")

    def save_version(self,
                    weights: Dict[str, float],
                    description: str = "",
                    performance_metrics: Optional[Dict[str, float]] = None) -> WeightVersion:
        """
        가중치 버전 저장 (B.2.1)

        Args:
            weights: 저장할 가중치
            description: 버전 설명
            performance_metrics: 성능 지표

        Returns:
            생성된 버전 정보
        """
        # 버전 ID 생성
        version_id = self._generate_version_id()

        # 체크섬 계산 (B.2.2)
        checksum = self._calculate_checksum(weights)

        # 버전 객체 생성
        version = WeightVersion(
            version_id=version_id,
            weights=weights.copy(),
            checksum=checksum,
            created_at=datetime.now().isoformat(),
            description=description,
            is_active=False,
            performance_metrics=performance_metrics or {}
        )

        # 저장
        self._versions[version_id] = version
        self._save_version_file(version)
        self._save_registry()

        logger.info(f"가중치 버전 저장: {version_id}")
        return version

    def load_version(self, version_id: str) -> Optional[WeightVersion]:
        """
        특정 버전 로드

        Args:
            version_id: 버전 ID

        Returns:
            버전 정보 (없으면 None)
        """
        version = self._versions.get(version_id)

        if version:
            # 무결성 검증 (B.2.2)
            if not self.verify_checksum(version):
                logger.error(f"가중치 무결성 검증 실패: {version_id}", exc_info=True)
                return None

        return version

    def get_active_version(self) -> Optional[WeightVersion]:
        """활성 버전 조회"""
        for version in self._versions.values():
            if version.is_active:
                return version
        return None

    def set_active_version(self, version_id: str) -> bool:
        """
        활성 버전 설정

        Args:
            version_id: 활성화할 버전 ID

        Returns:
            성공 여부
        """
        if version_id not in self._versions:
            logger.warning(f"존재하지 않는 버전: {version_id}")
            return False

        # 무결성 검증
        version = self._versions[version_id]
        if not self.verify_checksum(version):
            logger.error(f"무결성 검증 실패로 활성화 거부: {version_id}", exc_info=True)
            return False

        # 기존 활성 버전 비활성화
        for v in self._versions.values():
            v.is_active = False

        # 새 버전 활성화
        self._versions[version_id].is_active = True
        self._save_registry()

        logger.info(f"활성 버전 변경: {version_id}")
        return True

    def get_active_weights(self) -> Optional[Dict[str, float]]:
        """활성 버전의 가중치 반환"""
        active = self.get_active_version()
        if active:
            return active.weights.copy()
        return None

    def _calculate_checksum(self, weights: Dict[str, float]) -> str:
        """
        체크섬 계산 (B.2.2)

        Args:
            weights: 가중치

        Returns:
            SHA-256 체크섬
        """
        # 일관된 순서로 직렬화
        sorted_weights = json.dumps(weights, sort_keys=True)
        return hashlib.sha256(sorted_weights.encode()).hexdigest()

    def verify_checksum(self, version: WeightVersion) -> bool:
        """
        체크섬 검증 (B.2.2)

        Args:
            version: 검증할 버전

        Returns:
            검증 성공 여부
        """
        calculated = self._calculate_checksum(version.weights)
        is_valid = calculated == version.checksum

        if not is_valid:
            logger.warning(f"체크섬 불일치: {version.version_id}")
            logger.debug(f"저장된: {version.checksum}")
            logger.debug(f"계산된: {calculated}")

        return is_valid

    def _generate_version_id(self) -> str:
        """버전 ID 생성"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:6]
        return f"w_{timestamp}_{random_suffix}"

    def _save_version_file(self, version: WeightVersion):
        """버전 파일 저장"""
        version_file = self._storage_dir / f"{version.version_id}.json"

        try:
            with open(version_file, 'w', encoding='utf-8') as f:
                json.dump(version.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"버전 파일 저장 실패: {e}", exc_info=True)

    def _save_registry(self):
        """버전 레지스트리 저장"""
        registry_file = self._storage_dir / "weight_registry.json"

        try:
            registry = {
                'versions': {vid: v.to_dict() for vid, v in self._versions.items()},
                'updated_at': datetime.now().isoformat()
            }
            with open(registry_file, 'w', encoding='utf-8') as f:
                json.dump(registry, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"레지스트리 저장 실패: {e}", exc_info=True)

    def _load_all_versions(self):
        """모든 버전 로드"""
        registry_file = self._storage_dir / "weight_registry.json"

        try:
            if registry_file.exists():
                with open(registry_file, 'r', encoding='utf-8') as f:
                    registry = json.load(f)

                versions_data = registry.get('versions', {})
                for vid, vdata in versions_data.items():
                    try:
                        self._versions[vid] = WeightVersion.from_dict(vdata)
                    except Exception as e:
                        logger.warning(f"버전 로드 실패 {vid}: {e}")
        except Exception as e:
            logger.error(f"레지스트리 로드 실패: {e}", exc_info=True)

    def list_versions(self, limit: int = 20) -> List[WeightVersion]:
        """
        버전 목록 조회

        Args:
            limit: 최대 조회 개수

        Returns:
            버전 목록 (최신 순)
        """
        sorted_versions = sorted(
            self._versions.values(),
            key=lambda v: v.created_at,
            reverse=True
        )
        return sorted_versions[:limit]

    def delete_version(self, version_id: str) -> bool:
        """
        버전 삭제

        Args:
            version_id: 삭제할 버전 ID

        Returns:
            성공 여부
        """
        if version_id not in self._versions:
            return False

        version = self._versions[version_id]
        if version.is_active:
            logger.warning("활성 버전은 삭제할 수 없습니다")
            return False

        # 파일 삭제
        version_file = self._storage_dir / f"{version_id}.json"
        try:
            if version_file.exists():
                version_file.unlink()
        except Exception as e:
            logger.warning(f"버전 파일 삭제 실패: {e}")

        # 레지스트리에서 제거
        del self._versions[version_id]
        self._save_registry()

        logger.info(f"버전 삭제: {version_id}")
        return True

    def cleanup_old_versions(self, keep_count: int = 10):
        """
        오래된 버전 정리

        Args:
            keep_count: 유지할 최근 버전 수
        """
        sorted_versions = sorted(
            self._versions.items(),
            key=lambda x: x[1].created_at,
            reverse=True
        )

        for vid, version in sorted_versions[keep_count:]:
            if not version.is_active:
                self.delete_version(vid)

        logger.info(f"버전 정리 완료: {len(self._versions)}개 유지")

    def get_version_summary(self) -> Dict[str, Any]:
        """버전 요약 정보"""
        active = self.get_active_version()

        return {
            'total_versions': len(self._versions),
            'active_version': active.version_id if active else None,
            'active_weights': active.weights if active else None,
            'latest_version': self.list_versions(1)[0].version_id if self._versions else None
        }


# 싱글톤 인스턴스
_storage_instance: Optional[WeightStorage] = None


def get_weight_storage() -> WeightStorage:
    """WeightStorage 싱글톤 인스턴스 반환"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = WeightStorage()
    return _storage_instance
