# API 통합 워크플로우

## 작업 전 준비
1. 환경 설정 확인
   ```
   python scripts/manage.py setup
   ```

2. 토큰 파일 초기화 (필요시)
   ```
   python scripts/manage.py reset-tokens
   ```

## 참조할 파일
- core/config/settings.py
- core/config/api_config.py
- core/api/kis_api.py
- core/api/rest_client.py
- core/api/websocket_client.py

## 작업 단계
1. API 설정 확인
   - .env.example 파일을 기준으로 필요한 환경변수 설정
   - API 엔드포인트 및 서버 설정 검토

2. API 클라이언트 구현/수정
   - KISRestClient 클래스 수정 (필요한 엔드포인트 추가)
   - 응답 처리 및 에러 핸들링 구현
   - API 요청 레이트 리밋 준수 확인

3. WebSocket 클라이언트 구현/수정
   - 실시간 데이터 구독 설정
   - 메시지 처리 핸들러 등록
   - 연결 안정성 확보

4. 테스트
   - 잔고 조회 테스트
   - 실시간 데이터 수신 테스트
   - 토큰 갱신 테스트

## 주의사항
- API 키 노출 방지
- 로그에 민감 정보 마스킹 확인
- 오류 발생 시 적절한 재시도 로직 구현 