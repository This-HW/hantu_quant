# ML 자동 트리거 시스템 완성

## 📋 개요

B단계 ML 랭킹 시스템이 충분한 학습 데이터가 쌓이면 자동으로 시작되도록 하는 자동 트리거 시스템을 구현했습니다.

## 🎯 주요 기능

### 1. 데이터 조건 자동 체크
시스템은 매일 다음 조건들을 자동으로 체크합니다:

- **거래일 수**: 최소 60일의 거래 데이터
- **선정 기록**: 최소 50회의 종목 선정 기록
- **성과 기록**: 최소 30개의 완료된 거래 기록
- **승률**: 최소 45% (학습 가치가 있는 수준)

### 2. 진행률 추적
현재 ML 학습 준비 상태를 실시간으로 추적:
- 각 조건별 진행률 (%)
- 전체 진행률 (가중 평균)
- 예상 남은 기간 (일)

### 3. 자동 트리거
모든 조건이 충족되면 자동으로:
1. WorkflowStateManager에 B단계 시작 상태 저장
2. ML 학습 스크립트 실행 예약
3. 텔레그램 알림 전송

## 📁 파일 구조

```
core/
├── learning/
│   ├── __init__.py                  # 모듈 export 업데이트
│   └── auto_ml_trigger.py           # 자동 트리거 시스템 (NEW)
├── trading/
│   └── trade_journal.py             # get_all_trades() 메서드 추가
└── monitoring/
    └── __init__.py                  # ML 트리거 참조 추가

workflows/
└── integrated_scheduler.py          # ML 체크 스케줄 추가

tests/
└── test_ml_auto_trigger.py          # 테스트 스위트 (NEW)

data/
└── learning/
    └── ml_trigger_state.json        # 트리거 상태 저장 (자동 생성)
```

## 🔧 구현 세부사항

### AutoMLTrigger 클래스

**파일**: `core/learning/auto_ml_trigger.py`

**주요 메서드**:

```python
def check_and_trigger(force: bool = False) -> bool:
    """데이터 조건 체크 및 ML 학습 자동 트리거"""

def get_progress_to_ml() -> Dict:
    """ML 학습까지 진행률 조회"""

def _check_data_conditions() -> Tuple[bool, Dict]:
    """데이터 조건 체크"""
```

**조건 임계값**:
```python
self.min_trading_days = 60          # 최소 60일 거래 데이터
self.min_selection_records = 50     # 최소 50회 선정 기록
self.min_performance_records = 30   # 최소 30개 성과 기록
self.min_win_rate = 0.45            # 최소 승률 45%
```

### 스케줄러 통합

**파일**: `workflows/integrated_scheduler.py`

**스케줄**:
```python
# ML 학습 조건 체크: 매일 19:00
schedule.every().day.at("19:00").do(self._check_ml_trigger)
```

**실행 순서** (매일):
1. 06:00 - Phase 1 스크리닝
2. 자동 - Phase 2 일일 선정
3. 09:00 - 자동 매매 시작
4. 15:30 - 자동 매매 중지
5. 16:00 - 마감 후 정리
6. 17:00 - 일일 성과 분석
7. 18:30 - 강화된 적응형 학습
8. **19:00 - ML 학습 조건 체크 (NEW)** ⭐

### TradeJournal 개선

**파일**: `core/trading/trade_journal.py`

**추가된 메서드**:
```python
def get_all_trades(days: int = 365) -> List[Dict[str, Any]]:
    """전체 거래 내역 조회 (여러 날 통합)"""
```

이 메서드는 `data/trades/` 디렉토리의 모든 `trade_summary_*.json` 파일을 읽어서 완료된 거래 내역을 반환합니다.

## 📊 현재 상태 (테스트 결과)

```
전체 진행률: 63.3%

세부 진행률:
   - 거래일: 83.3% (50/60일)
   - 선정 기록: 100.0% (3691/50개) ✅
   - 성과 기록: 0.0% (0/30개)
   - 승률: 0.0% (0%/45%)

⏰ 예상 남은 기간: 약 10일
```

**분석**:
- 선정 기록은 이미 충분 (3,691개)
- 거래일 수는 83% 달성 (10일 더 필요)
- 성과 기록과 승률은 실제 매매가 시작되면 쌓임

## 🚀 사용 방법

### 1. 자동 실행 (스케줄러)

스케줄러를 실행하면 매일 19:00에 자동으로 체크:

```bash
python workflows/integrated_scheduler.py start
```

### 2. 수동 체크

진행률을 수동으로 확인하려면:

