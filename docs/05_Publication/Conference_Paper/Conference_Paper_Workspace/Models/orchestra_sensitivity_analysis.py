"""
ORCHESTRA Sensitivity Analysis Script

This script evaluates the robustness of the Full ORCHESTRA framework under four sensitivity conditions:

1. Uncertainty threshold sensitivity
2. Sensor noise sensitivity
3. Reward weight sensitivity
4. Human intervention frequency sensitivity

The script uses the trained PPO Scheduling Agent and evaluates how the system behaves when key simulation assumptions change.

Author: ORCHESTRA Framework Development
"""

import os
import random
from collections import Counter
from typing import Dict, Tuple

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

OUTPUT_DIR = "orchestra_sensitivity_outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

DATASET_PATH = "spot_welding_dataset_100k_adjusted.csv"
PPO_MODEL_PATH = "orchestra_ppo_outputs/orchestra_ppo_scheduling_agent.zip"

EVALUATION_EPISODES = 50
EPISODE_LENGTH = 100

DEFAULT_UNCERTAINTY_THRESHOLD = 0.60


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
    Custom Gymnasium environment for ORCHESTRA maintenance scheduling.

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
        severity_noise_std: float = 0.0,
        forced_human_review_probability: float | None = None,
        reward_weights: Dict[str, float] | None = None,
        seed: int = 42
    ):
        super().__init__()

        self.maintenance_scores = maintenance_scores
        self.episode_length = episode_length
        self.human_review_enabled = human_review_enabled
        self.uncertainty_threshold = uncertainty_threshold
        self.severity_noise_std = severity_noise_std
        self.forced_human_review_probability = forced_human_review_probability

        self.reward_weights = reward_weights or {
            "failure_penalty": 50.0,
            "production_penalty_immediate": 7.0,
            "production_penalty_low_load": 3.0,
            "uncertainty_penalty": 2.0,
            "unnecessary_penalty": 10.0,
            "high_risk_no_action_penalty": 14.0,
            "high_risk_delay_penalty": 16.0,
        }

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
        severity = float(self.maintenance_scores[self.current_index])

        if self.severity_noise_std > 0:
            severity += self.rng.normal(0.0, self.severity_noise_std)

        return float(np.clip(severity, 0.0, 1.0))

    def _generate_uncertainty(self, severity: float) -> float:
        """
        Generates uncertainty. Medium-severity cases receive higher uncertainty
        because they are more ambiguous than clearly low-risk or high-risk cases.
        """

        medium_region = 1.0 - abs(severity - 0.5) * 2.0
        medium_region = np.clip(medium_region, 0.0, 1.0)

        random_component = self.rng.uniform(0.0, 0.35)
        uncertainty = 0.65 * medium_region + random_component

        return float(np.clip(uncertainty, 0.0, 1.0))

    def _human_review(self, severity: float, uncertainty: float) -> Tuple[float, bool, bool]:
        """
        Simulates the Human Operator Agent.

        The default review logic is uncertainty-triggered.
        If forced_human_review_probability is provided, review is triggered according
        to that probability, which supports the human intervention frequency analysis.
        """

        if not self.human_review_enabled:
            return severity, False, False

        if self.forced_human_review_probability is not None:
            review_triggered = self.rng.random() < self.forced_human_review_probability
        else:
            medium_severity = 0.40 <= severity <= 0.70
            high_uncertainty = uncertainty >= self.uncertainty_threshold
            high_risk_ambiguous = severity >= 0.75 and uncertainty >= 0.45

            review_triggered = medium_severity or high_uncertainty or high_risk_ambiguous

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

        severity = float(self.state[1])
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
                reward -= self.reward_weights["high_risk_no_action_penalty"]
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
                reward -= self.reward_weights["unnecessary_penalty"]
                unnecessary = True

            reward -= self.reward_weights["production_penalty_immediate"] * production_load

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

            reward -= self.reward_weights["production_penalty_low_load"] * production_load

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
                reward -= self.reward_weights["high_risk_delay_penalty"]

            self.hidden_risk += degradation_pressure * 1.25
            self.time_since_last_maintenance += 0.07

        self.hidden_risk = float(np.clip(self.hidden_risk, 0.0, 1.0))
        self.time_since_last_maintenance = float(np.clip(self.time_since_last_maintenance, 0.0, 1.0))

        # Critical failure condition
        if self.hidden_risk >= 0.95:
            self.critical_failures += 1
            reward -= self.reward_weights["failure_penalty"]

            self.hidden_risk = self.rng.uniform(0.10, 0.25)
            self.time_since_last_maintenance = 0.0

            self.downtime_proxy += 0.80
            self.cost_proxy += 0.90

        if unnecessary:
            self.unnecessary_maintenance += 1

        if uncertainty > self.uncertainty_threshold and action in [0, 3, 4]:
            reward -= self.reward_weights["uncertainty_penalty"]

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
# 4. Evaluation
# ============================================================

