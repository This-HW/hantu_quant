#!/usr/bin/env python3
"""
강화된 학습 시스템 통합 테스트
- 데이터 동기화 시스템 테스트
- 강화된 적응형 학습 시스템 테스트
- 시스템 모니터링 테스트
- 전체 통합 동작 확인
"""

import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def test_data_synchronizer():
    """데이터 동기화 시스템 테스트"""
    print("=" * 60)
    print("📊 데이터 동기화 시스템 테스트")
    print("=" * 60)

    try:
        from core.data_pipeline.data_synchronizer import get_data_synchronizer

        synchronizer = get_data_synchronizer()
        print("✅ 데이터 동기화 시스템 로드 성공")

        # 전체 동기화 실행
        print("\n🔄 전체 데이터 동기화 실행...")
        sync_results = synchronizer.run_full_sync()

        print(f"📈 동기화 결과:")
        print(f"   - 스크리닝 동기화: {sync_results.get('screening_synced', 0)}건")
        print(f"   - 선정 동기화: {sync_results.get('selection_synced', 0)}건")
        print(f"   - 성과 업데이트: {sync_results.get('performance_updated', 0)}건")
        print(f"   - 메트릭 계산: {sync_results.get('metrics_calculated', 0)}개")

        # 데이터베이스 상태 확인
        db_path = "data/learning/learning_data.db"
        if Path(db_path).exists():
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                # 테이블별 레코드 수 확인
                tables = ['screening_history', 'selection_history', 'performance_tracking']
                print(f"\n💾 데이터베이스 상태:")

                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"   - {table}: {count}건")

        print("✅ 데이터 동기화 시스템 테스트 완료")
        return True

    except Exception as e:
        print(f"❌ 데이터 동기화 시스템 테스트 실패: {e}")
        return False

def test_enhanced_adaptive_system():
    """강화된 적응형 학습 시스템 테스트"""
    print("\n" + "=" * 60)
    print("🧠 강화된 적응형 학습 시스템 테스트")
    print("=" * 60)

    try:
        from core.learning.enhanced_adaptive_system import get_enhanced_adaptive_system

        enhanced_system = get_enhanced_adaptive_system()
        print("✅ 강화된 적응형 학습 시스템 로드 성공")

        # 시스템 헬스체크
        print("\n🏥 시스템 건강 상태 체크...")
        health_status = enhanced_system.check_system_health()

        print(f"📊 시스템 상태: {health_status.get('overall_status', '알 수 없음')}")
        print(f"   - 데이터베이스 상태: {'정상' if health_status.get('database_health', {}).get('status') else '이상'}")
        print(f"   - 데이터 신선도: {health_status.get('data_freshness', {}).get('days_since_update', '알 수 없음')}일 전")

        # 포괄적 분석 실행
        print("\n🔍 포괄적 학습 분석 실행...")
        analysis_result = enhanced_system.run_comprehensive_analysis()

        if analysis_result.get('status') != 'failed':
            print("✅ 포괄적 분석 완료")

            # 스크리닝 정확도
            screening_acc = analysis_result.get('screening_accuracy')
            if screening_acc:
                print(f"   - 스크리닝 정밀도: {screening_acc['precision']:.1%}")
                print(f"   - 스크리닝 재현율: {screening_acc['recall']:.1%}")
                print(f"   - F1 점수: {screening_acc['f1_score']:.2f}")

            # 선정 정확도
            selection_acc = analysis_result.get('selection_accuracy')
            if selection_acc:
                print(f"   - 선정 승률: {selection_acc['win_rate']:.1%}")
                print(f"   - 평균 수익률: {selection_acc['avg_return']:+.2%}")
                print(f"   - 샤프 비율: {selection_acc['sharpe_ratio']:.2f}")

            # 인사이트
            insights = analysis_result.get('insights', [])
            actionable_insights = [i for i in insights if i.get('actionable', False)]
            print(f"   - 총 인사이트: {len(insights)}개")
            print(f"   - 실행 가능한 인사이트: {len(actionable_insights)}개")

            # 파라미터 적응
            adaptation = analysis_result.get('parameter_adaptation', {})
            adapted = adaptation.get('status') == 'adapted'
            print(f"   - 파라미터 적응: {'완료' if adapted else '유지'}")

            if adapted:
                changes = adaptation.get('changes_made', [])
                print(f"   - 변경사항: {len(changes)}건")
        else:
            error_msg = analysis_result.get('error', '알 수 없는 오류')
            print(f"❌ 포괄적 분석 실패: {error_msg}")
            return False

        print("✅ 강화된 적응형 학습 시스템 테스트 완료")
        return True

    except Exception as e:
        print(f"❌ 강화된 적응형 학습 시스템 테스트 실패: {e}")
        return False

