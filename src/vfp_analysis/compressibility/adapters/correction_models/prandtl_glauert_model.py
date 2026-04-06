"""
Prandtl–Glauert compressibility correction model.

This correction is valid as a first-order approximation for subsonic compressible
flow. It corrects lift and pressure-related coefficients but drag requires
separate treatment.
"""

from __future__ import annotations

import math
from typing import Optional

import pandas as pd

from vfp_analysis.compressibility.core.domain.compressibility_case import (
    CompressibilityCase,
)


class PrandtlGlauertModel:
    """
    Prandtl–Glauert compressibility correction.

    Applies: C_corrected = C_reference / beta
    where beta = sqrt(1 - M^2)
    """

    @staticmethod
    def compute_beta(mach: float) -> float:
        """
        Compute compressibility factor beta = sqrt(1 - M^2).

        Parameters
        ----------
        mach : float
            Mach number.

        Returns
        -------
        float
            Compressibility factor.
        """
        if mach >= 1.0:
            raise ValueError(f"Mach {mach} >= 1.0: correction not valid for supersonic")
        return math.sqrt(1.0 - mach * mach)

    def correct_polar(
        self, df: pd.DataFrame, case: CompressibilityCase
    ) -> pd.DataFrame:
        """
        Apply Prandtl–Glauert correction to polar data.

        Parameters
        ----------
        df : pd.DataFrame
            Original polar data with columns: alpha, cl, cd, etc.
        case : CompressibilityCase
            Correction case (flight condition, target Mach, reference Mach).

        Returns
        -------
        pd.DataFrame
            Corrected polar with cl_corrected, ld_corrected, etc.
        """
        beta_ref = self.compute_beta(case.reference_mach)
        beta_target = self.compute_beta(case.target_mach)

        # Correction factor: C_corrected = C_ref * (beta_ref / beta_target)
        correction_factor = beta_ref / beta_target

        df_corrected = df.copy()

        # Correct lift coefficient (Prandtl–Glauert applies to lift/pressure)
        df_corrected["cl_corrected"] = df["cl"] * correction_factor

        # Drag: keep original or handle separately (not corrected by PG)
        # Documented that drag correction is more complex
        df_corrected["cd_original"] = df["cd"]
        df_corrected["cd_corrected"] = df["cd"]  # No correction applied

        # Corrected efficiency
        df_corrected["ld_corrected"] = (
            df_corrected["cl_corrected"] / df_corrected["cd_corrected"]
        )

        # Store corrected Mach
        df_corrected["mach_corrected"] = case.target_mach

        return df_corrected
