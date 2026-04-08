from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AirfoilScore:
    """Score assigned to one airfoil based on its polar data."""

    airfoil: str
    max_ld: float
    stall_alpha: float
    avg_cd: float
    total_score: float


def score_airfoil(df: pd.DataFrame) -> AirfoilScore:
    """
    Compute a multi-criteria score for a given airfoil polar table.

    The score combines three aerodynamic figures of merit relevant to
    turbofan fan-blade selection:

    1. Maximum aerodynamic efficiency ``(CL/CD)_max``  — primary driver of
       cruise fuel consumption (SFC ∝ 1/η_fan).
    2. Stall angle ``α_stall`` — angle of attack at peak CL, representing
       the usable incidence margin before separation.  A higher stall angle
       is critical for the large velocity-triangle excursions that occur
       during takeoff and climb in ultra-high-bypass configurations.
    3. Mean drag coefficient ``C̄_D`` — penalises profiles with persistently
       high viscous drag across the full operating range, not just at the
       design point.

    Weighted composite score (all terms in comparable magnitude):
    ::

        S = w1·(CL/CD)_max  +  w2·α_stall [°]  −  w3·C̄_D

    Default weights are calibrated so each term contributes roughly the
    same dynamic range for NACA 65-series fan profiles:

    * ``w1 = 1.0``   — (CL/CD)_max ≈ 60–120  → contribution ≈ 60–120
    * ``w2 = 5.0``   — α_stall ≈ 12–22 °     → contribution ≈ 60–110
    * ``w3 = 5000``  — C̄_D ≈ 0.006–0.015    → contribution ≈ 30–75

    References
    ----------
    Saravanamuttoo et al., *Gas Turbine Theory*, 6th ed., §4.3.
    Farokhi, *Aircraft Propulsion*, 2nd ed., §6.2.
    """

    if df.empty:
        return AirfoilScore(
            airfoil="",
            max_ld=np.nan,
            stall_alpha=np.nan,
            avg_cd=np.nan,
            total_score=np.nan,
        )

    airfoil_name = str(df["airfoil"].iloc[0])

    valid = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["ld", "cd"])
    if valid.empty:
        return AirfoilScore(
            airfoil=airfoil_name,
            max_ld=np.nan,
            stall_alpha=np.nan,
            avg_cd=np.nan,
            total_score=np.nan,
        )

    # Maximum aerodynamic efficiency
    idx_max_ld = valid["ld"].idxmax()
    max_ld = float(valid.loc[idx_max_ld, "ld"])

    # True stall angle: angle of attack at maximum CL.
    # This differs from the alpha at max(CL/CD), which occurs well before
    # stall.  The stall angle defines the usable incidence envelope of the
    # blade, a key criterion for variable-pitch operation.
    valid_cl = df.replace([np.inf, -np.inf], np.nan).dropna(subset=["cl"])
    if valid_cl.empty:
        stall_alpha = float(valid.loc[idx_max_ld, "alpha"])  # fallback
    else:
        idx_cl_max = valid_cl["cl"].idxmax()
        stall_alpha = float(valid_cl.loc[idx_cl_max, "alpha"])

    avg_cd = float(valid["cd"].mean())

    # Multi-criteria weighted score (see docstring for weight rationale)
    total_score = 1.0 * max_ld + 5.0 * stall_alpha - 5000.0 * avg_cd

    return AirfoilScore(
        airfoil=airfoil_name,
        max_ld=max_ld,
        stall_alpha=stall_alpha,
        avg_cd=avg_cd,
        total_score=total_score,
    )


