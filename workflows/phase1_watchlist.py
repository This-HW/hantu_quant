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
from datetime import datetime
from typing import List, Dict, Optional

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.watchlist.stock_screener import StockScreener
from core.watchlist.watchlist_manager import WatchlistManager
from core.watchlist.evaluation_engine import EvaluationEngine
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class Phase1Workflow:
    """Phase 1 워크플로우 클래스"""
    
    def __init__(self):
        """초기화 메서드"""
        self.screener = StockScreener()
        self.watchlist_manager = WatchlistManager()
        self.evaluation_engine = EvaluationEngine()
        
        logger.info("Phase 1 워크플로우 초기화 완료")
    
    def run_full_screening(self, p_stock_list: Optional[List[str]] = None) -> bool:
        """전체 스크리닝 실행
        
        Args:
            p_stock_list: 스크리닝할 종목 리스트 (None이면 전체 시장)
            
        Returns:
            실행 성공 여부
        """
        try:
            logger.info("=== 전체 스크리닝 시작 ===")
            
            # 종목 리스트 준비
            if not p_stock_list:
                p_stock_list = self._get_all_stock_codes()
            
            logger.info(f"스크리닝 대상 종목 수: {len(p_stock_list)}개")
            
            # 스크리닝 실행
            _v_screening_results = self.screener.comprehensive_screening(p_stock_list)
            
            if not _v_screening_results:
                logger.error("스크리닝 결과가 없습니다.")
                return False
            
            # 결과 저장
            _v_save_success = self.screener.save_screening_results(_v_screening_results)
            
            if _v_save_success:
                logger.info(f"스크리닝 완료 - 총 {len(_v_screening_results)}개 종목 처리")
                
                # 통과한 종목 통계
                _v_passed_stocks = [r for r in _v_screening_results if r["overall_passed"]]
                logger.info(f"스크리닝 통과 종목: {len(_v_passed_stocks)}개")
                
                # 상위 10개 종목 출력
                _v_top_stocks = sorted(_v_screening_results, key=lambda x: x["overall_score"], reverse=True)[:10]
                
                print("\n=== 상위 10개 종목 ===")
                for i, stock in enumerate(_v_top_stocks, 1):
                    print(f"{i:2d}. {stock['stock_code']} ({stock['stock_name']}) - {stock['overall_score']:.1f}점")
                
                # 스크리닝 통과 종목을 감시 리스트에 자동 추가
                _v_added_count = self._auto_add_to_watchlist(_v_passed_stocks)
                logger.info(f"감시 리스트 자동 추가 완료: {_v_added_count}개 종목")
                
                return True
            else:
                logger.error("스크리닝 결과 저장 실패")
                return False
                
        except Exception as e:
            logger.error(f"전체 스크리닝 실행 오류: {e}")
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
                logger.error(f"종목 정보를 찾을 수 없습니다: {p_stock_code}")
                return False
            
            # 평가 점수 계산
            _v_score, _v_details = self.evaluation_engine.calculate_comprehensive_score(_v_stock_info)
            
            # 감시 리스트에 추가
            _v_success = self.watchlist_manager.add_stock(
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
                logger.error(f"감시 리스트 추가 실패: {p_stock_code}")
                return False
                
        except Exception as e:
            logger.error(f"감시 리스트 추가 오류: {e}")
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
            print(f"평균 점수: {_v_stats['average_score']:.1f}점")
            
            if _v_stats['sector_distribution']:
                print(f"섹터별 분포:")
                for sector, count in _v_stats['sector_distribution'].items():
                    print(f"  - {sector}: {count}개")
                    
        except Exception as e:
            logger.error(f"감시 리스트 조회 오류: {e}")
    
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
                logger.error(f"감시 리스트 제거 실패: {p_stock_code}")
                return False
                
        except Exception as e:
            logger.error(f"감시 리스트 제거 오류: {e}")
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
            _v_report_lines.append(f"평균 점수: {_v_stats['average_score']:.1f}점")
            _v_report_lines.append("")
            
            # 섹터별 분포
            if _v_stats['sector_distribution']:
                _v_report_lines.append("=== 섹터별 분포 ===")
                for sector, count in _v_stats['sector_distribution'].items():
                    _v_report_lines.append(f"{sector}: {count}개")
                _v_report_lines.append("")
            
            # 점수 분포
            _v_score_dist = _v_stats['score_distribution']
            _v_report_lines.append("=== 점수 분포 ===")
            _v_report_lines.append(f"고득점 (80점 이상): {_v_score_dist['high']}개")
            _v_report_lines.append(f"중간점 (60-80점): {_v_score_dist['medium']}개")
            _v_report_lines.append(f"저득점 (60점 미만): {_v_score_dist['low']}개")
            _v_report_lines.append("")
            
            # 상위 종목
            if _v_stats['top_stocks']:
                _v_report_lines.append("=== 상위 10개 종목 ===")
                _v_report_lines.append(f"{'순위':<4} {'종목코드':<8} {'종목명':<15} {'섹터':<10} {'점수':<6}")
                _v_report_lines.append("-" * 50)
                
                for i, stock in enumerate(_v_stats['top_stocks'], 1):
                    _v_report_lines.append(f"{i:<4} {stock['stock_code']:<8} {stock['stock_name']:<15} "
                                         f"{stock['sector']:<10} {stock['score']:<6.1f}")
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
            logger.error(f"리포트 생성 오류: {e}")
            return False
    
    def _get_all_stock_codes(self) -> List[str]:
        """전체 종목 코드 조회
        
        Returns:
            종목 코드 리스트
        """
        # 더미 데이터 (실제로는 KRX API 등에서 조회)
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
            "003670",  # 포스코홀딩스
            "096770",  # SK이노베이션
            "034730",  # SK
            "015760",  # 한국전력
            "017670",  # SK텔레콤
            "030200",  # KT
            "032830",  # 삼성생명
            "066570",  # LG전자
            "028260",  # 삼성물산
            "009150"   # 삼성전기
        ]
    
    def _get_stock_info(self, p_stock_code: str) -> Optional[Dict]:
        """종목 정보 조회
        
        Args:
            p_stock_code: 종목 코드
            
        Returns:
            종목 정보 딕셔너리
        """
        # 더미 데이터 (실제로는 API에서 조회)
        _v_stock_names = {
            "005930": "삼성전자",
            "000660": "SK하이닉스",
            "035420": "NAVER",
            "005380": "현대차",
            "000270": "기아",
            "068270": "셀트리온",
            "207940": "삼성바이오로직스",
            "035720": "카카오",
            "051910": "LG화학",
            "006400": "삼성SDI",
            "003670": "포스코홀딩스",
            "096770": "SK이노베이션",
            "034730": "SK",
            "015760": "한국전력",
            "017670": "SK텔레콤",
            "030200": "KT",
            "032830": "삼성생명",
            "066570": "LG전자",
            "028260": "삼성물산",
            "009150": "삼성전기"
        }
        
        _v_stock_name = _v_stock_names.get(p_stock_code, f"종목{p_stock_code}")
        
        return {
            "stock_code": p_stock_code,
            "stock_name": _v_stock_name,
            "sector": "기타",
            "market_cap": 1000000000000,
            "current_price": 50000,
            # 재무 데이터
            "roe": 12.5,
            "per": 15.2,
            "pbr": 1.1,
            "debt_ratio": 45.2,
            "revenue_growth": 8.5,
            "operating_margin": 12.3,
            # 기술적 데이터
            "ma_20": 49000,
            "ma_60": 48000,
            "ma_120": 47000,
            "rsi": 45.2,
            "volume_ratio": 1.8,
            "price_momentum_1m": 5.2,
            "volatility": 0.25,
            # 모멘텀 데이터
            "relative_strength": 0.1,
            "price_momentum_3m": 8.3,
            "price_momentum_6m": 15.7,
            "volume_momentum": 0.2,
            "sector_momentum": 0.05
        }
    
    def _auto_add_to_watchlist(self, p_passed_stocks: List[Dict]) -> int:
        """스크리닝 통과 종목을 감시 리스트에 자동 추가
        
        Args:
            p_passed_stocks: 스크리닝 통과 종목 리스트
            
        Returns:
            추가된 종목 수
        """
        _v_added_count = 0
        
        try:
            logger.info(f"감시 리스트 자동 추가 시작: {len(p_passed_stocks)}개 종목")
            
            for stock in p_passed_stocks:
                _v_stock_code = stock["stock_code"]
                _v_stock_name = stock["stock_name"]
                _v_overall_score = stock["overall_score"]
                
                # 이미 감시 리스트에 있는지 확인
                _v_existing_stocks = self.watchlist_manager.list_stocks(p_status="active")
                _v_existing_codes = [s.stock_code for s in _v_existing_stocks]
                
                if _v_stock_code in _v_existing_codes:
                    logger.info(f"이미 감시 리스트에 존재: {_v_stock_code}")
                    continue
                
                # 종목 정보 조회
                _v_stock_info = self._get_stock_info(_v_stock_code)
                if not _v_stock_info:
                    logger.warning(f"종목 정보 조회 실패: {_v_stock_code}")
                    continue
                
                # 목표가와 손절가 계산 (현재가 기준)
                _v_current_price = _v_stock_info.get("current_price", 50000)
                _v_target_price = int(_v_current_price * 1.15)  # 15% 상승 목표
                _v_stop_loss = int(_v_current_price * 0.92)     # 8% 하락 손절
                
                # 섹터 정보 설정
                _v_sector_map = {
                    "005930": "반도체",
                    "000660": "반도체", 
                    "035420": "인터넷",
                    "005380": "자동차",
                    "000270": "자동차",
                    "068270": "바이오",
                    "207940": "바이오",
                    "035720": "인터넷",
                    "051910": "화학",
                    "006400": "배터리",
                    "003670": "철강",
                    "096770": "에너지",
                    "034730": "통신",
                    "015760": "전력",
                    "017670": "통신",
                    "030200": "통신",
                    "032830": "금융",
                    "066570": "전자",
                    "028260": "건설",
                    "009150": "전자"
                }
                _v_sector = _v_sector_map.get(_v_stock_code, "기타")
                
                # 감시 리스트에 추가
                _v_success = self.watchlist_manager.add_stock(
                    p_stock_code=_v_stock_code,
                    p_stock_name=_v_stock_name,
                    p_added_reason="스크리닝 통과",
                    p_target_price=_v_target_price,
                    p_stop_loss=_v_stop_loss,
                    p_sector=_v_sector,
                    p_screening_score=_v_overall_score,
                    p_notes=f"스크리닝 점수: {_v_overall_score:.1f}점"
                )
                
                if _v_success:
                    _v_added_count += 1
                    logger.info(f"감시 리스트 추가 성공: {_v_stock_code} ({_v_stock_name}) - {_v_overall_score:.1f}점")
                else:
                    logger.error(f"감시 리스트 추가 실패: {_v_stock_code}")
            
            logger.info(f"감시 리스트 자동 추가 완료: {_v_added_count}/{len(p_passed_stocks)}개 종목")
            return _v_added_count
            
        except Exception as e:
            logger.error(f"감시 리스트 자동 추가 오류: {e}")
            return _v_added_count

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
    
    # 워크플로우 실행
    workflow = Phase1Workflow()
    
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
        logger.error(f"워크플로우 실행 오류: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 