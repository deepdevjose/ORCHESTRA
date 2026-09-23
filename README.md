# ORCHESTRA Laser Welding

Research code for:

**ORCHESTRA: A Human-Centred Multi-Agent Framework for Predictive Maintenance Scheduling in Laser Welding-Based Smart Manufacturing**

This repository is designed for the journal paper pipeline. It can run immediately with only `numpy` and `pandas`, and it will automatically use stronger libraries such as `xgboost`, `scikit-learn`, `gymnasium`, and `stable-baselines3` when you install them.

## What The Code Does

1. Generates or loads laser welding process data.
2. Computes a lab-informed maintenance urgency score.
3. Trains an AI Predictive Agent for urgency prediction.
4. Estimates uncertainty and triggers selective human review.
5. Runs maintenance scheduling policies.
6. Compares ORCHESTRA against baselines.
7. Runs ablation and sensitivity experiments.
8. Exports paper-ready CSV tables.

## Quick Start In VS Code

Open this folder in VS Code:

```powershell
code "C:\Users\osiwa\OneDrive\Documents\RDF\ORCHESTRA-Laser-Welding"
```

Run the default pipeline:

```powershell
python scripts/run_pipeline.py
```

Outputs are written to:

```text
results/tables/
results/logs/
data/processed/
models/
```

## Optional Full Research Environment

For the strongest version of the paper, install:

```powershell
pip install -r requirements.txt
```

Then the project can use XGBoost, scikit-learn metrics, Gymnasium-compatible environments, and Stable-Baselines3 PPO.

## Expected Laser Welding Variables

If you collect real lab data, place CSV files in `data/raw/`. The recommended columns are:

- `laser_power_w`
- `welding_speed_mm_s`
- `focal_position_error_mm`
- `shielding_gas_flow_l_min`
- `melt_pool_temp_c`
- `back_reflection_intensity`
- `plume_intensity`
- `spatter_count`
- `vibration_rms`
- `robot_path_error_mm`
- `bead_width_mm`
- `bead_height_mm`
- `porosity_risk`
- `visual_defect_score`
- `lens_contamination_level`
- `cooling_system_alarm`
- `time_since_lens_cleaning_h`

If your real dataset has different column names, update `config/orchestra_config.json`.

## Main Scripts

- `scripts/run_pipeline.py` runs the full reproducible experiment.
- `scripts/live_inference_service.py` serves the repository model to the live dashboard.
- `src/orchestra_laser/synthetic_data.py` creates controlled laser welding scenarios.
- `src/orchestra_laser/urgency.py` derives maintenance urgency.
- `src/orchestra_laser/predictive_agent.py` trains the AI Predictive Agent.
- `src/orchestra_laser/human_agent.py` simulates uncertainty-triggered human review.
- `src/orchestra_laser/scheduling_env.py` defines the scheduling environment.
- `src/orchestra_laser/baselines.py` evaluates maintenance policies.
- `src/orchestra_laser/experiments.py` runs baseline, ablation, and sensitivity studies.

## Live dashboard and ESP32 ingestion

The `ui/` directory contains a Next.js control-room dashboard oriented to a China smart-manufacturing pilot context. It includes the MQTT gateway, payload validation, SSE live stream, Python model bridge, uncertainty-triggered human gate, and explicit demo fallback. Start it from `ui/` with:

~~~bash
npm install
npm run dev:stack
~~~

See `ui/README.md` for the MQTT topic and the 17-feature ESP32 payload contract. Demo telemetry is synthetic/lab-informed and is not evidence of live industrial validation.

## Paper Claims Supported

This code supports the honest claim:

> ORCHESTRA is evaluated using a laser welding lab demonstrator data model and a hybrid simulation environment for maintenance scheduling.

It does not claim full industrial validation unless real maintenance logs, real downtime records, and live production data are added.

## PhD-level simulation evidence package

The reproducible, simulation-only evidence package for the four-week validation plan is in `src/phd_simulation/`. It extends the Week 1 smoke foundation with latent process trajectories, case-level splits, grouped five-fold prediction validation, uncertainty calibration, matched-budget review routing, PPO-compatible scheduling, multi-seed confidence intervals, ablations, sensitivity analysis, counterfactual checks, and hash-chained audit traces.

Run a small smoke test:

```bash
python src/phd_simulation/run.py --quick --skip-ppo --output-dir /tmp/orchestra_phd_smoke
```

Run the configured five-seed experiment:

```bash
python src/phd_simulation/run.py
```

The package records its evidence manifest and explicitly preserves the simulation-only limitation: it is not real hardware validation, a live operator study, safety certification, or proof of industrial deployment.


## Test XGBoost And PPO

After installing optional packages, run the main pipeline:

```powershell
python scripts\run_pipeline.py
```

If XGBoost is active, the terminal and `models/predictive_agent_report.json` will show:

```text
"model": "xgboost"
```

To train and test a real Stable-Baselines3 PPO scheduler:

```powershell
python scripts\train_ppo.py
```

This creates:

```text
models/ppo_laser_maintenance_scheduler.zip
results/tables/ppo_evaluation.csv
results/logs/ppo_run_summary.json
```
