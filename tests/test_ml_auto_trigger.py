#!/usr/bin/env python3
"""
ML 자동 트리거 시스템 테스트

테스트 항목:
1. 트리거 초기화 및 상태 로드
2. 데이터 조건 체크 (거래일, 선정 기록, 성과 기록, 승률)
3. ML 학습 진행률 조회
4. 자동 트리거 시뮬레이션
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.learning.auto_ml_trigger import get_auto_ml_trigger  # noqa: E402
from core.utils.log_utils import get_logger  # noqa: E402

logger = get_logger(__name__)


def test_ml_trigger_initialization():
    """트리거 초기화 테스트"""
    print("\n" + "=" * 60)
    print("1. ML 자동 트리거 초기화 테스트")
    print("=" * 60)

    try:
        ml_trigger = get_auto_ml_trigger()

        print("✅ 트리거 초기화 완료")
        print(f"   - 최소 거래일 수: {ml_trigger.min_trading_days}일")
        print(f"   - 최소 선정 기록: {ml_trigger.min_selection_records}개")
        print(f"   - 최소 성과 기록: {ml_trigger.min_performance_records}개")
        print(f"   - 최소 승률: {ml_trigger.min_win_rate:.1%}")

        # 현재 상태 확인
        state = ml_trigger.state
        print("\n📊 현재 트리거 상태:")
        print(f"   - 마지막 체크: {state.get('last_check_date', '없음')}")
        print(f"   - ML 학습 트리거됨: {state.get('ml_training_triggered', False)}")
        print(f"   - ML 학습 날짜: {state.get('ml_training_date', '없음')}")

        return True

    except Exception as e:
        print(f"❌ 초기화 실패: {e}")
        return False


def test_data_conditions_check():
    """데이터 조건 체크 테스트"""
    print("\n" + "=" * 60)
    print("2. 데이터 조건 체크 테스트")
    print("=" * 60)

    try:
        ml_trigger = get_auto_ml_trigger()

        # 현재 데이터 상태 체크
        conditions_met, conditions = ml_trigger._check_data_conditions()

        print("\n📊 데이터 조건 체크 결과:")
        print("\n✓ 거래일 수:")
        print(f"   - 현재: {conditions['trading_days']}일")
        print(f"   - 필요: {ml_trigger.min_trading_days}일")
        print(f"   - 상태: {'✅ 충족' if conditions['trading_days'] >= ml_trigger.min_trading_days else '❌ 미충족'}")

        print("\n✓ 선정 기록:")
        print(f"   - 현재: {conditions['selection_records']}개")
        print(f"   - 필요: {ml_trigger.min_selection_records}개")
        print(f"   - 상태: {'✅ 충족' if conditions['selection_records'] >= ml_trigger.min_selection_records else '❌ 미충족'}")

        print("\n✓ 성과 기록:")
        print(f"   - 현재: {conditions['performance_records']}개")
        print(f"   - 필요: {ml_trigger.min_performance_records}개")
        print(f"   - 상태: {'✅ 충족' if conditions['performance_records'] >= ml_trigger.min_performance_records else '❌ 미충족'}")

        print("\n✓ 승률:")
        print(f"   - 현재: {conditions['current_win_rate']:.1%}")
        print(f"   - 필요: {ml_trigger.min_win_rate:.1%}")
        print(f"   - 상태: {'✅ 충족' if conditions['current_win_rate'] >= ml_trigger.min_win_rate else '❌ 미충족'}")

        print("\n✓ 데이터 품질:")
        print(f"   - 점수: {conditions['data_quality_score']:.1f}/100")

        print(f"\n{'='*60}")
        if conditions_met:
            print("🎉 모든 조건 충족! ML 학습 시작 가능")
        else:
            print("⏳ 조건 미충족 - 데이터 더 필요")
        print(f"{'='*60}")

        return conditions_met

    except Exception as e:
        print(f"❌ 조건 체크 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_progress_to_ml():
    """ML 학습 진행률 테스트"""
    print("\n" + "=" * 60)
    print("3. ML 학습 진행률 조회 테스트")
    print("=" * 60)

    try:
        ml_trigger = get_auto_ml_trigger()

        # 진행률 조회
        progress = ml_trigger.get_progress_to_ml()

        print("\n📊 ML 학습 준비 진행률:")
        print(f"\n{'='*60}")
        print(f"전체 진행률: {progress['overall_progress']:.1f}%")
        print(f"{'='*60}")

        print("\n세부 진행률:")
        print(f"   - 거래일: {progress['trading_days_progress']:.1f}%")
        print(f"   - 선정 기록: {progress['selection_records_progress']:.1f}%")
        print(f"   - 성과 기록: {progress['performance_records_progress']:.1f}%")
        print(f"   - 승률: {progress['win_rate_progress']:.1f}%")

        if not progress['conditions_met']:
            days_remaining = progress['estimated_days_remaining']
            print(f"\n⏰ 예상 남은 기간: 약 {days_remaining}일")
        else:
            print("\n🎉 ML 학습 준비 완료!")

        return True

    except Exception as e:
        print(f"❌ 진행률 조회 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_trigger_simulation():
    """자동 트리거 시뮬레이션 (실제 트리거 X)"""
    print("\n" + "=" * 60)
    print("4. 자동 트리거 로직 시뮬레이션")
    print("=" * 60)

    try:
        ml_trigger = get_auto_ml_trigger()

        # 조건 체크만 수행 (실제 트리거는 하지 않음)
        conditions_met, conditions = ml_trigger._check_data_conditions()

        print("\n🔍 트리거 시뮬레이션 결과:")

        if conditions_met:
            print("\n✅ 조건 충족 - ML 학습이 자동으로 시작될 것입니다")
            print("\n📋 충족된 조건:")
            print(f"   • 거래일 수: {conditions['trading_days']}일")
            print(f"   • 선정 기록: {conditions['selection_records']}개")
            print(f"   • 성과 기록: {conditions['performance_records']}개")
            print(f"   • 현재 승률: {conditions['current_win_rate']:.1%}")
            print(f"   • 데이터 품질: {conditions['data_quality_score']:.1f}점")

            print("\n🚀 다음 단계:")
            print("   1. WorkflowStateManager에 B단계 상태 저장")
            print("   2. ML 학습 스크립트 실행 예약")
            print("   3. 텔레그램 알림 전송")

        else:
            print("\n⏳ 조건 미충족 - ML 학습 대기 중")
            print("\n📋 현재 상태:")
            print(f"   • 거래일 수: {conditions['trading_days']}/{ml_trigger.min_trading_days}일")
            print(f"   • 선정 기록: {conditions['selection_records']}/{ml_trigger.min_selection_records}개")
            print(f"   • 성과 기록: {conditions['performance_records']}/{ml_trigger.min_performance_records}개")
            print(f"   • 현재 승률: {conditions['current_win_rate']:.1%}/{ml_trigger.min_win_rate:.1%}")

            print("\n⏰ 계속 모니터링 중...")

        return True

    except Exception as e:
        print(f"❌ 시뮬레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """메인 테스트 실행"""
    print("\n" + "=" * 60)
    print("ML 자동 트리거 시스템 테스트")
    print("=" * 60)

    results = []

    # 1. 초기화 테스트
    results.append(("초기화", test_ml_trigger_initialization()))

    # 2. 데이터 조건 체크
    results.append(("데이터 조건 체크", test_data_conditions_check()))

    # 3. 진행률 조회
    results.append(("진행률 조회", test_progress_to_ml()))

    # 4. 자동 트리거 시뮬레이션
    results.append(("자동 트리거 시뮬레이션", test_auto_trigger_simulation()))

    # 최종 결과 출력
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    for test_name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"{status} - {test_name}")

    all_passed = all(result for _, result in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 모든 테스트 통과!")
    else:
        print("⚠️ 일부 테스트 실패")
    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
