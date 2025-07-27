"""
병렬처리 기업 스크리닝 로직 모듈
- 멀티프로세싱 기반 배치 처리
- 멀티스레딩 기반 API 호출
- 성능 최적화된 스크리닝 실행
"""

import logging
import multiprocessing as mp
import concurrent.futures
from typing import List, Dict, Optional, Union, Any
from datetime import datetime
import json
import os
import time
from functools import partial

# 기존 StockScreener 클래스 import
from core.watchlist.stock_screener import StockScreener
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class ParallelStockScreener(StockScreener):
    """병렬처리 기업 스크리닝 클래스"""
    
    def __init__(self, p_max_workers: Optional[int] = None):
        """초기화
        
        Args:
            p_max_workers: 최대 워커 수 (None이면 CPU 코어 수)
        """
        super().__init__()
        self._v_max_workers = p_max_workers or min(mp.cpu_count(), 8)
        logger.info(f"병렬 스크리닝 초기화 완료 - 워커 수: {self._v_max_workers}")
    
    def parallel_comprehensive_screening(self, p_stock_list: List[str], p_batch_size: int = 50) -> List[Dict]:
        """병렬 종합 스크리닝 실행
        
        Args:
            p_stock_list: 스크리닝할 종목 코드 리스트
            p_batch_size: 배치 크기
            
        Returns:
            스크리닝 결과 리스트
        """
        try:
            logger.info(f"병렬 스크리닝 시작 - 대상 종목: {len(p_stock_list)}개, 워커: {self._v_max_workers}개")
            
            # 배치 생성
            _v_batches = [p_stock_list[i:i + p_batch_size] for i in range(0, len(p_stock_list), p_batch_size)]
            logger.info(f"배치 생성 완료: {len(_v_batches)}개 배치")
            
            _v_all_results = []
            
            # ProcessPoolExecutor 사용하여 배치 병렬 처리
            with concurrent.futures.ProcessPoolExecutor(max_workers=self._v_max_workers) as executor:
                # 각 배치에 대해 Future 생성
                _v_batch_function = partial(self._process_batch_worker, 
                                          screening_criteria=self._v_screening_criteria)
                
                _v_futures = {
                    executor.submit(_v_batch_function, batch): i 
                    for i, batch in enumerate(_v_batches)
                }
                
                # 완료된 배치 결과 수집
                for future in concurrent.futures.as_completed(_v_futures):
                    _v_batch_idx = _v_futures[future]
                    
                    try:
                        _v_batch_results = future.result()
                        _v_all_results.extend(_v_batch_results)
                        
                        _v_passed_count = len([r for r in _v_batch_results if r["overall_passed"]])
                        logger.info(f"배치 {_v_batch_idx + 1} 완료: {len(_v_batch_results)}개 처리, {_v_passed_count}개 통과")
                        print(f"🔄 배치 {_v_batch_idx + 1}/{len(_v_batches)} 완료 ({_v_passed_count}개 통과)")
                        
                    except Exception as e:
                        logger.error(f"배치 {_v_batch_idx + 1} 처리 오류: {e}")
                        continue
            
            logger.info(f"병렬 스크리닝 완료 - 총 {len(_v_all_results)}개 종목 처리")
            return _v_all_results
            
        except Exception as e:
            logger.error(f"병렬 스크리닝 오류: {e}")
            return []
    
    def threaded_screening_batch(self, p_stock_list: List[str]) -> List[Dict]:
        """스레드 기반 배치 스크리닝 (I/O 집약적 작업용)
        
        Args:
            p_stock_list: 스크리닝할 종목 코드 리스트
            
        Returns:
            스크리닝 결과 리스트
        """
        try:
            logger.info(f"스레드 배치 스크리닝 시작: {len(p_stock_list)}개 종목")
            
            _v_results = []
            
            # ThreadPoolExecutor 사용하여 I/O 작업 병렬화
            with concurrent.futures.ThreadPoolExecutor(max_workers=self._v_max_workers * 2) as executor:
                # 각 종목에 대해 Future 생성
                _v_futures = {
                    executor.submit(self._screen_single_stock, stock_code): stock_code 
                    for stock_code in p_stock_list
                }
                
                # 완료된 종목 결과 수집
                for future in concurrent.futures.as_completed(_v_futures):
                    _v_stock_code = _v_futures[future]
                    
                    try:
                        _v_result = future.result()
                        if _v_result:
                            _v_results.append(_v_result)
                            
                    except Exception as e:
                        logger.error(f"종목 {_v_stock_code} 스크리닝 오류: {e}")
                        continue
            
            logger.info(f"스레드 배치 스크리닝 완료: {len(_v_results)}개 결과")
            return _v_results
            
        except Exception as e:
            logger.error(f"스레드 배치 스크리닝 오류: {e}")
            return []
    
    def _screen_single_stock(self, p_stock_code: str) -> Optional[Dict]:
        """단일 종목 스크리닝 (스레드 워커용)
        
        Args:
            p_stock_code: 종목 코드
            
        Returns:
            스크리닝 결과 또는 None
        """
        try:
            # 주식 데이터 수집
            _v_stock_data = self._fetch_stock_data(p_stock_code)
            if not _v_stock_data:
                return None
            
            # 각 스크리닝 실행
            _v_fundamental_passed, _v_fundamental_score, _v_fundamental_details = self.screen_by_fundamentals(_v_stock_data)
            _v_technical_passed, _v_technical_score, _v_technical_details = self.screen_by_technical(_v_stock_data)
            _v_momentum_passed, _v_momentum_score, _v_momentum_details = self.screen_by_momentum(_v_stock_data)
            
            # 종합 결과 계산
            _v_overall_passed = _v_fundamental_passed and _v_technical_passed and _v_momentum_passed
            _v_overall_score = (_v_fundamental_score + _v_technical_score + _v_momentum_score) / 3.0
            
            _v_result = {
                "stock_code": p_stock_code,
                "stock_name": _v_stock_data.get("stock_name", ""),
                "sector": _v_stock_data.get("sector", ""),
                "screening_timestamp": datetime.now().isoformat(),
                "overall_passed": _v_overall_passed,
                "overall_score": round(_v_overall_score, 2),
                "fundamental": {
                    "passed": _v_fundamental_passed,
                    "score": round(_v_fundamental_score, 2),
                    "details": _v_fundamental_details
                },
                "technical": {
                    "passed": _v_technical_passed,
                    "score": round(_v_technical_score, 2),
                    "details": _v_technical_details
                },
                "momentum": {
                    "passed": _v_momentum_passed,
                    "score": round(_v_momentum_score, 2),
                    "details": _v_momentum_details
                }
            }
            
            return _v_result
            
        except Exception as e:
            logger.error(f"단일 종목 스크리닝 오류 ({p_stock_code}): {e}")
            return None
    
    @staticmethod
    def _process_batch_worker(p_batch: List[str], screening_criteria: Dict) -> List[Dict]:
        """배치 워커 함수 (프로세스 풀 워커용)
        
        Args:
            p_batch: 배치 종목 리스트
            screening_criteria: 스크리닝 기준
            
        Returns:
            배치 처리 결과 리스트
        """
        try:
            # 워커 프로세스에서 새로운 StockScreener 인스턴스 생성
            _v_screener = StockScreener()
            _v_screener._v_screening_criteria = screening_criteria
            
            # 배치 내 종목들 순차 처리
            _v_batch_results = []
            for stock_code in p_batch:
                try:
                    _v_result = _v_screener._screen_single_stock_static(stock_code)
                    if _v_result:
                        _v_batch_results.append(_v_result)
                        
                except Exception as e:
                    logger.error(f"배치 워커 종목 처리 오류 ({stock_code}): {e}")
                    continue
            
            return _v_batch_results
            
        except Exception as e:
            logger.error(f"배치 워커 오류: {e}")
            return []
    
    def get_performance_metrics(self) -> Dict:
        """성능 메트릭 조회
        
        Returns:
            성능 메트릭 정보
        """
        return {
            "max_workers": self._v_max_workers,
            "cpu_count": mp.cpu_count(),
            "recommended_batch_size": self._v_max_workers * 10,
            "optimization_tips": [
                "I/O 집약적 작업은 ThreadPoolExecutor 사용",
                "CPU 집약적 작업은 ProcessPoolExecutor 사용",
                "배치 크기는 워커 수의 5-10배로 설정",
                "메모리 사용량 모니터링 필요"
            ]
        }

