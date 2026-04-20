"""
common.py
---------
Shared logic for stage check scripts (Stages 1–7).

Pipeline step mapping:
    Stage 1  → step_2_airfoil_selection()            → Stage1Result
    Stage 2  → step_3_xfoil_simulations(s1)          → Stage2Result
    Stage 3  → step_4_compressibility_correction(s2) → Stage3Result
    Stage 4  → step_5_metrics_and_figures(s3)        → Stage4Result
    Stage 5  → step_6_pitch_kinematics()             → Stage5Result
    Stage 6  → step_7_reverse_thrust()               → Stage6Result
    Stage 7  → step_8_sfc_analysis()                 → Stage7Result
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import run_analysis
from vfp_analysis import config as base_config
from vfp_analysis.pipeline.contracts import (
    Stage1Result,
    Stage2Result,
    Stage3Result,
    Stage4Result,
    Stage5Result,
    Stage6Result,
    Stage7Result,
)


def _existing_count(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

def _validate_stage_outputs(stage_num: int) -> list[str]:
    """Return a list of [OK]/[MISSING]/[INFO] lines for the target stage."""
    stage_dir = base_config.get_stage_dir(stage_num)
    checks: list[tuple[Path, str]] = []

    if stage_num == 1:
        checks = [
            (stage_dir / "airfoil_selection" / "selected_airfoil.dat", "selected airfoil (.dat)"),
        ]
    elif stage_num == 2:
        checks = [
            (stage_dir / "simulation_plots", "simulation_plots directory"),
            (stage_dir / "polars",           "flat polars directory"),
        ]
    elif stage_num == 3:
        checks = [
            (stage_dir, "corrections output directory"),
        ]
    elif stage_num == 4:
        checks = [
            (stage_dir / "tables" / "summary_table.csv",      "metrics table"),
            (stage_dir / "tables" / "clcd_max_by_section.csv","CL/CD by section table"),
            (stage_dir / "figures",                            "figures directory"),
        ]
    elif stage_num == 5:
        checks = [
            (stage_dir / "tables" / "optimal_incidence.csv",        "optimal incidence table"),
            (stage_dir / "tables" / "stage_loading.csv",            "stage loading table"),
            (stage_dir / "tables" / "blade_twist_design.csv",       "blade twist design table"),
            (stage_dir / "tables" / "off_design_incidence.csv",     "off-design incidence table"),
            (stage_dir / "tables" / "cascade_corrections.csv",      "cascade corrections table"),
            (stage_dir / "tables" / "rotational_corrections.csv",   "rotational corrections table"),
            (stage_dir / "figures",                                  "figures directory"),
        ]
    elif stage_num == 6:
        checks = [
            (stage_dir / "tables" / "reverse_kinematics.csv",    "reverse kinematics table"),
            (stage_dir / "tables" / "reverse_thrust_sweep.csv",  "reverse thrust sweep table"),
            (stage_dir / "tables" / "reverse_thrust_optimal.csv","reverse thrust optimal point table"),
            (stage_dir / "tables" / "mechanism_weight.csv",      "mechanism weight table"),
            (stage_dir / "figures",                               "figures directory"),
        ]
    elif stage_num == 7:
        checks = [
            (stage_dir / "tables" / "sfc_analysis.csv",          "aggregated SFC table"),
            (stage_dir / "tables" / "sfc_section_breakdown.csv", "SFC by section table"),
            (stage_dir / "tables" / "sfc_sensitivity.csv",       "tau sensitivity table"),
            (stage_dir / "figures",                               "figures directory"),
        ]

    messages: list[str] = []
    for path, label in checks:
        status = "OK" if path.exists() else "MISSING"
        messages.append(f"[{status}] {label}: {path}")

    # Count artifacts
    if stage_num == 2:
        polars_dir = stage_dir / "polars"
        messages.append(f"[INFO] Flat polars (csv): {_existing_count(polars_dir, '*.csv')}")
    elif stage_num == 3:
        corrected = _existing_count(stage_dir, "*/*/corrected_polar.csv")
        messages.append(f"[INFO] Corrected polars: {corrected}")
    elif stage_num == 4:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Stage 4 figures: {_existing_count(figures_dir, '*.png')}")
    elif stage_num == 5:
        figures_dir = stage_dir / "figures"
        tables_dir = stage_dir / "tables"
        messages.append(f"[INFO] Stage 5 figures: {_existing_count(figures_dir, '*.png')}")
        messages.append(f"[INFO] Stage 5 tables:  {_existing_count(tables_dir, '*.csv')}")
    elif stage_num == 6:
        figures_dir = stage_dir / "figures"
        tables_dir = stage_dir / "tables"
        messages.append(f"[INFO] Stage 6 figures: {_existing_count(figures_dir, '*.png')}")
        messages.append(f"[INFO] Stage 6 tables:  {_existing_count(tables_dir, '*.csv')}")
    elif stage_num == 7:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Stage 7 figures: {_existing_count(figures_dir, '*.png')}")

    return messages


# ---------------------------------------------------------------------------
# Cache helpers (reconstruct result objects from disk without re-running)
# ---------------------------------------------------------------------------

def _cached_s1() -> Stage1Result | None:
    stage_dir = base_config.get_stage_dir(1)
    dat = stage_dir / "airfoil_selection" / "selected_airfoil.dat"
    if not dat.is_file():
        return None
    try:
        name = dat.read_text().splitlines()[0].strip()
    except Exception:
        name = dat.stem
    return Stage1Result(
        selected_airfoil_name=name,
        selected_airfoil_dat=dat,
        stage_dir=stage_dir,
        selection_dir=stage_dir / "airfoil_selection",
    )


def _cached_s2() -> Stage2Result | None:
    stage_dir = base_config.get_stage_dir(2)
    polars_dir = stage_dir / "polars"
    if not polars_dir.exists() or not any(polars_dir.glob("*.csv")):
        return None
    return Stage2Result(
        source_polars=stage_dir / "simulation_plots",
        alpha_eff_map={},
        stall_map={},
        n_simulations=_existing_count(polars_dir, "*.csv"),
        n_convergence_warnings=0,
        stage_dir=stage_dir,
    )


def _cached_s3() -> Stage3Result | None:
    stage_dir = base_config.get_stage_dir(3)
    n = _existing_count(stage_dir, "*/*/corrected_polar.csv")
    if n == 0:
        return None
    return Stage3Result(
        corrected_dir=stage_dir,
        n_cases_corrected=n,
        n_cases_failed=0,
        stage_dir=stage_dir,
    )


def _cached_s4() -> Stage4Result | None:
    stage_dir = base_config.get_stage_dir(4)
    if not (stage_dir / "tables" / "summary_table.csv").is_file():
        return None
    return Stage4Result(
        metrics=[],
        tables_dir=stage_dir / "tables",
        figures_dir=stage_dir / "figures",
        stage_dir=stage_dir,
    )


def _cached_s5() -> Stage5Result | None:
    stage_dir = base_config.get_stage_dir(5)
    tables_dir = stage_dir / "tables"
    if not (tables_dir / "optimal_incidence.csv").is_file():
        return None
    n_tables = _existing_count(tables_dir, "*.csv")
    n_figures = _existing_count(stage_dir / "figures", "*.png")
    return Stage5Result(
        tables_dir=tables_dir,
        figures_dir=stage_dir / "figures",
        n_tables=n_tables,
        n_figures=n_figures,
        twist_total_deg=float("nan"),
        max_off_design_loss_pct=float("nan"),
        stage_dir=stage_dir,
    )


def _cached_s6() -> Stage6Result | None:
    stage_dir = base_config.get_stage_dir(6)
    tables_dir = stage_dir / "tables"
    optimal_path = tables_dir / "reverse_thrust_optimal.csv"
    mw_path = tables_dir / "mechanism_weight.csv"
    if not optimal_path.is_file() or not mw_path.is_file():
        return None
    try:
        import pandas as pd
        idx_opt = pd.read_csv(optimal_path).set_index("metric")["value"]
        idx_mw = pd.read_csv(mw_path).set_index("metric")["value"]
        beta_opt = float(idx_opt.get("beta_opt_mid_deg", float("nan")))
        thrust_fraction = float(idx_opt.get("thrust_fraction_pct", float("nan"))) / 100.0
        mechanism_weight_kg = float(idx_mw.get("mechanism_weight_kg", float("nan")))
        sfc_penalty = float(idx_mw.get("sfc_cruise_penalty_pct", float("nan")))
    except Exception:
        beta_opt = float("nan")
        thrust_fraction = float("nan")
        mechanism_weight_kg = float("nan")
        sfc_penalty = float("nan")
    n_tables = _existing_count(tables_dir, "*.csv")
    n_figures = _existing_count(stage_dir / "figures", "*.png")
    return Stage6Result(
        tables_dir=tables_dir,
        figures_dir=stage_dir / "figures",
        n_tables=n_tables,
        n_figures=n_figures,
        beta_opt_deg=beta_opt,
        thrust_fraction=thrust_fraction,
        mechanism_weight_kg=mechanism_weight_kg,
        sfc_cruise_penalty_pct=sfc_penalty,
        stage_dir=stage_dir,
    )


def _cached_s7() -> Stage7Result | None:
    stage_dir = base_config.get_stage_dir(7)
    sfc_file = stage_dir / "tables" / "sfc_analysis.csv"
    if not sfc_file.is_file():
        return None
    try:
        import pandas as pd
        df = pd.read_csv(sfc_file)
        col = next((c for c in df.columns if "sfc_reduction" in c.lower()), None)
        mean_red = float(df[col].mean(skipna=True)) if col else float("nan")
    except Exception:
        mean_red = float("nan")
    return Stage7Result(
        tables_dir=stage_dir / "tables",
        figures_dir=stage_dir / "figures",
        mean_sfc_reduction_pct=mean_red,
        stage_dir=stage_dir,
    )


# ---------------------------------------------------------------------------
# Main check runner
# ---------------------------------------------------------------------------

def run_stage_check(stage_num: int, clean: bool = True, cache: bool = False) -> None:
    """Run the pipeline up to *stage_num* and validate its outputs.

    Parameters
    ----------
    stage_num : int   Target stage (1–7).
    clean : bool      Wipe previous results before running (ignored in cache mode).
    cache : bool      Skip re-running stages whose artifacts already exist on disk.
    """
    if stage_num < 1 or stage_num > 7:
        raise ValueError("stage_num must be between 1 and 7")

    if cache:
        clean = False

    print("=" * 80)
    print(f"Stage check: Stage {stage_num}"
          + ("  [cache — skipping completed stages]" if cache else ""))
    print("=" * 80)

    if clean:
        print("[RUN] Cleaning previous results")
        run_analysis.step_1_clean_results()

    s1: Stage1Result | None = None
    s2: Stage2Result | None = None
    s3: Stage3Result | None = None
    s4: Stage4Result | None = None
    s5: Stage5Result | None = None

    # ── Stage 1 — airfoil selection ──────────────────────────────────────────
    if stage_num >= 1:
        if cache and (r := _cached_s1()) is not None:
            s1 = r
            print(f"[CACHE] Stage 1 — airfoil: {s1.selected_airfoil_name}")
        else:
            print("[RUN] Stage 1 — airfoil selection")
            s1 = run_analysis.step_2_airfoil_selection()
            print(f"[INFO] Selected airfoil: {s1.selected_airfoil_name}")

    # ── Stage 2 — XFOIL simulations ─────────────────────────────────────────
    if stage_num >= 2:
        if cache and (r := _cached_s2()) is not None:
            s2 = r
            print(f"[CACHE] Stage 2 — {s2.n_simulations} polars on disk")
        else:
            print("[RUN] Stage 2 — XFOIL simulations")
            s2 = run_analysis.step_3_xfoil_simulations(s1)
            print(f"[INFO] Simulations: {s2.n_simulations}")

    # ── Stage 3 — compressibility corrections ───────────────────────────────
    if stage_num >= 3:
        if cache and (r := _cached_s3()) is not None:
            s3 = r
            print(f"[CACHE] Stage 3 — {s3.n_cases_corrected} corrected polars on disk")
        else:
            print("[RUN] Stage 3 — compressibility corrections")
            s3 = run_analysis.step_4_compressibility_correction(s2)
            print(f"[INFO] Corrected cases: {s3.n_cases_corrected}")

    # ── Stage 4 — aerodynamic metrics and figures ────────────────────────────
    if stage_num >= 4:
        if cache and (r := _cached_s4()) is not None:
            s4 = r
            print("[CACHE] Stage 4 — metrics on disk")
        else:
            print("[RUN] Stage 4 — aerodynamic metrics and figures")
            s4 = run_analysis.step_5_metrics_and_figures(s3)
            print(f"[INFO] Metrics computed: {len(s4.metrics)}")

    # ── Stage 5 — pitch kinematics ───────────────────────────────────────────
    if stage_num >= 5:
        if cache and (r := _cached_s5()) is not None:
            s5 = r
            print(f"[CACHE] Stage 5 — {s5.n_tables} tables, {s5.n_figures} figures on disk")
        else:
            print("[RUN] Stage 5 — pitch kinematics (3D fan analysis)")
            s5 = run_analysis.step_6_pitch_kinematics()
            print(f"[INFO] Tables: {s5.n_tables}  Figures: {s5.n_figures}")

    # ── Stage 6 — reverse thrust modelling ──────────────────────────────────
    if stage_num >= 6:
        if cache and (r := _cached_s6()) is not None:
            s6 = r
            print(f"[CACHE] Stage 6 — beta_opt={s6.beta_opt_deg:.1f} deg thrust_frac={s6.thrust_fraction:.3f}")
        else:
            print("[RUN] Stage 6 — reverse thrust modelling (BEM)")
            s6 = run_analysis.step_7_reverse_thrust()
            print(f"[INFO] beta_opt: {s6.beta_opt_deg:.1f} deg  thrust_fraction: {s6.thrust_fraction:.3f}")
            print(f"[INFO] Mechanism: {s6.mechanism_weight_kg:.0f} kg  SFC penalty: +{s6.sfc_cruise_penalty_pct:.3f}%")

    # ── Stage 7 — SFC analysis ──────────────────────────────────────────────
    if stage_num >= 7:
        if cache and (r := _cached_s7()) is not None:
            s7 = r
            print(f"[CACHE] Stage 7 — mean SFC reduction: {s7.mean_sfc_reduction_pct:.2f}%")
        else:
            print("[RUN] Stage 7 — SFC analysis")
            s7 = run_analysis.step_8_sfc_analysis()
            print(f"[INFO] Mean SFC reduction: {s7.mean_sfc_reduction_pct:.2f}%")

    print("-" * 80)
    for line in _validate_stage_outputs(stage_num):
        print(line)
    print("=" * 80)


def build_parser(stage_num: int) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Run and validate the pipeline up to Stage {stage_num}."
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not delete previous results before running.",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help=(
            "Skip stages whose results already exist on disk. "
            "Implies --no-clean."
        ),
    )
    return parser
