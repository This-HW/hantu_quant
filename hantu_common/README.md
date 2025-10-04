# Hantu Common Library

한투 퀀트 트레이딩 시스템의 공통 라이브러리입니다.

## 주요 기능

- 기술지표 (Technical Indicators)
- 유틸리티 함수
- 공통 데이터 모델

## 설치 방법

```bash
pip install -e .
```

## 사용 방법

```python
from hantu_common.indicators import MovingAverage, RSI, BollingerBands
from hantu_common.utils import DataLoader
from hantu_common.models import StockData
```

## 구조

```
hantu_common/
├── indicators/     # 기술지표
├── utils/         # 유틸리티
└── models/        # 공통 데이터 모델
``` 