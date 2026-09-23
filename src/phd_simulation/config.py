from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "default_config.json"


@dataclass(frozen=True)
class SimulationConfig:
    """Single source of truth for a reproducible paper run.

    The defaults are suitable for a complete local run.  ``quick`` mode in
    the runner reduces the sample and training budgets, but never changes the
    scientific semantics of the simulator or the metrics.
    """

    seed: int = 42
    seeds: tuple[int, ...] = (11, 22, 33, 44, 55)
    n_cases: int = 180
    episode_length: int = 40
    ood_fraction: float = 0.15
    train_case_fraction: float = 0.60
    calibration_case_fraction: float = 0.20
    cv_folds: int = 5
    review_budget: float = 0.25
    bootstrap_samples: int = 2000
    sensor_noise: float = 0.018
    missing_modality_rate: float = 0.0
    concept_drift: float = 0.0
    maintenance_delay: int = 0
    resource_availability_floor: float = 0.30
    xgb_estimators: int = 80
    ppo_timesteps: int = 8000
    ppo_eval_episodes: int = 20
    run_ppo: bool = True
    output_dir: str = "results/phd_simulation"
    reward_weights: dict[str, float] = field(
        default_factory=lambda: {
            "risk": 3.0,
            "downtime": 1.0,
            "cost": 0.8,
            "unnecessary_maintenance": 1.0,
            "human_review": 0.15,
            "failure": 45.0,
        }
    )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["seeds"] = list(self.seeds)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SimulationConfig":
        values = dict(payload)
        if "seeds" in values:
            values["seeds"] = tuple(int(seed) for seed in values["seeds"])
        return cls(**values)


def load_config(path: str | Path | None = None) -> SimulationConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as handle:
        return SimulationConfig.from_dict(json.load(handle))


def write_config(config: SimulationConfig, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(config.to_dict(), indent=2) + "\n", encoding="utf-8")
