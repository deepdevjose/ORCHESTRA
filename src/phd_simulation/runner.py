"""End-to-end orchestration for the reproducible E1–E9 research run."""

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
from .stats import aggregate_metrics, bootstrap_difference_ci, mean_ci, paired_test


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
    """Attach predictions, uncertainty, and full-review outputs to evaluation rows."""
    out = data.copy()
    predictions = predictor.predict(out)
    out["predicted_urgency"] = predictions
    out["uncertainty"] = predictor.uncertainty(out, predictions)
    router = HumanReviewRouter(budget=review_budget, seed=17)
    return router.apply(out, predictions, out["uncertainty"].to_numpy(), "uncertainty_triggered")


def _run_review_study(evaluation: pd.DataFrame, config: SimulationConfig, tables_dir: Path) -> pd.DataFrame:
    """Compare review modes at matched budgets and write the E4 sweep table."""
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
    """Evaluate all configured policies for one seed and persist its traces."""
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
    calibration_rows = []
    for name, subset in (("calibration", calibration), ("test", test), ("ood", data.loc[data["split"] == "ood"].copy())):
        metrics = calibration_metrics(subset, predictor)
        metrics["split"] = name
        metrics["seed"] = seed
        calibration_rows.append(metrics)
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
    return summaries_all, traces_all, evaluated, {"seed": seed, "cv": cv_df, "conformal_radius": radius, "predictor": predictor, "calibration": pd.DataFrame(calibration_rows)}


def _run_ablations(evaluated_by_seed: dict[int, pd.DataFrame], config: SimulationConfig, tables_dir: Path) -> pd.DataFrame:
    """Run E6 component ablations and write seed-level and summary tables."""
    rows: list[pd.DataFrame] = []
    for seed, evaluated in evaluated_by_seed.items():
        variants: list[tuple[str, pd.DataFrame, Any]] = [("full_orchestra", evaluated, full_orchestra_policy)]
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
        # Provenance is deliberately treated as a traceability ablation: the
        # current policy does not use it as a control feature, so a null effect
        # is an explicit result rather than evidence of causal value.
        no_provenance = evaluated.copy()
        no_provenance["provenance_source"] = "removed_in_ablation"
        no_provenance["quality_flag"] = "unknown"
        variants.append(("without_provenance", no_provenance, full_orchestra_policy))
        for name, frame, policy in variants:
            env = LaserWeldingSchedulingEnv(frame, config.reward_weights, episode_length=config.episode_length, seed=seed)
            summary, _ = evaluate_policy(env, policy, policy_name=name, episodes=min(20, len(env.case_ids)), seed=seed)
            summary["seed"] = seed
            summary["variant"] = name
            summary["provenance_available"] = int(name != "without_provenance")
            rows.append(summary)
    result = pd.concat(rows, ignore_index=True)
    result.to_csv(tables_dir / "e6_ablation_episode_metrics.csv", index=False)
    metric_columns = ["reward", "downtime", "cost", "failures", "unnecessary"]
    seed_means = result.groupby(["variant", "provenance_available", "seed"], as_index=False)[metric_columns].mean()
    aggregate = aggregate_metrics(seed_means, ["variant", "provenance_available"], metric_columns)
    aggregate["n_seeds"] = seed_means.groupby(["variant", "provenance_available"], dropna=False)["seed"].nunique().to_numpy()
    aggregate.to_csv(tables_dir / "e6_ablation_summary.csv", index=False)
    return aggregate


def _run_sensitivity(config: SimulationConfig, tables_dir: Path, seeds: tuple[int, ...]) -> pd.DataFrame:
    """Run E7 operating-condition sensitivity experiments across seeds."""
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
    for seed in seeds:
        for condition_index, (condition, change) in enumerate(conditions):
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
                seed=seed + condition_index + 1,
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
            row = {"condition": condition, "setting": ",".join(f"{key}={value}" for key, value in sorted(change.items())), **change, "seed": seed}
            for metric in ("reward", "downtime", "cost", "failures", "unnecessary"):
                row[f"mean_{metric}"] = float(summary[metric].mean())
            rows.append(row)
    result = pd.DataFrame(rows)
    result.to_csv(tables_dir / "e7_sensitivity.csv", index=False)
    metric_columns = ["mean_reward", "mean_downtime", "mean_cost", "mean_failures", "mean_unnecessary"]
    seed_means = result.groupby(["condition", "setting"], as_index=False)[metric_columns].mean()
    # CI is computed from one mean per seed and condition/setting, not from
    # individual time steps, keeping the sensitivity unit of analysis explicit.
    summary_rows: list[dict[str, object]] = []
    for keys, group in result.groupby(["condition", "setting"], dropna=False):
        condition, setting = keys
        summary_row: dict[str, object] = {"condition": condition, "setting": setting, "n_seeds": int(group["seed"].nunique())}
        for metric in metric_columns:
            mean, lower, upper = mean_ci(group.groupby("seed")[metric].mean().to_numpy(dtype=float))
            short = metric.removeprefix("mean_")
            summary_row[f"{short}_mean"] = mean
            summary_row[f"{short}_ci95_low"] = lower
            summary_row[f"{short}_ci95_high"] = upper
        summary_rows.append(summary_row)
    pd.DataFrame(summary_rows).to_csv(tables_dir / "e7_sensitivity_summary_ci95.csv", index=False)
    return result


