"""
optimal_incidence_service.py
----------------------------
Computes the optimal angle of attack (α_opt) per flight condition and blade
section from the Stage 2/3 polars.

The optimal point is defined as the second peak of CL/CD (α ≥ 3°) to avoid
the laminar separation bubble artefact at low angles.
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
from vfp_analysis.stage5_pitch_kinematics.core.domain.pitch_kinematics_result import (
    OptimalIncidence,
)

LOGGER = logging.getLogger(__name__)


def compute_optimal_incidence(
    df: pd.DataFrame,
    condition: str,
    section: str,
    reynolds: float,
    mach: float,
) -> OptimalIncidence:
    """
    Compute the optimal incidence point for a given polar.

    Parameters
    ----------
    df : pd.DataFrame
        Polar con columna ``alpha`` y al menos una columna de eficiencia.
    condition, section : str
        Identificadores de la condición de vuelo y sección de pala.
    reynolds, mach : float
        Reynolds y Mach de operación.

    Returns
    -------
    OptimalIncidence
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
    Compute optimal incidence for all conditions and sections.

    Uses Stage 3 corrected polars when available (higher fidelity to actual
    Mach); otherwise uses Stage 2 polars.

    Parameters
    ----------
    df_polars : pd.DataFrame
        Stage 2 polars with columns ``condition`` and ``section``.
    df_corrected : pd.DataFrame, optional
        Stage 3 corrected polars.

    Returns
    -------
    List[OptimalIncidence]
    """
    reynolds_table  = get_reynolds_table()
    target_mach     = get_target_mach()
    reference_mach  = get_reference_mach()

    all_incidences: List[OptimalIncidence] = []

    conditions = df_polars["condition"].unique() if "condition" in df_polars.columns else []
    sections   = df_polars["section"].unique()   if "section"   in df_polars.columns else []

    for condition in conditions:
        for section in sections:
            df_case = df_polars[
                (df_polars["condition"] == condition) & (df_polars["section"] == section)
            ]
            if df_case.empty:
                continue

            # Prefer corrected data if available
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
                    LOGGER.warning("Re not found for %s/%s — skipping.", condition, section)
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
