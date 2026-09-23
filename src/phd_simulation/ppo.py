from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .environment import LaserWeldingSchedulingEnv


def make_gym_env(data: pd.DataFrame, reward_weights: dict[str, float], episode_length: int, seed: int):
    try:
        import gymnasium as gym
        from gymnasium import spaces
    except Exception as exc:
        raise ImportError("PPO requires gymnasium and stable-baselines3") from exc

    class _GymEnv(gym.Env):
        metadata = {"render_modes": []}

        def __init__(self):
            super().__init__()
            self.core = LaserWeldingSchedulingEnv(data, reward_weights, episode_length=episode_length, seed=seed)
            self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(7,), dtype=np.float32)
            self.action_space = spaces.Discrete(5)

        def reset(self, *, seed: int | None = None, options: dict[str, Any] | None = None):
            super().reset(seed=seed)
            return self.core.reset(seed=seed), {}

        def step(self, action: int):
            observation, reward, done, info = self.core.step(int(action))
            return observation, float(reward), False, bool(done), info

        def render(self):
            return None

    return _GymEnv()


def train_ppo(
    data: pd.DataFrame,
    *,
    reward_weights: dict[str, float],
    episode_length: int,
    seed: int,
    total_timesteps: int,
    model_path: str | Path,
):
    try:
        from stable_baselines3 import PPO
    except Exception as exc:
        raise ImportError("PPO requires gymnasium and stable-baselines3") from exc

    env = make_gym_env(data, reward_weights, episode_length, seed)
    model = PPO(
        "MlpPolicy",
        env,
        seed=seed,
        verbose=0,
        n_steps=min(128, max(16, episode_length)),
        batch_size=min(64, max(8, episode_length)),
        learning_rate=2.5e-4,
        gamma=0.985,
        gae_lambda=0.95,
        ent_coef=0.01,
        device="cpu",
    )
    model.learn(total_timesteps=int(total_timesteps))
    output = Path(model_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(output))
    return model, env


def evaluate_ppo(model, data: pd.DataFrame, *, reward_weights: dict[str, float], episode_length: int, seed: int, episodes: int = 20) -> tuple[pd.DataFrame, pd.DataFrame]:
    env = LaserWeldingSchedulingEnv(data, reward_weights, episode_length=episode_length, seed=seed)
    summaries: list[dict[str, object]] = []
    traces: list[pd.DataFrame] = []
    for episode in range(episodes):
        case_id = env.case_ids[episode % len(env.case_ids)]
        env.reset(case_id=case_id, seed=seed + episode)
        totals = {"policy": "ppo_trained", "seed": seed, "episode": episode, "case_id": case_id, "reward": 0.0, "downtime": 0.0, "cost": 0.0, "failures": 0.0, "unnecessary": 0.0}
        events: list[dict[str, object]] = []
        done = False
        while not done:
            observation = env.state()
            action, _ = model.predict(observation, deterministic=True)
            row = env.current_row()
            _, reward, done, info = env.step(int(action))
            events.append({"policy": "ppo_trained", "seed": seed, "episode": episode, **info, "reward": reward})
            totals["reward"] += float(reward)
            totals["downtime"] += float(info["downtime"])
            totals["cost"] += float(info["cost"])
            totals["failures"] += float(info["failure"])
            totals["unnecessary"] += float(info["unnecessary"])
        summaries.append(totals)
        traces.append(pd.DataFrame(events))
    return pd.DataFrame(summaries), pd.concat(traces, ignore_index=True) if traces else pd.DataFrame()
