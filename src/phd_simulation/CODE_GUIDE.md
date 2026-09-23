# ORCHESTRA PhD Simulation Code Guide

I use this guide to explain the code-level contract of the reproducible
Weeks 1–3 package. The implementation is intentionally split by responsibility
so I can inspect data generation, prediction, review, scheduling, statistics,
audit, and reporting independently.

## Execution flow

```text
SimulationConfig
      |
      v
simulator.generate_laser_dataset
      |
      +--> validate_dataset
      |
      v
prediction.compare_models / fit_xgb_with_calibration
      |
      +--> E2 tables, feature importance, E3 calibration
      |
      v
review.HumanReviewRouter
      |
      +--> matched-budget E4 study
      |
      v
environment.LaserWeldingSchedulingEnv
      |
      +--> policies, PPO, E5/E6/E7 metrics
      |
      v
audit.hash_trace / counterfactual_tests
      |
      v
stats + plot_results + manifest
```

## Module contracts

| Module | Main contract | Primary outputs |
| --- | --- | --- |
| `config.py` | Keeps one typed configuration object and serializes it to JSON. | `SimulationConfig`, `resolved_config.json` |
| `schema.py` | Defines the feature, metadata, scenario, and action vocabulary. | `FEATURE_COLUMNS`, `ACTION_NAMES`, schema constants |
| `simulator.py` | Generates seeded latent trajectories and verifies their structure. | `raw_stream.csv`, `feature_vector.csv`, dataset validation JSON |
| `prediction.py` | Fits and evaluates regressors with case-grouped folds and conformal-style uncertainty. | E2 model tables, E3 calibration tables, uncertainty columns |
| `review.py` | Routes a fixed fraction of rows to a simulated expert using uncertainty, conflict, and risk. | Review flags, expert estimate, adjusted urgency, E4 metrics |
| `environment.py` | Converts a row and action into state transition, reward, and operational outcomes. | Episode metrics and action traces |
| `policies.py` | Provides controls and the full ORCHESTRA policy used by E5–E7. | Policy action functions |
| `ppo.py` | Adapts the scheduling environment to Gymnasium and trains/evaluates PPO. | PPO model archives and traces |
| `audit.py` | Canonicalizes rows, chains hashes, and checks directional counterfactuals. | E8 trace, report, and counterfactual CSV |
| `stats.py` | Computes seed-level confidence intervals and paired comparisons. | E5–E7 summaries and E9 statistics |
| `runner.py` | Orchestrates all experiment stages and writes the manifest. | Complete result tree and `manifest.json` |
| `plot_results.py` | Reads archived outputs and renders paper figures without resampling the experiment. | Fourteen PNG figures and the derived risk-gate matrix CSV |

## Core data contracts

### Simulator rows

Each row contains the seventeen process features plus case, cycle, scenario,
distribution, split, seed, provenance, latent state, target, and quality
metadata. I assign train, calibration, and test splits by case rather than by
row. This prevents neighbouring cycles from appearing in both training and
evaluation. OOD rows remain isolated in the OOD split.

### Predictor inputs and outputs

`FittedPredictor` receives the seventeen feature columns and uses train-time
medians for missing numeric values. It returns a continuous
`predicted_urgency`, an uncertainty estimate from the ensemble/conformal
calibration path, and the calibrated radius used by E3. The model is a
regressor; I only derive a binary risk gate for the diagnostic confusion matrix.

### Review outputs

`HumanReviewRouter.apply` preserves the original prediction and adds
`human_review_triggered`, `review_reason`, `expert_estimate`,
`orchestra_urgency`, `human_override`, and `review_mode`. The route uses the
configured budget and never treats the simulated expert as a real operator.

### Scheduling outputs

`LaserWeldingSchedulingEnv.step` returns the next observation, scalar reward,
termination flag, and an info dictionary containing action, urgency, failure,
downtime, maintenance cost, unnecessary action, review status, and provenance.
The reward weights live in `SimulationConfig`; reward values therefore have
meaning only inside this simulator.

### Audit outputs

`hash_trace` serializes stable row values and creates a `previous_hash` /
`row_hash` chain. `audit_report` checks completeness, unique records, action
domain, and hash validity. `counterfactual_tests` changes one observable risk
feature at a time and verifies the expected direction of urgency/action.

## Reproducibility invariants

I preserve these invariants in the code and results:

1. Every random component receives an explicit seed or a seed derived from the documented base seed.
2. Train/calibration/test assignment is case-level.
3. OOD cases are isolated from training and calibration.
4. E5–E7 confidence intervals use one mean per seed as the statistical unit.
5. E8 traces are hash chained after policy execution.
6. The runner writes `resolved_config.json` before generating results and `manifest.json` after completing the run.
7. `plot_results.py` reads archived outputs; it does not retrain models or change metrics.

## How I extend the package

When I add an experiment, I first define its seed, unit of analysis, input
table, output table, figure, and limitation. I then add the implementation to
the appropriate module, write the output under `tables/`, add a figure to
`plot_results.py` when visual evidence is useful, and register the artifact in
`Index.md` and the README. I keep core classes and research-facing functions
documented in English and preserve the simulation-only boundary in the manifest.
