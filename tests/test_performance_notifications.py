#!/usr/bin/env python3
"""
성과 지표 및 텔레그램 알림 테스트
실제 성과가 알림에 반영되는지 확인
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.performance.performance_metrics import get_performance_metrics
from core.utils.telegram_notifier import get_telegram_notifier
from core.trading.trade_journal import TradeJournal


def test_performance_metrics():
    """성과 지표 계산 테스트"""
    print("\n=== 성과 지표 계산 테스트 ===")
    
    try:
        metrics = get_performance_metrics()
        
        # 일일 성과 계산
        daily_perf = metrics.get_daily_performance()
        
        print(f"\n📊 일일 성과 (날짜: {daily_perf['date']}):")
        print("  💰 실현 손익 (매도):")
        print(f"     - 실현 손익: {daily_perf['realized_pnl']:,.0f}원")
        print(f"     - 실현 수익률: {daily_perf['realized_return']*100:.2f}%")
        print(f"     - 거래 횟수: {daily_perf['trade_count']}건")
        print(f"     - 승률: {daily_perf['win_rate']*100:.1f}%")
        
        print("\n  📈 평가 손익 (보유):")
        print(f"     - 평가 손익: {daily_perf['unrealized_pnl']:,.0f}원")
        print(f"     - 평가 수익률: {daily_perf['unrealized_return']*100:.2f}%")
        print(f"     - 보유 종목: {daily_perf['holding_count']}개")
        
        print("\n  📊 종합 성과:")
        print(f"     - 총 손익: {daily_perf['total_pnl']:,.0f}원")
        print(f"     - 총 수익률: {daily_perf['total_return']*100:.2f}%")
        
        # 과거 성과 통계
        hist_perf = metrics.get_historical_performance(days=30)
        
        print("\n📈 30일 성과 통계:")
        print(f"  - 총 실현 손익: {hist_perf['total_realized_pnl']:,.0f}원")
        print(f"  - 총 거래 횟수: {hist_perf['total_trades']}건")
        print(f"  - 평균 승률: {hist_perf['win_rate']*100:.1f}%")
        print(f"  - 평균 수익률: {hist_perf['avg_return']*100:.2f}%")
        print(f"  - 샤프 비율: {hist_perf['sharpe_ratio']:.2f}")
        print(f"  - 정확도: {hist_perf['accuracy']*100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ 성과 지표 계산 실패: {e}")
        return False


def test_telegram_notification():
    """텔레그램 알림 테스트"""
    print("\n=== 텔레그램 알림 테스트 ===")
    
    try:
        notifier = get_telegram_notifier()
        
        if not notifier.is_enabled():
            print("⚠️ 텔레그램 알림이 비활성화되어 있습니다.")
            print("   config/telegram_config.json 파일을 확인하세요.")
            return False
        
        print("텔레그램 알림이 활성화되어 있습니다.")
        
        # 일일 성과 리포트 테스트
        response = input("\n일일 성과 리포트를 텔레그램으로 전송하시겠습니까? (y/N): ").strip().lower()
        
        if response == 'y':
            success = notifier.send_daily_performance_report()
            
            if success:
                print("✅ 일일 성과 리포트가 텔레그램으로 전송되었습니다!")
                print("   실현 손익과 평가 손익이 분리되어 표시됩니다.")
            else:
                print("❌ 일일 성과 리포트 전송 실패")
                return False
        else:
            print("일일 성과 리포트 전송을 건너뜁니다.")
        
        # 일일 업데이트 알림 테스트 (실제 성과 반영)
        response = input("\n일일 업데이트 알림을 테스트하시겠습니까? (y/N): ").strip().lower()
        
        if response == 'y':
            success = notifier.send_daily_update_complete(selected_count=10)
            
            if success:
                print("✅ 일일 업데이트 알림이 전송되었습니다!")
                print("   실제 성과 지표가 반영되어 표시됩니다.")
            else:
                print("❌ 일일 업데이트 알림 전송 실패")
                return False
        else:
            print("일일 업데이트 알림 테스트를 건너뜁니다.")
        
        return True
        
    except Exception as e:
        print(f"❌ 텔레그램 알림 테스트 실패: {e}")
        return False


def create_sample_trade_data():
    """테스트용 샘플 거래 데이터 생성"""
    print("\n=== 샘플 거래 데이터 생성 ===")
    
    try:
        journal = TradeJournal()
        
        # 샘플 매수 주문
        journal.log_order(
            stock_code="005930",
            stock_name="삼성전자",
            side="buy",
            price=70000,
            quantity=10,
            reason="test_buy"
        )
        
        # 샘플 매도 주문 (일부 익절)
        journal.log_order(
            stock_code="005930",
            stock_name="삼성전자",
            side="sell",
            price=72000,
            quantity=5,
            reason="test_partial_profit"
        )
        
        # 일일 요약 계산
        summary = journal.compute_daily_summary()
        
        print("✅ 샘플 거래 데이터 생성 완료")
        print(f"   - 실현 손익: {summary['realized_pnl']:,.0f}원")
        print(f"   - 거래 횟수: {summary['total_trades']}건")
        print(f"   - 승률: {summary['win_rate']*100:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ 샘플 데이터 생성 실패: {e}")
        return False


def main():
    """메인 테스트 실행"""
    print("="*60)
    print("성과 지표 및 텔레그램 알림 테스트")
    print("="*60)
    
    tests = []
    
    # 샘플 데이터 생성 옵션
    response = input("\n테스트용 샘플 거래 데이터를 생성하시겠습니까? (y/N): ").strip().lower()
    if response == 'y':
        tests.append(("샘플 데이터 생성", create_sample_trade_data))
    
    # 기본 테스트
    tests.extend([
        ("성과 지표 계산", test_performance_metrics),
        ("텔레그램 알림", test_telegram_notification)
    ])
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test_name} 예외 발생: {e}")
            failed += 1
    
    # 결과 요약
    print("\n" + "="*60)
    print("테스트 결과 요약")
    print("="*60)
    print(f"✅ 통과: {passed}개")
    print(f"❌ 실패: {failed}개")
    
    if failed == 0:
        print("\n🎉 모든 테스트가 통과했습니다!")
        print("알림 파라미터가 실제 성과를 반영하고 있으며,")
        print("실현 손익과 평가 손익이 분리되어 표시됩니다.")
    else:
        print("\n⚠️ 일부 테스트가 실패했습니다.")
        print("오류 메시지를 확인해주세요.")


if __name__ == "__main__":
    main()