"""
run_reverse_thrust.py
---------------------
Orchestrator for Stage 6: VPF Reverse Thrust Modeling.

Execution chain:
  1. Load Stage 5 blade twist + Stage 3 takeoff polars
  2. Compute reverse-mode velocity triangles (N1_fraction × design RPM)
  3. BEM pitch sweep: delta_beta in [delta_beta_min, delta_beta_max]
  4. Select optimal operating point (target thrust fraction ~40%)
  5. Compute VPF mechanism weight and cruise SFC penalty
  6. Write 4 CSV tables + 4 PNG figures + summary text

Inputs:
    results/stage5_pitch_kinematics/tables/blade_twist_design.csv
    results/stage3_compressibility_correction/takeoff/{section}/corrected_polar.csv
    config/engine_parameters.yaml  (reverse_thrust section)

Outputs (results/stage6_reverse_thrust/):
    tables/reverse_kinematics.csv      — velocity triangles per section
    tables/reverse_thrust_sweep.csv    — full beta sweep (T, η, stall margin)
    tables/reverse_thrust_optimal.csv  — optimal operating point
    tables/mechanism_weight.csv        — weight and SFC impact
    figures/thrust_vs_pitch_sweep.png
    figures/efficiency_and_stall_margin.png
    figures/spanwise_thrust_at_optimum.png
    figures/mechanism_weight_comparison.png
    reverse_thrust_summary.txt
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import yaml

from vfp_analysis import config as base_config
from vfp_analysis.stage6_reverse_thrust.adapters.filesystem.data_loader import (
    ReverseDataLoader,
)
from vfp_analysis.stage6_reverse_thrust.adapters.filesystem.results_writer import (
    ReverseResultsWriter,
)
from vfp_analysis.stage6_reverse_thrust.core.services.mechanism_weight_service import (
    compute_mechanism_weight,
)
from vfp_analysis.stage6_reverse_thrust.core.services.reverse_kinematics_service import (
    compute_reverse_kinematics,
)
from vfp_analysis.stage6_reverse_thrust.core.services.reverse_thrust_service import (
    compute_reverse_sweep,
    select_optimal_point,
)

LOGGER = logging.getLogger(__name__)


def _load_reverse_config() -> dict:
    """Load engine_parameters.yaml and return the reverse_thrust sub-dict."""
    cfg_path = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    with cfg_path.open() as f:
        cfg = yaml.safe_load(f)
    if "reverse_thrust" not in cfg:
        raise KeyError("engine_parameters.yaml missing 'reverse_thrust' section")
    return cfg


def run_reverse_thrust() -> None:
    """Execute Stage 6 reverse thrust analysis and write all outputs."""
    LOGGER.info("=" * 60)
    LOGGER.info("Stage 6: VPF Reverse Thrust Modeling")
    LOGGER.info("=" * 60)

    cfg     = _load_reverse_config()
    rt_cfg  = cfg["reverse_thrust"]
    mission = cfg.get("mission", {})
    phases  = mission.get("phases", {})

    # Output directory
    out_dir = base_config.get_stage_dir(6)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Input directories
    stage5_dir = base_config.get_stage_dir(5)
    stage3_dir = base_config.get_stage_dir(3)

    # ------------------------------------------------------------------
    # 1. Load data
    # ------------------------------------------------------------------
    loader = ReverseDataLoader(stage5_dir=stage5_dir, stage3_dir=stage3_dir)
    blade_twist_df = loader.load_blade_twist()
    polar_map      = loader.load_polars_takeoff()

    LOGGER.info("Loaded blade twist for %d sections, polars for sections: %s",
                len(blade_twist_df), list(polar_map.keys()))

    # ------------------------------------------------------------------
    # 2. Velocity triangles in reverse
    # ------------------------------------------------------------------
    chord_map: dict[str, float] = rt_cfg.get("chord_m", {
        "root": 0.36, "mid_span": 0.46, "tip": 0.46,
    })
    kinematics = compute_reverse_kinematics(
        blade_twist_df=blade_twist_df,
        chord_map=chord_map,
        n1_fraction=float(rt_cfg["n1_fraction"]),
        va_landing_m_s=float(rt_cfg["va_landing_m_s"]),
    )
    for k in kinematics:
        LOGGER.info("  %s: phi_rev=%.1f°, U_rev=%.1f m/s, W_rel=%.1f m/s",
                    k.section, k.phi_rev_deg, k.u_rev_m_s, k.w_rel_m_s)

    # ------------------------------------------------------------------
    # 3. BEM pitch sweep
    # ------------------------------------------------------------------
    delta_beta_values = np.linspace(
        float(rt_cfg["delta_beta_min_deg"]),
        float(rt_cfg["delta_beta_max_deg"]),
        int(rt_cfg["delta_beta_steps"]),
    )

    design_thrust_kN = float(mission.get("design_thrust_kN", 105.0))

    sweep, omega_rev = compute_reverse_sweep(
        kinematics=kinematics,
        blade_twist_df=blade_twist_df,
        polar_map=polar_map,
        delta_beta_values=delta_beta_values,
        rho=float(rt_cfg["rho_sl_kg_m3"]),
        n_blades=int(rt_cfg["n_blades"]),
        t_forward_takeoff_kN=design_thrust_kN,
        stall_margin_min_threshold=float(rt_cfg["stall_margin_min"]),
    )
    LOGGER.info("Sweep complete: %d points, reverse thrust achieved at %d/%d points",
                len(sweep),
                sum(1 for p in sweep if p.thrust_kN < 0),
                len(sweep))

    # ------------------------------------------------------------------
    # 4. Optimal point
    # ------------------------------------------------------------------
    optimal = select_optimal_point(
        sweep=sweep,
        target_thrust_fraction=float(rt_cfg["target_thrust_fraction"]),
        n1_fraction=float(rt_cfg["n1_fraction"]),
        va_landing_m_s=float(rt_cfg["va_landing_m_s"]),
    )
    LOGGER.info(
        "Optimal: Δβ=%.1f°, T_rev=%.1f kN (%.1f%% of fwd), η_fan=%.3f, "
        "stall_margin=%.2f, valid=%s",
        optimal.delta_beta_opt_deg,
        optimal.thrust_net_kN,
        optimal.thrust_fraction * 100,
        optimal.eta_fan_rev,
        optimal.stall_margin_min,
        optimal.aerodynamically_valid,
    )

    # ------------------------------------------------------------------
    # 5. Mechanism weight and SFC impact
    # ------------------------------------------------------------------
    cruise_thrust_fraction = float(
        phases.get("cruise", {}).get("thrust_fraction", 0.25)
    )
    mechanism_weight = compute_mechanism_weight(
        engine_dry_weight_kg=float(rt_cfg["engine_dry_weight_kg"]),
        mechanism_weight_fraction=float(rt_cfg["mechanism_weight_fraction"]),
        conventional_reverser_fraction=float(rt_cfg["conventional_reverser_fraction"]),
        design_thrust_kN=design_thrust_kN,
        cruise_thrust_fraction=cruise_thrust_fraction,
        aircraft_L_D=float(rt_cfg["aircraft_L_D"]),
    )
    LOGGER.info(
        "Mechanism weight: %.0f kg (both engines) | saving vs conventional: %.0f kg | "
        "SFC penalty: +%.3f%% | SFC benefit vs cascade: -%.3f%%",
        mechanism_weight.mechanism_weight_kg,
        mechanism_weight.weight_saving_vs_conventional_kg,
        mechanism_weight.sfc_cruise_penalty_pct,
        mechanism_weight.sfc_benefit_vs_conventional_pct,
    )

    # ------------------------------------------------------------------
    # 6. Write outputs
    # ------------------------------------------------------------------
    writer = ReverseResultsWriter(out_dir)
    writer.write_kinematics(kinematics)
    writer.write_sweep(sweep)
    writer.write_optimal(optimal)
    writer.write_mechanism_weight(mechanism_weight)
    writer.write_figures(sweep, optimal, kinematics, mechanism_weight, design_thrust_kN)

    # Text summary
    _write_summary(out_dir, optimal, mechanism_weight, design_thrust_kN)

    LOGGER.info("Stage 6 complete. Outputs: %s", out_dir)


def _write_summary(
    out_dir: Path,
    opt: "ReverseOptimalResult",
    mw: "MechanismWeightResult",
    t_forward_kN: float,
) -> None:
    from vfp_analysis.stage6_reverse_thrust.core.domain.reverse_thrust_result import (
        MechanismWeightResult, ReverseOptimalResult,
    )
    lines = [
        "Stage 6 — VPF Reverse Thrust Modeling",
        "=" * 50,
        "",
        "OPTIMAL REVERSE THRUST OPERATING POINT",
        f"  Delta beta (from beta_metal):  {opt.delta_beta_opt_deg:+.1f}°",
        f"  Blade angle root:              {opt.beta_opt_root_deg:.1f}°",
        f"  Blade angle mid-span:          {opt.beta_opt_mid_deg:.1f}°",
        f"  Blade angle tip:               {opt.beta_opt_tip_deg:.1f}°",
        f"  Net reverse thrust:            {opt.thrust_net_kN:.1f} kN",
        f"  vs forward takeoff thrust:     {opt.thrust_fraction*100:.1f}%  (target: ~40%)",
        f"  Fan efficiency (reverse):      {opt.eta_fan_rev:.3f}",
        f"  N1 fraction:                   {opt.n1_fraction*100:.0f}%",
        f"  Axial landing speed:           {opt.va_landing_m_s:.0f} m/s",
        f"  Min stall margin:              {opt.stall_margin_min:+.2f}",
        f"  Aerodynamically valid:         {opt.aerodynamically_valid}",
        *(
            [
                "",
                "  WARNING — INFEASIBLE POINT: no Δβ in the sweep satisfies stall_margin ≥ 0",
                "  simultaneously with net reverse thrust. The reported point is the closest",
                "  to the target (40%) among points with T_rev < 0.",
                "  Likely cause: Stage 3 XFOIL polars do not cover very negative α",
                "  (current range α_min = -5°). For reversal analysis it would be necessary",
                "  to extend the polar to α ∈ [-25°, +5°] or use wind tunnel data.",
                "  The mechanism weight analysis and SFC impact are independent",
                "  of this result and remain valid.",
            ]
            if not opt.aerodynamically_valid
            else []
        ),
        "",
        "MECHANISM WEIGHT",
        f"  VPF mechanism (both engines):  {mw.mechanism_weight_kg:.0f} kg",
        f"  Cascade reverser equivalent:   {mw.conventional_reverser_weight_kg:.0f} kg",
        f"  Weight saving vs cascade:      {mw.weight_saving_vs_conventional_kg:.0f} kg",
        "",
        "SFC IMPACT AT CRUISE",
        f"  Penalty vs no reverser:        +{mw.sfc_cruise_penalty_pct:.3f}%",
        f"  Benefit vs cascade reverser:   −{mw.sfc_benefit_vs_conventional_pct:.3f}%",
        "",
        "NOTE: Although the VPF mechanism adds weight (+SFC penalty), it eliminates",
        "the cascade reverser, blocker doors and nacelle reinforcement. The net balance",
        f"vs a conventional reverser system is a saving of {mw.weight_saving_vs_conventional_kg:.0f} kg",
        f"and a cruise SFC improvement of {mw.sfc_benefit_vs_conventional_pct:.3f}%.",
    ]
    path = out_dir / "reverse_thrust_summary.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
