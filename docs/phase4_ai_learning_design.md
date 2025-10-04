# Phase 4: AI 학습 시스템 상세 설계 문서

## 📋 개요

**TODO 참조**: 2.1-2.8 (Phase 4 AI 학습 시스템 구현)

**목표**: Phase 1(종목 스크리닝)과 Phase 2(일일 선정) 시스템의 성능을 AI 학습을 통해 점진적으로 향상시키는 시스템

**방식**: 직접 학습 모델 구축 (외부 AI API 사용 안함)

**기술 스택**: 
- scikit-learn (기본 머신러닝)
- XGBoost (그래디언트 부스팅)
- TensorFlow/PyTorch (딥러닝)
- Optuna (하이퍼파라미터 최적화)

## 🗂️ TODO 기반 구현 계획

### TODO 2.1: Phase 4 기본 구조 설정
- `core/learning/` 디렉토리 구조 설정
- 기본 클래스 및 인터페이스 정의
- 로깅 및 설정 시스템 구축
- 데이터 저장소 구조 설계

### TODO 2.2: 데이터 수집 및 전처리 시스템 구현
- 과거 데이터 수집 시스템 구축
- 데이터 정규화 및 클리닝 로직
- 피처 추출 파이프라인 구현
- 데이터 검증 및 품질 관리

### TODO 2.3: 피처 엔지니어링 시스템 구현 (17개 피처)
- 기울기 피처 구현 (9개)
- 볼륨 피처 구현 (8개)
- 피처 선택 및 중요도 분석

### TODO 2.4: 일일 성과 분석 시스템 구현
- 선정 종목 성과 추적 시스템
- 수익률 및 리스크 지표 계산
- 전략별 성과 비교 분석

### TODO 2.5: 패턴 학습 엔진 구현
- 성공/실패 패턴 인식 시스템
- 시장 상황별 패턴 분석
- 예측 모델 개발 및 적용

### TODO 2.6: 파라미터 자동 최적화 시스템 구현
- 유전 알고리즘 기반 최적화
- A/B 테스트 프레임워크 구현
- 동적 파라미터 조정 시스템

### TODO 2.7: 백테스트 자동화 시스템 구현
- 일일 백테스트 실행 시스템
- 성과 검증 및 리포트 생성
- 전략 업데이트 자동화

### TODO 2.8: AI 학습 모델 통합 및 배포
- Phase 1/2 시스템에 AI 모델 통합
- 모델 성능 모니터링 시스템
- 실시간 예측 서비스 구현

## 🧠 AI 학습 알고리즘 상세 설명

### 1. 앙상블 학습 (Ensemble Learning)

#### 🎯 목적
Phase 1과 Phase 2에서 선정한 종목의 **성공 확률 예측**과 **수익률 예측**

#### 📊 적용 영역
- **Phase 1**: 스크리닝된 종목이 실제로 좋은 성과를 낼지 예측
- **Phase 2**: 선정된 종목의 단기 수익률 예측

#### 🔧 구체적인 학습 방법

##### A. Random Forest (랜덤 포레스트)
```python
# 종목 선정 정확도 예측
class StockSelectionPredictor:
    def __init__(self):
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
    
    def prepare_features(self, stock_data):
        """
        특징 데이터 준비 (TODO 2.3 기반)
        - 재무 지표: ROE, PER, PBR, 부채비율 등
        - 기술 지표: RSI, MACD, 볼린저밴드 등
        - 시장 지표: 거래량, 변동성, 상대강도 등
        - 기울기 피처: 9개 피처 (TODO 1.5 기반)
        - 볼륨 피처: 8개 피처 (TODO 1.6 기반)
        """
        features = {
            'financial_score': stock_data['roe'] * 0.3 + stock_data['per_rank'] * 0.2,
            'technical_score': stock_data['rsi'] * 0.4 + stock_data['macd'] * 0.3,
            'momentum_score': stock_data['relative_strength'] * 0.5,
            'market_condition': self.get_market_condition(),
            'slope_features': self.extract_slope_features(stock_data),  # TODO 2.3
            'volume_features': self.extract_volume_features(stock_data),  # TODO 2.3
```

