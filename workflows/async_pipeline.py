#!/usr/bin/env python3
"""
비동기 파이프라인: Phase1과 Phase2 독립 실행
- Phase1 결과를 실시간으로 Phase2에 전달
- 큐(Queue) 기반 비동기 처리
- 전체 처리 시간 최적화
"""

import time
from typing import List, Dict, Optional
from queue import Queue, Empty
import threading
import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflows.phase1_parallel import Phase1ParallelWorkflow
from workflows.phase2_daily_selection import Phase2CLI
from core.watchlist.watchlist_manager import WatchlistManager
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class AsyncPipeline:
    """비동기 파이프라인 클래스"""
    
    def __init__(self):
        """초기화"""
        self.phase1_workflow = Phase1ParallelWorkflow()
        self.phase2_cli = Phase2CLI()
        
        # 큐 설정
        self.screening_queue = Queue(maxsize=100)  # Phase1 → Phase2 데이터 전달 큐
        self.results_queue = Queue(maxsize=50)     # Phase2 결과 수집 큐
        
        # 상태 관리
        self.phase1_completed = False
        self.phase2_completed = False
        self.total_stocks = 0
        self.processed_stocks = 0
        
        logger.info("비동기 파이프라인 초기화 완료")
    
    def run_async_pipeline(self, p_stock_list: Optional[List[str]] = None) -> bool:
        """비동기 파이프라인 실행
        
        Args:
            p_stock_list: 스크리닝할 종목 리스트
            
        Returns:
            실행 성공 여부
        """
        try:
            start_time = time.time()
            logger.info("=== 비동기 파이프라인 시작 ===")
            
            # 종목 리스트 준비
            if not p_stock_list:
                p_stock_list = self.phase1_workflow._get_all_stock_codes()
            
            self.total_stocks = len(p_stock_list)
            logger.info(f"총 처리 종목: {self.total_stocks}개")
            
            # 스레드 생성
            phase1_thread = threading.Thread(
                target=self._run_phase1_streaming,
                args=(p_stock_list,),
                name="Phase1-Streaming"
            )
            
            phase2_thread = threading.Thread(
                target=self._run_phase2_consumer,
                name="Phase2-Consumer"
            )
            
            watchlist_thread = threading.Thread(
                target=self._run_watchlist_updater,
                name="Watchlist-Updater"
            )
            
            # 모든 스레드 시작
            print("[시작] 비동기 파이프라인 시작")
            print("├─ Phase1: 스크리닝 + 스트리밍")
            print("├─ Phase2: 실시간 분석")
            print("└─ Watchlist: 실시간 업데이트")
            
            phase1_thread.start()
            phase2_thread.start()
            watchlist_thread.start()
            
            # 진행률 모니터링
            self._monitor_progress()
            
            # 모든 스레드 완료 대기
            phase1_thread.join()
            phase2_thread.join()
            watchlist_thread.join()
            
            total_time = time.time() - start_time
            
            # 결과 요약
            self._print_pipeline_summary(total_time)
            
            return True
            
        except Exception as e:
            logger.error(f"비동기 파이프라인 실행 오류: {e}", exc_info=True)
            return False
    
    def _run_phase1_streaming(self, p_stock_list: List[str]):
        """Phase1 스트리밍 실행"""
        try:
            logger.info("Phase1 스트리밍 시작")
            
            # 배치 크기 설정
            batch_size = 10
            (len(p_stock_list) + batch_size - 1) // batch_size
            
            # 배치별 처리 및 스트리밍
            for i in range(0, len(p_stock_list), batch_size):
                batch_num = i // batch_size + 1
                batch_stocks = p_stock_list[i:i + batch_size]
                
                # 배치 스크리닝
                batch_results = self.phase1_workflow.screener.comprehensive_screening(batch_stocks)
                
                if batch_results:
                    # 결과를 큐에 스트리밍
                    for result in batch_results:
                        self.screening_queue.put(result)
                        self.processed_stocks += 1
                    
                    passed_count = len([r for r in batch_results if r["overall_passed"]])
                    print(f"[전송] Phase1 배치 {batch_num}: {len(batch_results)}개 처리, {passed_count}개 통과 → 스트리밍")
            
            # Phase1 완료 신호
            self.screening_queue.put({"END_OF_PHASE1": True})
            self.phase1_completed = True
            logger.info("Phase1 스트리밍 완료")
            
        except Exception as e:
            logger.error(f"Phase1 스트리밍 오류: {e}", exc_info=True)
            self.phase1_completed = True
    
    def _run_phase2_consumer(self):
        """Phase2 실시간 분석 소비자"""
        try:
            logger.info("Phase2 실시간 분석 시작")
            
            processed_count = 0
            selected_stocks = []
            
            while True:
                try:
                    # 큐에서 데이터 가져오기
                    result = self.screening_queue.get(timeout=5)
                    
                    # 종료 신호 확인
                    if isinstance(result, dict) and result.get("END_OF_PHASE1"):
                        break
                    
                    # 스크리닝 통과 종목만 Phase2 분석
                    if result.get("overall_passed"):
                        # 가격 매력도 분석
                        attractiveness = self._analyze_price_attractiveness(result)
                        
                        if attractiveness and attractiveness.get("price_attractiveness", 0) > 70:
                            selected_stocks.append(attractiveness)
                            print(f"[선정] Phase2 선정: {result['stock_name']} (매력도: {attractiveness['price_attractiveness']:.1f})")
                    
                    processed_count += 1
                    
                    # 결과를 watchlist 큐에 전달
                    self.results_queue.put(result)
                    
                except Empty:
                    if self.phase1_completed:
                        break
                    continue
            
            # Phase2 완료 처리
            self.results_queue.put({"END_OF_PHASE2": True})
            self.phase2_completed = True
            
            logger.info(f"Phase2 분석 완료 - 처리: {processed_count}개, 선정: {len(selected_stocks)}개")
            
        except Exception as e:
            logger.error(f"Phase2 분석 오류: {e}", exc_info=True)
            self.phase2_completed = True
    
    def _run_watchlist_updater(self):
        """감시 리스트 실시간 업데이트"""
        try:
            logger.info("감시 리스트 실시간 업데이트 시작")
            
            watchlist_manager = WatchlistManager()
            added_count = 0
            
            while True:
                try:
                    # 결과 큐에서 데이터 가져오기
                    result = self.results_queue.get(timeout=5)
                    
                    # 종료 신호 확인
                    if isinstance(result, dict) and result.get("END_OF_PHASE2"):
                        break
                    
                    # 통과 종목을 감시 리스트에 추가
                    if result.get("overall_passed"):
                        success = self._add_to_watchlist(watchlist_manager, result)
                        if success:
                            added_count += 1
                            if added_count % 10 == 0:
                                print(f"[기록] 감시 리스트: {added_count}개 종목 추가됨")
                    
                except Empty:
                    if self.phase2_completed:
                        break
                    continue
            
            logger.info(f"감시 리스트 업데이트 완료 - 총 {added_count}개 종목 추가")
            
        except Exception as e:
            logger.error(f"감시 리스트 업데이트 오류: {e}", exc_info=True)
    
    def _analyze_price_attractiveness(self, p_result: Dict) -> Optional[Dict]:
        """가격 매력도 분석"""
        try:
            # 간단한 가격 매력도 분석 (실제로는 Phase2 분석 로직 사용)
            stock_code = p_result["stock_code"]
            stock_name = p_result["stock_name"]
            overall_score = p_result["overall_score"]
            
            # 가격 매력도 점수 계산 (임시 로직)
            price_attractiveness = min(100, overall_score * 0.8 + 20)
            
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "price_attractiveness": price_attractiveness,
                "entry_price": 50000,
                "target_price": 57500,
                "stop_loss": 46000,
                "expected_return": 15.0,
                "risk_score": 25.0,
                "confidence": 0.7
            }
            
        except Exception as e:
            logger.error(f"가격 매력도 분석 오류: {e}", exc_info=True)
            return None
    
    def _add_to_watchlist(self, p_watchlist_manager: WatchlistManager, p_result: Dict) -> bool:
        """감시 리스트에 종목 추가"""
        try:
            stock_code = p_result["stock_code"]
            stock_name = p_result["stock_name"]
            overall_score = p_result["overall_score"]
            
            # 중복 확인
            existing_stocks = p_watchlist_manager.list_stocks(p_status="active")
            existing_codes = [s.stock_code for s in existing_stocks]
            
            if stock_code in existing_codes:
                return False
            
            # 감시 리스트에 추가
            success = p_watchlist_manager.add_stock(
                p_stock_code=stock_code,
                p_stock_name=stock_name,
                p_added_reason="스크리닝 통과 (비동기)",
                p_target_price=57500,
                p_stop_loss=46000,
                p_sector="기타",
                p_screening_score=overall_score,
                p_notes=f"비동기 파이프라인 - 점수: {overall_score:.1f}점"
            )
            
            return success
            
        except Exception as e:
            logger.error(f"감시 리스트 추가 오류: {e}", exc_info=True)
            return False
    
    def _monitor_progress(self):
        """진행률 모니터링"""
        try:
            print("\n[통계] 실시간 진행률 모니터링")
            
            while not (self.phase1_completed and self.phase2_completed):
                if self.total_stocks > 0:
                    phase1_progress = (self.processed_stocks / self.total_stocks) * 100
                    print(f"\r[진행중] Phase1: {phase1_progress:.1f}% | "
                          f"Queue: {self.screening_queue.qsize()} | "
                          f"Results: {self.results_queue.qsize()}", end="")
                
                time.sleep(1)
            
            print("\n[완료] 모든 단계 완료")
            
        except Exception as e:
            logger.error(f"진행률 모니터링 오류: {e}", exc_info=True)
    
    def _print_pipeline_summary(self, p_total_time: float):
        """파이프라인 결과 요약"""
        try:
            print("\n[요약] 비동기 파이프라인 결과 요약")
            print(f"├─ 총 처리 시간: {p_total_time:.1f}초")
            print(f"├─ 총 처리 종목: {self.total_stocks}개")
            print(f"├─ 처리 속도: {self.total_stocks / p_total_time:.1f}종목/초")
            print(f"├─ Phase1 완료: {'[완료]' if self.phase1_completed else '[실패]'}")
            print(f"└─ Phase2 완료: {'[완료]' if self.phase2_completed else '[실패]'}")
            
            # 순차 처리 대비 성능 향상
            sequential_time = 15 * 60  # 기존 15분
            speedup = sequential_time / p_total_time
            print("\n[성능] 성능 개선:")
            print(f"├─ 순차 처리 시간: {sequential_time / 60:.1f}분")
            print(f"├─ 비동기 처리 시간: {p_total_time / 60:.1f}분")
            print(f"└─ 속도 향상: {speedup:.1f}배")
            
        except Exception as e:
            logger.error(f"요약 출력 오류: {e}", exc_info=True)

def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="비동기 파이프라인: Phase1-Phase2 독립 실행")
    parser.add_argument('--stocks', nargs='+', help='스크리닝할 종목 코드 리스트')
    parser.add_argument('--queue-size', type=int, default=100, help='큐 크기')
    
    args = parser.parse_args()
    
    # 파이프라인 실행
    pipeline = AsyncPipeline()
    
    try:
        success = pipeline.run_async_pipeline(args.stocks)
        
        if success:
            print("\n[성공] 비동기 파이프라인 성공!")
        else:
            print("\n[실패] 비동기 파이프라인 실패!")
            
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        logger.error(f"파이프라인 실행 오류: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 