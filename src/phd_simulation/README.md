# ORCHESTRA PhD Simulation Reproduction Guide

I keep this folder as the reproducible simulation package for the four-week
validation plan. It is independent of the inherited Week 1 pipeline so I can
run the paper evidence without changing the original notebook or legacy
outputs.

## Requirements

- Python 3.10 or later.
- Git for checkout and provenance.
- Internet access while installing dependencies.
- Approximately 2 GB of free space for dependencies and generated results.

I do not require a GPU. The full run takes substantially longer than the smoke
run because it trains PPO for five evaluation seeds.

## 1. Clone and open the repository

```bash
git clone <REPOSITORY_URL>
cd ORCHESTRA
```

If I already have the repository, I open a terminal at the ORCHESTRA root. I
run the commands in this guide from that root, not from `src/phd_simulation`.

## 2. Create the Python environment

### Fedora

```bash
sudo dnf install python3 python3-pip python3-devel git
python3 --version
python3 -m venv .venv-phd
source .venv-phd/bin/activate
python -m pip install --upgrade pip
python -m pip install -r src/phd_simulation/requirements.txt
```

### Ubuntu

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git
python3 --version
python3 -m venv .venv-phd
source .venv-phd/bin/activate
python -m pip install --upgrade pip
python -m pip install -r src/phd_simulation/requirements.txt
```

If the current Ubuntu packages do not provide Python 3.10 or later, I install
a compatible version before creating the virtual environment.

### Windows PowerShell

I install Python from <https://www.python.org/downloads/windows/> and enable
**Add Python to PATH**. Then I run:

```powershell
py --version
py -3 -m venv .venv-phd
.\\.venv-phd\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r src\\phd_simulation\\requirements.txt
```

If PowerShell blocks activation, I run PowerShell as the current user and use:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

I can also use `cmd.exe`:

```bat
py -3 -m venv .venv-phd
.venv-phd\\Scripts\\activate.bat
python -m pip install --upgrade pip
python -m pip install -r src\\phd_simulation\\requirements.txt
```

## 3. Run the smoke tests

With the virtual environment active, I run:

```bash
python -m pytest src/phd_simulation/test_smoke.py -q
```

The expected result is three passing tests. These tests check seeded data
reproducibility, OOD isolation, valid actions, finite rewards, and hash-chain
reconstruction. They are execution checks, not the final paper evidence.

## 4. Run the quick smoke experiment

The quick run validates the complete pipeline with fewer cases and no PPO. I
use it to test installation and output paths, not as the final result.

```bash
python src/phd_simulation/run.py --quick --skip-ppo --output-dir results/phd_simulation_smoke
```

The command prints JSON with `status: completed` and writes outputs under
`results/phd_simulation_smoke/`.

## 5. Reproduce the full Weeks 1–3 simulation

I run the default configuration with:

```bash
python src/phd_simulation/run.py
```

The default run uses five evaluation seeds, 180 cases, and 40 steps per
episode. PPO is enabled. To run all analyses except PPO training, I use:

```bash
python src/phd_simulation/run.py --skip-ppo
```

The full Weeks 1–3 run writes:

- `tables/e5_baseline_summary_ci95.csv`, including the homogeneous `ppo_trained` control.
- `tables/e6_ablation_episode_metrics.csv` and `tables/e6_ablation_summary.csv`, with five seeds.
- `tables/e7_sensitivity.csv` and `tables/e7_sensitivity_summary_ci95.csv`, with five seeds per condition.
- `tables/e3_calibration_all_seeds.csv` and `tables/e3_calibration_summary_ci95.csv`.
- `models/ppo_scheduler_seed_<seed>.zip`, one archive per PPO seed.
- E1–E9 figures through the automatic `plot_results.py` call.
- `resolved_config.json` and `manifest.json` with the effective configuration and output inventory.

On Windows PowerShell I can use an explicit configuration path:

```powershell
python src\\phd_simulation\\run.py --config src\\phd_simulation\\default_config.json
```

## 5.1 Generate the paper figures directly

I can regenerate all figures from the frozen CSV and JSON outputs without
rerunning the experiment:

```bash
python -m src.phd_simulation.plot_results \
  --results-dir src/results/phd_simulation
```

The script writes fourteen figures to `src/results/phd_simulation/figures/`
and writes `tables/e3_risk_gate_confusion_matrix.csv`.

The confusion matrix is a derived risk-gate diagnostic. It thresholds the
continuous regression target and prediction at 70, the high-risk threshold
implemented in `review.py`. I do not describe it as a separately trained
classifier.

## 6. Review the archived results

The default output folder is:

```text
src/results/phd_simulation/
```

I use the following artifacts:

- `manifest.json`: execution mode, validation, audit, PPO status, figure status, supported claims, and output inventory.
- `resolved_config.json`: the effective configuration written by the run.
- `data/`: generated trajectories and model-ready exports.
- `figures/`: paper-ready E1–E9 figures.
- `tables/`: CSV tables for inspection and manuscript use.
- `logs/`: audit reports, traces, counterfactuals, and calibration JSON.
- `models/`: PPO model archives when PPO is enabled.

To write a run to another folder, I use:

```bash
python src/phd_simulation/run.py --output-dir results/phd_simulation_repeat
```

## 7. Configuration and reproducibility

The base configuration is [`default_config.json`](default_config.json), and
the dataclass source is [`config.py`](config.py). I can change seeds, case
counts, sensor noise, missing modalities, resource availability, reward
weights, and PPO budgets there.

For a reproducible paper run, I keep the effective configuration next to the
results and preserve the seed list. The current package uses:

- Base seed: `42`.
- Evaluation seeds: `11, 22, 33, 44, 55`.
- 180 cases with 40 cycles per episode.
- Five grouped CV folds.
- Review budget `0.25`.
- 2,000 bootstrap samples.
- PPO enabled for the full run.

The package implements a seeded laser-welding latent simulator with normal,
degraded, and OOD trajectories; case-level separation to prevent temporal
leakage; model validation; uncertainty calibration; simulated human review;
maintenance policies; sensitivity and ablation analysis; confidence
intervals; paired tests; counterfactual checks; and hash-chained audit traces.

In E6, `without_provenance` is a traceability ablation. Provenance is not
currently used as a control feature, so an equal result means that the policy
does not consume provenance for its action, not that provenance has no audit
value. E5–E7 intervals are computed over seed means rather than individual
cycles.

## 8. Interpretation boundaries

All evidence in this folder is simulation-only. The simulator, simulated
expert reviewer, process objectives, and reward function are designed
assumptions rather than real hardware measurements or a real operator study.
The results are not industrial validation, safety certification, or proof of
production deployment.

The most defensible interpretation is that the package demonstrates an
auditable research workflow and a simulated decision-support trade-off. It
does not establish universal policy superiority, strong OOD generalisation,
or a causal effect in a physical cell.

## 9. Deactivate the environment

When I finish a session, I run:

```bash
deactivate
```

In a later session, I return to the repository root and activate the environment
with `source .venv-phd/bin/activate` on Fedora/Ubuntu or
`.\\.venv-phd\\Scripts\\Activate.ps1` on Windows PowerShell.
