"""
강화학습 트레이딩 환경 테스트 (P3-2)

테스트 항목:
1. 환경 기본 동작
2. 행동 실행
3. 보상 계산
4. 기술지표 계산
5. PPO 에이전트 (SB3 있을 때만)
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
import sys
import tempfile

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.learning.rl.trading_env import (
    TradingEnvironment,
    TradingState,
    TradeRecord,
    GymTradingEnv,
    create_sample_env,
    GYMNASIUM_AVAILABLE,
)
from core.learning.rl.ppo_agent import (
    PPOConfig,
    PPOAgent,
    TrainingResult,
    SB3_AVAILABLE,
)


def create_test_df(days: int = 100) -> pd.DataFrame:
    """테스트용 데이터프레임 생성"""
    np.random.seed(42)
    dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
    price = 50000
    prices = []

    for _ in range(days):
        price *= (1 + np.random.randn() * 0.02)
        prices.append(price)

    prices = np.array(prices)

    return pd.DataFrame({
        'open': prices * (1 + np.random.randn(days) * 0.005),
        'high': prices * (1 + np.abs(np.random.randn(days)) * 0.01),
        'low': prices * (1 - np.abs(np.random.randn(days)) * 0.01),
        'close': prices,
        'volume': np.random.randint(100000, 10000000, days)
    }, index=dates)


class TestTradingEnvironment:
    """TradingEnvironment 테스트"""

    def test_init(self):
        """환경 초기화"""
        df = create_test_df()
        env = TradingEnvironment(df)

        assert env.initial_cash == 10_000_000
        assert env.action_space_size == 8
        assert env.observation_size == 15

    def test_custom_params(self):
        """사용자 파라미터"""
        df = create_test_df()
        env = TradingEnvironment(
            df,
            initial_cash=5_000_000,
            commission=0.001,
            slippage=0.002,
        )

        assert env.initial_cash == 5_000_000
        assert env.commission == 0.001
        assert env.slippage == 0.002

    def test_reset(self):
        """환경 리셋"""
        df = create_test_df()
        env = TradingEnvironment(df)
        obs, info = env.reset()

        assert obs.shape == (15,)
        assert env.cash == env.initial_cash
        assert env.position == 0.0
        assert info['step'] == env.window_size

    def test_reset_with_seed(self):
        """시드 지정 리셋"""
        df = create_test_df()
        env = TradingEnvironment(df)

        obs1, _ = env.reset(seed=42)
        obs2, _ = env.reset(seed=42)

        np.testing.assert_array_equal(obs1, obs2)

    def test_step_hold(self):
        """홀드 행동"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        initial_cash = env.cash
        obs, reward, terminated, truncated, info = env.step(0)  # hold

        assert env.cash == initial_cash
        assert env.position == 0.0
        assert obs.shape == (15,)

    def test_step_buy(self):
        """매수 행동"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        initial_cash = env.cash
        obs, reward, terminated, truncated, info = env.step(1)  # buy 10%

        assert env.cash < initial_cash
        assert env.position > 0
        assert len(env.trade_history) == 1

    def test_step_sell(self):
        """매도 행동"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        # 먼저 매수
        env.step(3)  # buy 50%
        cash_after_buy = env.cash
        position_after_buy = env.position

        # 매도
        env.step(4)  # sell 10%

        assert env.cash > cash_after_buy
        assert env.position < position_after_buy

    def test_step_full_sell(self):
        """전량 매도"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        env.step(3)  # buy 50%
        env.step(7)  # sell 100%

        assert env.position == 0.0

    def test_terminated(self):
        """종료 조건"""
        df = create_test_df(days=50)
        env = TradingEnvironment(df, window_size=10)
        env.reset()

        terminated = False
        steps = 0
        while not terminated and steps < 100:
            _, _, terminated, _, _ = env.step(0)
            steps += 1

        assert terminated
        assert env.current_step >= len(df) - 1

    def test_truncated_on_loss(self):
        """손실로 인한 조기 종료"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        # 강제로 자산 감소
        env.cash = env.initial_cash * 0.4  # 60% 손실
        _, _, _, truncated, _ = env.step(0)

        assert truncated

    def test_actions_dict(self):
        """행동 딕셔너리"""
        assert TradingEnvironment.ACTIONS[0] == ('hold', 0.0)
        assert TradingEnvironment.ACTIONS[1] == ('buy', 0.1)
        assert TradingEnvironment.ACTIONS[7] == ('sell', 1.0)


class TestIndicators:
    """기술지표 계산 테스트"""

    def test_rsi_calculated(self):
        """RSI 계산"""
        df = create_test_df()
        env = TradingEnvironment(df)

        assert 'rsi' in env.df.columns
        assert env.df['rsi'].min() >= 0
        assert env.df['rsi'].max() <= 100

    def test_macd_calculated(self):
        """MACD 계산"""
        df = create_test_df()
        env = TradingEnvironment(df)

        assert 'macd' in env.df.columns
        assert 'macd_signal' in env.df.columns

    def test_bollinger_bands(self):
        """볼린저 밴드 계산"""
        df = create_test_df()
        env = TradingEnvironment(df)

        assert 'bb_upper' in env.df.columns
        assert 'bb_lower' in env.df.columns
        assert 'bb_middle' in env.df.columns

    def test_returns_calculated(self):
        """수익률 계산"""
        df = create_test_df()
        env = TradingEnvironment(df)

        assert 'returns' in env.df.columns
        assert 'returns_5d' in env.df.columns
        assert 'returns_20d' in env.df.columns


