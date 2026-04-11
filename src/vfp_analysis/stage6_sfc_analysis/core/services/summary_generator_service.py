"""
summary_generator_service.py
-----------------------------
Genera el resumen de texto del análisis de SFC.
"""

from __future__ import annotations

from typing import List

from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import SfcAnalysisResult


def generate_sfc_summary(sfc_results: List[SfcAnalysisResult]) -> str:
    """Genera un resumen legible de los resultados del análisis de SFC."""
    lines = []
    lines.append("=" * 70)
    lines.append("SPECIFIC FUEL CONSUMPTION (SFC) IMPACT ANALYSIS SUMMARY")
    lines.append("=" * 70)
    lines.append("")
    lines.append("Este análisis estima cómo las mejoras de eficiencia aerodinámica")
    lines.append("del fan de paso variable (VPF) influyen en el consumo de combustible.")
    lines.append("")

    lines.append("-" * 70)
    lines.append("1. MEJORAS DE EFICIENCIA AERODINÁMICA")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        improvement = ((result.cl_cd_vpf - result.cl_cd_baseline) / result.cl_cd_baseline) * 100.0
        lines.append(f"Condición: {result.condition.upper()}")
        lines.append(f"  CL/CD base  : {result.cl_cd_baseline:7.2f}")
        lines.append(f"  CL/CD VPF   : {result.cl_cd_vpf:7.2f}  (+{improvement:5.2f}%)")
        lines.append("")

    lines.append("-" * 70)
    lines.append("2. MEJORAS DE EFICIENCIA DE FAN")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        fan_improvement = (
            (result.fan_efficiency_new - result.fan_efficiency_baseline)
            / result.fan_efficiency_baseline * 100.0
        )
        lines.append(f"Condición: {result.condition.upper()}")
        lines.append(f"  η_fan base  : {result.fan_efficiency_baseline:.3f}")
        lines.append(f"  η_fan VPF   : {result.fan_efficiency_new:.3f}  (+{fan_improvement:5.2f}%)")
        lines.append("")

    lines.append("-" * 70)
    lines.append("3. IMPACTO EN SFC")
    lines.append("-" * 70)
    lines.append("")
    for result in sorted(sfc_results, key=lambda x: x.condition):
        lines.append(f"Condición: {result.condition.upper()}")
        lines.append(f"  SFC base    : {result.sfc_baseline:.4f} lb/(lbf·hr)")
        lines.append(f"  SFC VPF     : {result.sfc_new:.4f} lb/(lbf·hr)")
        lines.append(f"  Reducción   : {result.sfc_reduction_percent:6.2f}%")
        lines.append("")

    avg_reduction = sum(r.sfc_reduction_percent for r in sfc_results) / len(sfc_results)
    lines.append("-" * 70)
    lines.append("4. RESULTADOS CLAVE")
    lines.append("-" * 70)
    lines.append("")
    lines.append(f"  Reducción media de SFC: {avg_reduction:.2f}%")
    lines.append("  El concepto VPF demuestra potencial de mejora significativa")
    lines.append("  en consumo de combustible optimizando la incidencia de pala.")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
