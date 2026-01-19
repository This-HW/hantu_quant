#!/usr/bin/env python3
"""
텔레그램 알림 시스템 진단 도구
- 설정 상태 확인
- 연결 테스트
- 알림 전송 테스트
- 전체 시스템 상태 진단
"""

import sys
import os
import json
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 디렉토리 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.utils.telegram_notifier import get_telegram_notifier
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


class TelegramDiagnostic:
    """텔레그램 알림 시스템 진단 클래스"""
    
    def __init__(self):
        """초기화"""
        self.notifier = get_telegram_notifier()
        self.config_file = Path("config/telegram_config.json")
        
    def run_full_diagnostic(self) -> bool:
        """전체 진단 실행
        
        Returns:
            진단 결과 (True: 정상, False: 문제 있음)
        """
        print("🔍 텔레그램 알림 시스템 진단 시작")
        print("=" * 50)
        
        all_tests_passed = True
        
        # 1. 설정 파일 확인
        config_ok = self._check_config_file()
        all_tests_passed &= config_ok
        
        # 2. 설정 값 검증
        settings_ok = self._check_settings()
        all_tests_passed &= settings_ok
        
        # 3. 연결 테스트
        connection_ok = self._test_connection()
        all_tests_passed &= connection_ok
        
        # 4. 알림 전송 테스트
        if connection_ok:
            notification_ok = self._test_notifications()
            all_tests_passed &= notification_ok
        
        # 5. 스케줄러 연동 테스트
        scheduler_ok = self._test_scheduler_integration()
        all_tests_passed &= scheduler_ok
        
        print("\n" + "=" * 50)
        if all_tests_passed:
            print("✅ 모든 진단 테스트 통과! 텔레그램 알림 시스템이 정상 작동합니다.")
        else:
            print("❌ 일부 테스트 실패. 위 오류들을 확인해주세요.")
        
        return all_tests_passed
    
    def _check_config_file(self) -> bool:
        """설정 파일 존재 및 형식 확인"""
        print("\n1. 설정 파일 확인")
        print("-" * 30)
        
        if not self.config_file.exists():
            print(f"❌ 설정 파일 없음: {self.config_file}")
            return False
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            print(f"✅ 설정 파일 존재: {self.config_file}")
            print(f"   파일 크기: {self.config_file.stat().st_size} bytes")
            
            # 필수 키 확인
            telegram_keys = ['bot_token', 'default_chat_ids']
            
            if 'telegram' not in config:
                print("❌ telegram 설정 섹션 없음")
                return False
            
            telegram_config = config['telegram']
            missing_keys = [key for key in telegram_keys if key not in telegram_config]
            
            if missing_keys:
                print(f"❌ 필수 설정 키 누락: {missing_keys}")
                return False
            
            print("✅ 필수 설정 키 모두 존재")
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON 파싱 오류: {e}")
            return False
        except Exception as e:
            print(f"❌ 설정 파일 읽기 오류: {e}")
            return False
    
    def _check_settings(self) -> bool:
        """설정 값 검증"""
        print("\n2. 설정 값 검증")
        print("-" * 30)
        
        if not self.notifier.is_enabled():
            print("❌ 텔레그램 알림이 비활성화됨")
            return False
        
        print("✅ 텔레그램 알림 시스템 활성화됨")
        
        # 설정 세부 정보 출력
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            telegram_config = config['telegram']
            
            # 봇 토큰 검증 (앞 몇 글자만 표시)
            bot_token = telegram_config.get('bot_token', '')
            if bot_token:
                masked_token = bot_token[:8] + "*" * (len(bot_token) - 12) + bot_token[-4:] if len(bot_token) > 12 else "*" * len(bot_token)
                print(f"✅ 봇 토큰: {masked_token}")
            else:
                print("❌ 봇 토큰이 비어있음")
                return False
            
            # 채팅 ID 확인
            chat_ids = telegram_config.get('default_chat_ids', [])
            if chat_ids:
                print(f"✅ 채팅 ID: {len(chat_ids)}개 설정됨")
                for i, chat_id in enumerate(chat_ids, 1):
                    print(f"   {i}. {chat_id}")
            else:
                print("❌ 채팅 ID가 설정되지 않음")
                return False
            
            # 알림 설정 확인
            notification_settings = telegram_config.get('notification_settings', {})
            if notification_settings:
                print(f"✅ 알림 설정: {len(notification_settings)}개 우선순위 설정됨")
            
            return True
            
        except Exception as e:
            print(f"❌ 설정 검증 오류: {e}")
            return False
    
    def _test_connection(self) -> bool:
        """텔레그램 봇 연결 테스트"""
        print("\n3. 연결 테스트")
        print("-" * 30)
        
        try:
            # 간단한 테스트 메시지 전송
            test_message = f"🔧 *한투 퀀트 연결 테스트*\n\n⏰ 테스트 시간: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n✅ 텔레그램 연결이 정상 작동합니다!"
            
            success = self.notifier.send_message(test_message, "low")
            
            if success:
                print("✅ 텔레그램 연결 성공!")
                print("   텔레그램에서 테스트 메시지를 확인하세요.")
                return True
            else:
                print("❌ 텔레그램 연결 실패")
                return False
                
        except Exception as e:
            print(f"❌ 연결 테스트 오류: {e}")
            return False
    
    def _test_notifications(self) -> bool:
        """각종 알림 메시지 테스트"""
        print("\n4. 알림 메시지 테스트")
        print("-" * 30)
        
        tests_passed = 0
        total_tests = 5
        
        # 스케줄러 시작 알림 테스트
        print("4.1 스케줄러 시작 알림...")
        try:
            success = self.notifier.send_scheduler_started()
            if success:
                print("✅ 스케줄러 시작 알림 성공")
                tests_passed += 1
            else:
                print("❌ 스케줄러 시작 알림 실패")
        except Exception as e:
            print(f"❌ 스케줄러 시작 알림 오류: {e}")
        
        # 스크리닝 완료 알림 테스트
        print("4.2 스크리닝 완료 알림...")
        try:
            test_stats = {
                'total_count': 150,
                'avg_score': 7.2,
                'sectors': {'테크': 45, '바이오': 32, '에너지': 28}
            }
            success = self.notifier.send_screening_complete(test_stats)
            if success:
                print("✅ 스크리닝 완료 알림 성공")
                tests_passed += 1
            else:
                print("❌ 스크리닝 완료 알림 실패")
        except Exception as e:
            print(f"❌ 스크리닝 완료 알림 오류: {e}")
        
        # 일일 업데이트 완료 알림 테스트
        print("4.3 일일 업데이트 완료 알림...")
        try:
            success = self.notifier.send_daily_update_complete(25)
            if success:
                print("✅ 일일 업데이트 완료 알림 성공")
                tests_passed += 1
            else:
                print("❌ 일일 업데이트 완료 알림 실패")
        except Exception as e:
            print(f"❌ 일일 업데이트 완료 알림 오류: {e}")
        
        # 오류 알림 테스트
        print("4.4 오류 알림...")
        try:
            success = self.notifier.send_error_alert("테스트 오류", "진단 도구에서 발생한 테스트 오류입니다")
            if success:
                print("✅ 오류 알림 성공")
                tests_passed += 1
            else:
                print("❌ 오류 알림 실패")
        except Exception as e:
            print(f"❌ 오류 알림 오류: {e}")
        
        # 스케줄러 종료 알림 테스트
        print("4.5 스케줄러 종료 알림...")
        try:
            success = self.notifier.send_scheduler_stopped("진단 테스트 완료")
            if success:
                print("✅ 스케줄러 종료 알림 성공")
                tests_passed += 1
            else:
                print("❌ 스케줄러 종료 알림 실패")
        except Exception as e:
            print(f"❌ 스케줄러 종료 알림 오류: {e}")
        
        success_rate = tests_passed / total_tests
        print(f"\n알림 테스트 결과: {tests_passed}/{total_tests} 성공 ({success_rate:.1%})")
        
        return success_rate >= 0.8  # 80% 이상 성공시 통과
    
    def _test_scheduler_integration(self) -> bool:
        """스케줄러 연동 테스트"""
        print("\n5. 스케줄러 연동 테스트")
        print("-" * 30)
        
        try:
            # 스케줄러 상태 확인
            import subprocess
            result = subprocess.run(
                ['python3', 'workflows/integrated_scheduler.py', 'status'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                if "실행 중" in result.stdout:
                    print("✅ 스케줄러가 실행 중입니다")
                    return True
                else:
                    print("⚠️ 스케줄러가 실행되지 않음 (정상 - 수동 시작 필요)")
                    print("   스케줄러 시작: python3 workflows/integrated_scheduler.py start")
                    return True
            else:
                print(f"❌ 스케줄러 상태 확인 실패: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ 스케줄러 상태 확인 시간 초과")
            return False
        except Exception as e:
            print(f"❌ 스케줄러 연동 테스트 오류: {e}")
            return False
    
    def quick_test(self) -> bool:
        """빠른 연결 테스트"""
        print("🚀 빠른 텔레그램 연결 테스트")
        print("-" * 30)
        
        if not self.notifier.is_enabled():
            print("❌ 텔레그램 알림이 비활성화됨")
            return False
        
        test_message = f"⚡ *빠른 테스트*\n\n⏰ {datetime.now().strftime('%H:%M:%S')}\n✅ 연결 정상!"
        success = self.notifier.send_message(test_message, "low")
        
        if success:
            print("✅ 텔레그램 연결 성공!")
        else:
            print("❌ 텔레그램 연결 실패")
        
        return success


def main():
    """메인 함수"""
    import argparse
    
    parser = argparse.ArgumentParser(description="텔레그램 알림 시스템 진단 도구")
    parser.add_argument('--quick', action='store_true', help='빠른 연결 테스트만 실행')
    parser.add_argument('--config-check', action='store_true', help='설정 확인만 실행')
    
    args = parser.parse_args()
    
    diagnostic = TelegramDiagnostic()
    
    try:
        if args.quick:
            success = diagnostic.quick_test()
        elif args.config_check:
            success = diagnostic._check_config_file() and diagnostic._check_settings()
        else:
            success = diagnostic.run_full_diagnostic()
        
        exit_code = 0 if success else 1
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단됨")
        sys.exit(1)
    except Exception as e:
        print(f"\n진단 도구 실행 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()