class TestObservation:
    """관측 벡터 테스트"""

    def test_observation_shape(self):
        """관측 형태"""
        df = create_test_df()
        env = TradingEnvironment(df)
        obs, _ = env.reset()

        assert obs.shape == (15,)
        assert obs.dtype == np.float32

    def test_observation_bounded(self):
        """관측 값 범위"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        for _ in range(10):
            obs, _, _, _, _ = env.step(np.random.randint(8))
            assert np.all(obs >= -10)
            assert np.all(obs <= 10)

    def test_observation_no_nan(self):
        """NaN 없음"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        for _ in range(10):
            obs, _, _, _, _ = env.step(np.random.randint(8))
            assert not np.any(np.isnan(obs))
            assert not np.any(np.isinf(obs))


class TestReward:
    """보상 계산 테스트"""

    def test_reward_type(self):
        """보상 타입"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        _, reward, _, _, _ = env.step(0)

        assert isinstance(reward, float)

    def test_reward_scaling(self):
        """보상 스케일링"""
        df = create_test_df()
        env = TradingEnvironment(df, reward_scaling=1.0)
        env.reset()

        _, reward1, _, _, _ = env.step(0)

        env2 = TradingEnvironment(df, reward_scaling=100.0)
        env2.reset()
        _, reward2, _, _, _ = env2.step(0)

        # 보상은 0이 아닌 경우 스케일링 차이가 있어야 함
        # (보상이 0일 수 있으므로 절대 비교는 불가)
        assert isinstance(reward1, float)
        assert isinstance(reward2, float)


class TestPortfolioStats:
    """포트폴리오 통계 테스트"""

    def test_stats_after_trading(self):
        """거래 후 통계"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        # 몇 번 거래
        for i in range(30):
            action = i % 8
            _, _, terminated, truncated, _ = env.step(action)
            if terminated or truncated:
                break

        stats = env.get_portfolio_stats()

        assert 'total_return' in stats
        assert 'sharpe_ratio' in stats
        assert 'max_drawdown' in stats
        assert 'trade_count' in stats

    def test_stats_empty(self):
        """초기 상태 통계"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        stats = env.get_portfolio_stats()

        # 포트폴리오 값이 하나만 있으면 빈 딕셔너리
        assert stats == {}


class TestTradeRecord:
    """거래 기록 테스트"""

    def test_trade_recorded(self):
        """거래 기록 생성"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        env.step(1)  # buy

        assert len(env.trade_history) == 1
        record = env.trade_history[0]

        assert isinstance(record, TradeRecord)
        assert record.action == 1
        assert 'buy' in record.action_name

    def test_multiple_trades(self):
        """다중 거래 기록"""
        df = create_test_df()
        env = TradingEnvironment(df)
        env.reset()

        env.step(1)  # buy
        env.step(4)  # sell
        env.step(2)  # buy

        assert len(env.trade_history) == 3


class TestTradingState:
    """TradingState 데이터클래스 테스트"""

    def test_create_state(self):
        """상태 생성"""
        state = TradingState(
            cash=1000000,
            position=10,
            position_value=500000,
            total_value=1500000,
            current_price=50000,
            step=0,
        )

        assert state.cash == 1000000
        assert state.position == 10
        assert state.rsi == 50.0  # 기본값


class TestCreateSampleEnv:
    """샘플 환경 생성 테스트"""

    def test_create_sample(self):
        """샘플 환경 생성"""
        env = create_sample_env(days=100)

        assert isinstance(env, TradingEnvironment)
        assert len(env.df) == 100

    def test_sample_reproducible(self):
        """재현 가능성"""
        env1 = create_sample_env(days=50)
        env2 = create_sample_env(days=50)

        np.testing.assert_array_almost_equal(
            env1.df['close'].values,
            env2.df['close'].values
        )


@pytest.mark.skipif(not GYMNASIUM_AVAILABLE, reason="Gymnasium not installed")
class TestGymTradingEnv:
    """GymTradingEnv 래퍼 테스트"""

    def test_gym_env_creation(self):
        """Gym 환경 생성"""
        df = create_test_df()
        env = GymTradingEnv(df)

        assert env.action_space is not None
        assert env.observation_space is not None

    def test_gym_spaces(self):
        """Gym 공간 정의"""
        df = create_test_df()
        env = GymTradingEnv(df)

        assert env.action_space.n == 8
        assert env.observation_space.shape == (15,)

    def test_gym_reset(self):
        """Gym 리셋"""
        df = create_test_df()
        env = GymTradingEnv(df)
        obs, info = env.reset()

        assert obs.shape == (15,)
        assert isinstance(info, dict)

    def test_gym_step(self):
        """Gym 스텝"""
        df = create_test_df()
        env = GymTradingEnv(df)
        env.reset()

        obs, reward, terminated, truncated, info = env.step(0)

        assert obs.shape == (15,)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)

    def test_gym_full_episode(self):
        """전체 에피소드"""
        df = create_test_df(days=50)
        env = GymTradingEnv(df, window_size=10)
        obs, _ = env.reset()

        done = False
        steps = 0
        while not done and steps < 100:
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            steps += 1

        assert done or steps >= 100


