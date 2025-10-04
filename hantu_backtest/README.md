# Hantu Backtest

한투 퀀트 트레이딩 시스템의 백테스트 엔진입니다.

## 주요 기능

- 과거 데이터 기반 전략 테스트
- 다양한 성과 지표 계산
- 전략 최적화 및 시각화
- 멀티 스레드 백테스팅 지원

## 설치 방법

```bash
pip install -e .
```

## 사용 방법

```python
from hantu_backtest.core import BacktestEngine
from hantu_backtest.strategies import MomentumStrategy

# 백테스트 엔진 초기화
engine = BacktestEngine(
    strategy=MomentumStrategy(),
    start_date='2023-01-01',
    end_date='2023-12-31'
)

# 백테스트 실행
results = engine.run()

# 결과 분석
engine.analyze()
```

## 구조

```
hantu_backtest/
├── core/           # 백테스트 엔진 코어
├── strategies/     # 백테스트 전략
├── optimization/   # 전략 최적화
└── visualization/  # 결과 시각화
```

## 지원하는 전략

1. 모멘텀 전략
   - RSI 기반 과매수/과매도 판단
   - 모멘텀 스코어 기반 종목 선정

2. 향후 추가 예정
   - 볼린저 밴드 전략
   - 듀얼 모멘텀 전략
   - 이동평균 크로스 전략 