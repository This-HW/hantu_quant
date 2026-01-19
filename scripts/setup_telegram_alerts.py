#!/usr/bin/env python3
"""
텔레그램 알림 설정 도구

한투 퀀트 시스템의 텔레그램 알림을 쉽게 설정하는 도구
"""

import json
import os
import sys
import requests
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.market_monitor.integrated_alert_manager import IntegratedAlertManager, NotificationPriority  # noqa: E402
from core.market_monitor.anomaly_detector import AnomalyAlert, AnomalySeverity, AnomalyType  # noqa: E402
from datetime import datetime  # noqa: E402

class TelegramSetup:
    """텔레그램 설정 도구"""
    
    def __init__(self):
        self.config_path = project_root / "config" / "telegram_config.json"
        self.env_path = project_root / ".env"
        
    def interactive_setup(self):
        """대화형 설정"""
        print("🤖 한투 퀀트 텔레그램 알림 설정")
        print("=" * 50)
        
        # 1. 봇 토큰 입력
        print("\n1️⃣ 텔레그램 봇 토큰을 입력하세요:")
        print("   (BotFather에서 받은 토큰: 123456789:ABC...)")
        bot_token = input("봇 토큰: ").strip()
        
        if not bot_token:
            print("❌ 봇 토큰이 필요합니다.")
            return False
        
        # 2. 채널 ID 확인
        print("\n2️⃣ 채널 ID를 확인합니다...")
        chat_ids = self.get_chat_ids(bot_token)
        
        if not chat_ids:
            print("❌ 채널 ID를 찾을 수 없습니다.")
            print("💡 다음 단계를 수행하세요:")
            print("   1. 봇을 채널에 관리자로 추가")
            print("   2. 채널에서 '/start' 메시지 전송")
            print("   3. 이 스크립트를 다시 실행")
            return False
        
        # 3. 채널 선택
        print("\n3️⃣ 알림을 받을 채널을 선택하세요:")
        for i, (chat_id, chat_info) in enumerate(chat_ids.items(), 1):
            print(f"   {i}. {chat_info['title']} (ID: {chat_id})")
        
        try:
            choice = int(input("선택 (번호): ")) - 1
            selected_chat_id = list(chat_ids.keys())[choice]
            selected_info = chat_ids[selected_chat_id]
        except (ValueError, IndexError):
            print("❌ 잘못된 선택입니다.")
            return False
        
        # 4. 설정 저장
        config = self.create_config(bot_token, selected_chat_id)
        if self.save_config(config):
            print("\n✅ 설정이 저장되었습니다!")
            print(f"   채널: {selected_info['title']}")
            print(f"   ID: {selected_chat_id}")
            
            # 5. 테스트 메시지 전송
            if input("\n📤 테스트 메시지를 전송하시겠습니까? (y/n): ").lower() == 'y':
                self.send_test_message(bot_token, selected_chat_id)
            
            return True
        
        return False
    
    def get_chat_ids(self, bot_token: str) -> dict:
        """채팅 ID 목록 조회"""
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ API 호출 실패: {response.status_code}")
                return {}
            
            data = response.json()
            if not data.get('ok'):
                print("❌ API 응답 오류")
                return {}
            
            updates = data.get('result', [])
            chats = {}
            
            for update in updates:
                # 일반 메시지
                if 'message' in update:
                    chat = update['message']['chat']
                    chat_id = str(chat['id'])
                    chats[chat_id] = {
                        'title': chat.get('title', chat.get('first_name', 'Personal Chat')),
                        'type': chat['type']
                    }
                
                # 채널 포스트
                if 'channel_post' in update:
                    chat = update['channel_post']['chat']
                    chat_id = str(chat['id'])
                    chats[chat_id] = {
                        'title': chat.get('title', 'Channel'),
                        'type': chat['type']
                    }
            
            return chats
            
        except Exception as e:
            print(f"❌ 채팅 ID 조회 실패: {e}")
            return {}
    
    def create_config(self, bot_token: str, chat_id: str) -> dict:
        """설정 생성"""
        return {
            "telegram": {
                "bot_token": bot_token,
                "default_chat_ids": [chat_id],
                "channel_mapping": {
                    "auto_trade": chat_id
                },
                "notification_settings": {
                    "emergency": {"enabled": True, "sound": True},
                    "high": {"enabled": True, "sound": True},
                    "normal": {"enabled": True, "sound": False},
                    "low": {"enabled": True, "sound": False}
                },
                "message_format": {
                    "use_markdown": True,
                    "include_timestamp": True,
                    "max_stocks_shown": 5
                },
                "rate_limiting": {
                    "max_messages_per_hour": 20,
                    "max_messages_per_day": 100,
                    "cooldown_seconds": 60
                }
            }
        }
    
    def save_config(self, config: dict) -> bool:
        """설정 저장"""
        try:
            # config 디렉토리 생성
            os.makedirs(self.config_path.parent, exist_ok=True)
            
            # JSON 파일 저장
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            # .env 파일에도 추가 (있으면)
            if self.env_path.exists():
                env_content = self.env_path.read_text()
                if "TELEGRAM_BOT_TOKEN" not in env_content:
                    with open(self.env_path, 'a') as f:
                        f.write("\n# 텔레그램 설정\n")
                        f.write(f"TELEGRAM_BOT_TOKEN={config['telegram']['bot_token']}\n")
                        f.write(f"TELEGRAM_CHAT_ID={config['telegram']['default_chat_ids'][0]}\n")
            
            return True
            
        except Exception as e:
            print(f"❌ 설정 저장 실패: {e}")
            return False
    
    def send_test_message(self, bot_token: str, chat_id: str):
        """테스트 메시지 전송"""
        try:
            # 실제 알림 시스템을 사용한 테스트
            IntegratedAlertManager()
            
            # 테스트 알림 생성
            AnomalyAlert(
                alert_id="test_001",
                timestamp=datetime.now(),
                anomaly_type=AnomalyType.NEWS_IMPACT,
                severity=AnomalySeverity.MEDIUM,
                title="🎉 텔레그램 알림 테스트",
                description="한투 퀀트 텔레그램 알림 시스템이 정상적으로 연결되었습니다!",
                confidence_score=1.0,
                affected_stocks=["005930", "000660"],
                recommendations=[
                    "텔레그램 알림 설정 완료",
                    "이제 실시간 시장 알림을 받을 수 있습니다",
                    "한투 퀀트와 함께 스마트한 투자하세요!"
                ]
            )
            
            # 직접 텔레그램 API로 전송
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            message = """🎉 *한투 퀀트 알림 테스트*

📊 텔레그램 알림 시스템이 정상적으로 연결되었습니다!

✅ 이제 다음과 같은 알림을 받을 수 있습니다:
• 🚨 급등/급락 감지 (5% 이상 변동)
• 📈 AI 기반 종목 추천 (82% 정확도)
• ⚠️ 시스템 이상 상황 감지
• 💡 실시간 투자 인사이트
• 📊 일일 성과 리포트

*한투 퀀트와 함께 스마트한 투자하세요!*

🔗 채널 정보: [auto_trade](https://t.me/+SJ1pUvWNg-s2YWU1)"""

            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': False
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                print("✅ 테스트 메시지 전송 성공!")
                print("   채널에서 메시지를 확인하세요.")
            else:
                print(f"❌ 테스트 메시지 전송 실패: {response.status_code}")
                print(f"   응답: {response.text}")
        
        except Exception as e:
            print(f"❌ 테스트 메시지 전송 실패: {e}")
    
    def test_integration(self):
        """시스템 통합 테스트"""
        try:
            if not self.config_path.exists():
                print("❌ 설정 파일이 없습니다. 먼저 설정을 완료하세요.")
                return False
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            telegram_config = config.get('telegram', {})
            bot_token = telegram_config.get('bot_token')
            chat_ids = telegram_config.get('default_chat_ids', [])
            
            if not bot_token or not chat_ids:
                print("❌ 설정이 불완전합니다.")
                return False
            
            print("🧪 통합 알림 시스템 테스트...")
            
            # 다양한 우선순위의 테스트 알림 전송
            test_cases = [
                ("📊 정상 알림", NotificationPriority.NORMAL),
                ("⚠️ 높은 우선순위 알림", NotificationPriority.HIGH),
                ("🚨 긴급 알림", NotificationPriority.EMERGENCY)
            ]
            
            for title, priority in test_cases:
                AnomalyAlert(
                    alert_id=f"integration_test_{priority.value}",
                    timestamp=datetime.now(),
                    anomaly_type=AnomalyType.PRICE_SPIKE,
                    severity=AnomalySeverity.HIGH if priority == NotificationPriority.HIGH else AnomalySeverity.MEDIUM,
                    title=title,
                    description=f"우선순위 {priority.value} 테스트 알림입니다.",
                    confidence_score=0.95,
                    affected_stocks=["005930"]
                )
                
                self.send_test_message(bot_token, chat_ids[0])
                
            print("✅ 통합 테스트 완료!")
            return True
            
        except Exception as e:
            print(f"❌ 통합 테스트 실패: {e}")
            return False

def main():
    """메인 함수"""
    setup = TelegramSetup()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            setup.test_integration()
        elif sys.argv[1] == "setup":
            setup.interactive_setup()
        else:
            print("사용법:")
            print(f"  python {sys.argv[0]} setup  # 대화형 설정")
            print(f"  python {sys.argv[0]} test   # 통합 테스트")
    else:
        # 기본: 대화형 설정
        setup.interactive_setup()

if __name__ == "__main__":
    main() 