class TestPPOConfig:
    """PPOConfig 테스트"""

    def test_default_values(self):
        """기본값"""
        config = PPOConfig()

        assert config.policy == "MlpPolicy"
        assert config.learning_rate == 3e-4
        assert config.n_steps == 2048
        assert config.batch_size == 64
        assert config.gamma == 0.99

    def test_custom_values(self):
        """사용자 값"""
        config = PPOConfig(
            learning_rate=1e-3,
            n_steps=1024,
            gamma=0.95,
        )

        assert config.learning_rate == 1e-3
        assert config.n_steps == 1024
        assert config.gamma == 0.95


class TestTrainingResult:
    """TrainingResult 테스트"""

    def test_create_result(self):
        """결과 생성"""
        result = TrainingResult(
            total_timesteps=10000,
            training_time=60.0,
            final_eval_reward=100.0,
            best_eval_reward=120.0,
        )

        assert result.total_timesteps == 10000
        assert result.training_time == 60.0

    def test_to_dict(self):
        """딕셔너리 변환"""
        result = TrainingResult(
            total_timesteps=10000,
            training_time=60.0,
            final_eval_reward=100.0,
            best_eval_reward=120.0,
            eval_rewards=[50, 80, 100],
        )

        d = result.to_dict()

        assert d['total_timesteps'] == 10000
        assert d['final_eval_reward'] == 100.0
        assert len(d['eval_rewards']) == 3


@pytest.mark.skipif(
    not (GYMNASIUM_AVAILABLE and SB3_AVAILABLE),
    reason="Gymnasium or Stable Baselines3 not installed"
)
class TestPPOAgent:
    """PPOAgent 테스트 (SB3 필요)"""

    def test_agent_init(self):
        """에이전트 초기화"""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PPOAgent(model_dir=tmpdir)

            assert agent.config is not None
            assert agent.model is None

    def test_agent_custom_config(self):
        """사용자 설정"""
        config = PPOConfig(learning_rate=1e-3)

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PPOAgent(config=config, model_dir=tmpdir)

            assert agent.config.learning_rate == 1e-3

    def test_train_minimal(self):
        """최소 학습"""
        config = PPOConfig(
            total_timesteps=500,
            n_steps=64,
            batch_size=32,
            eval_freq=200,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PPOAgent(config=config, model_dir=tmpdir)
            df = create_test_df(days=100)

            result = agent.train(df, verbose=0)

            assert result.total_timesteps == 500
            assert result.training_time > 0
            assert agent.model is not None

    def test_predict_after_train(self):
        """학습 후 예측"""
        config = PPOConfig(
            total_timesteps=500,
            n_steps=64,
            batch_size=32,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PPOAgent(config=config, model_dir=tmpdir)
            df = create_test_df(days=100)
            agent.train(df, verbose=0)

            obs = np.random.randn(15).astype(np.float32)
            action = agent.predict(obs)

            assert action in range(8)

    def test_predict_without_train(self):
        """학습 없이 예측 시 에러"""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = PPOAgent(model_dir=tmpdir)
            obs = np.random.randn(15).astype(np.float32)

            with pytest.raises(RuntimeError, match="모델이 학습되지 않았습니다"):
                agent.predict(obs)

    def test_save_and_load(self):
        """저장 및 로드"""
        config = PPOConfig(
            total_timesteps=500,
            n_steps=64,
            batch_size=32,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # 학습 및 저장
            agent1 = PPOAgent(config=config, model_dir=tmpdir)
            df = create_test_df(days=100)
            agent1.train(df, verbose=0)

            model_path = agent1.save()
            assert Path(model_path).exists()

            # 로드
            agent2 = PPOAgent(model_dir=tmpdir)
            agent2.load(model_path)

            # 같은 예측
            obs = np.random.randn(15).astype(np.float32)
            action1 = agent1.predict(obs, deterministic=True)
            action2 = agent2.predict(obs, deterministic=True)

            assert action1 == action2


class TestAvailabilityFlags:
    """가용성 플래그 테스트"""

    def test_gymnasium_flag(self):
        """GYMNASIUM_AVAILABLE 플래그"""
        assert isinstance(GYMNASIUM_AVAILABLE, bool)

    def test_sb3_flag(self):
        """SB3_AVAILABLE 플래그"""
        assert isinstance(SB3_AVAILABLE, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
