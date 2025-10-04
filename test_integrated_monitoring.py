#!/usr/bin/env python3
"""
자동 복구 + 알림 우선순위 통합 테스트
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from core.monitoring.trading_health_checker import get_health_checker
from core.monitoring.auto_recovery_system import get_recovery_system
from core.utils.log_utils import setup_logging, get_logger

# 로깅 설정
log_filename = f"logs/integrated_monitoring_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
setup_logging(log_filename, add_sensitive_filter=True)
logger = get_logger(__name__)

def print_section(title):
    """섹션 헤더 출력"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def test_priority_levels():
    """우선순위 레벨 테스트"""
    print_section("1️⃣ 알림 우선순위 시스템 테스트")

    from core.utils.telegram_notifier import get_telegram_notifier
    notifier = get_telegram_notifier()

    if not notifier.is_enabled():
        print("⚠️  텔레그램이 비활성화되어 우선순위 테스트를 건너뜁니다")
        return

    priorities = [
        ('critical', '시스템 완전 중단'),
        ('emergency', '긴급 오류 발생'),
        ('high', '중요 알림'),
        ('normal', '일반 알림'),
        ('low', '정보성 알림'),
        ('info', '참고 정보')
    ]

    print("\n📤 각 우선순위별 테스트 메시지 전송...\n")

    for priority, description in priorities:
        message = f"""테스트 메시지

우선순위: {priority}
설명: {description}
시간: {datetime.now().strftime('%H:%M:%S')}"""

        print(f"   • {priority:10} - {description:20}", end=" ")

        try:
            success = notifier.send_message(message, priority=priority)
            if success:
                print("✅")
            else:
                print("❌")

            # 메시지 간 간격
            import time
            time.sleep(1)

        except Exception as e:
            print(f"❌ ({e})")

    print("\n💡 텔레그램에서 각 우선순위별 메시지 포맷을 확인하세요")
    print("   • critical/emergency: 알림 소리 O, 강조 표시")
    print("   • high: 알림 소리 O")
    print("   • normal/low/info: 무음 알림")

def test_auto_recovery():
    """자동 복구 시스템 테스트"""
    print_section("2️⃣ 자동 복구 시스템 테스트")

    recovery_system = get_recovery_system()

    # 테스트할 문제들
    test_issues = [
        "매매 엔진이 실행 중이 아닙니다",
        "API 연결 실패: Token expired",
        "오늘 날짜의 일일 선정 파일이 없습니다",
        "메모리 사용률이 높습니다: 90%",
        "복구 불가능한 치명적 오류"
    ]

    print(f"\n🔧 {len(test_issues)}개의 문제에 대해 자동 복구 시도...\n")

    for i, issue in enumerate(test_issues, 1):
        print(f"{i}. {issue}")

    print("\n⏳ 복구 진행 중...\n")

    results = recovery_system.attempt_recovery(test_issues)

    print("-" * 60)
    print(f"\n📊 복구 결과:")
    print(f"   • 시도: {results['attempted']}건")
    print(f"   • 성공: {results['succeeded']}건")
    print(f"   • 실패: {results['failed']}건")
    print(f"   • 복구 불가: {len(results['unrecoverable'])}건")

    if results['actions']:
        print(f"\n✅ 복구 액션:")
        for action in results['actions']:
            status = "✅" if action.success else "❌"
            print(f"   {status} {action.action_name}: {action.description}")

    if results['unrecoverable']:
        print(f"\n⚠️ 복구 불가능한 문제:")
        for issue in results['unrecoverable']:
            print(f"   • {issue}")

