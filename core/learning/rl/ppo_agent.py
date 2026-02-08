"""
PPO 에이전트 (P3-2)

Stable Baselines3 PPO 래퍼

Features:
- 학습/평가
- 모델 저장/로드
- 하이퍼파라미터 설정
"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

# Stable Baselines3는 선택적 의존성
try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import EvalCallback, BaseCallback
    from stable_baselines3.common.vec_env import DummyVecEnv
    SB3_AVAILABLE = True
except ImportError:
    SB3_AVAILABLE = False
    PPO = None
    DummyVecEnv = None

from .trading_env import GymTradingEnv, GYMNASIUM_AVAILABLE
from core.utils.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class PPOConfig:
    """PPO 하이퍼파라미터 설정"""
    # 네트워크
    policy: str = "MlpPolicy"
    hidden_sizes: tuple = (256, 256)

    # 학습
    learning_rate: float = 3e-4
    n_steps: int = 2048
    batch_size: int = 64
    n_epochs: int = 10
    gamma: float = 0.99
    gae_lambda: float = 0.95

    # PPO 특정
    clip_range: float = 0.2
    ent_coef: float = 0.01
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5

    # 학습 설정
    total_timesteps: int = 100_000
    eval_freq: int = 10_000
    n_eval_episodes: int = 5

    # 저장
    model_dir: str = "models/ppo"


@dataclass
class TrainingResult:
    """학습 결과"""
    total_timesteps: int
    training_time: float  # seconds
    final_eval_reward: float
    best_eval_reward: float
    eval_rewards: List[float] = field(default_factory=list)
    model_path: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'total_timesteps': self.total_timesteps,
            'training_time': self.training_time,
            'final_eval_reward': self.final_eval_reward,
            'best_eval_reward': self.best_eval_reward,
            'eval_rewards': self.eval_rewards,
            'model_path': self.model_path,
        }


class RewardLoggerCallback(BaseCallback if SB3_AVAILABLE else object):
    """보상 기록 콜백"""

    def __init__(self, verbose: int = 0):
        if SB3_AVAILABLE:
            super().__init__(verbose)
        self.episode_rewards: List[float] = []
        self.current_rewards: List[float] = []

    def _on_step(self) -> bool:
        if 'rewards' in self.locals:
            self.current_rewards.append(self.locals['rewards'][0])

        if 'dones' in self.locals and self.locals['dones'][0]:
            self.episode_rewards.append(sum(self.current_rewards))
            self.current_rewards = []

        return True


if SB3_AVAILABLE and GYMNASIUM_AVAILABLE:

    class PPOAgent:
        """PPO 에이전트 (Stable Baselines3 래퍼)

        Usage:
            agent = PPOAgent(config)
            result = agent.train(train_df, eval_df)

            action = agent.predict(observation)
            agent.save("model.zip")
        """

        def __init__(
            self,
            config: Optional[PPOConfig] = None,
            model_dir: Optional[str] = None,
        ):
            """초기화

            Args:
                config: PPO 설정
                model_dir: 모델 저장 디렉토리
            """
            self.config = config or PPOConfig()
            self.model_dir = Path(model_dir or self.config.model_dir)
            self.model_dir.mkdir(parents=True, exist_ok=True)

            self.model: Optional[PPO] = None
            self.train_env = None
            self.eval_env = None

            logger.info(f"PPOAgent 초기화: model_dir={self.model_dir}")

        def _create_env(self, df: pd.DataFrame, **kwargs) -> DummyVecEnv:
            """환경 생성"""
            def make_env():
                return GymTradingEnv(df, **kwargs)
            return DummyVecEnv([make_env])

        def train(
            self,
            train_df: pd.DataFrame,
            eval_df: Optional[pd.DataFrame] = None,
            total_timesteps: Optional[int] = None,
            progress_callback: Optional[Callable[[int, int], None]] = None,
            verbose: int = 1,
        ) -> TrainingResult:
            """학습

            Args:
                train_df: 학습 데이터
                eval_df: 평가 데이터 (없으면 학습 데이터 사용)
                total_timesteps: 총 학습 스텝
                progress_callback: 진행 콜백
                verbose: 출력 레벨

            Returns:
                TrainingResult
            """
            start_time = datetime.now()

            # 환경 생성
            self.train_env = self._create_env(train_df)
            self.eval_env = self._create_env(eval_df if eval_df is not None else train_df)

            # PPO 모델 생성
            policy_kwargs = dict(
                net_arch=list(self.config.hidden_sizes)
            )

            self.model = PPO(
                policy=self.config.policy,
                env=self.train_env,
                learning_rate=self.config.learning_rate,
                n_steps=self.config.n_steps,
                batch_size=self.config.batch_size,
                n_epochs=self.config.n_epochs,
                gamma=self.config.gamma,
                gae_lambda=self.config.gae_lambda,
                clip_range=self.config.clip_range,
                ent_coef=self.config.ent_coef,
                vf_coef=self.config.vf_coef,
                max_grad_norm=self.config.max_grad_norm,
                policy_kwargs=policy_kwargs,
                verbose=verbose,
            )

            # 콜백
            callbacks = []
            reward_callback = RewardLoggerCallback(verbose=verbose)
            callbacks.append(reward_callback)

            # 평가 콜백
            eval_callback = EvalCallback(
                self.eval_env,
                best_model_save_path=str(self.model_dir / "best"),
                log_path=str(self.model_dir / "logs"),
                eval_freq=self.config.eval_freq,
                n_eval_episodes=self.config.n_eval_episodes,
                deterministic=True,
            )
            callbacks.append(eval_callback)

            # 학습
            timesteps = total_timesteps or self.config.total_timesteps
            logger.info(f"PPO 학습 시작: {timesteps:,} steps")

            self.model.learn(
                total_timesteps=timesteps,
                callback=callbacks,
            )

            # 결과
            training_time = (datetime.now() - start_time).total_seconds()

            # 최종 평가
            final_reward = self._evaluate(self.eval_env, n_episodes=10)

            # 베스트 모델 로드
            best_model_path = self.model_dir / "best" / "best_model.zip"
            if best_model_path.exists():
                best_model = PPO.load(str(best_model_path))
                self.model = best_model
                best_reward = final_reward  # 실제로는 콜백에서 기록
            else:
                best_reward = final_reward

            result = TrainingResult(
                total_timesteps=timesteps,
                training_time=training_time,
                final_eval_reward=final_reward,
                best_eval_reward=best_reward,
                eval_rewards=reward_callback.episode_rewards,
                model_path=str(best_model_path) if best_model_path.exists() else None,
            )

            logger.info(
                f"PPO 학습 완료: {training_time:.1f}초, "
                f"final_reward={final_reward:.2f}"
            )

            return result

        def _evaluate(
            self,
            env: DummyVecEnv,
            n_episodes: int = 10,
        ) -> float:
            """평가"""
            episode_rewards = []

            for _ in range(n_episodes):
                obs = env.reset()
                done = False
                total_reward = 0.0

                while not done:
                    action, _ = self.model.predict(obs, deterministic=True)
                    obs, reward, done, info = env.step(action)
                    total_reward += reward[0]
                    done = done[0]

                episode_rewards.append(total_reward)

            return float(np.mean(episode_rewards))

        def predict(
            self,
            observation: np.ndarray,
            deterministic: bool = True,
        ) -> int:
            """행동 예측

            Args:
                observation: 관측 벡터
                deterministic: 결정적 정책 사용

            Returns:
                행동 인덱스
            """
            if self.model is None:
                raise RuntimeError("모델이 학습되지 않았습니다")

            if observation.ndim == 1:
                observation = observation.reshape(1, -1)

            action, _ = self.model.predict(observation, deterministic=deterministic)
            return int(action[0])

        def evaluate(
            self,
            df: pd.DataFrame,
            n_episodes: int = 10,
        ) -> Dict[str, float]:
            """평가

            Args:
                df: 평가 데이터
                n_episodes: 에피소드 수

            Returns:
                평가 메트릭
            """
            if self.model is None:
                raise RuntimeError("모델이 학습되지 않았습니다")

            env = self._create_env(df)

            all_rewards = []
            all_stats = []

            for _ in range(n_episodes):
                obs = env.reset()
                done = False
                total_reward = 0.0

                while not done:
                    action, _ = self.model.predict(obs, deterministic=True)
                    obs, reward, done, info = env.step(action)
                    total_reward += reward[0]
                    done = done[0]

                all_rewards.append(total_reward)
                stats = env.envs[0].get_portfolio_stats()
                all_stats.append(stats)

            # 평균 통계
            return {
                'mean_reward': float(np.mean(all_rewards)),
                'std_reward': float(np.std(all_rewards)),
                'mean_return': float(np.mean([s.get('total_return', 0) for s in all_stats])),
                'mean_sharpe': float(np.mean([s.get('sharpe_ratio', 0) for s in all_stats])),
                'mean_max_drawdown': float(np.mean([s.get('max_drawdown', 0) for s in all_stats])),
                'n_episodes': n_episodes,
            }

        def save(self, path: Optional[str] = None) -> str:
            """모델 저장

            Args:
                path: 저장 경로 (없으면 기본 경로)

            Returns:
                저장된 경로
            """
            if self.model is None:
                raise RuntimeError("모델이 학습되지 않았습니다")

            if path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = str(self.model_dir / f"ppo_{timestamp}.zip")

            self.model.save(path)
            logger.info(f"모델 저장됨: {path}")
            return path

        def load(self, path: str):
            """모델 로드

            Args:
                path: 모델 경로
            """
            self.model = PPO.load(path)
            logger.info(f"모델 로드됨: {path}")

        def get_action_distribution(
            self,
            observation: np.ndarray,
        ) -> np.ndarray:
            """행동 분포 반환

            Args:
                observation: 관측 벡터

            Returns:
                행동 확률 분포
            """
            if self.model is None:
                raise RuntimeError("모델이 학습되지 않았습니다")

            if observation.ndim == 1:
                observation = observation.reshape(1, -1)

            # 정책에서 분포 추출
            obs_tensor = self.model.policy.obs_to_tensor(observation)[0]
            distribution = self.model.policy.get_distribution(obs_tensor)
            probs = distribution.distribution.probs.detach().cpu().numpy()[0]

            return probs

else:
    # Dummy classes when dependencies not installed
    class PPOAgent:
        """PPOAgent 더미 클래스 (stable-baselines3, gymnasium 필요)"""

        def __init__(self, *args, **kwargs):
            if not GYMNASIUM_AVAILABLE:
                raise ImportError(
                    "Gymnasium이 설치되어 있지 않습니다. "
                    "pip install gymnasium"
                )
            if not SB3_AVAILABLE:
                raise ImportError(
                    "Stable Baselines3가 설치되어 있지 않습니다. "
                    "pip install stable-baselines3"
                )
