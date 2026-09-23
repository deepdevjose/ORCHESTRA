"""
ORCHESTRA PPO-Based RL Scheduling Agent
Simulation-based maintenance scheduling environment for resistance spot welding.

This script implements:
1. A custom Gymnasium environment for predictive maintenance scheduling.
2. A seven-variable state space:
   - time_to_failure
   - predicted_severity
   - resource_availability
   - production_load
   - time_since_last_maintenance
   - maintenance_cost_factor
   - uncertainty
3. A five-action maintenance scheduling space:
   0 = No immediate action
   1 = Immediate maintenance
   2 = Maintenance during next low-load production window
   3 = Maintenance in 3 days
   4 = Maintenance in 7 days
4. An uncertainty-triggered simulated human review mechanism.
5. A context-aware reward function.
6. PPO training using Stable-Baselines3.
7. Evaluation metrics and result plots.

Author: ORCHESTRA Framework Development
"""

import os
import random
from collections import Counter

import gymnasium as gym
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from gymnasium import spaces
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.env_checker import check_env


# ============================================================
# 1. Configuration
# ============================================================

SEED = 42
np.random.seed(SEED)
random.seed(SEED)

OUTPUT_DIR = "orchestra_ppo_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Optional dataset path.
# If this file exists, the environment will use Predictive_Maintenance_Score
# or Predicted_Maintenance_Score as the severity source.
# If the file does not exist, synthetic severity values will be generated.
DATASET_PATH = "spot_welding_dataset_100k_adjusted.csv"

TOTAL_TIMESTEPS = 200_000
EVALUATION_EPISODES = 50
EPISODE_LENGTH = 100

HUMAN_REVIEW_ENABLED = True
UNCERTAINTY_THRESHOLD = 0.60


# ============================================================
# 2. Utility function to load maintenance urgency data
# ============================================================

