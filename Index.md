# ORCHESTRA Research Index

I use this file as the main map for the ORCHESTRA research repository. It
explains what the four-week validation plan asks for, where I keep each item,
how I reproduce the experiments, and how I interpret the evidence. The
current review date is 2026-09-24.

## 1. How I read this repository

I present the current research package as simulation-only evidence. The active
scientific scope covers Weeks 1–3: simulation foundations, prediction and
human-review routing, scheduling, and architecture. The Week 4 paper/archive
activities are described as delivery context rather than as completed
scientific experiments.

My recommended reading order is:

1. I start with the [original four-week validation plan](docs/4_Week_Validation_Plan.docx). An equivalent copy is kept in [`docs/04_Data_Models_and_Analysis/Validation_Plans/`](docs/04_Data_Models_and_Analysis/Validation_Plans/).
2. I read [`VALIDATION_PLAN_README.md`](docs/04_Data_Models_and_Analysis/Validation_Plans/VALIDATION_PLAN_README.md), which maps the plan to repository paths.
3. I read [`src/phd_simulation/README.md`](src/phd_simulation/README.md) and [`default_config.json`](src/phd_simulation/default_config.json).
4. I inspect the frozen run configuration and manifest: [`resolved_config.json`](src/results/phd_simulation/resolved_config.json) and [`manifest.json`](src/results/phd_simulation/manifest.json).
5. I review the E1–E9 tables, logs, models, and figures in [`src/results/phd_simulation/`](src/results/phd_simulation/).
6. I use the current paper draft in [`ORCHESTRA_Laser_Welding_Conference_Draft_05.docx`](docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/00_Manuscript_Current/ORCHESTRA_Laser_Welding_Conference_Draft_05.docx) when I write the research narrative.

## 2. Scientific contract

The source plan defines the following contract, which I preserve when I write
or present results:

| Element | Contract I follow |
| --- | --- |
| Working title | A Simulation-Based Human-Centred Multi-Agent Framework for Predictive Maintenance Decision Support in Laser Welding |
| Evidence scope | Simulation-only validation |
| Planned duration | Four weeks, approximately 160 hours, beginning 2026-09-03 |
| Intended submission | An 8–10 page conference paper plus a reproducible research package |
| Minimum evidence | E1–E9, at least five seeds, and 95% confidence intervals where applicable |
| Language contract | Code, comments, paper text, and technical documentation are written in English |
| Future evidence | Real hardware validation and a real operator study are separate research activities |

I use the Week 1 specification in [`spec.md`](docs/04_Data_Models_and_Analysis/Validation_Plans/W1D1/spec.md) to keep three claims separate: simulator plausibility, review-routing utility, and complete-architecture utility. I do not turn those claims into industrial or causal claims.

### Claims supported by the current package

I can support these statements from the archived run:

- My seeded simulator produces traceable normal, degraded, and OOD trajectories.
- My uncertainty-triggered review policy can be compared with random review at a matched budget.
- My scheduling policies can be compared with confidence intervals, paired tests, sensitivity analysis, and reconstructable traces.
- My dashboard and ESP32 vertical demonstrate an integrated technical workflow, not a validated production cell.

### Claims I do not make

- I do not claim real-hardware or production-cell validation.
- I do not claim a study with real operators; the Human Operator Agent is simulated.
- I do not claim safety certification, deployment readiness, or authority to stop a machine.
- I do not claim causal effects beyond the assumptions implemented by the simulator.
- I do not claim generalisation to every laser-welding process.
- I do not present XGBoost or PPO as novel algorithms; I evaluate them as components inside the architecture.

## 2.1 Production capacity assumption used by the dashboard

I use production capacity as a configurable planning assumption, not as a
measurement of the SIASUN arm. The dashboard models six independent cells that
can work in parallel:

| Reference or assumption | Value | Use in the demonstrator |
| --- | ---: | --- |
| ABB/GAC body-in-white reference | 46 s per body | Order-of-magnitude reference for an integrated automotive line ([ABB source](https://www.abb.com/global/en/areas/robotics/industries/automotive)) |
| ABB/KWD welded component reference | 37 s per component | Order-of-magnitude reference for a component cell ([ABB case](https://destination-zukunft.abb.com/robotik/automobilteile-im-sekundentakt/)) |
| ORCHESTRA conservative assumption | 60 s per piece and cell | Six cells × 1/60 = **0.100 pieces/s**, 6 pieces/min, or 360 pieces/h nominally |

The sixfold multiplication is valid only when each arm/cell makes an
independent piece. If six arms share one vehicle body, the line takt determines
the throughput and I must not multiply it by six. The dashboard makes this
assumption visible and uses an accelerated clock of ten simulated seconds per
tick so I can observe orders and checkpoints during a demonstration.

## 3. Source-of-truth map

| Area | Current source | What I find there | How I use it |
| --- | --- | --- | --- |
| Primary E1–E9 evidence | [`src/phd_simulation/`](src/phd_simulation/) and [`src/results/phd_simulation/`](src/results/phd_simulation/) | Reproducible PhD package and frozen results | Primary source for the paper |
| Week 1 foundations | [`src/src/orchestra_laser/`](src/src/orchestra_laser/), [`src/notebooks/`](src/notebooks/), and [`docs/04_Data_Models_and_Analysis/Validation_Plans/`](docs/04_Data_Models_and_Analysis/Validation_Plans/) | Smoke test, notebook, original simulator, and historical E1 evidence | Supporting foundation; I do not mix its metrics with E1–E9 PhD metrics |
| Legacy pipeline | [`src/scripts/run_pipeline.py`](src/scripts/run_pipeline.py), [`src/src/orchestra_laser/`](src/src/orchestra_laser/), and [`src/results/tables/`](src/results/tables/) | Earlier 600-row XGBoost, review, baseline, and sensitivity pipeline | Historical comparison only; I label it separately |
| Paper workspace | [`docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/`](docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/) | Current draft, versions, figures, and supporting material | Manuscript preparation |
| Dashboard and edge demonstrator | [`src/ui/`](src/ui/), [`src/scripts/live_inference_service.py`](src/scripts/live_inference_service.py), [`src/firmware/`](src/firmware/), and [`simulation/`](simulation/) | MQTT transport, UI, model bridge, broker, and ESP32 firmware | Technical demonstrator; not industrial evidence |
| Framework and background | [`docs/01_Ethics_Proposal_and_Approvals/`](docs/01_Ethics_Proposal_and_Approvals/), [`docs/02_Literature_Review_and_References/`](docs/02_Literature_Review_and_References/), [`docs/03_Framework_and_Methodology/`](docs/03_Framework_and_Methodology/), and [`docs/04_Data_Models_and_Analysis/`](docs/04_Data_Models_and_Analysis/) | Ethics, literature, IAPM framework, datasets, and historical analyses | Context; I reconcile every claim with the current code |

I keep these result families separate:

- [`src/results/phd_simulation/`](src/results/phd_simulation/) contains the complete five-seed E1–E9 package.
- [`results/phd_simulation_smoke/`](results/phd_simulation_smoke/) is a quick smoke run with two seeds and no PPO; I use it only to test the execution path.
- [`src/results/tables/`](src/results/tables/) belongs to the earlier 600-row pipeline and does not share the same experimental design.

## 4. E1–E9 evidence map

I use **Verified** when the result exists in the archived run and can be
reproduced. I use **Scope note** when the result is valid for the simulation
but should not be extended beyond it. I use **Statistical caution** when the
experiment is complete but the result does not support a strong significance
claim.

| ID | Plan requirement | Evidence and code | Interpretation I use |
| --- | --- | --- | --- |
| E1 | Simulator validity: normal, degraded, and OOD trajectories | [`dataset_validation.json`](src/results/phd_simulation/logs/dataset_validation.json), [`raw_stream.csv`](src/results/phd_simulation/data/raw_stream.csv), [`feature_vector.csv`](src/results/phd_simulation/data/feature_vector.csv), [`e1_dataset_overview.png`](src/results/phd_simulation/figures/e1_dataset_overview.png), [`scenario_plausibility_checks.csv`](docs/04_Data_Models_and_Analysis/Validation_Plans/W1D2/scenario_plausibility_checks.csv) | **Verified for simulation.** The complete run contains 7,200 rows, 180 cases, 1,080 OOD rows, finite features, and isolated OOD cases. I do not call this physical hardware validation. |
| E2 | XGBoost, five-fold CV, MAE/RMSE/R², SHAP, and model comparison | [`e2_xgboost_cv.csv`](src/results/phd_simulation/tables/e2_xgboost_cv.csv), [`e2_model_comparison.csv`](src/results/phd_simulation/tables/e2_model_comparison.csv), [`e2_model_comparison.png`](src/results/phd_simulation/figures/e2_model_comparison.png), [`e2_model_cv_distributions.png`](src/results/phd_simulation/figures/e2_model_cv_distributions.png), [`e2_feature_importance.png`](src/results/phd_simulation/figures/e2_feature_importance.png), [`e2_feature_importance.csv`](src/results/phd_simulation/tables/e2_feature_importance.csv) | **Verified.** XGBoost reaches mean CV MAE ≈ 4.347, RMSE ≈ 5.734, and R² ≈ 0.840. HistGradientBoosting and Random Forest perform better in this run, so I describe XGBoost as a viable component rather than the best model. |
| E3 | Uncertainty calibration and error–uncertainty relationship | [`e3_calibration.csv`](src/results/phd_simulation/tables/e3_calibration.csv), [`e3_calibration_all_seeds.csv`](src/results/phd_simulation/tables/e3_calibration_all_seeds.csv), [`e3_calibration_summary_ci95.csv`](src/results/phd_simulation/tables/e3_calibration_summary_ci95.csv), [`e3_calibration_summary.png`](src/results/phd_simulation/figures/e3_calibration_summary.png), [`e3_uncertainty_error.png`](src/results/phd_simulation/figures/e3_uncertainty_error.png), [`e3_risk_gate_confusion_matrix.png`](src/results/phd_simulation/figures/e3_risk_gate_confusion_matrix.png), [`e3_risk_gate_confusion_matrix.csv`](src/results/phd_simulation/tables/e3_risk_gate_confusion_matrix.csv) | **Verified with an OOD scope note.** Test coverage is ≈ 0.909; OOD coverage falls to ≈ 0.559 and OOD uncertainty–error Spearman correlation is ≈ −0.150. The confusion matrix is a derived risk gate, not a second classifier. |
| E4 | Review routing against no-review, random, and all-review at matched budgets | [`e4_review_threshold_sweep.csv`](src/results/phd_simulation/tables/e4_review_threshold_sweep.csv), [`e4_review_budget.png`](src/results/phd_simulation/figures/e4_review_budget.png), [`e4_review_tradeoffs.png`](src/results/phd_simulation/figures/e4_review_tradeoffs.png), [`review.py`](src/phd_simulation/review.py) | **Verified for the simulated study.** At budget 0.25, uncertainty-triggered review reaches high-risk recall ≈ 0.531 versus ≈ 0.255 for random review and leaves 134 risky decisions versus 213. The reviewer is simulated. |
| E5 | Full ORCHESTRA against baselines and PPO-only control | [`e5_baseline_summary_ci95.csv`](src/results/phd_simulation/tables/e5_baseline_summary_ci95.csv), [`e5_policy_metrics.png`](src/results/phd_simulation/figures/e5_policy_metrics.png), [`e5_policy_tradeoff.png`](src/results/phd_simulation/figures/e5_policy_tradeoff.png), [`e5_e9_episode_metrics_all_seeds.csv`](src/results/phd_simulation/tables/e5_e9_episode_metrics_all_seeds.csv), [`e5_ppo_trained_episode_metrics.csv`](src/results/phd_simulation/tables/e5_ppo_trained_episode_metrics.csv), [`ppo.py`](src/phd_simulation/ppo.py) | **Verified for simulation.** The homogeneous comparison includes `ppo_trained`, uses the same unit of analysis, and reports CI95 over five seed means. `predicted_urgency_only` remains a heuristic control, not PPO. |
| E6 | Ablations for review, PPO, XGBoost, provenance, and trigger | [`e6_ablation_summary.csv`](src/results/phd_simulation/tables/e6_ablation_summary.csv), [`e6_ablation_metrics.png`](src/results/phd_simulation/figures/e6_ablation_metrics.png), [`e6_ablation_episode_metrics.csv`](src/results/phd_simulation/tables/e6_ablation_episode_metrics.csv), [`runner.py`](src/phd_simulation/runner.py) | **Verified with an attribution note.** Every variant uses five seeds. `without_provenance` is a traceability ablation: provenance is not currently a control feature, so an equal result does not imply that provenance has no audit value. |
| E7 | Sensitivity to noise, missing modalities, drift, OOD, resources, and delay | [`e7_sensitivity.csv`](src/results/phd_simulation/tables/e7_sensitivity.csv), [`e7_sensitivity_summary_ci95.csv`](src/results/phd_simulation/tables/e7_sensitivity_summary_ci95.csv), [`e7_sensitivity_metrics.png`](src/results/phd_simulation/figures/e7_sensitivity_metrics.png), [`runner.py`](src/phd_simulation/runner.py) | **Verified for simulation.** Seven conditions are repeated over five seeds, with CI95 computed from seed-level means. I describe this as simulator sensitivity, not industrial robustness. |
| E8 | Complete traces and ten counterfactual checks | [`e8_audit_report.json`](src/results/phd_simulation/logs/e8_audit_report.json), [`e8_audit_quality.png`](src/results/phd_simulation/figures/e8_audit_quality.png), [`e8_full_orchestra_audit_trace.csv`](src/results/phd_simulation/logs/e8_full_orchestra_audit_trace.csv), [`e8_counterfactuals.csv`](src/results/phd_simulation/logs/e8_counterfactuals.csv), [`audit.py`](src/phd_simulation/audit.py) | **Verified for simulation.** The run reports 800/800 complete rows, a valid hash chain, and 10/10 passed counterfactuals. This supports reconstruction under the simulated schema, not a real-cell audit. |
| E9 | Five seeds, mean ± CI95, and paired tests | [`e9_paired_statistics.csv`](src/results/phd_simulation/tables/e9_paired_statistics.csv), [`e9_paired_effects.png`](src/results/phd_simulation/figures/e9_paired_effects.png), [`stats.py`](src/phd_simulation/stats.py) | **Statistical caution.** Wilcoxon and bootstrap results are present, but reward, failures, and downtime all have p = 0.0625. I do not claim significance at α = 0.05. |

### Reproducible run snapshot

The [`manifest.json`](src/results/phd_simulation/manifest.json) records
`seed=42`, evaluation seeds `[11, 22, 33, 44, 55]`, 180 cases, 40 episode
steps, five CV folds, review budget 0.25, 2,000 bootstrap samples, PPO
completion, audit metrics, and the generated figure package. The archived
dataset validation records 7,200 rows: 3,640 train, 1,240 calibration, 1,240
test, and 1,080 OOD.

## 4.1 Paper-ready figure package

I generate all figures from the frozen CSV and JSON outputs with
[`plot_results.py`](src/phd_simulation/plot_results.py). The script does not
change the experiment or manually edit images, so each figure remains tied to
the archived run.

| Evidence | Figure(s) | What I use it to show |
| --- | --- | --- |
| E1 | [`e1_dataset_overview.png`](src/results/phd_simulation/figures/e1_dataset_overview.png) | Explicit data partitions and the target distribution across in-distribution and OOD splits. |
| E2 | [`e2_model_comparison.png`](src/results/phd_simulation/figures/e2_model_comparison.png), [`e2_model_cv_distributions.png`](src/results/phd_simulation/figures/e2_model_cv_distributions.png), [`e2_feature_importance.png`](src/results/phd_simulation/figures/e2_feature_importance.png) | MAE/RMSE/R² comparison, fold variability, and variables associated with the target. |
| E3 | [`e3_calibration_summary.png`](src/results/phd_simulation/figures/e3_calibration_summary.png), [`e3_uncertainty_error.png`](src/results/phd_simulation/figures/e3_uncertainty_error.png), [`e3_risk_gate_confusion_matrix.png`](src/results/phd_simulation/figures/e3_risk_gate_confusion_matrix.png) | In-distribution calibration, OOD degradation, and high-risk gating behaviour. |
| E4 | [`e4_review_tradeoffs.png`](src/results/phd_simulation/figures/e4_review_tradeoffs.png) | Uncertainty-triggered routing versus random, no-review, and all-review controls. |
| E5 | [`e5_policy_metrics.png`](src/results/phd_simulation/figures/e5_policy_metrics.png), [`e5_policy_tradeoff.png`](src/results/phd_simulation/figures/e5_policy_tradeoff.png) | The trade-off between reward, failures, downtime, cost, and interventions. |
| E6–E7 | [`e6_ablation_metrics.png`](src/results/phd_simulation/figures/e6_ablation_metrics.png), [`e7_sensitivity_metrics.png`](src/results/phd_simulation/figures/e7_sensitivity_metrics.png) | Component contribution and behaviour under simulated operating changes. |
| E8–E9 | [`e8_audit_quality.png`](src/results/phd_simulation/figures/e8_audit_quality.png), [`e9_paired_effects.png`](src/results/phd_simulation/figures/e9_paired_effects.png) | Trace integrity and the still-inconclusive paired effect estimates. |

The target is continuous regression, not classification. I therefore treat the
confusion matrix as a derived diagnostic: I threshold
`maintenance_urgency_score` and `predicted_urgency` at 70, the high-risk gate
used by [`review.py`](src/phd_simulation/review.py). In the current run, the
test split has no positive high-risk rows and the OOD panel contains 286 true
high-risk rows that are not recovered by the thresholded prediction. I keep
this figure because it makes the OOD limitation visible; I do not use it as a
claim of classifier performance.

## 4.2 Dashboard capture register

The dashboard screenshots are retained as a chronological troubleshooting and
demonstration record. Images 01–04 show the disconnected or synthetic
fallback state. Images 05–10 show the same vertical after the ESP32 was
reflashed onto the external Wi-Fi network and began publishing MQTT telemetry.
The live group still uses `USE_SIMULATED_SENSORS=true`, so the transport and
orchestration path is demonstrated with firmware-generated values rather than
calibrated physical sensors.

| Image | ESP32/MQTT state | What the image shows | Evidence interpretation |
| --- | --- | --- | --- |
| [`01_control_room_simulation.png`](dashboard_simulation_pictures/01_control_room_simulation.png) | **Not connected**; synthetic fallback, no Orion MQTT frames | First-run production-order setup, six-cell fleet context, SIASUN SR12A scene, and the 17-feature contract. | Records the initial simulation configuration and disconnected baseline. |
| [`02_model_observatory_simulation.png`](dashboard_simulation_pictures/02_model_observatory_simulation.png) | **Not connected**; all visible machines are synthetic | Model Observatory with telemetry-quality, XGBoost predictive, and checkpoint-scheduler agents; urgency/uncertainty trace and fleet comparison. | Shows the model-laboratory fallback before physical MQTT was available. |
| [`03_control_room_production_started.png`](dashboard_simulation_pictures/03_control_room_production_started.png) | **Not connected**; `0 FROM MQTT`, fleet marked `SIM` | Active order, checkpoint scheduler, fleet review queue, machine urgency cards, and operator-aware decision rail. | Demonstrates order-aware simulation behaviour without physical edge telemetry. |
| [`04_model_observatory_human_decision_trace.png`](dashboard_simulation_pictures/04_model_observatory_human_decision_trace.png) | **Not connected**; synthetic decision record | Cell 04 review gate, three-agent trace, maintenance-hold state, and append-only simulated operator decision. | Demonstrates human-in-the-loop logic in the synthetic fallback. |
| [`05_control_room_orion_mqtt_viewport.png`](dashboard_simulation_pictures/05_control_room_orion_mqtt_viewport.png) | **Connected**; Cell 01 identified as `MQTT` | Live control room with Cell 01 / ESP32 prototype, accepted frames, order progress, fleet urgency, and review status. | Live Wi-Fi/MQTT/dashboard integration evidence; not calibrated sensor validation. |
| [`06_model_observatory_orion_mqtt.png`](dashboard_simulation_pictures/06_model_observatory_orion_mqtt.png) | **Connected**; MQTT source selected for Cell 01 | 17-feature telemetry quality, XGBoost inference, three-agent bounded trace, urgency/uncertainty chart, and gate activity. | Shows real telemetry transport entering the model and review loop. |
| [`07_control_room_orion_process_view.png`](dashboard_simulation_pictures/07_control_room_orion_process_view.png) | **Connected**; `MQTT LIVE` | Cell 01 SIASUN SR12A view, 17 numeric process fields, MQTT gateway identity, and urgency trajectory. | Shows the end-to-end edge payload as rendered by the dashboard. |
| [`08_control_room_orion_focal_offset_mqtt.png`](dashboard_simulation_pictures/08_control_room_orion_focal_offset_mqtt.png) | **Connected**; MQTT scenario command accepted | `focal_offset` response with Cell 01 risk increase, one high-risk fleet item, and review gate activation. | Demonstrates command-to-telemetry-to-decision propagation through the live demonstrator. |
| [`09_model_observatory_orion_focal_offset.png`](dashboard_simulation_pictures/09_model_observatory_orion_focal_offset.png) | **Connected**; Cell 01 MQTT stream under `focal_offset` | Model-laboratory response with adjusted urgency, uncertainty, agent decisions, and live gate events. | Shows model observability for a controlled firmware-generated scenario. |
| [`10_control_room_orion_focal_offset_process_view.png`](dashboard_simulation_pictures/10_control_room_orion_focal_offset_process_view.png) | **Connected**; `MQTT LIVE` | `Focal_offset`, focal-position error around 0.407 mm, bead-width change, process values, and review trajectory. | Paper-ready process detail for the integration demonstrator; not a physical calibration result. |

The disconnected images are intentionally preserved: they document the
failure mode that motivated the network reconfiguration and make the later
MQTT-connected evidence auditable. The connected images demonstrate firmware
upload, Wi-Fi association, MQTT publish/subscribe, gateway ingestion, model
scoring, and human-review routing. They do not establish industrial
deployment, sensor calibration, safety certification, causal superiority, or
a real operator study.

## 4.3 How I justify the multi-agent framework

I do not conclude that ORCHESTRA always wins. I make the narrower and more
defensible claim that the framework works as a simulated, auditable
decision-support workflow because it connects prediction, uncertainty,
review, scheduling, and traceability in one evaluation unit. The evidence does
not establish industrial superiority or real-world causality.

| Question | Evidence I observe | Interpretation I use |
| --- | --- | --- |
| Does the predictor work? | E2 gives XGBoost MAE ≈ 4.347, while HistGradientBoosting reaches ≈ 4.036 and Random Forest ≈ 4.146. | The predictor is useful enough to support routing, but the contribution is architectural rather than a claim that XGBoost is the best model. |
| Does review routing add information? | At review budget 0.25, uncertainty-triggered review reaches recall ≈ 0.531 versus ≈ 0.255 for random review and leaves 134 versus 213 risky decisions. | The simulated review gate selects more informative cases under a fixed budget. The reviewer remains synthetic. |
| Does the policy reduce failures? | `full_orchestra` averages 0 failures versus ≈ 11.17 for `predicted_urgency_only`, but it also averages ≈ 15.1 downtime and ≈ 14.4 cost versus ≈ 1.76 and ≈ 1.24. | The policy shifts the simulated trade-off toward prevention by paying for more maintenance interventions. I report both sides. |
| Does every agent contribute independently? | Removing review changes reward to ≈ −518.8 and failures to ≈ 11.17. Removing PPO or XGBoost changes the outcome less, while `without_provenance` matches the full policy. | Review has the clearest operational signal. PPO, XGBoost, and provenance do not receive isolated causal attribution in this design; provenance supports auditability rather than control. |
| Is the evidence statistically conclusive? | E9 includes five seeds, but all reported paired p-values are 0.0625. | The effect direction is promising but not confirmatory at α = 0.05. |
| Does the model generalise OOD? | E3 coverage is ≈ 0.909 on test and ≈ 0.559 on OOD; OOD Spearman uncertainty–error correlation is ≈ −0.150. | No strong OOD claim is justified. This is the main model limitation in the current package. |
| Can I reconstruct decisions? | E8 reports 800/800 complete traces, a valid hash chain, and 10/10 passed counterfactual checks. | The workflow is auditable within the simulated schema; this is not plant certification. |

I use the following sentence as a technically accurate paper summary:

> In the seeded simulation, ORCHESTRA provides an auditable multi-agent decision-support workflow and improves simulated high-risk routing and failure avoidance at the cost of additional maintenance interventions; however, OOD calibration degradation and non-significant paired comparisons prevent claims of general industrial superiority.

## 5. Week-by-week map

### Week 1 — Foundations and freeze

| Plan day | Current location | What I find there |
| --- | --- | --- |
| W1D1 | [`W1D1/spec.md`](docs/04_Data_Models_and_Analysis/Validation_Plans/W1D1/spec.md) | Scope, C1–C3, prohibited claims, four-agent contract, five actions, data, and reproducibility requirements. |
| W1D2 | [`simulator.py`](src/phd_simulation/simulator.py), [`W1D2/`](docs/04_Data_Models_and_Analysis/Validation_Plans/W1D2/) | Latent process generator, sensor noise, missingness, scenarios, raw stream, OOD cases, and plausibility checks. |
| W1D3 | [`schema.py`](src/phd_simulation/schema.py), [`W1D3/`](docs/04_Data_Models_and_Analysis/Validation_Plans/W1D3/) | Seventeen features, metadata, provenance, labels, and case-level splits. |
| W1D4 | [`environment.py`](src/phd_simulation/environment.py), [`test_smoke.py`](src/phd_simulation/test_smoke.py), [`W1D4/week1_environment_sanity.csv`](docs/04_Data_Models_and_Analysis/Validation_Plans/W1D4/week1_environment_sanity.csv) | Seven state variables, five actions, reward, downtime, cost, failures, and resource constraints. |
| W1D5 | [`config.py`](src/phd_simulation/config.py), [`default_config.json`](src/phd_simulation/default_config.json), [`runner.py`](src/phd_simulation/runner.py) | Frozen configuration, seeds, logging, and reproducible execution. |
| W1D6 | [`W1D6/figures/`](docs/04_Data_Models_and_Analysis/Validation_Plans/W1D6/figures/), [`src/results/figures/`](src/results/figures/), [`plot_results.py`](src/phd_simulation/plot_results.py) | Historical Week 1 figures and the reproducible E1–E9 figure package. |
| W1D7 | [`W1D7/week1_deliverable_summary.json`](docs/04_Data_Models_and_Analysis/Validation_Plans/W1D7/week1_deliverable_summary.json), [`manifest.json`](src/results/phd_simulation/manifest.json) | Summary, evidence inventory, checks, and supported claims. |

The inherited Week 1 evidence contains 660 rows, 600 in-distribution rows, 60
OOD rows, seed 42, a 450/150/60 split, and successful checks. Its JSON files
contain absolute paths from an earlier checkout, so I use the relative paths
listed in this repository when I deliver the work.

### Week 2 — Prediction and human review

| Plan day | Code | Evidence |
| --- | --- | --- |
| W2D1 | [`prediction.py`](src/phd_simulation/prediction.py), `fit_xgb_with_calibration`, `group_cross_validate` | [`e2_xgboost_cv.csv`](src/results/phd_simulation/tables/e2_xgboost_cv.csv), [`e2_model_cv_folds.csv`](src/results/phd_simulation/tables/e2_model_cv_folds.csv) |
| W2D2 | `feature_importance` in [`prediction.py`](src/phd_simulation/prediction.py) | [`e2_feature_importance.csv`](src/results/phd_simulation/tables/e2_feature_importance.csv); physical plausibility is interpreted through [`simulator.py`](src/phd_simulation/simulator.py). |
| W2D3 | `calibration_metrics` and `FittedPredictor.uncertainty` in [`prediction.py`](src/phd_simulation/prediction.py) | [`e3_calibration.csv`](src/results/phd_simulation/tables/e3_calibration.csv), seed-level calibration tables, and [`e3_calibration.json`](src/results/phd_simulation/logs/e3_calibration.json) |
| W2D4 | [`review.py`](src/phd_simulation/review.py) | `HumanReviewRouter`, uncertainty/conflict/risk priorities, fixed review budget, and actions 0–4 |
| W2D5 | `_run_review_study` in [`runner.py`](src/phd_simulation/runner.py) | [`e4_review_threshold_sweep.csv`](src/results/phd_simulation/tables/e4_review_threshold_sweep.csv) |
| W2D6 | `random_review`, `uncertainty_triggered`, `no_review`, and `all_review` in [`review.py`](src/phd_simulation/review.py) | Matched-budget E4 comparison |
| W2D7 | [`resolved_config.json`](src/results/phd_simulation/resolved_config.json), [`manifest.json`](src/results/phd_simulation/manifest.json) | Archived effective configuration and interpretation boundaries |

### Week 3 — Scheduling and architecture

| Plan day | Code | Evidence |
| --- | --- | --- |
| W3D1 | [`ppo.py`](src/phd_simulation/ppo.py), [`environment.py`](src/phd_simulation/environment.py) | [`ppo_scheduler_seed_<seed>.zip`](src/results/phd_simulation/models/), [`e5_ppo_trained_episode_metrics.csv`](src/results/phd_simulation/tables/e5_ppo_trained_episode_metrics.csv), and the homogeneous PPO baseline |
| W3D2 | `_run_ablations` in [`runner.py`](src/phd_simulation/runner.py) | [`e6_ablation_summary.csv`](src/results/phd_simulation/tables/e6_ablation_summary.csv), with CI95 and `n_seeds=5` |
| W3D3 | [`policies.py`](src/phd_simulation/policies.py) | [`e5_baseline_summary_ci95.csv`](src/results/phd_simulation/tables/e5_baseline_summary_ci95.csv) and seed-level metrics |
| W3D4 | `without_review`, `without_ppo`, `without_xgboost`, `without_provenance`, and `without_uncertainty_trigger` in [`runner.py`](src/phd_simulation/runner.py) | [`e6_ablation_episode_metrics.csv`](src/results/phd_simulation/tables/e6_ablation_episode_metrics.csv) |
| W3D5 | `_run_sensitivity` in [`runner.py`](src/phd_simulation/runner.py), options in [`simulator.py`](src/phd_simulation/simulator.py) | [`e7_sensitivity.csv`](src/results/phd_simulation/tables/e7_sensitivity.csv) and [`e7_sensitivity_summary_ci95.csv`](src/results/phd_simulation/tables/e7_sensitivity_summary_ci95.csv) |
| W3D6 | [`audit.py`](src/phd_simulation/audit.py) | [`e8_audit_report.json`](src/results/phd_simulation/logs/e8_audit_report.json), hash chain, trace, and ten counterfactuals |
| W3D7 | [`runner.py`](src/phd_simulation/runner.py), [`manifest.json`](src/results/phd_simulation/manifest.json) | Complete run frozen on 2026-09-24: five seeds, PPO completed, E6/E7 repeated, 800/800 trace rows, and 10/10 counterfactuals |

### Week 4 — Paper and archive context

I treat Week 4 as a packaging and manuscript phase rather than as an
additional experiment in this review. The current draft has sections 1–6 and
references, but its verified conversion is four A4 pages rather than the
planned 8–10 pages. The repository already contains the code, configuration,
results, manifest, traces, figures, and reproduction instructions. It does
not contain a verified Docker archive or an advisor pre-review note.

## 6. Code documentation map

I keep the implementation in English and use the following map to explain what
each module owns. Public classes/functions carry English docstrings where they
define a research contract; the repository READMEs and this index describe the
cross-module behaviour and output provenance.

### 6.1 Core `src/phd_simulation` package

| File | Responsibility |
| --- | --- |
| [`config.py`](src/phd_simulation/config.py) | `SimulationConfig`, default paths, seed lists, reward weights, JSON loading, and effective-config writing. |
| [`schema.py`](src/phd_simulation/schema.py) | Feature columns, metadata columns, action names, scenario names, and the schema contract. |
| [`simulator.py`](src/phd_simulation/simulator.py) | Seeded latent trajectories, sensor noise, missingness, degradation, OOD generation, case-level splits, clipping, and validation. |
| [`prediction.py`](src/phd_simulation/prediction.py) | Regression models, grouped CV, XGBoost calibration, ensemble uncertainty, metrics, and feature importance. |
| [`review.py`](src/phd_simulation/review.py) | Simulated observable expert signal, conflict score, budgeted review routing, decision adjustment, and risk metrics. |
| [`environment.py`](src/phd_simulation/environment.py) | Five-action scheduling environment, state vector, reward terms, resource constraints, episode execution, and trace fields. |
| [`policies.py`](src/phd_simulation/policies.py) | Corrective, periodic, alert-only, rule-based, urgency-only, full ORCHESTRA, and ablation policies. |
| [`ppo.py`](src/phd_simulation/ppo.py) | Gymnasium adapter, Stable-Baselines3 PPO training, PPO evaluation, and PPO trace output. |
| [`audit.py`](src/phd_simulation/audit.py) | Canonical row serialization, hash-chain construction, audit metrics, and one-feature counterfactual checks. |
| [`stats.py`](src/phd_simulation/stats.py) | Mean confidence intervals, grouped aggregation, paired tests, and bootstrap difference intervals. |
| [`runner.py`](src/phd_simulation/runner.py) | End-to-end orchestration of generation, E2–E9 analyses, figures, PPO, manifest, and output directories. |
| [`plot_results.py`](src/phd_simulation/plot_results.py) | Reproducible paper figures from archived CSV/JSON outputs, including the derived E3 risk-gate matrix. |
| [`run.py`](src/phd_simulation/run.py) | CLI entry point for full runs, quick smoke runs, PPO control, and output-directory selection. |
| [`test_smoke.py`](src/phd_simulation/test_smoke.py) | Lightweight tests for seeded generation, action validity, finite rewards, and hash-chain reconstruction. |
| [`CODE_GUIDE.md`](src/phd_simulation/CODE_GUIDE.md) | English module contracts, data contracts, reproducibility invariants, and extension rules. |

### 6.2 Legacy pipeline and scripts

| File or folder | Responsibility |
| --- | --- |
| [`src/scripts/run_pipeline.py`](src/scripts/run_pipeline.py) | Earlier end-to-end pipeline for synthetic data, urgency, model training, review, baselines, and tables. |
| [`src/scripts/train_ppo.py`](src/scripts/train_ppo.py) | Earlier PPO training entry point; I keep its outputs separate from the PhD package. |
| [`src/scripts/live_inference_service.py`](src/scripts/live_inference_service.py) | Small HTTP model bridge used by the live dashboard. |
| [`src/src/orchestra_laser/`](src/src/orchestra_laser/) | Earlier synthetic data, urgency, predictive agent, human agent, scheduling environment, baselines, and experiment helpers. |
| [`src/notebooks/01_simulation_validation_w1.ipynb`](src/notebooks/01_simulation_validation_w1.ipynb) | Executable Week 1 notebook with the original simulation validation. |
| [`src/notebooks/01_simulation_validation_w1_explained.md`](src/notebooks/01_simulation_validation_w1_explained.md) | English cell-by-cell explanation of the Week 1 notebook. |

### 6.3 Dashboard and live model bridge

| File | Responsibility |
| --- | --- |
| [`src/ui/app/page.tsx`](src/ui/app/page.tsx) | Operations view, first-run production order, checkpoints, reset actions, maintenance decisions, and fleet cards. |
| [`src/ui/app/models/page.tsx`](src/ui/app/models/page.tsx) | Model Observatory, three-agent registry, per-robot decision trace, uncertainty, and provenance views. |
| [`src/ui/app/components/RobotScene.tsx`](src/ui/app/components/RobotScene.tsx) | Local Three.js SIASUN SR12A scene with a lowered floor, lifted model, local Draco decoder, and responsive resize. |
| [`src/ui/lib/types.ts`](src/ui/lib/types.ts) | TypeScript contracts for telemetry, production orders, agent traces, decisions, fleet machines, and dashboard state. |
| [`src/ui/lib/live-service.ts`](src/ui/lib/live-service.ts) | MQTT plus synthetic feed, smoothing, order/checkpoint progression, maintenance wear, lifetime reset, inference, and agent decisions. |
| [`src/ui/lib/demo.ts`](src/ui/lib/demo.ts) | Deterministic six-cell fallback feed: one reserved ESP32 edge slot plus five synthetic streams. |
| [`src/ui/lib/model-client.ts`](src/ui/lib/model-client.ts) | HTTP call to the Predictive Agent bridge with fallback scoring. |
| [`src/ui/app/api/stream/route.ts`](src/ui/app/api/stream/route.ts) | Server-sent event stream for dashboard telemetry and decisions. |
| [`src/ui/app/api/state/route.ts`](src/ui/app/api/state/route.ts) | Current dashboard state endpoint. |
| [`src/ui/app/api/command/route.ts`](src/ui/app/api/command/route.ts) | Human command endpoint, including maintenance, scenario, and lifetime reset actions. |
| [`src/ui/app/api/simulation/route.ts`](src/ui/app/api/simulation/route.ts) | Production-order configuration, simulation reset, and failure-horizon control. |
| [`src/ui/app/globals.css`](src/ui/app/globals.css) | Full-width responsive industrial UI, order/checkpoint controls, fleet cards, agent traces, and model-laboratory layout. |
| [`src/ui/package.json`](src/ui/package.json) | Next.js, React, MQTT, Three.js dependencies and build/typecheck commands. |
| [`src/ui/public/3D_models/siasunsr12a.glb`](src/ui/public/3D_models/siasunsr12a.glb) | Local robot model asset. |
| [`src/ui/public/draco/`](src/ui/public/draco/) | Local Draco decoder files for the compressed GLB. |

The UI labels itself as a synthetic laboratory feed and does not claim
automatic stop authority. I preserve that boundary in the interface because
the dashboard is a demonstrator, not a safety controller.

### 6.4 ESP32 firmware and broker

| File | Responsibility |
| --- | --- |
| [`src/firmware/platformio.ini`](src/firmware/platformio.ini) | ESP32 Dev Module target, Arduino framework, PubSubClient, serial monitor, and upload settings. |
| [`src/firmware/include/config.example.h`](src/firmware/include/config.example.h) | Safe template for Wi-Fi, broker, topics, device, station, and simulated sensors. |
| [`src/firmware/include/config.h`](src/firmware/include/config.h) | Loads ignored local configuration when available and otherwise uses safe example values. |
| [`src/firmware/include/config.local.h`](src/firmware/include/config.local.h) | Ignored local laboratory configuration; I never copy its credentials into the paper. |
| [`src/firmware/src/main.cpp`](src/firmware/src/main.cpp) | Wi-Fi, 17 telemetry fields, 2.5-second telemetry publishing, command handling, status, acknowledgements, maintenance wear, and lifetime reset. |
| [`src/firmware/README.md`](src/firmware/README.md) | Firmware setup, topics, payloads, commands, smoke procedure, and prototype boundaries. |
| [`simulation/mosquitto/mosquitto.conf`](simulation/mosquitto/mosquitto.conf) | Isolated laboratory Mosquitto listener on TCP 1883 without persistence. |
| [`simulation/docker-compose.yml`](simulation/docker-compose.yml) | Reproducible Mosquitto service. |
| [`simulation/README_WINDOWS.md`](simulation/README_WINDOWS.md), [`README_UBUNTU.md`](simulation/README_UBUNTU.md), [`README_FEDORA.md`](simulation/README_FEDORA.md) | Platform-specific dashboard, broker, and ESP32 operation guides. |

The UI can use `mqtt://127.0.0.1:1883` locally, while the ESP32 must use the
computer's actual IPv4 address on the same isolated access point. Simulated
sensors validate transport and integration; they do not represent calibrated
physical sensors.

## 7. Data, variables, and provenance

### 7.1 The seventeen feature contract

I define the feature contract in [`schema.py`](src/phd_simulation/schema.py),
[`src/config/orchestra_config.json`](src/config/orchestra_config.json),
[`src/ui/lib/types.ts`](src/ui/lib/types.ts), and
[`src/firmware/src/main.cpp`](src/firmware/src/main.cpp):

`laser_power_w`, `welding_speed_mm_s`, `focal_position_error_mm`,
`shielding_gas_flow_l_min`, `melt_pool_temp_c`, `back_reflection_intensity`,
`plume_intensity`, `spatter_count`, `vibration_rms`, `robot_path_error_mm`,
`bead_width_mm`, `bead_height_mm`, `porosity_risk`, `visual_defect_score`,
`lens_contamination_level`, `cooling_system_alarm`, and
`time_since_lens_cleaning_h`.

I group them as process, focus and geometry, thermal, optical/plume, motion,
quality, and maintenance variables. The grouping explains the simulator and
does not replace a physical sensor specification.

### 7.2 Row-level audit metadata

The PhD rows include `case_id`, `record_id`, `cycle`, `timestamp_s`,
`scenario`, `distribution`, `split`, `seed`, `provenance_source`,
`provenance_seed`, `quality_flag`, `missing_modalities`, `production_load`,
`resource_availability`, `maintenance_cost_context`, `latent_health`,
`latent_fault_severity`, `failure_hazard`, `failure_event`,
`process_instability_score`, `maintenance_urgency_score`, and
`maintenance_label`.

`latent_health`, `latent_fault_severity`, and `failure_hazard` are internal
simulator variables. `maintenance_urgency_score` is a synthetic target
defined by the latent model; I do not call it industrial ground truth.

### 7.3 Raw stream and feature vector note

In the current PhD run, [`runner.py`](src/phd_simulation/runner.py) writes the
same `base` dataframe to both `data/raw_stream.csv` and
`data/feature_vector.csv`. The columns are model-ready features plus metadata,
so the names describe the intended contract rather than two physically
separate ETL transformations. The Week 1 notebook retains the conceptual raw
stream-to-feature-vector sequence. I would describe this as an export
convention unless a separate ETL stage is implemented.

## 8. Results and artifact map

| Folder or file | What I use it for |
| --- | --- |
| [`data/raw_stream.csv`](src/results/phd_simulation/data/raw_stream.csv) | Generated trajectories and metadata. |
| [`data/feature_vector.csv`](src/results/phd_simulation/data/feature_vector.csv) | Model-ready export from the same run. |
| [`data/evaluation_with_uncertainty.csv`](src/results/phd_simulation/data/evaluation_with_uncertainty.csv) | Test and OOD rows with prediction, uncertainty, review, expert estimate, and `orchestra_urgency`. |
| [`tables/e2_*`](src/results/phd_simulation/tables/) | CV, model comparison, feature importance, and E2-related calibration inputs. |
| [`tables/e3_calibration.csv`](src/results/phd_simulation/tables/e3_calibration.csv) | MAE, conformal radius, coverage, ECE, and low/high-uncertainty comparison. |
| [`tables/e3_risk_gate_confusion_matrix.csv`](src/results/phd_simulation/tables/e3_risk_gate_confusion_matrix.csv) | Derived high-risk/no-high-risk counts at threshold 70 for test and OOD. |
| [`tables/e4_review_threshold_sweep.csv`](src/results/phd_simulation/tables/e4_review_threshold_sweep.csv) | Review rate, overrides, high-risk recall, and risky decisions by budget. |
| [`tables/e5_baseline_summary_ci95.csv`](src/results/phd_simulation/tables/e5_baseline_summary_ci95.csv) | Reward, downtime, cost, failures, unnecessary actions, and reviewed rows with seed-level mean/CI95. |
| [`tables/e6_*`](src/results/phd_simulation/tables/) | Ablation metrics and aggregation. |
| [`tables/e7_sensitivity.csv`](src/results/phd_simulation/tables/e7_sensitivity.csv) | Seed-level results for sensitivity conditions. |
| [`tables/e9_paired_statistics.csv`](src/results/phd_simulation/tables/e9_paired_statistics.csv) | Full-policy versus urgency-only differences, Wilcoxon tests, and bootstrap intervals. |
| [`logs/traces/action_trace_seed_*.csv`](src/results/phd_simulation/logs/traces/) | Per-policy traces for each evaluation seed. |
| [`logs/e8_full_orchestra_audit_trace.csv`](src/results/phd_simulation/logs/e8_full_orchestra_audit_trace.csv) | Primary hash-chain trace. |
| [`logs/e8_ppo_trained_trace.csv`](src/results/phd_simulation/logs/e8_ppo_trained_trace.csv) | PPO trace kept separate from the heuristic baseline table. |
| [`figures/`](src/results/phd_simulation/figures/) | E1–E9 figure package generated by `plot_results.py` and called automatically by the runner. |
| [`models/`](src/results/phd_simulation/models/) | Five seed-specific PPO model archives. |
| [`resolved_config.json`](src/results/phd_simulation/resolved_config.json) | Effective configuration written by the run itself. |
| [`manifest.json`](src/results/phd_simulation/manifest.json) | Run mode, validation, audit, PPO, figure status, supported claims, and output inventory. |

For every table or figure, I record the seed(s), number of cases, split, unit
of analysis, metric, interval, synthetic-data status, and interpretation
boundary in the paper or its supplementary material.

## 9. Reproduction from a clean checkout

I run these commands from the repository root.

### PhD package

```bash
python -m venv .venv-phd
source .venv-phd/bin/activate        # Fedora/Ubuntu
python -m pip install --upgrade pip
python -m pip install -r src/phd_simulation/requirements.txt
python -m pytest src/phd_simulation/test_smoke.py -q
python src/phd_simulation/run.py --quick --skip-ppo --output-dir results/phd_simulation_smoke
python src/phd_simulation/run.py
python -m src.phd_simulation.plot_results --results-dir src/results/phd_simulation
```

On Windows PowerShell I use `\.venv-phd\Scripts\Activate.ps1`. The default
full run writes to `src/results/phd_simulation` because `runner.py` resolves
the default output directory relative to the `src` package. The explicit quick
smoke command writes to the root-level `results/phd_simulation_smoke` folder.

### Legacy pipeline

```bash
python src/scripts/run_pipeline.py
python src/scripts/train_ppo.py
```

Those commands write to `src/results/tables`, `src/results/logs`,
`src/results/figures`, `src/data/processed`, and `src/models`. I keep those
outputs separate from the PhD package unless I explain the design change.

### Dashboard and MQTT

```bash
cd src/ui
npm install
npm run typecheck
npm run build
npm run dev:stack
```

The expected local settings are in [`.env.example`](src/ui/.env.example). I
review an existing `.env.local` before changing it. The gateway can use
`mqtt://127.0.0.1:1883`; the ESP32 must use the computer's IPv4 address on the
same access point.

### Firmware

```bash
cd src/firmware
pio run
pio run --target upload       # only with the board connected and lab approval
pio device monitor
```

I verified `pio run` in this checkout on 2026-09-23. On 2026-09-24 I also
verified `pio run --target upload --upload-port /dev/ttyUSB0` for the connected
ESP32-D0WD-V3 board, Wi-Fi association on the external network, MQTT telemetry
publish/subscribe, and dashboard ingestion. `USE_SIMULATED_SENSORS=true`
remains enabled, so this is an edge-transport/integration smoke test rather
than calibrated physical-sensor validation.

## 10. End-to-end demonstrator architecture

```text
ESP32-WROOM-32 or synthetic feed
        |
        | MQTT telemetry
        v
Mosquitto :1883
        |
        v
Next.js live-service.ts -- validates 17 fields --> /api/stream and /api/state
        |
        v
live_inference_service.py -- PredictiveAgent + uncertainty + HumanOperatorAgent
        |
        v
Operations dashboard / Model Observatory / operator command
        |
        | MQTT command and status
        +------------------------------------> ESP32
```

Topics in the contract:

- Telemetry: `orchestra/laser-welding/<device_id>/telemetry`
- Gateway wildcard: `orchestra/laser-welding/+/telemetry`
- Command: `orchestra/laser-welding/<device_id>/command`
- Status: `orchestra/laser-welding/<device_id>/status`

I use this vertical to demonstrate integration and operational traceability.
It does not replace E1–E9 scientific evidence and it does not provide machine
safety control.

## 11. Documentary material and classification

| Folder | Content | How I use it |
| --- | --- | --- |
| [`docs/00_Project_Management_and_Admin/`](docs/00_Project_Management_and_Admin/) | Project management and administration | Administrative context, not metrics. |
| [`docs/01_Ethics_Proposal_and_Approvals/`](docs/01_Ethics_Proposal_and_Approvals/) | Information sheets, consent, interview questions, and ethics documents | Context for future human work; not evidence that a human study was completed. |
| [`docs/02_Literature_Review_and_References/`](docs/02_Literature_Review_and_References/) | Literature and guidance | Related work and theoretical justification. |
| [`docs/03_Framework_and_Methodology/IAPM_Framework/`](docs/03_Framework_and_Methodology/IAPM_Framework/) | Agent definitions, data integration, fault detection, scheduling, monitoring, and validation | Conceptual background and earlier versions; I reconcile claims with current code. |
| [`docs/04_Data_Models_and_Analysis/Validation_Plans/`](docs/04_Data_Models_and_Analysis/Validation_Plans/) | Validation plan, operational README, and Week 1 evidence | Operational foundation for the validation. |
| [`docs/04_Data_Models_and_Analysis/Haoyuan/`](docs/04_Data_Models_and_Analysis/Haoyuan/) | Historical methods, results, and paper versions | Archive; I do not use it as the current metric source without reconciliation. |
| [`docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/00_Manuscript_Current/`](docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/00_Manuscript_Current/) | Current manuscript draft | Recommended manuscript location. |
| [`docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/01_Drafts_and_Versions/`](docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/01_Drafts_and_Versions/) | Drafts 1–5 and long-paper versions | History; I do not edit these as the primary source. |
| [`docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/02_Figures_and_Images/`](docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/02_Figures_and_Images/) | Working images and figures | I select only figures reproducible from `src/results`. |
| [`docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/03_References_and_Supporting_Material/`](docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/03_References_and_Supporting_Material/) | Paper structure, novelty notes, references, and historical code | Editorial support reconciled with E1–E9. |
| [`docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/Models/`](docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/Models/) | Earlier baseline, PPO, and sensitivity results | Not mixed with `src/phd_simulation` without explaining the design. |
| [`docs/Welding arm Models and Documents/`](<docs/Welding arm Models and Documents/>) | SIASUN manuals, binaries, installers, and robot models | Asset context, not algorithm validation. |

## 12. Verification record

| Check | Result |
| --- | --- |
| `python -m pytest src/phd_simulation/test_smoke.py -q` | **Passed: 3 tests.** |
| `python -m src.phd_simulation.run --output-dir src/results/phd_simulation` | **Passed:** full run, five seeds, PPO 5/5, E6/E7 by seed, 800/800 complete traces, valid hash chain, and 10/10 counterfactuals. |
| `python -m src.phd_simulation.plot_results --results-dir src/results/phd_simulation` | **Passed:** fourteen reproducible E1–E9 figures generated from archived CSV/JSON outputs. |
| `npm run build` in `src/ui` | **Passed:** Next.js build and generated type validation. |
| `npm run typecheck` in `src/ui` | **Passed** after the build generated `.next/types`. |
| `pio run` in `src/firmware` | **Passed** for ESP32 Dev Module, Arduino, and PubSubClient; RAM 14.1%, flash 60.1%. |
| `e5_baseline_summary_ci95.csv` | **Verified:** `ppo_trained` is included with `n_seeds=5`. |
| `e6_ablation_summary.csv` and `e7_sensitivity_summary_ci95.csv` | **Verified:** five seeds and seed-level CI95. |
| `resolved_config.json` | **Verified:** effective configuration is archived with the results. |
| `manifest.json` | **Verified:** validation, audit, PPO, figure status, supported claims, and output inventory are archived. |
| E8 traces and counterfactuals | **Verified:** trace CSVs, hash-chain report, and counterfactual CSV are present. |
| Firmware upload and physical ESP32/Mosquitto smoke | **Passed on 2026-09-24:** ESP32-D0WD-V3 upload, Wi-Fi IP `10.80.65.213`, broker `10.80.65.66:1883`, `orchestra.telemetry.v1`, `orchestra.command_ack.v1`, and Cell 01 dashboard source `mqtt`; sensor values remain firmware-simulated. |
| Dashboard capture register | **Documented:** [`dashboard_simulation_pictures/`](dashboard_simulation_pictures/) maps disconnected fallback images 01–04 and MQTT-connected images 05–10, including the focal-offset scenario. |
| Current paper draft | **Verified conversion:** four A4 pages; this is manuscript packaging context, not a new simulation result. |

## 13. Current delivery state

I consider the Weeks 1–3 simulation package documented and reproducible. The
configuration, manifest, seed-specific models, traces, tables, figures, code
map, and reproduction commands are present in the repository. I keep the
following interpretation visible when I present the work:

1. I completed the Weeks 1–3 simulation evidence with five seeds, PPO, E6, E7, audit traces, and regenerated figures.
2. I report the E3 OOD degradation instead of hiding it: in-distribution calibration is substantially stronger than OOD calibration.
3. I describe E5 as a prevention-versus-intervention trade-off, not as universal policy superiority.
4. I describe E9 as directionally informative but not statistically significant at α = 0.05.
5. I keep Week 4 paper length, advisor review, Docker/archive packaging, and final Git tagging as manuscript-release context rather than presenting them as scientific results.
6. I keep firmware upload, physical MQTT smoke testing, real sensor calibration, and operator studies separate from the simulation evidence.

## 14. Delivery readiness summary

| Area | State recorded in this repository |
| --- | --- |
| Index and repository map | Englise, and linked to current paths |
| E1–E9 evidence | Tables, figures, seeds, metrics, interpretation boundaries, and source code mapped |
| Model comparison | XGBoost, Random Forest, HistGradientBoosting, MLP, CV distributions, and feature importance documented |
| Uncertainty and confusion diagnostic | Calibration figures, OOD error analysis, and threshold-70 derived matrix documented |
| Multi-agent justification | Positive routing/audit evidence and negative OOD/significance evidence documented together |
| Effective configuration | [`resolved_config.json`](src/results/phd_simulation/resolved_config.json) archived |
| Manifest and traces | [`manifest.json`](src/results/phd_simulation/manifest.json), E8 audit trace, PPO traces, and counterfactuals archived |
| Code documentation | Core modules, dashboard, live bridge, firmware, broker, and reproduction paths mapped in English |
| Security boundary | No Wi-Fi secrets or `config.local.h` credentials belong in the paper or index |

## 15. Quick reference

- Plan: [`docs/4_Week_Validation_Plan.docx`](docs/4_Week_Validation_Plan.docx)
- Week 1 contract: [`docs/04_Data_Models_and_Analysis/Validation_Plans/W1D1/spec.md`](docs/04_Data_Models_and_Analysis/Validation_Plans/W1D1/spec.md)
- Operational guide: [`docs/04_Data_Models_and_Analysis/Validation_Plans/VALIDATION_PLAN_README.md`](docs/04_Data_Models_and_Analysis/Validation_Plans/VALIDATION_PLAN_README.md)
- Evidence code: [`src/phd_simulation/`](src/phd_simulation/)
- Code guide: [`src/phd_simulation/CODE_GUIDE.md`](src/phd_simulation/CODE_GUIDE.md)
- Base configuration: [`src/phd_simulation/default_config.json`](src/phd_simulation/default_config.json)
- Effective configuration: [`src/results/phd_simulation/resolved_config.json`](src/results/phd_simulation/resolved_config.json)
- Manifest: [`src/results/phd_simulation/manifest.json`](src/results/phd_simulation/manifest.json)
- Results: [`src/results/phd_simulation/`](src/results/phd_simulation/)
- Week 1 notebook: [`src/notebooks/01_simulation_validation_w1.ipynb`](src/notebooks/01_simulation_validation_w1.ipynb)
- Week 1 explanation: [`src/notebooks/01_simulation_validation_w1_explained.md`](src/notebooks/01_simulation_validation_w1_explained.md)
- Current paper: [`docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/00_Manuscript_Current/ORCHESTRA_Laser_Welding_Conference_Draft_05.docx`](docs/05_Publication/Conference_Paper/Conference_Paper_Workspace/00_Manuscript_Current/ORCHESTRA_Laser_Welding_Conference_Draft_05.docx)
- Dashboard: [`src/ui/`](src/ui/)
- Live model bridge: [`src/scripts/live_inference_service.py`](src/scripts/live_inference_service.py)
- Firmware: [`src/firmware/`](src/firmware/)
- Broker and platform guides: [`simulation/`](simulation/)