##### B. XGBoost (그래디언트 부스팅)
```python
# 수익률 예측
class ReturnPredictor:
    def __init__(self):
        self.model = XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            random_state=42
        )
    
    def prepare_time_series_features(self, price_data):
        """
        시계열 특징 생성
        - 이동평균: 5일, 20일, 60일
        - 모멘텀: 1주일, 1개월 수익률
        - 변동성: 표준편차, ATR
        """
        features = {
            'ma5_ratio': price_data['close'] / price_data['ma5'],
            'ma20_ratio': price_data['close'] / price_data['ma20'],
            'ma60_ratio': price_data['close'] / price_data['ma60'],
            'rsi': price_data['rsi'],
            'macd': price_data['macd'],
            'volume_ratio': price_data['volume'] / price_data['volume_ma20'],
            'momentum_1m': price_data['return_1m'],
            'momentum_3m': price_data['return_3m'],
            'volatility': price_data['volatility'],
            'market_correlation': price_data['market_correlation'],
            
            # === 새로 추가된 기울기 지표 ===
            'price_slope_5d': self.calculate_price_slope(price_data, 5),
            'price_slope_20d': self.calculate_price_slope(price_data, 20),
            'ma5_slope': self.calculate_ma_slope(price_data, 5, 3),
            'ma20_slope': self.calculate_ma_slope(price_data, 20, 5),
            'ma60_slope': self.calculate_ma_slope(price_data, 60, 10),
            'slope_acceleration': self.calculate_slope_acceleration(price_data),
            'trend_consistency': self.check_trend_consistency(price_data),
            'slope_angle': self.calculate_slope_angle(price_data),
            'slope_strength_score': self.get_slope_strength_score(price_data),
            
            # === 향상된 거래량 지표 ===
            'volume_price_correlation': self.calculate_volume_price_correlation(price_data),
            'volume_price_divergence': self.calculate_volume_price_divergence(price_data),
            'volume_momentum_score': self.calculate_volume_momentum_score(price_data),
            'relative_volume_strength': self.calculate_relative_volume_strength(price_data),
            'volume_rank_percentile': self.calculate_volume_rank_percentile(price_data),
            'volume_intensity': self.calculate_volume_intensity(price_data),
            'volume_cluster_count': self.calculate_volume_cluster_count(price_data),
            'volume_anomaly_score': self.calculate_volume_anomaly_score(price_data)
        }
        
        return features
    
    def calculate_price_slope(self, price_data: pd.DataFrame, days: int) -> float:
        """가격 기울기 계산"""
        if len(price_data) < days:
            return 0.0
        
        recent_prices = price_data['close'].tail(days)
        x = np.arange(len(recent_prices))
        slope = np.polyfit(x, recent_prices.values, 1)[0]
        
        # 정규화 (현재가 대비 백분율)
        current_price = recent_prices.iloc[-1]
        normalized_slope = (slope / current_price) * 100 if current_price != 0 else 0.0
        
        return normalized_slope
    
    def calculate_ma_slope(self, price_data: pd.DataFrame, ma_period: int, slope_days: int) -> float:
        """이동평균 기울기 계산"""
        if len(price_data) < ma_period + slope_days:
            return 0.0
        
        ma = price_data['close'].rolling(window=ma_period).mean()
        recent_ma = ma.dropna().tail(slope_days)
        
        if len(recent_ma) < slope_days:
            return 0.0
        
        x = np.arange(len(recent_ma))
        slope = np.polyfit(x, recent_ma.values, 1)[0]
        
        # 정규화
        current_ma = recent_ma.iloc[-1]
        normalized_slope = (slope / current_ma) * 100 if current_ma != 0 else 0.0
        
        return normalized_slope
    
    def calculate_slope_acceleration(self, price_data: pd.DataFrame) -> float:
        """기울기 가속도 계산"""
        if len(price_data) < 10:
            return 0.0
        
        current_slope = self.calculate_price_slope(price_data, 5)
        previous_slope = self.calculate_price_slope(price_data.iloc[:-5], 5)
        
        return current_slope - previous_slope
    
    def check_trend_consistency(self, price_data: pd.DataFrame) -> float:
        """추세 일관성 확인 (0 또는 1)"""
        if len(price_data) < 70:
            return 0.0
        
        short_slope = self.calculate_ma_slope(price_data, 5, 3)
        medium_slope = self.calculate_ma_slope(price_data, 20, 5)
        long_slope = self.calculate_ma_slope(price_data, 60, 10)
        
        # 모든 기울기가 같은 방향인지 확인
        positive_trend = short_slope > 0 and medium_slope > 0 and long_slope > 0
        negative_trend = short_slope < 0 and medium_slope < 0 and long_slope < 0
        
        return 1.0 if (positive_trend or negative_trend) else 0.0
    
    def calculate_slope_angle(self, price_data: pd.DataFrame) -> float:
        """기울기 각도 계산"""
        slope = self.calculate_price_slope(price_data, 5)
        actual_slope = slope / 100
        angle = np.arctan(actual_slope) * 180 / np.pi
        
        return angle
    
    def get_slope_strength_score(self, price_data: pd.DataFrame) -> float:
        """기울기 강도 점수 (0-100)"""
        slope = self.calculate_price_slope(price_data, 5)
        
        if slope > 1.0:
            return 100.0  # strong_up
        elif slope > 0.3:
            return 75.0   # weak_up
        elif slope > -0.3:
            return 50.0   # neutral
        elif slope > -1.0:
            return 25.0   # weak_down
        else:
            return 0.0    # strong_down
    
    def calculate_volume_price_correlation(self, price_data: pd.DataFrame) -> float:
        """거래량-가격 변화 상관관계 계산"""
        if len(price_data) < 20:
            return 0.0
        
        price_changes = price_data['close'].pct_change().tail(20)
        volume_changes = price_data['volume'].pct_change().tail(20)
        
        correlation = price_changes.corr(volume_changes)
        return correlation if not pd.isna(correlation) else 0.0
    
    def calculate_volume_price_divergence(self, price_data: pd.DataFrame) -> float:
        """거래량-가격 다이버전스 점수 (0-100)"""
        if len(price_data) < 20:
            return 0.0
        
        # 최근 10일과 이전 10일 비교
        recent_data = price_data.tail(10)
        previous_data = price_data.iloc[-20:-10]
        
        # 가격 추세
        recent_price_trend = (recent_data['close'].iloc[-1] - recent_data['close'].iloc[0]) / recent_data['close'].iloc[0]
        previous_price_trend = (previous_data['close'].iloc[-1] - previous_data['close'].iloc[0]) / previous_data['close'].iloc[0]
        
        # 거래량 추세
        recent_volume_trend = (recent_data['volume'].mean() - previous_data['volume'].mean()) / previous_data['volume'].mean()
        
        # 다이버전스 점수
        price_direction = 1 if recent_price_trend > previous_price_trend else -1
        volume_direction = 1 if recent_volume_trend > 0 else -1
        
        if price_direction != volume_direction:
            return 75.0 if price_direction > 0 else 25.0  # bearish/bullish divergence
        else:
            return 50.0  # neutral
    
    def calculate_volume_momentum_score(self, price_data: pd.DataFrame) -> float:
        """거래량 모멘텀 점수 (0-100)"""
        if len(price_data) < 20:
            return 50.0
        
        # 단기 및 장기 거래량 평균
        short_volume_avg = price_data['volume'].tail(5).mean()
        long_volume_avg = price_data['volume'].tail(20).mean()
        
        # 가격 변화율
        short_price_change = (price_data['close'].iloc[-1] - price_data['close'].iloc[-5]) / price_data['close'].iloc[-5]
        long_price_change = (price_data['close'].iloc[-1] - price_data['close'].iloc[-20]) / price_data['close'].iloc[-20]
        
        # 거래량 비율
        volume_ratio = short_volume_avg / long_volume_avg if long_volume_avg > 0 else 1.0
        
        # 모멘텀 스코어
        momentum_score = (short_price_change + long_price_change) * volume_ratio
        
        # 0-100 스케일로 변환
        if momentum_score > 0.05:
            return 100.0  # strong_bullish
        elif momentum_score > 0.02:
            return 75.0   # moderate_bullish
        elif momentum_score > -0.02:
            return 50.0   # neutral
        elif momentum_score > -0.05:
            return 25.0   # moderate_bearish
        else:
            return 0.0    # strong_bearish
    
    def calculate_relative_volume_strength(self, price_data: pd.DataFrame) -> float:
        """상대적 거래량 강도 (현재 거래량 / 평균 거래량)"""
        if len(price_data) < 20:
            return 1.0
        
        current_volume = price_data['volume'].iloc[-1]
        avg_volume = price_data['volume'].tail(20).mean()
        
        return current_volume / avg_volume if avg_volume > 0 else 1.0
    
    def calculate_volume_rank_percentile(self, price_data: pd.DataFrame) -> float:
        """거래량 순위 백분위 (0-100)"""
        if len(price_data) < 60:
            return 50.0
        
        volumes = price_data['volume'].tail(60)
        current_volume = volumes.iloc[-1]
        
        percentile = (volumes < current_volume).sum() / len(volumes) * 100
        return percentile
    
    def calculate_volume_intensity(self, price_data: pd.DataFrame) -> float:
        """거래량 강도 (거래량 비율 / 가격 변화율)"""
        if len(price_data) < 20:
            return 0.0
        
        # 가격 변화율
        price_change = price_data['close'].pct_change().iloc[-1]
        
        # 거래량 비율
        current_volume = price_data['volume'].iloc[-1]
        avg_volume = price_data['volume'].tail(20).mean()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # 강도 계산
        if abs(price_change) > 0.02:
            intensity = volume_ratio / abs(price_change)
        else:
            intensity = volume_ratio
        
        return intensity
    
    def calculate_volume_cluster_count(self, price_data: pd.DataFrame) -> float:
        """거래량 클러스터 개수"""
        if len(price_data) < 20:
            return 0.0
        
        # 간단한 클러스터 감지 (평균 대비 1.5배 이상인 연속 구간)
        avg_volume = price_data['volume'].mean()
        high_volume_points = price_data['volume'] > (avg_volume * 1.5)
        
        # 연속 구간 개수 계산
        clusters = 0
        in_cluster = False
        
        for is_high in high_volume_points:
            if is_high and not in_cluster:
                clusters += 1
                in_cluster = True
            elif not is_high:
                in_cluster = False
        
        return float(clusters)
    
    def calculate_volume_anomaly_score(self, price_data: pd.DataFrame) -> float:
        """거래량 이상치 점수 (0-100)"""
        if len(price_data) < 20:
            return 0.0
        
        volumes = price_data['volume'].tail(20)
        mean_volume = volumes.mean()
        std_volume = volumes.std()
        
        if std_volume == 0:
            return 0.0
        
        # 현재 거래량의 Z-score
        current_volume = volumes.iloc[-1]
        z_score = (current_volume - mean_volume) / std_volume
        
        # 이상치 점수 (높은 거래량일수록 높은 점수)
        if z_score > 3:
            return 100.0
        elif z_score > 2:
            return 75.0
        elif z_score > 1:
            return 50.0
        else:
            return 0.0
```

