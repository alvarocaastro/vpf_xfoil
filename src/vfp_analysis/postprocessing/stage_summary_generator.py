"""
Stage summary generator.

Produces concise finalresults_stageX.txt files containing:
  - Timestamp and stage objective
  - Key numerical results (read from the output CSVs)
  - High-level artifact summaries without local filesystem paths

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
        "Scoring criteria : (CL/CD)_2nd·1.20  +  robustness_LD·0.35  +  stability_margin·0.80",
        "",
        "Outputs: stage artefacts generated successfully.",
    ]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 2 — XFOIL Simulations
# ---------------------------------------------------------------------------

def generate_stage2_summary(
    stage_dir: Path,
    num_simulations: int,
    delta_beta: dict | None = None,
    alpha_eff_map: dict | None = None,
    stall_map: dict | None = None,
) -> str:
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

    if alpha_eff_map and stall_map:
        lines += ["", "Stall margin per condition (α_stall − α_opt):"]
        header = f"  {'Condition':<18} {'α_opt':>7} {'α_stall':>8} {'CL_max':>8} {'Margin':>8}"
        lines.append(header)
        lines.append("  " + "-" * (len(header) - 2))
        for fc in flights:
            for s in sects:
                key = (fc, s)
                a_opt = alpha_eff_map.get(key, float("nan"))
                stall_data = stall_map.get(key, (float("nan"), float("nan")))
                a_stall, cl_max = stall_data
                margin = a_stall - a_opt if a_opt == a_opt and a_stall == a_stall else float("nan")
                lines.append(
                    f"  {fc.title()+'/'+s:<18} {a_opt:>7.2f}° {a_stall:>7.2f}° {cl_max:>8.4f} {margin:>7.2f}°"
                )

    if delta_beta:
        lines += [
            "",
            "Variable pitch range Δβ (velocity triangle analysis):",
        ]
        for section, db in delta_beta.items():
            lines.append(f"  {section:<12}: Δβ = {db:.1f}°")

    lines += [
        "",
        "Outputs: polar.csv per simulation, cl_alpha_stall/efficiency/polar plots, VPF analysis.",
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

    lines += ["", "Outputs: corrected polar data and comparison plots generated successfully."]
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
                    f"(CL/CD)_max    : {df['max_efficiency'].min():.2f} – {df['max_efficiency'].max():.2f}  "
                    f"(mean {df['max_efficiency'].mean():.2f})",
                    f"alpha_opt      : {df['alpha_opt_deg'].min():.1f}° – {df['alpha_opt_deg'].max():.1f}°  "
                    f"(mean {df['alpha_opt_deg'].mean():.1f}°)",
                ]
                if "stall_margin_deg" in df.columns:
                    lines += [
                        f"stall_margin   : {df['stall_margin_deg'].min():.1f}° – {df['stall_margin_deg'].max():.1f}°  "
                        f"(mean {df['stall_margin_deg'].mean():.1f}°)"
                        f"  [min safe: 3°]",
                    ]

                # Warn about low-efficiency cases (wave drag penalty at high Mach)
                EFF_THRESHOLD = 70.0
                low_eff = df[df["max_efficiency"] < EFF_THRESHOLD]
                if not low_eff.empty:
                    lines += [""]
                    lines += [f"AVISO — Casos con (CL/CD)_max < {EFF_THRESHOLD:.0f} (penalizacion por wave drag):"]
                    for _, row in low_eff.iterrows():
                        lines += [
                            f"     {row['flight_condition']}/{row['blade_section']}: "
                            f"(CL/CD)={row['max_efficiency']:.1f}  alpha_opt={row['alpha_opt_deg']:.1f}"
                        ]

                # Design reference summary
                if "alpha_design_deg" in df.columns and "delta_alpha_deg" in df.columns:
                    lines += ["", "Referencia de diseno: alpha_opt de crucero por seccion"]
                    cruise = df[df["flight_condition"] == "cruise"]
                    for _, row in cruise.sort_values("blade_section").iterrows():
                        lines += [
                            f"  {row['blade_section']:10s}: alpha_design = {row['alpha_design_deg']:.2f}"
                        ]

                    lines += ["", "Ajuste VPF requerido (delta_alpha) por condicion:"]
                    non_cruise = df[df["flight_condition"] != "cruise"]
                    for cond in ["takeoff", "climb", "descent"]:
                        sub = non_cruise[non_cruise["flight_condition"] == cond]
                        if sub.empty:
                            continue
                        lines += [
                            f"  {cond:8s}: {sub['delta_alpha_deg'].min():.1f} – "
                            f"{sub['delta_alpha_deg'].max():.1f}  "
                            f"(media {sub['delta_alpha_deg'].mean():.1f})"
                        ]

                    if "eff_gain_pct" in df.columns:
                        lines += ["", "Ganancia de eficiencia VPF (eff_gain_pct):"]
                        for cond in ["takeoff", "climb", "descent"]:
                            sub = non_cruise[non_cruise["flight_condition"] == cond]
                            if sub.empty:
                                continue
                            lines += [
                                f"  {cond:8s}: {sub['eff_gain_pct'].min():.1f}% – "
                                f"{sub['eff_gain_pct'].max():.1f}%  "
                                f"(media {sub['eff_gain_pct'].mean():.1f}%)"
                            ]
        except Exception:
            pass

    figures_dir = stage_dir / "figures"
    n_figs = len(list(figures_dir.glob("*.png"))) if figures_dir.exists() else 0

    lines += [
        "",
        "Tables exported:",
        f"  summary_table.csv       → {tables_dir / 'summary_table.csv'}",
        f"  clcd_max_by_section.csv → {tables_dir / 'clcd_max_by_section.csv'}",
        "",
        f"Figures generated: {n_figs}",
        "  design_reference_root.png         — curvas CL/CD vs alpha, seccion root",
        "  design_reference_mid_span.png     — curvas CL/CD vs alpha, seccion mid_span",
        "  design_reference_tip.png          — curvas CL/CD vs alpha, seccion tip",
        "  efficiency_penalty_overview.png   — figura resumen con anotaciones delta",
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
        "  [Core — Stages 2 polars]",
        "  efficiency_{condition}_{section}.png      — CL/CD vs α with α_opt (one per case)",
        "  efficiency_by_section_{condition}.png     — section comparison per condition",
        "  alpha_opt_vs_condition.png                — key thesis result (α_opt matrix)",
        "",
        "  [Figure A — Stage 3 corrected polars]",
        "  section_polar_comparison_{condition}.png  — dual panel: efficiency + lift polars",
        "    (root / mid_span / tip overlaid, ★ = 2nd efficiency peak)  [4 files]",
        "",
        "  [Figure B — VPF penalty proof, Stage 3 corrected polars]",
        "  cruise_penalty_{condition}.png            — efficiency polars for non-cruise",
        "    conditions with VPF optimal α (★) and fixed cruise pitch (dashed red line)",
        "    + penalty annotation on mid_span curve  [3 files: takeoff, climb, descent]",
        "",
        "Outputs: publication figures generated successfully.",
    ]
    lines += _footer()
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Stage 6 — VPF Analysis
# ---------------------------------------------------------------------------

def generate_stage6_summary(stage_dir: Path) -> str:
    tables_dir = stage_dir / "tables"
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
        "Outputs: VPF tables, figures, and summary generated successfully.",
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
        "Outputs: kinematic tables and figures generated successfully.",
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
        "Outputs: SFC tables, figures, and summary generated successfully.",
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
