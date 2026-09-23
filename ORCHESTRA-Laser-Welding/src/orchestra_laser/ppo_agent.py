from __future__ import annotations

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except Exception:  # pragma: no cover - handled at runtime in train_ppo.py
    gym = None
    spaces = None

from .scheduling_env import LaserMaintenanceSchedulingEnv


if gym is not None:
    _BaseEnv = gym.Env
else:
    _BaseEnv = object


class GymLaserMaintenanceEnv(_BaseEnv):
    """Gymnasium-compatible wrapper for Stable-Baselines3 PPO."""

    metadata = {"render_modes": []}

    def __init__(self, data, reward_weights: dict, episode_length: int = 120, seed: int = 42):
        if gym is None or spaces is None:
            raise ImportError(
                "PPO training requires gymnasium. Install it with: python -m pip install gymnasium stable-baselines3"
            )

        super().__init__()
        self.core = LaserMaintenanceSchedulingEnv(
            data=data,
            reward_weights=reward_weights,
            episode_length=episode_length,
            seed=seed,
        )
        self.action_space = spaces.Discrete(5)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(7,), dtype=np.float32)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        if seed is not None:
            self.core.rng = np.random.default_rng(seed)
        obs = self.core.reset().astype(np.float32)
        return obs, {}

    def step(self, action):
        obs, reward, done, info = self.core.step(int(action))
        terminated = bool(done and info.get("failure", False))
        truncated = bool(done and not terminated)
        return obs.astype(np.float32), float(reward), terminated, truncated, info

    def render(self):
        return None


def evaluate_ppo_model(model, env: GymLaserMaintenanceEnv, n_episodes: int = 10) -> dict:
    totals = []
    for _ in range(n_episodes):
        obs, _ = env.reset()
        done = False
        episode = {"reward": 0.0, "downtime": 0.0, "cost": 0.0, "failures": 0, "unnecessary": 0, "action_do_nothing": 0, "action_inspect": 0, "action_minor_maintenance": 0, "action_major_maintenance": 0, "action_urgent_intervention": 0}
        while not done:
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            episode["reward"] += float(reward)
            episode["downtime"] += float(info.get("downtime", 0.0))
            episode["cost"] += float(info.get("cost", 0.0))
            episode["failures"] += int(info.get("failure", False))
            episode["unnecessary"] += int(info.get("unnecessary", False))
            episode[f"action_{info.get('action_name', 'unknown')}"] += 1
        totals.append(episode)

    return {
        f"mean_{key}": float(np.mean([episode[key] for episode in totals]))
        for key in totals[0]
    } | {
        f"std_{key}": float(np.std([episode[key] for episode in totals]))
        for key in totals[0]
    }


