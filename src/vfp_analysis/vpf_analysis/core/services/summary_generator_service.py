"""
Service for generating analysis summary text.
"""

from __future__ import annotations

from typing import List

from vfp_analysis.vpf_analysis.core.domain.optimal_incidence import (
    OptimalIncidence,
    PitchAdjustment,
)


def generate_analysis_summary(
    optimal_incidences: List[OptimalIncidence],
    pitch_adjustments: List[PitchAdjustment],
) -> str:
    """
    Generate text summary of VPF analysis results.

    Parameters
    ----------
    optimal_incidences : List[OptimalIncidence]
        Optimal incidence angles for all conditions.
    pitch_adjustments : List[PitchAdjustment]
        Pitch adjustments relative to reference.

    Returns
    -------
    str
        Analysis summary text.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("VARIABLE PITCH FAN (VPF) AERODYNAMIC ANALYSIS SUMMARY")
    lines.append("=" * 70)
    lines.append("")
    lines.append("This analysis demonstrates how optimal blade incidence varies")
    lines.append("across flight conditions and quantifies the pitch adjustments")
    lines.append("required for a Variable Pitch Fan mechanism to maintain optimal")
    lines.append("aerodynamic efficiency.")
    lines.append("")
    lines.append("-" * 70)
    lines.append("1. OPTIMAL INCIDENCE VARIATION")
    lines.append("-" * 70)
    lines.append("")

    # Group by condition
    by_condition: dict[str, List[OptimalIncidence]] = {}
    for inc in optimal_incidences:
        if inc.condition not in by_condition:
            by_condition[inc.condition] = []
        by_condition[inc.condition].append(inc)

    for condition in sorted(by_condition.keys()):
        incidences = by_condition[condition]
        lines.append(f"Flight Condition: {condition.upper()}")
        for inc in sorted(incidences, key=lambda x: x.section):
            lines.append(
                f"  {inc.section:12s}: alpha_opt = {inc.alpha_opt:6.2f}°  "
                f"(CL/CD_max = {inc.cl_cd_max:7.2f}, Re = {inc.reynolds:.2e})"
            )
        lines.append("")

    lines.append("-" * 70)
    lines.append("2. PITCH ADJUSTMENT REQUIREMENTS")
    lines.append("-" * 70)
    lines.append("")
    lines.append("Pitch adjustments relative to CRUISE condition:")
    lines.append("")

    # Group by condition
    by_condition_adj: dict[str, List[PitchAdjustment]] = {}
    for adj in pitch_adjustments:
        if adj.condition not in by_condition_adj:
            by_condition_adj[adj.condition] = []
        by_condition_adj[adj.condition].append(adj)

    for condition in sorted(by_condition_adj.keys()):
        adjustments = by_condition_adj[condition]
        if condition == "cruise":
            lines.append(f"{condition.upper()}: Reference condition (delta_pitch = 0°)")
        else:
            lines.append(f"Flight Condition: {condition.upper()}")
            for adj in sorted(adjustments, key=lambda x: x.section):
                sign = "+" if adj.delta_pitch >= 0 else ""
                lines.append(
                    f"  {adj.section:12s}: delta_pitch = {sign}{adj.delta_pitch:6.2f}°  "
                    f"(alpha_opt = {adj.alpha_opt:6.2f}°)"
                )
        lines.append("")

    lines.append("-" * 70)
    lines.append("3. AERODYNAMIC IMPLICATIONS")
    lines.append("-" * 70)
    lines.append("")
    lines.append("Key Findings:")
    lines.append("")
    lines.append("• Optimal incidence varies significantly across flight conditions.")
    lines.append("  This variation represents the pitch adjustment that a VPF")
    lines.append("  mechanism could apply to maintain peak efficiency.")
    lines.append("")
    lines.append("• Different blade sections (root, mid_span, tip) show different")
    lines.append("  optimal angles due to varying Reynolds numbers and local")
    lines.append("  flow conditions.")
    lines.append("")
    lines.append("• A variable pitch mechanism allows the fan to operate at")
    lines.append("  maximum efficiency across all flight regimes, improving")
    lines.append("  overall engine performance and fuel efficiency.")
    lines.append("")
    lines.append("• The analysis uses the SECOND efficiency peak (alpha >= 3°)")
    lines.append("  to avoid the laminar separation bubble artifact at low angles,")
    lines.append("  ensuring results are representative of real turbomachinery")
    lines.append("  operation.")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
