"""Command-line entry point for full and quick ORCHESTRA simulation runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from phd_simulation.config import load_config
    from phd_simulation.runner import run
else:
    from .config import load_config
    from .runner import run


def main() -> None:
    """Parse CLI options, run the package, and print a compact JSON summary."""
    parser = argparse.ArgumentParser(description="Run the ORCHESTRA PhD-level simulation evidence package")
    parser.add_argument("--config", type=Path, default=None, help="Optional JSON configuration")
    parser.add_argument("--output-dir", type=Path, default=None, help="Override result directory")
    parser.add_argument("--quick", action="store_true", help="Small smoke run; not final paper evidence")
    parser.add_argument("--skip-ppo", action="store_true", help="Skip optional Stable-Baselines3 PPO training")
    args = parser.parse_args()
    config = load_config(args.config)
    manifest = run(config, output_dir=args.output_dir, quick=args.quick, skip_ppo=args.skip_ppo)
    print(json.dumps({"status": "completed", "mode": manifest["mode"], "output_dir": str(args.output_dir or config.output_dir), "audit": manifest["audit"]}, indent=2))


if __name__ == "__main__":
    main()
