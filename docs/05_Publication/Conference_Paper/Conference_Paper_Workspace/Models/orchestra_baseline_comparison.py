"""
ORCHESTRA Baseline Comparison Script

This script compares six maintenance decision strategies:

1. Reactive maintenance
2. Fixed preventive maintenance
3. XGBoost-only alert strategy
4. Rule-based scheduling
5. PPO-only scheduling without human review
6. Full ORCHESTRA with uncertainty-triggered human review

The script uses the same custom maintenance scheduling environment
as the PPO RL Scheduling Agent and exports a comparison table for
Section 5.6 Baseline Comparison.

Author: ORCHESTRA Framework Development
"""

import os
import random
from collections import Counter
from typing import Callable, Dict, Tuple

import gymnasium as gym
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from gymnasium import spaces
from stable_baselines3 import PPO


# ============================================================
# 1. Configuration
# ============================================================

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

OUTPUT_DIR = "orchestra_baseline_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DATASET_PATH = "spot_welding_dataset_100k_adjusted.csv"

PPO_MODEL_PATH = "orchestra_ppo_outputs/orchestra_ppo_scheduling_agent.zip"

EVALUATION_EPISODES = 50
EPISODE_LENGTH = 100

UNCERTAINTY_THRESHOLD = 0.60


# ============================================================
# 2. Load maintenance urgency scores
# ============================================================

def load_maintenance_scores(dataset_path: str) -> np.ndarray:
    """
    Loads maintenance urgency scores from a CSV file.

    Expected columns:
    - Predicted_Maintenance_Score
    - Predictive_Maintenance_Score

    If the dataset is not found, synthetic scores are generated.
    """

    if not os.path.exists(dataset_path):
        print("Dataset not found. Using synthetic maintenance urgency scores.")
        return np.random.beta(a=2.0, b=5.0, size=10_000)

    df = pd.read_csv(dataset_path)

    possible_columns = [
        "Predicted_Maintenance_Score",
        "Predictive_Maintenance_Score"
    ]

    score_column = None
    for col in possible_columns:
        if col in df.columns:
            score_column = col
            break

    if score_column is None:
        print("No maintenance score column found. Using synthetic maintenance urgency scores.")
        return np.random.beta(a=2.0, b=5.0, size=10_000)

    scores = df[score_column].astype(float).values

    if scores.max() > 1.0:
        scores = scores / 100.0

    scores = np.clip(scores, 0.0, 1.0)

    print(f"Loaded maintenance urgency scores from column: {score_column}")
    print(f"Number of samples loaded: {len(scores)}")

    return scores


# ============================================================
# 3. Custom ORCHESTRA maintenance environment
# ============================================================

