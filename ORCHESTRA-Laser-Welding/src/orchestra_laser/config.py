from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Paths:
    root: Path = PROJECT_ROOT
    config: Path = PROJECT_ROOT / "config" / "orchestra_config.json"
    raw_data: Path = PROJECT_ROOT / "data" / "raw"
    processed_data: Path = PROJECT_ROOT / "data" / "processed"
    models: Path = PROJECT_ROOT / "models"
    tables: Path = PROJECT_ROOT / "results" / "tables"
    logs: Path = PROJECT_ROOT / "results" / "logs"
    figures: Path = PROJECT_ROOT / "results" / "figures"

    def ensure(self) -> None:
        for path in [
            self.raw_data,
            self.processed_data,
            self.models,
            self.tables,
            self.logs,
            self.figures,
        ]:
            path.mkdir(parents=True, exist_ok=True)


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or Paths().config
    with config_path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


