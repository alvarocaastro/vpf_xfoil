"""
run_reverse_thrust.py
---------------------
Stage 6: VPF Reverse Thrust — BEM pitch sweep + mechanism weight analysis.

The variable-pitch fan reverses thrust by rotating blades to negative pitch angles,
redirecting fan airflow to produce braking force without cascade blocker doors.

Two analyses are performed:
  1. Mechanism weight — quantifies VPF actuator vs conventional cascade reverser.
  2. BEM pitch sweep — Blade Element Method with Viterna-Corrigan extrapolation
     to estimate reverse thrust as a function of pitch offset Δβ.

Inputs:
    config/engine_parameters.yaml           (reverse_thrust section)
    results/stage5_pitch_kinematics/tables/ (blade_twist_design.csv, kinematics_analysis.csv)
    results/stage3_compressibility_correction/{condition}/{section}/corrected_polar.csv

Outputs (results/stage6_reverse_thrust/):
    tables/mechanism_weight.csv       — VPF vs cascade reverser weight + SFC
    tables/bem_sweep.csv              — BEM pitch sweep results
    figures/mechanism_weight_comparison.png
    figures/bem_sweep.png             — Thrust fraction vs Δβ
    reverse_thrust_summary.txt
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml

from vpf_analysis import settings as base_config
from vpf_analysis.stage6_reverse_thrust.adapters.filesystem.results_writer import (
    ReverseResultsWriter,
)
from vpf_analysis.stage6_reverse_thrust.reverse_thrust_core import (
    ReverseOptimalResult,
    compute_mechanism_weight,
    compute_reverse_kinematics,
    compute_reverse_sweep,
    select_optimal_point,
)

LOGGER = logging.getLogger(__name__)

_ISA_SEA_LEVEL_RHO: float = 1.225  # [kg/m³] — landing rollout is at sea level


def _load_reverse_config() -> dict:
    cfg_path = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)
    if "reverse_thrust" not in cfg:
        raise KeyError("engine_parameters.yaml missing 'reverse_thrust' section")
    return cfg


def _load_polar_for_section(
    stage3_dir: Path,
    section: str,
    preferred_condition: str = "descent",
    fallback_condition: str = "takeoff",
) -> Optional[pd.DataFrame]:
    """Load Stage 3 corrected polar for BEM; tries descent then takeoff as fallback.

    Returns a DataFrame with at minimum columns [alpha, cl_kt, cd_corrected].
    If Stage 3 corrected polar is not found (e.g. tip was skipped as supersonic),
    falls back to the Stage 2 raw polar and renames columns for BEM compatibility.
    """
    for cond in (preferred_condition, fallback_condition):
        path = stage3_dir / cond.lower() / section / "corrected_polar.csv"
        if path.is_file():
            df = pd.read_csv(path)
            if "cl_kt" in df.columns and "cd_corrected" in df.columns:
                LOGGER.info("BEM polar loaded: %s/%s from Stage 3 (%s)", section, section, cond)
                return df[["alpha", "cl_kt", "cd_corrected"]].dropna()

    # Stage 3 missing — try Stage 2 raw polar
    s2_base = base_config.get_stage_dir(2).parent / "stage2_xfoil_simulations"
    for cond in (preferred_condition, fallback_condition):
        path = s2_base / "simulation_plots" / cond.lower() / section / "polar.csv"
        if path.is_file():
            df = pd.read_csv(path)
            if "cl" in df.columns and "cd" in df.columns:
                LOGGER.warning(
                    "BEM: Stage 3 polar not found for %s — using raw Stage 2 polar (%s). "
                    "Compressibility correction absent.",
                    section, cond,
                )
                df = df[["alpha", "cl", "cd"]].dropna().copy()
                df.rename(columns={"cl": "cl_kt", "cd": "cd_corrected"}, inplace=True)
                return df

    LOGGER.warning("BEM: no polar found for section=%s — section excluded from BEM.", section)
    return None


def _build_chord_map() -> dict[str, float]:
    """Derive chord [m] from solidity: c = σ · 2π · r / Z."""
    from vpf_analysis.config_loader import get_blade_geometry, get_blade_radii
    bg = get_blade_geometry()
    radii = get_blade_radii()
    Z = bg["num_blades"]
    return {
        sec: bg["solidity"][sec] * 2.0 * math.pi * radii[sec] / Z
        for sec in bg["solidity"]
    }


def run_reverse_thrust() -> None:
    """Execute Stage 6: mechanism weight + BEM reverse thrust pitch sweep."""
    LOGGER.info("=" * 60)
    LOGGER.info("Stage 6: VPF Reverse Thrust — BEM + Weight Analysis")
    LOGGER.info("=" * 60)

    cfg     = _load_reverse_config()
    rt_cfg  = cfg["reverse_thrust"]
    mission = cfg.get("mission", {})
    phases  = mission.get("phases", {})

    out_dir = base_config.get_stage_dir(6)
    out_dir.mkdir(parents=True, exist_ok=True)

    design_thrust_kN      = float(mission.get("design_thrust_kN", 467.0))
    cruise_thrust_fraction = float(phases.get("cruise", {}).get("thrust_fraction", 0.25))

    # ── 1. Mechanism weight ──────────────────────────────────────────────────
    mechanism_weight = compute_mechanism_weight(
        engine_dry_weight_kg=float(rt_cfg["engine_dry_weight_kg"]),
        mechanism_weight_fraction=float(rt_cfg["mechanism_weight_fraction"]),
        conventional_reverser_fraction=float(rt_cfg["conventional_reverser_fraction"]),
        design_thrust_kN=design_thrust_kN,
        cruise_thrust_fraction=cruise_thrust_fraction,
        aircraft_L_D=float(rt_cfg["aircraft_L_D"]),
    )

    LOGGER.info(
        "Mechanism weight: %.0f kg | saving vs cascade: %.0f kg | "
        "SFC penalty: +%.3f%% | SFC benefit vs cascade: -%.3f%%",
        mechanism_weight.mechanism_weight_kg,
        mechanism_weight.weight_saving_vs_conventional_kg,
        mechanism_weight.sfc_cruise_penalty_pct,
        mechanism_weight.sfc_benefit_vs_conventional_pct,
    )

    # ── 2. BEM pitch sweep (conditional on Stage 5 data) ────────────────────
    bem_result: Optional[ReverseOptimalResult] = None
    sweep_df: Optional[pd.DataFrame] = None

    stage5_dir = base_config.get_stage_dir(5)
    stage3_dir = base_config.get_stage_dir(3)
    blade_twist_path = stage5_dir / "tables" / "blade_twist_design.csv"

    if blade_twist_path.is_file():
        try:
            blade_twist_df = pd.read_csv(blade_twist_path)
            chord_map = _build_chord_map()

            # Load descent polars for each section (best approximation of landing condition)
            polar_map: dict[str, pd.DataFrame] = {}
            for section in ("root", "mid_span", "tip"):
                df_pol = _load_polar_for_section(stage3_dir, section)
                if df_pol is not None and len(df_pol) >= 5:
                    polar_map[section] = df_pol

            if len(polar_map) < 2:
                LOGGER.warning(
                    "Fewer than 2 sections have valid polars (%d found) — BEM skipped.",
                    len(polar_map),
                )
            else:
                kinematics = compute_reverse_kinematics(
                    blade_twist_df=blade_twist_df,
                    chord_map=chord_map,
                    n1_fraction=float(rt_cfg["n1_fraction"]),
                    va_landing_m_s=float(rt_cfg["va_landing_m_s"]),
                )

                delta_betas = np.linspace(
                    float(rt_cfg["delta_beta_min_deg"]),
                    float(rt_cfg["delta_beta_max_deg"]),
                    int(rt_cfg["delta_beta_steps"]),
                )

                from vpf_analysis.config_loader import get_blade_geometry
                n_blades = get_blade_geometry()["num_blades"]

                sweep, _omega_rev = compute_reverse_sweep(
                    kinematics=kinematics,
                    blade_twist_df=blade_twist_df,
                    polar_map=polar_map,
                    delta_beta_values=delta_betas,
                    rho=_ISA_SEA_LEVEL_RHO,
                    n_blades=n_blades,
                    t_forward_takeoff_kN=design_thrust_kN,
                    stall_margin_min_threshold=0.0,
                )

                if sweep:
                    bem_result = select_optimal_point(
                        sweep=sweep,
                        target_thrust_fraction=float(rt_cfg["target_thrust_fraction"]),
                        n1_fraction=float(rt_cfg["n1_fraction"]),
                        va_landing_m_s=float(rt_cfg["va_landing_m_s"]),
                    )
                    LOGGER.info(
                        "BEM optimal: Δβ=%.1f°, T=%.1f kN, fraction=%.1f%%, valid=%s",
                        bem_result.delta_beta_opt_deg,
                        bem_result.thrust_net_kN,
                        bem_result.thrust_fraction * 100.0,
                        bem_result.aerodynamically_valid,
                    )

                    # Save sweep table
                    tables_dir = out_dir / "tables"
                    tables_dir.mkdir(parents=True, exist_ok=True)
                    sweep_records = [
                        {
                            "delta_beta_deg": p.delta_beta_deg,
                            "thrust_kN": p.thrust_kN,
                            "thrust_fraction": p.thrust_fraction,
                            "eta_fan_rev": p.eta_fan_rev,
                            "stall_margin_min": p.stall_margin_min,
                            "aerodynamically_valid": p.aerodynamically_valid,
                            "alpha_rev_root_deg": p.alpha_rev_root_deg,
                            "alpha_rev_mid_deg": p.alpha_rev_mid_deg,
                            "alpha_rev_tip_deg": p.alpha_rev_tip_deg,
                        }
                        for p in sweep
                    ]
                    sweep_df = pd.DataFrame(sweep_records)
                    sweep_df.to_csv(tables_dir / "bem_sweep.csv", index=False, float_format="%.4f")
                    LOGGER.info("BEM sweep table saved (%d points).", len(sweep))

        except Exception as exc:
            LOGGER.warning("BEM analysis failed: %s — mechanism weight only.", exc, exc_info=True)
    else:
        LOGGER.warning(
            "Stage 5 blade twist not found (%s). BEM skipped — run Stage 5 first.",
            blade_twist_path,
        )

    # ── 3. Write standard outputs ────────────────────────────────────────────
    writer = ReverseResultsWriter(out_dir)
    writer.write_mechanism_weight(mechanism_weight)
    writer.write_figures(mechanism_weight)

    if sweep_df is not None:
        _plot_bem_sweep(sweep_df, out_dir / "figures", float(rt_cfg["target_thrust_fraction"]))

    _write_summary(out_dir, mechanism_weight, bem_result)
    LOGGER.info("Stage 6 complete. Outputs: %s", out_dir)


def _plot_bem_sweep(
    sweep_df: pd.DataFrame,
    figures_dir: Path,
    target_thrust_fraction: float,
) -> None:
    try:
        import matplotlib.pyplot as plt
        from vpf_analysis.shared.plot_style import apply_style

        figures_dir.mkdir(parents=True, exist_ok=True)
        with apply_style():
            fig, ax = plt.subplots(figsize=(6.5, 4.2))
            mask_valid = sweep_df["aerodynamically_valid"]
            ax.plot(
                sweep_df["delta_beta_deg"], sweep_df["thrust_fraction"] * 100.0,
                color="#AAAAAA", linewidth=1.4, linestyle="--", label="All points",
            )
            ax.plot(
                sweep_df.loc[mask_valid, "delta_beta_deg"],
                sweep_df.loc[mask_valid, "thrust_fraction"] * 100.0,
                color="#4477AA", linewidth=2.2, label="Aerodynamically valid",
            )
            ax.axhline(
                target_thrust_fraction * 100.0,
                color="#EE6677", linewidth=1.6, linestyle="--",
                label=f"Target {target_thrust_fraction*100:.0f}% forward thrust",
            )
            ax.set_xlabel(r"Pitch offset $\Delta\beta$ [°]")
            ax.set_ylabel("Reverse thrust fraction [%]")
            ax.set_title("VPF BEM reverse thrust sweep")
            ax.legend(loc="upper right")
            fig.tight_layout()
            fig.savefig(figures_dir / "bem_sweep.png")
            plt.close(fig)
    except Exception as exc:
        LOGGER.warning("BEM sweep plot failed: %s", exc)


def _write_summary(
    out_dir: Path,
    mw: object,
    bem: Optional[ReverseOptimalResult] = None,
) -> None:
    lines = [
        "Stage 6 — VPF Reverse Thrust: BEM + Theoretical Analysis",
        "=" * 58,
        "",
        "CONCEPT",
        "  Variable-pitch fans reverse thrust by rotating blades to negative",
        "  pitch angles during landing rollout. This eliminates cascade reverser",
        "  doors, blocker doors, and nacelle structural reinforcement.",
        "",
    ]

    if bem is not None:
        target_met = bem.thrust_fraction >= 0.40
        lines += [
            "BEM PITCH SWEEP RESULTS (Viterna-Corrigan extrapolation)",
            f"  Optimal pitch offset:   Δβ = {bem.delta_beta_opt_deg:.1f}°",
            f"  Net reverse thrust:     {abs(bem.thrust_net_kN):.1f} kN  "
            f"({bem.thrust_fraction*100:.1f}% of forward takeoff thrust)",
            f"  Fan reverse efficiency: {bem.eta_fan_rev*100:.1f}%",
            f"  Stall margin (min):     {bem.stall_margin_min:.2f}",
            f"  Aerodynamically valid:  {'YES' if bem.aerodynamically_valid else 'NO'}",
            f"  Target thrust met:      {'YES ≥40%' if target_met else 'NO <40%'}",
            "",
            "  Note: BEM uses Viterna-Corrigan (1982) extrapolation for α < −5°.",
            "  Full validation requires wind tunnel data at high negative incidence.",
            "",
        ]
    else:
        lines += [
            "BEM PITCH SWEEP",
            "  BEM analysis not executed (Stage 5 blade twist data not available).",
            "  Aerodynamic performance at α ≈ −15° to −20° requires Viterna-Corrigan",
            "  extrapolation and wind tunnel validation for quantitative results.",
            "",
        ]

    lines += [
        "MECHANISM WEIGHT",
        f"  VPF mechanism (both engines):  {mw.mechanism_weight_kg:.0f} kg",
        f"  Cascade reverser equivalent:   {mw.conventional_reverser_weight_kg:.0f} kg",
        f"  Weight saving vs cascade:      {mw.weight_saving_vs_conventional_kg:.0f} kg",
        "",
        "SFC IMPACT AT CRUISE",
        f"  Penalty vs no reverser:        +{mw.sfc_cruise_penalty_pct:.3f}%",
        f"  Benefit vs cascade reverser:   -{mw.sfc_benefit_vs_conventional_pct:.3f}%",
        "",
        "CONCLUSION",
        "  The VPF pitch mechanism adds weight (+SFC penalty) but eliminates the",
        "  cascade reverser, blocker doors and nacelle reinforcement. Net balance",
        f"  vs a conventional reverser: {mw.weight_saving_vs_conventional_kg:.0f} kg saved,",
        f"  {mw.sfc_benefit_vs_conventional_pct:.3f}% SFC improvement at cruise.",
        "",
        "References:",
        "  - Cumpsty & Heyes, Jet Propulsion, Cambridge (2015)",
        "  - Walsh & Fletcher, Gas Turbine Performance, Blackwell (2004)",
        "  - Butterfield et al., Variable-pitch fans for turbofan thrust reversal,",
        "    ASME Turbo Expo GT2004-53713",
        "  - Viterna & Corrigan (1982), Fixed Pitch Rotor Performance of Large HAWT,",
        "    DOE/NASA Workshop, NASA CP-2230",
    ]
    (out_dir / "reverse_thrust_summary.txt").write_text("\n".join(lines), encoding="utf-8")
