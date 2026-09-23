# ORCHESTRA Week 1 Notebook — English Explanation

I use this guide to explain [`01_simulation_validation_w1.ipynb`](01_simulation_validation_w1.ipynb) cell by cell at the level needed for review and reproducibility. The notebook validates the simulation foundation; it does not attempt to prove that ORCHESTRA is superior to every alternative.

## Global result

The notebook produces 660 synthetic observations:

| Group | Rows | Meaning |
| --- | ---: | --- |
| In-distribution | 600 | Base scenarios used for the train/test split. |
| OOD | 60 | Explicit `ood_focus_drift` stress cases held outside train/test. |
| Train | 450 | In-distribution rows used by the later model stage. |
| Test | 150 | In-distribution rows reserved for evaluation. |

The Week 1 checks cover the scientific contract, schema, missingness,
reproducibility, scenario separation, feature construction, scheduling
environment, baseline policies, traces, and diagnostic evidence.

## Seed and provenance

The notebook uses seed `42`, read from `config/orchestra_config.json`. I reuse
the seed for the base generator, row provenance, train/test assignment,
scheduling context, the random baseline, and environment resets. OOD generation
uses documented derived seeds so the stress cases remain repeatable while being
distinct from the base stream.

`provenance_seed` is metadata, not a physical welding measurement. It records
which deterministic random stream produced a row.

## Data contract

`raw_stream.csv` represents synthetic Machine/IoT Agent observations. The
feature vector contains laser power, welding speed, focal error, shielding gas,
melt-pool temperature, optical signals, plume, spatter, vibration, robot-path
error, bead geometry, porosity, visual defects, lens contamination, cooling
alarm, and time since lens cleaning.

Each row also carries `record_id`, `cycle`, timestamp, scenario, distribution,
seed, provenance, quality flag, and split metadata. OOD rows are retained as a
separate group and are not mixed into train/test.

## Cell-by-cell map

| Cell group | What the code does | Why I need it |
| --- | --- | --- |
| Title and scope | States the Week 1 acceptance question and simulation-only boundary. | Prevents a simulator smoke test from being presented as industrial validation. |
| Executive summary | Lists W1D1–W1D7 artifacts and their locations. | Makes the notebook auditable against the plan. |
| Acceptance logic | Defines the required simulator, schema, provenance, environment, and trace checks. | Explains why E1 comes before model quality. |
| Project setup | Finds the repository root, adds `src` to `sys.path`, creates evidence folders, and records versions. | Makes execution portable and repeatable. |
| Module imports | Imports the production simulator, urgency, scheduling context, environment, policies, and action names. | Keeps notebook logic aligned with source code. |
| Configuration | Loads `orchestra_config.json` and records seed, sample size, split, episode length, and feature count. | Freezes the run contract. |
| Base generation | Calls `generate_laser_welding_data` with seed 42 and the configured sample count. | Produces the in-distribution stream. |
| OOD generation | Creates `ood_focus_drift` rows with a derived seed and stronger sensor/process stress. | Tests distribution shift explicitly. |
| Stream assembly | Concatenates base and OOD data, assigns provenance, and saves the raw CSV. | Creates the auditable input artifact. |
| Schema checks | Verifies required columns, finite numeric values, expected row counts, and scenario names. | Detects broken simulator output early. |
| Missingness checks | Reports missing values and confirms the intended imputation/quality behaviour. | Separates data quality from model performance. |
| Reproducibility check | Regenerates the same seed and compares the result with the saved stream. | Demonstrates deterministic generation. |
| Feature cleaning | Converts numeric columns, applies the project cleaning function, and preserves metadata. | Produces model-ready numeric inputs. |
| Urgency construction | Calls `add_maintenance_urgency` and records process instability, urgency score, and label. | Creates the synthetic target used by later experiments. |
| Scheduling context | Adds production load, resource availability, cost context, and latent hazard fields. | Supplies operational variables to the environment. |
| Feature export | Writes `feature_vector.csv` and checks the seventeen feature columns. | Freezes the model input contract. |
| Target distribution | Uses descriptive statistics and label counts for urgency. | Shows class/target coverage before modelling. |
| Scenario summaries | Groups rows by scenario and distribution. | Confirms normal, degraded, and OOD coverage. |
| Diagnostic plots | Renders sensor and urgency distributions by scenario. | Provides visual plausibility evidence. |
| Environment construction | Creates `LaserMaintenanceSchedulingEnv` with five actions and configured rewards. | Tests the scheduling interface. |
| Reset check | Resets the environment with a fixed seed and inspects the initial observation. | Confirms deterministic state initialization. |
| Action sweep | Applies actions 0–4 and records finite rewards and valid info fields. | Confirms the action domain and reward path. |
| Baseline policies | Evaluates random, no-op, and rule-based controls. | Provides a Week 1 behavioural reference. |
| Trace capture | Stores state, action, reward, urgency, failure, downtime, and cost fields. | Makes one episode reconstructable. |
| Evidence files | Writes sanity CSVs, JSON summaries, plots, and an inventory. | Connects notebook execution to W1D7 delivery. |
| Final assertions | Checks expected files and acceptance flags. | Turns the notebook into a verifiable artifact rather than a visual demo. |

## Synthetic urgency target

The notebook derives `maintenance_urgency_score` from normalized thermal,
power, speed, focus, shielding-gas, optical, spatter, motion, quality, and
maintenance risk components. It then maps the aggregate to 0–100 and labels
rows as low, medium, or high risk. The value is a simulator target, not an
industrial ground-truth label.

## How I interpret the evidence

I use the notebook to establish that the data generator is seeded, the feature
contract is present, OOD rows are isolated, the environment accepts the five
actions, rewards remain finite, and traces can be reconstructed. I do not use
the Week 1 notebook alone to claim model superiority, causal benefit, safety,
operator validity, or production readiness.

For the complete Weeks 1–3 evidence, I use the newer package in
[`src/phd_simulation/`](../phd_simulation/) and its archived outputs in
[`src/results/phd_simulation/`](../results/phd_simulation/). The notebook is a
foundation and historical audit trail; the PhD runner is the primary source
for the final multi-seed tables and figures.
