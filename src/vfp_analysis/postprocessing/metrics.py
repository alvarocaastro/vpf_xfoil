"""
Aerodynamic performance metrics computation.

This module computes key aerodynamic metrics from simulation results,
including maximum efficiency, optimal angle of attack, and maximum lift.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import pandas as pd

from vfp_analysis.postprocessing.aerodynamics_utils import (
    find_second_peak_row,
    resolve_efficiency_column,
    resolve_polar_file,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AerodynamicMetrics:
    """Aerodynamic performance metrics for a single case."""

    flight_condition: str
    blade_section: str
    reynolds: float
    ncrit: float
    max_efficiency: float  # (CL/CD)_max
    alpha_opt: float  # Angle of attack at maximum efficiency
    cl_max: float  # Maximum lift coefficient
    cl_at_opt: float  # Lift coefficient at optimal angle
    cd_at_opt: float  # Drag coefficient at optimal angle


def compute_metrics_from_polar(
    df: pd.DataFrame,
    flight_condition: str,
    blade_section: str,
    reynolds: float,
    ncrit: float,
) -> AerodynamicMetrics:
    """
    Compute aerodynamic metrics from polar data.

    Parameters
    ----------
    df : pd.DataFrame
        Polar data with columns: alpha, cl/cl_corrected, cd/cd_corrected,
        and at least one efficiency column (ld, CL_CD, or corrected variants).
    flight_condition : str
        Flight condition name.
    blade_section : str
        Blade section name.
    reynolds : float
        Reynolds number.
    ncrit : float
        Ncrit value.

    Returns
    -------
    AerodynamicMetrics
        Computed metrics.
    """
    eff_col = resolve_efficiency_column(df)

    # Resolve lift and drag column names (prefer corrected data when available)
    cl_col = "cl_corrected" if "cl_corrected" in df.columns else "cl"
    cd_col = "cd_corrected" if "cd_corrected" in df.columns else "cd"

    row_opt = find_second_peak_row(df, eff_col)

    # Maximum lift over the entire cleaned range (not just second peak)
    df_clean = df[[cl_col]].replace(float("inf"), float("nan")).replace(float("-inf"), float("nan"))
    cl_max = float(df_clean[cl_col].max())

    return AerodynamicMetrics(
        flight_condition=flight_condition,
        blade_section=blade_section,
        reynolds=reynolds,
        ncrit=ncrit,
        max_efficiency=float(row_opt[eff_col]),
        alpha_opt=float(row_opt["alpha"]),
        cl_max=cl_max,
        cl_at_opt=float(row_opt[cl_col]),
        cd_at_opt=float(row_opt[cd_col]),
    )


def compute_all_metrics(
    polars_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
    reynolds_table: Dict[str, Dict[str, float]],
    ncrit_table: Dict[str, float],
) -> List[AerodynamicMetrics]:
    """
    Compute metrics for all polar files in the results directory.

    Parameters
    ----------
    polars_dir : Path
        Directory containing polar CSV files.
    flight_conditions : List[str]
        List of flight condition names.
    blade_sections : List[str]
        List of blade section names.
    reynolds_table : Dict[str, Dict[str, float]]
        Reynolds numbers table.
    ncrit_table : Dict[str, float]
        Ncrit values table.

    Returns
    -------
    List[AerodynamicMetrics]
        List of computed metrics for all cases.
    """
    all_metrics: List[AerodynamicMetrics] = []

    for flight in flight_conditions:
        for section in blade_sections:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            try:
                df = pd.read_csv(polar_file)
                reynolds = reynolds_table[flight][section]
                ncrit = ncrit_table[flight]
                metrics = compute_metrics_from_polar(df, flight, section, reynolds, ncrit)
                all_metrics.append(metrics)
            except Exception as exc:
                LOGGER.warning("Could not compute metrics for %s/%s: %s", flight, section, exc)

    return all_metrics
