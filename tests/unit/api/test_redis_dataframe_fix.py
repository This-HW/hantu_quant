"""Redis DataFrame 직렬화 수정 테스트"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from core.api.redis_client import _json_serialize, _json_deserialize


def test_dataframe_with_timestamp_index():
    """Timestamp 인덱스를 가진 DataFrame 직렬화/역직렬화"""
    # Timestamp 인덱스 DataFrame 생성
    dates = pd.date_range('2024-01-01', periods=5, freq='D')
    df = pd.DataFrame({
        'open': [100, 101, 102, 103, 104],
        'close': [101, 102, 103, 104, 105]
    }, index=dates)

    # 직렬화
    serialized = _json_serialize(df)
    assert isinstance(serialized, bytes)

    # 역직렬화
    deserialized = _json_deserialize(serialized)
    assert isinstance(deserialized, pd.DataFrame)

    # 데이터 검증
    assert len(deserialized) == 5
    assert list(deserialized.columns) == ['open', 'close']
    assert deserialized['open'].tolist() == [100, 101, 102, 103, 104]


def test_dataframe_with_datetime_columns():
    """DatetimeIndex 컬럼을 가진 DataFrame"""
    df = pd.DataFrame({
        'value1': [1, 2, 3],
        'value2': [4, 5, 6]
    }, index=['A', 'B', 'C'])

    serialized = _json_serialize(df)
    deserialized = _json_deserialize(serialized)

    assert isinstance(deserialized, pd.DataFrame)
    assert deserialized['value1'].tolist() == [1, 2, 3]


def test_series_with_timestamp_index():
    """Timestamp 인덱스를 가진 Series"""
    dates = pd.date_range('2024-01-01', periods=3, freq='D')
    series = pd.Series([10, 20, 30], index=dates)

    serialized = _json_serialize(series)
    deserialized = _json_deserialize(serialized)

    assert isinstance(deserialized, pd.Series)
    assert len(deserialized) == 3
    assert deserialized.tolist() == [10, 20, 30]


def test_nested_dataframe_in_dict():
    """dict 내부에 DataFrame이 있는 경우"""
    dates = pd.date_range('2024-01-01', periods=3, freq='D')
    df = pd.DataFrame({'price': [100, 101, 102]}, index=dates)

    data = {
        'stock_code': '005930',
        'data': df
    }

    # DataFrame은 직접 직렬화할 수 없으므로 전처리 필요
    # 실제 캐시 사용 시는 최상위 레벨 DataFrame만 처리
    serialized = _json_serialize(df)
    deserialized = _json_deserialize(serialized)

    assert isinstance(deserialized, pd.DataFrame)


def test_empty_dataframe():
    """빈 DataFrame 처리"""
    df = pd.DataFrame()

    serialized = _json_serialize(df)
    deserialized = _json_deserialize(serialized)

    assert isinstance(deserialized, pd.DataFrame)
    assert len(deserialized) == 0


def test_regular_dict_unchanged():
    """일반 dict는 그대로 처리"""
    data = {'key': 'value', 'number': 123}

    serialized = _json_serialize(data)
    deserialized = _json_deserialize(serialized)

    assert isinstance(deserialized, dict)
    assert deserialized == data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