def evaluate_ppo_model(
    model: PPO,
    maintenance_scores: np.ndarray,
    experiment_name: str,
    uncertainty_threshold: float = DEFAULT_UNCERTAINTY_THRESHOLD,
    severity_noise_std: float = 0.0,
    forced_human_review_probability: float | None = None,
    reward_weights: Dict[str, float] | None = None,
    human_review_enabled: bool = True,
    episodes: int = EVALUATION_EPISODES,
    episode_length: int = EPISODE_LENGTH,
    seed: int = SEED
) -> Dict:
    """
    Evaluates the trained PPO model under a specific sensitivity condition.
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
            uncertainty_threshold=uncertainty_threshold,
            severity_noise_std=severity_noise_std,
            forced_human_review_probability=forced_human_review_probability,
            reward_weights=reward_weights,
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

    action_counts = Counter(all_actions)
    total_actions = sum(action_counts.values())

    action_percentages = {
        f"action_{action}_percent": 100.0 * action_counts.get(action, 0) / total_actions
        for action in range(5)
    }

    mean_human_interventions = float(np.mean(human_interventions))
    mean_human_overrides = float(np.mean(human_overrides))

    results = {
        "experiment": experiment_name,
        "mean_episode_reward": float(np.mean(episode_rewards)),
        "std_episode_reward": float(np.std(episode_rewards)),
        "mean_critical_failures": float(np.mean(critical_failures)),
        "mean_unnecessary_maintenance": float(np.mean(unnecessary_maintenance)),
        "mean_downtime_proxy": float(np.mean(downtime_values)),
        "mean_cost_proxy": float(np.mean(cost_values)),
        "mean_human_interventions": mean_human_interventions,
        "human_intervention_rate_percent": 100.0 * mean_human_interventions / episode_length,
        "mean_human_overrides": mean_human_overrides,
        "human_override_rate_percent": 100.0 * mean_human_overrides / episode_length,
    }

    results.update(action_percentages)

    return results


# ============================================================
# 5. Sensitivity analysis experiments
# ============================================================

def run_uncertainty_threshold_sensitivity(model: PPO, scores: np.ndarray) -> pd.DataFrame:
    thresholds = [0.30, 0.50, 0.60, 0.70, 0.90]

    results = []
    for threshold in thresholds:
        print(f"Running uncertainty threshold sensitivity: threshold = {threshold}")
        results.append(
            evaluate_ppo_model(
                model=model,
                maintenance_scores=scores,
                experiment_name=f"threshold_{threshold}",
                uncertainty_threshold=threshold,
                severity_noise_std=0.0,
                human_review_enabled=True
            )
        )

    df = pd.DataFrame(results)
    df.to_csv(os.path.join(OUTPUT_DIR, "sensitivity_uncertainty_threshold.csv"), index=False)
    return df


def run_sensor_noise_sensitivity(model: PPO, scores: np.ndarray) -> pd.DataFrame:
    noise_levels = [0.00, 0.05, 0.10, 0.20]

    results = []
    for noise in noise_levels:
        print(f"Running sensor noise sensitivity: noise std = {noise}")
        results.append(
            evaluate_ppo_model(
                model=model,
                maintenance_scores=scores,
                experiment_name=f"noise_{noise}",
                uncertainty_threshold=DEFAULT_UNCERTAINTY_THRESHOLD,
                severity_noise_std=noise,
                human_review_enabled=True
            )
        )

    df = pd.DataFrame(results)
    df.to_csv(os.path.join(OUTPUT_DIR, "sensitivity_sensor_noise.csv"), index=False)
    return df


def run_reward_weight_sensitivity(model: PPO, scores: np.ndarray) -> pd.DataFrame:
    """
    This evaluates the trained PPO policy under different reward emphasis settings.

    Important for the paper:
    This is an evaluation sensitivity test, not a full retraining experiment.
    It shows how the same learned policy scores under different reward priorities.
    """

    reward_profiles = {
        "balanced": {
            "failure_penalty": 50.0,
            "production_penalty_immediate": 7.0,
            "production_penalty_low_load": 3.0,
            "uncertainty_penalty": 2.0,
            "unnecessary_penalty": 10.0,
            "high_risk_no_action_penalty": 14.0,
            "high_risk_delay_penalty": 16.0,
        },
        "risk_focused": {
            "failure_penalty": 80.0,
            "production_penalty_immediate": 5.0,
            "production_penalty_low_load": 2.0,
            "uncertainty_penalty": 3.0,
            "unnecessary_penalty": 8.0,
            "high_risk_no_action_penalty": 22.0,
            "high_risk_delay_penalty": 24.0,
        },
        "cost_focused": {
            "failure_penalty": 45.0,
            "production_penalty_immediate": 12.0,
            "production_penalty_low_load": 6.0,
            "uncertainty_penalty": 2.0,
            "unnecessary_penalty": 18.0,
            "high_risk_no_action_penalty": 12.0,
            "high_risk_delay_penalty": 14.0,
        },
        "uncertainty_focused": {
            "failure_penalty": 55.0,
            "production_penalty_immediate": 7.0,
            "production_penalty_low_load": 3.0,
            "uncertainty_penalty": 8.0,
            "unnecessary_penalty": 10.0,
            "high_risk_no_action_penalty": 16.0,
            "high_risk_delay_penalty": 18.0,
        },
    }

    results = []
    for profile_name, weights in reward_profiles.items():
        print(f"Running reward weight sensitivity: profile = {profile_name}")
        results.append(
            evaluate_ppo_model(
                model=model,
                maintenance_scores=scores,
                experiment_name=profile_name,
                uncertainty_threshold=DEFAULT_UNCERTAINTY_THRESHOLD,
                severity_noise_std=0.0,
                reward_weights=weights,
                human_review_enabled=True
            )
        )

    df = pd.DataFrame(results)
    df.to_csv(os.path.join(OUTPUT_DIR, "sensitivity_reward_weights.csv"), index=False)
    return df


def run_human_intervention_frequency_sensitivity(model: PPO, scores: np.ndarray) -> pd.DataFrame:
    """
    This test forces human review at different frequencies.

    It answers:
    What happens if the system uses low, moderate, or high human involvement,
    independent of the uncertainty threshold rule?
    """

    frequencies = [0.00, 0.20, 0.40, 0.60, 0.80, 1.00]

    results = []
    for freq in frequencies:
        print(f"Running human intervention frequency sensitivity: frequency = {freq}")
        results.append(
            evaluate_ppo_model(
                model=model,
                maintenance_scores=scores,
                experiment_name=f"human_frequency_{freq}",
                uncertainty_threshold=DEFAULT_UNCERTAINTY_THRESHOLD,
                severity_noise_std=0.0,
                forced_human_review_probability=freq,
                human_review_enabled=True
            )
        )

    df = pd.DataFrame(results)
    df.to_csv(os.path.join(OUTPUT_DIR, "sensitivity_human_frequency.csv"), index=False)
    return df


# ============================================================
# 6. Plotting functions
# ============================================================

def plot_metric(df: pd.DataFrame, x_col: str, y_col: str, title: str, output_name: str):
    plt.figure(figsize=(9, 5))
    plt.plot(df[x_col], df[y_col], marker="o")
    plt.xlabel(x_col.replace("_", " ").title())
    plt.ylabel(y_col.replace("_", " ").title())
    plt.title(title)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, output_name), dpi=300)
    plt.close()


def create_plots(
    threshold_df: pd.DataFrame,
    noise_df: pd.DataFrame,
    reward_df: pd.DataFrame,
    human_freq_df: pd.DataFrame
):
    # Uncertainty threshold plots
    threshold_df["threshold"] = threshold_df["experiment"].str.replace("threshold_", "", regex=False).astype(float)

    plot_metric(
        threshold_df,
        "threshold",
        "mean_episode_reward",
        "Sensitivity of Mean Reward to Uncertainty Threshold",
        "plot_threshold_reward.png"
    )

    plot_metric(
        threshold_df,
        "threshold",
        "human_intervention_rate_percent",
        "Sensitivity of Human Intervention Rate to Uncertainty Threshold",
        "plot_threshold_human_intervention.png"
    )

    # Sensor noise plots
    noise_df["noise_std"] = noise_df["experiment"].str.replace("noise_", "", regex=False).astype(float)

    plot_metric(
        noise_df,
        "noise_std",
        "mean_episode_reward",
        "Sensitivity of Mean Reward to Sensor Noise",
        "plot_noise_reward.png"
    )

    plot_metric(
        noise_df,
        "noise_std",
        "mean_critical_failures",
        "Sensitivity of Critical Failures to Sensor Noise",
        "plot_noise_failures.png"
    )

    # Reward profile bar chart
    plt.figure(figsize=(9, 5))
    plt.bar(reward_df["experiment"], reward_df["mean_episode_reward"])
    plt.xlabel("Reward profile")
    plt.ylabel("Mean episode reward")
    plt.title("Sensitivity of Mean Reward to Reward Weight Profiles")
    plt.xticks(rotation=25, ha="right")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "plot_reward_profile_reward.png"), dpi=300)
    plt.close()

    # Human frequency plots
    human_freq_df["human_frequency"] = human_freq_df["experiment"].str.replace(
        "human_frequency_", "", regex=False
    ).astype(float)

    plot_metric(
        human_freq_df,
        "human_frequency",
        "mean_episode_reward",
        "Sensitivity of Mean Reward to Human Review Frequency",
        "plot_human_frequency_reward.png"
    )

    plot_metric(
        human_freq_df,
        "human_frequency",
        "human_intervention_rate_percent",
        "Sensitivity of Actual Human Intervention Rate to Forced Review Frequency",
        "plot_human_frequency_intervention.png"
    )


# ============================================================
# 7. Main execution
# ============================================================

def main():
    print("\n==============================================")
    print("ORCHESTRA Sensitivity Analysis")
    print("==============================================\n")

    if not os.path.exists(PPO_MODEL_PATH):
        raise FileNotFoundError(
            f"PPO model not found at {PPO_MODEL_PATH}. "
            "Please run the PPO training script first."
        )

    scores = load_maintenance_scores(DATASET_PATH)

    print("Loading trained PPO model...")
    model = PPO.load(PPO_MODEL_PATH)

    print("\n--- 1. Uncertainty Threshold Sensitivity ---")
    threshold_df = run_uncertainty_threshold_sensitivity(model, scores)

    print("\n--- 2. Sensor Noise Sensitivity ---")
    noise_df = run_sensor_noise_sensitivity(model, scores)

    print("\n--- 3. Reward Weight Sensitivity ---")
    reward_df = run_reward_weight_sensitivity(model, scores)

    print("\n--- 4. Human Intervention Frequency Sensitivity ---")
    human_freq_df = run_human_intervention_frequency_sensitivity(model, scores)

    print("\nCreating plots...")
    create_plots(threshold_df, noise_df, reward_df, human_freq_df)

    print("\n==============================================")
    print("Sensitivity analysis completed.")
    print("Files saved in:", OUTPUT_DIR)
    print("==============================================\n")

    print("Generated CSV files:")
    print("- sensitivity_uncertainty_threshold.csv")
    print("- sensitivity_sensor_noise.csv")
    print("- sensitivity_reward_weights.csv")
    print("- sensitivity_human_frequency.csv")

    print("\nGenerated figures:")
    print("- plot_threshold_reward.png")
    print("- plot_threshold_human_intervention.png")
    print("- plot_noise_reward.png")
    print("- plot_noise_failures.png")
    print("- plot_reward_profile_reward.png")
    print("- plot_human_frequency_reward.png")
    print("- plot_human_frequency_intervention.png")


if __name__ == "__main__":
    main()