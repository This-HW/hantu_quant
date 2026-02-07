"""Redis 캐시 직렬화 테스트

DataFrame/Series의 Timestamp 인덱스/컬럼 직렬화 회귀 방지.
관련 에러: "keys must be str, int, float, bool or None, not Timestamp"

현재 구현: __pandas_type__ 메타데이터를 사용하여 역직렬화 시 DataFrame/Series 복원.
"""

import pytest
import pandas as pd
import numpy as np
from core.api.redis_client import _json_serialize, _json_deserialize


class TestDataFrameSerialization:
    """DataFrame 직렬화/역직렬화 테스트"""

    def test_timestamp_index(self):
        """Timestamp 인덱스를 가진 DataFrame - 직렬화 성공 및 복원"""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'price': [100, 101, 102, 103, 104],
            'volume': [1000, 1100, 1200, 1300, 1400]
        }, index=dates)

        serialized = _json_serialize(df)
        deserialized = _json_deserialize(serialized)

        # __pandas_type__ 메타데이터로 DataFrame 복원됨
        assert isinstance(deserialized, pd.DataFrame)
        assert len(deserialized) == 5
        assert list(deserialized.columns) == ['price', 'volume']

    def test_timestamp_columns(self):
        """Timestamp 컬럼을 가진 DataFrame"""
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        df = pd.DataFrame(
            np.random.rand(5, 3),
            columns=dates
        )

        serialized = _json_serialize(df)
        deserialized = _json_deserialize(serialized)

        assert isinstance(deserialized, pd.DataFrame)
        assert deserialized.shape == (5, 3)

    def test_normal_dataframe(self):
        """일반 DataFrame (회귀 테스트)"""
        df = pd.DataFrame({
            'A': [1, 2, 3],
            'B': ['x', 'y', 'z'],
            'C': [1.1, 2.2, 3.3]
        })

        serialized = _json_serialize(df)
        deserialized = _json_deserialize(serialized)

        assert isinstance(deserialized, pd.DataFrame)
        assert list(deserialized.columns) == ['A', 'B', 'C']
        assert len(deserialized) == 3

    def test_complex_timestamp_index(self):
        """복잡한 Timestamp 인덱스 (KIS API 응답 유사 구조)"""
        dates = pd.DatetimeIndex([
            pd.Timestamp('2024-01-01 09:00:00'),
            pd.Timestamp('2024-01-01 09:05:00'),
            pd.Timestamp('2024-01-01 09:10:00'),
        ])

        df = pd.DataFrame({
            'open': [100, 101, 102],
            'high': [105, 106, 107],
            'low': [98, 99, 100],
            'close': [103, 104, 105],
            'volume': [10000, 11000, 12000]
        }, index=dates)

        serialized = _json_serialize(df)
        deserialized = _json_deserialize(serialized)

        assert isinstance(deserialized, pd.DataFrame)
        assert len(deserialized) == 3
        assert len(deserialized.columns) == 5

    def test_empty_dataframe(self):
        """빈 DataFrame"""
        df = pd.DataFrame()

        serialized = _json_serialize(df)
        deserialized = _json_deserialize(serialized)

        assert isinstance(deserialized, pd.DataFrame)
        assert len(deserialized) == 0

    def test_data_values_preserved(self):
        """직렬화-역직렬화 후 데이터 값 보존 확인"""
        df = pd.DataFrame({
            'price': [100, 200, 300],
            'name': ['A', 'B', 'C']
        })

        serialized = _json_serialize(df)
        deserialized = _json_deserialize(serialized)

        assert deserialized['price'].tolist() == [100, 200, 300]
        assert deserialized['name'].tolist() == ['A', 'B', 'C']


class TestSeriesSerialization:
    """Series 직렬화/역직렬화 테스트"""

    def test_timestamp_index(self):
        """Timestamp 인덱스를 가진 Series"""
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        series = pd.Series([100, 101, 102, 103, 104], index=dates, name='price')

        serialized = _json_serialize(series)
        deserialized = _json_deserialize(serialized)

        assert isinstance(deserialized, pd.Series)
        assert len(deserialized) == 5

    def test_normal_series(self):
        """일반 Series (회귀 테스트)"""
        series = pd.Series([1, 2, 3], name='test')

        serialized = _json_serialize(series)
        deserialized = _json_deserialize(serialized)

        assert isinstance(deserialized, pd.Series)
        assert deserialized.tolist() == [1, 2, 3]


class TestBasicSerialization:
    """기본 타입 직렬화 테스트"""

    def test_dict(self):
        """dict 직렬화"""
        data = {'key': 'value', 'number': 42}
        serialized = _json_serialize(data)
        deserialized = _json_deserialize(serialized)
        assert deserialized == data

    def test_list(self):
        """list 직렬화"""
        data = [1, 2, 3, 'a', 'b']
        serialized = _json_serialize(data)
        deserialized = _json_deserialize(serialized)
        assert deserialized == data

    def test_roundtrip_preserves_structure(self):
        """직렬화-역직렬화 왕복 시 구조 보존"""
        data = {
            'stocks': [
                {'code': '005930', 'price': 70000},
                {'code': '000660', 'price': 120000},
            ],
            'timestamp': '2024-01-01T09:00:00'
        }
        serialized = _json_serialize(data)
        deserialized = _json_deserialize(serialized)
        assert deserialized == data