# StockScreener 클래스에 static 메서드 추가 (프로세스 풀 워커용)
# def _screen_single_stock_static(self, p_stock_code: str) -> Optional[Dict]:
#     """정적 단일 종목 스크리닝 메서드"""
#     이 메서드는 StockScreener 클래스로 이동됨

if __name__ == "__main__":
    # 테스트 실행
    import sys
    import os
    
    # 프로젝트 루트 디렉토리를 Python 경로에 추가
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    
    # 병렬 스크리닝 테스트
    _v_parallel_screener = ParallelStockScreener(p_max_workers=4)
    
    # 테스트 종목 리스트
    _v_test_stocks = ["005930", "000660", "035420", "005380", "000270", "068270", "207940", "035720", "051910", "006400"]
    
    print("병렬 스크리닝 테스트 시작...")
    _v_start_time = time.time()
    
    # 병렬 스크리닝 실행
    _v_results = _v_parallel_screener.parallel_comprehensive_screening(_v_test_stocks, p_batch_size=5)
    
    _v_end_time = time.time()
    _v_duration = _v_end_time - _v_start_time
    
    print(f"병렬 스크리닝 완료: {len(_v_results)}개 결과, 소요시간: {_v_duration:.2f}초")
    
    # 성능 메트릭 출력
    _v_metrics = _v_parallel_screener.get_performance_metrics()
    print(f"성능 메트릭: {_v_metrics}") 