```python
from core.learning.auto_ml_trigger import get_auto_ml_trigger

trigger = get_auto_ml_trigger()
progress = trigger.get_progress_to_ml()

print(f"전체 진행률: {progress['overall_progress']:.1f}%")
print(f"예상 남은 기간: {progress['estimated_days_remaining']}일")
```

### 3. 강제 트리거 (테스트용)

조건 무시하고 강제로 트리거:

```python
from core.learning.auto_ml_trigger import get_auto_ml_trigger

trigger = get_auto_ml_trigger()
success = trigger.check_and_trigger(force=True)
```

### 4. 테스트 실행

전체 시스템 테스트:

```bash
python tests/test_ml_auto_trigger.py
```

## 📱 텔레그램 알림

조건이 충족되어 ML 학습이 시작되면 다음 알림이 전송됩니다:

```
🤖 ML 학습 자동 시작

✅ 학습 조건 충족
• 거래일 수: 60일
• 선정 기록: 3691개
• 성과 기록: 30개
• 현재 승률: 50.0%
• 데이터 품질: 85.0점

🚀 B단계 ML 랭킹 시스템이 자동으로 시작됩니다.
학습 완료 시 다시 알림을 보내드립니다.
```

## 🔄 워크플로우 통합

ML 트리거는 기존 워크플로우와 완벽하게 통합됩니다:

```
Stage A (완료) → Stage D (완료) → Stage C (완료)
                                          ↓
                                    데이터 축적
                                          ↓
                              ML 조건 체크 (매일 19:00)
                                          ↓
                                    조건 충족?
                                       /    \
                                     Yes     No
                                      ↓       ↓
                              Stage B 자동 시작  계속 대기
                                      ↓
                              ML 랭킹 시스템
```

## 📈 예상 타임라인

현재 상태 기준:
- **10일 후**: 거래일 수 조건 충족 (60일)
- **실제 매매 시작 후**: 성과 기록 및 승률 조건 충족
- **예상 B단계 시작**: 약 30-40일 후 (실제 매매 데이터 30건 이상 필요)

## ⚙️ 설정 변경

필요시 조건을 조정할 수 있습니다:

**파일**: `core/learning/auto_ml_trigger.py`

```python
# 현재 설정
self.min_trading_days = 60          # 거래일 수
self.min_selection_records = 50     # 선정 기록
self.min_performance_records = 30   # 성과 기록
self.min_win_rate = 0.45            # 승률

# 더 빨리 트리거하려면 값을 낮추기
# 더 많은 데이터를 원하면 값을 높이기
```

## 🧪 테스트 결과

```
============================================================
테스트 결과 요약
============================================================
✅ 통과 - 초기화
✅ 통과 - 데이터 조건 체크 (미충족 상태 정상 감지)
✅ 통과 - 진행률 조회
✅ 통과 - 자동 트리거 시뮬레이션
```

모든 핵심 기능이 정상 작동합니다.

## 🎯 다음 단계

1. **실제 매매 시작**: 성과 데이터 축적 시작
2. **데이터 모니터링**: 매일 진행률 확인
3. **조건 충족 대기**: 약 30-40일 후 자동 트리거 예상
4. **B단계 실행**: ML 랭킹 시스템 자동 시작

## 📝 상태 파일

트리거 상태는 다음 파일에 저장됩니다:

```
data/learning/ml_trigger_state.json
```

**구조**:
```json
{
  "last_check_date": "2025-10-01",
  "ml_training_triggered": false,
  "ml_training_date": null,
  "next_check_date": "2025-10-02",
  "conditions": {
    "trading_days": 50,
    "selection_records": 3691,
    "performance_records": 0,
    "current_win_rate": 0.0,
    "data_quality_score": 63.3,
    "conditions_met": false
  }
}
```

## ✅ 완료 항목

- [x] AutoMLTrigger 클래스 구현
- [x] 데이터 조건 체크 로직
- [x] 진행률 추적 시스템
- [x] 자동 트리거 메커니즘
- [x] 스케줄러 통합 (매일 19:00)
- [x] TradeJournal.get_all_trades() 구현
- [x] 텔레그램 알림 연동
- [x] WorkflowStateManager 연동
- [x] 테스트 스위트 작성
- [x] 상태 파일 관리

## 🎉 결론

ML 자동 트리거 시스템이 완전히 구현되어 통합 스케줄러에 통합되었습니다. 시스템은 매일 자동으로 학습 조건을 체크하며, 충분한 데이터가 쌓이면 B단계 ML 랭킹 시스템을 자동으로 시작합니다.

이제 시스템은 완전히 자율적으로 작동하며, 사용자의 개입 없이도 적절한 시점에 ML 학습을 시작할 수 있습니다.