##### C. LSTM (시계열 딥러닝)
```python
# 시계열 패턴 학습
class TimeSeriesPatternLearner:
    def __init__(self):
        self.model = tf.keras.Sequential([
            tf.keras.layers.LSTM(50, return_sequences=True, input_shape=(60, 5)),
            tf.keras.layers.LSTM(50, return_sequences=False),
            tf.keras.layers.Dense(25),
            tf.keras.layers.Dense(1)
        ])
        self.model.compile(optimizer='adam', loss='mse')
    
    def prepare_sequences(self, price_data, sequence_length=60):
        """
        60일 가격 데이터로 다음 주 수익률 예측
        - 입력: 60일간의 [종가, 거래량, RSI, MACD, 볼린저밴드]
        - 출력: 1주일 후 수익률
        """
        sequences = []
        targets = []
        
        for i in range(sequence_length, len(price_data) - 7):
            # 60일 시퀀스
            sequence = price_data[i-sequence_length:i]
            # 1주일 후 수익률
            target = (price_data[i+7]['close'] / price_data[i]['close']) - 1
            
            sequences.append(sequence)
            targets.append(target)
        
        return np.array(sequences), np.array(targets)
    
    def train(self, historical_price_data):
        X, y = self.prepare_sequences(historical_price_data)
        self.model.fit(X, y, epochs=50, batch_size=32, validation_split=0.2)
```

