"""
Critical Mach number estimation for subsonic airfoils.

Mcr is the freestream Mach at which the flow first reaches M=1 somewhere on
the airfoil surface.  Below Mcr the flow is everywhere subsonic (subcritical);
above Mcr a supersonic pocket forms and wave drag rises sharply.

Formula used — Küchemann empirical correlation for NACA 6-series profiles:

    Mcr ≈ 0.87 - 0.108 × CL_operating

This is an engineering estimate valid for moderate lift coefficients
(0.2 ≤ CL ≤ 1.2) and NACA 6-series airfoils at typical cruise conditions.
It should be treated as indicative, not exact.

Reference: Küchemann, D. "The Aerodynamic Design of Aircraft", 1978.
           Anderson, J.D. "Introduction to Flight", 8th ed.
"""

from __future__ import annotations

import math


def estimate_mcr(cl_operating: float) -> float:
    """
    Estimate the critical Mach number for a NACA 6-series airfoil.

    Parameters
    ----------
    cl_operating : float
        Lift coefficient at the operating point (e.g. alpha_opt).

    Returns
    -------
    float
        Estimated critical Mach number Mcr.
    """
    mcr = 0.87 - 0.108 * cl_operating
    return max(0.50, min(mcr, 0.99))


def estimate_mdd(cl_operating: float, thickness_ratio: float, korn_kappa: float) -> float:
    """
    Estimate the drag-divergence Mach number using Korn's equation.

        Mdd = κ / t_c - CL / 10 - t_c / 10

    Parameters
    ----------
    cl_operating : float
        Lift coefficient at the operating point.
    thickness_ratio : float
        Airfoil thickness-to-chord ratio t/c.
    korn_kappa : float
        Technology factor κ (≈ 0.87 for NACA 6-series, ≈ 0.95 for supercritical).

    Returns
    -------
    float
        Estimated drag-divergence Mach number Mdd.
    """
    mdd = korn_kappa - thickness_ratio - cl_operating / 10.0
    return max(0.50, min(mdd, 0.99))


def wave_drag_increment(mach: float, mdd: float) -> float:
    """
    Compute wave drag increment using Lock's 4th-power law.

        ΔCDw = 20 × (M - Mdd)^4    if M > Mdd, else 0

    Parameters
    ----------
    mach : float
        Freestream Mach number.
    mdd : float
        Drag-divergence Mach number.

    Returns
    -------
    float
        Wave drag coefficient increment ΔCDw ≥ 0.
    """
    if mach <= mdd:
        return 0.0
    return 20.0 * (mach - mdd) ** 4
