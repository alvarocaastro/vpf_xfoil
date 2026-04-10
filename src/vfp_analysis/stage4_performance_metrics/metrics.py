"""
Aerodynamic performance metrics computation.

This module computes key aerodynamic metrics from simulation results,
including maximum efficiency, optimal angle of attack, and maximum lift.
"""

from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from vfp_analysis.postprocessing.aerodynamics_utils import (
    compute_stall_alpha,
    find_second_peak_row,
    lookup_efficiency_at_alpha,
    resolve_efficiency_column,
    resolve_polar_file,
)

LOGGER = logging.getLogger(__name__)

# Minimum CL for viable fan blade operation.
# Below this value the blade generates insufficient thrust regardless of CL/CD.
# Based on typical turbofan fan-blade loading: CL_kt ~ 0.7–1.2 at design conditions.
CL_MIN_VIABLE = 0.70


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
    stall_margin: float  # alpha_stall - alpha_opt (deg); safety margin before stall
    cm_at_opt: float  # Pitching-moment coefficient at the optimal angle
    # --- Design-reference fields (filled by enrich_with_cruise_reference) ---
    alpha_design: float = float("nan")   # alpha_opt at cruise for this section (fixed-blade angle)
    delta_alpha: float = float("nan")    # alpha_opt - alpha_design (VPF adjustment required)
    eff_at_design_alpha: float = float("nan")  # (CL/CD) at alpha_design (fixed-pitch performance)
    eff_gain: float = float("nan")       # max_efficiency - eff_at_design_alpha (absolute VPF gain)
    eff_gain_pct: float = float("nan")   # eff_gain / eff_at_design_alpha * 100 (%)


def _first_available(df: pd.DataFrame, candidates: tuple[str, ...]) -> str:
    """Return the first column name from *candidates* that exists in *df*.

    Raises ``KeyError`` if none of the candidates is present.
    """
    for col in candidates:
        if col in df.columns:
            return col
    raise KeyError(
        f"None of the expected columns {list(candidates)} found in DataFrame. "
        f"Available: {list(df.columns)}"
    )


def compute_metrics_from_polar(
    df: pd.DataFrame,
    flight_condition: str,
    blade_section: str,
    reynolds: float,
    ncrit: float,
    alpha_min: float = 3.0,
) -> AerodynamicMetrics:
    """
    Compute aerodynamic metrics from polar data.

    The operating point is defined as the second CL/CD peak (alpha >= alpha_min),
    which avoids the laminar-separation-bubble artefact at very low angles
    produced by XFOIL for NACA 6-series profiles.

    Column priority (highest to lowest):

    - Efficiency : ``ld_corrected`` → ``ld_kt`` → ``ld`` → ``CL_CD``
    - Lift       : ``cl_corrected`` → ``cl_kt`` → ``cl``
    - Drag       : ``cd_corrected`` → ``cd``
    - Moment     : ``cm`` (optional; NaN when absent)

    Parameters
    ----------
    df:
        Polar DataFrame. Must contain ``alpha``, a lift column, a drag column,
        and at least one efficiency column.
    flight_condition:
        Flight condition identifier (e.g. ``"cruise"``).
    blade_section:
        Blade section identifier (e.g. ``"tip"``).
    reynolds:
        Reynolds number for this case.
    ncrit:
        Ncrit (transition criterion) for this case.

    Returns
    -------
    AerodynamicMetrics
        Computed metrics including stall margin and pitching moment.
    """
    eff_col = resolve_efficiency_column(df)

    # Prefer corrected/KT columns when available (Stage 3 output).
    cl_col = _first_available(df, ("cl_corrected", "cl_kt", "cl"))
    cd_col = _first_available(df, ("cd_corrected", "cd"))
    cm_col: Optional[str] = "cm" if "cm" in df.columns else None

    # Apply minimum-CL constraint before finding the efficiency peak.
    # This replaces the old alpha_min=3° heuristic: instead of filtering by angle
    # (which excluded the true aerodynamic optimum in high-Mach corrected polars),
    # we filter by minimum viable lift coefficient. Points with CL < CL_MIN_VIABLE
    # cannot generate sufficient thrust regardless of their CL/CD ratio.
    df_viable = df[df[cl_col] >= CL_MIN_VIABLE]
    if df_viable.empty:
        LOGGER.warning(
            "No data with %s >= %.2f for %s/%s. Using full polar.",
            cl_col, CL_MIN_VIABLE, flight_condition, blade_section,
        )
        df_viable = df

    row_opt = find_second_peak_row(df_viable, eff_col, alpha_min=alpha_min)

    # Maximum lift over the entire cleaned range (not just second peak)
    df_clean = df[[cl_col]].replace(float("inf"), float("nan")).replace(float("-inf"), float("nan"))
    cl_max = float(df_clean[cl_col].max())

    # Stall margin: alpha_stall - alpha_opt
    alpha_stall = compute_stall_alpha(df, cl_col)
    stall_margin = alpha_stall - float(row_opt["alpha"])

    # Pitching moment at optimal angle (NaN if not available)
    cm_at_opt = float(row_opt[cm_col]) if cm_col is not None else float("nan")

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
        stall_margin=stall_margin,
        cm_at_opt=cm_at_opt,
    )


