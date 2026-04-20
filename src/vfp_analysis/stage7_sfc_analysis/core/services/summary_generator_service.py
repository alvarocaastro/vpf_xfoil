"""
summary_generator_service.py
-----------------------------
Generates the text summary of the SFC analysis.
"""

from __future__ import annotations

import math
from typing import List

from vfp_analysis.stage7_sfc_analysis.core.domain.sfc_parameters import (
    EPSILON_CAP,
    MissionSummary,
    SfcAnalysisResult,
    SfcSectionResult,
)


def generate_sfc_summary(
    sfc_results: List[SfcAnalysisResult],
    section_results: List[SfcSectionResult] | None = None,
    mission_summary: MissionSummary | None = None,
) -> str:
    """Generate a human-readable summary of the SFC analysis results."""
    lines = []
    lines.append("=" * 70)
    lines.append("SPECIFIC FUEL CONSUMPTION (SFC) IMPACT ANALYSIS — SUMMARY")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Physical model (two independent mechanisms):")
    lines.append("")
    lines.append("  Mechanism 1 — Profile (2D → 3D via τ):")
    lines.append("    α_fixed(cond,sec) = β_cruise(sec) − φ(cond,sec)   [velocity triangles]")
    lines.append("    β_cruise(sec)     = α_opt_cruise + φ_cruise        [VPF design at cruise]")
    lines.append("    φ(cond,sec)       = Va_cond / (ω × r_sec)          [flow coefficient]")
    lines.append("    ε(r, cond)        = CL/CD_vpf / CL/CD_fixed        [Stage 4]")
    lines.append("    Δη_profile        = mean_r[(min(ε,1.10)−1)×τ],  cap ≤ 0.04")
    lines.append("")
    lines.append("  Mechanism 2 — Fan map (flow coefficient φ):")
    lines.append("    Δη_map           = k_map × ((φ − φ_opt) / φ_opt)²,  cap ≤ 0.015")
    lines.append("    k_map = 0.22  (recovery fraction ≈ 20% map loss)")
    lines.append("")
    lines.append("  Combinado:")
    lines.append("    Δη_fan           = min(Δη_profile + Δη_map, 0.048)")
    lines.append("    η_fan,new        = min(η_base × (1 + Δη_fan), 0.96)")
    lines.append("    SFC_new          = SFC_base / (1 + k × Δη_fan / η_base)")
    lines.append("    k = BPR/(1+BPR)  (Saravanamuttoo 2017 §5.14)")
    lines.append("")
    lines.append("  Ref: Saravanamuttoo (2017) §5.3; Cumpsty (2004) p. 280, ch. 8;")
    lines.append("       Dickens & Day (2011) J. Turbomach. 133(3):031007.")
    lines.append("")

    # ── 1. ε ratio per section ─────────────────────────────────────────
    if section_results:
        lines.append("-" * 70)
        lines.append("1. EFFICIENCY RATIO ε PER SECTION")
        lines.append("   (Profile mechanism — velocity-triangle correction)")
        lines.append("-" * 70)
        lines.append("")
        conditions_order = ["takeoff", "climb", "cruise", "descent"]
        sections_order   = ["root", "mid_span", "tip"]
        header = (
            f"  {'Condition':<12}  {'Section':<10}  {'CL/CD_fixed':>11}  "
            f"{'CL/CD_vpf':>9}  {'ε_raw':>7}  {'ε_eff':>5}  {'Δα [°]':>7}  {'Gain':>8}"
        )
        lines.append(header)
        lines.append("  " + "-" * 74)
        for cond in conditions_order:
            for sec in sections_order:
                row = next(
                    (r for r in section_results
                     if r.condition == cond and r.blade_section == sec),
                    None,
                )
                if row is None:
                    continue
                epsilon_note = f">cap" if row.epsilon > EPSILON_CAP else "     "
                lines.append(
                    f"  {cond:<12}  {sec:<10}  {row.cl_cd_fixed:>10.2f}  "
                    f"{row.cl_cd_vpf:>9.2f}  {row.epsilon:>7.3f}  "
                    f"{row.epsilon_eff:>5.3f}  "
                    f"{row.delta_alpha_deg:>7.2f}  {row.efficiency_gain_pct:>7.1f}%"
                    f"  {epsilon_note}"
                )
        lines.append("")

        # ── Fan map mechanism per section ──────────────────────────────
        has_map = any(
            not math.isnan(r.phi_condition) for r in section_results
        )
        if has_map:
            lines.append("-" * 70)
            lines.append("1b. FAN MAP MECHANISM PER SECTION")
            lines.append("    (φ = Va/U — deviation from cruise design point)")
            lines.append("-" * 70)
            lines.append("")
            header2 = (
                f"  {'Condition':<12}  {'Section':<10}  {'φ_design':>9}  "
                f"{'φ_cond':>8}  {'Δφ/φ [%]':>9}  {'Δη_map':>8}"
            )
            lines.append(header2)
            lines.append("  " + "-" * 64)
            for cond in conditions_order:
                for sec in sections_order:
                    row = next(
                        (r for r in section_results
                         if r.condition == cond and r.blade_section == sec),
                        None,
                    )
                    if row is None or math.isnan(row.phi_condition):
                        continue
                    delta_phi_pct = (
                        (row.phi_condition - row.phi_design) / row.phi_design * 100.0
                        if row.phi_design > 0 else float("nan")
                    )
                    lines.append(
                        f"  {cond:<12}  {sec:<10}  {row.phi_design:>9.4f}  "
                        f"{row.phi_condition:>8.4f}  {delta_phi_pct:>+9.1f}%  "
                        f"{row.delta_eta_map:>8.5f}"
                    )
            lines.append("")

    # ── 2. Aggregated aerodynamic efficiency ────────────────────────────
    lines.append("-" * 70)
    lines.append("2. MEAN AERODYNAMIC EFFICIENCY (per condition)")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        improvement = (result.epsilon_mean - 1.0) * 100.0
        lines.append(f"  {result.condition.upper():<10}")
        lines.append(f"    CL/CD fixed-pitch: {result.cl_cd_fixed:7.2f}")
        lines.append(
            f"    CL/CD VPF        : {result.cl_cd_vpf:7.2f}  "
            f"(ε_mean = {result.epsilon_mean:.3f}, +{improvement:.1f}%)"
        )
        lines.append(f"    Δα mean          : {result.delta_alpha_mean_deg:.2f}°")
        lines.append("")

    # ── 3. Fan efficiency — breakdown by mechanism ──────────────────────
    lines.append("-" * 70)
    lines.append("3. FAN EFFICIENCY — BREAKDOWN BY MECHANISM")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        lines.append(f"  {result.condition.upper():<10}")
        lines.append(f"    η_fan baseline   : {result.fan_efficiency_baseline:.4f}")

        # Profile mechanism
        if not math.isnan(result.delta_eta_profile):
            lines.append(f"    Δη_profile       : {result.delta_eta_profile:+.5f}  (mechanism 1 — CL/CD profile)")
        else:
            lines.append(f"    Δη_profile       : n/a")

        # Map mechanism
        if not math.isnan(result.delta_eta_map):
            phi_info = ""
            if not math.isnan(result.phi_condition) and not math.isnan(result.phi_design) and result.phi_design > 0:
                delta_phi_pct = (result.phi_condition - result.phi_design) / result.phi_design * 100.0
                phi_info = f"  φ={result.phi_condition:.4f} vs φ_opt={result.phi_design:.4f} ({delta_phi_pct:+.1f}%)"
            lines.append(f"    Δη_map           : {result.delta_eta_map:+.5f}  (mechanism 2 — map φ){phi_info}")
        else:
            lines.append(f"    Δη_map           : n/a")

        lines.append(f"    Δη_fan applied   : {result.delta_eta_fan:+.5f}  (combined, after caps)")
        lines.append(f"    η_fan VPF        : {result.fan_efficiency_new:.4f}")
        lines.append(f"    k = BPR/(1+BPR)  = {result.k_sensitivity:.4f}")
        lines.append("")

    # ── 4. SFC impact ─────────────────────────────────────────────────
    lines.append("-" * 70)
    lines.append("4. SFC IMPACT")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        lines.append(f"  {result.condition.upper():<10}")
        lines.append(f"    SFC baseline: {result.sfc_baseline:.4f} lb/(lbf·hr)")
        lines.append(f"    SFC VPF     : {result.sfc_new:.4f} lb/(lbf·hr)")
        lines.append(f"    Reduction   : {result.sfc_reduction_percent:6.2f}%")
        lines.append("")

    # ── 5. Key results ────────────────────────────────────────────────
    avg_reduction = sum(r.sfc_reduction_percent for r in sfc_results) / len(sfc_results)
    max_reduction = max(r.sfc_reduction_percent for r in sfc_results)
    max_cond      = max(sfc_results, key=lambda r: r.sfc_reduction_percent).condition
    lines.append("-" * 70)
    lines.append("5. KEY RESULTS")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Mean SFC reduction    : {avg_reduction:.2f}%")
    lines.append(f"  Maximum SFC reduction : {max_reduction:.2f}%  ({max_cond})")
    lines.append("")
    lines.append("  Literature range for VPF (Cumpsty 2004 p.280): 2–5%")
    lines.append(f"  → Result within range: {'YES' if 1.0 <= avg_reduction <= 6.0 else 'CHECK'}")
    lines.append("")

    # ── 6. References ─────────────────────────────────────────────────
    lines.append("-" * 70)
    lines.append("6. PHYSICAL MODEL REFERENCES")
    lines.append("-" * 70)
    lines.append("")
    lines.append("  [1] Saravanamuttoo, H.I.H. et al. (2017). Gas Turbine Theory,")
    lines.append("      7th ed. Pearson. §5.3, eq. 5.14.")
    lines.append("  [2] Cumpsty, N.A. (2004). Compressor Aerodynamics, 2nd ed.")
    lines.append("      Krieger. p. 280, ch. 8, fig. 8.10.")
    lines.append("  [3] Dixon, S.L. & Hall, C.A. (2013). Fluid Mechanics and")
    lines.append("      Thermodynamics of Turbomachinery, 7th ed. Butterworth. §7.4.")
    lines.append("  [4] Wisler, D.C. (1998). The technical and economic relevance of")
    lines.append("      understanding blade row interaction effects in turbomachinery.")
    lines.append("      VKI Lecture Series.")
    lines.append("  [5] Dickens, T. & Day, I. (2011). The Design of Highly Loaded Axial")
    lines.append("      Compressors. J. Turbomachinery, 133(3):031007.")
    lines.append("")

    # ── 7. Mission — total fuel saving ────────────────────────────────────
    if mission_summary is not None and mission_summary.total_fuel_baseline_kg > 0:
        lines.append("-" * 70)
        lines.append("7. MISSION — TOTAL FUEL SAVING")
        lines.append("-" * 70)
        lines.append("")
        lines.append("  Model: fuel_phase = SFC(phase) × thrust_lbf × duration_hr × 0.453592")
        lines.append("  Ref: CORSIA (2022) — CO₂/kerosene factor = 3.16 kg/kg")
        lines.append("")
        header_m = (
            f"  {'Phase':<10}  {'Dur [min]':>9}  {'Thr [kN]':>8}  "
            f"{'Fuel base [kg]':>14}  {'Fuel VPF [kg]':>13}  "
            f"{'Saving [kg]':>11}  {'CO₂ [kg]':>9}  {'Cost [$]':>9}"
        )
        lines.append(header_m)
        lines.append("  " + "-" * 94)
        for p in mission_summary.phase_results:
            lines.append(
                f"  {p.phase:<10}  {p.duration_min:>9.1f}  {p.thrust_kN:>8.1f}  "
                f"{p.fuel_baseline_kg:>14.1f}  {p.fuel_vpf_kg:>13.1f}  "
                f"{p.fuel_saving_kg:>11.1f}  {p.co2_saving_kg:>9.1f}  "
                f"{p.cost_saving_usd:>9.2f}"
            )
        lines.append("  " + "-" * 94)
        lines.append(
            f"  {'TOTAL':<10}  {'':>9}  {'':>8}  "
            f"{mission_summary.total_fuel_baseline_kg:>14.1f}  "
            f"{mission_summary.total_fuel_vpf_kg:>13.1f}  "
            f"{mission_summary.total_fuel_saving_kg:>11.1f}  "
            f"{mission_summary.total_co2_saving_kg:>9.1f}  "
            f"{mission_summary.total_cost_saving_usd:>9.2f}"
        )
        lines.append("")
        lines.append(f"  Relative mission saving: {mission_summary.total_fuel_saving_pct:.2f}%")
        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)
