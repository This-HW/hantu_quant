# 배치 1: StockScreener Validator 통합 완료

## 작업 요약

StockScreener에 ScreeningValidator를 통합하여 데이터 품질 검증 기능을 추가했습니다.

## 변경 사항

### 1. Import 추가 (Line 22)

```python
from core.watchlist.validator import ScreeningValidator
```

### 2. 초기화 메서드 (Line 78)

```python
# 배치 1: 검증기 인스턴스 추가
self._validator = ScreeningValidator()
```

### 3. 필드명 매핑 함수 추가 (Line 748-767)

validator가 기대하는 필드명으로 변환하는 헬퍼 함수:

```python
def _map_fields_for_validation(self, stock_data: Dict) -> Dict:
    """validator가 기대하는 필드명으로 매핑"""
    return {
        'code': stock_data.get('stock_code', ''),
        'name': stock_data.get('stock_name', ''),
        'price': stock_data.get('current_price', 0),
        'volume': stock_data.get('volume', 0),
        'market_cap': stock_data.get('market_cap', 0),
        'per': stock_data.get('per', 0),
        'pbr': stock_data.get('pbr', 0),
        'roe': stock_data.get('roe', 0),
    }
```

**해결한 문제:**

- validator: `name`, `price`, `volume`, `market_cap` 기대
- stock_screener: `stock_name`, `current_price` 사용
- → 매핑 함수로 필드명 불일치 해결

### 4. comprehensive_screening() 검증 로직 통합 (Line 789-815)

```python
# 배치 1: 데이터 검증
_v_mapped_data = self._map_fields_for_validation(_v_stock_data)
_v_validation_result = self._validator.validate_stock_data(
    _v_stock_code, _v_mapped_data
)

if not _v_validation_result.is_valid:
    _v_validation_failed_count += 1
    self._logger.warning(
        f"종목 {_v_stock_code} 검증 실패 (점수: {_v_validation_result.score:.2f})",
        extra={
            'issues': _v_validation_result.issues,
            'warnings': _v_validation_result.warnings,
            'stock_code': _v_stock_code
        }
    )
    continue  # 검증 실패 시 스크리닝 건너뜀

# 검증 경고가 있으면 로깅
if _v_validation_result.warnings:
    self._logger.info(
        f"종목 {_v_stock_code} 검증 경고",
        extra={
            'warnings': _v_validation_result.warnings,
            'quality_score': _v_validation_result.score
        }
    )
```

### 5. 검증 결과 메타데이터 추가 (Line 872-875)

```python
"validation": {
    "quality_score": _v_validation_result.score,
    "warnings": _v_validation_result.warnings,
},
```

### 6. 최종 로깅 강화 (Line 893-896)

```python
self._logger.info(
    f"스크리닝 완료: {len(_v_results)}개 종목 처리 "
    f"(검증 실패: {_v_validation_failed_count}개)"
)
```

## 검증 효과

### Before

- 데이터 품질 검증 없음
- 비정상 데이터로 스크리닝 실행
- 결과 신뢰도 불확실

### After

- 5단계 검증 자동 실행:
  1. 필수 필드 검증 (name, price, volume, market_cap)
  2. 데이터 타입 검증 (숫자 필드 등)
  3. 값 범위 검증 (가격, 거래량, 재무 비율)
  4. 논리적 일관성 검증 (시가총액 vs 가격)
  5. 이상치 검증 (극단값 탐지)

- 검증 실패 종목은 스크리닝 건너뜀
- 검증 경고는 로그에 기록
- 검증 품질 점수 (0.0~1.0) 제공
- 최소 품질 점수 0.6 미만 시 실패 처리

## 로그 예시

### 검증 실패 시

```
WARNING: 종목 005930 검증 실패 (점수: 0.45)
  issues: ["필수 필드 누락: ['market_cap']"]
  warnings: ["매우 높은 가격: 1,000,000원"]
```

### 검증 경고 시

```
INFO: 종목 005930 검증 경고
  warnings: ["극단적 PER: 150"]
  quality_score: 0.75
```

### 최종 요약

```
INFO: 스크리닝 완료: 245개 종목 처리 (검증 실패: 12개)
```

## 다음 배치 작업

- 배치 2: DailyUpdater 통합
- 배치 3: WatchlistManager 통합
- 배치 4: 통합 테스트

## 참고

- validator.py: `/Users/grimm/Documents/Dev/hantu_quant/core/watchlist/validator.py`
- stock_screener.py: `/Users/grimm/Documents/Dev/hantu_quant/core/watchlist/stock_screener.py`
- 검증 규칙: Dexter 자가 검증 패턴 참고

## 검증 완료

- Syntax Check: PASS (py_compile)
- Import Chain: 확인 완료
- Field Mapping: 8개 필드 매핑 완료
- Error Handling: exc_info=True 적용