### 2. 강화학습 (Reinforcement Learning)

#### 🎯 목적
Phase 1, 2의 **파라미터 자동 최적화** (가중치, 임계값 등)

#### 📊 적용 영역
- **Phase 1**: 재무/기술/모멘텀 가중치 자동 조정
- **Phase 2**: 매력도 임계값, 리스크 임계값 자동 조정

#### 🔧 구체적인 학습 방법

```python
# PPO (Proximal Policy Optimization) 기반 파라미터 최적화
class ParameterOptimizationAgent:
    def __init__(self):
        # 환경 정의
        self.state_dim = 10  # 시장 상황, 최근 성과 등
        self.action_dim = 6   # 조정할 파라미터 개수
        
        # PPO 에이전트 초기화
        self.agent = PPO(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            lr=0.0003
        )
    
    def get_state(self):
        """
        현재 상태 정의
        - 시장 상황 (상승/하락/횡보)
        - 최근 1주일 성과
        - 최근 1개월 성과
        - 시장 변동성
        - 선정 종목 수
        """
        return np.array([
            self.market_condition,      # 0: 하락, 1: 횡보, 2: 상승
            self.recent_1w_performance, # 최근 1주일 평균 수익률
            self.recent_1m_performance, # 최근 1개월 평균 수익률
            self.market_volatility,     # 시장 변동성
            self.selection_count,       # 선정 종목 수
            self.hit_ratio,            # 적중률
            self.sharpe_ratio,         # 샤프 비율
            self.max_drawdown,         # 최대 낙폭
            self.sector_diversity,     # 섹터 다양성
            self.momentum_trend        # 모멘텀 트렌드
        ])
    
    def take_action(self, action):
        """
        행동 = 파라미터 조정
        - action[0]: Phase1 재무 가중치 조정 (-0.1 ~ +0.1)
        - action[1]: Phase1 기술 가중치 조정
        - action[2]: Phase1 모멘텀 가중치 조정
        - action[3]: Phase2 매력도 임계값 조정
        - action[4]: Phase2 리스크 임계값 조정
        - action[5]: Phase2 섹터별 제한 조정
        """
        # 현재 파라미터 가져오기
        current_params = self.get_current_parameters()
        
        # 행동에 따라 파라미터 조정
        new_params = {
            'phase1_financial_weight': current_params['phase1_financial_weight'] + action[0] * 0.1,
            'phase1_technical_weight': current_params['phase1_technical_weight'] + action[1] * 0.1,
            'phase1_momentum_weight': current_params['phase1_momentum_weight'] + action[2] * 0.1,
            'phase2_min_attractiveness': current_params['phase2_min_attractiveness'] + action[3] * 5,
            'phase2_max_risk': current_params['phase2_max_risk'] + action[4] * 5,
            'phase2_sector_limit': max(1, current_params['phase2_sector_limit'] + int(action[5] * 2))
        }
        
        # 파라미터 제약 조건 적용
        new_params = self.apply_constraints(new_params)
        
        # 새 파라미터로 시스템 업데이트
        self.update_system_parameters(new_params)
        
        return new_params
    
    def calculate_reward(self, performance_data):
        """
        보상 계산
        - 주 보상: 위험 조정 수익률 (샤프 비율)
        - 보조 보상: 적중률, 다양성 등
        """
        sharpe_ratio = performance_data['sharpe_ratio']
        hit_ratio = performance_data['hit_ratio']
        max_drawdown = performance_data['max_drawdown']
        
        # 샤프 비율이 주요 보상
        reward = sharpe_ratio * 10
        
        # 적중률 보너스
        if hit_ratio > 0.7:
            reward += 5
        
        # 최대 낙폭 페널티
        if max_drawdown > 0.15:
            reward -= 10
        
        return reward
    
    def train_step(self):
        """
        일일 학습 스텝
        1. 현재 상태 관찰
        2. 행동 선택 (파라미터 조정)
        3. 1일 후 성과 측정
        4. 보상 계산
        5. 정책 업데이트
        """
        state = self.get_state()
        action = self.agent.select_action(state)
        new_params = self.take_action(action)
        
        # 1일 후 성과 측정 (다음날 실행 후)
        # 이 부분은 비동기적으로 처리됨
        
    def update_policy(self, state, action, reward, next_state):
        """정책 업데이트"""
        self.agent.update(state, action, reward, next_state)
```

