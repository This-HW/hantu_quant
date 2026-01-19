"""
APIConfig 클래스 사용 예제
"""

import logging
import sys
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# 프로젝트 루트 경로를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config.api_config import APIConfig  # noqa: E402

def main():
    """APIConfig 클래스 사용 예제 메인 함수"""
    # 1. APIConfig 싱글톤 인스턴스 생성
    api_config = APIConfig()
    
    # 2. 현재 환경 정보 출력
    print(f"현재 설정된 환경: {'모의투자' if api_config.server == 'virtual' else '실제투자'}")
    print(f"API 엔드포인트: {api_config.base_url}")
    print(f"WebSocket 엔드포인트: {api_config.ws_url}")
    
    # 3. 토큰 갱신
    print("\n토큰 갱신 중...")
    if api_config.refresh_token():
        print("토큰 갱신 성공")
        
        # 토큰 정보 출력 (실제 서비스에서는 출력하지 않는 것이 안전)
        if api_config.token_expired_at:
            print(f"토큰 만료 시간: {api_config.token_expired_at.isoformat()}")
    else:
        print("토큰 갱신 실패")
        return
    
    # 4. API 요청 헤더 생성
    headers = api_config.get_headers()
    print("\nAPI 요청 헤더 (민감 정보 마스킹):")
    safe_headers = headers.copy()
    safe_headers['authorization'] = '***MASKED***'
    safe_headers['appkey'] = '***MASKED***'
    safe_headers['appsecret'] = '***MASKED***'
    for key, value in safe_headers.items():
        print(f"  {key}: {value}")
    
    # 5. API 호출 제한 테스트
    print("\nAPI 호출 제한 테스트...")
    for i in range(10):
        print(f"API 호출 {i+1}번째...")
        api_config.apply_rate_limit()
    print("API 호출 제한 테스트 완료")
    
    # 6. 토큰 유효성 검사
    print("\n토큰 유효성 검사 결과:", "유효함" if api_config.validate_token() else "유효하지 않음")
    
    print("\n모든 테스트 완료")

if __name__ == "__main__":
    main() 