class OrchestraMaintenanceEnv(gym.Env):
    """
    Custom Gymnasium environment for maintenance scheduling.

    State:
        [0] time_to_failure
        [1] predicted_severity
        [2] resource_availability
        [3] production_load
        [4] time_since_last_maintenance
        [5] maintenance_cost_factor
        [6] uncertainty

    Actions:
        0 = No immediate action
        1 = Immediate maintenance
        2 = Maintenance during next low-load window
        3 = Maintenance in 3 days
        4 = Maintenance in 7 days
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        maintenance_scores: np.ndarray,
        episode_length: int = 100,
        human_review_enabled: bool = True,
        uncertainty_threshold: float = 0.60,
        seed: int = 42
    ):
        super().__init__()

        self.maintenance_scores = maintenance_scores
        self.episode_length = episode_length
        self.human_review_enabled = human_review_enabled
        self.uncertainty_threshold = uncertainty_threshold

        self.rng = np.random.default_rng(seed)

        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(7,),
            dtype=np.float32
        )

        self.action_space = spaces.Discrete(5)

        self.current_step = 0
        self.current_index = 0
        self.hidden_risk = 0.0
        self.time_since_last_maintenance = 0.0

        self.episode_reward = 0.0
        self.critical_failures = 0
        self.unnecessary_maintenance = 0
        self.human_interventions = 0
        self.human_overrides = 0
        self.downtime_proxy = 0.0
        self.cost_proxy = 0.0
        self.action_history = []

        self.state = None

    def _sample_score(self) -> float:
        self.current_index = self.rng.integers(0, len(self.maintenance_scores))
        return float(self.maintenance_scores[self.current_index])

    def _generate_uncertainty(self, severity: float) -> float:
        """
        Higher uncertainty is generated around medium-severity cases,
        because those cases are more ambiguous.
        """

        medium_region = 1.0 - abs(severity - 0.5) * 2.0
        medium_region = np.clip(medium_region, 0.0, 1.0)

        random_component = self.rng.uniform(0.0, 0.35)
        uncertainty = 0.65 * medium_region + random_component

        return float(np.clip(uncertainty, 0.0, 1.0))

    def _human_review(self, severity: float, uncertainty: float) -> Tuple[float, bool, bool]:
        """
        Simulates the Human Operator Agent.

        Human review is triggered when:
        - severity is medium,
        - uncertainty is high,
        - high-risk cases are also uncertain.
        """

        medium_severity = 0.40 <= severity <= 0.70
        high_uncertainty = uncertainty >= self.uncertainty_threshold
        high_risk_ambiguous = severity >= 0.75 and uncertainty >= 0.45

        review_triggered = (
            self.human_review_enabled
            and (medium_severity or high_uncertainty or high_risk_ambiguous)
        )

        override_applied = False
        refined_severity = severity

        if review_triggered:
            self.human_interventions += 1

            correction = self.rng.normal(loc=0.0, scale=0.06)
            refined_severity = np.clip(severity + correction, 0.0, 1.0)

            if abs(refined_severity - severity) > 0.08:
                override_applied = True
                self.human_overrides += 1

        return float(refined_severity), review_triggered, override_applied

    def _get_observation(self) -> np.ndarray:
        predicted_severity = self._sample_score()

        self.hidden_risk = np.clip(
            0.75 * self.hidden_risk
            + 0.25 * predicted_severity
            + self.rng.normal(0, 0.03),
            0.0,
            1.0
        )

        uncertainty = self._generate_uncertainty(predicted_severity)

        final_severity, _, _ = self._human_review(predicted_severity, uncertainty)

        time_to_failure = 1.0 - self.hidden_risk
        resource_availability = self.rng.uniform(0.2, 1.0)
        production_load = self.rng.uniform(0.0, 1.0)
        maintenance_cost_factor = self.rng.uniform(0.3, 1.0)

        obs = np.array([
            time_to_failure,
            final_severity,
            resource_availability,
            production_load,
            self.time_since_last_maintenance,
            maintenance_cost_factor,
            uncertainty
        ], dtype=np.float32)

        return np.clip(obs, 0.0, 1.0)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        self.current_step = 0
        self.hidden_risk = self.rng.uniform(0.05, 0.35)
        self.time_since_last_maintenance = 0.0

        self.episode_reward = 0.0
        self.critical_failures = 0
        self.unnecessary_maintenance = 0
        self.human_interventions = 0
        self.human_overrides = 0
        self.downtime_proxy = 0.0
        self.cost_proxy = 0.0
        self.action_history = []

        self.state = self._get_observation()

        return self.state, {}

    def step(self, action: int):
        self.current_step += 1
        self.action_history.append(int(action))

        time_to_failure = float(self.state[0])
        severity = float(self.state[1])
        resource_availability = float(self.state[2])
        production_load = float(self.state[3])
        cost_factor = float(self.state[5])
        uncertainty = float(self.state[6])

        reward = 0.0
        unnecessary = False

        degradation_pressure = 0.02 + (0.04 * production_load) + (0.03 * severity)

        # Action 0: No immediate action
        if action == 0:
            if severity < 0.30 and uncertainty < 0.50:
                reward += 4.0
            elif severity >= 0.70:
                reward -= 14.0
            else:
                reward -= 3.0

            self.hidden_risk += degradation_pressure

        # Action 1: Immediate maintenance
        elif action == 1:
            downtime = 0.35 + 0.35 * production_load
            cost = 0.45 + 0.45 * cost_factor

            self.downtime_proxy += downtime
            self.cost_proxy += cost

            if severity >= 0.70:
                reward += 18.0
            elif 0.40 <= severity < 0.70:
                reward += 6.0
            else:
                reward -= 10.0
                unnecessary = True

            reward -= 7.0 * production_load

            self.hidden_risk = self.rng.uniform(0.05, 0.20)
            self.time_since_last_maintenance = 0.0

        # Action 2: Maintenance during next low-load window
        elif action == 2:
            downtime = 0.20 + 0.20 * production_load
            cost = 0.30 + 0.30 * cost_factor

            self.downtime_proxy += downtime
            self.cost_proxy += cost

            if 0.40 <= severity < 0.75:
                reward += 12.0
            elif severity >= 0.75:
                reward += 8.0
            else:
                reward -= 5.0
                unnecessary = True

            reward -= 3.0 * production_load

            self.hidden_risk = max(0.10, self.hidden_risk - 0.35)
            self.time_since_last_maintenance = 0.0

        # Action 3: Maintenance in 3 days
        elif action == 3:
            cost = 0.15 + 0.20 * cost_factor
            self.cost_proxy += cost

            if 0.30 <= severity < 0.60:
                reward += 7.0
            elif severity >= 0.75:
                reward -= 10.0
            else:
                reward += 1.0

            self.hidden_risk += degradation_pressure * 0.75
            self.time_since_last_maintenance += 0.03

        # Action 4: Maintenance in 7 days
        elif action == 4:
            cost = 0.10 + 0.15 * cost_factor
            self.cost_proxy += cost

            if severity < 0.30:
                reward += 5.0
            elif 0.30 <= severity < 0.60:
                reward -= 2.0
            else:
                reward -= 16.0

            self.hidden_risk += degradation_pressure * 1.25
            self.time_since_last_maintenance += 0.07

        self.hidden_risk = float(np.clip(self.hidden_risk, 0.0, 1.0))
        self.time_since_last_maintenance = float(np.clip(self.time_since_last_maintenance, 0.0, 1.0))

        # Critical failure condition
        if self.hidden_risk >= 0.95:
            self.critical_failures += 1
            reward -= 50.0

            self.hidden_risk = self.rng.uniform(0.10, 0.25)
            self.time_since_last_maintenance = 0.0

            self.downtime_proxy += 0.80
            self.cost_proxy += 0.90

        if unnecessary:
            self.unnecessary_maintenance += 1

        # Penalty for ignoring high uncertainty
        if uncertainty > self.uncertainty_threshold and action in [0, 3, 4]:
            reward -= 2.0

        self.episode_reward += reward

        self.state = self._get_observation()

        terminated = False
        truncated = self.current_step >= self.episode_length

        info = {
            "critical_failures": self.critical_failures,
            "unnecessary_maintenance": self.unnecessary_maintenance,
            "human_interventions": self.human_interventions,
            "human_overrides": self.human_overrides,
            "downtime_proxy": self.downtime_proxy,
            "cost_proxy": self.cost_proxy,
            "episode_reward": self.episode_reward
        }

        return self.state, float(reward), terminated, truncated, info


# ============================================================
# 4. Baseline strategy rules
# ============================================================

def reactive_strategy(obs: np.ndarray, step_number: int) -> int:
    """
    Reactive maintenance:
    Wait until the machine is very close to failure.
    """

    time_to_failure = obs[0]

    if time_to_failure < 0.10:
        return 1  # immediate maintenance
    return 0      # no immediate action


def fixed_preventive_strategy(obs: np.ndarray, step_number: int) -> int:
    """
    Fixed preventive maintenance:
    Perform maintenance every 20 decision steps.
    """

    if step_number > 0 and step_number % 20 == 0:
        return 1  # immediate maintenance
    return 0      # no immediate action


def xgboost_only_alert_strategy(obs: np.ndarray, step_number: int) -> int:
    """
    XGBoost-only alert strategy:
    Use only the predicted severity score.
    """

    severity = obs[1]

    if severity >= 0.70:
        return 1  # immediate maintenance
    elif severity >= 0.40:
        return 2  # low-load window
    else:
        return 0  # no immediate action


def rule_based_strategy(obs: np.ndarray, step_number: int) -> int:
    """
    Rule-based scheduling:
    Use severity, uncertainty, production load, and resource availability.
    """

    severity = obs[1]
    resource_availability = obs[2]
    production_load = obs[3]
    uncertainty = obs[6]

    if severity >= 0.85:
        return 1  # immediate maintenance

    if severity >= 0.70 and resource_availability >= 0.50:
        if production_load < 0.60:
            return 2  # low-load window
        return 3      # maintenance in 3 days

    if 0.40 <= severity < 0.70:
        if uncertainty >= 0.60:
            return 2  # low-load window
        return 3      # maintenance in 3 days

    return 4          # maintenance in 7 days


# ============================================================
# 5. Evaluation functions
# ============================================================

def evaluate_rule_strategy(
    strategy_name: str,
    strategy_function: Callable[[np.ndarray, int], int],
    maintenance_scores: np.ndarray,
    human_review_enabled: bool = False,
    episodes: int = 50,
    episode_length: int = 100,
    seed: int = 42
) -> Dict:
    """
    Evaluates a non-PPO baseline strategy.
    """

    episode_rewards = []
    critical_failures = []
    unnecessary_maintenance = []
    human_interventions = []
    human_overrides = []
    downtime_values = []
    cost_values = []
    all_actions = []

    for ep in range(episodes):
        env = OrchestraMaintenanceEnv(
            maintenance_scores=maintenance_scores,
            episode_length=episode_length,
            human_review_enabled=human_review_enabled,
            uncertainty_threshold=UNCERTAINTY_THRESHOLD,
            seed=seed + ep
        )

        obs, _ = env.reset()
        done = False
        truncated = False
        total_reward = 0.0
        step_number = 0
        final_info = {}

        while not (done or truncated):
            action = strategy_function(obs, step_number)
            obs, reward, done, truncated, info = env.step(action)

            total_reward += reward
            all_actions.append(action)
            final_info = info
            step_number += 1

        episode_rewards.append(total_reward)
        critical_failures.append(final_info.get("critical_failures", 0))
        unnecessary_maintenance.append(final_info.get("unnecessary_maintenance", 0))
        human_interventions.append(final_info.get("human_interventions", 0))
        human_overrides.append(final_info.get("human_overrides", 0))
        downtime_values.append(final_info.get("downtime_proxy", 0.0))
        cost_values.append(final_info.get("cost_proxy", 0.0))

    return summarise_results(
        strategy_name=strategy_name,
        episode_rewards=episode_rewards,
        critical_failures=critical_failures,
        unnecessary_maintenance=unnecessary_maintenance,
        human_interventions=human_interventions,
        human_overrides=human_overrides,
        downtime_values=downtime_values,
        cost_values=cost_values,
        all_actions=all_actions
    )


def evaluate_ppo_strategy(
    strategy_name: str,
    model: PPO,
    maintenance_scores: np.ndarray,
    human_review_enabled: bool,
    episodes: int = 50,
    episode_length: int = 100,
    seed: int = 42
) -> Dict:
    """
    Evaluates a PPO-based strategy.
    """

    episode_rewards = []
    critical_failures = []
    unnecessary_maintenance = []
    human_interventions = []
    human_overrides = []
    downtime_values = []
    cost_values = []
    all_actions = []

    for ep in range(episodes):
        env = OrchestraMaintenanceEnv(
            maintenance_scores=maintenance_scores,
            episode_length=episode_length,
            human_review_enabled=human_review_enabled,
            uncertainty_threshold=UNCERTAINTY_THRESHOLD,
            seed=seed + ep
        )

        obs, _ = env.reset()
        done = False
        truncated = False
        total_reward = 0.0
        final_info = {}

        while not (done or truncated):
            action, _ = model.predict(obs, deterministic=True)
            action = int(action)

            obs, reward, done, truncated, info = env.step(action)

            total_reward += reward
            all_actions.append(action)
            final_info = info

        episode_rewards.append(total_reward)
        critical_failures.append(final_info.get("critical_failures", 0))
        unnecessary_maintenance.append(final_info.get("unnecessary_maintenance", 0))
        human_interventions.append(final_info.get("human_interventions", 0))
        human_overrides.append(final_info.get("human_overrides", 0))
        downtime_values.append(final_info.get("downtime_proxy", 0.0))
        cost_values.append(final_info.get("cost_proxy", 0.0))

    return summarise_results(
        strategy_name=strategy_name,
        episode_rewards=episode_rewards,
        critical_failures=critical_failures,
        unnecessary_maintenance=unnecessary_maintenance,
        human_interventions=human_interventions,
        human_overrides=human_overrides,
        downtime_values=downtime_values,
        cost_values=cost_values,
        all_actions=all_actions
    )


def summarise_results(
    strategy_name: str,
    episode_rewards,
    critical_failures,
    unnecessary_maintenance,
    human_interventions,
    human_overrides,
    downtime_values,
    cost_values,
    all_actions
) -> Dict:
    """
    Aggregates metrics into one dictionary.
    """

    action_counts = Counter(all_actions)
    total_actions = sum(action_counts.values())

    action_percentages = {
        f"action_{action}_percent": 100.0 * action_counts.get(action, 0) / total_actions
        for action in range(5)
    }

    human_intervention_rate = 100.0 * np.mean(human_interventions) / EPISODE_LENGTH
    human_override_rate = 100.0 * np.mean(human_overrides) / EPISODE_LENGTH

    results = {
        "strategy": strategy_name,
        "mean_episode_reward": np.mean(episode_rewards),
        "std_episode_reward": np.std(episode_rewards),
        "mean_critical_failures": np.mean(critical_failures),
        "mean_unnecessary_maintenance": np.mean(unnecessary_maintenance),
        "mean_downtime_proxy": np.mean(downtime_values),
        "mean_cost_proxy": np.mean(cost_values),
        "mean_human_interventions": np.mean(human_interventions),
        "human_intervention_rate_percent": human_intervention_rate,
        "mean_human_overrides": np.mean(human_overrides),
        "human_override_rate_percent": human_override_rate,
    }

    results.update(action_percentages)

    return results


# ============================================================
# 6. Plotting
# ============================================================

def plot_baseline_rewards(results_df: pd.DataFrame, output_path: str):
    plt.figure(figsize=(10, 5))
    plt.bar(results_df["strategy"], results_df["mean_episode_reward"])
    plt.ylabel("Mean episode reward")
    plt.xlabel("Strategy")
    plt.title("Baseline Comparison: Mean Episode Reward")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def plot_failures(results_df: pd.DataFrame, output_path: str):
    plt.figure(figsize=(10, 5))
    plt.bar(results_df["strategy"], results_df["mean_critical_failures"])
    plt.ylabel("Mean critical failures")
    plt.xlabel("Strategy")
    plt.title("Baseline Comparison: Critical Failures")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


# ============================================================
# 7. Main execution
# ============================================================

def main():
    print("\n==============================================")
    print("ORCHESTRA Baseline Comparison")
    print("==============================================\n")

    maintenance_scores = load_maintenance_scores(DATASET_PATH)

    all_results = []

    # ------------------------------------------------------------
    # Non-PPO baselines
    # ------------------------------------------------------------

    print("\nEvaluating reactive maintenance...")
    all_results.append(
        evaluate_rule_strategy(
            strategy_name="Reactive maintenance",
            strategy_function=reactive_strategy,
            maintenance_scores=maintenance_scores,
            human_review_enabled=False,
            episodes=EVALUATION_EPISODES,
            episode_length=EPISODE_LENGTH,
            seed=SEED
        )
    )

    print("Evaluating fixed preventive maintenance...")
    all_results.append(
        evaluate_rule_strategy(
            strategy_name="Fixed preventive maintenance",
            strategy_function=fixed_preventive_strategy,
            maintenance_scores=maintenance_scores,
            human_review_enabled=False,
            episodes=EVALUATION_EPISODES,
            episode_length=EPISODE_LENGTH,
            seed=SEED
        )
    )

    print("Evaluating XGBoost-only alert strategy...")
    all_results.append(
        evaluate_rule_strategy(
            strategy_name="XGBoost-only alert",
            strategy_function=xgboost_only_alert_strategy,
            maintenance_scores=maintenance_scores,
            human_review_enabled=False,
            episodes=EVALUATION_EPISODES,
            episode_length=EPISODE_LENGTH,
            seed=SEED
        )
    )

    print("Evaluating rule-based scheduling...")
    all_results.append(
        evaluate_rule_strategy(
            strategy_name="Rule-based scheduling",
            strategy_function=rule_based_strategy,
            maintenance_scores=maintenance_scores,
            human_review_enabled=False,
            episodes=EVALUATION_EPISODES,
            episode_length=EPISODE_LENGTH,
            seed=SEED
        )
    )

    # ------------------------------------------------------------
    # PPO-based strategies
    # ------------------------------------------------------------

    if not os.path.exists(PPO_MODEL_PATH):
        raise FileNotFoundError(
            f"PPO model not found at {PPO_MODEL_PATH}. "
            "Please run the PPO training script first."
        )

    print("Loading trained PPO model...")
    model = PPO.load(PPO_MODEL_PATH)

    print("Evaluating PPO-only scheduling without human review...")
    all_results.append(
        evaluate_ppo_strategy(
            strategy_name="PPO-only scheduling",
            model=model,
            maintenance_scores=maintenance_scores,
            human_review_enabled=False,
            episodes=EVALUATION_EPISODES,
            episode_length=EPISODE_LENGTH,
            seed=SEED
        )
    )

    print("Evaluating Full ORCHESTRA...")
    all_results.append(
        evaluate_ppo_strategy(
            strategy_name="Full ORCHESTRA",
            model=model,
            maintenance_scores=maintenance_scores,
            human_review_enabled=True,
            episodes=EVALUATION_EPISODES,
            episode_length=EPISODE_LENGTH,
            seed=SEED
        )
    )

    # ------------------------------------------------------------
    # Save and display results
    # ------------------------------------------------------------

    results_df = pd.DataFrame(all_results)

    csv_path = os.path.join(OUTPUT_DIR, "baseline_comparison_results.csv")
    results_df.to_csv(csv_path, index=False)

    print("\n==============================================")
    print("Baseline Comparison Results")
    print("==============================================\n")
    print(results_df.to_string(index=False))

    reward_plot_path = os.path.join(OUTPUT_DIR, "baseline_mean_rewards.png")
    failure_plot_path = os.path.join(OUTPUT_DIR, "baseline_critical_failures.png")

    plot_baseline_rewards(results_df, reward_plot_path)
    plot_failures(results_df, failure_plot_path)

    print(f"\nResults saved to: {csv_path}")
    print(f"Reward plot saved to: {reward_plot_path}")
    print(f"Failure plot saved to: {failure_plot_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()