### 3. 유전 알고리즘 (Genetic Algorithm)

#### 🎯 목적
**파라미터 조합의 전역 최적화** (강화학습이 지역 최적해에 빠질 때 보완)

#### 📊 적용 영역
- 주말에 실행하여 파라미터 대폭 조정
- 강화학습으로 찾기 어려운 파라미터 조합 탐색

#### 🔧 구체적인 학습 방법

```python
# 유전 알고리즘 기반 파라미터 최적화
class GeneticParameterOptimizer:
    def __init__(self, population_size=50, generations=100):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = 0.1
        self.crossover_rate = 0.8
    
    def create_individual(self):
        """
        개체 생성 (파라미터 조합)
        - 각 파라미터는 유효 범위 내에서 랜덤 생성
        """
        individual = {
            'phase1_financial_weight': random.uniform(0.2, 0.6),
            'phase1_technical_weight': random.uniform(0.2, 0.6),
            'phase1_momentum_weight': random.uniform(0.1, 0.4),
            'phase2_min_attractiveness': random.uniform(50, 80),
            'phase2_max_risk': random.uniform(30, 60),
            'phase2_min_confidence': random.uniform(0.3, 0.7),
            'phase2_sector_limit': random.randint(2, 6)
        }
        
        # 가중치 합이 1이 되도록 정규화
        weight_sum = (individual['phase1_financial_weight'] + 
                     individual['phase1_technical_weight'] + 
                     individual['phase1_momentum_weight'])
        
        individual['phase1_financial_weight'] /= weight_sum
        individual['phase1_technical_weight'] /= weight_sum
        individual['phase1_momentum_weight'] /= weight_sum
        
        return individual
    
    def evaluate_fitness(self, individual):
        """
        적합도 평가 (백테스트 실행)
        - 최근 6개월 데이터로 백테스트
        - 샤프 비율, 최대 낙폭, 적중률 종합 평가
        """
        # 파라미터 적용하여 백테스트 실행
        backtest_results = self.run_backtest(individual)
        
        # 종합 점수 계산
        sharpe_ratio = backtest_results['sharpe_ratio']
        max_drawdown = backtest_results['max_drawdown']
        hit_ratio = backtest_results['hit_ratio']
        
        # 적합도 = 샤프 비율 * 적중률 - 최대 낙폭 페널티
        fitness = sharpe_ratio * hit_ratio - max_drawdown * 2
        
        return fitness
    
    def crossover(self, parent1, parent2):
        """교배 (균등 교배)"""
        child1 = {}
        child2 = {}
        
        for key in parent1.keys():
            if random.random() < 0.5:
                child1[key] = parent1[key]
                child2[key] = parent2[key]
            else:
                child1[key] = parent2[key]
                child2[key] = parent1[key]
        
        return child1, child2
    
    def mutate(self, individual):
        """돌연변이 (가우시안 노이즈 추가)"""
        for key, value in individual.items():
            if random.random() < self.mutation_rate:
                if isinstance(value, float):
                    # 가우시안 노이즈 추가
                    noise = random.gauss(0, 0.05)
                    individual[key] = max(0.01, min(1.0, value + noise))
                elif isinstance(value, int):
                    # 정수는 ±1 변경
                    individual[key] = max(1, min(10, value + random.choice([-1, 1])))
        
        return individual
    
    def optimize(self):
        """유전 알고리즘 실행"""
        # 초기 집단 생성
        population = [self.create_individual() for _ in range(self.population_size)]
        
        for generation in range(self.generations):
            # 적합도 평가
            fitness_scores = [self.evaluate_fitness(ind) for ind in population]
            
            # 선택 (토너먼트 선택)
            new_population = []
            for _ in range(self.population_size // 2):
                parent1 = self.tournament_selection(population, fitness_scores)
                parent2 = self.tournament_selection(population, fitness_scores)
                
                # 교배
                if random.random() < self.crossover_rate:
                    child1, child2 = self.crossover(parent1, parent2)
                else:
                    child1, child2 = parent1.copy(), parent2.copy()
                
                # 돌연변이
                child1 = self.mutate(child1)
                child2 = self.mutate(child2)
                
                new_population.extend([child1, child2])
            
            population = new_population
            
            # 진행 상황 출력
            best_fitness = max(fitness_scores)
            print(f"Generation {generation}: Best Fitness = {best_fitness:.4f}")
        
        # 최고 개체 반환
        best_individual = population[fitness_scores.index(max(fitness_scores))]
        return best_individual
```

