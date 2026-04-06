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
    Compute a simple score for a given airfoil polar table.

    The score combines:
    - maximum L/D
    - stall angle (higher is better)
    - average CD (lower is better)
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

    idx_max = valid["ld"].idxmax()
    row_max = valid.loc[idx_max]
    max_ld = float(row_max["ld"])
    stall_alpha = float(row_max["alpha"])

    avg_cd = float(valid["cd"].mean())

    total_score = max_ld - 0.5 * avg_cd + 0.01 * stall_alpha

    return AirfoilScore(
        airfoil=airfoil_name,
        max_ld=max_ld,
        stall_alpha=stall_alpha,
        avg_cd=avg_cd,
        total_score=total_score,
    )