def compute_all_metrics(
    polars_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
    reynolds_table: Dict[str, Dict[str, float]],
    ncrit_table: Dict[str, float],
    design_condition: str = "cruise",
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
                # For the design condition (cruise) the wave drag eliminates the
                # conventional second peak. We use a per-section alpha_min to
                # capture the stabilisation point post-laminar-bubble (CL/CD ≥ 60
                # at M=0.85). Values tuned per section polar:
                #   root     2.5° — stabilises later due to thicker profile
                #   mid_span 2.2° — intermediate stabilisation
                #   tip      2.0° — thinnest section, earliest stabilisation
                # For other conditions the second peak (alpha >= 3°) applies.
                _CRUISE_ALPHA_MIN: dict[str, float] = {
                    "root": 2.5,
                    "mid_span": 2.2,
                    "tip": 2.0,
                }
                if flight == design_condition:
                    alpha_min = _CRUISE_ALPHA_MIN.get(section, 2.0)
                else:
                    alpha_min = 3.0
                metrics = compute_metrics_from_polar(
                    df, flight, section, reynolds, ncrit, alpha_min=alpha_min
                )
                all_metrics.append(metrics)
            except Exception as exc:
                LOGGER.warning("Could not compute metrics for %s/%s: %s", flight, section, exc)

    return all_metrics


def enrich_with_cruise_reference(
    metrics: List[AerodynamicMetrics],
    polars_dir: Path,
    design_condition: str = "cruise",
) -> List[AerodynamicMetrics]:
    """Enrich metrics with design-reference fields relative to the cruise condition.

    The blade design angle is defined as the α_opt at *design_condition* for each
    section. For non-design conditions this function computes:

    - ``alpha_design``       : α_opt_cruise for the same section
    - ``delta_alpha``        : α_opt − α_design (VPF pitch adjustment required)
    - ``eff_at_design_alpha``: (CL/CD) evaluated at α_design (fixed-pitch performance)
    - ``eff_gain``           : max_efficiency − eff_at_design_alpha
    - ``eff_gain_pct``       : eff_gain / eff_at_design_alpha × 100

    For the design condition itself all gains are zero by definition.

    Parameters
    ----------
    metrics:
        List produced by ``compute_all_metrics``.
    polars_dir:
        Directory used to locate polar files (same as passed to ``compute_all_metrics``).
    design_condition:
        Flight condition that defines the reference blade angle (default: ``"cruise"``).

    Returns
    -------
    List[AerodynamicMetrics]
        New list with design-reference fields filled in.
    """
    # Step 1: extract alpha_design per section from the design condition
    alpha_design_map: Dict[str, float] = {
        m.blade_section: m.alpha_opt
        for m in metrics
        if m.flight_condition == design_condition
    }

    if not alpha_design_map:
        LOGGER.warning(
            "No metrics found for design condition '%s'. "
            "Design-reference fields will remain NaN.",
            design_condition,
        )
        return metrics

    # Step 2: enrich each case
    enriched: List[AerodynamicMetrics] = []
    for m in metrics:
        alpha_design = alpha_design_map.get(m.blade_section, float("nan"))

        if m.flight_condition == design_condition:
            # At the design condition the blade is perfectly aligned → no gain
            enriched.append(dataclasses.replace(
                m,
                alpha_design=alpha_design,
                delta_alpha=0.0,
                eff_at_design_alpha=m.max_efficiency,
                eff_gain=0.0,
                eff_gain_pct=0.0,
            ))
            continue

        # For non-design conditions: evaluate efficiency at alpha_design
        polar_file = resolve_polar_file(polars_dir, m.flight_condition, m.blade_section)
        eff_at_design = float("nan")
        if polar_file is not None:
            try:
                df = pd.read_csv(polar_file)
                eff_col = resolve_efficiency_column(df)
                eff_at_design = lookup_efficiency_at_alpha(df, eff_col, alpha_design)
            except Exception as exc:
                LOGGER.warning(
                    "Could not evaluate efficiency at alpha_design for %s/%s: %s",
                    m.flight_condition, m.blade_section, exc,
                )

        delta_alpha = m.alpha_opt - alpha_design
        eff_gain = m.max_efficiency - eff_at_design if not (
            eff_at_design != eff_at_design  # NaN check
        ) else float("nan")
        eff_gain_pct = (
            eff_gain / eff_at_design * 100
            if eff_at_design > 0 and eff_gain == eff_gain  # not NaN
            else float("nan")
        )

        enriched.append(dataclasses.replace(
            m,
            alpha_design=alpha_design,
            delta_alpha=delta_alpha,
            eff_at_design_alpha=eff_at_design,
            eff_gain=eff_gain,
            eff_gain_pct=eff_gain_pct,
        ))

    return enriched
