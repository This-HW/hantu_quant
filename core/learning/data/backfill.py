"""
Phase 4: AI 학습 시스템 - 히스토리 데이터 백필 시스템
과거 데이터를 일괄 수집하고 처리하여 AI 학습용 데이터베이스를 구축
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from pathlib import Path

# 인터페이스 및 데이터 클래스 import
from core.interfaces.learning import LearningData
from core.learning.config.settings import get_learning_config
from core.learning.utils.logging import get_learning_logger
from core.learning.data.storage import get_learning_storage
from core.learning.data.collector import get_data_collector
from core.learning.data.preprocessor import get_data_preprocessor

# 임시 플러그인 시스템 (추후 실제 아키텍처로 교체)
def plugin(**kwargs):
    """임시 플러그인 데코레이터"""
    def decorator(cls):
        cls._plugin_metadata = kwargs
        return cls
    return decorator

def inject(cls):
    """임시 DI 데코레이터"""
    return cls

logger = get_learning_logger(__name__)

@plugin(
    name="learning_data_backfill",
    version="1.0.0",
    description="AI 학습용 히스토리 데이터 백필 플러그인",
    author="HantuQuant",
    dependencies=["learning_config", "learning_storage", "data_collector"],
    category="learning"
)
class LearningDataBackfill:
    """AI 학습용 히스토리 데이터 백필 시스템"""
    
    @inject
    def __init__(self, config=None, storage=None, collector=None, preprocessor=None):
        """초기화"""
        self._config = config or get_learning_config()
        self._storage = storage or get_learning_storage()
        self._collector = collector or get_data_collector()
        self._preprocessor = preprocessor or get_data_preprocessor()
        self._logger = logger
        
        # 백필 상태 관리
        self._backfill_status = {
            "is_running": False,
            "current_date": None,
            "progress": 0.0,
            "total_dates": 0,
            "processed_dates": 0,
            "errors": []
        }
        self._lock = threading.Lock()
        
        self._logger.info("LearningDataBackfill 초기화 완료")
    
    def run_backfill(self, start_date: str, end_date: str, 
                     stock_codes: Optional[List[str]] = None,
                     batch_size: int = 100,
                     max_workers: int = 4) -> Dict[str, Any]:
        """히스토리 데이터 백필 실행"""
        try:
            with self._lock:
                if self._backfill_status["is_running"]:
                    return {"error": "백필이 이미 실행 중입니다"}
                
                self._backfill_status["is_running"] = True
                self._backfill_status["errors"] = []
            
            self._logger.info(f"히스토리 데이터 백필 시작: {start_date} ~ {end_date}")
            
            # 1. 백필 계획 수립
            _v_backfill_plan = self._create_backfill_plan(start_date, end_date, stock_codes)
            
            # 2. 데이터 수집
            _v_collected_data = self._collect_historical_data(_v_backfill_plan, batch_size, max_workers)
            
            # 3. 데이터 전처리
            _v_processed_data = self._process_collected_data(_v_collected_data)
            
            # 4. 데이터 저장
            _v_saved_count = self._save_processed_data(_v_processed_data)
            
            # 5. 백필 완료 처리
            _v_result = self._complete_backfill(_v_backfill_plan, _v_saved_count)
            
            self._logger.info(f"히스토리 데이터 백필 완료: {_v_saved_count}개 데이터 저장")
            return _v_result
            
        except Exception as e:
            self._logger.error(f"히스토리 데이터 백필 오류: {e}")
            return {"error": str(e)}
        finally:
            with self._lock:
                self._backfill_status["is_running"] = False
    
    def _create_backfill_plan(self, start_date: str, end_date: str, 
                             stock_codes: Optional[List[str]]) -> Dict[str, Any]:
        """백필 계획 수립"""
        try:
            # 날짜 범위 생성
            _v_start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            _v_end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            _v_date_range = []
            
            _v_current_dt = _v_start_dt
            while _v_current_dt <= _v_end_dt:
                # 주말 제외
                if _v_current_dt.weekday() < 5:  # 월~금
                    _v_date_range.append(_v_current_dt.strftime('%Y-%m-%d'))
                _v_current_dt += timedelta(days=1)
            
            # 종목 코드 설정
            if not stock_codes:
                stock_codes = self._get_default_stock_codes()
            
            # 백필 계획 생성
            _v_plan = {
                "start_date": start_date,
                "end_date": end_date,
                "date_range": _v_date_range,
                "stock_codes": stock_codes,
                "total_dates": len(_v_date_range),
                "total_combinations": len(_v_date_range) * len(stock_codes),
                "created_at": datetime.now().isoformat()
            }
            
            # 상태 업데이트
            with self._lock:
                self._backfill_status["total_dates"] = len(_v_date_range)
                self._backfill_status["processed_dates"] = 0
            
            self._logger.info(f"백필 계획 수립 완료: {len(_v_date_range)}일, {len(stock_codes)}개 종목")
            return _v_plan
            
        except Exception as e:
            self._logger.error(f"백필 계획 수립 오류: {e}")
            return {}
    
    def _collect_historical_data(self, plan: Dict[str, Any], 
                               batch_size: int, max_workers: int) -> List[LearningData]:
        """히스토리 데이터 수집"""
        try:
            _v_all_data = []
            _v_date_range = plan["date_range"]
            _v_stock_codes = plan["stock_codes"]
            
            # 날짜별 병렬 처리
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # 날짜별 Future 생성
                _v_futures = {
                    executor.submit(self._collect_date_data, date, _v_stock_codes): date
                    for date in _v_date_range
                }
                
                # 결과 수집
                for future in as_completed(_v_futures):
                    _v_date = _v_futures[future]
                    
                    try:
                        _v_date_data = future.result()
                        _v_all_data.extend(_v_date_data)
                        
                        # 진행 상황 업데이트
                        with self._lock:
                            self._backfill_status["processed_dates"] += 1
                            self._backfill_status["current_date"] = _v_date
                            self._backfill_status["progress"] = (
                                self._backfill_status["processed_dates"] / 
                                self._backfill_status["total_dates"]
                            )
                        
                        self._logger.debug(f"날짜 {_v_date} 데이터 수집 완료: {len(_v_date_data)}개")
                        
                    except Exception as e:
                        self._logger.error(f"날짜 {_v_date} 데이터 수집 오류: {e}")
                        with self._lock:
                            self._backfill_status["errors"].append(f"{_v_date}: {str(e)}")
            
            self._logger.info(f"히스토리 데이터 수집 완료: {len(_v_all_data)}개 데이터")
            return _v_all_data
            
        except Exception as e:
            self._logger.error(f"히스토리 데이터 수집 오류: {e}")
            return []
    
    def _collect_date_data(self, date: str, stock_codes: List[str]) -> List[LearningData]:
        """특정 날짜의 데이터 수집"""
        try:
            # Phase 1, 2 결과 수집
            _v_phase1_results = self._collector.collect_phase1_results(date)
            _v_phase2_results = self._collector.collect_phase2_results(date)
            
            # 실제 성과 데이터 수집 (7일 후)
            _v_future_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=7)).strftime('%Y-%m-%d')
            _v_performance_data = self._collector.collect_actual_performance(stock_codes, date, _v_future_date)
            
            # 데이터 병합
            _v_merged_data = self._collector._merge_data(_v_phase1_results, _v_phase2_results, _v_performance_data, date)
            
            return _v_merged_data
            
        except Exception as e:
            self._logger.error(f"날짜 {date} 데이터 수집 오류: {e}")
            return []
    
    def _process_collected_data(self, collected_data: List[LearningData]) -> List[LearningData]:
        """수집된 데이터 처리"""
        try:
            self._logger.info(f"수집된 데이터 전처리 시작: {len(collected_data)}개")
            
            # 데이터 전처리
            _v_processed_data = self._preprocessor.preprocess_learning_data(collected_data)
            
            # 데이터 품질 검증
            _v_quality_report = self._collector.validate_data_quality(_v_processed_data)
            
            self._logger.info(f"데이터 전처리 완료: {len(_v_processed_data)}개 (품질: {_v_quality_report.get('quality_score', 0):.2%})")
            
            return _v_processed_data
            
        except Exception as e:
            self._logger.error(f"데이터 처리 오류: {e}")
            return collected_data
    
    def _save_processed_data(self, processed_data: List[LearningData]) -> int:
        """처리된 데이터 저장"""
        try:
            _v_saved_count = 0
            
            for _v_data in processed_data:
                try:
                    if self._storage.save_learning_data(_v_data):
                        _v_saved_count += 1
                except Exception as e:
                    self._logger.error(f"데이터 저장 오류 ({_v_data.stock_code}): {e}")
                    continue
            
            self._logger.info(f"데이터 저장 완료: {_v_saved_count}개")
            return _v_saved_count
            
        except Exception as e:
            self._logger.error(f"데이터 저장 오류: {e}")
            return 0
    
    def _complete_backfill(self, plan: Dict[str, Any], saved_count: int) -> Dict[str, Any]:
        """백필 완료 처리"""
        try:
            _v_result = {
                "success": True,
                "start_date": plan["start_date"],
                "end_date": plan["end_date"],
                "total_dates": plan["total_dates"],
                "processed_dates": self._backfill_status["processed_dates"],
                "total_combinations": plan["total_combinations"],
                "saved_count": saved_count,
                "errors": self._backfill_status["errors"],
                "completion_rate": self._backfill_status["processed_dates"] / plan["total_dates"],
                "completed_at": datetime.now().isoformat()
            }
            
            # 백필 로그 저장
            self._save_backfill_log(_v_result)
            
            return _v_result
            
        except Exception as e:
            self._logger.error(f"백필 완료 처리 오류: {e}")
            return {"success": False, "error": str(e)}
    
    def _save_backfill_log(self, result: Dict[str, Any]) -> None:
        """백필 로그 저장"""
        try:
            _v_log_dir = Path(self._config.log_dir) / "backfill"
            _v_log_dir.mkdir(parents=True, exist_ok=True)
            
            _v_log_file = _v_log_dir / f"backfill_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            with open(_v_log_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            self._logger.info(f"백필 로그 저장: {_v_log_file}")
            
        except Exception as e:
            self._logger.error(f"백필 로그 저장 오류: {e}")
    
    def _get_default_stock_codes(self) -> List[str]:
        """기본 종목 코드 목록 조회"""
        try:
            # 실제 구현에서는 데이터베이스나 파일에서 종목 코드 조회
            # 여기서는 임시로 주요 종목들 반환
            return [
                "005930", "000660", "035420", "005380", "000270",  # 대형주
                "068270", "207940", "035720", "051910", "006400",  # 중형주
                "042700", "028260", "066570", "036570", "064350",  # 소형주
                "086900", "095720", "112040", "041190", "067630"   # 기타
            ]
            
        except Exception as e:
            self._logger.error(f"기본 종목 코드 조회 오류: {e}")
            return []
    
    def get_backfill_status(self) -> Dict[str, Any]:
        """백필 상태 조회"""
        with self._lock:
            return self._backfill_status.copy()
    
    def cancel_backfill(self) -> bool:
        """백필 취소"""
        try:
            with self._lock:
                if self._backfill_status["is_running"]:
                    self._backfill_status["is_running"] = False
                    self._logger.info("백필 취소 요청")
                    return True
                else:
                    return False
                    
        except Exception as e:
            self._logger.error(f"백필 취소 오류: {e}")
            return False
    
    def get_backfill_history(self, days: int = 30) -> List[Dict[str, Any]]:
        """백필 히스토리 조회"""
        try:
            _v_log_dir = Path(self._config.log_dir) / "backfill"
            if not _v_log_dir.exists():
                return []
            
            _v_log_files = list(_v_log_dir.glob("backfill_*.json"))
            _v_log_files.sort(key=lambda x: x.name, reverse=True)
            
            _v_history = []
            for _v_file in _v_log_files[:days]:
                try:
                    with open(_v_file, 'r', encoding='utf-8') as f:
                        _v_log_data = json.load(f)
                        _v_history.append(_v_log_data)
                except Exception as e:
                    self._logger.error(f"백필 로그 읽기 오류 {_v_file}: {e}")
                    continue
            
            return _v_history
            
        except Exception as e:
            self._logger.error(f"백필 히스토리 조회 오류: {e}")
            return []
    
    def estimate_backfill_time(self, start_date: str, end_date: str, 
                             stock_codes: Optional[List[str]] = None) -> Dict[str, Any]:
        """백필 소요 시간 추정"""
        try:
            # 백필 계획 수립
            _v_plan = self._create_backfill_plan(start_date, end_date, stock_codes)
            
            # 추정 계산
            _v_total_combinations = _v_plan["total_combinations"]
            _v_avg_time_per_combination = 0.1  # 초당 10개 처리 가정
            _v_estimated_seconds = _v_total_combinations * _v_avg_time_per_combination
            
            _v_estimation = {
                "total_dates": _v_plan["total_dates"],
                "total_combinations": _v_total_combinations,
                "estimated_seconds": _v_estimated_seconds,
                "estimated_minutes": _v_estimated_seconds / 60,
                "estimated_hours": _v_estimated_seconds / 3600,
                "completion_time": (datetime.now() + timedelta(seconds=_v_estimated_seconds)).isoformat()
            }
            
            return _v_estimation
            
        except Exception as e:
            self._logger.error(f"백필 시간 추정 오류: {e}")
            return {"error": str(e)}


# 전역 인스턴스
_backfill_system = None

def get_backfill_system() -> LearningDataBackfill:
    """백필 시스템 전역 인스턴스 반환"""
    global _backfill_system
    if _backfill_system is None:
        _backfill_system = LearningDataBackfill()
    return _backfill_system 