"""Generate paper-ready figures from a completed ORCHESTRA PhD run.

The script deliberately reads the archived CSV/JSON outputs instead of
recomputing metrics. This keeps the figures traceable to one frozen run and
makes it possible to regenerate them without changing the experiment.

Usage from the repository root::

    python -m src.phd_simulation.plot_results \
        --results-dir src/results/phd_simulation

The confusion matrix in this module is a derived risk-gate diagnostic for the
regression target. It thresholds the simulated and predicted urgency at 70,
the same high-risk threshold used by ``review.py``; it is not presented as a
new classification experiment.
"""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


COLORS = {
    "blue": "#185ADB",
    "teal": "#0F8B8D",
    "orange": "#E76F51",
    "gold": "#E9C46A",
    "green": "#2A9D8F",
    "purple": "#7B61FF",
    "red": "#C44536",
    "ink": "#17202A",
    "muted": "#59636E",
    "grid": "#D8DEE6",
}


def _load(root: Path, relative: str) -> pd.DataFrame:
    path = root / relative
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _wrap(value: object, width: int = 18) -> str:
    return "\n".join(textwrap.wrap(str(value), width=width, break_long_words=False))


def _setup_plt():
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.edgecolor": COLORS["grid"],
            "axes.labelcolor": COLORS["ink"],
            "xtick.color": COLORS["muted"],
            "ytick.color": COLORS["muted"],
            "text.color": COLORS["ink"],
            "axes.titleweight": "bold",
            "figure.dpi": 120,
            "savefig.dpi": 240,
        }
    )
    return plt


def _save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=240, bbox_inches="tight", facecolor="white")


def _errorbar(ax, frame: pd.DataFrame, mean: str, low: str, high: str, **kwargs) -> None:
    y = frame[mean].to_numpy(float)
    lower = y - frame[low].to_numpy(float)
    upper = frame[high].to_numpy(float) - y
    ax.errorbar(
        np.arange(len(frame)),
        y,
        yerr=np.vstack([lower, upper]),
        fmt="o",
        capsize=3,
        linewidth=1.2,
        markersize=5,
        **kwargs,
    )


def _finish_axis(ax) -> None:
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.7, alpha=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def _boxplot(ax, values: list[np.ndarray], labels: list[str], **kwargs):
    """Use the current Matplotlib keyword while retaining 3.8 compatibility."""

    try:
        return ax.boxplot(values, tick_labels=labels, **kwargs)
    except TypeError:
        return ax.boxplot(values, labels=labels, **kwargs)


