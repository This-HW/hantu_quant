#!/usr/bin/env python3
"""
텔레그램 채널 ID 확인 유틸리티

봇 토큰을 사용하여 채널 ID를 확인하는 스크립트
"""

import requests
import sys

def get_channel_id(bot_token: str):
    """
    텔레그램 봇으로 채널 ID 확인
    
    Args:
        bot_token: 텔레그램 봇 토큰
    """
    try:
        # 봇에게 온 업데이트 확인
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"❌ API 호출 실패: {response.status_code}")
            return
        
        data = response.json()
        
        if not data.get('ok'):
            print(f"❌ API 응답 오류: {data}")
            return
        
        updates = data.get('result', [])
        
        if not updates:
            print("📝 채널에서 다음 메시지를 보내세요:")
            print("   '/start' 또는 아무 메시지나")
            print("   그 후 이 스크립트를 다시 실행하세요.")
            return
        
        print("📍 발견된 채팅/채널 ID들:")
        print("-" * 50)
        
        seen_chats = set()
        
        for update in updates:
            # 일반 메시지
            if 'message' in update:
                chat = update['message']['chat']
                chat_id = chat['id']
                chat_type = chat['type']
                chat_title = chat.get('title', chat.get('first_name', 'Unknown'))
                
                if chat_id not in seen_chats:
                    print(f"🏷️  타입: {chat_type}")
                    print(f"📍 ID: {chat_id}")
                    print(f"📝 이름: {chat_title}")
                    print("-" * 30)
                    seen_chats.add(chat_id)
            
            # 채널 포스트
            if 'channel_post' in update:
                chat = update['channel_post']['chat']
                chat_id = chat['id']
                chat_type = chat['type']
                chat_title = chat.get('title', 'Unknown Channel')
                
                if chat_id not in seen_chats:
                    print(f"🏷️  타입: {chat_type}")
                    print(f"📍 ID: {chat_id}")
                    print(f"📝 이름: {chat_title}")
                    print("-" * 30)
                    seen_chats.add(chat_id)
        
        if seen_chats:
            print("✅ 위 ID들 중 하나를 설정 파일에 사용하세요!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

def test_send_message(bot_token: str, chat_id: str):
    """
    테스트 메시지 전송
    
    Args:
        bot_token: 봇 토큰
        chat_id: 채팅/채널 ID
    """
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        message = """🎉 *한투 퀀트 알림 테스트*

📊 텔레그램 알림 시스템이 정상적으로 연결되었습니다!

✅ 이제 다음과 같은 알림을 받을 수 있습니다:
• 🚨 급등/급락 알림
• 📈 AI 종목 추천
• ⚠️ 시스템 이상 감지
• 💡 투자 인사이트

*한투 퀀트와 함께 스마트한 투자하세요!*"""

        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            print("✅ 테스트 메시지 전송 성공!")
            print("   채널에서 메시지를 확인하세요.")
        else:
            print(f"❌ 메시지 전송 실패: {response.status_code}")
            print(f"   응답: {response.text}")
    
    except Exception as e:
        print(f"❌ 테스트 전송 실패: {e}")

if __name__ == "__main__":
    print("🤖 텔레그램 채널 ID 확인 도구")
    print("=" * 40)
    
    if len(sys.argv) < 2:
        print("사용법:")
        print(f"  python {sys.argv[0]} <봇_토큰>")
        print(f"  python {sys.argv[0]} <봇_토큰> <채널_ID>  # 테스트 메시지 전송")
        print()
        print("예시:")
        print(f"  python {sys.argv[0]} 123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
        sys.exit(1)
    
    bot_token = sys.argv[1]
    
    if len(sys.argv) >= 3:
        # 테스트 메시지 전송
        chat_id = sys.argv[2]
        print(f"📤 테스트 메시지 전송 중... (채널 ID: {chat_id})")
        test_send_message(bot_token, chat_id)
    else:
        # 채널 ID 확인
        print("🔍 채널 ID 확인 중...")
        get_channel_id(bot_token) 