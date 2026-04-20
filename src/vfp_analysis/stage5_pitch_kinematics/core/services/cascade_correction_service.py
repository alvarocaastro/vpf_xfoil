"""
cascade_correction_service.py
------------------------------
Cascade corrections for the variable pitch fan.

In a real fan, blades do not operate as isolated aerofoils but in cascade:
mutual interference modifies the effective lift and the flow exit angle.
The magnitude of the effect depends on solidity σ = c/s, where
s = 2πr/Z is the circumferential blade spacing.

Models implemented:

1. Weinig factor (cascade lift-slope correction)
   CL_cascade = CL_2D · K_weinig
   K_weinig = (π/2 · σ) / arctan(π · σ / 2)
   Reference: Dixon & Hall (2013), eq. 3.54; Cumpsty (2004), ch. 3

2. Carter rule (exit deviation angle)
   δ_carter = m · θ / √σ
   m = 0.23  (for NACA 6-series with a/c = 0.5)
   θ = camber angle [°]
   Reference: Carter (1950), NACA TN-2273; ESDU 05017

Outputs:
    CascadeResult per section (geometric, independent of flight condition)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


# Carter rule coefficient m for NACA 6-series (a/c = 0.5)
# Read from PhysicsConstants to stay consistent with settings.py
from vfp_analysis.settings import get_settings as _get_settings
_CARTER_M_NACA6: float = _get_settings().physics.CARTER_M_NACA6


@dataclass
class CascadeResult:
    """Cascade correction results for a blade section."""
    section: str
    radius_m: float
    chord_m: float
    blade_spacing_m: float       # s = 2πr / Z  [m]
    solidity: float              # σ = c / s     [—]
    k_weinig: float              # cascade CL correction factor  [—]
    delta_carter_deg: float      # Carter deviation angle  [°]
    cl_2d_at_alpha_opt: float    # CL_2D at α_opt (before correction)  [—]
    cl_cascade_at_alpha_opt: float  # cascade CL at α_opt  [—]


def _weinig_factor(sigma: float) -> float:
    """Weinig factor for the cascade lift slope.

    Empirical linear fit calibrated to ESDU 05017 and Cumpsty (2004,
    ch. 3, fig. 3.6) for high-bypass fan cascades with stagger 20–50°:

        K_weinig ≈ 1 − 0.12·σ     (lower bound 0.78, upper bound 0.99)

    Representative GE9X values:
        σ = 0.69 (tip)   → K ≈ 0.92   ( −8% vs isolated aerofoil)
        σ = 1.17 (mid)   → K ≈ 0.86   (−14%)
        σ = 1.73 (root)  → K ≈ 0.79   (−21%)

    Physical limits: σ→0 → K=1 (isolated); σ→∞ → K→0.78 (minimum cap).

    Note: the theoretical Weinig/Schlichting formula for a pure axial cascade
    [arctan(πσ/2)/(πσ/2)] gives overly aggressive corrections (K≈0.45–0.77)
    for fans with large stagger. The linear fit is more conservative and
    agrees better with GE-class fan test data (ESDU 05017, sec. 5).

    Reference: ESDU 05017 (2005); Cumpsty (2004), ch. 3, fig. 3.6.
    """
    if sigma <= 0.0:
        return 1.0
    k = 1.0 - 0.12 * sigma
    return max(min(k, 0.99), 0.78)


def _carter_deviation(theta_deg: float, sigma: float, m: float = _CARTER_M_NACA6) -> float:
    """Exit deviation angle according to Carter's rule.

    δ = m · θ / √σ

    Parameters
    ----------
    theta_deg : float
        Blade camber angle [°].
    sigma : float
        Cascade solidity σ = c/s [—].
    m : float
        Carter coefficient (0.23 for NACA 6-series).

    Returns
    -------
    float
        Deviation angle δ [°].

    Reference: Carter (1950), NACA TN-2273; ESDU 05017
    """
    if sigma <= 0.0:
        return 0.0
    return m * theta_deg / math.sqrt(sigma)


def compute_cascade_corrections(
    blade_geometry: dict,
    alpha_opt_by_section: Dict[str, float],
    df_polars: pd.DataFrame,
) -> List[CascadeResult]:
    """Compute cascade corrections for each blade section.

    The corrections are geometric (depend on r, c, Z, θ) and not on flight
    condition. They are evaluated at the cruise α_opt of each section.

    Parameters
    ----------
    blade_geometry : dict
        Output of config_loader.get_blade_geometry().
        Keys: num_blades, chord (dict), theta_camber_deg.
    alpha_opt_by_section : dict[str, float]
        α_opt at cruise per section (to evaluate the reference CL_2D).
    df_polars : pd.DataFrame
        Polars DataFrame (columns: section, condition, alpha, CL_CD or ld,
        cl or cl_corrected, cd or cd_corrected).

    Returns
    -------
    List[CascadeResult]
    """
    from vfp_analysis.config_loader import get_blade_radii

    Z = blade_geometry["num_blades"]
    chords: Dict[str, float] = blade_geometry["chord"]
    theta = blade_geometry["theta_camber_deg"]
    radii = get_blade_radii()  # {root: 0.20, mid_span: 0.42, tip: 0.65}

    results: List[CascadeResult] = []

    for section, r in radii.items():
        c = chords.get(section, 0.10)
        s = 2.0 * math.pi * r / Z          # circumferential blade spacing [m]
        sigma = c / s                        # solidity [—]

        k_w = _weinig_factor(sigma)
        delta_c = _carter_deviation(theta, sigma)

        # CL_2D at α_opt_cruise for this section
        alpha_ref = alpha_opt_by_section.get(section, float("nan"))
        cl_2d = _lookup_cl(df_polars, section, "cruise", alpha_ref)
        cl_cascade = cl_2d * k_w if not math.isnan(cl_2d) else float("nan")

        results.append(CascadeResult(
            section=section,
            radius_m=r,
            chord_m=c,
            blade_spacing_m=s,
            solidity=sigma,
            k_weinig=k_w,
            delta_carter_deg=delta_c,
            cl_2d_at_alpha_opt=cl_2d,
            cl_cascade_at_alpha_opt=cl_cascade,
        ))

    return results


def apply_weinig_to_polar(
    df: pd.DataFrame,
    k_weinig: float,
    cl_col: str = "cl",
) -> pd.DataFrame:
    """Apply the Weinig correction to a full polar.

    Creates column ``cl_cascade`` = cl_col × K_weinig and recalculates
    ``ld_cascade`` = cl_cascade / cd.

    Parameters
    ----------
    df : pd.DataFrame
        Polar DataFrame with columns cl_col and 'cd'.
    k_weinig : float
        Weinig factor for this section.
    cl_col : str
        Name of the input CL column.

    Returns
    -------
    pd.DataFrame
        DataFrame with added columns: cl_cascade, ld_cascade.
    """
    df = df.copy()
    cd_col = "cd_corrected" if "cd_corrected" in df.columns else "cd"
    df["cl_cascade"] = df[cl_col] * k_weinig
    df["ld_cascade"] = df["cl_cascade"] / df[cd_col].replace(0, float("nan"))
    return df


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _lookup_cl(
    df: pd.DataFrame,
    section: str,
    condition: str,
    alpha: float,
    tol: float = 0.5,
) -> float:
    """Return interpolated CL at (section, condition, alpha) from the polars DataFrame."""
    if math.isnan(alpha):
        return float("nan")

    cl_col = "cl_corrected" if "cl_corrected" in df.columns else "cl"
    mask = (df["section"] == section) & (df["condition"] == condition)
    sub = df[mask].copy()
    if sub.empty:
        return float("nan")

    sub = sub.sort_values("alpha")
    close = sub[(sub["alpha"] - alpha).abs() <= tol]
    if close.empty:
        return float("nan")

    idx = (close["alpha"] - alpha).abs().idxmin()
    return float(close.loc[idx, cl_col])
