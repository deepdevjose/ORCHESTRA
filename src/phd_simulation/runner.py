from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .audit import audit_report, counterfactual_tests, hash_trace
from .config import SimulationConfig, write_config
from .environment import LaserWeldingSchedulingEnv, evaluate_policy
from .policies import (
    alert_only_policy,
    corrective_policy,
    full_orchestra_policy,
    periodic_policy_factory,
    predicted_urgency_policy,
    rule_based_policy,
)
from .prediction import calibration_metrics, compare_models, feature_importance, fit_xgb_with_calibration, regression_metrics
from .review import HumanReviewRouter, review_metrics
from .simulator import SimulatorOptions, generate_laser_dataset, validate_dataset
from .stats import aggregate_metrics, bootstrap_difference_ci, paired_test


def _json_default(value: object) -> object:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialise {type(value).__name__}")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default, allow_nan=False) + "\n", encoding="utf-8")


def _output_dirs(root: Path) -> dict[str, Path]:
    dirs = {
        "root": root,
        "data": root / "data",
        "models": root / "models",
        "tables": root / "tables",
        "logs": root / "logs",
        "figures": root / "figures",
    }
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return dirs


def _enrich_for_evaluation(data: pd.DataFrame, predictor, review_budget: float = 0.25) -> pd.DataFrame:
    out = data.copy()
    predictions = predictor.predict(out)
    out["predicted_urgency"] = predictions
    out["uncertainty"] = predictor.uncertainty(out, predictions)
    router = HumanReviewRouter(budget=review_budget, seed=17)
    return router.apply(out, predictions, out["uncertainty"].to_numpy(), "uncertainty_triggered")


def _run_review_study(evaluation: pd.DataFrame, config: SimulationConfig, tables_dir: Path) -> pd.DataFrame:
    predictions = evaluation["predicted_urgency"].to_numpy(dtype=float)
    uncertainties = evaluation["uncertainty"].to_numpy(dtype=float)
    rows: list[dict[str, object]] = []
    for budget in (0.10, 0.15, config.review_budget, 0.35, 0.50):
        for mode in ("random_review", "uncertainty_triggered"):
            router = HumanReviewRouter(budget=budget, seed=101 + int(budget * 1000))
            reviewed = router.apply(evaluation, predictions, uncertainties, mode)
            metrics = review_metrics(reviewed)
            rows.append({"budget": budget, "mode": mode, **metrics})
    for mode in ("no_review", "all_review"):
        router = HumanReviewRouter(budget=config.review_budget, seed=404)
        reviewed = router.apply(evaluation, predictions, uncertainties, mode)
        metrics = review_metrics(reviewed)
        rows.append({"budget": 1.0 if mode == "all_review" else 0.0, "mode": mode, **metrics})
    result = pd.DataFrame(rows)
    result.to_csv(tables_dir / "e4_review_threshold_sweep.csv", index=False)
    return result


