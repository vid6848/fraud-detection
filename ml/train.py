"""Phase 2 training pipeline. Run with:  python -m ml.train  [--review-cost 5] [--quick]

Steps (validation is used for every choice; the test set is scored exactly once):
 1. Time-based train / validation / test split.
 2. Grid over 4 models x 4 imbalance strategies x small hyperparameter grids,
    each fitted on train and scored by validation PR-AUC.
 3. Best config by validation PR-AUC; duplicate-removal sensitivity check.
 4. Probability calibration (TimeSeriesSplit inside train; sigmoid vs isotonic).
 5. Cost-based threshold (and 90%-precision threshold) on validation.
 6. One evaluation on test, with bootstrap confidence intervals.
 7. Global SHAP check, plots, and artifacts.
"""
import argparse
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import imblearn
import joblib
import numpy as np
import pandas as pd
import shap
import sklearn
import xgboost
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import brier_score_loss
from sklearn.model_selection import TimeSeriesSplit

from ml import config, plots
from ml.eda_utils import load_data
from ml.explain import (
    make_explainer,
    plot_shap_importance,
    plot_shap_summary,
    shap_ranking,
    shap_values,
)
from ml.features import FEATURE_COLUMNS
from ml.metrics import (
    best_cost_threshold,
    bootstrap_ci,
    cost_curve,
    evaluate,
    pr_auc,
    recall_at_precision,
    threshold_for_precision,
    threshold_metrics,
)
from ml.models import (
    GRIDS,
    MODEL_LABELS,
    MODELS,
    QUICK_GRIDS,
    STRATEGIES,
    STRATEGY_LABELS,
    build_pipeline,
    expand_grid,
)
from ml.split import split_summary, time_split


def log(msg: str = "") -> None:
    print(msg, flush=True)


def _xy(part: pd.DataFrame):
    return part[config.RAW_COLUMNS], part[config.TARGET], part[config.AMOUNT_COLUMN]


def _fmt_params(params: dict) -> str:
    return ",".join(f"{k}={v}" for k, v in params.items())


def compare_models(X_train, y_train, X_val, y_val, grids: dict) -> tuple[pd.DataFrame, dict]:
    """Fit every (model, strategy, params) on train, score on validation.

    Returns the comparison table and, per model family, the best fitted pipeline
    with its validation scores.
    """
    jobs = [
        (m, s, params)
        for m in MODELS
        if m in grids
        for s in STRATEGIES
        for params in expand_grid(grids[m])
    ]
    rows, best_per_model = [], {}
    for i, (model, strategy, params) in enumerate(jobs, 1):
        start = time.perf_counter()
        pipe = build_pipeline(model, strategy, params, y_train).fit(X_train, y_train)
        seconds = time.perf_counter() - start
        p_val = pipe.predict_proba(X_val)[:, 1]
        ap = pr_auc(y_val, p_val)
        r90 = recall_at_precision(y_val, p_val)
        rows.append(
            {
                "model": model,
                "strategy": strategy,
                "params": json.dumps(params),
                "val_pr_auc": ap,
                "val_recall_at_90_precision": r90,
                "fit_seconds": round(seconds, 2),
            }
        )
        log(
            f"[{i:>2}/{len(jobs)}] {MODEL_LABELS[model]:<19} | {strategy:<12} | "
            f"{_fmt_params(params):<30} -> val PR-AUC {ap:.3f}, recall@90%P {r90:.3f} ({seconds:.1f}s)"
        )
        if model not in best_per_model or ap > best_per_model[model]["val_pr_auc"]:
            best_per_model[model] = {
                "strategy": strategy,
                "params": params,
                "val_pr_auc": ap,
                "pipeline": pipe,
                "p_val": p_val,
            }

    table = pd.DataFrame(rows)
    combo_best = table.groupby(["model", "strategy"])["val_pr_auc"].transform("max")
    table["best_in_combo"] = table["val_pr_auc"] == combo_best
    table = table.sort_values("val_pr_auc", ascending=False).reset_index(drop=True)
    return table, best_per_model


