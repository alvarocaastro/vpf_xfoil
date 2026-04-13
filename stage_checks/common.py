"""
common.py
---------
Shared logic for stage check scripts (Stages 1–6).

Pipeline step mapping:
    Stage 1  → step_2_airfoil_selection()       → Stage1Result
    Stage 2  → step_3_xfoil_simulations(s1)     → Stage2Result
    Stage 3  → step_4_compressibility_correction(s2) → Stage3Result
    Stage 4  → step_5_metrics_and_figures(s3)   → Stage4Result
    Stage 5  → step_6_pitch_kinematics()        → Stage5Result
    Stage 6  → step_7_sfc_analysis()            → Stage6Result
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
            (stage_dir / "airfoil_selection" / "selected_airfoil.dat", "perfil seleccionado (.dat)"),
        ]
    elif stage_num == 2:
        checks = [
            (stage_dir / "simulation_plots", "directorio simulation_plots"),
            (stage_dir / "polars",           "directorio polares planas"),
        ]
    elif stage_num == 3:
        checks = [
            (stage_dir, "directorio de salida correcciones"),
        ]
    elif stage_num == 4:
        checks = [
            (stage_dir / "tables" / "summary_table.csv",      "tabla de métricas"),
            (stage_dir / "tables" / "clcd_max_by_section.csv","tabla CL/CD por sección"),
            (stage_dir / "figures",                            "directorio de figuras"),
        ]
    elif stage_num == 5:
        checks = [
            (stage_dir / "tables" / "optimal_incidence.csv",        "tabla de incidencia óptima"),
            (stage_dir / "tables" / "stage_loading.csv",            "tabla de carga de etapa"),
            (stage_dir / "tables" / "blade_twist_design.csv",       "tabla de twist de diseño"),
            (stage_dir / "tables" / "off_design_incidence.csv",     "tabla de incidencia off-design"),
            (stage_dir / "tables" / "cascade_corrections.csv",      "tabla de correcciones de cascada"),
            (stage_dir / "tables" / "rotational_corrections.csv",   "tabla de correcciones rotacionales"),
            (stage_dir / "figures",                                  "directorio de figuras"),
        ]
    elif stage_num == 6:
        checks = [
            (stage_dir / "tables" / "sfc_analysis.csv",          "tabla SFC agregada"),
            (stage_dir / "tables" / "sfc_section_breakdown.csv", "tabla SFC por sección"),
            (stage_dir / "tables" / "sfc_sensitivity.csv",       "tabla sensibilidad tau"),
            (stage_dir / "figures",                               "directorio de figuras"),
        ]

    messages: list[str] = []
    for path, label in checks:
        status = "OK" if path.exists() else "MISSING"
        messages.append(f"[{status}] {label}: {path}")

    # Count artifacts
    if stage_num == 2:
        polars_dir = stage_dir / "polars"
        messages.append(f"[INFO] Polares planas (csv): {_existing_count(polars_dir, '*.csv')}")
    elif stage_num == 3:
        corrected = _existing_count(stage_dir, "*/*/corrected_polar.csv")
        messages.append(f"[INFO] Polares corregidas: {corrected}")
    elif stage_num == 4:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Figuras Stage 4: {_existing_count(figures_dir, '*.png')}")
    elif stage_num == 5:
        figures_dir = stage_dir / "figures"
        tables_dir = stage_dir / "tables"
        messages.append(f"[INFO] Figuras Stage 5: {_existing_count(figures_dir, '*.png')}")
        messages.append(f"[INFO] Tablas Stage 5:  {_existing_count(tables_dir, '*.csv')}")
    elif stage_num == 6:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Figuras Stage 6: {_existing_count(figures_dir, '*.png')}")

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
    from vfp_analysis.core.domain.airfoil import Airfoil
    airfoil = Airfoil(name=name, family="", dat_path=dat)
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
    import pandas as pd
    from vfp_analysis.stage4_performance_metrics.metrics import AerodynamicMetrics
    # Return a minimal result — metrics list left empty (only needed for downstream stages
    # that read from disk anyway)
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


# ---------------------------------------------------------------------------
# Main check runner
# ---------------------------------------------------------------------------

def run_stage_check(stage_num: int, clean: bool = True, cache: bool = False) -> None:
    """Run the pipeline up to *stage_num* and validate its outputs.

    Parameters
    ----------
    stage_num : int   Target stage (1–6).
    clean : bool      Wipe previous results before running (ignored in cache mode).
    cache : bool      Skip re-running stages whose artifacts already exist on disk.
    """
    if stage_num < 1 or stage_num > 6:
        raise ValueError("stage_num must be between 1 and 6")

    if cache:
        clean = False

    print("=" * 80)
    print(f"Stage check: Stage {stage_num}"
          + ("  [cache — saltando stages completados]" if cache else ""))
    print("=" * 80)

    if clean:
        print("[RUN] Limpiando resultados anteriores")
        run_analysis.step_1_clean_results()

    s1: Stage1Result | None = None
    s2: Stage2Result | None = None
    s3: Stage3Result | None = None
    s4: Stage4Result | None = None
    s5: Stage5Result | None = None

    # ── Stage 1 — selección de perfil ───────────────────────────────────────
    if stage_num >= 1:
        if cache and (r := _cached_s1()) is not None:
            s1 = r
            print(f"[CACHE] Stage 1 — perfil: {s1.selected_airfoil_name}")
        else:
            print("[RUN] Stage 1 — selección de perfil")
            s1 = run_analysis.step_2_airfoil_selection()
            print(f"[INFO] Perfil seleccionado: {s1.selected_airfoil_name}")

    # ── Stage 2 — simulaciones XFOIL ────────────────────────────────────────
    if stage_num >= 2:
        if cache and (r := _cached_s2()) is not None:
            s2 = r
            print(f"[CACHE] Stage 2 — {s2.n_simulations} polares en disco")
        else:
            print("[RUN] Stage 2 — simulaciones XFOIL")
            s2 = run_analysis.step_3_xfoil_simulations(s1)
            print(f"[INFO] Simulaciones: {s2.n_simulations}")

    # ── Stage 3 — correcciones de compresibilidad ────────────────────────────
    if stage_num >= 3:
        if cache and (r := _cached_s3()) is not None:
            s3 = r
            print(f"[CACHE] Stage 3 — {s3.n_cases_corrected} polares corregidas en disco")
        else:
            print("[RUN] Stage 3 — correcciones de compresibilidad")
            s3 = run_analysis.step_4_compressibility_correction(s2)
            print(f"[INFO] Casos corregidos: {s3.n_cases_corrected}")

    # ── Stage 4 — métricas y figuras ────────────────────────────────────────
    if stage_num >= 4:
        if cache and (r := _cached_s4()) is not None:
            s4 = r
            print("[CACHE] Stage 4 — métricas en disco")
        else:
            print("[RUN] Stage 4 — métricas aerodinámicas y figuras")
            s4 = run_analysis.step_5_metrics_and_figures(s3)
            print(f"[INFO] Métricas computadas: {len(s4.metrics)}")

    # ── Stage 5 — cinemática de pitch ───────────────────────────────────────
    if stage_num >= 5:
        if cache and (r := _cached_s5()) is not None:
            s5 = r
            print(f"[CACHE] Stage 5 — {s5.n_tables} tablas, {s5.n_figures} figuras en disco")
        else:
            print("[RUN] Stage 5 — cinemática de paso (análisis 3D de fan)")
            s5 = run_analysis.step_6_pitch_kinematics()
            print(f"[INFO] Tablas: {s5.n_tables}  Figuras: {s5.n_figures}")

    # ── Stage 6 — análisis de SFC ───────────────────────────────────────────
    if stage_num >= 6:
        stage6_dir = base_config.get_stage_dir(6)
        cached_s6 = cache and (stage6_dir / "tables" / "sfc_analysis.csv").is_file()
        if cached_s6:
            print("[CACHE] Stage 6 — SFC en disco")
        else:
            print("[RUN] Stage 6 — análisis de SFC")
            s6 = run_analysis.step_7_sfc_analysis()
            print(f"[INFO] Reducción media SFC: {s6.mean_sfc_reduction_pct:.2f}%")

    print("-" * 80)
    for line in _validate_stage_outputs(stage_num):
        print(line)
    print("=" * 80)


def build_parser(stage_num: int) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Ejecuta y valida el pipeline hasta el Stage {stage_num}."
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="No eliminar resultados anteriores antes de ejecutar.",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help=(
            "Saltar stages cuyos resultados ya existen en disco. "
            "Implica --no-clean."
        ),
    )
    return parser
