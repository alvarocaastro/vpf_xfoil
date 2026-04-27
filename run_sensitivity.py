"""
run_sensitivity.py — VPF SFC sensitivity analysis.

Reads results already on disk (Stage 3 polars + Stage 4 summary table) and
sweeps two independent parameters:

  tau           : 2D-to-3D profile efficiency transfer coefficient [0.30 – 0.80]
  rpm_delta_pct : Fan RPM deviation from design point [−10 % – +10 %]

For each (tau, rpm_delta) point the script re-computes the fixed-pitch flow
angle phi, derives the incidence at fixed blade angle (alpha_fixed), looks up
the CL/CD from the Stage 3 corrected polars, and evaluates the SFC improvement.

Outputs
-------
  results/sensitivity/sensitivity_table.csv   — full results grid
  results/sensitivity/sensitivity_heatmap.png — ΔSFC% as 2D heatmap
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vpf_analysis import settings as base_config
from vpf_analysis.settings import get_settings
from vpf_analysis.shared.plot_style import apply_style
from vpf_analysis.stage7_sfc_analysis.sfc_core import (
    compute_combined_fan_efficiency_improvement,
    compute_sfc_improvement,
    compute_sfc_reduction_percent,
)

# ── Parameter grids ───────────────────────────────────────────────────────────

TAU_VALUES      = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
RPM_DELTA_PCT   = [-10.0, -7.5, -5.0, -2.5, 0.0, 2.5, 5.0, 7.5, 10.0]

# Engine baseline (from engine_parameters.yaml defaults)
SFC_BASELINE         = 0.49   # lb/(lbf·hr)
ETA_FAN_BASELINE     = 0.90
PHI_DESIGN_MIDSPAN   = 0.43   # Va_cruise / U_mid_cruise ≈ 150 / 347 (design point)


def _load_corrected_polar(stage3_dir: Path, flight: str, section: str) -> pd.DataFrame | None:
    path = stage3_dir / flight / section / "corrected_polar.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    eff_col = "ld_corrected" if "ld_corrected" in df.columns else "ld_kt"
    if eff_col not in df.columns:
        return None
    df = df[["alpha", eff_col]].replace([np.inf, -np.inf], np.nan).dropna().sort_values("alpha")
    df = df.rename(columns={eff_col: "ld"})
    return df


def _lookup_ld(df: pd.DataFrame, alpha_deg: float) -> float | None:
    """Interpolate CL/CD from corrected polar at a given alpha."""
    if df is None or len(df) < 2:
        return None
    alpha_arr = df["alpha"].to_numpy()
    ld_arr    = df["ld"].to_numpy()
    if alpha_deg < alpha_arr[0] or alpha_deg > alpha_arr[-1]:
        return None
    return float(np.interp(alpha_deg, alpha_arr, ld_arr))


def _compute_sensitivity_row(
    summary: pd.DataFrame,
    polars: dict[tuple[str, str], pd.DataFrame | None],
    cfg,
    rpm_delta_pct: float,
    tau: float,
) -> float:
    """Return mean ΔSFC% for a given (rpm_delta, tau) combination."""
    omega_ref = cfg.fan.rpm * (2.0 * math.pi / 60.0)
    omega_new = omega_ref * (1.0 + rpm_delta_pct / 100.0)

    # Cruise reference: compute β_cruise per section from summary (alpha_opt at cruise + φ_cruise)
    cruise_rows = summary[summary["flight_condition"] == "cruise"]
    beta_cruise: dict[str, float] = {}
    for _, row in cruise_rows.iterrows():
        section = str(row["blade_section"])
        alpha_opt_cruise = float(row["alpha_opt_deg"])
        r = cfg.fan.radii_m.get(section, 1.0)
        va_cruise = cfg.fan.axial_velocity_m_s.get("cruise", 150.0)
        u_cruise = omega_ref * r
        phi_cruise = math.degrees(math.atan2(va_cruise, u_cruise))
        beta_cruise[section] = alpha_opt_cruise + phi_cruise

    epsilon_vals: list[float] = []

    for _, row in summary.iterrows():
        flight  = str(row["flight_condition"])
        section = str(row["blade_section"])
        max_ld  = float(row["max_efficiency"])

        if flight == "cruise":
            epsilon_vals.append(1.0)
            continue

        r  = cfg.fan.radii_m.get(section, 1.0)
        va = cfg.fan.axial_velocity_m_s.get(flight, 150.0)
        u_new   = omega_new * r
        phi_new = math.degrees(math.atan2(va, u_new))

        bc = beta_cruise.get(section)
        if bc is None:
            epsilon_vals.append(1.0)
            continue
        alpha_fixed_new = bc - phi_new

        polar_df = polars.get((flight, section))
        ld_fixed = _lookup_ld(polar_df, alpha_fixed_new)
        if ld_fixed is None or ld_fixed <= 0:
            epsilon_vals.append(1.0)
            continue

        eps = max_ld / ld_fixed
        epsilon_vals.append(eps)

    if not epsilon_vals:
        return 0.0

    eta_new, *_ = compute_combined_fan_efficiency_improvement(
        epsilon_values=epsilon_vals,
        phi_values=[PHI_DESIGN_MIDSPAN],
        phi_design=PHI_DESIGN_MIDSPAN,
        fan_efficiency_baseline=ETA_FAN_BASELINE,
        tau=tau,
    )
    delta_eta = eta_new - ETA_FAN_BASELINE
    sfc_new   = compute_sfc_improvement(SFC_BASELINE, delta_eta, ETA_FAN_BASELINE)
    return compute_sfc_reduction_percent(SFC_BASELINE, sfc_new)


def main() -> None:
    cfg = get_settings()
    stage3_dir  = base_config.get_stage_dir(3)
    stage4_dir  = base_config.get_stage_dir(4)
    summary_csv = stage4_dir / "tables" / "summary_table.csv"
    out_dir     = base_config.RESULTS_DIR / "sensitivity"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not summary_csv.exists():
        print(f"ERROR: {summary_csv} not found. Run the full pipeline first.")
        sys.exit(1)

    summary = pd.read_csv(summary_csv)

    # Pre-load corrected polars from disk
    polars: dict[tuple[str, str], pd.DataFrame | None] = {}
    for flight in cfg.flight_conditions:
        for section in cfg.blade_sections:
            polars[(flight, section)] = _load_corrected_polar(stage3_dir, flight, section)

    # ── Sweep ─────────────────────────────────────────────────────────────────
    rows: list[dict] = []
    for rpm_delta in RPM_DELTA_PCT:
        for tau in TAU_VALUES:
            sfc_red = _compute_sensitivity_row(summary, polars, cfg, rpm_delta, tau)
            rows.append({"rpm_delta_pct": rpm_delta, "tau": tau, "sfc_reduction_pct": sfc_red})

    df_out = pd.DataFrame(rows)
    csv_path = out_dir / "sensitivity_table.csv"
    df_out.to_csv(csv_path, index=False, float_format="%.4f")
    print(f"Saved: {csv_path}")

    # ── Heatmap ───────────────────────────────────────────────────────────────
    pivot = df_out.pivot(index="tau", columns="rpm_delta_pct", values="sfc_reduction_pct")

    with apply_style():
        fig, ax = plt.subplots(figsize=(10.0, 5.5))

        Z = pivot.values
        vmin, vmax = float(Z.min()), float(Z.max())
        cmap = "RdYlGn"

        im = ax.imshow(
            Z, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax,
            origin="lower",
        )

        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels([f"{v:+.1f}%" for v in pivot.columns], fontsize=9)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([f"{v:.2f}" for v in pivot.index], fontsize=9)
        ax.set_xlabel("RPM deviation from design point")
        ax.set_ylabel("Profile efficiency transfer coefficient τ")
        ax.set_title("VPF SFC reduction sensitivity — ΔSFC% = f(τ, ΔRPM)",
                     fontweight="bold")

        cbar = fig.colorbar(im, ax=ax, pad=0.02)
        cbar.set_label("ΔSFC (%)", fontsize=10)

        # Annotate cells
        for i in range(Z.shape[0]):
            for j in range(Z.shape[1]):
                val = Z[i, j]
                text_color = "white" if val < (vmin + 0.4 * (vmax - vmin)) else "black"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=7, color=text_color)

        fig.savefig(out_dir / "sensitivity_heatmap.png", bbox_inches="tight")
        plt.close(fig)
        print(f"Saved: {out_dir / 'sensitivity_heatmap.png'}")

    # ── Summary ───────────────────────────────────────────────────────────────
    baseline_row = df_out[(df_out["rpm_delta_pct"] == 0.0) & (df_out["tau"] == 0.50)]
    if not baseline_row.empty:
        baseline_val = float(baseline_row["sfc_reduction_pct"].iloc[0])
        print(f"\nBaseline (τ=0.50, ΔRPM=0%): ΔSFC = {baseline_val:.2f}%")
    print(f"Range across all parameters:   ΔSFC ∈ [{df_out['sfc_reduction_pct'].min():.2f}%, "
          f"{df_out['sfc_reduction_pct'].max():.2f}%]")


if __name__ == "__main__":
    main()
