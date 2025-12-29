#!/usr/bin/env python3
"""
Phase 2: 일일 선정 CLI 워크플로우
가격 매력도 분석, 일일 업데이트, 선정 기준 관리를 통합한 명령어 인터페이스
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.daily_selection.price_analyzer import PriceAnalyzer, PriceAttractiveness
from core.daily_selection.price_analyzer_parallel import ParallelPriceAnalyzer
from core.daily_selection.daily_updater import DailyUpdater, FilteringCriteria
from core.daily_selection.selection_criteria import SelectionCriteriaManager, MarketCondition, SelectionCriteria
from core.watchlist.watchlist_manager import WatchlistManager
from core.utils.log_utils import get_logger
from core.utils.telegram_notifier import get_telegram_notifier
from core.utils.partial_result import PartialResult, save_failed_items

logger = get_logger(__name__)

class Phase2CLI:
    """Phase 2 CLI 메인 클래스"""
    
    def __init__(self, p_parallel_workers: int = 4):
        """초기화
        
        Args:
            p_parallel_workers: 병렬 처리 워커 수 (기본값: 4)
        """
        self._v_price_analyzer = PriceAnalyzer()
        self._v_parallel_price_analyzer = ParallelPriceAnalyzer(p_max_workers=p_parallel_workers)
        self._v_daily_updater = DailyUpdater()
        self._v_criteria_manager = SelectionCriteriaManager()
        self._v_watchlist_manager = WatchlistManager()
        self._v_parallel_workers = p_parallel_workers
        
        logger.info(f"Phase 2 CLI 초기화 완료 (병렬 워커: {p_parallel_workers}개)")

    def run_update(self) -> Optional[Dict]:
        """일일 업데이트 실행 (CLI 인터페이스용)

        Returns:
            결과 딕셔너리 또는 None (실패 시)
            - evaluated_count: 평가된 종목 수
            - selected_count: 선정된 종목 수
            - duration_seconds: 처리 시간 (초)
            - selections: 선정된 종목 리스트
        """
        import time
        start_time = time.time()

        try:
            # 일일 업데이트 실행
            success = self._v_daily_updater.run_daily_update(p_force_run=True)
            duration = time.time() - start_time

            if success:
                # 최신 선정 결과 가져오기
                latest_result = self._v_daily_updater.get_latest_selection()
                selected_stocks = latest_result.get('data', {}).get('selected_stocks', []) if latest_result else []

                # 감시 리스트 수 조회
                watchlist_stocks = self._v_watchlist_manager.list_stocks(p_status="active")

                return {
                    'evaluated_count': len(watchlist_stocks),
                    'selected_count': len(selected_stocks),
                    'duration_seconds': duration,
                    'selections': [
                        {
                            'code': s.get('stock_code', ''),
                            'name': s.get('stock_name', ''),
                            'score': s.get('price_attractiveness', 0),
                            'signal': 'BUY' if s.get('price_attractiveness', 0) >= 70 else 'HOLD'
                        }
                        for s in selected_stocks
                    ]
                }

            return None

        except Exception as e:
            logger.error(f"run_update 오류: {e}")
            return None

    def run_analysis(self) -> Optional[Dict]:
        """상세 분석 실행 (CLI 인터페이스용)

        Returns:
            결과 딕셔너리 또는 None (실패 시)
            - evaluated_count: 평가된 종목 수
            - selected_count: 선정된 종목 수
            - duration_seconds: 처리 시간 (초)
            - selections: 선정된 종목 리스트
        """
        import time
        start_time = time.time()

        try:
            # 전체 감시 리스트 분석 실행
            results = self._analyze_all_stocks()
            duration = time.time() - start_time

            if results:
                # 상위 종목 선정 (점수 70점 이상)
                selected = [r for r in results if r.total_score >= 70]

                return {
                    'evaluated_count': len(results),
                    'selected_count': len(selected),
                    'duration_seconds': duration,
                    'selections': [
                        {
                            'code': r.stock_code,
                            'name': r.stock_name,
                            'score': r.total_score,
                            'signal': 'BUY' if r.total_score >= 80 else 'HOLD' if r.total_score >= 70 else 'WAIT'
                        }
                        for r in sorted(results, key=lambda x: x.total_score, reverse=True)[:10]
                    ]
                }

            return None

        except Exception as e:
            logger.error(f"run_analysis 오류: {e}")
            return None

    def run(self):
        """CLI 실행"""
        parser = argparse.ArgumentParser(
            description="한투 퀀트 Phase 2: 일일 선정 시스템",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
사용 예시:
  # 일일 업데이트 실행
  python workflows/phase2_daily_selection.py update
  
  # 가격 분석 실행
  python workflows/phase2_daily_selection.py analyze --stock-code 005930
  
  # 일일 선정 결과 조회
  python workflows/phase2_daily_selection.py show --date 2024-01-15
  
  # 선정 기준 조회
  python workflows/phase2_daily_selection.py criteria --market bull_market
  
  # 스케줄러 시작
  python workflows/phase2_daily_selection.py scheduler --start
            """
        )
        
        subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령어')
        
        # 1. 일일 업데이트 명령어
        update_parser = subparsers.add_parser('update', help='일일 업데이트 실행')
        update_parser.add_argument('--force', action='store_true', help='강제 실행')
        update_parser.add_argument('--market-condition', choices=['bull_market', 'bear_market', 'sideways', 'volatile', 'recovery'],
                                 help='시장 상황 지정')
        
        # 2. 가격 분석 명령어
        analyze_parser = subparsers.add_parser('analyze', help='가격 매력도 분석')
        analyze_parser.add_argument('--stock-code', help='종목코드')
        analyze_parser.add_argument('--all', action='store_true', help='감시 리스트 전체 분석')
        analyze_parser.add_argument('--save', action='store_true', help='결과 저장')
        
        # 3. 선정 결과 조회 명령어
        show_parser = subparsers.add_parser('show', help='일일 선정 결과 조회')
        show_parser.add_argument('--date', help='조회 날짜 (YYYY-MM-DD)')
        show_parser.add_argument('--latest', action='store_true', help='최신 결과 조회')
        show_parser.add_argument('--history', type=int, default=7, help='이력 조회 일수')
        show_parser.add_argument('--format', choices=['table', 'json'], default='table', help='출력 형식')
        
        # 4. 선정 기준 관리 명령어
        criteria_parser = subparsers.add_parser('criteria', help='선정 기준 관리')
        criteria_parser.add_argument('--market', choices=['bull_market', 'bear_market', 'sideways', 'volatile', 'recovery'],
                                   help='시장 상황')
        criteria_parser.add_argument('--optimize', action='store_true', help='기준 최적화')
        criteria_parser.add_argument('--compare', action='store_true', help='기준 성과 비교')
        criteria_parser.add_argument('--summary', action='store_true', help='기준 요약 조회')
        
        # 5. 스케줄러 관리 명령어
        scheduler_parser = subparsers.add_parser('scheduler', help='스케줄러 관리')
        scheduler_parser.add_argument('--start', action='store_true', help='스케줄러 시작')
        scheduler_parser.add_argument('--stop', action='store_true', help='스케줄러 중지')
        scheduler_parser.add_argument('--status', action='store_true', help='스케줄러 상태 조회')
        
        # 6. 성과 분석 명령어
        performance_parser = subparsers.add_parser('performance', help='성과 분석')
        performance_parser.add_argument('--period', type=int, default=30, help='분석 기간 (일)')
        performance_parser.add_argument('--sector', help='섹터별 분석')
        performance_parser.add_argument('--export', help='결과 내보내기 파일 경로')
        
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            return
        
        try:
            # 명령어별 실행
            if args.command == 'update':
                self._handle_update(args)
            elif args.command == 'analyze':
                self._handle_analyze(args)
            elif args.command == 'show':
                self._handle_show(args)
            elif args.command == 'criteria':
                self._handle_criteria(args)
            elif args.command == 'scheduler':
                self._handle_scheduler(args)
            elif args.command == 'performance':
                self._handle_performance(args)
                
        except Exception as e:
            logger.error(f"명령어 실행 오류: {e}")
            print(f"❌ 오류: {e}")
    
    def _handle_update(self, p_args):
        """일일 업데이트 처리
        
        Args:
            p_args: 명령어 인자
        """
        print("🔄 일일 업데이트 시작...")
        
        # 시장 상황 설정
        if p_args.market_condition:
            print(f"📊 시장 상황: {p_args.market_condition}")
        
        # 업데이트 실행
        success = self._v_daily_updater.run_daily_update(p_force_run=p_args.force)
        
        if success:
            print("✅ 일일 업데이트 완료!")
            
            # 결과 요약 출력
            latest_result = self._v_daily_updater.get_latest_selection()
            if latest_result:
                self._print_update_summary(latest_result)
        else:
            print("❌ 일일 업데이트 실패")
    
    def _handle_analyze(self, p_args):
        """가격 분석 처리
        
        Args:
            p_args: 명령어 인자
        """
        print("📈 가격 매력도 분석 시작...")
        
        if p_args.stock_code:
            # 단일 종목 분석 (실데이터 조회)
            result = self._analyze_single_stock(p_args.stock_code)
            if result:
                self._print_analysis_result(result)
        
        elif p_args.all:
            # 전체 감시 리스트 분석 (실데이터 조회)
            results = self._analyze_all_stocks()
            if results:
                self._print_analysis_results(results)
                
                if p_args.save:
                    self._v_price_analyzer.save_analysis_results(results)
                    print("💾 분석 결과 저장 완료")
        
        else:
            print("❌ 종목코드 또는 --all 옵션을 지정해주세요")
    
    def _handle_show(self, p_args):
        """선정 결과 조회 처리
        
        Args:
            p_args: 명령어 인자
        """
        if p_args.latest:
            # 최신 결과 조회
            result = self._v_daily_updater.get_latest_selection()
            if result:
                self._print_selection_result(result, p_args.format)
            else:
                print("❌ 최신 선정 결과가 없습니다")
        
        elif p_args.date:
            # 특정 날짜 결과 조회
            result = self._get_selection_by_date(p_args.date)
            if result:
                self._print_selection_result(result, p_args.format)
            else:
                print(f"❌ {p_args.date} 날짜의 선정 결과가 없습니다")
        
        else:
            # 이력 조회
            history = self._v_daily_updater.get_selection_history(p_args.history)
            if history:
                self._print_selection_history(history, p_args.format)
            else:
                print("❌ 선정 이력이 없습니다")
    
    def _handle_criteria(self, p_args):
        """선정 기준 관리 처리
        
        Args:
            p_args: 명령어 인자
        """
        if p_args.summary:
            # 기준 요약 조회
            summary = self._v_criteria_manager.get_criteria_summary()
            self._print_criteria_summary(summary)
        
        elif p_args.market:
            # 특정 시장 상황 기준 조회
            market_condition = MarketCondition(p_args.market)
            criteria = self._v_criteria_manager.get_criteria(market_condition)
            
            if p_args.optimize:
                # 기준 최적화
                print(f"🔧 {p_args.market} 기준 최적화 시작...")
                historical_data = self._get_historical_data()
                optimized_criteria = self._v_criteria_manager.optimize_criteria(market_condition, historical_data)
                print(f"✅ 기준 최적화 완료: {optimized_criteria.name}")
                self._print_criteria_details(optimized_criteria)
            
            elif p_args.compare:
                # 기준 성과 비교
                print(f"📊 {p_args.market} 기준 성과 비교...")
                historical_data = self._get_historical_data()
                performance = self._v_criteria_manager.evaluate_criteria_performance(market_condition, historical_data)
                self._print_criteria_performance(performance)
            
            else:
                # 기준 조회
                self._print_criteria_details(criteria)
        
        else:
            # 전체 기준 조회
            all_criteria = self._v_criteria_manager.get_all_criteria()
            self._print_all_criteria(all_criteria)
    
    def _handle_scheduler(self, p_args):
        """스케줄러 관리 처리
        
        Args:
            p_args: 명령어 인자
        """
        if p_args.start:
            # 스케줄러 시작
            print("⏰ 스케줄러 시작...")
            self._v_daily_updater.start_scheduler()
            print("✅ 스케줄러가 시작되었습니다 (매일 08:30 실행)")
        
        elif p_args.stop:
            # 스케줄러 중지
            print("⏹️ 스케줄러 중지...")
            self._v_daily_updater.stop_scheduler()
            print("✅ 스케줄러가 중지되었습니다")
        
        elif p_args.status:
            # 스케줄러 상태 조회
            status = self._get_scheduler_status()
            self._print_scheduler_status(status)
        
        else:
            print("❌ --start, --stop, --status 중 하나를 선택해주세요")
    
    def _handle_performance(self, p_args):
        """성과 분석 처리
        
        Args:
            p_args: 명령어 인자
        """
        print(f"📊 성과 분석 시작 (최근 {p_args.period}일)...")
        
        # 성과 데이터 수집
        performance_data = self._collect_performance_data(p_args.period)
        
        if p_args.sector:
            # 섹터별 성과 분석
            sector_performance = self._analyze_sector_performance(performance_data, p_args.sector)
            self._print_sector_performance(sector_performance)
        else:
            # 전체 성과 분석
            overall_performance = self._analyze_overall_performance(performance_data)
            self._print_overall_performance(overall_performance)
        
        if p_args.export:
            # 결과 내보내기
            self._export_performance_data(performance_data, p_args.export)
            print(f"💾 성과 데이터 내보내기 완료: {p_args.export}")
    
    def _analyze_single_stock(self, p_stock_code: str) -> Optional[PriceAttractiveness]:
        """단일 종목 분석
        
        Args:
            p_stock_code: 종목코드
            
        Returns:
            분석 결과
        """
        try:
            # 감시 리스트에서 종목 정보 조회
            watchlist_stocks = self._v_watchlist_manager.list_stocks()
            target_stock = next((s for s in watchlist_stocks if s.stock_code == p_stock_code), None)
            if not target_stock:
                print(f"❌ 종목 {p_stock_code}이 감시 리스트에 없습니다")
                return None

            # 실데이터 조회 (KIS 현재가 + 최근 일봉)
            from core.api.kis_api import KISAPI
            kis = KISAPI()
            price_info = kis.get_current_price(target_stock.stock_code) or {}
            try:
                df = kis.get_stock_history(target_stock.stock_code, period="D", count=60)
                recent_close = df['close'].tolist() if df is not None else []
                recent_volume = df['volume'].tolist() if df is not None else []
            except Exception:
                recent_close, recent_volume = [], []

            # 분석용 데이터 준비 (실데이터 기반)
            stock_data = {
                "stock_code": target_stock.stock_code,
                "stock_name": target_stock.stock_name,
                "current_price": float(price_info.get("current_price", 0.0)),
                "sector": target_stock.sector,
                "market_cap": float(price_info.get("market_cap", 0.0)),
                # 변동성/섹터모멘텀은 추후 실데이터 지표 연동 전까지 보수적 기본값
                "volatility": 0.25,
                "sector_momentum": 0.05,
                # 참고용: 최근 거래량
                "volume": float(price_info.get("volume", 0.0)),
                "recent_close_prices": recent_close,
                "recent_volumes": recent_volume,
            }
            
            # 분석 실행
            result = self._v_price_analyzer.analyze_price_attractiveness(stock_data)
            return result
            
        except Exception as e:
            logger.error(f"단일 종목 분석 오류: {e}")
            return None
    
    def _analyze_all_stocks(self) -> List[PriceAttractiveness]:
        """전체 감시 리스트 분석 (부분 실패 허용)

        Returns:
            분석 결과 리스트
        """
        try:
            # 감시 리스트 조회
            watchlist_stocks = self._v_watchlist_manager.list_stocks(p_status="active")
            if not watchlist_stocks:
                print("❌ 활성 감시 리스트가 비어있습니다")
                return []

            # 부분 실패 허용 결과 추적
            _v_partial_result = PartialResult[dict](min_success_rate=0.9)

            # KIS 현재가 및 최근 일봉 조회(순차; API 한도 고려). 병목이면 배치 설계
            from core.api.kis_api import KISAPI
            kis = KISAPI()
            stock_data_list = []

            for stock in watchlist_stocks:
                try:
                    price_info = kis.get_current_price(stock.stock_code) or {}
                    # 최근 일봉 (가격/거래량 시계열)
                    try:
                        df = kis.get_stock_history(stock.stock_code, period="D", count=60)  # 최근 60일
                        recent_close = df['close'].tolist() if df is not None else []
                        recent_volume = df['volume'].tolist() if df is not None else []
                    except Exception as hist_err:
                        logger.warning(f"종목 {stock.stock_code} 히스토리 조회 실패: {hist_err}")
                        recent_close, recent_volume = [], []

                    stock_data = {
                        "stock_code": stock.stock_code,
                        "stock_name": stock.stock_name,
                        "current_price": float(price_info.get("current_price", 0.0)),
                        "sector": stock.sector,
                        "market_cap": float(price_info.get("market_cap", 0.0)),
                        "volatility": 0.25,
                        "sector_momentum": 0.05,
                        "volume": float(price_info.get("volume", 0.0)),
                        "recent_close_prices": recent_close,
                        "recent_volumes": recent_volume,
                    }
                    stock_data_list.append(stock_data)
                    _v_partial_result.add_success(stock_data)

                except Exception as e:
                    _v_partial_result.add_failure(stock.stock_code, str(e))

            # 부분 실패 결과 로깅
            _v_partial_result.log_summary("가격 데이터 조회")

            # 실패 항목 저장
            if _v_partial_result.failed:
                save_failed_items(
                    _v_partial_result.failed,
                    "phase2_price_data_fetch",
                    "data/logs/failures"
                )

            # 성공률 체크 및 경고
            if not _v_partial_result.is_acceptable:
                logger.warning(
                    f"⚠️ 가격 데이터 조회 성공률({_v_partial_result.success_rate:.1%})이 "
                    f"최소 기준({_v_partial_result.min_success_rate:.0%}) 미만입니다!"
                )
                print(f"⚠️ 가격 데이터 조회 성공률이 낮습니다: {_v_partial_result.success_rate:.1%}")

            if not stock_data_list:
                print("❌ 분석할 수 있는 종목 데이터가 없습니다")
                return []

            # 병렬 일괄 분석 실행
            logger.info(f"🚀 병렬 가격 분석 시작 - 워커: {self._v_parallel_workers}개, 종목: {len(stock_data_list)}개")
            print(f"🚀 병렬 가격 분석 시작 - 워커: {self._v_parallel_workers}개, 종목: {len(stock_data_list)}개 (데이터 조회 성공률: {_v_partial_result.success_rate:.1%})")

            # 데이터 크기에 따른 적응형 분석 사용
            results = self._v_parallel_price_analyzer.adaptive_analysis(stock_data_list)
            return results

        except Exception as e:
            logger.error(f"전체 종목 분석 오류: {e}")
            return []
    
    def _get_selection_by_date(self, p_date: str) -> Optional[Dict]:
        """특정 날짜 선정 결과 조회
        
        Args:
            p_date: 조회 날짜 (YYYY-MM-DD)
            
        Returns:
            선정 결과 데이터
        """
        try:
            date_str = p_date.replace("-", "")
            file_path = f"data/daily_selection/daily_selection_{date_str}.json"
            
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"날짜별 선정 결과 조회 오류: {e}")
            return None
    
    def _get_historical_data(self) -> List[Dict]:
        """과거 데이터 조회 (더미 구현)
        
        Returns:
            과거 데이터 리스트
        """
        # 실제로는 데이터베이스나 파일에서 과거 데이터 조회
        return [{"date": "2024-01-01", "return": 0.05}] * 100
    
    def _get_scheduler_status(self) -> Dict:
        """스케줄러 상태 조회
        
        Returns:
            스케줄러 상태 정보
        """
        return {
            "running": self._v_daily_updater._v_scheduler_running,
            "next_run": "08:30",
            "last_run": "2024-01-15 08:30:00",
            "status": "정상"
        }
    
    def _collect_performance_data(self, p_period: int) -> Dict:
        """성과 데이터 수집
        
        Args:
            p_period: 분석 기간
            
        Returns:
            성과 데이터
        """
        # 더미 성과 데이터
        return {
            "period": p_period,
            "total_trades": 150,
            "win_rate": 0.65,
            "avg_return": 0.08,
            "max_drawdown": 0.12,
            "sharpe_ratio": 1.35
        }
    
    def _analyze_sector_performance(self, p_data: Dict, p_sector: str) -> Dict:
        """섹터별 성과 분석"""
        return {
            "sector": p_sector,
            "trades": 25,
            "win_rate": 0.68,
            "avg_return": 0.09
        }
    
    def _analyze_overall_performance(self, p_data: Dict) -> Dict:
        """전체 성과 분석"""
        return p_data
    
    def _export_performance_data(self, p_data: Dict, p_file_path: str):
        """성과 데이터 내보내기"""
        with open(p_file_path, 'w', encoding='utf-8') as f:
            json.dump(p_data, f, ensure_ascii=False, indent=2)
    
    # 출력 메서드들
    def _print_update_summary(self, p_result: Dict):
        """업데이트 요약 출력"""
        metadata = p_result.get("metadata", {})
        print(f"""
📊 업데이트 요약
├─ 선정 종목: {metadata.get('total_selected', 0)}개
├─ 감시 리스트: {metadata.get('watchlist_count', 0)}개
├─ 선정률: {metadata.get('selection_rate', 0):.1%}
├─ 평균 매력도: {metadata.get('avg_attractiveness', 0):.1f}점
└─ 시장 상황: {p_result.get('market_condition', 'unknown')}
        """)
    
    def _print_analysis_result(self, p_result: PriceAttractiveness):
        """단일 분석 결과 출력"""
        print(f"""
📈 {p_result.stock_name} ({p_result.stock_code}) 분석 결과
├─ 종합 점수: {p_result.total_score:.1f}점
├─ 기술적 점수: {p_result.technical_score:.1f}점
├─ 거래량 점수: {p_result.volume_score:.1f}점
├─ 패턴 점수: {p_result.pattern_score:.1f}점
├─ 현재가: {p_result.current_price:,.0f}원
├─ 목표가: {p_result.target_price:,.0f}원
├─ 손절가: {p_result.stop_loss:,.0f}원
├─ 기대수익률: {p_result.expected_return:.1f}%
├─ 리스크점수: {p_result.risk_score:.1f}점
├─ 신뢰도: {p_result.confidence:.1%}
└─ 선정이유: {p_result.selection_reason}
        """)
    
    def _print_analysis_results(self, p_results: List[PriceAttractiveness]):
        """분석 결과 리스트 출력"""
        print(f"\n📊 전체 분석 결과 ({len(p_results)}개 종목)")
        print("=" * 80)
        print(f"{'순위':<4} {'종목명':<12} {'코드':<8} {'점수':<6} {'수익률':<8} {'리스크':<6} {'신뢰도':<6}")
        print("-" * 80)
        
        sorted_results = sorted(p_results, key=lambda x: x.total_score, reverse=True)
        
        for i, result in enumerate(sorted_results[:20], 1):  # 상위 20개만 출력
            print(f"{i:<4} {result.stock_name:<12} {result.stock_code:<8} "
                  f"{result.total_score:<6.1f} {result.expected_return:<8.1f}% "
                  f"{result.risk_score:<6.1f} {result.confidence:<6.1%}")
    
    def _print_selection_result(self, p_result: Dict, p_format: str):
        """선정 결과 출력"""
        if p_format == 'json':
            print(json.dumps(p_result, ensure_ascii=False, indent=2))
        else:
            self._print_selection_table(p_result)
    
    def _print_selection_table(self, p_result: Dict):
        """선정 결과 테이블 출력"""
        selected_stocks = p_result.get("data", {}).get("selected_stocks", [])
        
        print(f"\n📅 {p_result.get('market_date')} 일일 선정 결과")
        print(f"🌊 시장 상황: {p_result.get('market_condition')}")
        print(f"📊 선정 종목: {len(selected_stocks)}개")
        print("=" * 100)
        print(f"{'순위':<4} {'종목명':<12} {'코드':<8} {'점수':<6} {'진입가':<8} {'목표가':<8} {'비중':<6} {'섹터':<8}")
        print("-" * 100)
        
        for stock in selected_stocks:
            print(f"{stock.get('priority', 0):<4} {stock.get('stock_name', ''):<12} "
                  f"{stock.get('stock_code', ''):<8} {stock.get('price_attractiveness', 0):<6.1f} "
                  f"{stock.get('entry_price', 0):<8,.0f} {stock.get('target_price', 0):<8,.0f} "
                  f"{stock.get('position_size', 0):<6.1%} {stock.get('sector', ''):<8}")
    
    def _print_selection_history(self, p_history: List[Dict], p_format: str):
        """선정 이력 출력"""
        if p_format == 'json':
            print(json.dumps(p_history, ensure_ascii=False, indent=2))
        else:
            print(f"\n📈 선정 이력 ({len(p_history)}일)")
            print("=" * 80)
            print(f"{'날짜':<12} {'선정수':<6} {'평균점수':<8} {'시장상황':<12}")
            print("-" * 80)
            
            for data in p_history:
                metadata = data.get("metadata", {})
                print(f"{data.get('market_date', ''):<12} "
                      f"{metadata.get('total_selected', 0):<6} "
                      f"{metadata.get('avg_attractiveness', 0):<8.1f} "
                      f"{data.get('market_condition', ''):<12}")
    
    def _print_criteria_summary(self, p_summary: Dict):
        """기준 요약 출력"""
        print(f"""
📋 선정 기준 요약
├─ 총 기준 수: {p_summary.get('total_criteria', 0)}개
├─ 시장 상황: {', '.join(p_summary.get('market_conditions', []))}
├─ 최종 업데이트: {p_summary.get('last_updated', '')}
└─ 기준 세부사항:
        """)
        
        for condition, details in p_summary.get('criteria_details', {}).items():
            print(f"   {condition}:")
            print(f"   ├─ 최대 종목: {details.get('max_stocks', 0)}개")
            print(f"   ├─ 최소 매력도: {details.get('price_attractiveness_min', 0):.1f}점")
            print(f"   ├─ 최대 리스크: {details.get('risk_score_max', 0):.1f}점")
            print(f"   └─ 최소 신뢰도: {details.get('confidence_min', 0):.1%}")
    
    def _print_criteria_details(self, p_criteria: SelectionCriteria):
        """기준 세부사항 출력"""
        print(f"""
📋 {p_criteria.name} 상세 정보
├─ 설명: {p_criteria.description}
├─ 시장 상황: {p_criteria.market_condition.value}
├─ 생성 날짜: {p_criteria.created_date}
├─ 포트폴리오 설정:
│  ├─ 최대 종목: {p_criteria.max_stocks}개
│  ├─ 섹터별 최대: {p_criteria.max_sector_stocks}개
│  └─ 최대 포지션: {p_criteria.max_position_size:.1%}
├─ 기술적 기준:
│  ├─ 가격 매력도: {p_criteria.price_attractiveness.min_value:.1f}~{p_criteria.price_attractiveness.max_value:.1f} (최적: {p_criteria.price_attractiveness.optimal_value:.1f})
│  ├─ 기술적 점수: {p_criteria.technical_score.min_value:.1f}~{p_criteria.technical_score.max_value:.1f} (최적: {p_criteria.technical_score.optimal_value:.1f})
│  └─ 거래량 점수: {p_criteria.volume_score.min_value:.1f}~{p_criteria.volume_score.max_value:.1f} (최적: {p_criteria.volume_score.optimal_value:.1f})
└─ 리스크 기준:
   ├─ 리스크 점수: {p_criteria.risk_score.min_value:.1f}~{p_criteria.risk_score.max_value:.1f} (최적: {p_criteria.risk_score.optimal_value:.1f})
   ├─ 변동성: {p_criteria.volatility.min_value:.1%}~{p_criteria.volatility.max_value:.1%} (최적: {p_criteria.volatility.optimal_value:.1%})
   └─ 신뢰도: {p_criteria.confidence.min_value:.1%}~{p_criteria.confidence.max_value:.1%} (최적: {p_criteria.confidence.optimal_value:.1%})
        """)
    
    def _print_all_criteria(self, p_all_criteria: Dict):
        """전체 기준 출력"""
        print(f"\n📋 전체 선정 기준 ({len(p_all_criteria)}개)")
        print("=" * 80)
        print(f"{'시장상황':<15} {'기준명':<20} {'최대종목':<8} {'최소매력도':<10}")
        print("-" * 80)
        
        for condition, criteria in p_all_criteria.items():
            print(f"{condition.value:<15} {criteria.name:<20} "
                  f"{criteria.max_stocks:<8} {criteria.price_attractiveness.min_value:<10.1f}")
    
    def _print_criteria_performance(self, p_performance):
        """기준 성과 출력"""
        print(f"""
📊 {p_performance.criteria_name} 성과 분석
├─ 테스트 기간: {p_performance.test_period}
├─ 총 거래 수: {p_performance.total_trades}회
├─ 승률: {p_performance.win_rate:.1%}
├─ 평균 수익률: {p_performance.avg_return:.1%}
├─ 최대 손실: {p_performance.max_drawdown:.1%}
├─ 샤프 비율: {p_performance.sharpe_ratio:.2f}
├─ 소르티노 비율: {p_performance.sortino_ratio:.2f}
└─ 수익 팩터: {p_performance.profit_factor:.2f}
        """)
    
    def _print_scheduler_status(self, p_status: Dict):
        """스케줄러 상태 출력"""
        status_icon = "🟢" if p_status.get("running") else "🔴"
        print(f"""
⏰ 스케줄러 상태
├─ 상태: {status_icon} {p_status.get('status', 'unknown')}
├─ 실행 중: {'예' if p_status.get('running') else '아니오'}
├─ 다음 실행: {p_status.get('next_run', 'unknown')}
└─ 마지막 실행: {p_status.get('last_run', 'unknown')}
        """)
    
    def _print_overall_performance(self, p_performance: Dict):
        """전체 성과 출력"""
        print(f"""
📊 전체 성과 분석 (최근 {p_performance.get('period', 0)}일)
├─ 총 거래 수: {p_performance.get('total_trades', 0)}회
├─ 승률: {p_performance.get('win_rate', 0):.1%}
├─ 평균 수익률: {p_performance.get('avg_return', 0):.1%}
├─ 최대 손실: {p_performance.get('max_drawdown', 0):.1%}
└─ 샤프 비율: {p_performance.get('sharpe_ratio', 0):.2f}
        """)
    
    def _print_sector_performance(self, p_performance: Dict):
        """섹터별 성과 출력"""
        print(f"""
📊 {p_performance.get('sector', '')} 섹터 성과
├─ 거래 수: {p_performance.get('trades', 0)}회
├─ 승률: {p_performance.get('win_rate', 0):.1%}
└─ 평균 수익률: {p_performance.get('avg_return', 0):.1%}
        """)

def main():
    """메인 함수"""
    cli = Phase2CLI(p_parallel_workers=4)
    cli.run()

if __name__ == "__main__":
    main() 