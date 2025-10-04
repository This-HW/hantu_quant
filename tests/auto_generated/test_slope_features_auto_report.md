# 자동 테스트 생성 리포트

**소스 파일**: `core/learning/features/slope_features.py`
**테스트 파일**: `tests/auto_generated/test_slope_features_auto.py`
**생성 시간**: 2025-07-26 21:53:26

## 📊 분석 결과
- **총 함수 수**: 13개
- **평균 복잡도**: 3.5
- **총 엣지 케이스**: 86개

## 🔍 함수별 상세
### `to_dict`
- **인자**: 1개
- **복잡도**: 1
- **엣지 케이스**: 5개
- **반환 타입**: Dict[str, float]

### `__init__`
- **인자**: 1개
- **복잡도**: 1
- **엣지 케이스**: 5개
- **반환 타입**: 미지정

### `extract_features`
- **인자**: 2개
- **복잡도**: 4
- **엣지 케이스**: 7개
- **반환 타입**: SlopeFeatures

### `_calculate_price_slope`
- **인자**: 3개
- **복잡도**: 3
- **엣지 케이스**: 8개
- **반환 타입**: float

### `_calculate_ma_slope`
- **인자**: 4개
- **복잡도**: 4
- **엣지 케이스**: 9개
- **반환 타입**: float

### `_calculate_slope_acceleration`
- **인자**: 2개
- **복잡도**: 4
- **엣지 케이스**: 7개
- **반환 타입**: float

### `_check_trend_consistency`
- **인자**: 2개
- **복잡도**: 8
- **엣지 케이스**: 7개
- **반환 타입**: float

### `_calculate_slope_angle`
- **인자**: 2개
- **복잡도**: 2
- **엣지 케이스**: 7개
- **반환 타입**: float

### `_get_slope_strength_score`
- **인자**: 2개
- **복잡도**: 10
- **엣지 케이스**: 7개
- **반환 타입**: float

### `extract_features_from_stock_data`
- **인자**: 2개
- **복잡도**: 3
- **엣지 케이스**: 7개
- **반환 타입**: SlopeFeatures

### `_generate_ohlcv_data`
- **인자**: 2개
- **복잡도**: 4
- **엣지 케이스**: 7개
- **반환 타입**: Optional[pd.DataFrame]

### `get_feature_names`
- **인자**: 1개
- **복잡도**: 1
- **엣지 케이스**: 5개
- **반환 타입**: List[str]

### `get_feature_descriptions`
- **인자**: 1개
- **복잡도**: 1
- **엣지 케이스**: 5개
- **반환 타입**: Dict[str, str]
