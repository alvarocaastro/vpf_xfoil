from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from vfp_analysis.postprocessing.aerodynamics_utils import find_second_peak_row


@dataclass(frozen=True)
class AirfoilScore:
    """Score assigned to one airfoil based on its polar data."""

    airfoil: str
    max_ld: float
    alpha_opt: float
    stall_alpha: float
    stability_margin: float
    robustness_ld: float
    total_score: float


def score_airfoil(df: pd.DataFrame) -> AirfoilScore:
    """
    Compute a fan-oriented score for a given airfoil polar table.

    The selection criterion is aligned with the rest of the project:

    1. ``max_ld`` is taken from the second aerodynamic efficiency peak
       (``alpha >= 3°``), not from the low-alpha laminar-bubble artefact.
    2. ``stability_margin`` measures the incidence distance between the
       operating point and stall: ``stall_alpha - alpha_opt``.
    3. ``robustness_ld`` is the mean ``CL/CD`` in a narrow window around the
       operating point (``alpha_opt ± 1°``), rewarding broad, stable peaks
       instead of needle-like maxima.

    Composite score:

    ``S = 1.0 * max_ld + 0.5 * robustness_ld + 1.0 * stability_margin``
    """

    if df.empty:
        return AirfoilScore(
            airfoil="",
            max_ld=np.nan,
            alpha_opt=np.nan,
            stall_alpha=np.nan,
            stability_margin=np.nan,
            robustness_ld=np.nan,
            total_score=np.nan,
        )

    airfoil_name = str(df["airfoil"].iloc[0])

    valid = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["ld", "alpha", "cl"])
    if valid.empty:
        return AirfoilScore(
            airfoil=airfoil_name,
            max_ld=np.nan,
            alpha_opt=np.nan,
            stall_alpha=np.nan,
            stability_margin=np.nan,
            robustness_ld=np.nan,
            total_score=np.nan,
        )

    row_opt = find_second_peak_row(valid, "ld", alpha_min=3.0)
    max_ld = float(row_opt["ld"])
    alpha_opt = float(row_opt["alpha"])

    idx_cl_max = valid["cl"].idxmax()
    stall_alpha = float(valid.loc[idx_cl_max, "alpha"])
    stability_margin = max(0.0, stall_alpha - alpha_opt)

    df_window = valid[(valid["alpha"] >= alpha_opt - 1.0) & (valid["alpha"] <= alpha_opt + 1.0)]
    robustness_ld = float(df_window["ld"].mean()) if not df_window.empty else max_ld

    total_score = 1.0 * max_ld + 0.5 * robustness_ld + 1.0 * stability_margin

    return AirfoilScore(
        airfoil=airfoil_name,
        max_ld=max_ld,
        alpha_opt=alpha_opt,
        stall_alpha=stall_alpha,
        stability_margin=stability_margin,
        robustness_ld=robustness_ld,
        total_score=total_score,
    )
