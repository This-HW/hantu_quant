# 한투 퀀트 개발 가이드라인

## 코딩 표준

### 네이밍 규칙
- **클래스명**: PascalCase (예: `StockScreener`, `WatchlistManager`)
- **함수명**: snake_case (예: `analyze_stock`, `update_watchlist`)
- **변수명**: snake_case (예: `stock_code`, `price_data`)
- **상수명**: UPPER_SNAKE_CASE (예: `MAX_STOCKS`, `DEFAULT_TIMEOUT`)
- **파라미터 변수**: `p_` 접두사 (예: `p_stock_code`, `p_start_date`)
- **내부 변수**: `_v_` 접두사 (예: `_v_result`, `_v_temp_data`)

### 파일 구조
```python
"""
모듈 설명
- 주요 기능 1
- 주요 기능 2
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from core.config.settings import Settings
from core.utils.log_utils import get_logger

logger = get_logger(__name__)

class ClassName:
    """클래스 설명"""
    
    def __init__(self, p_param: str):
        """초기화 메서드"""
        self._v_param = p_param
        
    def method_name(self, p_input: str) -> str:
        """메서드 설명
        
        Args:
            p_input: 입력 파라미터 설명
            
        Returns:
            반환값 설명
            
        Raises:
            ValueError: 에러 조건 설명
        """
        try:
            _v_result = self._process_input(p_input)
            logger.info(f"처리 완료: {p_input}")
            return _v_result
        except Exception as e:
            logger.error(f"처리 실패: {e}")
            raise
```

### 로깅 규칙
- 모든 모듈에서 `core.utils.log_utils.get_logger` 사용
- 중요한 작업 시작/완료 시 INFO 레벨 로그
- 오류 발생 시 ERROR 레벨 로그
- 디버깅 정보는 DEBUG 레벨 로그
- 민감 정보는 마스킹 처리

### 예외 처리
```python
try:
    # 위험한 작업
    _v_result = risky_operation()
except SpecificException as e:
    logger.error(f"특정 오류 발생: {e}")
    # 복구 로직 또는 재시도
    raise
except Exception as e:
    logger.error(f"예상치 못한 오류: {e}")
    raise
```

## 데이터 관리 규칙

### 데이터 저장 구조
```
data/
├── watchlist/
│   ├── watchlist.json          # 감시 리스트
│   ├── screening_results.json  # 스크리닝 결과
│   └── evaluation_history.json # 평가 이력
├── daily_selection/
│   ├── daily_list_YYYYMMDD.json # 일일 매매 리스트
│   ├── price_analysis.json      # 가격 분석 결과
│   └── selection_criteria.json  # 선정 기준
├── intraday/
│   ├── minute_data_YYYYMMDD.json # 분 단위 데이터
│   ├── trading_signals.json     # 매매 신호
│   └── order_history.json       # 주문 이력
├── learning/
│   ├── daily_analysis.json      # 일일 분석 결과
│   ├── pattern_data.json        # 패턴 데이터
│   └── optimization_results.json # 최적화 결과
└── market_events/
    ├── events_YYYYMMDD.json     # 시장 이벤트
    ├── news_analysis.json       # 뉴스 분석
    └── market_scan_results.json # 시장 스캔 결과
```

### JSON 데이터 형식
```python
# 표준 데이터 형식
{
    "timestamp": "2024-01-01T09:00:00",
    "version": "1.0.0",
    "data": {
        # 실제 데이터
    },
    "metadata": {
        "source": "module_name",
        "processed_by": "function_name",
        "parameters": {}
    }
}
```

## API 사용 규칙

### API 호출 패턴
```python
from core.config.api_config import APIConfig

class SomeService:
    def __init__(self):
        self.api_config = APIConfig()
        
    def make_api_call(self, p_endpoint: str, p_params: dict) -> dict:
        """API 호출 표준 패턴"""
        try:
            # 레이트 리미팅 적용
            self.api_config.apply_rate_limit()
            
            # API 호출
            _v_response = self.api_config.rest_client.get(
                p_endpoint, 
                params=p_params,
                headers=self.api_config.get_headers()
            )
            
            logger.info(f"API 호출 성공: {p_endpoint}")
            return _v_response.json()
            
        except Exception as e:
            logger.error(f"API 호출 실패: {e}")
            raise
```

### 토큰 관리
- 토큰 만료 시 자동 갱신
- 갱신 실패 시 재시도 로직
- 토큰 정보는 data/token/ 디렉토리에만 저장

## 테스트 규칙

### 단위 테스트
```python
import unittest
from unittest.mock import Mock, patch

class TestStockScreener(unittest.TestCase):
    def setUp(self):
        self.screener = StockScreener()
        
    def test_screen_by_fundamentals(self):
        """재무제표 기반 스크리닝 테스트"""
        # Given
        _v_mock_data = {"stock_code": "005930", "per": 10.5}
        
        # When
        _v_result = self.screener.screen_by_fundamentals(_v_mock_data)
        
        # Then
        self.assertIsNotNone(_v_result)
        self.assertIn("005930", _v_result)
```

### 통합 테스트
- 각 Phase 완료 시 통합 테스트 실행
- 모의투자 환경에서 실제 API 호출 테스트
- 성능 및 안정성 검증

## 보안 규칙

### 민감 정보 처리
```python
# 올바른 예
api_key = os.getenv("KIS_APP_KEY")
if not api_key:
    raise ValueError("API 키가 설정되지 않았습니다")

# 잘못된 예 - 절대 금지
api_key = "your_api_key_here"  # 하드코딩 금지
```

### 로깅 시 마스킹
```python
# 민감 정보 마스킹
logger.info(f"API 호출: {endpoint}, 키: {api_key[:4]}***")
```

### 환경 변수 관리
- 모든 민감 정보는 .env 파일에 저장
- .env.example에는 예시 값만 포함
- 프로덕션 환경에서는 시스템 환경 변수 사용

## 성능 최적화 규칙

### 데이터 처리
- 대용량 데이터는 청크 단위로 처리
- 메모리 사용량 모니터링
- 불필요한 데이터 로딩 방지

### API 호출 최적화
- 배치 처리 가능한 API는 일괄 호출
- 캐싱 활용으로 중복 호출 방지
- 비동기 처리 고려

### 데이터베이스 최적화
- 인덱스 활용
- 쿼리 최적화
- 연결 풀 사용

## 모니터링 및 알림

### 시스템 모니터링
- 메모리 사용량 모니터링
- API 호출 성공률 추적
- 거래 성과 실시간 추적

### 알림 시스템
- 중요 이벤트 발생 시 알림
- 오류 발생 시 즉시 알림
- 일일 성과 리포트 자동 발송

## 배포 및 운영

### 배포 전 체크리스트
- [ ] 모든 테스트 통과
- [ ] 코드 리뷰 완료
- [ ] 문서 업데이트
- [ ] 백업 및 롤백 계획 수립

### 운영 중 모니터링
- 로그 레벨 적절히 설정
- 성능 지표 정기 확인
- 보안 업데이트 적시 적용 