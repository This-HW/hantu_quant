# 백테스트 스크립트 사용 가이드

> Wave 3 Batch 3에서 구현된 백테스트 실행 스크립트 사용법

---

## 개요

백테스트 관련 3개의 CLI 스크립트가 제공됩니다:

1. **run_backtest.py** - 특정 기간 백테스트 실행
2. **run_walk_forward.py** - Walk-Forward Analysis 실행
3. **backtest_report.py** - 백테스트 결과 보고서 형식 변환

---

## 1. run_backtest.py

### 기본 사용법

```bash
python scripts/run_backtest.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31
```

### 주요 옵션

| 옵션                 | 설명                         | 기본값                      |
| -------------------- | ---------------------------- | --------------------------- |
| `--start-date`       | 시작일 (YYYY-MM-DD)          | 필수                        |
| `--end-date`         | 종료일 (YYYY-MM-DD)          | 필수                        |
| `--strategy`         | 전략명                       | selection                   |
| `--initial-capital`  | 초기 자본 (원)               | 10,000,000                  |
| `--stop-loss`        | 손절 비율                    | 0.03 (3%)                   |
| `--take-profit`      | 익절 비율                    | 0.08 (8%)                   |
| `--max-holding-days` | 최대 보유일                  | 10                          |
| `--output`           | 출력 파일 경로               | reports/backtest/result.txt |
| `--format`           | 보고서 형식 (text/json/html) | text                        |

### 사용 예제

```bash
# 1. 2024년 전체 백테스트 (기본 설정)
python scripts/run_backtest.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31

# 2. 초기 자본 5천만원으로 백테스트
python scripts/run_backtest.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --initial-capital 50000000

# 3. 손절/익절 비율 조정
python scripts/run_backtest.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --stop-loss 0.05 \
    --take-profit 0.10

# 4. JSON 형식으로 저장
python scripts/run_backtest.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --format json \
    --output reports/backtest/2024_result.json

# 5. HTML 보고서 생성
python scripts/run_backtest.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --format html \
    --output reports/backtest/2024_result.html
```

### 출력 예제

```
백테스트 실행 중...
기간: 2024-01-01 ~ 2024-12-31
================================================================================

================================================================================
                              백테스트 결과 요약
================================================================================

전략명: selection
기간: 2024-01-01 ~ 2024-12-31

[성과 지표]
  총 수익률:              +15.32%
  Sharpe Ratio:             1.45
  최대 손실폭:              -8.21%
  승률:                    58.5%

[거래 통계]
  총 거래 수:               120건
  승리 거래:                 70건
  손실 거래:                 50건
  평균 보유일:               7.5일

...

✅ 백테스트 완료
   상세 결과: reports/backtest/result.txt
```

---

## 2. run_walk_forward.py

### 기본 사용법

```bash
python scripts/run_walk_forward.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31
```

### 주요 옵션

| 옵션             | 설명                         | 기본값                          |
| ---------------- | ---------------------------- | ------------------------------- |
| `--start-date`   | 전체 분석 시작일             | 필수                            |
| `--end-date`     | 전체 분석 종료일             | 필수                            |
| `--train-window` | Train 윈도우 일수            | 180 (6개월)                     |
| `--test-window`  | Test 윈도우 일수             | 30 (1개월)                      |
| `--step`         | 윈도우 이동 일수             | 30                              |
| `--min-trades`   | 윈도우 최소 거래 수          | 20                              |
| `--purge-days`   | Train/Test 격리 기간         | 5                               |
| `--output`       | 출력 파일 경로               | reports/walk_forward/result.txt |
| `--format`       | 보고서 형식 (text/json/html) | text                            |

### 사용 예제

```bash
# 1. 기본 설정 (180일 train, 30일 test)
python scripts/run_walk_forward.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31

# 2. 윈도우 설정 커스터마이징 (120일 train, 20일 test, 20일 step)
python scripts/run_walk_forward.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --train-window 120 \
    --test-window 20 \
    --step 20

# 3. JSON 형식으로 저장
python scripts/run_walk_forward.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --format json \
    --output reports/walk_forward/2024_wf.json

# 4. 최소 거래 수 조정 (더 엄격한 검증)
python scripts/run_walk_forward.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --min-trades 50
```

### 출력 예제

```
Walk-Forward Analysis 실행 중...
기간: 2024-01-01 ~ 2024-12-31
Train: 180일, Test: 30일, Step: 30일
================================================================================

================================================================================
                            윈도우별 결과
================================================================================

[윈도우 1]
  Train: 2024-01-01 ~ 2024-06-29
  Test:  2024-07-05 ~ 2024-08-03
  Train 결과:
    - 거래수: 45건
    - 승률: 62.2%
    - 수익률: +18.5%
    - Sharpe: 1.52
  Test 결과:
    - 거래수: 8건
    - 승률: 50.0%
    - 수익률: +8.3%
    - Sharpe: 0.98
  Overfitting Ratio: 0.645

...

================================================================================
                     Walk-Forward Analysis 종합 결과
================================================================================

[윈도우 정보]
  전체 윈도우: 6개
  유효 윈도우: 5개
  Train: 180일
  Test: 30일
  Step: 30일

[평균 성과 - Train]
  평균 수익률:     +16.2%
  평균 Sharpe:      1.42

[평균 성과 - Test]
  평균 수익률:      +9.8%
  평균 Sharpe:      1.05

[과적합 분석]
  Overfitting Ratio:      0.739
  평가: ✅ 양호

[일관성 분석]
  Consistency Score:    0.0324
  평가: ✅ 안정적

✅ Walk-Forward Analysis 완료
   상세 결과: reports/walk_forward/result.txt
```

