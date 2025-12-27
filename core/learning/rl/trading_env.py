"""
강화학습 트레이딩 환경 (P3-2)

OpenAI Gymnasium 호환 트레이딩 환경

상태 (State):
- 잔고, 포지션 비율
- 기술지표 (RSI, MACD, BB 등)
- 최근 수익률

행동 (Action):
- 0: 홀드
- 1: 매수 10%
- 2: 매수 30%
- 3: 매수 50%
- 4: 매도 10%
- 5: 매도 30%
- 6: 매도 50%
- 7: 전량 청산

보상 (Reward):
- 포트폴리오 수익률 변화
- 리스크 조정 수익률 (샤프비율)
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import pandas as pd

# Gymnasium은 선택적 의존성
try:
    import gymnasium as gym
    from gymnasium import spaces
    GYMNASIUM_AVAILABLE = True
except ImportError:
    try:
        import gym
        from gym import spaces
        GYMNASIUM_AVAILABLE = True
    except ImportError:
        GYMNASIUM_AVAILABLE = False
        gym = None
        spaces = None

logger = logging.getLogger(__name__)


@dataclass
class TradingState:
    """트레이딩 상태"""
    cash: float  # 현금
    position: float  # 보유 수량
    position_value: float  # 포지션 가치
    total_value: float  # 총 자산
    current_price: float  # 현재가
    step: int  # 현재 스텝

    # 기술지표
    rsi: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0

    # 수익률
    returns_1d: float = 0.0
    returns_5d: float = 0.0
    returns_20d: float = 0.0


@dataclass
class TradeRecord:
    """거래 기록"""
    step: int
    action: int
    action_name: str
    price: float
    quantity: float
    cash_before: float
    cash_after: float
    position_before: float
    position_after: float
    total_value: float
    reward: float


class TradingEnvironment:
    """강화학습 트레이딩 환경 (Gymnasium 호환)

    Usage:
        env = TradingEnvironment(df)
        obs, info = env.reset()

        for _ in range(1000):
            action = agent.select_action(obs)
            obs, reward, terminated, truncated, info = env.step(action)
            if terminated or truncated:
                break
    """

    # 행동 정의
    ACTIONS = {
        0: ('hold', 0.0),
        1: ('buy', 0.1),
        2: ('buy', 0.3),
        3: ('buy', 0.5),
        4: ('sell', 0.1),
        5: ('sell', 0.3),
        6: ('sell', 0.5),
        7: ('sell', 1.0),  # 전량 청산
    }

    def __init__(
        self,
        df: pd.DataFrame,
        initial_cash: float = 10_000_000,
        commission: float = 0.00015,  # 0.015%
        slippage: float = 0.001,  # 0.1%
        window_size: int = 20,
        reward_scaling: float = 100.0,
    ):
        """초기화

        Args:
            df: OHLCV 데이터프레임
            initial_cash: 초기 현금 (기본 1000만원)
            commission: 수수료율
            slippage: 슬리피지율
            window_size: 관측 윈도우 크기
            reward_scaling: 보상 스케일링 팩터
        """
        self.df = df.copy()
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage
        self.window_size = window_size
        self.reward_scaling = reward_scaling

        # 기술지표 계산
        self._compute_indicators()

        # 상태 변수
        self.current_step = 0
        self.cash = initial_cash
        self.position = 0.0
        self.entry_price = 0.0
        self.trade_history: List[TradeRecord] = []

        # 포트폴리오 가치 히스토리
        self.portfolio_values: List[float] = []

        # 행동/관측 공간 (Gymnasium 호환)
        self.action_space_size = len(self.ACTIONS)
        self.observation_size = 15  # 상태 벡터 크기

        logger.info(
            f"TradingEnvironment 초기화: {len(df)}일, "
            f"initial_cash={initial_cash:,.0f}"
        )

    def _compute_indicators(self):
        """기술지표 계산"""
        df = self.df

        # 수익률
        df['returns'] = df['close'].pct_change()
        df['returns_5d'] = df['close'].pct_change(5)
        df['returns_20d'] = df['close'].pct_change(20)

        # RSI (14일)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = exp12 - exp26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

        # Bollinger Bands (20일)
        df['bb_middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * bb_std
        df['bb_lower'] = df['bb_middle'] - 2 * bb_std

        # 정규화된 가격 위치
        df['price_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # NaN 채우기
        df.bfill(inplace=True)
        df.fillna(0, inplace=True)

        self.df = df

    def reset(self, seed: Optional[int] = None) -> Tuple[np.ndarray, Dict]:
        """환경 초기화

        Args:
            seed: 랜덤 시드

        Returns:
            (observation, info)
        """
        if seed is not None:
            np.random.seed(seed)

        self.current_step = self.window_size
        self.cash = self.initial_cash
        self.position = 0.0
        self.entry_price = 0.0
        self.trade_history = []
        self.portfolio_values = [self.initial_cash]

        obs = self._get_observation()
        info = self._get_info()

        return obs, info

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """환경 스텝 실행

        Args:
            action: 행동 인덱스

        Returns:
            (observation, reward, terminated, truncated, info)
        """
        # 현재 가격
        current_price = self.df['close'].iloc[self.current_step]
        prev_total_value = self._get_total_value(current_price)

        # 행동 실행
        action_name, ratio = self.ACTIONS.get(action, ('hold', 0.0))
        self._execute_action(action_name, ratio, current_price)

        # 스텝 진행
        self.current_step += 1

        # 종료 조건
        terminated = self.current_step >= len(self.df) - 1
        truncated = self._get_total_value(current_price) <= self.initial_cash * 0.5  # 50% 손실

        # 새로운 가격으로 포트폴리오 가치 계산
        if not terminated:
            new_price = self.df['close'].iloc[self.current_step]
        else:
            new_price = current_price

        new_total_value = self._get_total_value(new_price)
        self.portfolio_values.append(new_total_value)

        # 보상 계산
        reward = self._calculate_reward(prev_total_value, new_total_value)

        # 관측, 정보
        obs = self._get_observation()
        info = self._get_info()

        return obs, reward, terminated, truncated, info

    def _execute_action(self, action_name: str, ratio: float, price: float):
        """행동 실행"""
        if action_name == 'hold':
            return

        # 슬리피지 적용
        if action_name == 'buy':
            exec_price = price * (1 + self.slippage)
        else:
            exec_price = price * (1 - self.slippage)

        cash_before = self.cash
        position_before = self.position

        if action_name == 'buy':
            # 매수: 현금의 ratio% 사용
            buy_amount = self.cash * ratio
            commission = buy_amount * self.commission
            actual_buy = buy_amount - commission
            quantity = actual_buy / exec_price

            if quantity > 0:
                self.cash -= buy_amount
                self.position += quantity
                if self.entry_price == 0:
                    self.entry_price = exec_price
                else:
                    # 평균 매입가 갱신
                    total_cost = self.entry_price * position_before + exec_price * quantity
                    self.entry_price = total_cost / self.position

        elif action_name == 'sell':
            # 매도: 포지션의 ratio% 매도
            sell_quantity = self.position * ratio

            if sell_quantity > 0:
                sell_value = sell_quantity * exec_price
                commission = sell_value * self.commission
                actual_receive = sell_value - commission

                self.position -= sell_quantity
                self.cash += actual_receive

                if self.position < 0.0001:  # 거의 0이면 정리
                    self.position = 0.0
                    self.entry_price = 0.0

        # 거래 기록
        record = TradeRecord(
            step=self.current_step,
            action=list(self.ACTIONS.keys())[
                list(self.ACTIONS.values()).index((action_name, ratio))
            ],
            action_name=f"{action_name}_{int(ratio*100)}%",
            price=exec_price,
            quantity=abs(self.position - position_before),
            cash_before=cash_before,
            cash_after=self.cash,
            position_before=position_before,
            position_after=self.position,
            total_value=self._get_total_value(price),
            reward=0.0  # 나중에 업데이트
        )
        self.trade_history.append(record)

    def _get_total_value(self, price: float) -> float:
        """총 자산 가치"""
        return self.cash + self.position * price

    def _calculate_reward(self, prev_value: float, new_value: float) -> float:
        """보상 계산"""
        # 기본 보상: 수익률
        returns = (new_value - prev_value) / prev_value

        # 샤프비율 기반 보상 (변동성 패널티)
        if len(self.portfolio_values) > 5:
            recent_returns = np.diff(self.portfolio_values[-6:]) / self.portfolio_values[-6:-1]
            volatility = np.std(recent_returns) if len(recent_returns) > 1 else 0.01
            risk_adjusted = returns / (volatility + 0.001)
        else:
            risk_adjusted = returns

        # 스케일링
        reward = risk_adjusted * self.reward_scaling

        # 거래 패널티 (과다 거래 방지)
        if len(self.trade_history) > 0:
            last_trade = self.trade_history[-1]
            if last_trade.step == self.current_step - 1:
                reward -= 0.1  # 연속 거래 패널티

        return float(reward)

    def _get_observation(self) -> np.ndarray:
        """관측 벡터 생성"""
        row = self.df.iloc[self.current_step]
        price = row['close']
        total_value = self._get_total_value(price)

        # 포지션 비율
        position_ratio = (self.position * price) / total_value if total_value > 0 else 0

        # 수익률
        if self.entry_price > 0:
            unrealized_pnl = (price - self.entry_price) / self.entry_price
        else:
            unrealized_pnl = 0.0

        obs = np.array([
            # 포트폴리오 상태 (정규화)
            self.cash / self.initial_cash,
            position_ratio,
            unrealized_pnl,
            total_value / self.initial_cash,

            # 기술지표 (정규화)
            row['rsi'] / 100,
            row['macd'] / price * 100,
            row['macd_signal'] / price * 100,
            row.get('price_position', 0.5),

            # 수익률
            row['returns'] if not np.isnan(row['returns']) else 0,
            row['returns_5d'] if not np.isnan(row['returns_5d']) else 0,
            row['returns_20d'] if not np.isnan(row['returns_20d']) else 0,

            # 거래량
            row['volume'] / self.df['volume'].mean() if self.df['volume'].mean() > 0 else 1,

            # 시간 정보
            self.current_step / len(self.df),

            # 변동성
            self.df['close'].iloc[max(0, self.current_step-20):self.current_step+1].std() / price,

            # 추세
            (price - self.df['close'].iloc[max(0, self.current_step-20)]) / price,
        ], dtype=np.float32)

        # NaN/Inf 처리
        obs = np.nan_to_num(obs, nan=0.0, posinf=1.0, neginf=-1.0)
        obs = np.clip(obs, -10, 10)

        return obs

    def _get_info(self) -> Dict[str, Any]:
        """추가 정보"""
        price = self.df['close'].iloc[self.current_step]
        total_value = self._get_total_value(price)

        return {
            'step': self.current_step,
            'date': self.df.index[self.current_step] if hasattr(self.df.index, '__getitem__') else self.current_step,
            'price': price,
            'cash': self.cash,
            'position': self.position,
            'total_value': total_value,
            'returns': (total_value - self.initial_cash) / self.initial_cash,
            'trade_count': len(self.trade_history),
        }

    def get_portfolio_stats(self) -> Dict[str, float]:
        """포트폴리오 통계"""
        if len(self.portfolio_values) < 2:
            return {}

        values = np.array(self.portfolio_values)
        returns = np.diff(values) / values[:-1]

        total_return = (values[-1] - values[0]) / values[0]

        # 샤프비율 (연율화)
        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0.0

        # 최대 낙폭
        peak = np.maximum.accumulate(values)
        drawdown = (peak - values) / peak
        max_drawdown = np.max(drawdown)

        # 승률
        if len(self.trade_history) > 0:
            wins = sum(1 for t in self.trade_history if t.reward > 0)
            win_rate = wins / len(self.trade_history)
        else:
            win_rate = 0.0

        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'trade_count': len(self.trade_history),
            'final_value': values[-1],
        }

    def render(self, mode: str = 'human'):
        """환경 렌더링"""
        info = self._get_info()
        print(
            f"Step {info['step']}: "
            f"Price={info['price']:,.0f}, "
            f"Cash={info['cash']:,.0f}, "
            f"Position={info['position']:.4f}, "
            f"Total={info['total_value']:,.0f}, "
            f"Returns={info['returns']*100:.2f}%"
        )


# Gymnasium 래퍼 (gym.Env 호환)
if GYMNASIUM_AVAILABLE:
    class GymTradingEnv(gym.Env):
        """Gymnasium 호환 트레이딩 환경"""

        metadata = {'render_modes': ['human']}

        def __init__(self, df: pd.DataFrame, **kwargs):
            super().__init__()
            self.env = TradingEnvironment(df, **kwargs)

            # 행동 공간
            self.action_space = spaces.Discrete(self.env.action_space_size)

            # 관측 공간
            self.observation_space = spaces.Box(
                low=-10.0,
                high=10.0,
                shape=(self.env.observation_size,),
                dtype=np.float32
            )

        def reset(self, seed=None, options=None):
            super().reset(seed=seed)
            return self.env.reset(seed=seed)

        def step(self, action):
            return self.env.step(action)

        def render(self):
            return self.env.render()

        def get_portfolio_stats(self):
            return self.env.get_portfolio_stats()

else:
    class GymTradingEnv:
        """GymTradingEnv 더미 (Gymnasium 필요)"""
        def __init__(self, *args, **kwargs):
            raise ImportError("Gymnasium이 설치되어 있지 않습니다.")


def create_sample_env(days: int = 500) -> TradingEnvironment:
    """테스트용 샘플 환경 생성"""
    np.random.seed(42)

    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    price = 50000
    prices = []

    for _ in range(days):
        price *= (1 + np.random.randn() * 0.02)
        prices.append(price)

    prices = np.array(prices)

    df = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.randn(days) * 0.005),
        'high': prices * (1 + np.abs(np.random.randn(days)) * 0.01),
        'low': prices * (1 - np.abs(np.random.randn(days)) * 0.01),
        'close': prices,
        'volume': np.random.randint(100000, 10000000, days)
    }).set_index('date')

    return TradingEnvironment(df)
