#!/usr/bin/env python3
"""
In/Out-of-Sample 데이터 분할기
Walk-Forward Analysis를 위한 시계열 데이터 분할
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class DataSplit:
    """데이터 분할 결과"""
    train_data: List[Dict]
    val_data: List[Dict]
    test_data: List[Dict]
    split_info: Dict[str, Any]


class DataSplitter:
    """시계열 데이터 분할기"""

    def __init__(
        self,
        train_ratio: float = 0.7,
        val_ratio: float = 0.0,
        purge_days: int = 5
    ):
        """
        Args:
            train_ratio: 학습 데이터 비율 (기본 70%)
            val_ratio: 검증 데이터 비율 (기본 0%, Walk-Forward에서는 미사용)
            purge_days: Train/Test 사이 격리 기간 (기본 5일)
        """
        # 입력 검증
        if not (0 < train_ratio <= 1.0):
            raise ValueError(f"train_ratio must be in (0, 1], got {train_ratio}")
        if not (0 <= val_ratio < 1.0):
            raise ValueError(f"val_ratio must be in [0, 1), got {val_ratio}")
        if purge_days < 0:
            raise ValueError(f"purge_days must be >= 0, got {purge_days}")

        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = 1.0 - train_ratio - val_ratio
        self.purge_days = purge_days

        if self.test_ratio <= 0:
            raise ValueError(f"test_ratio must be > 0, got {self.test_ratio}")

        logger.info(
            f"DataSplitter 초기화: train={train_ratio:.1%}, "
            f"val={val_ratio:.1%}, test={self.test_ratio:.1%}, "
            f"purge={purge_days}일"
        )

    def split_walk_forward(
        self,
        data: List[Dict],
        date_key: str = 'selection_date'
    ) -> DataSplit:
        """Walk-Forward를 위한 시계열 분할 (purge gap 포함)

        Args:
            data: 분할할 데이터 리스트
            date_key: 날짜 필드명 (기본: 'selection_date')

        Returns:
            DataSplit: 분할된 데이터
        """
        if not data:
            logger.warning("빈 데이터셋 전달됨")
            return self._empty_split()

        # 1. 날짜순 정렬
        sorted_data = sorted(data, key=lambda x: x[date_key])
        total = len(sorted_data)

        # 2. Train/Val/Test 경계 계산
        train_end_idx = int(total * self.train_ratio)
        val_end_idx = train_end_idx + int(total * self.val_ratio)

        # 3. Purge gap 적용
        train_data = sorted_data[:train_end_idx]
        val_data = sorted_data[train_end_idx:val_end_idx]

        # Purge anchor: val이 있으면 val 마지막, 없으면 train 마지막
        if val_data:
            purge_anchor_date = datetime.strptime(
                val_data[-1][date_key], "%Y-%m-%d"
            )
        elif train_data:
            purge_anchor_date = datetime.strptime(
                train_data[-1][date_key], "%Y-%m-%d"
            )
        else:
            # train도 val도 없으면 test 전체 사용
            test_data = sorted_data[val_end_idx:]
            purge_anchor_date = None

        if purge_anchor_date:
            purge_end_date = purge_anchor_date + timedelta(days=self.purge_days)
            purge_end_str = purge_end_date.strftime("%Y-%m-%d")

            # Purge 이후 데이터만 test로 사용
            test_data = [
                item for item in sorted_data[val_end_idx:]
                if item[date_key] > purge_end_str
            ]
        else:
            test_data = sorted_data[val_end_idx:]

        # 4. 분할 정보 기록
        split_info = {
            'total_samples': total,
            'train_samples': len(train_data),
            'val_samples': len(val_data),
            'test_samples': len(test_data),
            'purged_samples': total - len(train_data) - len(val_data) - len(test_data),
            'train_start': train_data[0][date_key] if train_data else None,
            'train_end': train_data[-1][date_key] if train_data else None,
            'test_start': test_data[0][date_key] if test_data else None,
            'test_end': test_data[-1][date_key] if test_data else None,
            'purge_days': self.purge_days
        }

        logger.info(
            f"데이터 분할 완료: Train={split_info['train_samples']}개 "
            f"({split_info['train_start']}~{split_info['train_end']}), "
            f"Test={split_info['test_samples']}개 "
            f"({split_info['test_start']}~{split_info['test_end']}), "
            f"Purged={split_info['purged_samples']}개"
        )

        return DataSplit(
            train_data=train_data,
            val_data=val_data,
            test_data=test_data,
            split_info=split_info
        )

    def _empty_split(self) -> DataSplit:
        """빈 분할 결과"""
        return DataSplit(
            train_data=[],
            val_data=[],
            test_data=[],
            split_info={
                'total_samples': 0,
                'train_samples': 0,
                'val_samples': 0,
                'test_samples': 0,
                'purged_samples': 0
            }
        )
