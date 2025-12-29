"""
모델 핫스왑 시스템

Task A.2.4: 모델 핫스왑 - 서비스 중단 없이 모델 교체
"""

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, asdict
import json

from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ModelInfo:
    """모델 정보"""
    version: str
    loaded_at: str
    model_path: str
    accuracy: float = 0.0
    is_active: bool = False


class ModelSwapper:
    """모델 핫스왑 시스템"""

    def __init__(self,
                 model_dir: str = "data/models",
                 swap_timeout_seconds: int = 30):
        """
        초기화

        Args:
            model_dir: 모델 디렉토리
            swap_timeout_seconds: 스왑 타임아웃 (초)
        """
        self._model_dir = Path(model_dir)
        self._swap_timeout = swap_timeout_seconds

        # 현재 활성 모델
        self._active_model: Optional[Any] = None
        self._active_model_info: Optional[ModelInfo] = None

        # 대기 모델 (핫스왑 준비)
        self._standby_model: Optional[Any] = None
        self._standby_model_info: Optional[ModelInfo] = None

        # 스왑 동기화
        self._swap_lock = threading.RLock()
        self._is_swapping = False

        # 모델 로더 (외부 주입)
        self._model_loader: Optional[Callable] = None

        logger.info("ModelSwapper 초기화 완료")

    def set_model_loader(self, loader: Callable[[str], Any]):
        """
        모델 로더 설정

        Args:
            loader: 모델 버전을 받아 모델 객체를 반환하는 함수
        """
        self._model_loader = loader

    def get_active_model(self) -> Optional[Any]:
        """
        현재 활성 모델 반환 (스레드 안전)

        Returns:
            활성 모델 또는 None
        """
        with self._swap_lock:
            return self._active_model

    def get_active_model_info(self) -> Optional[ModelInfo]:
        """활성 모델 정보 반환"""
        with self._swap_lock:
            return self._active_model_info

    def prepare_standby_model(self, version: str) -> bool:
        """
        대기 모델 준비 (백그라운드 로드)

        Args:
            version: 로드할 모델 버전

        Returns:
            준비 성공 여부
        """
        if not self._model_loader:
            logger.error("모델 로더가 설정되지 않음")
            return False

        try:
            logger.info(f"대기 모델 로드 시작: {version}")

            # 모델 로드 (시간 소요될 수 있음)
            model = self._model_loader(version)

            if model is None:
                logger.error(f"모델 로드 실패: {version}")
                return False

            # 대기 모델 설정
            with self._swap_lock:
                self._standby_model = model
                self._standby_model_info = ModelInfo(
                    version=version,
                    loaded_at=datetime.now().isoformat(),
                    model_path=str(self._model_dir / f"model_{version}.pkl"),
                    is_active=False
                )

            logger.info(f"대기 모델 준비 완료: {version}")
            return True

        except Exception as e:
            logger.error(f"대기 모델 준비 실패: {e}")
            return False

    def swap(self, immediate: bool = False) -> bool:
        """
        모델 핫스왑 실행

        Args:
            immediate: 즉시 스왑 (대기 없이)

        Returns:
            스왑 성공 여부
        """
        with self._swap_lock:
            if self._is_swapping:
                logger.warning("이미 스왑 진행 중")
                return False

            if self._standby_model is None:
                logger.warning("대기 모델이 없음")
                return False

            self._is_swapping = True

        try:
            start_time = time.time()

            # 스왑 전 상태 백업
            old_model = self._active_model
            old_info = self._active_model_info

            # 원자적 스왑 (락 내에서)
            with self._swap_lock:
                self._active_model = self._standby_model
                self._active_model_info = self._standby_model_info
                self._active_model_info.is_active = True

                # 대기 모델 클리어
                self._standby_model = None
                self._standby_model_info = None

            swap_time = time.time() - start_time

            # 스왑 완료 로그
            old_version = old_info.version if old_info else "None"
            new_version = self._active_model_info.version

            logger.info(f"모델 스왑 완료: {old_version} → {new_version} "
                       f"(소요시간: {swap_time*1000:.1f}ms)")

            # 이전 모델 정리 (비동기)
            if old_model and not immediate:
                threading.Thread(
                    target=self._cleanup_old_model,
                    args=(old_model, old_version),
                    daemon=True
                ).start()

            return True

        except Exception as e:
            logger.error(f"모델 스왑 실패: {e}")
            return False

        finally:
            with self._swap_lock:
                self._is_swapping = False

    def swap_with_fallback(self, version: str, fallback_version: Optional[str] = None) -> bool:
        """
        폴백을 포함한 모델 스왑

        Args:
            version: 스왑할 모델 버전
            fallback_version: 실패 시 폴백 버전

        Returns:
            스왑 성공 여부
        """
        # 1. 대기 모델 준비
        if not self.prepare_standby_model(version):
            if fallback_version:
                logger.warning(f"폴백 모델로 전환 시도: {fallback_version}")
                if not self.prepare_standby_model(fallback_version):
                    return False
            else:
                return False

        # 2. 스왑 실행
        return self.swap()

    def rollback(self) -> bool:
        """
        이전 모델로 롤백

        Returns:
            롤백 성공 여부
        """
        # 마지막 활성 모델 기록에서 이전 버전 찾기
        history = self._load_swap_history()

        if len(history) < 2:
            logger.warning("롤백할 이전 모델이 없음")
            return False

        previous_version = history[-2].get('version')
        if not previous_version:
            return False

        logger.info(f"이전 모델로 롤백: {previous_version}")
        return self.swap_with_fallback(previous_version)

    def _cleanup_old_model(self, model: Any, version: str):
        """이전 모델 정리"""
        try:
            # 잠시 대기 (진행 중인 요청 완료 대기)
            time.sleep(5)

            # 모델 리소스 해제 (있다면)
            if hasattr(model, 'cleanup'):
                model.cleanup()
            elif hasattr(model, 'close'):
                model.close()

            logger.debug(f"이전 모델 정리 완료: {version}")

        except Exception as e:
            logger.warning(f"이전 모델 정리 중 오류: {e}")

    def _load_swap_history(self) -> list:
        """스왑 이력 로드"""
        history_file = self._model_dir / "swap_history.json"

        try:
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass

        return []

    def _save_swap_history(self):
        """스왑 이력 저장"""
        if not self._active_model_info:
            return

        history_file = self._model_dir / "swap_history.json"
        history = self._load_swap_history()

        history.append({
            'version': self._active_model_info.version,
            'swapped_at': datetime.now().isoformat()
        })

        # 최근 20개만 유지
        history = history[-20:]

        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"스왑 이력 저장 실패: {e}")

    def get_status(self) -> Dict[str, Any]:
        """스왑퍼 상태 조회"""
        with self._swap_lock:
            return {
                'has_active_model': self._active_model is not None,
                'active_model_info': asdict(self._active_model_info) if self._active_model_info else None,
                'has_standby_model': self._standby_model is not None,
                'standby_model_info': asdict(self._standby_model_info) if self._standby_model_info else None,
                'is_swapping': self._is_swapping
            }


# 싱글톤 인스턴스
_swapper_instance: Optional[ModelSwapper] = None


def get_model_swapper() -> ModelSwapper:
    """ModelSwapper 싱글톤 인스턴스 반환"""
    global _swapper_instance
    if _swapper_instance is None:
        _swapper_instance = ModelSwapper()
    return _swapper_instance