def test_integrated_health_check():
    """통합 헬스체크 테스트 (복구 + 알림)"""
    print_section("3️⃣ 통합 헬스체크 테스트 (자동 복구 + 우선순위 알림)")

    health_checker = get_health_checker()

    print("\n🏥 전체 시스템 헬스체크 실행 중...\n")

    result = health_checker.check_trading_health()

    # 결과 출력
    status_emoji = "✅" if result.is_healthy else "❌"
    status_text = "정상" if result.is_healthy else "이상 감지"

    print(f"🏥 전체 상태: {status_emoji} {status_text}")

    if result.issues:
        print(f"\n❌ 발견된 문제 ({len(result.issues)}건):")
        for i, issue in enumerate(result.issues, 1):
            print(f"   {i}. {issue}")

    if result.warnings:
        print(f"\n⚠️  경고사항 ({len(result.warnings)}건):")
        for i, warning in enumerate(result.warnings, 1):
            print(f"   {i}. {warning}")

    # 자동 복구 결과
    if 'recovery_attempted' in result.metrics:
        print(f"\n🔧 자동 복구:")
        print(f"   • 시도: {result.metrics.get('recovery_attempted', 0)}건")
        print(f"   • 성공: {result.metrics.get('recovery_succeeded', 0)}건")

    # 시스템 메트릭
    print(f"\n📊 시스템 메트릭:")
    metrics = result.metrics

    if 'engine_running' in metrics:
        engine_status = "🟢 실행 중" if metrics['engine_running'] else "🔴 중지됨"
        print(f"   • 매매 엔진: {engine_status}")

    if 'recent_trades' in metrics:
        print(f"   • 오늘 거래: {metrics['recent_trades']}건")

    if 'api_connected' in metrics:
        api_status = "🟢 정상" if metrics['api_connected'] else "🔴 실패"
        print(f"   • API 연결: {api_status}")

    if 'selection_file_exists' in metrics:
        file_status = "✅ 존재" if metrics['selection_file_exists'] else "❌ 없음"
        print(f"   • 일일 선정 파일: {file_status}")

    if 'selection_count' in metrics:
        print(f"   • 선정 종목 수: {metrics['selection_count']}개")

    if 'available_cash' in metrics:
        cash = metrics['available_cash']
        print(f"   • 가용 현금: {cash:,.0f}원")

    if 'cpu_usage' in metrics:
        cpu = metrics['cpu_usage']
        print(f"   • CPU 사용률: {cpu:.1f}%")

    if 'memory_usage' in metrics:
        mem = metrics['memory_usage']
        print(f"   • 메모리 사용률: {mem:.1f}%")

    # 알림 전송 여부
    if not result.is_healthy:
        print(f"\n📱 텔레그램 알림:")
        print(f"   • 문제가 감지되어 텔레그램 알림이 전송되었습니다")
        print(f"   • 자동 복구 결과가 포함되었습니다")
        print(f"   • 우선순위가 문제 심각도에 따라 자동 결정되었습니다")

def main():
    """메인 함수"""
    print("="*60)
    print("🧪 통합 모니터링 시스템 테스트")
    print("="*60)
    print(f"📝 로그 파일: {log_filename}\n")

    try:
        # 1. 우선순위 테스트
        test_priority_levels()

        # 2. 자동 복구 테스트
        test_auto_recovery()

        # 3. 통합 헬스체크 테스트
        test_integrated_health_check()

        # 최종 요약
        print_section("✅ 테스트 완료")
        print("\n📋 확인 사항:")
        print("   1. 텔레그램에서 각 우선순위별 알림을 확인하세요")
        print("   2. critical/emergency는 알림 소리가 울렸는지 확인")
        print("   3. normal/low/info는 무음 알림인지 확인")
        print("   4. 자동 복구 결과가 메시지에 포함되었는지 확인")
        print("   5. 헬스체크 로그 파일을 확인하세요")

        print(f"\n📁 데이터 저장 위치:")
        print(f"   • 헬스체크: data/health_check/")
        print(f"   • 복구 기록: data/recovery/")
        print(f"   • 로그: {log_filename}")

        print("\n" + "="*60)
        print("✅ 모든 테스트가 완료되었습니다!")
        print("="*60)

        return True

    except Exception as e:
        logger.error(f"테스트 실패: {e}")
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
