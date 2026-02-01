#!/usr/bin/env python3
"""
Phase 1 병렬 처리 버전: 감시 리스트 구축 워크플로우
- 멀티프로세싱 기반 배치 처리
- 성능 최적화된 스크리닝 실행
"""

import argparse
import sys
import os
import time
import multiprocessing as mp
from typing import List, Dict, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.watchlist.stock_screener import StockScreener
from core.watchlist.watchlist_manager import WatchlistManager
from core.watchlist.evaluation_engine import EvaluationEngine
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

def process_batch(batch_info: Dict) -> List[Dict]:
    """배치 처리 함수 (병렬 처리용)
    
    Args:
        batch_info: 배치 정보 딕셔너리
        
    Returns:
        스크리닝 결과 리스트
    """
    batch_stocks = batch_info["stocks"]
    batch_num = batch_info["batch_num"]
    total_batches = batch_info["total_batches"]
    
    try:
        # 각 프로세스에서 독립적인 스크리너 생성
        screener = StockScreener()
        
        print(f"[처리중] 배치 {batch_num}/{total_batches} 처리 시작... (PID: {os.getpid()})")

        # 배치 스크리닝 실행
        results = screener.comprehensive_screening(batch_stocks)

        if results:
            passed_count = len([r for r in results if r["overall_passed"]])
            print(f"[완료] 배치 {batch_num} 완료: {len(results)}개 처리, {passed_count}개 통과")
            return results
        else:
            print(f"[경고] 배치 {batch_num} 결과 없음")
            return []

    except Exception as e:
        print(f"[오류] 배치 {batch_num} 처리 오류: {e}")
        return []