---

## 3. backtest_report.py

### 기본 사용법

```bash
python scripts/backtest_report.py \
    --input reports/backtest/2024_result.json \
    --format html
```

### 주요 옵션

| 옵션       | 설명                                       |
| ---------- | ------------------------------------------ |
| `--input`  | 입력 JSON 파일 경로 (필수)                 |
| `--format` | 출력 형식 (text/json/html, 필수)           |
| `--output` | 출력 파일 경로 (선택, 미지정 시 자동 생성) |

### 사용 예제

```bash
# 1. JSON → HTML 변환
python scripts/backtest_report.py \
    --input reports/backtest/2024_result.json \
    --format html \
    --output reports/backtest/2024_result.html

# 2. JSON → Text 변환
python scripts/backtest_report.py \
    --input reports/backtest/2024_result.json \
    --format text \
    --output reports/backtest/2024_result.txt

# 3. 출력 경로 자동 생성 (확장자만 변경)
python scripts/backtest_report.py \
    --input reports/backtest/2024_result.json \
    --format html
# → reports/backtest/2024_result.html 자동 생성
```

---

## 워크플로우 예제

### 1. 기본 백테스트 → HTML 보고서

```bash
# 1단계: 백테스트 실행 (JSON 저장)
python scripts/run_backtest.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --format json \
    --output reports/backtest/2024.json

# 2단계: HTML 보고서 생성
python scripts/backtest_report.py \
    --input reports/backtest/2024.json \
    --format html
```

### 2. Walk-Forward Analysis → JSON 저장

```bash
# Walk-Forward 실행 (JSON 저장)
python scripts/run_walk_forward.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --format json \
    --output reports/walk_forward/2024_wf.json
```

### 3. 다양한 파라미터 테스트

```bash
# 손절 3% vs 5% 비교
python scripts/run_backtest.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --stop-loss 0.03 \
    --output reports/backtest/sl_3pct.txt

python scripts/run_backtest.py \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --stop-loss 0.05 \
    --output reports/backtest/sl_5pct.txt
```

---

## 주의사항

### 1. 데이터 요구사항

백테스트 실행 전 다음 데이터가 필요합니다:

- `data/daily_selection/daily_selection_YYYYMMDD.json` 파일들

### 2. 실행 환경

가상환경 활성화 필요:

```bash
source venv/bin/activate
```

### 3. 출력 디렉토리

출력 디렉토리가 없으면 자동 생성됩니다:

- `reports/backtest/`
- `reports/walk_forward/`

---

## 트러블슈팅

### "데이터가 없습니다"

```bash
# 원인: 일일 선정 데이터 누락
# 해결: Phase 2 워크플로우 먼저 실행
python workflows/phase2_daily_selection.py
```

### "ModuleNotFoundError: numpy"

```bash
# 원인: 가상환경 미활성화
# 해결:
source venv/bin/activate
```

### "파일을 찾을 수 없습니다"

```bash
# 원인: 잘못된 입력 경로
# 해결: 경로 확인
ls -la reports/backtest/
```

---

## Walk-Forward 파라미터 가이드

`WalkForwardConfig` 주요 파라미터와 권장값:

| 파라미터            | 기본값 | 권장 범위          | 설명                                    |
| ------------------- | ------ | ------------------ | --------------------------------------- |
| `train_window_days` | 180    | 90~365             | 학습 윈도우. 최소 90일 이상 권장        |
| `test_window_days`  | 30     | 20~60              | 테스트 윈도우. train의 1/6~1/3이 적절   |
| `step_days`         | 30     | test_window와 동일 | 겹침 없이 진행하려면 test_window와 동일 |
| `min_train_trades`  | 20     | 15~50              | 통계적 유의성 위해 최소 15건 이상       |
| `purge_days`        | 5      | 3~10               | 보유 기간과 동일하게 설정 권장          |

**판정 기준**:

- Overfitting Ratio > 0.5: 양호 (Test가 Train의 50% 이상)
- Consistency Score < 0.05: 안정적 (Test 수익률 변동 낮음)

---

## 참고 문서

- **백테스트 시스템 설계**: `docs/planning/phase4/wave3-backtest-system.md`
- **P1 구현 계획**: `docs/design/p1-implementation-plan.md`
- **수익성 개선 로드맵**: `docs/analysis/profitability-improvement-roadmap.md`
- **알고리즘 개요**: `docs/ALGORITHMS_OVERVIEW.md`
- **백테스트 모듈**: `core/backtesting/`
- **기존 스크립트**: `scripts/run_p0_backtest.py`
