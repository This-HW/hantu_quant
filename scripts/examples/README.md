# KIS Minimal Examples (examples_llm 스타일)

- chk_inquire_price.py: 현재가 조회
- chk_inquire_daily_price.py: 최근 일봉 조회
- chk_inquire_balance.py: 잔고 조회

실행 예시:

- python3 scripts/examples/chk_inquire_price.py
- STOCK_CODE=005930 python3 scripts/examples/chk_inquire_daily_price.py
- python3 scripts/examples/chk_inquire_balance.py

사전 요구:
- .env에 KIS 앱키/시크릿/계좌/환경 설정
- 최초 실행 시 토큰 자동 발급(저장 파일 경로는 core/config/api_config.py 기준)
