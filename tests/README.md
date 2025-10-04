# 🧪 테스트 가이드

한투 퀀트 트레이딩 시스템의 테스트 코드 및 실행 가이드입니다.

## 📁 테스트 구조

### [integration/](integration/) - 통합 테스트
전체 시스템 또는 여러 모듈 간의 통합 테스트

**주요 테스트 파일:**
- `test_auto_trading.py` - 자동 매매 시스템 통합 테스트
- `test_full_integration.py` - 전체 시스템 통합 테스트
- `test_health_check.py` - 시스템 헬스 체크 테스트
- `test_integrated_monitoring.py` - 통합 모니터링 테스트

### [manual/](manual/) - 수동 테스트
디버깅 및 개발 중 수동 확인용 테스트

**주요 테스트 파일:**
- `test_enhanced_learning_system.py` - 학습 시스템 수동 테스트
- `test_enhanced_screening.py` - 스크리닝 시스템 수동 테스트
- `test_manual_trading.py` - 수동 매매 테스트
- `test_trading_debug.py` - 매매 디버깅 테스트

### 기타 테스트
루트의 `tests/` 폴더에 있는 다른 테스트들:
- Phase별 테스트 (`test_phase1.py`, `test_phase2.py`)
- API 테스트
- 개별 모듈 단위 테스트

## 🚀 테스트 실행 방법

### 전체 테스트 실행

```bash
# pytest를 사용한 전체 테스트
pytest tests/

# 상세 출력과 함께 실행
pytest tests/ -v

# 특정 카테고리만 실행
pytest tests/integration/ -v
pytest tests/manual/ -v
```

### 개별 테스트 실행

```bash
# 통합 테스트
python tests/integration/test_auto_trading.py
python tests/integration/test_full_integration.py
python tests/integration/test_health_check.py
python tests/integration/test_integrated_monitoring.py

# 수동 테스트
python tests/manual/test_enhanced_learning_system.py
python tests/manual/test_enhanced_screening.py
python tests/manual/test_manual_trading.py
python tests/manual/test_trading_debug.py
```

### Phase별 테스트

```bash
# Phase 1: 종목 스크리닝 테스트
python tests/test_phase1.py

# Phase 2: 일일 선정 테스트
python tests/test_phase2.py
```

## 📊 테스트 환경

### 환경 변수 설정

테스트 실행 전 `.env` 파일 확인:
```bash
# 모의투자 환경 사용 권장
SERVER=virtual
APP_KEY=your_virtual_app_key
APP_SECRET=your_virtual_app_secret
ACCOUNT_NUMBER=your_virtual_account
```

### 데이터 준비

일부 테스트는 실제 데이터가 필요합니다:
```bash
# 스크리닝 데이터 생성
python workflows/phase1_watchlist.py screen

# 일일 선정 데이터 생성
python workflows/phase2_daily_selection.py update
```

## ⚠️ 테스트 주의사항

### 1. 모의투자 환경 사용
- **실제 계좌 사용 금지**: 테스트는 항상 모의투자 환경(`SERVER=virtual`)에서 실행
- 실전 투자 전 충분한 모의투자 테스트 필요

### 2. API 호출 제한
- 한국투자증권 API는 초당 호출 횟수 제한 있음
- 대량 테스트 시 시간 간격 고려

### 3. 시장 시간
- 일부 테스트는 장 시간 중에만 정상 작동
- 장 외 시간 테스트 시 모의 데이터 사용

## 🔍 테스트 커버리지

### 커버리지 확인

```bash
# 커버리지 측정
pytest tests/ --cov=core --cov=workflows --cov-report=html

# 커버리지 리포트 확인
open htmlcov/index.html
```

## 🐛 디버깅

### 로그 확인

```bash
# 테스트 실행 로그
tail -f logs/$(date +%Y%m%d).log

# pytest 상세 출력
pytest tests/ -v -s  # -s 옵션으로 print 출력 확인
```

### 특정 테스트만 실행

```bash
# 특정 테스트 함수만 실행
pytest tests/integration/test_auto_trading.py::test_function_name -v

# 패턴 매칭
pytest tests/ -k "test_screening" -v
```

## 📝 테스트 작성 규칙

### 1. 파일 위치
- 통합 테스트 → `tests/integration/`
- 수동/디버그 테스트 → `tests/manual/`
- 단위 테스트 → `tests/unit/` (추후 추가)

### 2. 파일명 규칙
- `test_` 접두사 필수: `test_example.py`
- 명확하고 설명적인 이름 사용
- 소문자와 언더스코어 사용

### 3. 테스트 함수 규칙
```python
def test_example_function():
    """테스트 함수는 test_ 접두사 필수"""
    # Arrange (준비)
    expected = "expected_value"

    # Act (실행)
    result = function_to_test()

    # Assert (검증)
    assert result == expected
```

### 4. 테스트 클래스 규칙
```python
class TestExampleClass:
    """테스트 클래스는 Test 접두사 필수"""

    def setup_method(self):
        """각 테스트 전 실행"""
        pass

    def teardown_method(self):
        """각 테스트 후 실행"""
        pass

    def test_example(self):
        """개별 테스트 메서드"""
        assert True
```

### 5. Mock 사용
외부 API 호출이 필요한 경우 mock 사용 권장:
```python
from unittest.mock import Mock, patch

@patch('core.api.kis_api.KISApi.get_current_price')
def test_with_mock(mock_get_price):
    mock_get_price.return_value = 50000
    # 테스트 코드
```

## 📈 CI/CD 통합

### GitHub Actions (추후 추가)
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: pytest tests/
```

## 🔗 관련 링크
- [메인 README](../README.md) - 프로젝트 메인 페이지
- [스크립트 가이드](../scripts/README.md) - 스크립트 사용법
- [문서 인덱스](../docs/README.md) - 전체 문서 목록
- [코드 리뷰 보고서](../docs/reports/CODE_REVIEW_REPORT.md) - 코드 품질 체크리스트