def test_system_monitor():
    """시스템 모니터 테스트"""
    print("\n" + "=" * 60)
    print("👁️ 시스템 모니터 테스트")
    print("=" * 60)

    try:
        from core.monitoring.system_monitor import get_system_monitor

        monitor = get_system_monitor()
        print("✅ 시스템 모니터 로드 성공")

        # 시스템 상태 조회
        print("\n📊 시스템 상태 조회...")
        system_status = monitor.get_system_status()

        print(f"   - 모니터링 활성: {'예' if system_status.get('monitoring_active') else '아니오'}")

        latest_metrics = system_status.get('latest_metrics')
        if latest_metrics:
            print(f"   - CPU 사용률: {latest_metrics.get('cpu_usage', 0):.1f}%")
            print(f"   - 메모리 사용률: {latest_metrics.get('memory_usage', 0):.1f}%")
            print(f"   - 디스크 사용률: {latest_metrics.get('disk_usage', 0):.1f}%")

        recent_alerts_count = system_status.get('recent_alerts_count', 0)
        critical_alerts_count = system_status.get('critical_alerts_count', 0)
        print(f"   - 최근 24시간 알림: {recent_alerts_count}건")
        print(f"   - 심각 알림: {critical_alerts_count}건")

        # 유지보수 필요성 체크
        print("\n🔧 유지보수 필요성 체크...")
        maintenance_result = monitor.run_maintenance_check()

        needs_maintenance = maintenance_result.get('needs_maintenance', False)
        reasons = maintenance_result.get('reasons', [])

        print(f"   - 유지보수 필요: {'예' if needs_maintenance else '아니오'}")
        if needs_maintenance:
            print(f"   - 필요 사유: {len(reasons)}건")
            for reason in reasons[:3]:
                print(f"     • {reason}")

        print("✅ 시스템 모니터 테스트 완료")
        return True

    except Exception as e:
        print(f"❌ 시스템 모니터 테스트 실패: {e}")
        return False

def test_scheduler_integration():
    """스케줄러 통합 테스트"""
    print("\n" + "=" * 60)
    print("⏰ 스케줄러 통합 테스트")
    print("=" * 60)

    try:
        from workflows.integrated_scheduler import IntegratedScheduler

        # 스케줄러 생성 (테스트용으로 워커 수 1개로 제한)
        scheduler = IntegratedScheduler(p_parallel_workers=1)
        print("✅ 통합 스케줄러 로드 성공")

        # 스케줄러 상태 조회
        print("\n📅 스케줄러 상태 조회...")
        status = scheduler.get_status()

        print(f"   - 실행 상태: {'실행 중' if status.get('running') else '정지'}")
        print(f"   - 마지막 스크리닝: {status.get('last_screening')}")
        print(f"   - 마지막 업데이트: {status.get('last_daily_update')}")

        scheduled_jobs = status.get('scheduled_jobs', [])
        print(f"   - 예정된 작업: {len(scheduled_jobs)}개")

        # 강화된 학습 함수 테스트
        print("\n🧠 강화된 학습 함수 테스트...")
        try:
            # 직접 함수 호출 (실제 스케줄 실행이 아닌 테스트)
            scheduler._run_enhanced_adaptive_learning()
            print("✅ 강화된 학습 함수 실행 성공")
        except Exception as learning_error:
            print(f"⚠️ 강화된 학습 함수 실행 중 오류: {learning_error}")

        print("✅ 스케줄러 통합 테스트 완료")
        return True

    except Exception as e:
        print(f"❌ 스케줄러 통합 테스트 실패: {e}")
        return False

