#!/usr/bin/env python3
"""
자동 매매 수동 실행 테스트
스케줄러의 _start_auto_trading 함수를 직접 호출하여 테스트
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from workflows.integrated_scheduler import IntegratedScheduler
from core.utils.log_utils import setup_logging, get_logger

# 로깅 설정
log_filename = f"logs/manual_trading_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
setup_logging(log_filename, add_sensitive_filter=True)
logger = get_logger(__name__)

def main():
    """메인 함수"""
    print("="*60)
    print("🧪 자동 매매 수동 실행 테스트")
    print("="*60)
    print(f"📝 로그 파일: {log_filename}\n")

    try:
        # 1. 스케줄러 초기화
        print("[1] 스케줄러 초기화...")
        scheduler = IntegratedScheduler(p_parallel_workers=4)
        print("✅ 스케줄러 초기화 완료\n")

        # 2. 자동 매매 시작 함수 직접 호출
        print("[2] 자동 매매 시작 함수 호출...")
        print("⚠️  주의: 실제 가상계좌에서 매매가 시도됩니다!\n")

        # 5초 대기
        print("5초 후 자동 매매를 시작합니다...")
        import time
        for i in range(5, 0, -1):
            print(f"   {i}...")
            time.sleep(1)

        print("\n🚀 자동 매매 시작!\n")
        scheduler._start_auto_trading()

        print("\n✅ 자동 매매가 백그라운드에서 시작되었습니다!")
        print("📊 매매 로직이 30초마다 실행됩니다.")
        print("📝 상세 로그는 로그 파일을 확인하세요.")

        # 30초 대기 후 상태 확인
        print("\n⏳ 30초 대기 중...")
        time.sleep(30)

        print("\n[3] 로그 파일 확인...")
        with open(log_filename, 'r', encoding='utf-8') as f:
            recent_logs = f.readlines()[-30:]
            print("="*60)
            print("📋 최근 로그 (마지막 30줄):")
            print("="*60)
            for line in recent_logs:
                print(line.rstrip())

        print("\n" + "="*60)
        print("✅ 테스트 완료!")
        print("="*60)
        print("\n📌 참고사항:")
        print("   • 자동 매매는 백그라운드에서 계속 실행됩니다")
        print("   • 장 시간(09:00~15:30)에만 실제 매매가 이루어집니다")
        print("   • 로그 파일에서 상세 정보를 확인할 수 있습니다")

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
