from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .schema import FEATURE_COLUMNS


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    error = y_true - y_pred
    denominator = float(np.sum((y_true - y_true.mean()) ** 2))
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error**2))),
        "r2": float(1 - np.sum(error**2) / denominator) if denominator else 0.0,
    }


def _make_model(name: str, seed: int, xgb_estimators: int = 80) -> Any:
    name = name.lower()
    if name == "xgboost":
        try:
            from xgboost import XGBRegressor

            return XGBRegressor(
                n_estimators=xgb_estimators,
                max_depth=4,
                learning_rate=0.045,
                subsample=0.9,
                colsample_bytree=0.9,
                min_child_weight=2,
                reg_lambda=1.2,
                objective="reg:squarederror",
                random_state=seed,
                n_jobs=1,
                verbosity=0,
            )
        except Exception:
            name = "hist_gradient_boosting"
    if name == "random_forest":
        from sklearn.ensemble import RandomForestRegressor

        return RandomForestRegressor(
            n_estimators=120,
            min_samples_leaf=2,
            random_state=seed,
            n_jobs=1,
        )
    if name == "mlp":
        from sklearn.neural_network import MLPRegressor

        return MLPRegressor(
            hidden_layer_sizes=(48, 24),
            alpha=0.001,
            learning_rate_init=0.003,
            max_iter=350,
            early_stopping=True,
            validation_fraction=0.15,
            random_state=seed,
        )
    if name == "lightgbm":
        try:
            from lightgbm import LGBMRegressor

            return LGBMRegressor(
                n_estimators=120,
                learning_rate=0.04,
                num_leaves=24,
                max_depth=-1,
                subsample=0.9,
                colsample_bytree=0.9,
                random_state=seed,
                n_jobs=1,
                verbosity=-1,
            )
        except Exception as exc:
            raise ImportError("lightgbm is not installed") from exc
    if name == "hist_gradient_boosting":
        from sklearn.ensemble import HistGradientBoostingRegressor

        return HistGradientBoostingRegressor(
            max_iter=120,
            learning_rate=0.05,
            max_leaf_nodes=24,
            l2_regularization=0.5,
            random_state=seed,
        )
    raise ValueError(f"Unknown predictor: {name}")


@dataclass
class FittedPredictor:
    model_name: str
    feature_columns: list[str]
    model: Any
    medians: pd.Series
    means: pd.Series
    stds: pd.Series
    ensemble_models: list[Any]
    conformal_radius: float

    def _matrix(self, frame: pd.DataFrame) -> np.ndarray:
        values = frame[self.feature_columns].copy()
        for column in self.feature_columns:
            values[column] = pd.to_numeric(values[column], errors="coerce").fillna(self.medians[column])
        return values.to_numpy(dtype=float)

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        prediction = np.asarray(self.model.predict(self._matrix(frame)), dtype=float)
        return np.clip(prediction, 0, 100)

    def ensemble_predict(self, frame: pd.DataFrame) -> np.ndarray:
        models = self.ensemble_models or [self.model]
        values = self._matrix(frame)
        predictions = [np.asarray(model.predict(values), dtype=float) for model in models]
        return np.clip(np.vstack(predictions), 0, 100)

    def uncertainty(self, frame: pd.DataFrame, predictions: np.ndarray | None = None) -> np.ndarray:
        predictions = self.predict(frame) if predictions is None else np.asarray(predictions, dtype=float)
        ensemble = self.ensemble_predict(frame)
        disagreement = np.std(ensemble, axis=0) / 14.0
        z = np.abs((frame[self.feature_columns].fillna(self.medians) - self.means) / self.stds)
        # A single modality can move far outside the training support in a
        # focus-drift event.  The max robust z-score therefore complements the
        # mean score instead of diluting that signal across 17 features.
        z_values = z.to_numpy(dtype=float)
        ood_score = np.clip(0.65 * z_values.max(axis=1) / 2.2 + 0.35 * z_values.mean(axis=1) / 2.5, 0, 1)
        distance_to_boundary = np.minimum(np.abs(predictions - 40.0), np.abs(predictions - 70.0))
        boundary_score = np.exp(-distance_to_boundary / 20.0)
        return np.clip(0.25 * disagreement + 0.60 * ood_score + 0.15 * boundary_score, 0, 1)


