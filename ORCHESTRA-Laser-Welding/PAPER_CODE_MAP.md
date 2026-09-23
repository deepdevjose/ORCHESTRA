# Paper-To-Code Map

This file maps the ORCHESTRA journal-paper sections to the code.

## Methodology

- Laser welding data preparation: `src/orchestra_laser/preprocessing.py`
- Lab-informed scenario generator: `src/orchestra_laser/synthetic_data.py`
- Maintenance urgency score: `src/orchestra_laser/urgency.py`
- AI Predictive Agent: `src/orchestra_laser/predictive_agent.py`
- Uncertainty estimation: `src/orchestra_laser/uncertainty.py`
- Human Operator Agent: `src/orchestra_laser/human_agent.py`
- RL/PPO scheduling environment interface: `src/orchestra_laser/scheduling_env.py`

## Experiments

- Reactive baseline: `reactive_policy`
- Fixed preventive baseline: `fixed_preventive_policy_factory`
- Prediction-only baseline: `prediction_only_policy`
- Rule-based baseline: `rule_based_policy`
- Full ORCHESTRA policy: `greedy_orchestra_policy`
- Ablation study: `run_ablation_study`
- Sensitivity analysis: `run_sensitivity_analysis`

## Tables For Paper

After running:

```powershell
python scripts/run_pipeline.py
```

use:

- `results/tables/baseline_comparison.csv`
- `results/tables/ablation_study.csv`
- `results/tables/sensitivity_analysis.csv`
- `models/predictive_agent_report.json`

## What To Replace With Real Lab Data

Once the laser welding station data is collected, replace the generated dataset with a CSV in `data/raw/` and pass it into `load_or_create_dataset`, or modify `scripts/run_pipeline.py` to load the chosen CSV explicitly.

