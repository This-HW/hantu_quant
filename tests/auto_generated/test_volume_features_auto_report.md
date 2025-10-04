# 자동 테스트 생성 리포트

**소스 파일**: `core/learning/features/volume_features.py`
**테스트 파일**: `tests/auto_generated/test_volume_features_auto.py`
**생성 시간**: 2025-07-26 21:53:26

## 📊 분석 결과
- **총 함수 수**: 15개
- **평균 복잡도**: 3.7
- **총 엣지 케이스**: 95개

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
- **반환 타입**: VolumeFeatures

### `_calculate_volume_price_correlation`
- **인자**: 2개
- **복잡도**: 4
- **엣지 케이스**: 7개
- **반환 타입**: float

### `_calculate_volume_price_divergence`
- **인자**: 2개
- **복잡도**: 4
- **엣지 케이스**: 7개
- **반환 타입**: float

### `_calculate_volume_momentum_score`
- **인자**: 2개
- **복잡도**: 7
- **엣지 케이스**: 7개
- **반환 타입**: float

### `_calculate_relative_volume_strength`
- **인자**: 2개
- **복잡도**: 8
- **엣지 케이스**: 7개
- **반환 타입**: float

### `_calculate_volume_rank_percentile`
- **인자**: 2개
- **복잡도**: 2
- **엣지 케이스**: 7개
- **반환 타입**: float

### `_calculate_volume_intensity`
- **인자**: 2개
- **복잡도**: 6
- **엣지 케이스**: 7개
- **반환 타입**: float

### `_calculate_volume_cluster_count`
- **인자**: 2개
- **복잡도**: 2
- **엣지 케이스**: 6개
- **반환 타입**: float

### `_calculate_volume_anomaly_score`
- **인자**: 2개
- **복잡도**: 8
- **엣지 케이스**: 6개
- **반환 타입**: float

### `extract_features_from_stock_data`
- **인자**: 2개
- **복잡도**: 3
- **엣지 케이스**: 7개
- **반환 타입**: VolumeFeatures

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