def _evaluate_seed(seed: int, config: SimulationConfig, tables_dir: Path, traces_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    traces_dir.mkdir(parents=True, exist_ok=True)
    data = generate_laser_dataset(
        n_cases=config.n_cases,
        episode_length=config.episode_length,
        seed=seed,
        ood_fraction=config.ood_fraction,
        options=SimulatorOptions(
            sensor_noise=config.sensor_noise,
            missing_modality_rate=config.missing_modality_rate,
            concept_drift=config.concept_drift,
            resource_availability_floor=config.resource_availability_floor,
            maintenance_delay=config.maintenance_delay,
        ),
        train_fraction=config.train_case_fraction,
        calibration_fraction=config.calibration_case_fraction,
    )
    train = data.loc[data["split"] == "train"].copy()
    calibration = data.loc[data["split"] == "calibration"].copy()
    test = data.loc[data["split"] == "test"].copy()
    predictor, cv_df, radius = fit_xgb_with_calibration(train, calibration, seed=seed, folds=config.cv_folds, xgb_estimators=config.xgb_estimators)
    evaluated = _enrich_for_evaluation(test, predictor, config.review_budget)
    env = LaserWeldingSchedulingEnv(evaluated, config.reward_weights, episode_length=config.episode_length, seed=seed, maintenance_delay=config.maintenance_delay)
    policies = {
        "corrective": corrective_policy,
        "fixed_periodic": periodic_policy_factory(8),
        "alert_only": alert_only_policy,
        "rule_based": rule_based_policy,
        "predicted_urgency_only": predicted_urgency_policy,
        "full_orchestra": full_orchestra_policy,
    }
    summary_frames: list[pd.DataFrame] = []
    trace_frames: list[pd.DataFrame] = []
    episodes = min(20, len(env.case_ids))
    for name, policy in policies.items():
        summaries, traces = evaluate_policy(env, policy, policy_name=name, episodes=episodes, seed=seed)
        summaries["seed"] = seed
        summary_frames.append(summaries)
        traces["seed"] = seed
        trace_frames.append(traces)
    summaries_all = pd.concat(summary_frames, ignore_index=True)
    traces_all = pd.concat(trace_frames, ignore_index=True)
    traces_all = hash_trace(traces_all)
    summaries_all.to_csv(tables_dir / f"episode_metrics_seed_{seed}.csv", index=False)
    traces_all.to_csv(traces_dir / f"action_trace_seed_{seed}.csv", index=False)
    return summaries_all, traces_all, evaluated, {"seed": seed, "cv": cv_df, "conformal_radius": radius, "predictor": predictor}


def _run_ablations(evaluated: pd.DataFrame, config: SimulationConfig, tables_dir: Path, seed: int) -> pd.DataFrame:
    variants: list[tuple[str, pd.DataFrame, Any]] = []
    variants.append(("full_orchestra", evaluated, full_orchestra_policy))
    no_review = evaluated.copy()
    no_review["orchestra_urgency"] = no_review["predicted_urgency"]
    no_review["uncertainty"] = 0.0
    variants.append(("without_review", no_review, predicted_urgency_policy))
    variants.append(("without_ppo", evaluated, rule_based_policy))
    no_xgboost = evaluated.copy()
    no_xgboost["predicted_urgency"] = no_xgboost["process_instability_score"]
    no_xgboost["orchestra_urgency"] = no_xgboost["process_instability_score"]
    variants.append(("without_xgboost", no_xgboost, rule_based_policy))
    no_uncertainty = evaluated.copy()
    no_uncertainty["uncertainty"] = 0.0
    no_uncertainty["orchestra_urgency"] = no_uncertainty["predicted_urgency"]
    variants.append(("without_uncertainty_trigger", no_uncertainty, predicted_urgency_policy))
    no_provenance = evaluated.copy()
    no_provenance["provenance_source"] = "removed_in_ablation"
    no_provenance["quality_flag"] = "unknown"
    variants.append(("without_provenance", no_provenance, full_orchestra_policy))

    rows: list[pd.DataFrame] = []
    for name, frame, policy in variants:
        env = LaserWeldingSchedulingEnv(frame, config.reward_weights, episode_length=config.episode_length, seed=seed)
        summary, trace = evaluate_policy(env, policy, policy_name=name, episodes=min(20, len(env.case_ids)), seed=seed)
        summary["variant"] = name
        summary["provenance_available"] = int(name != "without_provenance")
        rows.append(summary)
    result = pd.concat(rows, ignore_index=True)
    result.to_csv(tables_dir / "e6_ablation_episode_metrics.csv", index=False)
    aggregate = aggregate_metrics(result, ["variant", "provenance_available"], ["reward", "downtime", "cost", "failures", "unnecessary"])
    aggregate.to_csv(tables_dir / "e6_ablation_summary.csv", index=False)
    return aggregate


def _run_sensitivity(config: SimulationConfig, tables_dir: Path, seed: int) -> pd.DataFrame:
    conditions: list[tuple[str, dict[str, object]]] = [
        ("sensor_noise", {"sensor_noise": 0.0}),
        ("sensor_noise", {"sensor_noise": 0.06}),
        ("missing_modality", {"missing_modality_rate": 0.25}),
        ("concept_drift", {"concept_drift": 0.30}),
        ("ood_shift", {"ood_fraction": 0.30}),
        ("scarce_resources", {"resource_availability_floor": 0.15}),
        ("maintenance_delay", {"maintenance_delay": 3}),
    ]
    rows: list[dict[str, object]] = []
    for condition, change in conditions:
        kwargs = {
            "sensor_noise": config.sensor_noise,
            "missing_modality_rate": config.missing_modality_rate,
            "concept_drift": config.concept_drift,
            "resource_availability_floor": config.resource_availability_floor,
            "maintenance_delay": config.maintenance_delay,
            "ood_fraction": config.ood_fraction,
        }
        kwargs.update(change)
        data = generate_laser_dataset(
            n_cases=max(60, config.n_cases // 2),
            episode_length=config.episode_length,
            seed=seed + len(rows) + 1,
            ood_fraction=float(kwargs["ood_fraction"]),
            options=SimulatorOptions(
                sensor_noise=float(kwargs["sensor_noise"]),
                missing_modality_rate=float(kwargs["missing_modality_rate"]),
                concept_drift=float(kwargs["concept_drift"]),
                resource_availability_floor=float(kwargs["resource_availability_floor"]),
                maintenance_delay=int(kwargs["maintenance_delay"]),
            ),
            train_fraction=config.train_case_fraction,
            calibration_fraction=config.calibration_case_fraction,
        )
        train = data.loc[data["split"] == "train"]
        cal = data.loc[data["split"] == "calibration"]
        test = data.loc[data["split"] == "test"]
        predictor, _, _ = fit_xgb_with_calibration(train, cal, seed=seed, folds=config.cv_folds, xgb_estimators=config.xgb_estimators)
        evaluated = _enrich_for_evaluation(test, predictor, config.review_budget)
        env = LaserWeldingSchedulingEnv(evaluated, config.reward_weights, episode_length=config.episode_length, seed=seed, maintenance_delay=int(kwargs["maintenance_delay"]))
        summary, _ = evaluate_policy(env, full_orchestra_policy, policy_name="full_orchestra", episodes=min(12, len(env.case_ids)), seed=seed)
        row = {"condition": condition, **change, "seed": seed}
        for metric in ("reward", "downtime", "cost", "failures", "unnecessary"):
            row[f"mean_{metric}"] = float(summary[metric].mean())
        rows.append(row)
    result = pd.DataFrame(rows)
    result.to_csv(tables_dir / "e7_sensitivity.csv", index=False)
    return result


def _make_figures(output: dict[str, Path], evaluation: pd.DataFrame, review_sweep: pd.DataFrame, baseline_summary: pd.DataFrame) -> None:
    try:
        import matplotlib.pyplot as plt
    except Exception:
        return
    figures = output["figures"]
    fig, ax = plt.subplots(figsize=(9, 5))
    for mode, group in review_sweep.loc[review_sweep["mode"].isin(["random_review", "uncertainty_triggered"])].groupby("mode"):
        ax.plot(group["budget"], group["high_risk_recall_after"], marker="o", label=mode)
    ax.set(xlabel="Review budget", ylabel="High-risk recall after review", title="E4 Selective review at matched budgets")
    ax.set_ylim(0, 1.05)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "e4_review_budget.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    if not baseline_summary.empty:
        plot = baseline_summary.sort_values("reward_mean")
        ax.bar(plot["policy"], plot["reward_mean"], yerr=[plot["reward_mean"] - plot["reward_ci95_low"], plot["reward_ci95_high"] - plot["reward_mean"]], capsize=4)
        ax.tick_params(axis="x", rotation=30)
    ax.set(ylabel="Mean episode reward", title="E5 Policy comparison with 95% CI")
    fig.tight_layout()
    fig.savefig(figures / "e5_policy_comparison.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    if "maintenance_urgency_score" in evaluation:
        ax.scatter(evaluation["predicted_urgency"], evaluation["maintenance_urgency_score"], c=evaluation["uncertainty"], cmap="viridis", alpha=0.55, s=16)
    ax.set(xlabel="Predicted urgency", ylabel="Simulated latent urgency", title="E2/E3 Prediction and uncertainty")
    fig.tight_layout()
    fig.savefig(figures / "e2_e3_prediction_uncertainty.png", dpi=180)
    plt.close(fig)


def run(config: SimulationConfig, *, output_dir: str | Path | None = None, quick: bool = False, skip_ppo: bool = False) -> dict[str, Any]:
    if quick:
        config = replace(config, n_cases=min(config.n_cases, 48), episode_length=min(config.episode_length, 20), seeds=tuple(config.seeds[:2]), xgb_estimators=min(config.xgb_estimators, 35), ppo_timesteps=min(config.ppo_timesteps, 1200), ppo_eval_episodes=5, bootstrap_samples=400)
    if skip_ppo:
        config = replace(config, run_ppo=False)
    project_root = Path(__file__).resolve().parents[1]
    result_root = Path(output_dir) if output_dir else project_root / config.output_dir
    dirs = _output_dirs(result_root)
    write_config(config, dirs["root"] / "resolved_config.json")

    base = generate_laser_dataset(
        n_cases=config.n_cases,
        episode_length=config.episode_length,
        seed=config.seed,
        ood_fraction=config.ood_fraction,
        options=SimulatorOptions(
            sensor_noise=config.sensor_noise,
            missing_modality_rate=config.missing_modality_rate,
            concept_drift=config.concept_drift,
            resource_availability_floor=config.resource_availability_floor,
            maintenance_delay=config.maintenance_delay,
        ),
        train_fraction=config.train_case_fraction,
        calibration_fraction=config.calibration_case_fraction,
    )
    base.to_csv(dirs["data"] / "feature_vector.csv", index=False)
    base.to_csv(dirs["data"] / "raw_stream.csv", index=False)
    validation = validate_dataset(base)
    _write_json(dirs["logs"] / "dataset_validation.json", validation)

    train = base.loc[base["split"] == "train"].copy()
    calibration = base.loc[base["split"] == "calibration"].copy()
    test = base.loc[base["split"] == "test"].copy()
    ood = base.loc[base["split"] == "ood"].copy()

    model_summary, model_folds = compare_models(train, seed=config.seed, folds=config.cv_folds, xgb_estimators=config.xgb_estimators)
    model_summary.to_csv(dirs["tables"] / "e2_model_comparison.csv", index=False)
    model_folds.to_csv(dirs["tables"] / "e2_model_cv_folds.csv", index=False)
    predictor, cv_df, radius = fit_xgb_with_calibration(train, calibration, seed=config.seed, folds=config.cv_folds, xgb_estimators=config.xgb_estimators)
    cv_df.to_csv(dirs["tables"] / "e2_xgboost_cv.csv", index=False)
    importance = feature_importance(predictor, train)
    importance.to_csv(dirs["tables"] / "e2_feature_importance.csv", index=False)

    calibration_rows = []
    for name, subset in (("calibration", calibration), ("test", test), ("ood", ood)):
        metrics = calibration_metrics(subset, predictor)
        metrics["split"] = name
        calibration_rows.append(metrics)
    calibration_table = pd.DataFrame(calibration_rows)
    calibration_table.to_csv(dirs["tables"] / "e3_calibration.csv", index=False)
    _write_json(dirs["logs"] / "e3_calibration.json", {row["split"]: {key: value for key, value in row.items() if key != "split"} for row in calibration_rows})

    evaluation = _enrich_for_evaluation(pd.concat([test, ood], ignore_index=True), predictor, config.review_budget)
    evaluation.to_csv(dirs["data"] / "evaluation_with_uncertainty.csv", index=False)
    review_sweep = _run_review_study(evaluation, config, dirs["tables"])

    seed_summaries: list[pd.DataFrame] = []
    seed_traces: list[pd.DataFrame] = []
    evaluation_for_ablation = evaluation.loc[evaluation["distribution"] == "in_distribution"].copy()
    for seed in config.seeds:
        summaries, traces, evaluated_seed, artifacts = _evaluate_seed(seed, config, dirs["tables"], dirs["logs"] / "traces")
        seed_summaries.append(summaries)
        seed_traces.append(traces)
        if seed == config.seeds[0]:
            evaluation_for_ablation = evaluated_seed
    episode_metrics = pd.concat(seed_summaries, ignore_index=True)
    episode_metrics.to_csv(dirs["tables"] / "e5_e9_episode_metrics_all_seeds.csv", index=False)
    metric_columns = ["reward", "downtime", "cost", "failures", "unnecessary", "reviewed"]
    baseline_summary = aggregate_metrics(episode_metrics, ["policy"], metric_columns)
    baseline_summary.to_csv(dirs["tables"] / "e5_baseline_summary_ci95.csv", index=False)
    significance_rows = []
    for metric in ("reward", "failures", "downtime"):
        significance_rows.append({**paired_test(episode_metrics, metric, "full_orchestra", "predicted_urgency_only"), **{f"bootstrap_{key}": value for key, value in bootstrap_difference_ci(episode_metrics, metric=metric, treatment="full_orchestra", control="predicted_urgency_only", samples=config.bootstrap_samples, seed=config.seed).items()}})
    pd.DataFrame(significance_rows).to_csv(dirs["tables"] / "e9_paired_statistics.csv", index=False)

    _run_ablations(evaluation_for_ablation, config, dirs["tables"], seed=config.seeds[0])
    sensitivity = _run_sensitivity(config, dirs["tables"], seed=config.seeds[0])

    first_trace = seed_traces[0].loc[seed_traces[0]["policy"] == "full_orchestra"].copy()
    first_trace = hash_trace(first_trace)
    first_trace.to_csv(dirs["logs"] / "e8_full_orchestra_audit_trace.csv", index=False)
    audit = audit_report(first_trace)
    counterfactual = counterfactual_tests(evaluation_for_ablation, seed=config.seed, n_tests=10)
    counterfactual.to_csv(dirs["logs"] / "e8_counterfactuals.csv", index=False)
    audit["counterfactuals_total"] = int(len(counterfactual))
    audit["counterfactuals_passed"] = int(counterfactual["passed"].sum()) if not counterfactual.empty else 0
    audit["counterfactual_pass_rate"] = float(counterfactual["passed"].mean()) if not counterfactual.empty else 0.0
    _write_json(dirs["logs"] / "e8_audit_report.json", audit)

    ppo_status: dict[str, object] = {"enabled": False, "status": "skipped"}
    if config.run_ppo:
        try:
            from .ppo import evaluate_ppo, train_ppo

            ppo_data = evaluation.loc[evaluation["distribution"] == "in_distribution"].copy()
            model, _ = train_ppo(
                ppo_data,
                reward_weights=config.reward_weights,
                episode_length=config.episode_length,
                seed=config.seeds[0],
                total_timesteps=config.ppo_timesteps,
                model_path=dirs["models"] / "ppo_scheduler.zip",
            )
            ppo_summary, ppo_trace = evaluate_ppo(model, ppo_data, reward_weights=config.reward_weights, episode_length=config.episode_length, seed=config.seeds[0], episodes=config.ppo_eval_episodes)
            ppo_summary.to_csv(dirs["tables"] / "e5_ppo_trained_episode_metrics.csv", index=False)
            hash_trace(ppo_trace).to_csv(dirs["logs"] / "e8_ppo_trained_trace.csv", index=False)
            ppo_status = {"enabled": True, "status": "completed", "rows": len(ppo_summary), "model": str(dirs["models"] / "ppo_scheduler.zip")}
        except Exception as exc:
            ppo_status = {"enabled": True, "status": "unavailable", "error": str(exc)}
            _write_json(dirs["logs"] / "ppo_error.json", ppo_status)

    _make_figures(dirs, evaluation, review_sweep, baseline_summary)
    manifest = {
        "package": "src/phd_simulation",
        "version": "1.0.0",
        "mode": "quick_smoke" if quick else "full_research_run",
        "scientific_scope": "simulation-only",
        "seed": config.seed,
        "evaluation_seeds": list(config.seeds),
        "validation": validation,
        "audit": audit,
        "ppo": ppo_status,
        "supported_claims": [
            "The seeded latent simulator generates traceable normal, degraded, and OOD trajectories.",
            "Uncertainty-triggered review can be compared with random review at a matched budget.",
            "Scheduling policies can be compared with confidence intervals, paired tests, sensitivity analysis, and reconstructable traces.",
        ],
        "must_not_claim": [
            "No real hardware or production-cell validation.",
            "No live operator study; human review is a stochastic simulated agent.",
            "No safety certification or deployment readiness.",
            "No causal claim beyond the implemented simulator assumptions.",
            "No generalisation to all laser welding processes.",
        ],
        "key_outputs": [str(path.relative_to(dirs["root"])) for path in sorted(dirs["root"].rglob("*")) if path.is_file() and path.name != "manifest.json"],
    }
    _write_json(dirs["root"] / "manifest.json", manifest)
    return manifest
