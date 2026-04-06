"""
Service for computing optimal incidence angles from aerodynamic data.
"""

from __future__ import annotations

import logging
from typing import List

import pandas as pd

from vfp_analysis.config_loader import (
    get_reference_mach,
    get_reynolds_table,
    get_target_mach,
)
from vfp_analysis.postprocessing.aerodynamics_utils import (
    find_second_peak_row,
    resolve_efficiency_column,
)
from vfp_analysis.vpf_analysis.core.domain.optimal_incidence import OptimalIncidence

LOGGER = logging.getLogger(__name__)


def compute_optimal_incidence(
    df: pd.DataFrame,
    condition: str,
    section: str,
    reynolds: float,
    mach: float,
) -> OptimalIncidence:
    """
    Compute optimal incidence angle from polar data.

    Uses the second efficiency peak (alpha >= 3°) to avoid the laminar
    separation bubble artifact at low angles.

    Parameters
    ----------
    df : pd.DataFrame
        Polar data with at least an ``alpha`` column and one efficiency column
        (ld, CL_CD, or their corrected variants).
    condition : str
        Flight condition name.
    section : str
        Blade section name.
    reynolds : float
        Reynolds number.
    mach : float
        Mach number.

    Returns
    -------
    OptimalIncidence
        Optimal incidence data.
    """
    eff_col = resolve_efficiency_column(df)
    row_opt = find_second_peak_row(df, eff_col)

    return OptimalIncidence(
        condition=condition,
        section=section,
        reynolds=reynolds,
        mach=mach,
        alpha_opt=float(row_opt["alpha"]),
        cl_cd_max=float(row_opt[eff_col]),
    )


def compute_all_optimal_incidences(
    df_polars: pd.DataFrame,
    df_corrected: pd.DataFrame | None = None,
) -> List[OptimalIncidence]:
    """
    Compute optimal incidence for all flight conditions and sections.

    Parameters
    ----------
    df_polars : pd.DataFrame
        Polar data from Stage 2 (XFOIL simulations).
    df_corrected : pd.DataFrame, optional
        Corrected data from Stage 3 (compressibility). When provided,
        corrected efficiency data takes priority.

    Returns
    -------
    List[OptimalIncidence]
        List of optimal incidence data for all cases.
    """
    reynolds_table = get_reynolds_table()
    target_mach = get_target_mach()
    reference_mach = get_reference_mach()

    all_incidences: List[OptimalIncidence] = []

    conditions = df_polars["condition"].unique() if "condition" in df_polars.columns else []
    sections = df_polars["section"].unique() if "section" in df_polars.columns else []

    for condition in conditions:
        for section in sections:
            df_case = df_polars[
                (df_polars["condition"] == condition) & (df_polars["section"] == section)
            ]
            if df_case.empty:
                continue

            # Prefer compressibility-corrected data when available
            if df_corrected is not None and not df_corrected.empty:
                df_corr_case = df_corrected[
                    (df_corrected["condition"] == condition)
                    & (df_corrected["section"] == section)
                ]
                if not df_corr_case.empty:
                    df_case = df_corr_case

            try:
                reynolds = reynolds_table[condition][section]
            except KeyError:
                if "re" in df_case.columns:
                    reynolds = float(df_case["re"].iloc[0])
                else:
                    LOGGER.warning(
                        "Reynolds number not found for %s/%s — skipping.", condition, section
                    )
                    continue

            mach = (
                target_mach.get(condition, reference_mach)
                if df_corrected is not None and not df_corrected.empty
                else reference_mach
            )

            try:
                incidence = compute_optimal_incidence(df_case, condition, section, reynolds, mach)
                all_incidences.append(incidence)
            except Exception as exc:
                LOGGER.warning(
                    "Could not compute optimal incidence for %s/%s: %s", condition, section, exc
                )

    return all_incidences
