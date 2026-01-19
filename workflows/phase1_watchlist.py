#!/usr/bin/env python3
"""
Phase 1: 감시 리스트 구축 워크플로우
- 전체 스크리닝 실행
- 감시 리스트 관리
- 명령행 인터페이스
"""

import argparse
import sys
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.watchlist.stock_screener import StockScreener
from core.watchlist.stock_screener_parallel import ParallelStockScreener
from core.watchlist.watchlist_manager import WatchlistManager
from core.watchlist.evaluation_engine import EvaluationEngine
from core.utils.log_utils import get_logger
from core.utils.telegram_notifier import get_telegram_notifier
from core.utils.partial_result import PartialResult, save_failed_items

logger = get_logger(__name__)

class Phase1Workflow:
    """Phase 1 워크플로우 클래스"""
    
    def __init__(self, p_parallel_workers: int = 4):
        """초기화 메서드
        
        Args:
            p_parallel_workers: 병렬 처리 워커 수 (기본값: 4)
        """
        self.screener = StockScreener()
        self.parallel_screener = ParallelStockScreener(p_max_workers=p_parallel_workers)
        self.watchlist_manager = WatchlistManager()
        self.evaluation_engine = EvaluationEngine()
        self._v_parallel_workers = p_parallel_workers
        
        logger.info(f"Phase 1 워크플로우 초기화 완료 (병렬 워커: {p_parallel_workers}개)")
    
    def run_screening(self) -> Optional[Dict]:
        """스크리닝 실행 (CLI 인터페이스용)

        Returns:
            결과 딕셔너리 또는 None (실패 시)
            - total_screened: 스크리닝된 총 종목 수
            - added_count: 감시 리스트에 추가된 종목 수
            - duration_seconds: 처리 시간 (초)
        """
        import time
        start_time = time.time()

        try:
            success = self.run_full_screening(p_send_notification=False)
            duration = time.time() - start_time

            if success:
                # 최신 스크리닝 결과 파일에서 통계 가져오기
                _v_screening_files = [f for f in os.listdir("data/watchlist/") if f.startswith("screening_results_")]
                total_screened = 0
                added_count = 0

                if _v_screening_files:
                    _v_latest_file = sorted(_v_screening_files)[-1]
                    _v_filepath = os.path.join("data/watchlist", _v_latest_file)

                    with open(_v_filepath, 'r', encoding='utf-8') as f:
                        _v_data = json.load(f)

                    _v_results = _v_data.get('results', [])
                    total_screened = len(_v_results)
                    added_count = len([r for r in _v_results if r.get('overall_passed', False)])

                return {
                    'total_screened': total_screened,
                    'added_count': added_count,
                    'duration_seconds': duration
                }

            return None

        except Exception as e:
            logger.error(f"run_screening 오류: {e}", exc_info=True)
            return None

    def run_full_screening(self, p_stock_list: Optional[List[str]] = None, p_send_notification: bool = True) -> bool:
        """전체 스크리닝 실행 (배치 처리 최적화)
        
        Args:
            p_stock_list: 스크리닝할 종목 리스트 (None이면 전체 시장)
            
        Returns:
            실행 성공 여부
        """
        try:
            logger.info("=== 전체 스크리닝 시작 (배치 처리) ===")
            
            # 종목 리스트 준비
            if not p_stock_list:
                p_stock_list = self._get_all_stock_codes()
            
            logger.info(f"스크리닝 대상 종목 수: {len(p_stock_list)}개")
            
            # 병렬 처리 설정
            _v_batch_size = self._v_parallel_workers * 10  # 워커 수의 10배로 배치 크기 설정
            
            logger.info(f"🚀 병렬 스크리닝 시작 - 워커: {self._v_parallel_workers}개, 배치크기: {_v_batch_size}")
            print(f"🚀 병렬 스크리닝 시작 - 워커: {self._v_parallel_workers}개")
            
            # 병렬 종합 스크리닝 실행
            _v_all_results = self.parallel_screener.parallel_comprehensive_screening(
                p_stock_list, p_batch_size=_v_batch_size
            )
            
            if not _v_all_results:
                logger.error("전체 스크리닝 결과가 없습니다.")
                return False
            
            logger.info(f"전체 스크리닝 완료 - 총 {len(_v_all_results)}개 종목 처리")
            
            # 결과 저장
            _v_save_success = self.screener.save_screening_results(_v_all_results)
            
            if _v_save_success:
                # 통과한 종목 통계
                _v_passed_stocks = [r for r in _v_all_results if r["overall_passed"]]
                logger.info(f"스크리닝 통과 종목: {len(_v_passed_stocks)}개")
                
                # 상위 10개 종목 출력
                _v_top_stocks = sorted(_v_all_results, key=lambda x: x["overall_score"], reverse=True)[:10]
                
                print("\n=== 상위 10개 종목 ===")
                for i, stock in enumerate(_v_top_stocks, 1):
                    print(f"{i:2d}. {stock['stock_code']} ({stock['stock_name']}) - {stock['overall_score']:.1f}점")
                
                # 시장별 통계 출력
                _v_market_stats = {}
                for stock in _v_passed_stocks:
                    market = stock.get('market', '미분류')
                    _v_market_stats[market] = _v_market_stats.get(market, 0) + 1
                
                print(f"\n=== 시장별 통과 종목 통계 ===")
                for market, count in _v_market_stats.items():
                    print(f"{market}: {count}개")
                
                # 스크리닝 통과 종목을 감시 리스트에 자동 추가
                _v_added_count = self._auto_add_to_watchlist(_v_passed_stocks)
                logger.info(f"감시 리스트 자동 추가 완료: {_v_added_count}개 종목")
                
                # 파티션 저장 및 이력 갱신
                try:
                    self._persist_daily_screening_partition(_v_passed_stocks)
                except Exception as _e:
                    logger.warning(f"스크리닝 파티션 저장 실패 (무시하고 진행): {_e}")

                # 텔레그램 스크리닝 완료 알림 전송 (옵션)
                if p_send_notification:
                    self._send_screening_complete_notification(_v_passed_stocks, _v_all_results)
                
                return True
            else:
                logger.error("스크리닝 결과 저장 실패")
                return False
                
        except Exception as e:
            logger.error(f"전체 스크리닝 실행 오류: {e}", exc_info=True)
            return False
    
    def add_to_watchlist(self, p_stock_code: str, p_target_price: float, 
                        p_stop_loss: float, p_notes: str = "") -> bool:
        """감시 리스트에 종목 추가
        
        Args:
            p_stock_code: 종목 코드
            p_target_price: 목표가
            p_stop_loss: 손절가
            p_notes: 메모
            
        Returns:
            추가 성공 여부
        """
        try:
            logger.info(f"감시 리스트 추가 시도: {p_stock_code}")
            
            # 종목 정보 조회 (더미 데이터)
            _v_stock_info = self._get_stock_info(p_stock_code)
            if not _v_stock_info:
                logger.error(f"종목 정보를 찾을 수 없습니다: {p_stock_code}", exc_info=True)
                return False
            
            # 평가 점수 계산
            _v_score, _v_details = self.evaluation_engine.calculate_comprehensive_score(_v_stock_info)
            
            # 감시 리스트에 추가
            _v_success = self.watchlist_manager.add_stock_legacy(
                p_stock_code=p_stock_code,
                p_stock_name=_v_stock_info.get("stock_name", f"종목{p_stock_code}"),
                p_added_reason="수동 추가",
                p_target_price=p_target_price,
                p_stop_loss=p_stop_loss,
                p_sector=_v_stock_info.get("sector", "기타"),
                p_screening_score=_v_score,
                p_notes=p_notes
            )
            
            if _v_success:
                logger.info(f"감시 리스트 추가 완료: {p_stock_code} (점수: {_v_score:.1f})")
                return True
            else:
                logger.error(f"감시 리스트 추가 실패: {p_stock_code}", exc_info=True)
                return False
                
        except Exception as e:
            logger.error(f"감시 리스트 추가 오류: {e}", exc_info=True)
            return False
    
    def list_watchlist(self, p_status: str = "active", p_sector: Optional[str] = None) -> None:
        """감시 리스트 조회
        
        Args:
            p_status: 상태 필터
            p_sector: 섹터 필터
        """
        try:
            logger.info(f"감시 리스트 조회 - 상태: {p_status}, 섹터: {p_sector}")
            
            _v_stocks = self.watchlist_manager.list_stocks(
                p_status=p_status,
                p_sector=p_sector,
                p_sort_by="screening_score",
                p_ascending=False
            )
            
            if not _v_stocks:
                print("감시 리스트가 비어있습니다.")
                return
            
            print(f"\n=== 감시 리스트 ({len(_v_stocks)}개 종목) ===")
            print(f"{'순위':<4} {'종목코드':<8} {'종목명':<15} {'섹터':<10} {'점수':<6} {'목표가':<10} {'손절가':<10} {'추가일':<12}")
            print("-" * 85)
            
            for i, stock in enumerate(_v_stocks, 1):
                print(f"{i:<4} {stock.stock_code:<8} {stock.stock_name:<15} {stock.sector:<10} "
                      f"{stock.screening_score:<6.1f} {stock.target_price:<10,.0f} {stock.stop_loss:<10,.0f} {stock.added_date:<12}")
            
            # 통계 정보 출력
            _v_stats = self.watchlist_manager.get_statistics()
            print(f"\n=== 통계 정보 ===")
            print(f"총 종목 수: {_v_stats['total_count']}개")
            print(f"활성 종목: {_v_stats['active_count']}개")
            print(f"평균 점수: {_v_stats.get('avg_score', 0.0):.1f}점")
            
            if _v_stats['sectors']:
                print(f"섹터별 분포:")
                for sector, count in _v_stats['sectors'].items():
                    print(f"  - {sector}: {count}개")
                    
        except Exception as e:
            logger.error(f"감시 리스트 조회 오류: {e}", exc_info=True)
    
    def remove_from_watchlist(self, p_stock_code: str, p_permanent: bool = False) -> bool:
        """감시 리스트에서 종목 제거
        
        Args:
            p_stock_code: 종목 코드
            p_permanent: 영구 삭제 여부
            
        Returns:
            제거 성공 여부
        """
        try:
            logger.info(f"감시 리스트 제거: {p_stock_code} (영구삭제: {p_permanent})")
            
            _v_success = self.watchlist_manager.remove_stock(p_stock_code, p_permanent)
            
            if _v_success:
                _v_action = "영구 삭제" if p_permanent else "제거"
                logger.info(f"감시 리스트 {_v_action} 완료: {p_stock_code}")
                return True
            else:
                logger.error(f"감시 리스트 제거 실패: {p_stock_code}", exc_info=True)
                return False
                
        except Exception as e:
            logger.error(f"감시 리스트 제거 오류: {e}", exc_info=True)
            return False
    
    def generate_report(self, p_output_file: Optional[str] = None) -> bool:
        """감시 리스트 리포트 생성
        
        Args:
            p_output_file: 출력 파일 경로
            
        Returns:
            생성 성공 여부
        """
        try:
            logger.info("감시 리스트 리포트 생성 시작")
            
            # 감시 리스트 조회
            _v_stocks = self.watchlist_manager.list_stocks(p_status="active")
            _v_stats = self.watchlist_manager.get_statistics()
            
            # 리포트 내용 생성
            _v_report_lines = []
            _v_report_lines.append("=" * 80)
            _v_report_lines.append("감시 리스트 리포트")
            _v_report_lines.append("=" * 80)
            _v_report_lines.append(f"생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            _v_report_lines.append(f"총 종목 수: {_v_stats['total_count']}개")
            _v_report_lines.append(f"활성 종목: {_v_stats['active_count']}개")
            _v_report_lines.append(f"평균 점수: {_v_stats.get('avg_score', 0.0):.1f}점")
            _v_report_lines.append("")
            
            # 섹터별 분포
            if _v_stats['sectors']:
                _v_report_lines.append("=== 섹터별 분포 ===")
                for sector, count in _v_stats['sectors'].items():
                    _v_report_lines.append(f"{sector}: {count}개")
                _v_report_lines.append("")
            
            # 점수 분포
            _v_score_dist = _v_stats['score_distribution']
            _v_report_lines.append("=== 점수 분포 ===")
            
            # 점수 분포가 새로운 구조인지 확인하고 처리
            if 'high' in _v_score_dist:
                # 구 방식 (high/medium/low)
                _v_report_lines.append(f"고득점 (80점 이상): {_v_score_dist['high']}개")
                _v_report_lines.append(f"중간점 (60-80점): {_v_score_dist['medium']}개")
                _v_report_lines.append(f"저득점 (60점 미만): {_v_score_dist['low']}개")
            else:
                # 신 방식 (구간별 상세 분류)
                high_count = _v_score_dist.get('90-100', 0) + _v_score_dist.get('80-89', 0)
                medium_count = _v_score_dist.get('70-79', 0) + _v_score_dist.get('60-69', 0)
                low_count = (
                    _v_score_dist.get('50-59', 0) + 
                    _v_score_dist.get('40-49', 0) + 
                    _v_score_dist.get('0-39', 0)
                )
                
                _v_report_lines.append(f"고득점 (80점 이상): {high_count}개")
                _v_report_lines.append(f"중간점 (60-80점): {medium_count}개")
                _v_report_lines.append(f"저득점 (60점 미만): {low_count}개")
                
                # 상세 분포도 표시
                _v_report_lines.append("")
                _v_report_lines.append("=== 상세 점수 분포 ===")
                for score_range, count in _v_score_dist.items():
                    if count > 0:
                        _v_report_lines.append(f"{score_range}점: {count}개")
            
            _v_report_lines.append("")
            
            # 상위 종목
            if _v_stats.get('top_stocks'):
                _v_report_lines.append("=== 상위 10개 종목 ===")
                _v_report_lines.append(f"{'순위':<4} {'종목코드':<8} {'종목명':<15} {'섹터':<10} {'점수':<6}")
                _v_report_lines.append("-" * 50)
                
                for i, stock in enumerate(_v_stats['top_stocks'], 1):
                    _v_report_lines.append(f"{i:<4} {stock['stock_code']:<8} {stock['stock_name']:<15} "
                                         f"{stock['sector']:<10} {stock['score']:<6.1f}")
                _v_report_lines.append("")
            else:
                # top_stocks가 없는 경우 활성 종목에서 상위 10개 직접 조회
                _v_active_stocks = sorted(
                    [s for s in self.watchlist_manager.list_stocks("active")],
                    key=lambda x: x.screening_score, 
                    reverse=True
                )[:10]
                
                if _v_active_stocks:
                    _v_report_lines.append("=== 상위 10개 종목 ===")
                    _v_report_lines.append(f"{'순위':<4} {'종목코드':<8} {'종목명':<15} {'섹터':<10} {'점수':<6}")
                    _v_report_lines.append("-" * 50)
                    
                    for i, stock in enumerate(_v_active_stocks, 1):
                        _v_report_lines.append(f"{i:<4} {stock.stock_code:<8} {stock.stock_name:<15} "
                                             f"{stock.sector:<10} {stock.screening_score:<6.1f}")
                    _v_report_lines.append("")
            
            # 전체 종목 목록
            if _v_stocks:
                _v_report_lines.append("=== 전체 종목 목록 ===")
                _v_report_lines.append(f"{'종목코드':<8} {'종목명':<15} {'섹터':<10} {'점수':<6} {'목표가':<10} {'손절가':<10} {'추가일':<12}")
                _v_report_lines.append("-" * 85)
                
                for stock in _v_stocks:
                    _v_report_lines.append(f"{stock.stock_code:<8} {stock.stock_name:<15} {stock.sector:<10} "
                                         f"{stock.screening_score:<6.1f} {stock.target_price:<10,.0f} "
                                         f"{stock.stop_loss:<10,.0f} {stock.added_date:<12}")
            
            # 리포트 저장
            if not p_output_file:
                _v_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                p_output_file = f"data/watchlist/reports/watchlist_report_{_v_timestamp}.txt"
            
            os.makedirs(os.path.dirname(p_output_file), exist_ok=True)
            
            with open(p_output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(_v_report_lines))
            
            logger.info(f"감시 리스트 리포트 생성 완료: {p_output_file}")
            
            # 콘솔에도 출력
            print('\n'.join(_v_report_lines))
            
            return True
            
        except Exception as e:
            logger.error(f"리포트 생성 오류: {e}", exc_info=True)
            return False
    
    def _get_all_stock_codes(self) -> List[str]:
        """전체 종목 코드 조회 (저장된 종목 리스트 파일 사용)
        
        Returns:
            종목 코드 리스트
        """
        try:
            # 저장된 종목 리스트 파일 사용 (데이터 일관성 보장)
            from pathlib import Path
            
            # 프로젝트 루트 경로 기준으로 절대 경로 생성
            _v_project_root = Path(__file__).parent.parent
            _v_stock_dir = _v_project_root / "data" / "stock"
            
            # 가장 최신 종목 리스트 파일 찾기
            _v_stock_list_files = list(_v_stock_dir.glob("krx_stock_list_*.json"))
            if not _v_stock_list_files:
                logger.warning(f"종목 리스트 파일을 찾을 수 없음: {_v_stock_dir}")
                logger.info("KRX에서 종목 리스트를 자동으로 가져옵니다...")

                # KRXClient를 사용해 종목 리스트 파일 생성
                from core.api.krx_client import KRXClient
                krx_client = KRXClient()
                krx_client.save_stock_list()

                # 파일 생성 후 다시 검색
                _v_stock_list_files = list(_v_stock_dir.glob("krx_stock_list_*.json"))
                if not _v_stock_list_files:
                    raise FileNotFoundError("KRX에서 종목 리스트 가져오기 실패")
            
            _v_stock_list_file = max(_v_stock_list_files, key=lambda x: x.name)
            logger.info(f"종목 리스트 파일 사용: {_v_stock_list_file}")
            
            # JSON 파일 로드
            with open(_v_stock_list_file, 'r', encoding='utf-8') as f:
                _v_stock_list = json.load(f)
            
            # 종목 코드 리스트 추출
            stock_codes = [stock['ticker'] for stock in _v_stock_list]
            
            logger.info(f"전체 상장 종목 수: {len(stock_codes)}개")
            
            # 시장별 통계 출력
            market_stats = {}
            for stock in _v_stock_list:
                market = stock.get('market', '미분류')
                # 시장 명칭 통일
                if market == "코스닥":
                    market = "KOSDAQ"
                elif market != "KOSPI":
                    market = "기타"
                    
                market_stats[market] = market_stats.get(market, 0) + 1
            
            for market, count in market_stats.items():
                logger.info(f"{market}: {count}개 종목")
            
            return stock_codes
            
        except Exception as e:
            logger.error(f"전체 종목 조회 오류: {e}", exc_info=True)
            logger.warning("종목 리스트 파일 오류로 인해 샘플 종목으로 대체합니다")
            
            # 파일 오류 시 대표 종목들로 대체 (임시)
            return [
                "005930",  # 삼성전자
                "000660",  # SK하이닉스
                "035420",  # NAVER
                "005380",  # 현대차
                "000270",  # 기아
                "068270",  # 셀트리온
                "207940",  # 삼성바이오로직스
                "035720",  # 카카오
                "051910",  # LG화학
                "006400",  # 삼성SDI
            ]
    
    def _get_stock_info(self, p_stock_code: str) -> Optional[Dict]:
        """종목 정보 조회 (종목 리스트 + 재무 데이터 파일 사용)

        Args:
            p_stock_code: 종목 코드

        Returns:
            종목 정보 딕셔너리 (실제 재무 데이터 포함)
        """
        try:
            # 전체 종목 리스트 파일 로드
            _v_stock_name = None
            _v_market = None
            _v_sector = "기타"

            from pathlib import Path

            # 프로젝트 루트 경로 기준으로 절대 경로 생성
            _v_project_root = Path(__file__).parent.parent
            _v_stock_dir = _v_project_root / "data" / "stock"

            # 가장 최신 종목 리스트 파일 찾기
            _v_stock_list_files = list(_v_stock_dir.glob("krx_stock_list_*.json"))
            if _v_stock_list_files:
                _v_stock_list_file = max(_v_stock_list_files, key=lambda x: x.name)

                try:
                    with open(_v_stock_list_file, 'r', encoding='utf-8') as f:
                        _v_stock_list = json.load(f)

                    # 종목 코드로 검색
                    for stock in _v_stock_list:
                        if stock.get("ticker") == p_stock_code:
                            _v_stock_name = stock.get("name", f"종목{p_stock_code}")
                            _v_market = stock.get("market", "기타")

                            # 시장 명칭 통일
                            if _v_market == "코스닥":
                                _v_market = "KOSDAQ"
                            elif _v_market == "KOSPI":
                                _v_market = "KOSPI"
                            else:
                                _v_market = "기타"

                            break

                    logger.debug(f"종목 정보 로드 성공: {p_stock_code} → {_v_stock_name} ({_v_market})")

                except Exception as e:
                    logger.warning(f"종목 리스트 파일 로드 실패: {e}")
            else:
                logger.warning(f"종목 리스트 파일을 찾을 수 없음: {_v_stock_dir}")

            # 종목 정보가 없으면 기본값 사용
            if not _v_stock_name:
                _v_stock_name = f"종목{p_stock_code}"
                _v_market = "KOSPI" if p_stock_code.startswith(('0', '1', '2', '3')) else "KOSDAQ"
                logger.warning(f"종목 정보 없음, 기본값 사용: {p_stock_code} → {_v_stock_name} ({_v_market})")

            # 섹터 추정 (기본 매핑 사용)
            _v_sector_map = {
                "005930": "반도체", "000660": "반도체",
                "035420": "인터넷", "035720": "인터넷",
                "005380": "자동차", "000270": "자동차",
                "068270": "바이오", "207940": "바이오",
                "051910": "화학", "006400": "배터리",
                "003670": "철강", "096770": "에너지",
                "034730": "통신", "015760": "전력",
                "017670": "통신", "030200": "통신",
                "032830": "금융", "066570": "전자",
                "028260": "건설", "009150": "전자"
            }
            _v_sector = _v_sector_map.get(p_stock_code, "기타")

            # 재무 데이터 로드 (저장된 파일에서)
            _v_fundamental = self._load_fundamental_data(p_stock_code, _v_stock_dir)

            return {
                "stock_code": p_stock_code,
                "stock_name": _v_stock_name,
                "sector": _v_sector,
                "market": _v_market,
                "market_cap": 1000000000000,  # 시가총액은 별도 조회 필요
                "current_price": 50000,       # 현재가는 실시간 조회 필요
                # 재무 데이터 (실제 데이터 또는 기본값)
                "roe": _v_fundamental.get("roe", 0.0),
                "per": _v_fundamental.get("per", 0.0),
                "pbr": _v_fundamental.get("pbr", 0.0),
                "eps": _v_fundamental.get("eps", 0.0),
                "bps": _v_fundamental.get("bps", 0.0),
                "debt_ratio": 50.0,  # 부채비율은 별도 소스 필요
                "revenue_growth": 0.0,
                "operating_margin": 0.0,
                # 기술적 데이터 (실시간 조회 필요 - Phase 2에서 처리)
                "ma_20": 0,
                "ma_60": 0,
                "ma_120": 0,
                "rsi": 50.0,
                "volume_ratio": 1.0,
                "price_momentum_1m": 0.0,
                "volatility": 0.0,
                # 모멘텀 데이터
                "relative_strength": 0.0,
                "price_momentum_3m": 0.0,
                "price_momentum_6m": 0.0,
                "volume_momentum": 0.0,
                "sector_momentum": 0.0
            }

        except Exception as e:
            logger.error(f"종목 정보 조회 오류 - {p_stock_code}: {e}", exc_info=True)
            return None

    def _load_fundamental_data(self, p_stock_code: str, p_stock_dir) -> Dict:
        """DB에서 종목 재무 정보 로드 (파일 폴백)

        Args:
            p_stock_code: 종목 코드
            p_stock_dir: 데이터 디렉토리 경로 (파일 폴백용)

        Returns:
            재무 데이터 딕셔너리
        """
        try:
            # 1. DB에서 먼저 조회 시도
            from core.api.krx_client import KRXClient
            krx_client = KRXClient()
            db_data = krx_client.load_fundamentals_from_db(p_stock_code)

            if db_data:
                logger.debug(f"DB에서 재무 데이터 로드 성공: {p_stock_code}")
                return {
                    'per': float(db_data.get('per', 0)) if db_data.get('per') is not None else 0.0,
                    'pbr': float(db_data.get('pbr', 0)) if db_data.get('pbr') is not None else 0.0,
                    'eps': float(db_data.get('eps', 0)) if db_data.get('eps') is not None else 0.0,
                    'bps': float(db_data.get('bps', 0)) if db_data.get('bps') is not None else 0.0,
                    'roe': float(db_data.get('roe', 0)) if db_data.get('roe') is not None else 0.0,
                    'div': float(db_data.get('div', 0)) if db_data.get('div') is not None else 0.0,
                }

            # 2. DB에 없으면 파일에서 폴백 로드
            logger.debug(f"DB에 재무 데이터 없음, 파일에서 로드 시도: {p_stock_code}")
            import pandas as pd

            # 가장 최신 재무 데이터 파일 찾기
            _v_fundamental_files = list(p_stock_dir.glob("krx_fundamentals_*.json"))

            if not _v_fundamental_files:
                logger.debug(f"재무 데이터 파일 없음, 기본값 사용: {p_stock_code}")
                return {}

            _v_latest_file = max(_v_fundamental_files, key=lambda x: x.name)

            # JSON 파일 로드
            _v_df = pd.read_json(_v_latest_file)

            if _v_df.empty:
                return {}

            # 종목 코드로 검색
            _v_stock_data = _v_df[_v_df['ticker'] == p_stock_code]

            if _v_stock_data.empty:
                logger.debug(f"종목 {p_stock_code} 재무 데이터 없음")
                return {}

            _v_row = _v_stock_data.iloc[0]

            return {
                'per': float(_v_row.get('PER', 0)) if pd.notna(_v_row.get('PER')) else 0.0,
                'pbr': float(_v_row.get('PBR', 0)) if pd.notna(_v_row.get('PBR')) else 0.0,
                'eps': float(_v_row.get('EPS', 0)) if pd.notna(_v_row.get('EPS')) else 0.0,
                'bps': float(_v_row.get('BPS', 0)) if pd.notna(_v_row.get('BPS')) else 0.0,
                'roe': float(_v_row.get('ROE', 0)) if pd.notna(_v_row.get('ROE')) else 0.0,
                'div': float(_v_row.get('DIV', 0)) if pd.notna(_v_row.get('DIV')) else 0.0,
            }

        except Exception as e:
            logger.warning(f"재무 데이터 로드 실패 - {p_stock_code}: {e}")
            return {}
    
    def _load_top_stocks_from_results(self, p_top_count: int = 100) -> List[Dict]:
        """스크리닝 결과 파일에서 상위 종목 로드

        Args:
            p_top_count: 가져올 상위 종목 수 (기본값: 100, API 호출 제한 고려)

        Returns:
            상위 종목 리스트 (실패 시 빈 리스트)
        """
        try:
            _v_screening_files = [
                f for f in os.listdir("data/watchlist/")
                if f.startswith("screening_results_")
            ]
            if not _v_screening_files:
                logger.warning("스크리닝 결과 파일이 없습니다.")
                return []

            _v_latest_file = sorted(_v_screening_files)[-1]
            _v_filepath = os.path.join("data/watchlist", _v_latest_file)

            with open(_v_filepath, 'r', encoding='utf-8') as f:
                _v_data = json.load(f)

            _v_all_results = _v_data.get('results', [])
            _v_top_stocks = sorted(
                _v_all_results,
                key=lambda x: x.get('overall_score', 0),
                reverse=True
            )[:p_top_count]

            logger.info(f"상위 {len(_v_top_stocks)}개 종목을 감시 리스트 후보로 선정")
            return _v_top_stocks

        except Exception as e:
            logger.error(f"스크리닝 결과 파일 로드 오류: {e}", exc_info=True)
            return []

    def _process_single_stock_for_watchlist(
        self,
        p_stock: Dict,
        p_existing_codes: set
    ) -> tuple[bool, bool, Optional[str]]:
        """단일 종목을 감시 리스트에 추가 처리

        Args:
            p_stock: 종목 정보 딕셔너리
            p_existing_codes: 기존 감시 리스트 종목 코드 집합

        Returns:
            (성공 여부, 신규 추가 여부, 오류 메시지)
            - 성공 여부: 처리 성공 (이미 존재하는 경우 포함)
            - 신규 추가 여부: 실제로 새로 추가된 경우 True
            - 오류 메시지: 실패 시 오류 내용, 성공 시 None
        """
        _v_stock_code = p_stock.get("stock_code", "unknown")
        _v_stock_name = p_stock.get("stock_name", "")
        _v_overall_score = p_stock.get("overall_score", 0.0)
        _v_sector = p_stock.get("sector", "기타")

        # 이미 감시 리스트에 있는지 확인
        if _v_stock_code in p_existing_codes:
            logger.debug(f"이미 감시 리스트에 존재: {_v_stock_code}")
            return (True, False, None)  # 성공, 신규 아님

        # 종목 정보 조회
        _v_stock_info = self._get_stock_info(_v_stock_code)
        if not _v_stock_info:
            return (False, False, "종목 정보 조회 실패")

        # 목표가와 손절가 계산 (현재가 기준)
        _v_current_price = _v_stock_info.get("current_price", 50000)
        _v_target_price = int(_v_current_price * 1.15)  # 15% 상승 목표
        _v_stop_loss = int(_v_current_price * 0.92)     # 8% 하락 손절

        # 추가 사유 결정
        _v_reason = (
            "스크리닝 통과" if p_stock.get('overall_passed', False)
            else "스크리닝 상위 종목"
        )

        # 감시 리스트에 추가
        _v_success = self.watchlist_manager.add_stock_legacy(
            p_stock_code=_v_stock_code,
            p_stock_name=_v_stock_name,
            p_added_reason=_v_reason,
            p_target_price=_v_target_price,
            p_stop_loss=_v_stop_loss,
            p_sector=_v_sector,
            p_screening_score=_v_overall_score,
            p_notes=f"스크리닝 점수: {_v_overall_score:.1f}점"
        )

        if _v_success:
            logger.info(
                f"감시 리스트 추가 성공: {_v_stock_code} ({_v_stock_name}) "
                f"- {_v_overall_score:.1f}점 ({_v_sector})"
            )
            return (True, True, None)  # 성공, 신규 추가
        else:
            return (False, False, "감시 리스트 추가 실패")

    def _auto_add_to_watchlist(self, p_passed_stocks: List[Dict]) -> int:
        """스크리닝 통과 종목을 감시 리스트에 자동 추가 (부분 실패 허용)

        Args:
            p_passed_stocks: 스크리닝 통과 종목 리스트

        Returns:
            추가된 종목 수
        """
        _v_added_count = 0

        # 통과 종목이 없으면 상위 점수 종목들을 선택 (최대 100개로 제한)
        if not p_passed_stocks:
            logger.info("통과 종목이 없으므로 상위 점수 종목들을 감시 리스트에 추가합니다.")
            p_passed_stocks = self._load_top_stocks_from_results(p_top_count=100)
            if not p_passed_stocks:
                return 0

        logger.info(f"감시 리스트 자동 추가 시작: {len(p_passed_stocks)}개 종목")

        # 부분 실패 허용 결과 추적
        _v_partial_result = PartialResult[str](min_success_rate=0.9)

        # 기존 감시 리스트 조회 (루프 밖에서 한 번만)
        _v_existing_stocks = self.watchlist_manager.list_stocks(p_status="active")
        _v_existing_codes = {s.stock_code for s in _v_existing_stocks}

        # 각 종목 처리
        for stock in p_passed_stocks:
            _v_stock_code = stock.get("stock_code", "unknown")

            try:
                _v_success, _v_is_new, _v_error = self._process_single_stock_for_watchlist(
                    stock, _v_existing_codes
                )

                if _v_success:
                    _v_partial_result.add_success(_v_stock_code)
                    if _v_is_new:
                        _v_added_count += 1
                else:
                    _v_partial_result.add_failure(_v_stock_code, _v_error or "알 수 없는 오류")

            except Exception as e:
                _v_partial_result.add_failure(_v_stock_code, str(e))

        # 결과 로깅 및 저장
        self._finalize_watchlist_results(_v_partial_result, len(p_passed_stocks), _v_added_count)

        return _v_added_count

    def _finalize_watchlist_results(
        self,
        p_partial_result: PartialResult,
        p_total_count: int,
        p_added_count: int
    ) -> None:
        """감시 리스트 추가 결과 로깅 및 저장

        Args:
            p_partial_result: 부분 결과 객체
            p_total_count: 처리 대상 총 종목 수
            p_added_count: 실제 추가된 종목 수
        """
        # 부분 실패 결과 로깅
        p_partial_result.log_summary("감시 리스트 자동 추가")

        # 실패 항목 저장
        if p_partial_result.failed:
            save_failed_items(
                p_partial_result.failed,
                "phase1_watchlist_add",
                "data/logs/failures"
            )

        # 성공률 체크 및 경고
        if not p_partial_result.is_acceptable:
            logger.warning(
                f"⚠️ 감시 리스트 추가 성공률({p_partial_result.success_rate:.1%})이 "
                f"최소 기준({p_partial_result.min_success_rate:.0%}) 미만입니다!"
            )

        logger.info(
            f"감시 리스트 자동 추가 완료: {p_added_count}/{p_total_count}개 종목 "
            f"(성공률: {p_partial_result.success_rate:.1%})"
        )
    
    def _send_screening_complete_notification(self, passed_stocks: List[Dict], all_results: List[Dict]) -> None:
        """스크리닝 완료 텔레그램 알림 전송"""
        try:
            notifier = get_telegram_notifier()
            if not notifier.is_enabled():
                logger.debug("텔레그램 알림이 비활성화됨")
                return
            
            # 통계 정보 생성
            total_stocks = len(all_results)
            passed_count = len(passed_stocks)
            avg_score = sum(r.get('overall_score', 0) for r in passed_stocks) / passed_count if passed_count > 0 else 0.0
            
            # 섹터별 통계 생성
            sector_stats = {}
            for stock in passed_stocks:
                sector = stock.get('sector', '기타')
                sector_stats[sector] = sector_stats.get(sector, 0) + 1
            
            stats = {
                'total_count': passed_count,
                'avg_score': avg_score,
                'sectors': sector_stats
            }
            
            # 스크리닝 완료 알림 전송
            success = notifier.send_screening_complete(stats)
            if success:
                logger.info("스크리닝 완료 텔레그램 알림 전송 성공")
                print("📱 스크리닝 완료 텔레그램 알림 전송됨")
            else:
                logger.warning("스크리닝 완료 텔레그램 알림 전송 실패")
                
        except Exception as e:
            logger.error(f"스크리닝 완료 알림 전송 오류: {e}", exc_info=True)

    def _persist_daily_screening_partition(self, passed_stocks: List[Dict]) -> None:
        """당일 스크리닝 통과 종목 파티션 저장 (DB 우선, JSON 폴백)

        Note: 스크리닝 결과는 이미 stock_screener.save_screening_results()에서 DB에 저장됨.
        이 함수는 DB 저장 실패 시에만 JSON 폴백으로 저장.
        """
        from datetime import datetime
        from pathlib import Path
        import json

        try:
            today_key = datetime.now().strftime("%Y%m%d")
            today_date = datetime.now().date()

            # === 1. DB에 이미 저장되었는지 확인 ===
            db_has_data = False
            try:
                from core.database.session import DatabaseSession
                from core.database.models import ScreeningResult

                db = DatabaseSession()
                with db.get_session() as session:
                    count = session.query(ScreeningResult).filter(
                        ScreeningResult.screening_date == today_date,
                        ScreeningResult.passed == 1
                    ).count()
                    db_has_data = count > 0
                    if db_has_data:
                        logger.info(f"스크리닝 파티션 DB 확인: {count}건 (JSON 저장 스킵)")
            except Exception as e:
                logger.warning(f"DB 확인 실패: {e}")

            # === 2. DB에 없으면 JSON 폴백 저장 ===
            if not db_has_data:
                out_dir = Path("data/watchlist")
                out_dir.mkdir(parents=True, exist_ok=True)
                part_file = out_dir / f"screening_{today_key}.json"

                payload = {
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "timestamp": datetime.now().isoformat(),
                    "passed_count": len(passed_stocks),
                    "stocks": [
                        {
                            "stock_code": s.get("stock_code"),
                            "stock_name": s.get("stock_name"),
                            "sector": s.get("sector", ""),
                            "overall_score": s.get("overall_score", 0.0),
                        }
                        for s in passed_stocks
                    ],
                    "db_fallback": True
                }
                with part_file.open("w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                logger.info(f"스크리닝 파티션 JSON 폴백 저장: {part_file}")

        except Exception as e:
            logger.warning(f"스크리닝 파티션 저장 실패: {e}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="Phase 1: 감시 리스트 구축 워크플로우")
    
    # 서브커맨드 설정
    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령')
    
    # 스크리닝 명령
    screen_parser = subparsers.add_parser('screen', help='전체 스크리닝 실행')
    screen_parser.add_argument('--stocks', nargs='+', help='스크리닝할 종목 코드 리스트')
    
    # 감시 리스트 조회 명령
    list_parser = subparsers.add_parser('list', help='감시 리스트 조회')
    list_parser.add_argument('--status', default='active', help='상태 필터 (active/paused/removed)')
    list_parser.add_argument('--sector', help='섹터 필터')
    
    # 종목 추가 명령
    add_parser = subparsers.add_parser('add', help='감시 리스트에 종목 추가')
    add_parser.add_argument('stock_code', help='종목 코드')
    add_parser.add_argument('target_price', type=float, help='목표가')
    add_parser.add_argument('stop_loss', type=float, help='손절가')
    add_parser.add_argument('--notes', default='', help='메모')
    
    # 종목 제거 명령
    remove_parser = subparsers.add_parser('remove', help='감시 리스트에서 종목 제거')
    remove_parser.add_argument('stock_code', help='종목 코드')
    remove_parser.add_argument('--permanent', action='store_true', help='영구 삭제')
    
    # 리포트 생성 명령
    report_parser = subparsers.add_parser('report', help='감시 리스트 리포트 생성')
    report_parser.add_argument('--output', help='출력 파일 경로')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 워크플로우 실행 (병렬 워커 수 설정)
    workflow = Phase1Workflow(p_parallel_workers=4)
    
    try:
        if args.command == 'screen':
            success = workflow.run_full_screening(args.stocks)
            sys.exit(0 if success else 1)
            
        elif args.command == 'list':
            workflow.list_watchlist(args.status, args.sector)
            
        elif args.command == 'add':
            success = workflow.add_to_watchlist(args.stock_code, args.target_price, args.stop_loss, args.notes)
            sys.exit(0 if success else 1)
            
        elif args.command == 'remove':
            success = workflow.remove_from_watchlist(args.stock_code, args.permanent)
            sys.exit(0 if success else 1)
            
        elif args.command == 'report':
            success = workflow.generate_report(args.output)
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        logger.error(f"워크플로우 실행 오류: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main() 