"""
summary_generator_service.py
-----------------------------
Genera el resumen de texto del análisis de SFC.
"""

from __future__ import annotations

import math
from typing import List

from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import (
    EPSILON_CAP,
    SfcAnalysisResult,
    SfcSectionResult,
)


def generate_sfc_summary(
    sfc_results: List[SfcAnalysisResult],
    section_results: List[SfcSectionResult] | None = None,
) -> str:
    """Genera un resumen legible de los resultados del análisis de SFC."""
    lines = []
    lines.append("=" * 70)
    lines.append("SPECIFIC FUEL CONSUMPTION (SFC) IMPACT ANALYSIS — SUMMARY")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Modelo físico (dos mecanismos independientes):")
    lines.append("")
    lines.append("  Mecanismo 1 — Perfil (2D → 3D vía τ):")
    lines.append("    α_fijo(cond,sec) = β_crucero(sec) − φ(cond,sec)   [triángulos de velocidad]")
    lines.append("    β_crucero(sec)   = α_opt_crucero + φ_crucero       [diseño VPF en crucero]")
    lines.append("    φ(cond,sec)      = Va_cond / (ω × r_sec)           [coef. de flujo]")
    lines.append("    ε(r, cond)       = CL/CD_vpf / CL/CD_fijo          [Stage 4]")
    lines.append("    Δη_profile       = mean_r[(min(ε,1.10)−1)×τ],  cap ≤ 0.04")
    lines.append("")
    lines.append("  Mecanismo 2 — Mapa del fan (coeficiente de flujo φ):")
    lines.append("    Δη_map           = k_map × ((φ − φ_opt) / φ_opt)²,  cap ≤ 0.015")
    lines.append("    k_map = 0.22  (recovery fraction ≈ 20% pérdida de mapa)")
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

    # ── 1. Ratio ε por sección ─────────────────────────────────────────
    if section_results:
        lines.append("-" * 70)
        lines.append("1. RATIO DE EFICIENCIA ε POR SECCIÓN")
        lines.append("   (Mecanismo de perfil — corrección por triángulos de velocidad)")
        lines.append("-" * 70)
        lines.append("")
        conditions_order = ["takeoff", "climb", "cruise", "descent"]
        sections_order   = ["root", "mid_span", "tip"]
        header = (
            f"  {'Condición':<12}  {'Sección':<10}  {'CL/CD_fijo':>10}  "
            f"{'CL/CD_vpf':>9}  {'ε_real':>7}  {'ε_ef':>5}  {'Δα [°]':>7}  {'Ganancia':>8}"
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

        # ── Mecanismo de mapa del fan por sección ──────────────────────
        has_map = any(
            not math.isnan(r.phi_condition) for r in section_results
        )
        if has_map:
            lines.append("-" * 70)
            lines.append("1b. MECANISMO DE MAPA DEL FAN POR SECCIÓN")
            lines.append("    (φ = Va/U — desviación respecto al punto de diseño en crucero)")
            lines.append("-" * 70)
            lines.append("")
            header2 = (
                f"  {'Condición':<12}  {'Sección':<10}  {'φ_diseño':>9}  "
                f"{'φ_cond':>8}  {'Δφ/φ [%]':>9}  {'Δη_mapa':>8}"
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

    # ── 2. Eficiencia aerodinámica agregada ────────────────────────────
    lines.append("-" * 70)
    lines.append("2. EFICIENCIA AERODINÁMICA MEDIA (por condición)")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        improvement = (result.epsilon_mean - 1.0) * 100.0
        lines.append(f"  {result.condition.upper():<10}")
        lines.append(f"    CL/CD paso fijo : {result.cl_cd_fixed:7.2f}")
        lines.append(
            f"    CL/CD VPF       : {result.cl_cd_vpf:7.2f}  "
            f"(ε_medio = {result.epsilon_mean:.3f}, +{improvement:.1f}%)"
        )
        lines.append(f"    Δα medio        : {result.delta_alpha_mean_deg:.2f}°")
        lines.append("")

    # ── 3. Eficiencia de fan — desglose por mecanismo ──────────────────
    lines.append("-" * 70)
    lines.append("3. EFICIENCIA DE FAN — DESGLOSE POR MECANISMO")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        lines.append(f"  {result.condition.upper():<10}")
        lines.append(f"    η_fan base       : {result.fan_efficiency_baseline:.4f}")

        # Mecanismo de perfil
        if not math.isnan(result.delta_eta_profile):
            lines.append(f"    Δη_perfil        : {result.delta_eta_profile:+.5f}  (mecanismo 1 — CL/CD profile)")
        else:
            lines.append(f"    Δη_perfil        : n/a")

        # Mecanismo de mapa
        if not math.isnan(result.delta_eta_map):
            phi_info = ""
            if not math.isnan(result.phi_condition) and not math.isnan(result.phi_design) and result.phi_design > 0:
                delta_phi_pct = (result.phi_condition - result.phi_design) / result.phi_design * 100.0
                phi_info = f"  φ={result.phi_condition:.4f} vs φ_opt={result.phi_design:.4f} ({delta_phi_pct:+.1f}%)"
            lines.append(f"    Δη_mapa          : {result.delta_eta_map:+.5f}  (mecanismo 2 — map φ){phi_info}")
        else:
            lines.append(f"    Δη_mapa          : n/a")

        lines.append(f"    Δη_fan aplicado  : {result.delta_eta_fan:+.5f}  (combinado, tras caps)")
        lines.append(f"    η_fan VPF        : {result.fan_efficiency_new:.4f}")
        lines.append(f"    k = BPR/(1+BPR)  = {result.k_sensitivity:.4f}")
        lines.append("")

    # ── 4. Impacto en SFC ─────────────────────────────────────────────
    lines.append("-" * 70)
    lines.append("4. IMPACTO EN SFC")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        lines.append(f"  {result.condition.upper():<10}")
        lines.append(f"    SFC base    : {result.sfc_baseline:.4f} lb/(lbf·hr)")
        lines.append(f"    SFC VPF     : {result.sfc_new:.4f} lb/(lbf·hr)")
        lines.append(f"    Reducción   : {result.sfc_reduction_percent:6.2f}%")
        lines.append("")

    # ── 5. Resultados clave ────────────────────────────────────────────
    avg_reduction = sum(r.sfc_reduction_percent for r in sfc_results) / len(sfc_results)
    max_reduction = max(r.sfc_reduction_percent for r in sfc_results)
    max_cond      = max(sfc_results, key=lambda r: r.sfc_reduction_percent).condition
    lines.append("-" * 70)
    lines.append("5. RESULTADOS CLAVE")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Reducción media de SFC   : {avg_reduction:.2f}%")
    lines.append(f"  Reducción máxima de SFC  : {max_reduction:.2f}%  ({max_cond})")
    lines.append("")
    lines.append("  Rango literario para VPF (Cumpsty 2004 p.280): 2–5%")
    lines.append(f"  → Resultado dentro del rango: {'SÍ' if 1.0 <= avg_reduction <= 6.0 else 'REVISAR'}")
    lines.append("")

    # ── 6. Referencias ────────────────────────────────────────────────
    lines.append("-" * 70)
    lines.append("6. REFERENCIAS DEL MODELO FÍSICO")
    lines.append("-" * 70)
    lines.append("")
    lines.append("  [1] Saravanamuttoo, H.I.H. et al. (2017). Gas Turbine Theory,")
    lines.append("      7ª ed. Pearson. §5.3, ec. 5.14.")
    lines.append("  [2] Cumpsty, N.A. (2004). Compressor Aerodynamics, 2ª ed.")
    lines.append("      Krieger. p. 280, ch. 8, fig. 8.10.")
    lines.append("  [3] Dixon, S.L. & Hall, C.A. (2013). Fluid Mechanics and")
    lines.append("      Thermodynamics of Turbomachinery, 7ª ed. Butterworth. §7.4.")
    lines.append("  [4] Wisler, D.C. (1998). The technical and economic relevance of")
    lines.append("      understanding blade row interaction effects in turbomachinery.")
    lines.append("      VKI Lecture Series.")
    lines.append("  [5] Dickens, T. & Day, I. (2011). The Design of Highly Loaded Axial")
    lines.append("      Compressors. J. Turbomachinery, 133(3):031007.")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