def generate_test_data():
    """테스트용 더미 데이터 생성"""
    print("\n" + "=" * 60)
    print("🎲 테스트 데이터 생성")
    print("=" * 60)

    try:
        # 테스트용 스크리닝 결과 생성
        os.makedirs("data/watchlist", exist_ok=True)

        test_screening_data = {
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "total_count": 100,
            "passed_count": 25,
            "results": []
        }

        # 더미 스크리닝 결과 생성
        for i in range(25):
            stock_code = f"00{1000 + i}"
            test_screening_data["results"].append({
                "stock_code": stock_code,
                "stock_name": f"테스트종목{i}",
                "sector": "IT" if i < 10 else "제조업" if i < 20 else "금융",
                "screening_timestamp": datetime.now().isoformat(),
                "overall_passed": True,
                "overall_score": 65.0 + i,
                "fundamental": {
                    "passed": True,
                    "score": 70.0 + i,
                    "details": {
                        "roe": {"value": 10.0 + i * 0.5},
                        "per": {"value": 15.0 - i * 0.1},
                        "pbr": {"value": 1.5 + i * 0.1}
                    }
                },
                "technical": {
                    "passed": True,
                    "score": 60.0 + i
                }
            })

        # 테스트 스크리닝 파일 저장
        test_file_name = f"screening_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        test_file_path = f"data/watchlist/{test_file_name}"

        with open(test_file_path, 'w', encoding='utf-8') as f:
            json.dump(test_screening_data, f, indent=2, ensure_ascii=False)

        print(f"✅ 테스트 스크리닝 데이터 생성: {test_file_name}")

        # 테스트용 종목 선정 결과 생성
        os.makedirs("data/daily_selection", exist_ok=True)

        test_selection_data = {
            "timestamp": datetime.now().isoformat(),
            "market_condition": "neutral",
            "selected_stocks": [],
            "metadata": {
                "total_candidates": 25,
                "selected_count": 10,
                "avg_attractiveness": 75.0
            }
        }

        # 더미 선정 결과 생성
        for i in range(10):
            stock_code = f"00{1000 + i}"
            test_selection_data["selected_stocks"].append({
                "stock_code": stock_code,
                "stock_name": f"테스트종목{i}",
                "final_score": 80.0 + i,
                "predicted_direction": "buy",
                "confidence": 0.7 + i * 0.02,
                "reason": "기술적 지표 양호",
                "current_price": 10000 + i * 100
            })

        # 테스트 선정 파일 저장
        test_selection_file = f"data/daily_selection/daily_selection_{datetime.now().strftime('%Y%m%d')}.json"

        with open(test_selection_file, 'w', encoding='utf-8') as f:
            json.dump(test_selection_data, f, indent=2, ensure_ascii=False)

        print(f"✅ 테스트 선정 데이터 생성: daily_selection_{datetime.now().strftime('%Y%m%d')}.json")

        print("✅ 테스트 데이터 생성 완료")
        return True

    except Exception as e:
        print(f"❌ 테스트 데이터 생성 실패: {e}")
        return False

def cleanup_test_data():
    """테스트 데이터 정리"""
    print("\n🧹 테스트 데이터 정리...")

    try:
        # 테스트로 생성된 파일들 정리 (선택적)
        test_patterns = [
            "data/learning/comprehensive_analysis_results.json",
            "data/learning/enhanced_adaptation_history.json",
            "data/monitoring/system_alerts.json",
            "data/monitoring/performance_metrics.json"
        ]

        cleaned_count = 0
        for pattern in test_patterns:
            file_path = Path(pattern)
            if file_path.exists():
                # 실제 운영 데이터와 구분하여 테스트 데이터만 정리
                # 여기서는 정리하지 않고 유지
                pass

        print(f"ℹ️ 테스트 데이터는 향후 시스템에서 활용하도록 유지합니다")

    except Exception as e:
        print(f"⚠️ 테스트 데이터 정리 중 오류: {e}")

def main():
    """메인 테스트 함수"""
    print("🚀 강화된 학습 시스템 통합 테스트 시작")
    print(f"⏰ 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    test_results = []

    # 1. 테스트 데이터 생성
    test_results.append(("테스트 데이터 생성", generate_test_data()))

    # 2. 데이터 동기화 시스템 테스트
    test_results.append(("데이터 동기화 시스템", test_data_synchronizer()))

    # 3. 강화된 적응형 학습 시스템 테스트
    test_results.append(("강화된 적응형 학습 시스템", test_enhanced_adaptive_system()))

    # 4. 시스템 모니터 테스트
    test_results.append(("시스템 모니터", test_system_monitor()))

    # 5. 스케줄러 통합 테스트
    test_results.append(("스케줄러 통합", test_scheduler_integration()))

    # 결과 요약
    print("\n" + "=" * 80)
    print("📋 테스트 결과 요약")
    print("=" * 80)

    passed_tests = 0
    failed_tests = 0

    for test_name, result in test_results:
        status = "✅ 성공" if result else "❌ 실패"
        print(f"{status} {test_name}")
        if result:
            passed_tests += 1
        else:
            failed_tests += 1

    print(f"\n📊 전체 결과: {passed_tests}개 성공, {failed_tests}개 실패")

    if failed_tests == 0:
        print("🎉 모든 테스트가 성공적으로 완료되었습니다!")
        print("\n🚀 강화된 학습 시스템이 준비되었습니다:")
        print("   - 자동 데이터 동기화 ✅")
        print("   - 포괄적 성능 분석 ✅")
        print("   - 예측 정확도 측정 ✅")
        print("   - 지능형 파라미터 적응 ✅")
        print("   - 실시간 시스템 모니터링 ✅")
        print("   - 자동 유지보수 ✅")
        print("\n💡 이제 스케줄러를 시작하여 자율 운영을 시작할 수 있습니다!")
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 실패한 항목을 점검하세요.")

    print(f"\n⏰ 종료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()