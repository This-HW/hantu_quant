#!/usr/bin/env python3
"""
전체 시스템 통합 테스트
1. 자동 매매 시스템 (Trading Engine)
2. 새로운 기술적 지표들 (VWAP, ADX, MFI, Ichimoku, Patterns, A/D)
3. 향상된 스크리닝 시스템
4. 학습 시스템
5. 스케줄러
"""

import sys
import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class IntegrationTestRunner:
    """통합 테스트 실행기"""

    def __init__(self):
        self.results = {}
        self.errors = []
        self.start_time = datetime.now()

    def log_test(self, component: str, test: str, success: bool, details: str = ""):
        """테스트 결과 기록"""
        if component not in self.results:
            self.results[component] = []

        self.results[component].append({
            'test': test,
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })

        status = "✅" if success else "❌"
        print(f"{status} {component}: {test}")
        if details and not success:
            print(f"   └─ {details}")

    def test_trading_engine(self) -> bool:
        """자동 매매 엔진 테스트"""
        print("\n" + "="*60)
        print("🤖 자동 매매 엔진 테스트")
        print("="*60)

        try:
            from core.trading.trading_engine import TradingEngine, TradingConfig

            # 1. 초기화 테스트
            config = TradingConfig(
                max_positions=5,
                position_size_method="account_pct",
                position_size_value=0.05
            )
            engine = TradingEngine(config)
            self.log_test("TradingEngine", "초기화", True)

            # 2. API 초기화 테스트
            api_success = engine._initialize_api()
            self.log_test("TradingEngine", "API 초기화", api_success)

            # 3. 일일 선정 종목 로드 테스트
            selected = engine._load_daily_selection()
            has_selection = selected is not None and len(selected) > 0
            self.log_test("TradingEngine", "일일 선정 종목 로드", has_selection,
                         f"{len(selected) if selected else 0}개 종목")

            # 4. 거래 시간 체크
            is_market_time = engine._is_market_time()
            self.log_test("TradingEngine", "거래 시간 체크", True,
                         f"현재 거래시간: {'예' if is_market_time else '아니오'}")

            return all([api_success, has_selection])

        except Exception as e:
            self.log_test("TradingEngine", "전체", False, str(e))
            self.errors.append(f"TradingEngine: {e}")
            return False

    def test_new_indicators(self) -> bool:
        """새로운 지표들 테스트"""
        print("\n" + "="*60)
        print("📊 새로운 기술적 지표 테스트")
        print("="*60)

        import pandas as pd
        import numpy as np

        # 테스트 데이터 생성
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        test_df = pd.DataFrame({
            'date': dates,
            'open': np.random.uniform(50000, 52000, 60),
            'high': np.random.uniform(52000, 53000, 60),
            'low': np.random.uniform(49000, 50000, 60),
            'close': np.random.uniform(50000, 52000, 60),
            'volume': np.random.uniform(1000000, 2000000, 60)
        })
        test_df.set_index('date', inplace=True)
        test_df['close'] = test_df['close'].ewm(span=5).mean()

        all_success = True

        # 1. VWAP 테스트
        try:
            from hantu_common.indicators.vwap import VWAP
            vwap = VWAP.calculate(test_df['close'], test_df['volume'],
                                 test_df['high'], test_df['low'])
            signals = VWAP.get_trade_signals(test_df)
            self.log_test("Indicators", "VWAP", True,
                         f"값: {vwap.iloc[-1]:,.0f}")
        except Exception as e:
            self.log_test("Indicators", "VWAP", False, str(e))
            all_success = False

        # 2. ADX 테스트
        try:
            from hantu_common.indicators.adx import ADX
            adx_data = ADX.calculate(test_df['high'], test_df['low'], test_df['close'])
            trend = ADX.analyze_trend_strength(adx_data['adx'].iloc[-1])
            self.log_test("Indicators", "ADX", True,
                         f"값: {adx_data['adx'].iloc[-1]:.2f}, 추세: {trend}")
        except Exception as e:
            self.log_test("Indicators", "ADX", False, str(e))
            all_success = False

        # 3. MFI 테스트
        try:
            from hantu_common.indicators.mfi import MFI
            mfi = MFI.calculate(test_df['high'], test_df['low'],
                               test_df['close'], test_df['volume'])
            level = MFI.analyze_level(mfi.iloc[-1])
            self.log_test("Indicators", "MFI", True,
                         f"값: {mfi.iloc[-1]:.2f}, 레벨: {level}")
        except Exception as e:
            self.log_test("Indicators", "MFI", False, str(e))
            all_success = False

        # 4. Ichimoku 테스트
        try:
            from hantu_common.indicators.ichimoku import Ichimoku
            ichimoku = Ichimoku.calculate(test_df['high'], test_df['low'], test_df['close'])
            signals = Ichimoku.get_trade_signals(test_df)
            self.log_test("Indicators", "Ichimoku", True,
                         f"신호 강도: {signals['signal_strength'].iloc[-1]}")
        except Exception as e:
            self.log_test("Indicators", "Ichimoku", False, str(e))
            all_success = False

        # 5. Pattern Recognition 테스트
        try:
            from hantu_common.indicators.pattern_recognition import PatternRecognition
            patterns = PatternRecognition.get_pattern_signals(test_df)
            self.log_test("Indicators", "Pattern Recognition", True,
                         f"패턴 점수: {patterns['pattern_score'].iloc[-1]}")
        except Exception as e:
            self.log_test("Indicators", "Pattern Recognition", False, str(e))
            all_success = False

        # 6. A/D Line 테스트
        try:
            from hantu_common.indicators.accumulation_distribution import AccumulationDistribution
            ad_signals = AccumulationDistribution.get_trade_signals(test_df)
            phase = ad_signals['accumulation_phase'].iloc[-1]
            self.log_test("Indicators", "A/D Line", True,
                         f"단계: {phase}")
        except Exception as e:
            self.log_test("Indicators", "A/D Line", False, str(e))
            all_success = False

        return all_success

    def test_enhanced_screener(self) -> bool:
        """향상된 스크리너 테스트"""
        print("\n" + "="*60)
        print("🔍 향상된 스크리닝 시스템 테스트")
        print("="*60)

        try:
            from core.watchlist.enhanced_screener import EnhancedScreener

            screener = EnhancedScreener()
            self.log_test("EnhancedScreener", "초기화", True)

            # 테스트 종목으로 지표 계산
            test_stock = '005930'  # 삼성전자
            indicators = screener.calculate_enhanced_indicators(test_stock, period=30)

            if indicators:
                score = screener.calculate_enhanced_score(indicators)
                self.log_test("EnhancedScreener", "지표 계산", True,
                             f"향상 점수: {score:.1f}/100")

                # 각 지표 확인
                has_vwap = indicators.get('vwap') is not None
                has_adx = indicators.get('adx') is not None
                has_mfi = indicators.get('mfi') is not None

                self.log_test("EnhancedScreener", "VWAP 통합", has_vwap)
                self.log_test("EnhancedScreener", "ADX 통합", has_adx)
                self.log_test("EnhancedScreener", "MFI 통합", has_mfi)

                return True
            else:
                self.log_test("EnhancedScreener", "지표 계산", False, "데이터 없음")
                return False

        except Exception as e:
            self.log_test("EnhancedScreener", "전체", False, str(e))
            self.errors.append(f"EnhancedScreener: {e}")
            return False

    def test_scheduler(self) -> bool:
        """스케줄러 테스트"""
        print("\n" + "="*60)
        print("📅 스케줄러 시스템 테스트")
        print("="*60)

        try:
            from workflows.integrated_scheduler import IntegratedScheduler

            # 스케줄러 초기화
            scheduler = IntegratedScheduler(p_parallel_workers=1)
            self.log_test("Scheduler", "초기화", True)

            # 스케줄 확인 - 스케줄러 속성이 있는지 확인
            if hasattr(scheduler, 'scheduler'):
                jobs = scheduler.scheduler.get_jobs()
                self.log_test("Scheduler", "작업 등록", len(jobs) > 0,
                             f"{len(jobs)}개 작업")
            else:
                # 대신 phase1과 phase2가 있는지 확인
                has_workflows = hasattr(scheduler, 'phase1') and hasattr(scheduler, 'phase2')
                self.log_test("Scheduler", "워크플로우 초기화", has_workflows)

            # 자동 매매 함수 테스트
            try:
                scheduler._start_auto_trading()
                self.log_test("Scheduler", "자동 매매 함수", True)
            except Exception as e:
                self.log_test("Scheduler", "자동 매매 함수", False, str(e))

            return True

        except Exception as e:
            self.log_test("Scheduler", "전체", False, str(e))
            self.errors.append(f"Scheduler: {e}")
            return False

    def test_daily_selection(self) -> bool:
        """일일 선정 시스템 테스트"""
        print("\n" + "="*60)
        print("📋 일일 선정 시스템 테스트")
        print("="*60)

        try:
            # 최신 선정 파일 확인
            selection_file = "data/daily_selection/latest_selection.json"

            if os.path.exists(selection_file):
                with open(selection_file, 'r') as f:
                    data = json.load(f)

                has_stocks = len(data.get('selected_stocks', [])) > 0
                self.log_test("DailySelection", "선정 파일 존재", True,
                             f"{len(data.get('selected_stocks', []))}개 종목")

                # 선정 종목 구조 확인
                if has_stocks:
                    stock = data['selected_stocks'][0]
                    required_fields = ['stock_code', 'stock_name', 'entry_price',
                                     'confidence', 'price_attractiveness']
                    has_all_fields = all(field in stock for field in required_fields)
                    self.log_test("DailySelection", "데이터 구조", has_all_fields)

                return has_stocks
            else:
                self.log_test("DailySelection", "선정 파일", False, "파일 없음")
                return False

        except Exception as e:
            self.log_test("DailySelection", "전체", False, str(e))
            self.errors.append(f"DailySelection: {e}")
            return False

    def test_config_files(self) -> bool:
        """설정 파일 테스트"""
        print("\n" + "="*60)
        print("⚙️ 설정 파일 테스트")
        print("="*60)

        config_files = [
            ".env",
            "config/telegram_config.json",
            "data/watchlist/watchlist.json",
            "data/daily_selection/latest_selection.json"
        ]

        all_exist = True
        for config_file in config_files:
            exists = os.path.exists(config_file)
            self.log_test("Config", os.path.basename(config_file), exists)
            if not exists:
                all_exist = False

        return all_exist

    def run_all_tests(self) -> bool:
        """모든 테스트 실행"""
        print("🚀 전체 시스템 통합 테스트 시작")
        print(f"⏰ 시작 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        test_results = []

        # 1. 설정 파일 테스트
        test_results.append(("설정 파일", self.test_config_files()))

        # 2. 새로운 지표 테스트
        test_results.append(("기술적 지표", self.test_new_indicators()))

        # 3. 향상된 스크리너 테스트
        test_results.append(("향상된 스크리너", self.test_enhanced_screener()))

        # 4. 일일 선정 시스템 테스트
        test_results.append(("일일 선정", self.test_daily_selection()))

        # 5. 자동 매매 엔진 테스트
        test_results.append(("자동 매매", self.test_trading_engine()))

        # 6. 스케줄러 테스트
        test_results.append(("스케줄러", self.test_scheduler()))

        # 결과 요약
        self.print_summary(test_results)

        # 모든 테스트 통과 여부
        all_passed = all(result for _, result in test_results)
        return all_passed

    def print_summary(self, test_results: List[tuple]):
        """테스트 결과 요약 출력"""
        print("\n" + "="*80)
        print("📊 통합 테스트 결과 요약")
        print("="*80)

        total_components = 0
        passed_components = 0

        for component, results in self.results.items():
            component_passed = all(r['success'] for r in results)
            total_tests = len(results)
            passed_tests = sum(1 for r in results if r['success'])

            status = "✅" if component_passed else "❌"
            print(f"{status} {component}: {passed_tests}/{total_tests} 테스트 통과")

            total_components += 1
            if component_passed:
                passed_components += 1

        print(f"\n📈 전체 컴포넌트: {passed_components}/{total_components} 통과")

        if self.errors:
            print("\n⚠️ 오류 목록:")
            for error in self.errors:
                print(f"  - {error}")

        elapsed = datetime.now() - self.start_time
        print(f"\n⏱️ 소요 시간: {elapsed.total_seconds():.2f}초")

        # 전체 통과 여부
        all_passed = all(result for _, result in test_results)
        if all_passed:
            print("\n🎉 모든 통합 테스트를 통과했습니다!")
            print("시스템이 정상적으로 작동합니다.")
        else:
            print("\n⚠️ 일부 테스트가 실패했습니다.")
            print("위의 오류를 확인하고 수정이 필요합니다.")


async def test_trading_async():
    """비동기 매매 테스트"""
    from core.trading.trading_engine import TradingEngine, TradingConfig

    config = TradingConfig(
        max_positions=3,
        position_size_method="fixed",
        fixed_position_size=100000
    )

    engine = TradingEngine(config)

    # 테스트 실행 (5초)
    result = await engine.start_trading()
    if result:
        await asyncio.sleep(5)
        await engine.stop_trading("테스트 완료")

    return result


def main():
    """메인 함수"""
    runner = IntegrationTestRunner()
    all_passed = runner.run_all_tests()

    # 비동기 테스트 (선택적)
    if all_passed:
        print("\n📌 비동기 매매 테스트 (선택적)")
        try:
            async_result = asyncio.run(test_trading_async())
            print(f"  {'✅' if async_result else '❌'} 비동기 매매 테스트")
        except Exception as e:
            print(f"  ❌ 비동기 매매 테스트: {e}")

    print(f"\n⏰ 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 테스트 결과 반환
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())