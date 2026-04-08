"""
Stage summary generator.

Produces concise finalresults_stageX.txt files containing:
  - Timestamp and stage objective
  - Key numerical results (read from the output CSVs)
  - Paths of files generated

Deliberately minimal — detailed methodology is documented in the thesis itself.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, List

import pandas as pd

from vfp_analysis.config_loader import (
    get_alpha_range,
    get_blade_sections,
    get_flight_conditions,
    get_ncrit_table,
    get_reynolds_table,
    get_selection_alpha_range,
    get_selection_ncrit,
    get_selection_reynolds,
    get_target_mach,
)


def _ts() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _header(stage: int, title: str) -> List[str]:
    return [
        "=" * 70,
        f"STAGE {stage}: {title}",
        f"Generated: {_ts()}",
        "=" * 70,
        "",
    ]


def _footer() -> List[str]:
    return ["", "=" * 70]


# ---------------------------------------------------------------------------
# Stage 1 — Airfoil Selection
# ---------------------------------------------------------------------------

def generate_stage1_summary(stage_dir: Path, selected_airfoil_name: str) -> str:
    alpha = get_selection_alpha_range()
    re    = get_selection_reynolds()
    nc    = get_selection_ncrit()
    lines = _header(1, "AIRFOIL SELECTION")
    lines += [
        f"Selected airfoil : {selected_airfoil_name}",
        f"Alpha range      : {alpha['min']:.1f}° → {alpha['max']:.1f}° (step {alpha['step']:.2f}°)",
        f"Reference Re     : {re:.2e}  |  Ncrit: {nc:.1f}",
        "Scoring criteria : (CL/CD)_max (w=1.0)  +  α_stall·5 (w=5.0)  −  C̄_D·5000 (w=5000)",
        "",
        "Outputs:",
        f"  {stage_dir / 'airfoil_selection'}",
    ]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 2 — XFOIL Simulations
# ---------------------------------------------------------------------------

def generate_stage2_summary(stage_dir: Path, num_simulations: int) -> str:
    alpha   = get_alpha_range()
    flights = get_flight_conditions()
    sects   = get_blade_sections()
    re_tab  = get_reynolds_table()
    nc_tab  = get_ncrit_table()

    lines = _header(2, "XFOIL AERODYNAMIC SIMULATIONS")
    lines += [
        f"Simulations run  : {num_simulations}  ({len(flights)} conditions × {len(sects)} sections)",
        f"Alpha range      : {alpha['min']:.1f}° → {alpha['max']:.1f}° (step {alpha['step']:.2f}°)",
        "",
        "Reynolds & Ncrit per condition:",
    ]
    for fc in flights:
        re_str = "  ".join(f"{s}: {re_tab[fc][s]:.2e}" for s in sects)
        lines.append(f"  {fc.title():<10} Ncrit={nc_tab[fc]:.1f}  |  {re_str}")
    lines += [
        "",
        "Outputs:",
        f"  Polars  : {stage_dir / 'polars'}",
        f"  Raw     : {stage_dir / 'final_analysis'}",
    ]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 3 — Compressibility Corrections
# ---------------------------------------------------------------------------

def generate_stage3_summary(stage_dir: Path) -> str:
    flights  = get_flight_conditions()
    sects    = get_blade_sections()
    mach_tab = get_target_mach()

    lines = _header(3, "PRANDTL-GLAUERT COMPRESSIBILITY CORRECTIONS")
    lines += [
        "Correction model : Prandtl-Glauert  (CL only; CD unchanged)",
        "Reference Mach   : 0.20",
        "",
        "Target Mach numbers:",
    ]
    for fc in flights:
        lines.append(f"  {fc.title():<10} M = {mach_tab[fc]:.2f}")

    # Read corrected summary if available
    corr_summary = stage_dir / "corrected_efficiency_summary.csv"
    if corr_summary.exists():
        try:
            df = pd.read_csv(corr_summary)
            if not df.empty:
                lines += [
                    "",
                    f"Cases corrected  : {len(df)}  ({len(flights)} × {len(sects)})",
                    f"alpha_opt range  : {df['alpha_opt_deg'].min():.1f}° – {df['alpha_opt_deg'].max():.1f}°",
                    f"(CL/CD)_max range: {df['ld_max_corrected'].min():.2f} – {df['ld_max_corrected'].max():.2f}",
                ]
        except Exception:
            pass

    lines += ["", f"Output: {stage_dir}"]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 4 — Performance Metrics
# ---------------------------------------------------------------------------

def generate_stage4_summary(stage_dir: Path, metrics: List[Any]) -> str:
    tables_dir   = stage_dir / "tables"
    summary_file = tables_dir / "summary_table.csv"

    lines = _header(4, "AERODYNAMIC PERFORMANCE METRICS")
    lines += [
        f"Cases analysed   : {len(metrics)}",
        "Optimal point    : second CL/CD peak (alpha ≥ 3°) — avoids laminar-bubble artefact",
        "",
    ]

    if summary_file.exists():
        try:
            df = pd.read_csv(summary_file)
            if not df.empty:
                lines += [
                    f"(CL/CD)_max: {df['max_efficiency'].min():.2f} – {df['max_efficiency'].max():.2f}  "
                    f"(mean {df['max_efficiency'].mean():.2f})",
                    f"alpha_opt  : {df['alpha_opt_deg'].min():.1f}° – {df['alpha_opt_deg'].max():.1f}°  "
                    f"(mean {df['alpha_opt_deg'].mean():.1f}°)",
                ]
        except Exception:
            pass

    lines += [
        "",
        "Tables exported:",
        f"  summary_table.csv      → {tables_dir / 'summary_table.csv'}",
        f"  clcd_max_by_section.csv→ {tables_dir / 'clcd_max_by_section.csv'}",
    ]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 5 — Figures
# ---------------------------------------------------------------------------

def generate_stage5_summary(stage_dir: Path) -> str:
    figures_dir = stage_dir / "figures"
    n_figs      = len(list(figures_dir.glob("*.png"))) if figures_dir.exists() else 0

    lines = _header(5, "PUBLICATION-QUALITY FIGURES")
    lines += [
        f"Figures generated: {n_figs}  (300 DPI PNG, LaTeX-ready)",
        "",
        "Figure set:",
        "  efficiency_{condition}_{section}.png  — CL/CD vs α with α_opt (one per case)",
        "  efficiency_by_section_{condition}.png — section comparison per condition",
        "  alpha_opt_vs_condition.png            — key thesis result (α_opt matrix)",
        "",
        f"Output: {figures_dir}",
    ]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 6 — VPF Analysis
# ---------------------------------------------------------------------------

def generate_stage6_summary(stage_dir: Path) -> str:
    tables_dir = stage_dir.parent / "stage_4" / "tables"
    figures_dir = stage_dir / "figures"

    lines = _header(6, "VARIABLE PITCH FAN (VPF) ANALYSIS")
    lines += [
        "Computes α_opt per condition/section and pitch adjustments relative to cruise.",
        "",
    ]

    opt_file = tables_dir / "vpf_optimal_pitch.csv"
    adj_file = tables_dir / "vpf_pitch_adjustment.csv"
    if opt_file.exists():
        try:
            df = pd.read_csv(opt_file)
            if not df.empty:
                lines += [
                    f"alpha_opt range  : {df['alpha_opt'].min():.1f}° – {df['alpha_opt'].max():.1f}°  "
                    f"(mean {df['alpha_opt'].mean():.1f}°)",
                    f"(CL/CD)_max mean : {df['CL_CD_max'].mean():.2f}",
                ]
        except Exception:
            pass

    lines += [
        "",
        "Outputs:",
        f"  {opt_file}",
        f"  {adj_file}",
        f"  {figures_dir}",
    ]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 7 — Kinematics Analysis
# ---------------------------------------------------------------------------

def generate_stage7_summary(stage_dir: Path) -> str:
    tables_dir  = stage_dir / "tables"
    figures_dir = stage_dir / "figures"
    kin_file    = tables_dir / "kinematics_analysis.csv"

    lines = _header(7, "KINEMATIC VELOCITY-TRIANGLE ANALYSIS")
    lines += [
        "Translates aerodynamic pitch angles into mechanical pitch commands",
        "via the velocity triangle: Δβ_mech = Δα_aero + Δφ.",
        "",
    ]

    if kin_file.exists():
        try:
            df = pd.read_csv(kin_file)
            if not df.empty and "delta_beta_mech_deg" in df.columns:
                # Exclude cruise (reference, Δβ=0) from range display
                non_cruise = df[df["condition"] != "cruise"]
                if not non_cruise.empty:
                    lines += [
                        f"Δφ range (non-cruise) : "
                        f"{non_cruise['delta_beta_mech_deg'].min():.2f}° – "
                        f"{non_cruise['delta_beta_mech_deg'].max():.2f}°",
                    ]
        except Exception:
            pass

    lines += [
        "",
        "Outputs:",
        f"  {kin_file}",
        f"  {figures_dir}",
    ]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 8 — SFC Analysis
# ---------------------------------------------------------------------------

def generate_stage8_summary(stage_dir: Path) -> str:
    tables_dir  = stage_dir / "tables"
    figures_dir = stage_dir / "figures"
    sfc_file    = tables_dir / "sfc_analysis.csv"

    lines = _header(8, "SPECIFIC FUEL CONSUMPTION (SFC) IMPACT ANALYSIS")
    lines += [
        "Estimates SFC reduction enabled by VPF optimised-pitch operation.",
        "Fan efficiency transfer: η_fan,new = η_base·[1 + τ·((CL/CD)_new/(CL/CD)_base − 1)]",
        "Dampening factor τ = 0.65 (accounts for 3-D tip-clearance and secondary-flow losses).",
        "",
    ]

    if sfc_file.exists():
        try:
            df = pd.read_csv(sfc_file)
            if not df.empty and "sfc_reduction_percent" in df.columns:
                mean_red = df["sfc_reduction_percent"].mean()
                max_red  = df["sfc_reduction_percent"].max()
                lines += [
                    f"SFC reduction range  : {df['sfc_reduction_percent'].min():.2f}% – {max_red:.2f}%",
                    f"Envelope mean        : {mean_red:.2f}%",
                ]
        except Exception:
            pass

    lines += [
        "",
        "Outputs:",
        f"  {sfc_file}",
        f"  {figures_dir}",
    ]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def write_stage_summary(stage_num: int, summary_text: str, stage_dir: Path) -> None:
    """Write stage summary to finalresults_stageX.txt."""
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / f"finalresults_stage{stage_num}.txt").write_text(
        summary_text, encoding="utf-8"
    )
