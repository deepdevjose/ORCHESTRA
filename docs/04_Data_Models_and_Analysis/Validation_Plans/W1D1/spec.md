# ORCHESTRA Validation Specification

## 1. Scope

This project validates ORCHESTRA using a simulation-only laser welding maintenance environment.

This version does not include real hardware validation, live operator studies, or industrial deployment evidence.

## 2. Core Claims

| Claim ID | Claim | Evidence | Acceptance Criterion |
| --- | --- | --- | --- |
| C1 | The synthetic laser welding simulator produces physically plausible normal, degradation, and OOD scenarios. | E1 | Clear separation between normal/focus-drift/OOD cases, documented variables, fixed seed reproducibility, diagnostic plots. |
| C2 | Uncertainty-triggered human review improves decision support compared with non-selective review strategies. | E3, E4 | At equal review budget, uncertainty-triggered review reduces risky decisions or improves review usefulness. |
| C3 | The full ORCHESTRA coordination architecture adds value over simpler baselines and ablated variants. | E5, E6, E9 | Full system performs competitively against baselines, each removed component causes measurable degradation, results use >=5 seeds and 95% CI. |

## 3. Must Not Claim

- ORCHESTRA has been validated on real laser welding hardware.
- ORCHESTRA has been validated with real industrial operators.
- XGBoost or PPO are novel algorithms in this work.
- The system is safety-certified.
- The system is ready for industrial deployment.
- Results generalize to all welding processes.
- The framework has proven causal effects beyond the simulated environment.

## 4. Four-Agent Message Contract

| Agent | Input | Output | Responsibility |
| --- | --- | --- | --- |
| Machine / IoT Agent | Raw laser welding sensor stream | Validated feature vector + provenance | Validate sensor fields, units, missing values, source, timestamp, and quality. |
| AI Predictive Agent | Feature vector | Predicted maintenance urgency | Estimate urgency from current available features. |
| Human Operator Agent | Prediction, uncertainty, severity/context | Review decision and possible override | Review uncertain/high-risk cases under limited review budget. |
| RL Scheduling Agent | Urgency, uncertainty, context, resources | Maintenance action 0-4 | Select maintenance action considering risk, downtime, cost, and resources. |

## 5. Action Space

| Action | Name | Meaning |
| --- | --- | --- |
| 0 | do_nothing | Continue production. |
| 1 | inspect | Inspect machine/process condition. |
| 2 | minor_maintenance | Perform low-impact maintenance. |
| 3 | major_maintenance | Perform major planned maintenance. |
| 4 | urgent_intervention | Immediate intervention for high-risk state. |

## 6. Data Contract

### `raw_stream.csv`

Must contain seeded synthetic laser welding observations, including:

- scenario
- laser process variables
- thermal variables
- optical variables
- motion variables
- quality proxies
- maintenance history variables
- timestamp or cycle index
- random seed

### `feature_vector.csv`

Must contain the model-ready features plus provenance fields:

- record_id
- timestamp or cycle
- scenario
- split
- feature columns
- maintenance_urgency_score
- maintenance_label
- provenance_source
- provenance_seed
- quality_flag

## 7. Reproducibility Contract

Default seed: `42`.

Configuration file:

```text
05_Publications/Journal_Paper/ORCHESTRA-Laser-Welding/config/orchestra_config.json
```

## 8. Logs:

--- 
- Friday Sep 4 15:50: 
    I ran the official ORCHESTRA pipeline with the default configuration.
    The system generated/processed 600 synthetic laser welding samples, trained an XGBoost urgency predictor on 450 rows, evaluated on 150 rows, applied uncertainty-triggered simulated human review, and generated baseline, ablation, and sensitivity result tables.

    This run is a reproducibility smoke test, not final statistical evidence.

    - MAE = 4.96: on average, it is off by about 5 urgency units on a 0-100 scale.
    - RMSE = 6.13: error metric that penalizes larger errors more heavily.
    - R2 = 0.83: the model explains approximately 83% of the variation in the synthetic score.
    - human_review_rate = 0.86: means that the system sent 86% of the test cases for simulated human review.
    - human_override_rate = 0.1933: means that an override occurred in 19.3% of all test cases. Among the reviewed cases, this is approximately 22.5%.