class Phase1ParallelWorkflow:
    """Phase 1 병렬 처리 워크플로우 클래스"""
    
    def __init__(self):
        """초기화 메서드"""
        self.screener = StockScreener()
        self.watchlist_manager = WatchlistManager()
        self.evaluation_engine = EvaluationEngine()
        
        # CPU 코어 수 감지
        self.cpu_count = mp.cpu_count()
        self.max_workers = max(2, self.cpu_count - 1)  # 1개 코어는 시스템용으로 예약
        
        logger.info(f"Phase 1 병렬 워크플로우 초기화 완료 (CPU: {self.cpu_count}개, 워커: {self.max_workers}개)")
    
    def run_full_screening_parallel(self, p_stock_list: Optional[List[str]] = None) -> bool:
        """전체 스크리닝 병렬 실행
        
        Args:
            p_stock_list: 스크리닝할 종목 리스트 (None이면 전체 시장)
            
        Returns:
            실행 성공 여부
        """
        try:
            start_time = time.time()
            logger.info("=== 전체 스크리닝 시작 (병렬 처리) ===")
            
            # 종목 리스트 준비
            if not p_stock_list:
                p_stock_list = self._get_all_stock_codes()
            
            logger.info(f"스크리닝 대상 종목 수: {len(p_stock_list)}개")
            
            # 배치 처리 설정
            batch_size = 10  # 각 배치 크기
            total_batches = (len(p_stock_list) + batch_size - 1) // batch_size
            
            # 배치 정보 생성
            batch_infos = []
            for i in range(0, len(p_stock_list), batch_size):
                batch_num = i // batch_size + 1
                batch_stocks = p_stock_list[i:i + batch_size]
                
                batch_infos.append({
                    "stocks": batch_stocks,
                    "batch_num": batch_num,
                    "total_batches": total_batches
                })
            
            logger.info(f"병렬 처리 시작 - 총 {total_batches}개 배치, {self.max_workers}개 워커")
            print(f"[시작] 병렬 처리 시작: {total_batches}개 배치 → {self.max_workers}개 워커")
            
            # 병렬 처리 실행
            all_results = []
            
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # 모든 배치 작업 제출
                future_to_batch = {executor.submit(process_batch, batch_info): batch_info 
                                 for batch_info in batch_infos}
                
                # 완료된 작업 처리
                completed_batches = 0
                for future in as_completed(future_to_batch):
                    batch_info = future_to_batch[future]
                    completed_batches += 1
                    
                    try:
                        batch_results = future.result()
                        if batch_results:
                            all_results.extend(batch_results)
                        
                        # 진행률 출력
                        progress = (completed_batches / total_batches) * 100
                        print(f"[진행률] {completed_batches}/{total_batches} ({progress:.1f}%)")
                        
                    except Exception as e:
                        batch_num = batch_info["batch_num"]
                        logger.error(f"배치 {batch_num} 결과 처리 오류: {e}", exc_info=True)
            
            processing_time = time.time() - start_time
            
            if not all_results:
                logger.error("전체 스크리닝 결과가 없습니다.")
                return False
            
            logger.info(f"전체 스크리닝 완료 - 총 {len(all_results)}개 종목 처리 (소요시간: {processing_time:.1f}초)")
            print(f"[완료] 병렬 처리 완료: {len(all_results)}개 종목 처리 (소요시간: {processing_time:.1f}초)")
            
            # 결과 저장
            save_success = self.screener.save_screening_results(all_results)
            
            if save_success:
                # 통과한 종목 통계
                passed_stocks = [r for r in all_results if r["overall_passed"]]
                logger.info(f"스크리닝 통과 종목: {len(passed_stocks)}개")
                
                # 상위 10개 종목 출력
                top_stocks = sorted(all_results, key=lambda x: x["overall_score"], reverse=True)[:10]
                
                print("\n=== 상위 10개 종목 ===")
                for i, stock in enumerate(top_stocks, 1):
                    print(f"{i:2d}. {stock['stock_code']} ({stock['stock_name']}) - {stock['overall_score']:.1f}점")
                
                # 성능 통계 출력
                sequential_time = len(all_results) * 0.05  # 순차 처리 예상 시간 (배치당 0.05초)
                speedup = sequential_time / processing_time
                
                print("\n[성능통계] 성능 통계:")
                print(f"├─ 병렬 처리 시간: {processing_time:.1f}초")
                print(f"├─ 순차 처리 예상 시간: {sequential_time:.1f}초")
                print(f"├─ 속도 향상: {speedup:.1f}배")
                print(f"└─ 워커 효율성: {speedup / self.max_workers:.1f}")
                
                # 스크리닝 통과 종목을 감시 리스트에 자동 추가
                added_count = self._auto_add_to_watchlist(passed_stocks)
                logger.info(f"감시 리스트 자동 추가 완료: {added_count}개 종목")
                
                return True
            else:
                logger.error("스크리닝 결과 저장 실패")
                return False
                
        except Exception as e:
            logger.error(f"전체 스크리닝 실행 오류: {e}", exc_info=True)
            return False
    
    def _get_all_stock_codes(self) -> List[str]:
        """전체 종목 코드 조회"""
        try:
            # KRX API를 통해 전체 상장 기업 조회
            from core.api.krx_client import KRXClient
            
            krx_client = KRXClient()
            stock_df = krx_client.get_stock_list(market="ALL")
            stock_codes = stock_df['ticker'].tolist()
            
            logger.info(f"전체 상장 종목 수: {len(stock_codes)}개")
            return stock_codes
            
        except Exception as e:
            logger.error(f"전체 종목 조회 오류: {e}", exc_info=True)
            logger.warning("KRX API 오류로 인해 샘플 종목으로 대체합니다")
            
            # 샘플 종목으로 대체
            return [
                "005930", "000660", "035420", "005380", "000270",
                "068270", "207940", "035720", "051910", "006400"
            ]
    
    def _auto_add_to_watchlist(self, p_passed_stocks: List[Dict]) -> int:
        """스크리닝 통과 종목을 감시 리스트에 자동 추가"""
        # 기존 Phase1Workflow와 동일한 로직 사용
        added_count = 0
        
        try:
            logger.info(f"감시 리스트 자동 추가 시작: {len(p_passed_stocks)}개 종목")
            
            for stock in p_passed_stocks:
                stock_code = stock["stock_code"]
                stock_name = stock["stock_name"]
                overall_score = stock["overall_score"]
                
                # 중복 확인 및 추가 로직
                existing_stocks = self.watchlist_manager.list_stocks(p_status="active")
                existing_codes = [s.stock_code for s in existing_stocks]
                
                if stock_code not in existing_codes:
                    # 종목 정보 생성
                    current_price = 50000  # 임시값
                    target_price = int(current_price * 1.15)
                    stop_loss = int(current_price * 0.92)
                    
                    success = self.watchlist_manager.add_stock(
                        p_stock_code=stock_code,
                        p_stock_name=stock_name,
                        p_added_reason="스크리닝 통과",
                        p_target_price=target_price,
                        p_stop_loss=stop_loss,
                        p_sector="기타",
                        p_screening_score=overall_score,
                        p_notes=f"스크리닝 점수: {overall_score:.1f}점"
                    )
                    
                    if success:
                        added_count += 1
            
            logger.info(f"감시 리스트 자동 추가 완료: {added_count}개 종목")
            return added_count
            
        except Exception as e:
            logger.error(f"감시 리스트 자동 추가 오류: {e}", exc_info=True)
            return added_count

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Phase 1 병렬 처리: 감시 리스트 구축 워크플로우")
    
    # 명령어 옵션
    parser.add_argument('--stocks', nargs='+', help='스크리닝할 종목 코드 리스트')
    parser.add_argument('--workers', type=int, help='워커 프로세스 수 (기본값: CPU코어수-1)')
    parser.add_argument('--batch-size', type=int, default=10, help='배치 크기 (기본값: 10)')
    
    args = parser.parse_args()
    
    # 워크플로우 실행
    workflow = Phase1ParallelWorkflow()
    
    # 워커 수 설정
    if args.workers:
        workflow.max_workers = args.workers
    
    try:
        print("[시작] Phase 1 병렬 스크리닝 시작")
        print(f"├─ CPU 코어: {workflow.cpu_count}개")
        print(f"├─ 워커 프로세스: {workflow.max_workers}개")
        print(f"└─ 배치 크기: {args.batch_size}개")
        
        success = workflow.run_full_screening_parallel(args.stocks)
        
        if success:
            print("\n[완료] 병렬 스크리닝 완료!")
        else:
            print("\n[실패] 병렬 스크리닝 실패!")
            
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        logger.error(f"워크플로우 실행 오류: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 