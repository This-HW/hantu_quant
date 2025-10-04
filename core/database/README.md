# 데이터베이스 구조

## 개요
한투 퀀트 시스템의 데이터베이스는 SQLite를 사용하여 주식 데이터를 관리합니다.

## 테이블 구조

### 1. stocks (종목 정보)
- `id`: 기본키
- `code`: 종목코드 (6자리)
- `name`: 종목명
- `market`: 시장구분 (KOSPI/KOSDAQ)
- `sector`: 섹터
- `updated_at`: 갱신일시

### 2. stock_prices (주가 데이터)
- `id`: 기본키
- `stock_id`: 종목 ID (외래키)
- `date`: 날짜
- `open`: 시가
- `high`: 고가
- `low`: 저가
- `close`: 종가
- `volume`: 거래량
- `amount`: 거래대금

### 3. technical_indicators (기술적 지표)
- `id`: 기본키
- `stock_id`: 종목 ID (외래키)
- `date`: 날짜
- `indicator_type`: 지표 유형
- `value`: 지표값
- `params`: 지표 파라미터 (JSON)

### 4. trades (거래 내역)
- `id`: 기본키
- `stock_id`: 종목 ID (외래키)
- `datetime`: 거래 시각
- `type`: 매수/매도
- `price`: 거래가
- `quantity`: 수량
- `amount`: 거래금액
- `commission`: 수수료
- `strategy`: 전략명

## 데이터베이스 조회 방법

### 1. 파이썬 코드로 조회

#### 종목 정보 조회
```python
from core.database import StockRepository

repository = StockRepository()

# 단일 종목 조회
stock = repository.get_stock("005930")  # 삼성전자

# 전체 종목 목록 조회
stocks = repository.get_all_stocks()
```

#### 주가 데이터 조회
```python
from datetime import datetime

# 특정 기간의 주가 데이터 조회
start_date = datetime(2024, 1, 1)
end_date = datetime(2024, 2, 1)
prices = repository.get_stock_prices(
    stock_id=stock.id,
    start_date=start_date,
    end_date=end_date
)
```

#### 기술적 지표 조회
```python
# RSI 지표 조회
indicators = repository.get_technical_indicators(
    stock_id=stock.id,
    indicator_type='rsi',
    start_date=start_date,
    end_date=end_date
)
```

#### 거래 내역 조회
```python
# 특정 종목의 거래 내역 조회
trades = repository.get_trades(
    stock_id=stock.id,
    start_date=start_date,
    end_date=end_date
)

# 전체 거래 내역 조회
all_trades = repository.get_trades()
```

### 2. 터미널에서 직접 조회

#### SQLite 접속
```bash
# 데이터베이스 접속
sqlite3 stock_data.db

# 테이블 목록 확인
.tables

# 테이블 스키마 확인
.schema stocks
.schema stock_prices
.schema technical_indicators
.schema trades

# 보기 좋게 출력 설정
.mode column   # 컬럼 모드로 출력
.headers on    # 헤더 표시
```

#### 주요 조회 쿼리 예시

1. 종목 정보 조회
```sql
-- 전체 종목 목록
SELECT code, name, market, sector FROM stocks;

-- 특정 종목 조회 (예: 삼성전자)
SELECT * FROM stocks WHERE code = '005930';

-- KOSPI 종목만 조회
SELECT code, name FROM stocks WHERE market = 'KOSPI';
```

2. 주가 데이터 조회
```sql
-- 특정 종목의 최근 주가 데이터
SELECT s.code, s.name, p.date, p.close, p.volume
FROM stocks s
JOIN stock_prices p ON s.id = p.stock_id
WHERE s.code = '005930'
ORDER BY p.date DESC
LIMIT 10;

-- 특정 기간의 주가 데이터
SELECT date, open, high, low, close, volume
FROM stock_prices p
JOIN stocks s ON s.id = p.stock_id
WHERE s.code = '005930'
AND date BETWEEN '2024-01-01' AND '2024-02-01'
ORDER BY date;
```

3. 기술적 지표 조회
```sql
-- RSI 지표 조회
SELECT s.code, t.date, t.value
FROM technical_indicators t
JOIN stocks s ON s.id = t.stock_id
WHERE s.code = '005930'
AND t.indicator_type = 'rsi'
ORDER BY t.date DESC
LIMIT 10;

-- 여러 지표 한번에 조회
SELECT s.code, t.date, t.indicator_type, t.value
FROM technical_indicators t
JOIN stocks s ON s.id = t.stock_id
WHERE s.code = '005930'
AND t.date = '2024-02-01';
```

4. 거래 내역 조회
```sql
-- 전체 거래 내역
SELECT s.code, t.datetime, t.type, t.price, t.quantity, t.amount
FROM trades t
JOIN stocks s ON s.id = t.stock_id
ORDER BY t.datetime DESC
LIMIT 10;

-- 특정 종목의 거래 내역
SELECT datetime, type, price, quantity, amount
FROM trades t
JOIN stocks s ON s.id = t.stock_id
WHERE s.code = '005930'
ORDER BY datetime DESC;
```

## 데이터베이스 설정

데이터베이스 설정은 `.env` 파일에서 관리됩니다:
```
DATABASE_URL="sqlite:///stock_data.db"
```

## 주의사항

1. 데이터베이스 파일은 `.gitignore`에 포함되어 있어 Git에서 추적되지 않습니다.
2. 첫 실행 시 자동으로 테이블이 생성됩니다.
3. 데이터베이스 세션은 자동으로 관리되므로 별도의 연결/해제가 필요 없습니다.
4. SQLite 데이터베이스 파일을 직접 조작할 때는 주의가 필요합니다.
5. 대량의 데이터를 조회할 때는 적절한 WHERE 조건과 LIMIT을 사용하세요. 