def _make_figures(output: dict[str, Path], evaluation: pd.DataFrame, review_sweep: pd.DataFrame, baseline_summary: pd.DataFrame) -> None:
    """Write the original compact figures retained for backward compatibility."""
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
    """Run the complete simulation package and return the archived manifest."""
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
    seed_calibration_frames: list[pd.DataFrame] = []
    evaluated_by_seed: dict[int, pd.DataFrame] = {}
    for seed in config.seeds:
        summaries, traces, evaluated_seed, artifacts = _evaluate_seed(seed, config, dirs["tables"], dirs["logs"] / "traces")
        seed_summaries.append(summaries)
        seed_traces.append(traces)
        seed_calibration_frames.append(artifacts["calibration"])
        evaluated_by_seed[seed] = evaluated_seed
    evaluation_for_ablation = evaluated_by_seed[config.seeds[0]]
    calibration_all = pd.concat(seed_calibration_frames, ignore_index=True)
    calibration_all.to_csv(dirs["tables"] / "e3_calibration_all_seeds.csv", index=False)
    calibration_metric_columns = ["mae", "conformal_radius_90", "interval_coverage", "ece", "low_uncertainty_mae", "high_uncertainty_mae", "uncertainty_error_spearman"]
    calibration_summary_rows: list[dict[str, object]] = []
    for split, group in calibration_all.groupby("split"):
        summary_row: dict[str, object] = {"split": split, "n_seeds": int(group["seed"].nunique())}
        for metric in calibration_metric_columns:
            mean, lower, upper = mean_ci(group[metric].to_numpy(dtype=float))
            summary_row[f"{metric}_mean"] = mean
            summary_row[f"{metric}_ci95_low"] = lower
            summary_row[f"{metric}_ci95_high"] = upper
        calibration_summary_rows.append(summary_row)
    pd.DataFrame(calibration_summary_rows).to_csv(dirs["tables"] / "e3_calibration_summary_ci95.csv", index=False)
    episode_metrics = pd.concat(seed_summaries, ignore_index=True)
    episode_metrics.to_csv(dirs["tables"] / "e5_e9_episode_metrics_all_seeds.csv", index=False)

    _run_ablations(evaluated_by_seed, config, dirs["tables"])
    sensitivity = _run_sensitivity(config, dirs["tables"], seeds=config.seeds)

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

            ppo_summaries: list[pd.DataFrame] = []
            ppo_traces: list[pd.DataFrame] = []
            ppo_models: list[str] = []
            for seed, seed_evaluation in evaluated_by_seed.items():
                ppo_data = seed_evaluation.loc[seed_evaluation["distribution"] == "in_distribution"].copy()
                if ppo_data.empty:
                    continue
                model_path = dirs["models"] / f"ppo_scheduler_seed_{seed}.zip"
                model, _ = train_ppo(
                    ppo_data,
                    reward_weights=config.reward_weights,
                    episode_length=config.episode_length,
                    seed=seed,
                    total_timesteps=config.ppo_timesteps,
                    model_path=model_path,
                )
                ppo_summary, ppo_trace = evaluate_ppo(model, ppo_data, reward_weights=config.reward_weights, episode_length=config.episode_length, seed=seed, episodes=config.ppo_eval_episodes)
                ppo_summaries.append(ppo_summary)
                ppo_traces.append(ppo_trace)
                ppo_models.append(str(model_path))
            if ppo_summaries:
                ppo_summary_all = pd.concat(ppo_summaries, ignore_index=True)
                ppo_trace_all = hash_trace(pd.concat(ppo_traces, ignore_index=True))
                ppo_summary_all.to_csv(dirs["tables"] / "e5_ppo_trained_episode_metrics.csv", index=False)
                ppo_trace_all.to_csv(dirs["logs"] / "e8_ppo_trained_trace.csv", index=False)
                episode_metrics = pd.concat([episode_metrics, ppo_summary_all], ignore_index=True)
                ppo_status = {"enabled": True, "status": "completed", "rows": len(ppo_summary_all), "models": ppo_models}
        except Exception as exc:
            ppo_status = {"enabled": True, "status": "unavailable", "error": str(exc)}
            _write_json(dirs["logs"] / "ppo_error.json", ppo_status)

    metric_columns = ["reward", "downtime", "cost", "failures", "unnecessary", "reviewed"]
    baseline_seed_means = episode_metrics.groupby(["policy", "seed"], as_index=False)[metric_columns].mean()
    baseline_summary = aggregate_metrics(baseline_seed_means, ["policy"], metric_columns)
    baseline_summary["n_seeds"] = baseline_seed_means.groupby("policy")["seed"].nunique().reindex(baseline_summary["policy"]).to_numpy()
    baseline_summary.to_csv(dirs["tables"] / "e5_baseline_summary_ci95.csv", index=False)
    episode_metrics.to_csv(dirs["tables"] / "e5_e9_episode_metrics_all_seeds.csv", index=False)
    significance_rows = []
    for metric in ("reward", "failures", "downtime"):
        significance_rows.append({**paired_test(episode_metrics, metric, "full_orchestra", "predicted_urgency_only"), **{f"bootstrap_{key}": value for key, value in bootstrap_difference_ci(episode_metrics, metric=metric, treatment="full_orchestra", control="predicted_urgency_only", samples=config.bootstrap_samples, seed=config.seed).items()}})
    pd.DataFrame(significance_rows).to_csv(dirs["tables"] / "e9_paired_statistics.csv", index=False)

    _make_figures(dirs, evaluation, review_sweep, baseline_summary)
    figure_status: dict[str, object]
    try:
        from .plot_results import generate_figures

        generated_figures = generate_figures(dirs["root"])
        figure_status = {"status": "completed", "count": len(generated_figures), "paths": generated_figures}
    except Exception as exc:
        # The scientific tables remain usable if a local plotting backend is
        # unavailable, but the manifest must make the missing figure step
        # explicit rather than silently claiming a complete paper package.
        figure_status = {"status": "error", "error": str(exc)}
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
        "figures": figure_status,
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
