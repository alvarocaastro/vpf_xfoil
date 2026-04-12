"""
summary_generator_service.py
-----------------------------
Genera el resumen de texto del análisis de SFC.
"""

from __future__ import annotations

from typing import List

from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import (
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
    lines.append("Modelo físico: comparación VPF (α_opt) vs paso fijo (α_diseño de crucero)")
    lines.append("  ε(r, cond)   = CL/CD_vpf / CL/CD_fijo  [Stage 4, mismo Mach/Re]")
    lines.append("  Δη_fan       = mean_r[(min(ε,1.10)−1)×τ],  cap Δη ≤ 0.04")
    lines.append("  SFC_new      = SFC_base / (1 + k×Δη/η_base),  k = BPR/(1+BPR)")
    lines.append("  Ref: Saravanamuttoo (2017) §5.3; Cumpsty (2004) p. 280")
    lines.append("")

    # ── 1. Ratio ε por sección ─────────────────────────────────────────
    if section_results:
        lines.append("-" * 70)
        lines.append("1. RATIO DE EFICIENCIA ε POR SECCIÓN")
        lines.append("   (ε = 1.00 en crucero — referencia de diseño)")
        lines.append("-" * 70)
        lines.append("")
        conditions_order = ["takeoff", "climb", "cruise", "descent"]
        sections_order   = ["root", "mid_span", "tip"]
        header = f"  {'Condición':<12}  {'Sección':<10}  {'CL/CD_fijo':>10}  {'CL/CD_vpf':>9}  {'ε':>6}  {'Δα [°]':>7}  {'Ganancia':>8}"
        lines.append(header)
        lines.append("  " + "-" * 66)
        for cond in conditions_order:
            for sec in sections_order:
                row = next(
                    (r for r in section_results
                     if r.condition == cond and r.blade_section == sec),
                    None,
                )
                if row is None:
                    continue
                lines.append(
                    f"  {cond:<12}  {sec:<10}  {row.cl_cd_fixed:>10.2f}  "
                    f"{row.cl_cd_vpf:>9.2f}  {row.epsilon:>6.3f}  "
                    f"{row.delta_alpha_deg:>7.2f}  {row.efficiency_gain_pct:>7.1f}%"
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
        lines.append(f"    CL/CD VPF       : {result.cl_cd_vpf:7.2f}  (ε_medio = {result.epsilon_mean:.3f}, +{improvement:.1f}%)")
        lines.append(f"    Δα medio        : {result.delta_alpha_mean_deg:.2f}°")
        lines.append("")

    # ── 3. Eficiencia de fan ───────────────────────────────────────────
    lines.append("-" * 70)
    lines.append("3. EFICIENCIA DE FAN")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        lines.append(f"  {result.condition.upper():<10}")
        lines.append(f"    η_fan base  : {result.fan_efficiency_baseline:.4f}")
        lines.append(f"    η_fan VPF   : {result.fan_efficiency_new:.4f}  (Δη = {result.delta_eta_fan:+.4f})")
        lines.append(f"    k = BPR/(1+BPR) = {result.k_sensitivity:.4f}")
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
    lines.append("      Krieger. p. 280, ch. 8.")
    lines.append("  [3] Dixon, S.L. & Hall, C.A. (2013). Fluid Mechanics and")
    lines.append("      Thermodynamics of Turbomachinery, 7ª ed. Butterworth. §7.4.")
    lines.append("  [4] Wisler, D.C. (1998). The technical and economic relevance of")
    lines.append("      understanding blade row interaction effects in turbomachinery.")
    lines.append("      VKI Lecture Series.")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
