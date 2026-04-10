"""
Table generation for thesis export.

This module generates CSV tables ready for LaTeX import.

Two tables are produced — all others were subsets of summary_table:
  - summary_table.csv       — comprehensive: Re, Ncrit, (CL/CD)_max, alpha_opt, CL_max
  - clcd_max_by_section.csv — adds CL_at_opt and CD_at_opt (not in summary)
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from vfp_analysis.stage4_performance_metrics.metrics import AerodynamicMetrics


def export_summary_table(
    metrics: List[AerodynamicMetrics],
    output_path: Path,
) -> None:
    """
    Export comprehensive summary table with all metrics.

    Parameters
    ----------
    metrics : List[AerodynamicMetrics]
        List of computed metrics.
    output_path : Path
        Output CSV file path.
    """
    rows = []
    for m in metrics:
        rows.append(
            {
                "flight_condition": m.flight_condition,
                "blade_section": m.blade_section,
                "reynolds": m.reynolds,
                "ncrit": m.ncrit,
                "max_efficiency": m.max_efficiency,
                "alpha_opt_deg": m.alpha_opt,
                "cl_max": m.cl_max,
                "cl_at_opt": m.cl_at_opt,
                "cd_at_opt": m.cd_at_opt,
                "stall_margin_deg": m.stall_margin,
                "cm_at_opt": m.cm_at_opt,
                "alpha_design_deg": m.alpha_design,
                "delta_alpha_deg": m.delta_alpha,
                "eff_at_design_alpha": m.eff_at_design_alpha,
                "eff_gain": m.eff_gain,
                "eff_gain_pct": m.eff_gain_pct,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(["flight_condition", "blade_section"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")


def export_clcd_max_table(
    metrics: List[AerodynamicMetrics],
    output_path: Path,
) -> None:
    """
    Export maximum CL/CD by section table, including CL and CD at optimum.

    This table complements summary_table by making the CL/CD operating
    point explicit (CL_at_opt, CD_at_opt), which is useful for verifying
    the actual lift-to-drag working point per section.

    Parameters
    ----------
    metrics : List[AerodynamicMetrics]
        List of computed metrics.
    output_path : Path
        Output CSV file path.
    """
    rows = []
    for m in metrics:
        rows.append(
            {
                "flight_condition": m.flight_condition,
                "blade_section": m.blade_section,
                "clcd_max": m.max_efficiency,
                "alpha_opt_deg": m.alpha_opt,
                "cl_at_opt": m.cl_at_opt,
                "cd_at_opt": m.cd_at_opt,
                "stall_margin_deg": m.stall_margin,
                "cm_at_opt": m.cm_at_opt,
                "alpha_design_deg": m.alpha_design,
                "delta_alpha_deg": m.delta_alpha,
                "eff_at_design_alpha": m.eff_at_design_alpha,
                "eff_gain": m.eff_gain,
                "eff_gain_pct": m.eff_gain_pct,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(["flight_condition", "blade_section"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")
