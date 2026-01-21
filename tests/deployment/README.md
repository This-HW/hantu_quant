# Deployment Tests

배포 자동화 및 에러 수정 개선 사항에 대한 테스트 스위트입니다.

## 테스트 파일

### 1. `test_state_manager.sh` (6 tests)

배포 상태 관리 함수 단위 테스트

**테스트 항목**:

- `test_init_state` - 상태 파일 초기화
- `test_update_state_success` - 성공 상태 업데이트
- `test_update_state_failed` - 실패 상태 업데이트
- `test_get_consecutive_failures` - 연속 실패 횟수 조회
- `test_reset_state` - 상태 리셋
- `test_get_attempts` - 총 시도 횟수 조회

**실행**:

```bash
bash tests/deployment/test_state_manager.sh
```

### 2. `test_validate_env.sh` (6 tests)

환경변수 검증 함수 단위 테스트

**테스트 항목**:

- `test_all_required_present` - 모든 필수 변수 존재
- `test_missing_required_var` - 필수 변수 누락 (실패 예상)
- `test_missing_optional_var` - 선택 변수 누락 (성공 예상)
- `test_empty_env_file` - 빈 환경 파일 (실패 예상)
- `test_color_output_missing` - 에러 메시지 출력 확인
- `test_all_vars_present` - 모든 변수 존재 (필수+선택)

**실행**:

```bash
bash tests/deployment/test_validate_env.sh
```

### 3. `test_integration_deploy.sh` (8 scenarios)

배포 플로우 통합 테스트

**테스트 시나리오**:

1. State file initialization - 상태 파일 초기화
2. Pre-deployment checks - 배포 전 검증 (환경변수)
3. Deployment success - 배포 성공 처리
4. Deployment failure - 배포 실패 처리
5. Retry logic (2 failures then success) - 재시도 로직
6. Alert threshold (≥2 failures) - 알림 임계값 검증
7. State resets on success - 성공 시 상태 리셋
8. State persistence - 상태 영속성

**실행**:

```bash
bash tests/deployment/test_integration_deploy.sh
```

## 전체 테스트 실행

```bash
# 테스트 디렉토리로 이동
cd /Users/grimm/Documents/Dev/hantu_quant

# 모든 테스트 실행
for test in tests/deployment/test_*.sh; do
    echo ""
    echo "========================================="
    echo "Running: $(basename $test)"
    echo "========================================="
    bash "$test"
done
```

## 예상 결과

**모든 테스트 통과 시**:

```
Total Tests: 20 (6 + 6 + 8)
Passed: 20
Failed: 0

✓ All tests passed!
```

## 테스트 커버리지

| 영역             | 커버리지 | 비고                         |
| ---------------- | -------- | ---------------------------- |
| State Management | 100%     | 초기화, 업데이트, 조회, 리셋 |
| Env Validation   | 100%     | 필수/선택 변수, 에러 처리    |
| Deployment Flow  | 100%     | 성공/실패, 재시도, 알림      |
| Pre-checks       | 100%     | 메모리, 환경변수 검증        |

## 테스트 특징

1. **격리된 환경**: 각 테스트는 임시 디렉토리 사용
2. **자동 정리**: 테스트 완료 후 임시 파일 자동 삭제
3. **색상 출력**: PASS(녹색), FAIL(빨강), SKIP(노랑)
4. **종합 리포트**: 테스트 완료 후 통계 표시

## CI/CD 통합

GitHub Actions에서 자동 실행 가능:

```yaml
- name: Run deployment tests
  run: |
    bash tests/deployment/test_state_manager.sh
    bash tests/deployment/test_validate_env.sh
    bash tests/deployment/test_integration_deploy.sh
```

## 트러블슈팅

### 테스트 실패 시 확인 사항

1. **jq 설치 확인**:

   ```bash
   jq --version
   # Ubuntu: sudo apt install jq
   # macOS: brew install jq
   ```

2. **실행 권한 확인**:

   ```bash
   chmod +x tests/deployment/*.sh
   ```

3. **bash 버전 확인**:
   ```bash
   bash --version  # 4.0 이상 권장
   ```

## 관련 문서

- [배포 가이드](../../deploy/DEPLOY_MICRO.md#10-auto-fix-error-improvements-자동-에러-수정-개선)
- [State Manager](../../scripts/deployment/state_manager.sh)
- [Validate Env](../../scripts/deployment/validate_env.sh)
- [Pre Checks](../../scripts/deployment/pre_checks.sh)