### 4. 베이지안 최적화 (Bayesian Optimization)

#### 🎯 목적
**하이퍼파라미터 최적화** (머신러닝 모델의 파라미터 튜닝)

#### 📊 적용 영역
- Random Forest, XGBoost, LSTM 모델의 하이퍼파라미터 최적화
- 적은 시도로 최적 파라미터 찾기

#### 🔧 구체적인 학습 방법

```python
# Optuna를 사용한 베이지안 최적화
import optuna

class HyperparameterOptimizer:
    def __init__(self):
        self.study = optuna.create_study(direction='maximize')
    
    def objective_function(self, trial):
        """
        목적 함수 정의
        - trial에서 하이퍼파라미터 샘플링
        - 모델 훈련 및 성과 평가
        - 최대화할 지표 반환
        """
        # Random Forest 하이퍼파라미터 샘플링
        rf_params = {
            'n_estimators': trial.suggest_int('rf_n_estimators', 50, 300),
            'max_depth': trial.suggest_int('rf_max_depth', 3, 20),
            'min_samples_split': trial.suggest_int('rf_min_samples_split', 2, 20),
            'min_samples_leaf': trial.suggest_int('rf_min_samples_leaf', 1, 10)
        }
        
        # XGBoost 하이퍼파라미터 샘플링
        xgb_params = {
            'n_estimators': trial.suggest_int('xgb_n_estimators', 100, 500),
            'max_depth': trial.suggest_int('xgb_max_depth', 3, 12),
            'learning_rate': trial.suggest_float('xgb_learning_rate', 0.01, 0.3),
            'subsample': trial.suggest_float('xgb_subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('xgb_colsample_bytree', 0.6, 1.0)
        }
        
        # LSTM 하이퍼파라미터 샘플링
        lstm_params = {
            'lstm_units': trial.suggest_int('lstm_units', 32, 128),
            'dense_units': trial.suggest_int('dense_units', 16, 64),
            'dropout': trial.suggest_float('dropout', 0.1, 0.5),
            'learning_rate': trial.suggest_float('lstm_learning_rate', 0.0001, 0.01)
        }
        
        # 모델 훈련 및 평가
        performance = self.train_and_evaluate_models(rf_params, xgb_params, lstm_params)
        
        # 종합 성과 점수 반환
        return performance['weighted_score']
    
    def train_and_evaluate_models(self, rf_params, xgb_params, lstm_params):
        """
        주어진 하이퍼파라미터로 모델 훈련 및 평가
        """
        # 훈련/검증 데이터 분할
        train_data, val_data = self.split_data()
        
        # Random Forest 모델 훈련
        rf_model = RandomForestClassifier(**rf_params)
        rf_model.fit(train_data['X'], train_data['y'])
        rf_score = rf_model.score(val_data['X'], val_data['y'])
        
        # XGBoost 모델 훈련
        xgb_model = XGBRegressor(**xgb_params)
        xgb_model.fit(train_data['X_reg'], train_data['y_reg'])
        xgb_score = self.calculate_r2_score(xgb_model, val_data['X_reg'], val_data['y_reg'])
        
        # LSTM 모델 훈련
        lstm_model = self.build_lstm_model(lstm_params)
        lstm_history = lstm_model.fit(train_data['X_seq'], train_data['y_seq'], 
                                     validation_data=(val_data['X_seq'], val_data['y_seq']),
                                     epochs=50, verbose=0)
        lstm_score = 1 - min(lstm_history.history['val_loss'])
        
        # 가중 평균 점수 계산
        weighted_score = rf_score * 0.4 + xgb_score * 0.4 + lstm_score * 0.2
        
        return {
            'rf_score': rf_score,
            'xgb_score': xgb_score,
            'lstm_score': lstm_score,
            'weighted_score': weighted_score
        }
    
    def optimize(self, n_trials=100):
        """베이지안 최적화 실행"""
        self.study.optimize(self.objective_function, n_trials=n_trials)
        
        # 최적 하이퍼파라미터 반환
        best_params = self.study.best_params
        best_score = self.study.best_value
        
        print(f"Best score: {best_score:.4f}")
        print(f"Best parameters: {best_params}")
        
        return best_params
```

