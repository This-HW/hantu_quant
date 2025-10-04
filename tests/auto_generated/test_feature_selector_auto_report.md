# 자동 테스트 생성 리포트

**소스 파일**: `core/learning/features/feature_selector.py`
**테스트 파일**: `tests/auto_generated/test_feature_selector_auto.py`
**생성 시간**: 2025-07-26 21:53:26

## 📊 분석 결과
- **총 함수 수**: 13개
- **평균 복잡도**: 3.2
- **총 엣지 케이스**: 87개

## 🔍 함수별 상세
### `to_dict`
- **인자**: 1개
- **복잡도**: 1
- **엣지 케이스**: 5개
- **반환 타입**: Dict[str, float]

### `to_array`
- **인자**: 1개
- **복잡도**: 1
- **엣지 케이스**: 5개
- **반환 타입**: np.ndarray

### `get_feature_names`
- **인자**: 1개
- **복잡도**: 1
- **엣지 케이스**: 5개
- **반환 타입**: List[str]

### `__init__`
- **인자**: 1개
- **복잡도**: 1
- **엣지 케이스**: 5개
- **반환 타입**: 미지정

### `extract_all_features`
- **인자**: 2개
- **복잡도**: 2
- **엣지 케이스**: 7개
- **반환 타입**: CombinedFeatures

### `extract_all_features_from_stock_data`
- **인자**: 2개
- **복잡도**: 2
- **엣지 케이스**: 7개
- **반환 타입**: CombinedFeatures

### `analyze_feature_importance`
- **인자**: 3개
- **복잡도**: 9
- **엣지 케이스**: 8개
- **반환 타입**: List[FeatureImportance]

### `select_optimal_features`
- **인자**: 4개
- **복잡도**: 7
- **엣지 케이스**: 9개
- **반환 타입**: FeatureSelectionResult

### `_calculate_feature_correlations`
- **인자**: 3개
- **복잡도**: 3
- **엣지 케이스**: 7개
- **반환 타입**: Dict[str, float]

### `_select_features_by_importance_and_correlation`
- **인자**: 4개
- **복잡도**: 7
- **엣지 케이스**: 8개
- **반환 타입**: List[str]

### `_evaluate_feature_selection`
- **인자**: 5개
- **복잡도**: 4
- **엣지 케이스**: 9개
- **반환 타입**: float

### `get_feature_summary`
- **인자**: 1개
- **복잡도**: 1
- **엣지 케이스**: 5개
- **반환 타입**: Dict[str, Any]

### `save_selection_result`
- **인자**: 3개
- **복잡도**: 3
- **엣지 케이스**: 7개
- **반환 타입**: bool
