"""
병렬처리 가격 매력도 분석 시스템
- 멀티스레딩 기반 종목 분석
- 배치 처리 최적화
- 성능 향상된 Phase2 분석
"""

import os
import sys
import time
import logging
import multiprocessing as mp
import concurrent.futures
from typing import Dict, List, Optional, Any
from datetime import datetime
from functools import partial

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 기존 PriceAnalyzer 클래스 import
from core.daily_selection.price_analyzer import PriceAnalyzer, PriceAttractiveness
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class ParallelPriceAnalyzer(PriceAnalyzer):
    """병렬처리 가격 매력도 분석 클래스"""
    
    def __init__(self, p_config_file: str = "core/config/api_config.py", p_max_workers: int = None):
        """초기화

        Args:
            p_config_file: 설정 파일 경로
            p_max_workers: 최대 워커 수 (None이면 1, API Rate Limit 준수)

        Note:
            KIS API Rate Limit: 실전 20건/초, 모의 5건/초
            Rate Limit 초과 방지를 위해 기본값 1로 설정 (순차 처리)
        """
        super().__init__(p_config_file)
        # API rate limit 방지를 위해 워커 수 제한 (기본값 1, 순차 처리)
        self._v_max_workers = p_max_workers or 1
        logger.info(f"병렬 가격 분석기 초기화 완료 - 워커 수: {self._v_max_workers}")
    
    def parallel_analyze_multiple_stocks(self, p_stock_list: List[Dict], p_batch_size: int = 20) -> List[PriceAttractiveness]:
        """병렬 다중 종목 분석
        
        Args:
            p_stock_list: 종목 데이터 리스트
            p_batch_size: 배치 크기
            
        Returns:
            분석 결과 리스트
        """
        try:
            logger.info(f"병렬 다중 종목 분석 시작: {len(p_stock_list)}개 종목, 워커: {self._v_max_workers}개")
            
            _v_results = []
            
            # ThreadPoolExecutor 사용 (I/O 집약적 작업)
            with concurrent.futures.ThreadPoolExecutor(max_workers=self._v_max_workers) as executor:
                # 각 종목에 대해 Future 생성
                _v_futures = {
                    executor.submit(self._analyze_single_stock_wrapper, stock_data): i 
                    for i, stock_data in enumerate(p_stock_list)
                }
                
                # 완료된 종목 결과 수집
                for future in concurrent.futures.as_completed(_v_futures):
                    _v_stock_idx = _v_futures[future]
                    
                    try:
                        _v_result = future.result()
                        if _v_result:
                            _v_results.append(_v_result)
                            
                        # 진행 상황 로깅
                        if len(_v_results) % 10 == 0:
                            logger.info(f"분석 진행: {len(_v_results)}/{len(p_stock_list)} 완료")
                            
                    except Exception as e:
                        _v_stock_code = p_stock_list[_v_stock_idx].get("stock_code", "Unknown")
                        logger.error(f"종목 {_v_stock_code} 분석 오류: {e}", exc_info=True)
                        continue
            
            logger.info(f"병렬 다중 종목 분석 완료: {len(_v_results)}개 결과")
            return _v_results
            
        except Exception as e:
            logger.error(f"병렬 다중 종목 분석 오류: {e}", exc_info=True)
            return []
    
    def batch_analyze_stocks(self, p_stock_list: List[Dict], p_batch_size: int = 50) -> List[PriceAttractiveness]:
        """배치 기반 종목 분석 (프로세스 풀 활용)
        
        Args:
            p_stock_list: 종목 데이터 리스트
            p_batch_size: 배치 크기
            
        Returns:
            분석 결과 리스트
        """
        try:
            logger.info(f"배치 종목 분석 시작: {len(p_stock_list)}개 종목")
            
            # 배치 생성
            _v_batches = [p_stock_list[i:i + p_batch_size] for i in range(0, len(p_stock_list), p_batch_size)]
            logger.info(f"배치 생성 완료: {len(_v_batches)}개 배치")
            
            _v_all_results = []
            
            # ProcessPoolExecutor 사용하여 배치 병렬 처리
            with concurrent.futures.ProcessPoolExecutor(max_workers=self._v_max_workers) as executor:
                # 각 배치에 대해 Future 생성
                _v_batch_function = partial(self._process_analysis_batch_worker, 
                                          weights=self._v_weights)
                
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
                        
                        logger.info(f"배치 {_v_batch_idx + 1} 완료: {len(_v_batch_results)}개 분석")
                        print(f"🔄 분석 배치 {_v_batch_idx + 1}/{len(_v_batches)} 완료")
                        
                    except Exception as e:
                        logger.error(f"배치 {_v_batch_idx + 1} 분석 오류: {e}", exc_info=True)
                        continue
            
            logger.info(f"배치 종목 분석 완료 - 총 {len(_v_all_results)}개 결과")
            return _v_all_results
            
        except Exception as e:
            logger.error(f"배치 종목 분석 오류: {e}", exc_info=True)
            return []
    
    def _analyze_single_stock_wrapper(self, p_stock_data: Dict) -> Optional[PriceAttractiveness]:
        """단일 종목 분석 래퍼 (스레드 워커용)
        
        Args:
            p_stock_data: 종목 데이터
            
        Returns:
            분석 결과 또는 None
        """
        try:
            return self.analyze_price_attractiveness(p_stock_data)
            
        except Exception as e:
            logger.error(f"종목 분석 래퍼 오류 ({p_stock_data.get('stock_code', 'Unknown')}): {e}", exc_info=True)
            return None
    
    @staticmethod
    def _process_analysis_batch_worker(p_batch: List[Dict], weights: Dict) -> List[PriceAttractiveness]:
        """배치 분석 워커 함수 (프로세스 풀 워커용)
        
        Args:
            p_batch: 배치 종목 데이터 리스트
            weights: 분석 가중치
            
        Returns:
            배치 분석 결과 리스트
        """
        try:
            # 워커 프로세스에서 새로운 PriceAnalyzer 인스턴스 생성
            _v_analyzer = PriceAnalyzer()
            _v_analyzer._v_weights = weights
            
            # 배치 내 종목들 순차 분석
            _v_batch_results = []
            for stock_data in p_batch:
                try:
                    _v_result = _v_analyzer.analyze_price_attractiveness(stock_data)
                    if _v_result:
                        _v_batch_results.append(_v_result)
                        
                except Exception as e:
                    logger.error(f"배치 워커 종목 분석 오류 ({stock_data.get('stock_code', 'Unknown')}): {e}", exc_info=True)
                    continue
            
            return _v_batch_results
            
        except Exception as e:
            logger.error(f"배치 분석 워커 오류: {e}", exc_info=True)
            return []
    
    def concurrent_technical_analysis(self, p_stock_data_list: List[Dict]) -> List[Dict]:
        """동시 기술적 분석 (기술적 지표 병렬 계산)
        
        Args:
            p_stock_data_list: 종목 데이터 리스트
            
        Returns:
            기술적 분석 결과 리스트
        """
        try:
            logger.info(f"동시 기술적 분석 시작: {len(p_stock_data_list)}개 종목")
            
            _v_results = []
            
            # ThreadPoolExecutor 사용하여 기술적 분석 병렬화
            with concurrent.futures.ThreadPoolExecutor(max_workers=self._v_max_workers * 2) as executor:
                # 각 종목에 대해 Future 생성
                _v_futures = {
                    executor.submit(self._analyze_technical_indicators, stock_data): stock_data.get("stock_code", "Unknown")
                    for stock_data in p_stock_data_list
                }
                
                # 완료된 결과 수집
                for future in concurrent.futures.as_completed(_v_futures):
                    _v_stock_code = _v_futures[future]
                    
                    try:
                        _v_technical_score, _v_technical_signals = future.result()
                        _v_results.append({
                            "stock_code": _v_stock_code,
                            "technical_score": _v_technical_score,
                            "technical_signals": _v_technical_signals
                        })
                        
                    except Exception as e:
                        logger.error(f"종목 {_v_stock_code} 기술적 분석 오류: {e}", exc_info=True)
                        continue
            
            logger.info(f"동시 기술적 분석 완료: {len(_v_results)}개 결과")
            return _v_results
            
        except Exception as e:
            logger.error(f"동시 기술적 분석 오류: {e}", exc_info=True)
            return []
    
    def get_performance_comparison(self, p_stock_list: List[Dict]) -> Dict:
        """성능 비교 (순차 vs 병렬)
        
        Args:
            p_stock_list: 테스트할 종목 데이터 리스트
            
        Returns:
            성능 비교 결과
        """
        try:
            logger.info(f"성능 비교 시작: {len(p_stock_list)}개 종목")
            
            # 순차 처리 시간 측정
            _v_start_time = time.time()
            _v_sequential_results = super().analyze_multiple_stocks(p_stock_list)
            _v_sequential_time = time.time() - _v_start_time
            
            # 병렬 처리 시간 측정
            _v_start_time = time.time()
            _v_parallel_results = self.parallel_analyze_multiple_stocks(p_stock_list)
            _v_parallel_time = time.time() - _v_start_time
            
            # 성능 비교 결과
            _v_speedup = _v_sequential_time / _v_parallel_time if _v_parallel_time > 0 else 0
            
            _v_comparison = {
                "stock_count": len(p_stock_list),
                "sequential_time": _v_sequential_time,
                "parallel_time": _v_parallel_time,
                "speedup": _v_speedup,
                "sequential_results": len(_v_sequential_results),
                "parallel_results": len(_v_parallel_results),
                "efficiency": _v_speedup / self._v_max_workers if self._v_max_workers > 0 else 0,
                "workers": self._v_max_workers,
                "recommendation": self._get_performance_recommendation(_v_speedup)
            }
            
            logger.info(f"성능 비교 완료 - 속도 향상: {_v_speedup:.2f}배")
            return _v_comparison
            
        except Exception as e:
            logger.error(f"성능 비교 오류: {e}", exc_info=True)
            return {}
    
    def _get_performance_recommendation(self, p_speedup: float) -> str:
        """성능 기반 추천
        
        Args:
            p_speedup: 속도 향상 배수
            
        Returns:
            추천 사항
        """
        if p_speedup >= 3.0:
            return "병렬 처리 매우 효과적 - 대용량 데이터 처리 시 사용 권장"
        elif p_speedup >= 2.0:
            return "병렬 처리 효과적 - 중간 규모 이상 데이터 처리 시 사용 권장"
        elif p_speedup >= 1.5:
            return "병렬 처리 보통 효과 - 소규모 데이터는 순차 처리 권장"
        else:
            return "병렬 처리 오버헤드 큼 - 순차 처리 권장"
    
    def get_optimization_metrics(self) -> Dict:
        """최적화 메트릭 조회
        
        Returns:
            최적화 메트릭 정보
        """
        return {
            "max_workers": self._v_max_workers,
            "cpu_count": mp.cpu_count(),
            "recommended_batch_size": self._v_max_workers * 5,
            "memory_estimation": {
                "per_stock_mb": 0.5,  # 종목당 예상 메모리 사용량
                "total_mb_estimate": len([]) * 0.5,  # 총 예상 메모리 사용량
                "safe_concurrent_limit": min(self._v_max_workers * 10, 100)
            },
            "optimization_tips": [
                "기술적 분석은 ThreadPoolExecutor 사용 (I/O 집약적)",
                "대용량 배치는 ProcessPoolExecutor 사용 (CPU 집약적)",
                "메모리 사용량이 높은 경우 배치 크기 감소",
                "네트워크 지연이 있는 경우 워커 수 증가"
            ],
            "performance_thresholds": {
                "small_dataset": 50,   # 50개 이하: 순차 처리
                "medium_dataset": 200, # 50-200개: 스레드 풀
                "large_dataset": 500   # 200개 이상: 프로세스 풀
            }
        }
    
    def adaptive_analysis(self, p_stock_list: List[Dict]) -> List[PriceAttractiveness]:
        """적응형 분석 (데이터 크기에 따른 최적 방법 선택)
        
        Args:
            p_stock_list: 종목 데이터 리스트
            
        Returns:
            분석 결과 리스트
        """
        try:
            _v_stock_count = len(p_stock_list)
            _v_metrics = self.get_optimization_metrics()
            
            logger.info(f"적응형 분석 시작: {_v_stock_count}개 종목")
            
            # 데이터 크기에 따른 최적 방법 선택
            if _v_stock_count <= _v_metrics["performance_thresholds"]["small_dataset"]:
                logger.info("소규모 데이터 - 순차 처리 선택")
                return super().analyze_multiple_stocks(p_stock_list)
            
            elif _v_stock_count <= _v_metrics["performance_thresholds"]["medium_dataset"]:
                logger.info("중규모 데이터 - 스레드 풀 병렬 처리 선택")
                return self.parallel_analyze_multiple_stocks(p_stock_list)
            
            else:
                logger.info("대규모 데이터 - 프로세스 풀 배치 처리 선택")
                _v_optimal_batch_size = _v_metrics["recommended_batch_size"]
                return self.batch_analyze_stocks(p_stock_list, _v_optimal_batch_size)
                
        except Exception as e:
            logger.error(f"적응형 분석 오류: {e}", exc_info=True)
            return []