## 🔄 통합 학습 프로세스

### 일일 학습 사이클

```python
class IntegratedLearningSystem:
    def __init__(self):
        self.ensemble_learner = EnsembleLearner()
        self.rl_agent = ParameterOptimizationAgent()
        self.performance_tracker = PerformanceTracker()
    
    def daily_learning_cycle(self):
        """
        매일 실행되는 학습 사이클
        """
        # 1. 전날 성과 데이터 수집
        yesterday_performance = self.performance_tracker.get_yesterday_performance()
        
        # 2. 강화학습 에이전트 업데이트
        if yesterday_performance:
            state = self.rl_agent.get_state()
            action = self.rl_agent.last_action
            reward = self.rl_agent.calculate_reward(yesterday_performance)
            next_state = self.rl_agent.get_state()
            
            self.rl_agent.update_policy(state, action, reward, next_state)
        
        # 3. 앙상블 모델 점진적 학습
        if len(self.performance_tracker.get_recent_data(days=7)) >= 7:
            recent_data = self.performance_tracker.get_recent_data(days=30)
            self.ensemble_learner.incremental_training(recent_data)
        
        # 4. 오늘의 파라미터 조정
        current_state = self.rl_agent.get_state()
        action = self.rl_agent.select_action(current_state)
        new_params = self.rl_agent.take_action(action)
        
        # 5. Phase 1, 2 시스템에 새 파라미터 적용
        self.update_phase_parameters(new_params)
        
        print(f"Daily learning completed. New parameters: {new_params}")

    def weekly_optimization(self):
        """
        주말에 실행되는 대규모 최적화
        """
        # 1. 유전 알고리즘으로 파라미터 대폭 조정
        genetic_optimizer = GeneticParameterOptimizer()
        best_genetic_params = genetic_optimizer.optimize()
        
        # 2. 베이지안 최적화로 하이퍼파라미터 튜닝
        hyperopt = HyperparameterOptimizer()
        best_hyperparams = hyperopt.optimize(n_trials=50)
        
        # 3. 앙상블 모델 재훈련
        self.ensemble_learner.full_retrain(best_hyperparams)
        
        # 4. 강화학습 에이전트에 최적 파라미터 반영
        self.rl_agent.update_baseline(best_genetic_params)
        
        print(f"Weekly optimization completed.")
        print(f"Genetic algorithm best params: {best_genetic_params}")
        print(f"Best hyperparameters: {best_hyperparams}")
```