def calibrate(model, strategy, params, X_train, y_train, X_val, y_val, folds: int) -> dict:
    """Fit sigmoid and isotonic calibration on train; keep the lower validation Brier."""
    results = {}
    for method in ("sigmoid", "isotonic"):
        start = time.perf_counter()
        cal = CalibratedClassifierCV(
            build_pipeline(model, strategy, params, y_train),
            method=method,
            cv=TimeSeriesSplit(n_splits=folds),
        ).fit(X_train, y_train)
        p_val = cal.predict_proba(X_val)[:, 1]
        results[method] = {
            "model": cal,
            "p_val": p_val,
            "val_brier": float(brier_score_loss(y_val, p_val)),
            "val_pr_auc": pr_auc(y_val, p_val),
        }
        log(
            f"  calibration {method:<8}: val Brier {results[method]['val_brier']:.6f}, "
            f"val PR-AUC {results[method]['val_pr_auc']:.3f} ({time.perf_counter() - start:.1f}s)"
        )
    best = min(results, key=lambda m: results[m]["val_brier"])
    return {"method": best, **results[best], "all": results}


def _json_default(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"not JSON serialisable: {type(obj)}")


def run(
    df: pd.DataFrame,
    grids: dict = GRIDS,
    artifacts_dir: Path = config.ARTIFACTS_DIR,
    figures_dir: Path = config.FIGURES_DIR,
    review_cost: float = config.REVIEW_COST_PER_ALERT,
    n_bootstrap: int = config.N_BOOTSTRAP,
    boundaries: tuple[float, float] = config.SPLIT_BOUNDARIES,
    calibration_folds: int = config.CALIBRATION_FOLDS,
    shap_normal_rows: int = 5000,
) -> dict:
    """Run the whole pipeline on `df` and write artifacts. Returns the metadata dict."""
    t0 = time.perf_counter()
    artifacts_dir, figures_dir = Path(artifacts_dir), Path(figures_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Split -----------------------------------------------------------------
    train, val, test = time_split(df, boundaries)
    summary = split_summary(train, val, test)
    log("== 1. Time-based split ==")
    for name, s in summary.items():
        log(f"  {name:<10} {s['rows']:>7,} rows, {s['frauds']:>3} frauds ({s['fraud_pct']:.3f}%), "
            f"Time {s['start_time']:,.0f}-{s['end_time']:,.0f}")
    X_train, y_train, _ = _xy(train)
    X_val, y_val, amt_val = _xy(val)
    X_test, y_test, amt_test = _xy(test)

    # 2. Model comparison ------------------------------------------------------
    log("\n== 2. Model x imbalance strategy comparison (fit on train, score on validation) ==")
    table, best_per_model = compare_models(X_train, y_train, X_val, y_val, grids)
    table.to_csv(artifacts_dir / "model_comparison.csv", index=False)

    best_model = max(best_per_model, key=lambda m: best_per_model[m]["val_pr_auc"])
    best = best_per_model[best_model]
    strategy, params, base_pipe = best["strategy"], best["params"], best["pipeline"]
    log(f"\n== 3. Best: {MODEL_LABELS[best_model]} + {STRATEGY_LABELS[strategy]} "
        f"({_fmt_params(params)}), val PR-AUC {best['val_pr_auc']:.3f} ==")

    # 3b. Duplicate sensitivity check (EDA finding 2) — reported only.
    dedup = train.drop_duplicates()
    Xd, yd, _ = _xy(dedup)
    dedup_pipe = build_pipeline(best_model, strategy, params, yd).fit(Xd, yd)
    dedup_ap = pr_auc(y_val, dedup_pipe.predict_proba(X_val)[:, 1])
    dedup_check = {
        "train_rows_removed": len(train) - len(dedup),
        "val_pr_auc_with_duplicates": best["val_pr_auc"],
        "val_pr_auc_without_duplicates": dedup_ap,
    }
    log(f"  duplicate check: removed {dedup_check['train_rows_removed']} train rows -> "
        f"val PR-AUC {dedup_ap:.3f} (vs {best['val_pr_auc']:.3f}); keeping duplicates")

    # 4. Calibration -----------------------------------------------------------
    log(f"\n== 4. Calibration (TimeSeriesSplit({calibration_folds}) inside train) ==")
    cal = calibrate(best_model, strategy, params, X_train, y_train, X_val, y_val, calibration_folds)
    model, p_val = cal["model"], cal["p_val"]
    p_val_base = best["p_val"]
    calibration = {
        "method": cal["method"],
        "cv": f"TimeSeriesSplit(n_splits={calibration_folds}) on train",
        "val_brier_uncalibrated": float(brier_score_loss(y_val, p_val_base)),
        "val_brier_calibrated": cal["val_brier"],
        "val_pr_auc_uncalibrated": best["val_pr_auc"],
        "val_pr_auc_calibrated": cal["val_pr_auc"],
        "candidates": {m: {"val_brier": r["val_brier"], "val_pr_auc": r["val_pr_auc"]}
                       for m, r in cal["all"].items()},
    }
    log(f"  chose {cal['method']}: Brier {calibration['val_brier_uncalibrated']:.6f} -> "
        f"{calibration['val_brier_calibrated']:.6f}")

    # 5. Thresholds on validation ------------------------------------------------
    log(f"\n== 5. Thresholds on validation (review cost ${review_cost:g}/alert) ==")
    threshold = best_cost_threshold(y_val, p_val, amt_val, review_cost)
    threshold_90p = threshold_for_precision(y_val, p_val, config.TARGET_PRECISION)
    val_metrics = evaluate(y_val, p_val, amt_val, threshold, review_cost)
    log(f"  cost-optimal threshold {threshold:.4f}: precision {val_metrics['precision']:.3f}, "
        f"recall {val_metrics['recall']:.3f}, cost saved ${val_metrics['cost_saved']:,.0f}")
    log(f"  90%-precision threshold: {threshold_90p if threshold_90p is None else round(threshold_90p, 4)}")

    # 6. Test set — exactly once ----------------------------------------------
    log("\n== 6. Test set (evaluated once) ==")
    p_test = model.predict_proba(X_test)[:, 1]
    test_metrics = evaluate(y_test, p_test, amt_test, threshold, review_cost)
    test_at_90p = (
        threshold_metrics(y_test, p_test, threshold_90p) if threshold_90p is not None else None
    )
    ci = bootstrap_ci(y_test, p_test, amt_test, threshold, review_cost, n_resamples=n_bootstrap)
    for key in ("pr_auc", "precision", "recall", "f1", "recall_at_90_precision",
                "pct_fraud_dollars_caught", "cost_saved"):
        log(f"  {key:<26} {test_metrics[key]:>10.3f}  95% CI [{ci[key]['low']:.3f}, {ci[key]['high']:.3f}]")
    log(f"  confusion matrix: {test_metrics['confusion_matrix']}")

    # 7. SHAP ------------------------------------------------------------------
    log("\n== 7. SHAP (base model, validation sample) ==")
    rng = np.random.default_rng(config.RANDOM_SEED)
    normal_idx = np.flatnonzero(y_val.to_numpy() == 0)
    fraud_idx = np.flatnonzero(y_val.to_numpy() == 1)
    pick = np.r_[fraud_idx, rng.choice(normal_idx, min(shap_normal_rows, len(normal_idx)), replace=False)]
    background = X_train.sample(min(1000, len(X_train)), random_state=config.RANDOM_SEED)
    explainer = make_explainer(base_pipe, background)
    values, Xt = shap_values(explainer, base_pipe, X_val.iloc[pick])
    ranking = shap_ranking(values, FEATURE_COLUMNS)
    top = list(ranking.index[: config.SHAP_TOP_K])
    shap_check = {
        "top_features": [{"feature": f, "mean_abs_shap": float(ranking[f])} for f in top],
        "expected": config.EXPECTED_TOP_FEATURES,
        "expected_in_top_k": {f: f in top for f in config.EXPECTED_TOP_FEATURES},
        "all_expected_in_top_k": all(f in top for f in config.EXPECTED_TOP_FEATURES),
        "k": config.SHAP_TOP_K,
    }
    log(f"  top {config.SHAP_TOP_K}: {', '.join(top)}")
    log(f"  EDA check (V17/V14/V12/V10 in top {config.SHAP_TOP_K}): "
        f"{'PASS' if shap_check['all_expected_in_top_k'] else 'MISS'} {shap_check['expected_in_top_k']}")

    # 8. Plots -----------------------------------------------------------------
    log("\n== 8. Saving figures and artifacts ==")
    val_rate = float(y_val.mean())
    plots.plot_pr_curves(
        {f"{MODEL_LABELS[m]} + {STRATEGY_LABELS[b['strategy']]}": (y_val, b["p_val"], b["val_pr_auc"])
         for m, b in best_per_model.items()},
        val_rate, "Validation PR curves (best setup per model)", figures_dir / "pr_curves_validation.png",
    )
    plots.plot_pr_curves(
        {f"{MODEL_LABELS[best_model]} (calibrated)": (y_test, p_test, test_metrics["pr_auc"])},
        float(y_test.mean()), "Test PR curve (final model, evaluated once)", figures_dir / "pr_curve_test.png",
    )
    plots.plot_confusion_matrix(
        test_metrics["confusion_matrix"],
        f"Test confusion matrix (threshold {threshold:.3f})", figures_dir / "confusion_matrix_test.png",
    )
    plots.plot_calibration(
        y_val, {"Uncalibrated": p_val_base, f"Calibrated ({cal['method']})": p_val},
        figures_dir / "calibration_curve.png",
    )
    thr_grid, costs = cost_curve(y_val, p_val, amt_val, review_cost)
    plots.plot_cost_curve(thr_grid, costs, threshold, review_cost, figures_dir / "cost_vs_threshold.png")
    plot_shap_summary(values, Xt, figures_dir / "shap_summary.png")
    plot_shap_importance(ranking, figures_dir / "shap_importance.png", config.EXPECTED_TOP_FEATURES)

    # 9. Artifacts -------------------------------------------------------------
    joblib.dump(model, artifacts_dir / "model.joblib")
    joblib.dump(base_pipe, artifacts_dir / "base_model.joblib")
    pr_points = {
        f"{m}": {
            "label": MODEL_LABELS[m],
            "strategy": b["strategy"],
            "val_pr_auc": b["val_pr_auc"],
            "points": plots.pr_curve_points(y_val, b["p_val"]),
        }
        for m, b in best_per_model.items()
    }
    (artifacts_dir / "pr_curves.json").write_text(json.dumps(pr_points, indent=1))

    metadata = {
        "model_version": config.MODEL_VERSION,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "runtime_seconds": None,  # filled in below
        "random_seed": config.RANDOM_SEED,
        "libraries": {
            "python": platform.python_version(),
            "scikit-learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "imbalanced-learn": imblearn.__version__,
            "shap": shap.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
        "input_columns": config.RAW_COLUMNS,
        "features": FEATURE_COLUMNS,
        "model": {
            "name": best_model,
            "label": MODEL_LABELS[best_model],
            "imbalance_strategy": strategy,
            "params": params,
            "selected_by": "validation PR-AUC",
        },
        "calibration": calibration,
        "threshold": threshold,
        "threshold_selection": "minimises validation cost = missed fraud $ + alerts x review cost",
        "threshold_90_precision": threshold_90p,
        "review_cost_per_alert": review_cost,
        "split": {"boundaries": list(boundaries), **summary},
        "validation_metrics": val_metrics,
        "test_metrics": {
            **test_metrics,
            "at_90_precision_threshold": test_at_90p,
            "ci95": ci,
            "n_bootstrap": n_bootstrap,
        },
        "model_comparison_best_per_model": {
            m: {"strategy": b["strategy"], "params": b["params"], "val_pr_auc": b["val_pr_auc"]}
            for m, b in best_per_model.items()
        },
        "shap": shap_check,
        "duplicate_check": dedup_check,
    }
    metadata["runtime_seconds"] = round(time.perf_counter() - t0, 1)
    (artifacts_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, default=_json_default))
    log(f"  wrote {artifacts_dir} and {figures_dir}")
    log(f"\nDone in {metadata['runtime_seconds'] / 60:.1f} min.")
    return metadata


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate the fraud model.")
    parser.add_argument("--review-cost", type=float, default=config.REVIEW_COST_PER_ALERT,
                        help="USD cost of one analyst review (default: %(default)s)")
    parser.add_argument("--quick", action="store_true", help="tiny grids for a fast smoke run")
    parser.add_argument("--n-bootstrap", type=int, default=config.N_BOOTSTRAP)
    args = parser.parse_args(argv)
    df = load_data(config.DATA_PATH)
    if args.quick:  # keep smoke-run outputs away from the real artifacts and figures
        out = config.ARTIFACTS_DIR / "quick"
        run(df, grids=QUICK_GRIDS, artifacts_dir=out, figures_dir=out,
            review_cost=args.review_cost, n_bootstrap=args.n_bootstrap)
    else:
        run(df, review_cost=args.review_cost, n_bootstrap=args.n_bootstrap)


if __name__ == "__main__":
    main()
