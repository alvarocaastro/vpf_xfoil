"""
Kármán–Tsien compressibility correction model.

The Kármán–Tsien rule is a higher-order (non-linear) correction that accounts
for the variation of Mach number through the flow field.  It is more accurate
than Prandtl-Glauert for Mach numbers above ~0.5, where the linear PG theory
begins to over-predict the compressibility effect.

Correction applied to the pressure coefficient:

    Cp_KT = Cp_0 / (β + M²/(2(1+β)) × Cp_0)

where β = sqrt(1 - M²) and Cp_0 is the incompressible pressure coefficient.

For bulk lift-polar correction (thin-airfoil approximation Cp ≈ -CL/n),
this translates to a point-wise correction on each CL value:

    CL_KT(α) = CL_0(α) / (β_target + M²_target/(2(1+β_target)) × CL_0(α))
               × [β_ref + M²_ref/(2(1+β_ref)) × CL_0(α)]

The second factor normalises to the reference Mach (M=0.2), ensuring both
models start from the same XFOIL baseline.

References:
    von Kármán, T. (1941). "Compressibility Effects in Aerodynamics."
    J. Aeronautical Sciences, 8(9), 337-356.
    Tsien, H.S. (1939). "Two-dimensional subsonic flow of compressible fluids."
    J. Aeronautical Sciences, 6(10), 399-407.
"""

from __future__ import annotations

import math

import pandas as pd

from vfp_analysis.stage3_compressibility_correction.core.domain.compressibility_case import (
    CompressibilityCase,
)
from vfp_analysis.stage3_compressibility_correction.utils.critical_mach import (
    wave_drag_increment,
    estimate_mdd,
)


class KarmanTsienModel:
    """
    Kármán–Tsien compressibility correction.

    Applies a non-linear correction to each CL value in the polar, accounting
    for the Mach-number dependence of the local pressure distribution.
    Also applies wave-drag correction to CD via Lock's 4th-power law.
    """

    def __init__(self, thickness_ratio: float = 0.10, korn_kappa: float = 0.87) -> None:
        self._tc    = thickness_ratio
        self._kappa = korn_kappa

    @staticmethod
    def _kt_denominator(cl: float, mach: float) -> float:
        """Kármán–Tsien denominator for a given CL and Mach."""
        beta = math.sqrt(1.0 - mach * mach)
        return beta + (mach * mach / (2.0 * (1.0 + beta))) * cl

    def correct_polar(self, df: pd.DataFrame, case: CompressibilityCase) -> pd.DataFrame:
        """
        Apply Kármán–Tsien correction to polar data.

        Adds columns cl_kt and ld_kt to the DataFrame (alongside the existing
        cl_pg / ld_pg columns from PrandtlGlauertModel).

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame already containing cl_pg from PrandtlGlauertModel.
        case : CompressibilityCase

        Returns
        -------
        pd.DataFrame
            df with additional columns cl_kt, ld_kt, cd_corrected.
        """
        df_out = df.copy()
        cl_0 = df["cl"].values
        m_ref = case.reference_mach
        m_tgt = case.target_mach

        cl_kt = []
        for cl in cl_0:
            denom_tgt = self._kt_denominator(cl, m_tgt)
            denom_ref = self._kt_denominator(cl, m_ref)
            # Avoid division by zero near stall (large negative CL or near-zero denominator)
            if abs(denom_tgt) < 1e-6 or abs(denom_ref) < 1e-6:
                cl_kt.append(float("nan"))
            else:
                cl_kt.append(cl * denom_ref / denom_tgt)

        df_out["cl_kt"] = cl_kt

        # Kármán-Tsien correction for pitching moment (same non-linear rule as CL)
        if "cm" in df.columns:
            cm_kt = []
            for cm in df["cm"].values:
                denom_tgt = self._kt_denominator(cm, m_tgt)
                denom_ref = self._kt_denominator(cm, m_ref)
                if abs(denom_tgt) < 1e-6 or abs(denom_ref) < 1e-6:
                    cm_kt.append(float("nan"))
                else:
                    cm_kt.append(cm * denom_ref / denom_tgt)
            df_out["cm_kt"] = cm_kt

        # Wave drag: Lock's 4th-power law applied per-alpha using CL at that alpha
        cd_corrected = []
        for cl, cd in zip(cl_0, df["cd"].values):
            mdd = estimate_mdd(max(cl, 0.0), self._tc, self._kappa)
            delta_cd = wave_drag_increment(m_tgt, mdd)
            cd_corrected.append(cd + delta_cd)

        df_out["cd_corrected"] = cd_corrected

        # Recompute efficiencies using K-T CL and corrected CD
        df_out["ld_kt"] = [
            cl / cd if (cd > 0 and cl == cl) else float("nan")
            for cl, cd in zip(df_out["cl_kt"], df_out["cd_corrected"])
        ]

        # Also recompute PG efficiency with corrected CD (consistent comparison)
        if "cl_pg" in df_out.columns:
            df_out["ld_pg"] = [
                cl / cd if (cd > 0 and cl == cl) else float("nan")
                for cl, cd in zip(df_out["cl_pg"], df_out["cd_corrected"])
            ]

        return df_out