def _prepare_xy(frame: pd.DataFrame, feature_columns: list[str]) -> tuple[np.ndarray, np.ndarray, pd.Series, pd.Series, pd.Series]:
    x = frame[feature_columns].copy()
    for column in feature_columns:
        x[column] = pd.to_numeric(x[column], errors="coerce")
    medians = x.median().fillna(0.0)
    x = x.fillna(medians)
    means = x.mean()
    stds = x.std().replace(0, 1.0).fillna(1.0)
    y = frame["maintenance_urgency_score"].to_numpy(dtype=float)
    return x.to_numpy(dtype=float), y, medians, means, stds


def fit_predictor(
    train: pd.DataFrame,
    *,
    model_name: str = "xgboost",
    feature_columns: list[str] | None = None,
    seed: int = 42,
    xgb_estimators: int = 80,
    ensemble_frames: list[tuple[pd.DataFrame, pd.DataFrame]] | None = None,
    conformal_radius: float = 0.0,
) -> FittedPredictor:
    feature_columns = feature_columns or FEATURE_COLUMNS
    x, y, medians, means, stds = _prepare_xy(train, feature_columns)
    models: list[Any] = []
    if ensemble_frames:
        for fold_train, _ in ensemble_frames:
            fold_x, fold_y, fold_medians, _, _ = _prepare_xy(fold_train, feature_columns)
            model = _make_model(model_name, seed + len(models), xgb_estimators)
            model.fit(fold_x, fold_y)
            models.append(model)
    model = _make_model(model_name, seed, xgb_estimators)
    model.fit(x, y)
    return FittedPredictor(
        model_name=model_name,
        feature_columns=feature_columns,
        model=model,
        medians=medians,
        means=means,
        stds=stds,
        ensemble_models=models,
        conformal_radius=float(conformal_radius),
    )


def group_cross_validate(
    frame: pd.DataFrame,
    *,
    model_name: str,
    seed: int,
    folds: int = 5,
    feature_columns: list[str] | None = None,
    xgb_estimators: int = 80,
) -> tuple[pd.DataFrame, list[tuple[pd.DataFrame, pd.DataFrame]], list[Any]]:
    """Run case-grouped CV and return fold metrics, train/validation pairs and models."""

    from sklearn.model_selection import GroupKFold

    feature_columns = feature_columns or FEATURE_COLUMNS
    splitter = GroupKFold(n_splits=folds)
    groups = frame["case_id"].to_numpy()
    records: list[dict[str, float | int | str]] = []
    fold_frames: list[tuple[pd.DataFrame, pd.DataFrame]] = []
    models: list[Any] = []
    for fold, (train_idx, valid_idx) in enumerate(splitter.split(frame, frame["maintenance_urgency_score"], groups)):
        train = frame.iloc[train_idx].copy()
        valid = frame.iloc[valid_idx].copy()
        predictor = fit_predictor(train, model_name=model_name, feature_columns=feature_columns, seed=seed + fold, xgb_estimators=xgb_estimators)
        metrics = regression_metrics(valid["maintenance_urgency_score"].to_numpy(), predictor.predict(valid))
        records.append({"model": model_name, "fold": fold, **metrics})
        fold_frames.append((train, valid))
        models.append(predictor.model)
    return pd.DataFrame(records), fold_frames, models