if __name__ == "__main__":
    # 테스트 실행
    _v_parallel_analyzer = ParallelPriceAnalyzer(p_max_workers=4)
    
    # 테스트 데이터 생성
    _v_test_stocks = []
    for i in range(20):
        _v_test_stocks.append({
            "stock_code": f"00593{i:01d}",
            "stock_name": f"테스트주식{i}",
            "current_price": 50000 + i * 1000,
            "sector": "테스트",
            "market_cap": 1000000000000 + i * 100000000000,
            "volatility": 0.25 + i * 0.01,
            "sector_momentum": 0.05 + i * 0.001
        })
    
    print("병렬 가격 분석 테스트 시작...")
    
    # 성능 비교 실행
    _v_comparison = _v_parallel_analyzer.get_performance_comparison(_v_test_stocks)
    
    print(f"\n=== 성능 비교 결과 ===")
    print(f"종목 수: {_v_comparison.get('stock_count', 0)}개")
    print(f"순차 처리 시간: {_v_comparison.get('sequential_time', 0):.2f}초")
    print(f"병렬 처리 시간: {_v_comparison.get('parallel_time', 0):.2f}초")
    print(f"속도 향상: {_v_comparison.get('speedup', 0):.2f}배")
    print(f"추천 사항: {_v_comparison.get('recommendation', '')}")
    
    # 최적화 메트릭 출력
    _v_metrics = _v_parallel_analyzer.get_optimization_metrics()
    print(f"\n=== 최적화 메트릭 ===")
    print(f"워커 수: {_v_metrics['max_workers']}")
    print(f"권장 배치 크기: {_v_metrics['recommended_batch_size']}")
    print(f"메모리 사용량 추정: {_v_metrics['memory_estimation']['total_mb_estimate']:.1f}MB")
    
    # 적응형 분석 테스트
    print(f"\n=== 적응형 분석 테스트 ===")
    _v_adaptive_results = _v_parallel_analyzer.adaptive_analysis(_v_test_stocks)
    print(f"적응형 분석 결과: {len(_v_adaptive_results)}개 종목 분석 완료") 