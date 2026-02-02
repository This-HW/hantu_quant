"""
데이터 수집 서비스 모듈

Phase 1/2 결과를 수집하여 AI 학습 시스템에 전달합니다.
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class DataCollectionService:
    """데이터 수집 서비스 클래스

    Phase 1/2의 실행 결과를 수집하고 AI 학습용 데이터로 변환합니다.

    Features:
        - Phase 1 스크리닝 데이터 수집
        - Phase 2 선정 데이터 수집
        - AI 학습용 통합 데이터 생성
        - 피드백 시스템 업데이트
        - 파일 크기 제한 처리
    """

    def __init__(
        self,
        screening_dir: str = "data/watchlist",
        selection_file: str = "data/daily_selection/latest_selection.json",
        ai_raw_data_dir: str = "data/learning/raw_data",
        ai_feedback_dir: str = "data/learning/feedback",
        max_file_size_mb: float = 1.0,
    ):
        """초기화

        Args:
            screening_dir: Phase 1 스크리닝 결과 디렉토리
            selection_file: Phase 2 선정 결과 파일
            ai_raw_data_dir: AI 학습 원본 데이터 디렉토리
            ai_feedback_dir: AI 피드백 데이터 디렉토리
            max_file_size_mb: 파일 크기 제한 (MB)
        """
        self.screening_dir = Path(screening_dir)
        self.selection_file = Path(selection_file)
        self.ai_raw_data_dir = Path(ai_raw_data_dir)
        self.ai_feedback_dir = Path(ai_feedback_dir)
        self.max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)

        # 디렉토리 생성
        self.ai_raw_data_dir.mkdir(parents=True, exist_ok=True)
        self.ai_feedback_dir.mkdir(parents=True, exist_ok=True)

    def collect_phase1_data(self) -> Dict[str, Any]:
        """Phase 1 스크리닝 데이터 수집

        최신 스크리닝 결과 파일을 찾아 데이터를 수집합니다.
        파일이 너무 큰 경우 요약 정보만 반환합니다.

        Returns:
            Phase 1 데이터 딕셔너리
        """
        try:
            if not self.screening_dir.exists():
                logger.warning(f"스크리닝 디렉토리가 존재하지 않음: {self.screening_dir}")
                return {"status": "directory_not_found"}

            # screening_results_*.json 파일 찾기 (Path.glob 사용)
            screening_files = [
                f.name
                for f in self.screening_dir.glob("screening_results_*.json")
                if f.is_file()
            ]

            if not screening_files:
                logger.warning("스크리닝 결과 파일을 찾을 수 없음")
                return {
                    "status": "no_results",
                    "total_screened_stocks": 0,
                    "watchlist_stocks": 0,
                }

            # 최신 파일 선택
            latest_file = max(screening_files)
            screening_file_path = self.screening_dir / latest_file

            # 파일 크기 확인
            file_size = screening_file_path.stat().st_size

            if file_size > self.max_file_size_bytes:
                # 파일이 너무 큰 경우 요약만 반환
                logger.info(
                    f"스크리닝 파일이 큼 ({file_size / (1024 * 1024):.2f} MB) - 요약만 반환"
                )
                return {
                    "file_name": latest_file,
                    "file_size_mb": round(file_size / (1024 * 1024), 2),
                    "status": "large_file_summarized",
                    "total_screened_stocks": None,  # 파일이 커서 정확한 수치 알 수 없음
                }

            # 파일 읽기 시도
            try:
                with open(screening_file_path, "r", encoding="utf-8") as f:
                    screening_data = json.load(f)

                # 데이터 구조 파싱
                total_screened = len(screening_data.get("results", []))
                watchlist_count = len(
                    [r for r in screening_data.get("results", []) if r.get("in_watchlist")]
                )

                return {
                    "file_name": latest_file,
                    "total_screened_stocks": total_screened,
                    "watchlist_stocks": watchlist_count,
                    "status": "completed",
                }
            except json.JSONDecodeError as e:
                logger.error(f"스크리닝 파일 JSON 파싱 실패: {e}", exc_info=True)
                return {"status": "json_error", "error": str(e)}

        except Exception as e:
            logger.error(f"Phase 1 데이터 수집 오류: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def collect_phase2_data(self) -> Dict[str, Any]:
        """Phase 2 선정 데이터 수집

        최신 일일 선정 결과를 읽어 데이터를 수집합니다.

        Returns:
            Phase 2 데이터 딕셔너리
        """
        try:
            if not self.selection_file.exists():
                logger.warning(f"선정 결과 파일이 존재하지 않음: {self.selection_file}")
                return {
                    "total_selected_stocks": 0,
                    "status": "file_not_found",
                }

            with open(self.selection_file, "r", encoding="utf-8") as f:
                selection_data = json.load(f)

            # 다양한 데이터 형식 지원
            if isinstance(selection_data, list):
                selected_stocks = selection_data
                filtering_criteria = {}
                market_condition = "neutral"
            elif isinstance(selection_data, dict):
                selected_stocks = (
                    selection_data.get("data", {}).get("selected_stocks", [])
                    or selection_data.get("stocks", [])
                )
                filtering_criteria = (
                    selection_data.get("metadata", {}).get("filtering_criteria", {})
                )
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

        except json.JSONDecodeError as e:
            logger.error(f"선정 결과 파일 JSON 파싱 실패: {e}", exc_info=True)
            return {"status": "json_error", "error": str(e)}
        except Exception as e:
            logger.error(f"Phase 2 데이터 수집 오류: {e}", exc_info=True)
            return {"status": "error", "error": str(e)}

    def send_ai_data(self) -> bool:
        """Phase 1,2 완료 후 AI 학습 시스템에 데이터 전달

        두 Phase의 데이터를 통합하여 AI 학습용 데이터로 저장합니다.

        Returns:
            성공 여부
        """
        try:
            logger.info("=== AI 학습 시스템 데이터 연동 시작 ===")

            # Phase 1 스크리닝 결과 수집
            screening_data = self.collect_phase1_data()

            # Phase 2 선정 결과 수집
            selection_data = self.collect_phase2_data()

            # AI 학습용 통합 데이터 생성
            ai_learning_data = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "timestamp": datetime.now().isoformat(),
                "phase1_screening": screening_data,
                "phase2_selection": selection_data,
                "integration_status": "completed",
            }

            # AI 학습 데이터 저장
            ai_data_file = (
                self.ai_raw_data_dir
                / f"daily_integration_{datetime.now().strftime('%Y%m%d')}.json"
            )

            with open(ai_data_file, "w", encoding="utf-8") as f:
                json.dump(ai_learning_data, f, indent=2, ensure_ascii=False)

            logger.info(f"AI 학습 데이터 저장 완료: {ai_data_file}")

            # 피드백 시스템에 데이터 전달
            self.update_feedback(ai_learning_data)

            logger.info("AI 학습 시스템 데이터 연동 완료")
            return True

        except Exception as e:
            logger.error(f"AI 학습 데이터 연동 오류: {e}", exc_info=True)
            return False

    def update_feedback(self, ai_learning_data: Dict[str, Any]) -> bool:
        """피드백 시스템 업데이트

        AI 학습 결과에 대한 피드백 데이터를 생성합니다.

        Args:
            ai_learning_data: AI 학습용 통합 데이터

        Returns:
            성공 여부
        """
        try:
            # 피드백 데이터 생성
            # Note: data_quality_score는 향후 실제 계산 로직 추가 시 구현
            phase1_status = ai_learning_data["phase1_screening"].get("status")
            phase2_status = ai_learning_data["phase2_selection"].get("status")

            feedback_data = {
                "feedback_date": datetime.now().isoformat(),
                "total_predictions": ai_learning_data["phase2_selection"].get(
                    "total_selected_stocks", 0
                ),
                "data_quality_score": None,  # TODO: 향후 실제 품질 계산 로직 구현
                "integration_success": phase1_status == "completed" and phase2_status == "completed",
                "learning_ready": phase1_status in ("completed", "large_file_summarized"),
                "phase1_status": phase1_status,
                "phase2_status": phase2_status,
            }

            # 피드백 데이터 저장
            feedback_file = (
                self.ai_feedback_dir
                / f"daily_feedback_{datetime.now().strftime('%Y%m%d')}.json"
            )

            with open(feedback_file, "w", encoding="utf-8") as f:
                json.dump(feedback_data, f, indent=2, ensure_ascii=False)

            logger.info(f"피드백 시스템 업데이트 완료: {feedback_file}")
            return True

        except Exception as e:
            logger.error(f"피드백 시스템 업데이트 오류: {e}", exc_info=True)
            return False

    def get_latest_ai_data(self) -> Optional[Dict[str, Any]]:
        """최신 AI 학습 데이터 조회

        Returns:
            최신 AI 학습 데이터 또는 None
        """
        try:
            # daily_integration_*.json 파일 찾기 (Path.glob 사용)
            ai_files = [
                f.name
                for f in self.ai_raw_data_dir.glob("daily_integration_*.json")
                if f.is_file()
            ]

            if not ai_files:
                logger.warning("AI 학습 데이터 파일을 찾을 수 없음")
                return None

            # 최신 파일 선택
            latest_file = max(ai_files)
            ai_data_file = self.ai_raw_data_dir / latest_file

            with open(ai_data_file, "r", encoding="utf-8") as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"최신 AI 학습 데이터 조회 오류: {e}", exc_info=True)
            return None