def plot_dataset(root: Path, figures: Path) -> list[str]:
    """Plot dataset partitions and urgency distributions for E1."""
    data = _load(root, "data/feature_vector.csv")
    if data.empty or "split" not in data:
        return []
    plt = _setup_plt()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1, 1.35]})
    counts = data["split"].value_counts().reindex(["train", "calibration", "test", "ood"]).dropna()
    axes[0].bar(counts.index, counts.values, color=[COLORS["blue"], COLORS["teal"], COLORS["green"], COLORS["orange"]])
    axes[0].set(title="E1 · Dataset partition", ylabel="Rows")
    axes[0].tick_params(axis="x", rotation=25)
    axes[0].bar_label(axes[0].containers[0], fmt="%.0f", padding=3)
    _finish_axis(axes[0])

    split_order = [split for split in ["train", "calibration", "test", "ood"] if split in set(data["split"])]
    boxes = [data.loc[data["split"] == split, "maintenance_urgency_score"].to_numpy(float) for split in split_order]
    bp = _boxplot(axes[1], boxes, split_order, patch_artist=True, showfliers=False)
    for patch, color in zip(bp["boxes"], [COLORS["blue"], COLORS["teal"], COLORS["green"], COLORS["orange"]]):
        patch.set_facecolor(color)
        patch.set_alpha(0.72)
        patch.set_linewidth(0)
    axes[1].set(title="Target distribution by split", ylabel="Maintenance urgency score (0–100)")
    _finish_axis(axes[1])
    fig.suptitle("ORCHESTRA simulated dataset and target coverage", y=1.02, fontweight="bold")
    fig.tight_layout()
    name = "e1_dataset_overview.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_model_comparison(root: Path, figures: Path) -> list[str]:
    """Plot model-level MAE, RMSE, and R-squared comparison for E2."""
    summary = _load(root, "tables/e2_model_comparison.csv")
    folds = _load(root, "tables/e2_model_cv_folds.csv")
    if summary.empty:
        return []
    available = summary.loc[summary["available"].astype(str).str.lower().eq("true")].copy()
    available = available.sort_values("cv_mae_mean")
    labels = [str(value).replace("_", " ").title() for value in available["model"]]
    x = np.arange(len(available))
    plt = _setup_plt()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))
    metrics = [("cv_mae_mean", "MAE ↓", COLORS["blue"]), ("cv_rmse_mean", "RMSE ↓", COLORS["orange"]), ("cv_r2_mean", "R² ↑", COLORS["green"])]
    for ax, (column, title, color) in zip(axes, metrics):
        std = []
        fold_column = {"cv_mae_mean": "mae", "cv_rmse_mean": "rmse", "cv_r2_mean": "r2"}[column]
        for model in available["model"]:
            values = folds.loc[folds["model"] == model, fold_column].to_numpy(float) if not folds.empty else np.array([])
            std.append(float(values.std(ddof=1)) if len(values) > 1 else 0.0)
        bars = ax.bar(x, available[column], yerr=std, capsize=3, color=color, alpha=0.85)
        ax.set_title(title)
        ax.set_xticks(x, labels, rotation=28, ha="right")
        if column == "cv_r2_mean":
            ax.set_ylim(0, 1)
        ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=8)
        _finish_axis(ax)
    fig.suptitle("E2 · Five-fold model comparison", y=1.02, fontweight="bold")
    fig.text(0.5, -0.02, "Whiskers are standard deviation across the five CV folds; lower is better for MAE/RMSE.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e2_model_comparison.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_cv_distributions(root: Path, figures: Path) -> list[str]:
    """Plot fold-level metric distributions for the available E2 models."""
    folds = _load(root, "tables/e2_model_cv_folds.csv")
    if folds.empty:
        return []
    plt = _setup_plt()
    models = list(folds["model"].drop_duplicates())
    labels = [model.replace("_", " ").title() for model in models]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6))
    for ax, metric, title in zip(axes, ["mae", "rmse", "r2"], ["MAE", "RMSE", "R²"]):
        values = [folds.loc[folds["model"] == model, metric].to_numpy(float) for model in models]
        bp = _boxplot(ax, values, labels, patch_artist=True, showmeans=True, showfliers=False)
        for patch, color in zip(bp["boxes"], [COLORS["blue"], COLORS["orange"], COLORS["purple"], COLORS["green"]]):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
            patch.set_linewidth(0)
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=28)
        _finish_axis(ax)
    fig.suptitle("E2 · Fold-level variability", y=1.02, fontweight="bold")
    fig.text(0.5, -0.02, "Each box contains the five validation folds; this visualizes stability, not independent seed replication.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e2_model_cv_distributions.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_feature_importance(root: Path, figures: Path) -> list[str]:
    """Plot the archived feature-attribution table for E2."""
    importance = _load(root, "tables/e2_feature_importance.csv")
    if importance.empty:
        return []
    importance = importance.sort_values("importance").tail(17)
    plt = _setup_plt()
    fig, ax = plt.subplots(figsize=(9, 6.6))
    ax.barh(importance["feature"], importance["importance"], color=COLORS["blue"], alpha=0.85)
    ax.set(xlabel="Mean absolute contribution", title="E2 · Feature importance for maintenance urgency")
    _finish_axis(ax)
    fig.text(0.01, -0.01, "Method archived in the table: SHAP mean absolute value when available; interpret as association within this simulator.", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e2_feature_importance.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_calibration(root: Path, figures: Path) -> list[str]:
    """Plot seed-level calibration, coverage, ECE, and rank association for E3."""
    frame = _load(root, "tables/e3_calibration_summary_ci95.csv")
    if frame.empty:
        return []
    order = [split for split in ["calibration", "test", "ood"] if split in set(frame["split"])]
    frame = frame.set_index("split").loc[order].reset_index()
    labels = [split.upper() for split in frame["split"]]
    plt = _setup_plt()
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2))
    specs = [
        ("mae", "MAE ↓", "mae_mean", "mae_ci95_low", "mae_ci95_high"),
        ("coverage", "90% interval coverage", "interval_coverage_mean", "interval_coverage_ci95_low", "interval_coverage_ci95_high"),
        ("ece", "ECE ↓", "ece_mean", "ece_ci95_low", "ece_ci95_high"),
        ("spearman", "Uncertainty–error Spearman ↑", "uncertainty_error_spearman_mean", "uncertainty_error_spearman_ci95_low", "uncertainty_error_spearman_ci95_high"),
    ]
    for ax, (_, title, mean, low, high) in zip(axes.flat, specs):
        _errorbar(ax, frame, mean, low, high, color=COLORS["blue"], ecolor=COLORS["blue"])
        ax.set_title(title)
        ax.set_xticks(np.arange(len(frame)), labels)
        if mean == "interval_coverage_mean":
            ax.axhline(0.9, color=COLORS["orange"], linestyle="--", linewidth=1, label="Nominal 90%")
            ax.set_ylim(0, 1.05)
        if mean == "ece_mean":
            ax.set_ylim(bottom=0)
        _finish_axis(ax)
    fig.suptitle("E3 · Calibration and uncertainty quality across splits", y=1.01, fontweight="bold")
    fig.text(0.5, -0.01, "Points and whiskers are means and 95% CI over five evaluation seeds; OOD is intentionally shown as a limitation.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e3_calibration_summary.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_uncertainty_error(root: Path, figures: Path) -> list[str]:
    """Plot uncertainty against absolute urgency error for test and OOD rows."""
    frame = _load(root, "data/evaluation_with_uncertainty.csv")
    if frame.empty or not {"uncertainty", "predicted_urgency", "maintenance_urgency_score", "split"}.issubset(frame.columns):
        return []
    frame = frame.copy()
    frame["absolute_error"] = (frame["predicted_urgency"] - frame["maintenance_urgency_score"]).abs()
    plt = _setup_plt()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    colors = {"test": COLORS["green"], "ood": COLORS["orange"]}
    for ax, split in zip(axes, ["test", "ood"]):
        subset = frame.loc[frame["split"] == split]
        ax.scatter(subset["uncertainty"], subset["absolute_error"], s=12, alpha=0.18, color=colors[split], edgecolors="none")
        if not subset.empty:
            bins = pd.qcut(subset["uncertainty"], q=min(10, subset["uncertainty"].nunique()), duplicates="drop")
            grouped = subset.assign(bin=bins).groupby("bin", observed=True).agg(uncertainty=("uncertainty", "mean"), absolute_error=("absolute_error", "mean"))
            ax.plot(grouped["uncertainty"], grouped["absolute_error"], marker="o", color=COLORS["ink"], linewidth=1.6, label="Binned mean")
        ax.set_title(split.upper())
        ax.set_xlabel("Predictive uncertainty")
        ax.legend(frameon=False, fontsize=8)
        _finish_axis(ax)
    axes[0].set_ylabel("Absolute urgency error")
    fig.suptitle("E3 · Does uncertainty track prediction error?", y=1.02, fontweight="bold")
    fig.text(0.5, -0.02, "The OOD panel is diagnostic evidence only; its weak/negative association is a limitation, not a success claim.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e3_uncertainty_error.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_risk_gate_confusion(root: Path, figures: Path) -> list[str]:
    """Plot and archive the threshold-70 regression risk-gate diagnostic."""
    frame = _load(root, "data/evaluation_with_uncertainty.csv")
    if frame.empty or not {"maintenance_urgency_score", "predicted_urgency", "split"}.issubset(frame.columns):
        return []
    threshold = 70.0
    records: list[dict[str, object]] = []
    matrices: list[tuple[str, np.ndarray]] = []
    for split in ["test", "ood"]:
        subset = frame.loc[frame["split"] == split]
        actual = subset["maintenance_urgency_score"].to_numpy(float) >= threshold
        predicted = subset["predicted_urgency"].to_numpy(float) >= threshold
        matrix = np.array([[np.sum(~actual & ~predicted), np.sum(~actual & predicted)], [np.sum(actual & ~predicted), np.sum(actual & predicted)]], dtype=int)
        matrices.append((split, matrix))
        for actual_class, row in enumerate(matrix):
            for predicted_class, count in enumerate(row):
                records.append({"split": split, "actual_high_risk": actual_class, "predicted_high_risk": predicted_class, "count": int(count), "threshold": threshold})
    pd.DataFrame(records).to_csv(root / "tables/e3_risk_gate_confusion_matrix.csv", index=False)
    plt = _setup_plt()
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.1))
    vmax = max(int(matrix.max()) for _, matrix in matrices) if matrices else 1
    for ax, (split, matrix) in zip(axes, matrices):
        image = ax.imshow(matrix, cmap="Blues", vmin=0, vmax=vmax)
        for i in range(2):
            for j in range(2):
                color = "white" if matrix[i, j] > vmax * 0.55 else COLORS["ink"]
                ax.text(j, i, f"{matrix[i, j]:,}", ha="center", va="center", color=color, fontweight="bold")
        ax.set(title=split.upper(), xlabel="Predicted high risk", ylabel="Actual high risk", xticks=[0, 1], yticks=[0, 1], xticklabels=["No", "Yes"], yticklabels=["No", "Yes"])
    fig.colorbar(image, ax=axes.ravel().tolist(), shrink=0.8, label="Rows")
    fig.suptitle("Derived risk-gate confusion matrix (threshold = 70)", y=1.02, fontweight="bold")
    fig.text(0.5, -0.02, "This is a thresholded diagnostic of the regression model, aligned with the review high-risk definition; it is not a separate classifier.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.subplots_adjust(left=0.08, right=0.93, bottom=0.25, top=0.79, wspace=0.34)
    name = "e3_risk_gate_confusion_matrix.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_review(root: Path, figures: Path) -> list[str]:
    """Plot matched-budget review recall, risky decisions, and overrides for E4."""
    frame = _load(root, "tables/e4_review_threshold_sweep.csv")
    if frame.empty:
        return []
    plt = _setup_plt()
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4))
    colors = {"random_review": COLORS["orange"], "uncertainty_triggered": COLORS["blue"], "no_review": COLORS["muted"], "all_review": COLORS["green"]}
    labels = {key: key.replace("_", " ").title() for key in colors}
    for mode, group in frame.groupby("mode"):
        group = group.sort_values("budget")
        color = colors.get(mode, COLORS["purple"])
        label = labels.get(mode, mode)
        axes[0].plot(group["budget"], group["high_risk_recall_after"], marker="o", label=label, color=color)
        axes[1].plot(group["budget"], group["risky_decisions"], marker="o", label=label, color=color)
        axes[2].plot(group["budget"], group["override_rate"], marker="o", label=label, color=color)
    axes[0].set(title="High-risk recall ↑", ylabel="Recall", ylim=(0, 1.05))
    axes[1].set(title="Risky decisions ↓", ylabel="Count")
    axes[2].set(title="Override rate", ylabel="Rate", ylim=(0, 0.38))
    for ax in axes:
        ax.set_xlabel("Review budget")
        _finish_axis(ax)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("E4 · Review routing at matched budgets", y=1.02, fontweight="bold")
    fig.text(0.5, -0.02, "Uncertainty-triggered review is compared with random review, no review, and all review on the same simulated rows.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e4_review_tradeoffs.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


POLICY_LABELS = {
    "alert_only": "Alert only",
    "corrective": "Corrective",
    "fixed_periodic": "Fixed periodic",
    "full_orchestra": "Full ORCHESTRA",
    "ppo_trained": "PPO trained",
    "predicted_urgency_only": "Urgency only",
    "rule_based": "Rule based",
}


def plot_policies(root: Path, figures: Path) -> list[str]:
    """Plot E5 policy metrics and the reward–downtime trade-off."""
    frame = _load(root, "tables/e5_baseline_summary_ci95.csv")
    if frame.empty:
        return []
    order = [policy for policy in ["alert_only", "corrective", "fixed_periodic", "full_orchestra", "ppo_trained", "predicted_urgency_only", "rule_based"] if policy in set(frame["policy"])]
    frame = frame.set_index("policy").loc[order].reset_index()
    labels = [POLICY_LABELS.get(policy, policy) for policy in frame["policy"]]
    x = np.arange(len(frame))
    plt = _setup_plt()
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.2))
    specs = [("reward", "Reward ↑", COLORS["blue"]), ("downtime", "Downtime ↓", COLORS["orange"]), ("cost", "Cost ↓", COLORS["purple"]), ("failures", "Failures ↓", COLORS["red"]), ("unnecessary", "Unnecessary actions ↓", COLORS["gold"]), ("reviewed", "Reviewed rows", COLORS["teal"])]
    for ax, (metric, title, color) in zip(axes.flat, specs):
        mean, low, high = f"{metric}_mean", f"{metric}_ci95_low", f"{metric}_ci95_high"
        y = frame[mean].to_numpy(float)
        yerr = np.vstack([y - frame[low].to_numpy(float), frame[high].to_numpy(float) - y])
        bars = ax.bar(x, y, yerr=yerr, capsize=3, color=color, alpha=0.82)
        ax.set_title(title)
        ax.set_xticks(x, labels, rotation=35, ha="right")
        ax.bar_label(bars, fmt="%.1f", padding=2, fontsize=7)
        _finish_axis(ax)
    fig.suptitle("E5 · Multi-agent policy compared with baselines", y=1.01, fontweight="bold")
    fig.text(0.5, -0.01, "Bars are five-seed means with 95% CI over seed means; reward is simulator-specific and should not be read as a physical unit.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e5_policy_metrics.png"
    _save(fig, figures / name)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.4, 5.1))
    for _, row in frame.iterrows():
        label = POLICY_LABELS.get(row["policy"], row["policy"])
        ax.scatter(row["downtime_mean"], row["reward_mean"], s=max(35, row["cost_mean"] * 15), alpha=0.82, label=label)
        ax.annotate(label, (row["downtime_mean"], row["reward_mean"]), xytext=(5, 4), textcoords="offset points", fontsize=8)
    ax.set(xlabel="Mean downtime ↓", ylabel="Mean episode reward ↑", title="E5 · Reward–downtime policy trade-off")
    _finish_axis(ax)
    fig.text(0.5, -0.01, "Marker area is proportional to mean cost; this is a compact decision trade-off, not a Pareto proof.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name2 = "e5_policy_tradeoff.png"
    _save(fig, figures / name2)
    plt.close(fig)
    return [name, name2]


def plot_ablations(root: Path, figures: Path) -> list[str]:
    """Plot E6 component-ablation metrics with seed-level confidence intervals."""
    frame = _load(root, "tables/e6_ablation_summary.csv")
    if frame.empty:
        return []
    frame = frame.sort_values("variant")
    labels = [str(value).replace("without_", "−").replace("full_orchestra", "Full ORCHESTRA").replace("_", " ") for value in frame["variant"]]
    x = np.arange(len(frame))
    plt = _setup_plt()
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.2))
    specs = [("reward", "Reward ↑", COLORS["blue"]), ("downtime", "Downtime ↓", COLORS["orange"]), ("cost", "Cost ↓", COLORS["purple"]), ("failures", "Failures ↓", COLORS["red"]), ("unnecessary", "Unnecessary actions ↓", COLORS["gold"])]
    for ax, (metric, title, color) in zip(axes.flat, specs):
        y = frame[f"{metric}_mean"].to_numpy(float)
        yerr = np.vstack([y - frame[f"{metric}_ci95_low"].to_numpy(float), frame[f"{metric}_ci95_high"].to_numpy(float) - y])
        ax.bar(x, y, yerr=yerr, capsize=3, color=color, alpha=0.82)
        ax.set(title=title, xticks=x, xticklabels=labels)
        ax.tick_params(axis="x", rotation=35)
        _finish_axis(ax)
    axes[1, 2].axis("off")
    fig.suptitle("E6 · Ablation evidence", y=1.01, fontweight="bold")
    fig.text(0.5, -0.01, "Ablations identify operational contributions inside the implemented simulator; equal provenance results are traceability evidence, not causal evidence.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e6_ablation_metrics.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_sensitivity(root: Path, figures: Path) -> list[str]:
    """Plot E7 sensitivity means and confidence intervals by condition."""
    frame = _load(root, "tables/e7_sensitivity_summary_ci95.csv")
    if frame.empty:
        return []
    frame = frame.copy()
    frame["label"] = [f"{condition}\n{setting.split('=', 1)[-1]}" for condition, setting in zip(frame["condition"], frame["setting"])]
    x = np.arange(len(frame))
    plt = _setup_plt()
    fig, axes = plt.subplots(2, 2, figsize=(13, 7.4))
    specs = [("reward", "Reward ↑", COLORS["blue"]), ("downtime", "Downtime ↓", COLORS["orange"]), ("cost", "Cost ↓", COLORS["purple"]), ("unnecessary", "Unnecessary actions ↓", COLORS["gold"])]
    for ax, (metric, title, color) in zip(axes.flat, specs):
        y = frame[f"{metric}_mean"].to_numpy(float)
        yerr = np.vstack([y - frame[f"{metric}_ci95_low"].to_numpy(float), frame[f"{metric}_ci95_high"].to_numpy(float) - y])
        ax.errorbar(x, y, yerr=yerr, fmt="o", color=color, ecolor=color, capsize=3, linewidth=1.3)
        ax.axhline(0, color=COLORS["grid"], linewidth=0.8)
        ax.set(title=title, xticks=x, xticklabels=frame["label"])
        ax.tick_params(axis="x", rotation=45)
        _finish_axis(ax)
    fig.suptitle("E7 · Sensitivity to simulated operating conditions", y=1.01, fontweight="bold")
    fig.text(0.5, -0.02, "Each point is a five-seed mean with 95% CI. Conditions are stress tests of the simulator, not industrial robustness guarantees.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e7_sensitivity_metrics.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_audit(root: Path, figures: Path) -> list[str]:
    """Plot E8 completeness, hash-chain, and counterfactual pass rates."""
    report_path = root / "logs/e8_audit_report.json"
    if not report_path.exists():
        return []
    report = json.loads(report_path.read_text(encoding="utf-8"))
    values = [float(report.get("completeness_rate", 0)), float(report.get("hash_chain_valid", False)), float(report.get("counterfactual_pass_rate", 0))]
    labels = ["Complete rows", "Hash chain", "Counterfactuals"]
    plt = _setup_plt()
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    bars = ax.bar(labels, values, color=[COLORS["blue"], COLORS["teal"], COLORS["green"]], alpha=0.85)
    ax.set_ylim(0, 1.08)
    ax.set_ylabel("Rate")
    ax.set_title("E8 · Audit and counterfactual integrity")
    ax.bar_label(bars, labels=[f"{value:.0%}" for value in values], padding=3)
    _finish_axis(ax)
    fig.text(0.5, -0.01, f"Archived counts: {report.get('complete_rows', 0)}/{report.get('rows', 0)} complete and {report.get('counterfactuals_passed', 0)}/{report.get('counterfactuals_total', 0)} counterfactuals passed.", ha="center", color=COLORS["muted"], fontsize=9)
    fig.tight_layout()
    name = "e8_audit_quality.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def plot_statistics(root: Path, figures: Path) -> list[str]:
    """Plot E9 paired treatment-control differences and bootstrap intervals."""
    frame = _load(root, "tables/e9_paired_statistics.csv")
    if frame.empty:
        return []
    frame = frame.sort_values("metric")
    labels = [str(value).title() for value in frame["metric"]]
    y = np.arange(len(frame))
    plt = _setup_plt()
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    low = frame["bootstrap_ci95_low"].to_numpy(float)
    high = frame["bootstrap_ci95_high"].to_numpy(float)
    mean = frame["difference_mean"].to_numpy(float)
    ax.errorbar(mean, y, xerr=np.vstack([mean - low, high - mean]), fmt="o", color=COLORS["blue"], ecolor=COLORS["blue"], capsize=4, linewidth=1.4)
    ax.axvline(0, color=COLORS["ink"], linewidth=1)
    ax.set(yticks=y, yticklabels=labels, xlabel="Full ORCHESTRA − urgency-only difference", title="E9 · Paired effects with bootstrap 95% CI")
    ax.text(0.99, 0.03, "p = 0.0625 for each reported metric", transform=ax.transAxes, ha="right", color=COLORS["muted"], fontsize=9)
    _finish_axis(ax)
    fig.tight_layout()
    name = "e9_paired_effects.png"
    _save(fig, figures / name)
    plt.close(fig)
    return [name]


def generate_figures(results_dir: str | Path) -> list[str]:
    """Generate all available paper figures and return relative paths."""

    root = Path(results_dir)
    figures = root / "figures"
    generated: list[str] = []
    generators = [
        plot_dataset,
        plot_model_comparison,
        plot_cv_distributions,
        plot_feature_importance,
        plot_calibration,
        plot_uncertainty_error,
        plot_risk_gate_confusion,
        plot_review,
        plot_policies,
        plot_ablations,
        plot_sensitivity,
        plot_audit,
        plot_statistics,
    ]
    for generator in generators:
        generated.extend(generator(root, figures))
    return generated


def main() -> None:
    """Parse the result directory, generate figures, and print JSON metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="src/results/phd_simulation", type=Path)
    args = parser.parse_args()
    generated = generate_figures(args.results_dir)
    print(json.dumps({"status": "completed", "figures": generated}, indent=2))


if __name__ == "__main__":
    main()