## 📊 성과 측정 및 평가

### 평가 지표

```python
class PerformanceMetrics:
    def calculate_comprehensive_score(self, results):
        """종합 성과 점수 계산"""
        metrics = {
            # 수익성 지표
            'total_return': results['total_return'],
            'annualized_return': results['annualized_return'],
            'excess_return': results['return'] - results['benchmark_return'],
            
            # 위험 지표
            'volatility': results['volatility'],
            'max_drawdown': results['max_drawdown'],
            'var_95': results['value_at_risk_95'],
            
            # 위험조정수익률
            'sharpe_ratio': results['return'] / results['volatility'],
            'sortino_ratio': results['return'] / results['downside_deviation'],
            'calmar_ratio': results['annualized_return'] / results['max_drawdown'],
            
            # 정확도 지표
            'hit_ratio': results['winning_trades'] / results['total_trades'],
            'profit_factor': results['gross_profit'] / results['gross_loss'],
            'avg_win_loss_ratio': results['avg_win'] / results['avg_loss']
        }
        
        # 가중 종합 점수
        score = (
            metrics['sharpe_ratio'] * 0.3 +
            metrics['hit_ratio'] * 0.2 +
            metrics['excess_return'] * 0.2 +
            (1 - metrics['max_drawdown']) * 0.2 +
            metrics['calmar_ratio'] * 0.1
        )
        
        return score, metrics
```

## 🛠️ 구현 로드맵

### Phase 4.1: 기본 성과 추적 (1-2주)
1. **PerformanceTracker 구현**
2. **기본 통계 분석 함수**
3. **데이터 저장 구조 설계**

### Phase 4.2: 앙상블 학습 (2-3주)
1. **Random Forest 모델 구현**
2. **XGBoost 모델 구현**  
3. **LSTM 모델 구현**
4. **모델 앙상블 및 예측 시스템**

### Phase 4.3: 강화학습 (2-3주)
1. **PPO 에이전트 구현**
2. **환경 및 보상 함수 설계**
3. **파라미터 조정 메커니즘**
4. **일일 학습 사이클 구현**

### Phase 4.4: 최적화 시스템 (2-3주)
1. **유전 알고리즘 구현**
2. **베이지안 최적화 구현**
3. **백테스트 자동화**
4. **주간 최적화 사이클**

### Phase 4.5: 통합 및 배포 (1-2주)
1. **전체 시스템 통합**
2. **성능 최적화**
3. **테스트 및 검증**
4. **모니터링 시스템**

## 📝 참고 자료

- **scikit-learn**: https://scikit-learn.org/
- **XGBoost**: https://xgboost.readthedocs.io/
- **TensorFlow**: https://tensorflow.org/
- **Optuna**: https://optuna.org/
- **강화학습 PPO**: https://arxiv.org/abs/1707.06347
- **유전 알고리즘**: https://en.wikipedia.org/wiki/Genetic_algorithm
- **베이지안 최적화**: https://distill.pub/2020/bayesian-optimization/

---

**마지막 업데이트**: 2025년 7월 13일  
**작성자**: AI Assistant  
**버전**: 1.0.0 