def load_maintenance_scores(dataset_path: str) -> np.ndarray:
    """
    Loads maintenance urgency scores from a CSV file.

    Expected column options:
    - Predicted_Maintenance_Score
    - Predictive_Maintenance_Score

    Scores are normalised to the range [0, 1].

    If the file or required columns are not found, synthetic scores are generated.
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

    # If scores are 0-100, normalise to 0-1.
    if scores.max() > 1.0:
        scores = scores / 100.0

    scores = np.clip(scores, 0.0, 1.0)

    print(f"Loaded maintenance urgency scores from column: {score_column}")
    print(f"Number of samples loaded: {len(scores)}")

    return scores


# ============================================================
# 3. ORCHESTRA custom PPO environment
# ============================================================

class OrchestraMaintenanceEnv(gym.Env):
    """
    Custom Gymnasium environment for PPO-based maintenance scheduling.

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
        2 = Schedule maintenance during next low-load window
        3 = Schedule maintenance in 3 days
        4 = Schedule maintenance in 7 days
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
        self.seed_value = seed

        self.rng = np.random.default_rng(seed)

        # Seven continuous state variables, all normalised between 0 and 1.
        self.observation_space = spaces.Box(
            low=0.0,
            high=1.0,
            shape=(7,),
            dtype=np.float32
        )

        # Five maintenance scheduling actions.
        self.action_space = spaces.Discrete(5)

        # Internal episode variables.
        self.current_step = 0
        self.current_index = 0
        self.hidden_risk = 0.0
        self.time_since_last_maintenance = 0.0

        # Metrics recorded during each episode.
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
        """Samples a maintenance urgency score from the dataset or synthetic source."""
        self.current_index = self.rng.integers(0, len(self.maintenance_scores))
        return float(self.maintenance_scores[self.current_index])

    def _generate_uncertainty(self, severity: float) -> float:
        """
        Generates uncertainty.

        The uncertainty is higher around medium-severity cases because these cases
        are more ambiguous than clearly low-risk or clearly high-risk cases.
        """

        medium_region = 1.0 - abs(severity - 0.5) * 2.0
        medium_region = np.clip(medium_region, 0.0, 1.0)

        random_component = self.rng.uniform(0.0, 0.35)
        uncertainty = 0.65 * medium_region + random_component

        return float(np.clip(uncertainty, 0.0, 1.0))

    def _human_review(self, severity: float, uncertainty: float) -> tuple[float, bool, bool]:
        """
        Simulates the Human Operator Agent.

        Human review is triggered under:
        - medium severity,
        - high uncertainty,
        - high severity with operational ambiguity.

        The simulated human operator can validate, refine, or override severity.
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

            # Simulated contextual correction.
            # The operator reduces some uncertainty by refining the severity estimate.
            correction = self.rng.normal(loc=0.0, scale=0.06)
            refined_severity = np.clip(severity + correction, 0.0, 1.0)

            # A larger correction is treated as an override.
            if abs(refined_severity - severity) > 0.08:
                override_applied = True
                self.human_overrides += 1

        return float(refined_severity), review_triggered, override_applied

    def _get_observation(self) -> np.ndarray:
        """Builds the current state vector."""

        predicted_severity = self._sample_score()

        # Hidden risk evolves around predicted severity.
        # This represents degradation that is not perfectly observable.
        self.hidden_risk = np.clip(
            0.75 * self.hidden_risk + 0.25 * predicted_severity + self.rng.normal(0, 0.03),
            0.0,
            1.0
        )

        uncertainty = self._generate_uncertainty(predicted_severity)

        # Human review may refine the severity before PPO receives the final state.
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
        """Resets the environment at the beginning of an episode."""

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

        info = {}
        return self.state, info

    def step(self, action: int):
        """
        Executes one scheduling decision and returns:
        observation, reward, terminated, truncated, info
        """

        self.current_step += 1
        self.action_history.append(int(action))

        time_to_failure = float(self.state[0])
        severity = float(self.state[1])
        resource_availability = float(self.state[2])
        production_load = float(self.state[3])
        time_since_last_maintenance = float(self.state[4])
        cost_factor = float(self.state[5])
        uncertainty = float(self.state[6])

        reward = 0.0
        failure = False
        unnecessary = False

        # ------------------------------------------------------------
        # Reward logic
        # ------------------------------------------------------------

        # Risk increases naturally if maintenance is delayed.
        degradation_pressure = 0.02 + (0.04 * production_load) + (0.03 * severity)

        # Action 0: No immediate action.
        if action == 0:
            if severity < 0.30 and uncertainty < 0.50:
                reward += 4.0
            elif severity >= 0.70:
                reward -= 14.0
            else:
                reward -= 3.0

            self.hidden_risk += degradation_pressure

        # Action 1: Immediate maintenance.
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

            # Penalty for disrupting production.
            reward -= 7.0 * production_load

            # Maintenance strongly reduces risk.
            self.hidden_risk = self.rng.uniform(0.05, 0.20)
            self.time_since_last_maintenance = 0.0

        # Action 2: Maintenance during next low-load window.
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

            # Lower disruption than immediate maintenance.
            reward -= 3.0 * production_load

            # Planned maintenance reduces risk, but less aggressively.
            self.hidden_risk = max(0.10, self.hidden_risk - 0.35)
            self.time_since_last_maintenance = 0.0

        # Action 3: Maintenance in 3 days.
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

        # Action 4: Maintenance in 7 days.
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

        # ------------------------------------------------------------
        # Critical failure logic
        # ------------------------------------------------------------

        self.hidden_risk = float(np.clip(self.hidden_risk, 0.0, 1.0))
        self.time_since_last_maintenance = float(np.clip(self.time_since_last_maintenance, 0.0, 1.0))

        if self.hidden_risk >= 0.95:
            failure = True
            self.critical_failures += 1
            reward -= 50.0

            # After a critical failure, assume emergency repair resets the machine.
            self.hidden_risk = self.rng.uniform(0.10, 0.25)
            self.time_since_last_maintenance = 0.0

            self.downtime_proxy += 0.80
            self.cost_proxy += 0.90

        if unnecessary:
            self.unnecessary_maintenance += 1

        # Additional small penalty for high uncertainty without early action.
        if uncertainty > self.uncertainty_threshold and action in [0, 3, 4]:
            reward -= 2.0

        self.episode_reward += reward

        # Get next state.
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

    def render(self):
        """Optional rendering for debugging."""
        print(f"Step: {self.current_step}, State: {self.state}")


# ============================================================
# 4. Evaluation function
# ============================================================

def evaluate_agent(model: PPO, env: OrchestraMaintenanceEnv, episodes: int = 50) -> dict:
    """
    Evaluates the trained PPO agent across multiple episodes.
    Returns aggregated performance metrics.
    """

    episode_rewards = []
    critical_failures = []
    unnecessary_maintenance = []
    human_interventions = []
    human_overrides = []
    downtime_values = []
    cost_values = []
    all_actions = []

    for _ in range(episodes):
        obs, _ = env.reset()
        done = False
        truncated = False
        total_reward = 0.0
        final_info = {}

        while not (done or truncated):
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, truncated, info = env.step(int(action))
            total_reward += reward
            all_actions.append(int(action))
            final_info = info

        episode_rewards.append(total_reward)
        critical_failures.append(final_info.get("critical_failures", 0))
        unnecessary_maintenance.append(final_info.get("unnecessary_maintenance", 0))
        human_interventions.append(final_info.get("human_interventions", 0))
        human_overrides.append(final_info.get("human_overrides", 0))
        downtime_values.append(final_info.get("downtime_proxy", 0.0))
        cost_values.append(final_info.get("cost_proxy", 0.0))

    action_counts = Counter(all_actions)
    total_actions = sum(action_counts.values())

    action_distribution = {
        action: 100.0 * count / total_actions
        for action, count in sorted(action_counts.items())
    }

    results = {
        "mean_episode_reward": np.mean(episode_rewards),
        "std_episode_reward": np.std(episode_rewards),
        "mean_critical_failures": np.mean(critical_failures),
        "mean_unnecessary_maintenance": np.mean(unnecessary_maintenance),
        "mean_human_interventions": np.mean(human_interventions),
        "mean_human_overrides": np.mean(human_overrides),
        "mean_downtime_proxy": np.mean(downtime_values),
        "mean_cost_proxy": np.mean(cost_values),
        "action_distribution_percent": action_distribution
    }

    return results


# ============================================================
# 5. Plotting functions
# ============================================================

def plot_action_distribution(action_distribution: dict, output_path: str):
    """Saves a bar chart of the PPO action distribution."""

    action_labels = {
        0: "No action",
        1: "Immediate",
        2: "Low-load window",
        3: "In 3 days",
        4: "In 7 days"
    }

    actions = list(range(5))
    values = [action_distribution.get(a, 0.0) for a in actions]
    labels = [action_labels[a] for a in actions]

    plt.figure(figsize=(9, 5))
    plt.bar(labels, values)
    plt.ylabel("Action selection (%)")
    plt.xlabel("Maintenance action")
    plt.title("PPO Maintenance Scheduling Action Distribution")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()


def save_results_to_csv(results: dict, output_path: str):
    """Saves evaluation results to a CSV file."""

    rows = []

    for key, value in results.items():
        if key != "action_distribution_percent":
            rows.append({"Metric": key, "Value": value})

    for action, percentage in results["action_distribution_percent"].items():
        rows.append({
            "Metric": f"action_{action}_percentage",
            "Value": percentage
        })

    pd.DataFrame(rows).to_csv(output_path, index=False)


# ============================================================
# 6. Main execution
# ============================================================

def main():
    print("\n==============================================")
    print("ORCHESTRA PPO RL Scheduling Agent")
    print("==============================================\n")

    maintenance_scores = load_maintenance_scores(DATASET_PATH)

    env = OrchestraMaintenanceEnv(
        maintenance_scores=maintenance_scores,
        episode_length=EPISODE_LENGTH,
        human_review_enabled=HUMAN_REVIEW_ENABLED,
        uncertainty_threshold=UNCERTAINTY_THRESHOLD,
        seed=SEED
    )

    # Check environment compatibility with Stable-Baselines3.
    print("Checking custom Gymnasium environment...")
    check_env(env, warn=True)
    print("Environment check completed.\n")

    monitored_env = Monitor(env)

    print("Training PPO agent...")
    model = PPO(
        policy="MlpPolicy",
        env=monitored_env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        gamma=0.99,
        gae_lambda=0.95,
        clip_range=0.2,
        ent_coef=0.01,
        verbose=1,
        seed=SEED,
        policy_kwargs=dict(net_arch=[64, 64])
    )

    model.learn(total_timesteps=TOTAL_TIMESTEPS)

    model_path = os.path.join(OUTPUT_DIR, "orchestra_ppo_scheduling_agent")
    model.save(model_path)

    print(f"\nModel saved to: {model_path}.zip")

    print("\nEvaluating trained PPO agent...")
    evaluation_env = OrchestraMaintenanceEnv(
        maintenance_scores=maintenance_scores,
        episode_length=EPISODE_LENGTH,
        human_review_enabled=HUMAN_REVIEW_ENABLED,
        uncertainty_threshold=UNCERTAINTY_THRESHOLD,
        seed=SEED + 1
    )

    results = evaluate_agent(
        model=model,
        env=evaluation_env,
        episodes=EVALUATION_EPISODES
    )

    print("\n==============================================")
    print("Evaluation Results")
    print("==============================================")

    for key, value in results.items():
        if key != "action_distribution_percent":
            print(f"{key}: {value:.4f}")

    print("\nAction Distribution (%)")
    for action, percentage in results["action_distribution_percent"].items():
        print(f"Action {action}: {percentage:.2f}%")

    results_csv_path = os.path.join(OUTPUT_DIR, "ppo_evaluation_results.csv")
    save_results_to_csv(results, results_csv_path)

    plot_path = os.path.join(OUTPUT_DIR, "ppo_action_distribution.png")
    plot_action_distribution(results["action_distribution_percent"], plot_path)

    print(f"\nResults saved to: {results_csv_path}")
    print(f"Action distribution plot saved to: {plot_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()