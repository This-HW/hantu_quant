#!/usr/bin/env python3
"""
간단한 텔레그램 알림 설정 도구

의존성 없이 텔레그램 알림을 쉽게 설정하는 도구
"""

import json
import os
import requests
import sys
from pathlib import Path

class SimpleTelegramSetup:
    """간단한 텔레그램 설정"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.config_dir = self.project_root / "config"
        
    def setup(self):
        """대화형 설정"""
        print("🤖 한투 퀀트 텔레그램 알림 설정")
        print("=" * 50)
        print("\n📝 먼저 다음 단계를 완료해주세요:")
        print("   1. @BotFather에게 /newbot 명령으로 봇 생성")
        print("   2. 생성한 봇을 채널에 관리자로 추가")
        print("   3. 채널에서 '/start' 메시지 전송")
        print()
        
        # 1. 봇 토큰 입력
        bot_token = input("🔑 텔레그램 봇 토큰을 입력하세요: ").strip()
        if not bot_token:
            print("❌ 봇 토큰이 필요합니다.")
            return False
        
        # 2. 채널 ID 확인
        print("\n🔍 채널 ID를 확인하는 중...")
        chat_ids = self.get_chat_ids(bot_token)
        
        if not chat_ids:
            print("❌ 채널을 찾을 수 없습니다.")
            print("\n💡 해결 방법:")
            print("   1. 봇이 채널에 관리자로 추가되었는지 확인")
            print("   2. 채널에서 아무 메시지나 전송")
            print("   3. 다시 실행해보세요")
            return False
        
        # 3. 채널 선택
        print("\n📺 발견된 채널/채팅:")
        for i, (chat_id, info) in enumerate(chat_ids.items(), 1):
            print(f"   {i}. {info['title']} ({info['type']}) - ID: {chat_id}")
        
        try:
            choice = int(input("\n선택할 번호를 입력하세요: ")) - 1
            selected_chat_id = list(chat_ids.keys())[choice]
            selected_info = chat_ids[selected_chat_id]
        except (ValueError, IndexError):
            print("❌ 잘못된 선택입니다.")
            return False
        
        # 4. 설정 저장
        if self.save_config(bot_token, selected_chat_id):
            print(f"\n✅ 설정 완료!")
            print(f"   채널: {selected_info['title']}")
            print(f"   ID: {selected_chat_id}")
            
            # 5. 테스트 메시지
            if input("\n📤 테스트 메시지를 보내시겠습니까? (y/n): ").lower() == 'y':
                self.send_test_message(bot_token, selected_chat_id)
            
            print("\n🎉 텔레그램 알림 설정이 완료되었습니다!")
            print("   이제 한투 퀀트 시스템에서 실시간 알림을 받을 수 있습니다.")
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
                print(f"❌ 봇 토큰이 잘못되었거나 API 오류입니다.")
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
            print(f"❌ 오류 발생: {e}")
            return {}
    
    def save_config(self, bot_token: str, chat_id: str) -> bool:
        """설정 저장"""
        try:
            # 설정 생성
            config = {
                "telegram": {
                    "bot_token": bot_token,
                    "default_chat_ids": [chat_id],
                    "channel_mapping": {
                        "auto_trade": chat_id
                    },
                    "enabled": True,
                    "message_format": {
                        "use_markdown": True,
                        "include_timestamp": True,
                        "max_stocks_shown": 5
                    }
                }
            }
            
            # config 디렉토리 생성
            os.makedirs(self.config_dir, exist_ok=True)
            
            # JSON 파일 저장
            config_file = self.config_dir / "telegram_config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            
            print(f"📁 설정 파일 저장: {config_file}")
            
            # .env 파일에도 추가
            env_file = self.project_root / ".env"
            try:
                # 기존 .env 내용 읽기
                env_content = ""
                if env_file.exists():
                    env_content = env_file.read_text()
                
                # 텔레그램 설정 추가
                if "TELEGRAM_BOT_TOKEN" not in env_content:
                    with open(env_file, 'a') as f:
                        f.write(f"\n# 텔레그램 알림 설정\n")
                        f.write(f"TELEGRAM_BOT_TOKEN={bot_token}\n")
                        f.write(f"TELEGRAM_CHAT_ID={chat_id}\n")
                    print(f"📁 환경 변수 추가: {env_file}")
            except Exception as e:
                print(f"⚠️ .env 파일 업데이트 실패 (무시 가능): {e}")
            
            return True
            
        except Exception as e:
            print(f"❌ 설정 저장 실패: {e}")
            return False
    
    def send_test_message(self, bot_token: str, chat_id: str):
        """테스트 메시지 전송"""
        try:
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

🔗 채널: [auto_trade](https://t.me/+SJ1pUvWNg-s2YWU1)
⏰ 설정 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""

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
                return True
            else:
                print(f"❌ 메시지 전송 실패: {response.status_code}")
                if response.status_code == 403:
                    print("   💡 봇이 채널에서 메시지 전송 권한이 없습니다.")
                    print("      채널 설정에서 봇에게 '메시지 전송' 권한을 부여하세요.")
                elif response.status_code == 400:
                    print("   💡 채널 ID가 잘못되었을 수 있습니다.")
                return False
        
        except Exception as e:
            print(f"❌ 테스트 메시지 전송 실패: {e}")
            return False
    
    def test_existing_config(self):
        """기존 설정 테스트"""
        config_file = self.config_dir / "telegram_config.json"
        
        if not config_file.exists():
            print("❌ 설정 파일이 없습니다.")
            print("   먼저 'python scripts/simple_telegram_setup.py setup' 을 실행하세요.")
            return False
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            telegram_config = config.get('telegram', {})
            bot_token = telegram_config.get('bot_token')
            chat_ids = telegram_config.get('default_chat_ids', [])
            
            if not bot_token or not chat_ids:
                print("❌ 설정이 불완전합니다.")
                return False
            
            print("🧪 기존 설정으로 테스트 메시지 전송...")
            return self.send_test_message(bot_token, chat_ids[0])
        
        except Exception as e:
            print(f"❌ 설정 테스트 실패: {e}")
            return False

def main():
    """메인 함수"""
    setup = SimpleTelegramSetup()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            setup.test_existing_config()
        elif sys.argv[1] == "setup":
            setup.setup()
        else:
            print("사용법:")
            print(f"  python {sys.argv[0]} setup  # 새로 설정")
            print(f"  python {sys.argv[0]} test   # 기존 설정 테스트")
    else:
        # 기본: 새로 설정
        setup.setup()

if __name__ == "__main__":
    main() 