"""
optimal_incidence_service.py
----------------------------
Calcula el ángulo de ataque óptimo (α_opt) por condición de vuelo y sección
de pala a partir de los polares de Stage 2/3.

El punto óptimo se define como el segundo pico de CL/CD (α ≥ 3°) para evitar
el artefacto de burbuja de separación laminar a ángulos bajos.
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
    Calcula el punto de incidencia óptima de un polar dado.

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
    Calcula la incidencia óptima para todas las condiciones y secciones.

    Usa los polares corregidos de Stage 3 cuando están disponibles
    (mayor fidelidad a Mach real); si no, usa los polares de Stage 2.

    Parameters
    ----------
    df_polars : pd.DataFrame
        Polares de Stage 2 con columnas ``condition`` y ``section``.
    df_corrected : pd.DataFrame, optional
        Polares corregidos de Stage 3.

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

            # Preferir datos corregidos si existen
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
                    LOGGER.warning("Re no encontrado para %s/%s — omitiendo.", condition, section)
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
                    "No se pudo calcular incidencia óptima para %s/%s: %s", condition, section, exc
                )

    return all_incidences
