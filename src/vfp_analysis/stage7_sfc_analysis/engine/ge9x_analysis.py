"""GE9X turbofan SFC parametric analysis for Stage 7.

Loads mid-span Cl/Cd data from Stage 4 results, identifies the reference
(fixed-pitch cruise β) and optimised (VPF α_opt) operating points, then
produces a Cl/Cd → fuel saving sweep with figures and a LaTeX table.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis.shared.plot_style import apply_style
from vfp_analysis.stage7_sfc_analysis.engine.engine_data import (
    GE9X_PARAMS,
    sfc_lbh_to_si,
    sfc_si_to_lbh,
)
from vfp_analysis.stage7_sfc_analysis.engine.sfc_model import compute_sfc_improvement
from vfp_analysis.stage7_sfc_analysis.engine.turbofan_cycle import compute_turbofan_sfc

LOGGER = logging.getLogger(__name__)

_CLCD_SWEEP = np.linspace(80.0, 150.0, 50)
_K_THROTTLE_VARIANTS = [0.05, 0.08, 0.12, 0.15]
_CONDITION_ORDER = ["takeoff", "climb", "cruise", "descent"]
_CONDITION_LABELS = {
    "takeoff": "Takeoff", "climb": "Climb",
    "cruise": "Cruise", "descent": "Descent",
}
# Paul Tol colorblind-safe
_COND_COLORS = {
    "takeoff": "#4477AA", "climb": "#CCBB44",
    "cruise": "#228833",  "descent": "#EE6677",
}


def _load_clcd_at_alpha_opt(
    pitch_map_csv: Path,
    polars_dir: Path,
) -> dict[str, float]:
    """Return {condition: Cl/Cd at α_opt} for mid-span section."""
    pitch_df = pd.read_csv(pitch_map_csv)
    mid_rows = pitch_df[pitch_df["section"] == "mid_span"].set_index("flight")
    clcd_map: dict[str, float] = {}
    for cond in _CONDITION_ORDER:
        if cond not in mid_rows.index:
            continue
        alpha_opt = float(mid_rows.loc[cond, "alpha_opt"])
        polar_path = polars_dir / f"{cond}_mid_span.csv"
        if not polar_path.exists():
            continue
        pf = pd.read_csv(polar_path)
        # Resolve efficiency column
        for col in ("ld_kt", "ld_corrected", "CL_CD_corrected", "ld", "CL_CD"):
            if col in pf.columns:
                eff_col = col
                break
        else:
            continue
        pf = pf.replace([float("inf"), float("-inf")], pd.NA).dropna(subset=[eff_col, "alpha"])
        if pf.empty:
            continue
        ld_interp = (
            pf.set_index("alpha")[eff_col]
            .reindex(sorted(set(pf["alpha"].tolist() + [alpha_opt])))
            .interpolate(method="index")
        )
        val = ld_interp.loc[alpha_opt]
        clcd_map[cond] = float(val.iloc[0] if hasattr(val, "iloc") else val)
    return clcd_map


def run_ge9x_analysis(
    stage4_dir: Path,
    stage2_dir: Path,
    tables_dir: Path,
    figures_dir: Path,
) -> Optional[float]:
    """Run GE9X parametric SFC analysis. Returns fuel_saving_pct at takeoff α_opt, or None."""
    # blade_pitch_map is written by Stage 2 pitch-map step
    pitch_map_csv = stage2_dir / "pitch_map" / "blade_pitch_map.csv"
    polars_dir    = stage2_dir / "polars"

    if not pitch_map_csv.exists():
        # Fallback: Stage 4 tables
        pitch_map_csv = stage4_dir / "tables" / "blade_pitch_map.csv"
    if not pitch_map_csv.exists():
        LOGGER.warning("blade_pitch_map.csv not found — skipping GE9X analysis")
        return None

    # ── Validate cycle model ──────────────────────────────────────────────
    cycle = compute_turbofan_sfc(GE9X_PARAMS, "cruise")
    LOGGER.info(
        "GE9X cycle validation: SFC_cruise = %.4f lb/lbf·h  (ref %.2f, delta %+.1f%%)",
        cycle["SFC_lbh"], GE9X_PARAMS["SFC_ref_cruise"], cycle["validation_delta_pct"],
    )
    SFC_design_si = sfc_lbh_to_si(GE9X_PARAMS["SFC_ref_cruise"])

    # ── Load Cl/Cd at α_opt per condition ────────────────────────────────
    clcd_opt = _load_clcd_at_alpha_opt(pitch_map_csv, polars_dir)
    if not clcd_opt:
        LOGGER.warning("No Cl/Cd data found for GE9X analysis")
        return None

    # Reference = cruise Cl/Cd (fixed-pitch design point)
    ClCd_ref = clcd_opt.get("cruise", 100.0)
    LOGGER.info("Cl/Cd reference (cruise, fixed pitch): %.1f", ClCd_ref)
    for cond, val in clcd_opt.items():
        LOGGER.info("  Cl/Cd at alpha_opt (%s): %.1f", cond, val)

    # ── Parametric sweep ─────────────────────────────────────────────────
    sweep_rows = [
        compute_sfc_improvement(ClCd_ref, float(clcd), SFC_design_si)
        for clcd in _CLCD_SWEEP
    ]
    df_sweep = pd.DataFrame(sweep_rows)
    df_sweep["SFC_lbh"] = df_sweep["SFC_new_kgNs"].apply(sfc_si_to_lbh)
    df_sweep.to_csv(tables_dir / "ge9x_sfc_parametric.csv", index=False, float_format="%.6f")

    # ── Key-points table ─────────────────────────────────────────────────
    key_clcd = [80, 90, 100, 110, 120, 130, 140, 150]
    key_rows = [compute_sfc_improvement(ClCd_ref, float(c), SFC_design_si) for c in key_clcd]
    df_key = pd.DataFrame(key_rows)
    df_key["SFC_lbh"] = df_key["SFC_new_kgNs"].apply(sfc_si_to_lbh)
    df_key.to_csv(tables_dir / "ge9x_sfc_improvement.csv", index=False, float_format="%.6f")

    # ── LaTeX table (manual generation — no jinja2 dependency) ───────────
    lines = [
        r"\begin{table}[htbp]",
        r"  \centering",
        r"  \caption{Fuel consumption improvement as a function of aerodynamic efficiency"
        r" $C_L/C_D$ for the GE9X-105B1A engine in takeoff phase.}",
        r"  \label{tab:ge9x_sfc_improvement}",
        r"  \begin{tabular}{cccc}",
        r"    \toprule",
        r"    $C_L/C_D$ [-] & SFC [lb/lbf$\cdot$h] & $\Delta$SFC [\%] & Fuel saving [\%] \\",
        r"    \midrule",
    ]
    for _, row in df_key.iterrows():
        lines.append(
            f"    {row['ClCd_new']:.0f} & {row['SFC_lbh']:.4f} & "
            f"{row['SFC_improvement_pct']:.4f} & {row['fuel_saving_pct']:.4f} \\\\"
        )
    lines += [r"    \bottomrule", r"  \end{tabular}", r"\end{table}"]
    (tables_dir / "ge9x_sfc_improvement.tex").write_text("\n".join(lines), encoding="utf-8")
    LOGGER.info("LaTeX table written: ge9x_sfc_improvement.tex")

    # ── Figures ───────────────────────────────────────────────────────────
    _plot_fuel_saving(df_sweep, ClCd_ref, clcd_opt, figures_dir)
    _plot_sfc_absolute(df_sweep, ClCd_ref, SFC_design_si, figures_dir)
    _plot_sensitivity(ClCd_ref, figures_dir)

    takeoff_clcd = clcd_opt.get("takeoff", None)
    if takeoff_clcd is not None:
        res = compute_sfc_improvement(ClCd_ref, takeoff_clcd, SFC_design_si)
        LOGGER.info(
            "GE9X: takeoff Cl/Cd=%.1f vs cruise ref %.1f → fuel saving %.2f%%",
            takeoff_clcd, ClCd_ref, res["fuel_saving_pct"],
        )
        return float(res["fuel_saving_pct"])
    return None


def _plot_fuel_saving(
    df_sweep: pd.DataFrame,
    ClCd_ref: float,
    clcd_opt: dict[str, float],
    figures_dir: Path,
) -> None:
    with apply_style():
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(df_sweep["ClCd_new"], df_sweep["fuel_saving_pct"],
                color="#4477AA", linewidth=2.2, label="Fuel saving (k_throttle=0.08)")
        ax.fill_between(df_sweep["ClCd_new"], df_sweep["fuel_saving_pct"],
                        alpha=0.12, color="#4477AA")
        ax.axvline(ClCd_ref, color="#888888", linestyle="--", linewidth=1.2,
                   label=f"Fixed-pitch reference (Cl/Cd = {ClCd_ref:.0f})")
        for cond in _CONDITION_ORDER:
            if cond in clcd_opt and cond != "cruise":
                val = clcd_opt[cond]
                res = compute_sfc_improvement(ClCd_ref, val,
                                              sfc_lbh_to_si(GE9X_PARAMS["SFC_ref_cruise"]))
                ax.scatter(val, res["fuel_saving_pct"],
                           color=_COND_COLORS.get(cond, "#999999"), s=60, zorder=5,
                           label=f"{_CONDITION_LABELS.get(cond, cond)} α_opt ({val:.0f})")
        ax.axhline(0, color="black", linewidth=0.8, linestyle=":")
        ax.set_xlabel(r"$C_L / C_D$ [-]")
        ax.set_ylabel("Fuel saving [%]")
        ax.set_title("Fuel consumption improvement vs aerodynamic efficiency\n"
                     "(GE9X-105B1A, takeoff phase)")
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
        fig.tight_layout()
        fig.savefig(figures_dir / "fuel_saving_vs_ClCd.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def _plot_sfc_absolute(
    df_sweep: pd.DataFrame,
    ClCd_ref: float,
    SFC_design_si: float,
    figures_dir: Path,
) -> None:
    SFC_ref_lbh = GE9X_PARAMS["SFC_ref_cruise"]
    with apply_style():
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(df_sweep["ClCd_new"], df_sweep["SFC_lbh"],
                color="#D55E00", linewidth=2.2, label="SFC at reduced throttle")
        ax.axhline(SFC_ref_lbh, color="navy", linestyle=":", linewidth=1.5,
                   label=f"GE9X cruise SFC = {SFC_ref_lbh} lb/lbf·h")
        ax.axvline(ClCd_ref, color="#888888", linestyle="--", linewidth=1.2,
                   label=f"Fixed-pitch reference (Cl/Cd = {ClCd_ref:.0f})")
        ax.set_xlabel(r"$C_L / C_D$ [-]")
        ax.set_ylabel("SFC [lb/lbf·h]")
        ax.set_title("SFC vs aerodynamic efficiency — GE9X-105B1A")
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
        fig.tight_layout()
        fig.savefig(figures_dir / "SFC_vs_ClCd.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


def _plot_sensitivity(ClCd_ref: float, figures_dir: Path) -> None:
    SFC_design_si = sfc_lbh_to_si(GE9X_PARAMS["SFC_ref_cruise"])
    with apply_style():
        fig, ax = plt.subplots(figsize=(8, 5))
        colors = ["#4477AA", "#228833", "#EE6677", "#CCBB44"]
        for k, color in zip(_K_THROTTLE_VARIANTS, colors):
            savings = [
                compute_sfc_improvement(ClCd_ref, float(c), SFC_design_si, k_throttle=k)["fuel_saving_pct"]
                for c in _CLCD_SWEEP
            ]
            ax.plot(_CLCD_SWEEP, savings, label=f"k_throttle = {k}", color=color, linewidth=1.8)
        ax.axvline(ClCd_ref, color="#888888", linestyle="--", linewidth=1.2,
                   label=f"Reference (Cl/Cd = {ClCd_ref:.0f})")
        ax.set_xlabel(r"$C_L / C_D$ [-]")
        ax.set_ylabel("Fuel saving [%]")
        ax.set_title("Sensitivity of fuel saving to part-power SFC coefficient\n"
                     r"$k_\mathrm{throttle}$ (Walsh & Fletcher, 2004)")
        ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
        fig.tight_layout()
        fig.savefig(figures_dir / "sensitivity_k_throttle.png", dpi=300, bbox_inches="tight")
        plt.close(fig)
