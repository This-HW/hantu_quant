#!/usr/bin/env python3
"""
자동 매매 헬스체크 테스트
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.monitoring.trading_health_checker import get_health_checker
from core.utils.log_utils import setup_logging, get_logger

# 로깅 설정
log_filename = f"logs/health_check_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
setup_logging(log_filename, add_sensitive_filter=True)
logger = get_logger(__name__)

def main():
    """메인 함수"""
    print("="*60)
    print("🏥 자동 매매 헬스체크 테스트")
    print("="*60)
    print(f"📝 로그 파일: {log_filename}\n")

    try:
        # 1. 헬스체커 초기화
        print("[1] 헬스체커 초기화...")
        health_checker = get_health_checker()
        print("✅ 헬스체커 초기화 완료\n")

        # 2. 헬스체크 실행
        print("[2] 헬스체크 실행 중...")
        print("-" * 60)

        result = health_checker.check_trading_health()

        print("\n" + "="*60)
        print("📊 헬스체크 결과")
        print("="*60)

        # 전체 상태
        status_emoji = "✅" if result.is_healthy else "❌"
        status_text = "정상" if result.is_healthy else "이상 감지"
        print(f"\n🏥 전체 상태: {status_emoji} {status_text}")

        # 발견된 문제
        if result.issues:
            print(f"\n❌ 발견된 문제 ({len(result.issues)}건):")
            for i, issue in enumerate(result.issues, 1):
                print(f"   {i}. {issue}")
        else:
            print(f"\n✅ 발견된 문제: 없음")

        # 경고사항
        if result.warnings:
            print(f"\n⚠️  경고사항 ({len(result.warnings)}건):")
            for i, warning in enumerate(result.warnings, 1):
                print(f"   {i}. {warning}")
        else:
            print(f"\n✅ 경고사항: 없음")

        # 메트릭 출력
        if result.metrics:
            print(f"\n📊 시스템 메트릭:")
            print("-" * 60)

            metrics = result.metrics

            # 매매 엔진 상태
            if 'engine_running' in metrics:
                engine_status = "🟢 실행 중" if metrics['engine_running'] else "🔴 중지됨"
                print(f"   매매 엔진: {engine_status}")

            # 거래 활동
            if 'recent_trades' in metrics:
                print(f"   오늘 거래: {metrics['recent_trades']}건")

            if 'last_trade_time' in metrics and metrics['last_trade_time']:
                print(f"   마지막 거래: {metrics['last_trade_time']}")

            # API 연결
            if 'api_connected' in metrics:
                api_status = "🟢 정상" if metrics['api_connected'] else "🔴 실패"
                print(f"   API 연결: {api_status}")

            # 일일 선정
            if 'selection_file_exists' in metrics:
                selection_status = "✅ 존재" if metrics['selection_file_exists'] else "❌ 없음"
                print(f"   일일 선정 파일: {selection_status}")

            if 'selection_count' in metrics:
                print(f"   선정 종목 수: {metrics['selection_count']}개")

            # 계좌 정보
            if 'available_cash' in metrics:
                cash = metrics['available_cash']
                print(f"   가용 현금: {cash:,.0f}원")

            if 'total_assets' in metrics:
                total = metrics['total_assets']
                print(f"   총 자산: {total:,.0f}원")

            # 시스템 리소스
            if 'cpu_usage' in metrics:
                cpu = metrics['cpu_usage']
                cpu_status = "⚠️" if cpu > 80 else "✅"
                print(f"   CPU 사용률: {cpu_status} {cpu:.1f}%")

            if 'memory_usage' in metrics:
                mem = metrics['memory_usage']
                mem_status = "⚠️" if mem > 80 else "✅"
                print(f"   메모리 사용률: {mem_status} {mem:.1f}%")

            # 오류 로그
            if 'recent_errors' in metrics:
                errors = metrics['recent_errors']
                error_status = "⚠️" if errors > 0 else "✅"
                print(f"   최근 오류: {error_status} {errors}건 (1시간 내)")

        print("\n" + "="*60)

        # 알림 전송 여부
        if not result.is_healthy:
            print("\n⚠️  이상이 감지되어 텔레그램 알림이 전송되었을 수 있습니다.")
            print("   (30분 이내 중복 알림은 자동으로 방지됩니다)")

        print("\n✅ 헬스체크 테스트 완료!")
        print("="*60)

        return result.is_healthy

    except Exception as e:
        logger.error(f"헬스체크 테스트 실패: {e}")
        print(f"\n❌ 헬스체크 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