def compare_models(
    frame: pd.DataFrame,
    *,
    seed: int = 42,
    folds: int = 5,
    xgb_estimators: int = 80,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare requested regressors and keep unavailable optional models explicit."""

    models = ["xgboost", "random_forest", "lightgbm", "mlp", "hist_gradient_boosting"]
    fold_rows: list[pd.DataFrame] = []
    summary_rows: list[dict[str, object]] = []
    for model_name in models:
        try:
            folds_df, _, _ = group_cross_validate(frame, model_name=model_name, seed=seed, folds=folds, xgb_estimators=xgb_estimators)
            fold_rows.append(folds_df)
            summary_rows.append({
                "model": model_name,
                "available": True,
                "implementation": model_name,
                "cv_mae_mean": float(folds_df["mae"].mean()),
                "cv_rmse_mean": float(folds_df["rmse"].mean()),
                "cv_r2_mean": float(folds_df["r2"].mean()),
            })
        except ImportError as exc:
            summary_rows.append({
                "model": model_name,
                "available": False,
                "implementation": "not_installed",
                "cv_mae_mean": np.nan,
                "cv_rmse_mean": np.nan,
                "cv_r2_mean": np.nan,
                "note": str(exc),
            })
    folds_result = pd.concat(fold_rows, ignore_index=True) if fold_rows else pd.DataFrame()
    return pd.DataFrame(summary_rows), folds_result


def fit_xgb_with_calibration(
    train: pd.DataFrame,
    calibration: pd.DataFrame,
    *,
    seed: int,
    folds: int,
    xgb_estimators: int,
) -> tuple[FittedPredictor, pd.DataFrame, float]:
    """Fit an ensemble on grouped training folds and a final calibrated model."""

    cv_df, fold_frames, fold_models = group_cross_validate(
        train,
        model_name="xgboost",
        seed=seed,
        folds=folds,
        xgb_estimators=xgb_estimators,
    )
    provisional = fit_predictor(
        train,
        model_name="xgboost",
        seed=seed,
        xgb_estimators=xgb_estimators,
        ensemble_frames=fold_frames,
    )
    calibration_predictions = provisional.predict(calibration)
    residuals = np.abs(calibration["maintenance_urgency_score"].to_numpy(dtype=float) - calibration_predictions)
    radius = float(np.quantile(residuals, 0.90)) if len(residuals) else 0.0
    final = fit_predictor(
        train,
        model_name="xgboost",
        seed=seed,
        xgb_estimators=xgb_estimators,
        ensemble_frames=fold_frames,
        conformal_radius=radius,
    )
    cv_df["calibration_radius"] = radius
    return final, cv_df, radius


def calibration_metrics(frame: pd.DataFrame, predictor: FittedPredictor) -> dict[str, float]:
    y = frame["maintenance_urgency_score"].to_numpy(dtype=float)
    pred = predictor.predict(frame)
    uncertainty = predictor.uncertainty(frame, pred)
    absolute_error = np.abs(y - pred)
    radius = predictor.conformal_radius
    coverage = float(np.mean((y >= pred - radius) & (y <= pred + radius))) if radius else 0.0
    order = np.argsort(uncertainty)
    cutoff = max(1, len(order) // 5)
    low_error = float(np.mean(absolute_error[order[:cutoff]]))
    high_error = float(np.mean(absolute_error[order[-cutoff:]]))
    bins = np.linspace(0, 1, 6)
    ece = 0.0
    for lower, upper in zip(bins[:-1], bins[1:]):
        mask = (uncertainty >= lower) & (uncertainty <= upper if upper == 1 else uncertainty < upper)
        if mask.any():
            expected_error = float(np.mean(absolute_error[mask]) / 100.0)
            mean_uncertainty = float(np.mean(uncertainty[mask]))
            ece += float(mask.mean()) * abs(expected_error - mean_uncertainty)
    return {
        "rows": int(len(frame)),
        "mae": float(np.mean(absolute_error)),
        "conformal_radius_90": radius,
        "interval_coverage": coverage,
        "ece": float(ece),
        "low_uncertainty_mae": low_error,
        "high_uncertainty_mae": high_error,
        "uncertainty_error_spearman": float(pd.Series(uncertainty).corr(pd.Series(absolute_error), method="spearman")),
    }


def feature_importance(predictor: FittedPredictor, frame: pd.DataFrame, max_rows: int = 512) -> pd.DataFrame:
    """Return SHAP values when available, with model gain as a transparent fallback."""

    sample = frame.sample(min(max_rows, len(frame)), random_state=7) if len(frame) else frame
    values = predictor._matrix(sample)
    try:
        import shap

        explanation = shap.TreeExplainer(predictor.model)(values)
        importance = np.abs(np.asarray(explanation.values)).mean(axis=0)
        method = "shap_mean_abs"
    except Exception:
        importance = np.asarray(getattr(predictor.model, "feature_importances_", np.zeros(len(FEATURE_COLUMNS))), dtype=float)
        method = "model_feature_importance_fallback"
    return pd.DataFrame({"feature": predictor.feature_columns, "importance": importance, "method": method}).sort_values("importance", ascending=False).reset_index(drop=True)
