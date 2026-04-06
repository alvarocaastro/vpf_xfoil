"""
Table generation for thesis export.

This module generates CSV tables ready for LaTeX import.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from vfp_analysis.postprocessing.metrics import AerodynamicMetrics


def export_efficiency_table(
    metrics: List[AerodynamicMetrics],
    output_path: Path,
) -> None:
    """
    Export efficiency by condition table.

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
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(["flight_condition", "blade_section"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")


def export_alpha_opt_table(
    metrics: List[AerodynamicMetrics],
    output_path: Path,
) -> None:
    """
    Export optimal angle of attack by condition table.

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
                "alpha_opt_deg": m.alpha_opt,
                "max_efficiency": m.max_efficiency,
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
    Export maximum CL/CD by section table.

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
                "cl_at_opt": m.cl_at_opt,
                "cd_at_opt": m.cd_at_opt,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(["flight_condition", "blade_section"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")


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
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(["flight_condition", "blade_section"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")


def export_alpha_opt_second_peak(
    metrics: List[AerodynamicMetrics],
    output_path: Path,
) -> None:
    """
    Export optimal angle of attack from second efficiency peak.

    This table specifically focuses on the second CL/CD peak (alpha >= 3°),
    which represents the relevant operating point for turbomachinery blades.
    The first peak at low alpha is an artifact of laminar separation bubble
    effects and is not representative of real fan blade operation.

    Parameters
    ----------
    metrics : List[AerodynamicMetrics]
        List of computed metrics (already using second peak).
    output_path : Path
        Output CSV file path.
    """
    rows = []
    for m in metrics:
        rows.append(
            {
                "condition": m.flight_condition,
                "section": m.blade_section,
                "Re": m.reynolds,
                "alpha_opt": m.alpha_opt,
                "CL_CD_max": m.max_efficiency,
            }
        )

    df = pd.DataFrame(rows)
    df = df.sort_values(["condition", "section"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")
