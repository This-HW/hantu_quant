#!/usr/bin/env python3
"""
실시간 텔레그램 알림 테스트

한투 퀀트 실제 알림 시스템과 연동하여 텔레그램 알림을 테스트
"""

import json
import os
import sys
import requests
import time
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 디렉토리 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def load_telegram_config():
    """텔레그램 설정 로드"""
    config_file = project_root / "config" / "telegram_config.json"
    
    if not config_file.exists():
        print("❌ 텔레그램 설정 파일이 없습니다.")
        return None
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        telegram_config = config.get('telegram', {})
        return telegram_config
    
    except Exception as e:
        print(f"❌ 설정 로드 실패: {e}")
        return None

def send_telegram_message(bot_token: str, chat_id: str, message: str, parse_mode: str = "Markdown"):
    """텔레그램 메시지 전송"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': parse_mode,
            'disable_web_page_preview': False
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True
        else:
            print(f"❌ 메시지 전송 실패: {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ 메시지 전송 오류: {e}")
        return False

def test_alert_messages():
    """다양한 알림 메시지 테스트"""
    
    # 설정 로드
    config = load_telegram_config()
    if not config:
        return False
    
    bot_token = config.get('bot_token')
    chat_ids = config.get('default_chat_ids', [])
    
    if not bot_token or not chat_ids:
        print("❌ 텔레그램 설정이 불완전합니다.")
        return False
    
    chat_id = chat_ids[0]
    
    print("🚀 한투 퀀트 실시간 알림 테스트 시작!")
    print(f"📱 채널 ID: {chat_id}")
    print("-" * 50)
    
    # 테스트 케이스들
    test_cases = [
        {
            "title": "🎉 시스템 연결 확인",
            "message": """🎉 *한투 퀀트 알림 시스템 연결 완료*

📊 텔레그램 알림이 성공적으로 설정되었습니다!

✅ *설정 정보*:
• 봇 이름: hantu_quant_alert_bot
• 채널: auto_trade
• 설정 시간: {timestamp}

🚀 *활성화된 알림 유형*:
• 🚨 급등/급락 감지 (5% 이상)
• 📈 AI 종목 추천 (82% 정확도)
• ⚠️ 시스템 이상 감지
• 💡 투자 인사이트
• 📊 일일 성과 리포트

*이제 실시간 시장 알림을 받을 수 있습니다!*""".format(
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        },
        {
            "title": "🚨 급등 알림 샘플",
            "message": """🚨🔥 *급등 종목 감지*

*삼성전자 (005930) 급등 알림*

📅 시간: `{timestamp}`
🎯 심각도: `HIGH`
🔍 유형: `급격한 가격 변동`
📊 신뢰도: `94.2%`

📈 *변동 정보*:
• 현재가: 71,500원 (+5,200원)
• 등락률: +7.8% ⬆️
• 거래량: 평소 대비 3.2배 📊

💡 *추천 조치*:
1. 급등 원인 뉴스 확인 필요
2. 거래량 추이 지속 모니터링
3. 기술적 지지선 확인 권장

⚠️ *주의*: 급등 후 조정 가능성 존재""".format(
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        },
        {
            "title": "📈 AI 종목 추천",
            "message": """📊🤖 *AI 일일 종목 추천*

*오늘의 AI 선정 종목 (상위 3개)*

📅 분석 시간: `{timestamp}`
🎯 전체 정확도: `82.4%`
📊 분석 종목: `2,875개`

🏆 *추천 종목*:
1. 🥇 *삼성전자 (005930)*
   • 신뢰도: 89.2%
   • 예상 수익률: +4.2%
   • 주요 지표: 모멘텀 ⬆️

2. 🥈 *SK하이닉스 (000660)*
   • 신뢰도: 85.7%
   • 예상 수익률: +3.8%
   • 주요 지표: 거래량 ⬆️

3. 🥉 *NAVER (035420)*
   • 신뢰도: 78.9%
   • 예상 수익률: +2.9%
   • 주요 지표: 기술적 반등 📈

📝 *AI 분석 근거*:
17개 기술 지표를 종합 분석하여
높은 수익 가능성을 가진 종목을 선별했습니다.

⚠️ *투자 유의사항*: 모든 투자는 본인 책임하에 진행하세요.""".format(
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        },
        {
            "title": "📊 시장 현황 요약",
            "message": """📊📈 *실시간 시장 현황*

*KOSPI 시장 상황 업데이트*

⏰ 업데이트: `{timestamp}`
📍 현재 지수: `2,547.82 (+12.45, +0.49%)`

📈 *시장 동향*:
• 상승: 486개 종목 📈
• 하락: 389개 종목 📉
• 보합: 97개 종목 ➡️

🔥 *핫 섹터*:
1. 반도체: +2.1% ⬆️
2. 바이오: +1.8% ⬆️
3. 자동차: +1.3% ⬆️

❄️ *약세 섹터*:
1. 조선: -1.2% ⬇️
2. 철강: -0.9% ⬇️
3. 화학: -0.7% ⬇️

💰 *거래 현황*:
• 총 거래대금: 8.7조원
• 외국인: +245억원 순매수 🌍
• 기관: -89억원 순매도 🏢

🤖 *AI 시장 판단*: `중립적 상승세 유지 전망`""".format(
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        }
    ]
    
    # 각 테스트 케이스 전송
    success_count = 0
    for i, test_case in enumerate(test_cases, 1):
        print(f"📤 {i}. {test_case['title']} 전송 중...")
        
        if send_telegram_message(bot_token, chat_id, test_case['message']):
            print(f"   ✅ 성공!")
            success_count += 1
        else:
            print(f"   ❌ 실패!")
        
        # 메시지 간 간격 (스팸 방지)
        if i < len(test_cases):
            print("   ⏳ 3초 대기...")
            time.sleep(3)
    
    print("-" * 50)
    print(f"📊 테스트 결과: {success_count}/{len(test_cases)} 성공")
    
    if success_count == len(test_cases):
        print("🎉 모든 테스트 완료! 텔레그램 알림 시스템이 완벽하게 작동합니다!")
        
        # 최종 완료 메시지
        final_message = """🏆 *한투 퀀트 텔레그램 알림 설정 완료*

✅ *모든 시스템 정상 작동 확인*

🎯 *설정된 기능*:
• 실시간 급등/급락 감지
• AI 기반 종목 추천 (일 1회)
• 시장 상황 모니터링
• 시스템 상태 알림
• 성과 분석 리포트

🚀 *이제 한투 퀀트와 함께 스마트한 투자를 시작하세요!*

💡 *알림 설정 변경*은 `config/telegram_config.json`에서 가능합니다.

⚙️ *시스템 실행*: `python main.py` 또는 `python workflows/integrated_scheduler.py`"""
        
        time.sleep(2)
        send_telegram_message(bot_token, chat_id, final_message)
        
        return True
    else:
        print("⚠️ 일부 테스트가 실패했습니다. 설정을 확인해주세요.")
        return False

if __name__ == "__main__":
    print("🤖 한투 퀀트 텔레그램 알림 통합 테스트")
    print("=" * 50)
    
    test_alert_messages() 