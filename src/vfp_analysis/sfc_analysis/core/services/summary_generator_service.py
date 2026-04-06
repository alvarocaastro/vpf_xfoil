"""
Service for generating SFC analysis summary text.
"""

from __future__ import annotations

from typing import List

from vfp_analysis.sfc_analysis.core.domain.sfc_parameters import SfcAnalysisResult


def generate_sfc_summary(
    sfc_results: List[SfcAnalysisResult],
) -> str:
    """
    Generate text summary of SFC analysis results.

    Parameters
    ----------
    sfc_results : List[SfcAnalysisResult]
        SFC analysis results for all conditions.

    Returns
    -------
    str
        Analysis summary text.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("SPECIFIC FUEL CONSUMPTION (SFC) IMPACT ANALYSIS SUMMARY")
    lines.append("=" * 70)
    lines.append("")
    lines.append("This analysis estimates how aerodynamic efficiency improvements")
    lines.append("from the Variable Pitch Fan (VPF) concept influence overall")
    lines.append("engine fuel consumption.")
    lines.append("")
    lines.append("-" * 70)
    lines.append("1. AERODYNAMIC EFFICIENCY IMPROVEMENTS")
    lines.append("-" * 70)
    lines.append("")

    for result in sorted(sfc_results, key=lambda x: x.condition):
        improvement = ((result.cl_cd_vpf - result.cl_cd_baseline) / result.cl_cd_baseline) * 100.0
        lines.append(f"Flight Condition: {result.condition.upper()}")
        lines.append(
            f"  Baseline CL/CD:     {result.cl_cd_baseline:7.2f}"
        )
        lines.append(
            f"  VPF CL/CD:           {result.cl_cd_vpf:7.2f}  (+{improvement:5.2f}%)"
        )
        lines.append("")

    lines.append("-" * 70)
    lines.append("2. FAN EFFICIENCY IMPROVEMENTS")
    lines.append("-" * 70)
    lines.append("")

    for result in sorted(sfc_results, key=lambda x: x.condition):
        fan_improvement = ((result.fan_efficiency_new - result.fan_efficiency_baseline) 
                          / result.fan_efficiency_baseline) * 100.0
        lines.append(f"Flight Condition: {result.condition.upper()}")
        lines.append(
            f"  Baseline fan efficiency: {result.fan_efficiency_baseline:.3f}"
        )
        lines.append(
            f"  VPF fan efficiency:      {result.fan_efficiency_new:.3f}  (+{fan_improvement:5.2f}%)"
        )
        lines.append("")

    lines.append("-" * 70)
    lines.append("3. SPECIFIC FUEL CONSUMPTION IMPACT")
    lines.append("-" * 70)
    lines.append("")

    for result in sorted(sfc_results, key=lambda x: x.condition):
        lines.append(f"Flight Condition: {result.condition.upper()}")
        lines.append(
            f"  Baseline SFC:  {result.sfc_baseline:.4f} lb/(lbf·hr)"
        )
        lines.append(
            f"  VPF SFC:       {result.sfc_new:.4f} lb/(lbf·hr)"
        )
        lines.append(
            f"  Reduction:    {result.sfc_reduction_percent:6.2f}%"
        )
        lines.append("")

    # Compute average reduction
    avg_reduction = sum(r.sfc_reduction_percent for r in sfc_results) / len(sfc_results)

    lines.append("-" * 70)
    lines.append("4. KEY FINDINGS")
    lines.append("-" * 70)
    lines.append("")
    lines.append("• Aerodynamic efficiency improvements from VPF enable")
    lines.append("  proportional improvements in fan efficiency.")
    lines.append("")
    lines.append("• Improved fan efficiency directly reduces Specific Fuel")
    lines.append("  Consumption, improving overall engine efficiency.")
    lines.append("")
    lines.append(f"• Average SFC reduction across all flight conditions: {avg_reduction:.2f}%")
    lines.append("")
    lines.append("• The Variable Pitch Fan concept demonstrates potential")
    lines.append("  for meaningful fuel consumption improvements in turbofan")
    lines.append("  engines through optimized blade incidence.")
    lines.append("")
    lines.append("=" * 70)

    return "\n".join(lines)
