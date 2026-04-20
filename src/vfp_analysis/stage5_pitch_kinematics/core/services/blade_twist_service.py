"""
blade_twist_service.py
-----------------------
Design twist analysis and aerodynamic off-design compromise.

In a variable pitch fan, the blade has a design twist (variation of β_metal
along the radius) that centres α at its individual optimum in each section
during the design point (cruise). In off-design conditions, the single
mechanical actuator rotates the entire blade by the same angle Δβ_hub, so
the root and tip sections deviate from their individual α_opt.

This module quantifies:

1. Design twist at cruise:
   φ_flow(r) = arctan(Va_cruise / U(r))
   β_metal(r) = α_opt_3D_cruise(r) + φ_flow(r)
   twist_total = β_metal(root) − β_metal(tip)

2. Off-design with a single actuator (strategy: optimise mid_span):
   Δβ_hub(cond) = Δβ computed so that mid_span reaches its α_opt_3D
   α_actual(r, cond) = β_metal(r) + Δβ_hub(cond) − φ_flow(r, cond)

3. Span-wise compromise penalty:
   loss_pct(r, cond) = 1 − (CL_3D/CD)[α_actual] / (CL/CD)_max_3D(r, cond)

References:
- Dixon & Hall (2013), ch. 5 — Velocity triangles and blade design
- Saravanamuttoo et al. (2017), ch. 5 — Fan design and off-design performance
- Cumpsty (2004), ch. 9 — Three-dimensional flows and blade twist
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class TwistDesignResult:
    """Design twist of the blade at the cruise design point."""
    section: str
    radius_m: float
    u_cruise_m_s: float          # blade tangential velocity [m/s]
    phi_cruise_deg: float         # cruise inflow angle φ = arctan(Va/U) [°]
    alpha_opt_3d_cruise: float    # α_opt_3D at cruise for this section [°]
    beta_metal_deg: float         # design metal angle β_metal = α_opt + φ [°]
    twist_from_tip_deg: float     # twist relative to tip (β_metal − β_metal_tip) [°]


@dataclass
class OffDesignIncidenceResult:
    """Actual incidence and efficiency penalty under off-design conditions."""
    condition: str
    section: str
    va_m_s: float                # axial velocity [m/s]
    u_m_s: float                 # blade tangential velocity [m/s]
    phi_flow_deg: float          # inflow angle φ in this condition [°]
    delta_beta_hub_deg: float    # single actuator command [°]
    alpha_opt_3d: float          # individual α_opt_3D for this section [°]
    alpha_actual_deg: float      # actual α with single actuator [°]
    delta_alpha_compromise_deg: float  # α_actual − α_opt_3D (deviation) [°]
    cl_cd_max_3d: float          # (CL/CD)_max_3D at α_opt [—]
    cl_cd_actual: float          # (CL/CD)_3D at α_actual [—]
    efficiency_loss_pct: float   # efficiency loss [%]


def compute_blade_twist(
    alpha_opt_3d_cruise: Dict[str, float],
    va_cruise: float,
    omega: float,
    radii: Dict[str, float],
) -> List[TwistDesignResult]:
    """Compute the blade design twist at cruise.

    Parameters
    ----------
    alpha_opt_3d_cruise : dict[section, alpha_opt_3D_cruise]
    va_cruise : float — axial velocity at cruise [m/s]
    omega : float — fan angular velocity [rad/s]
    radii : dict[section, r_m]

    Returns
    -------
    List[TwistDesignResult] sorted by radius (root → tip)
    """
    results: List[TwistDesignResult] = []
    for section, r in radii.items():
        u = omega * r
        if u <= 0:
            continue
        phi = math.degrees(math.atan2(va_cruise, u))
        alpha = alpha_opt_3d_cruise.get(section, float("nan"))
        beta_metal = alpha + phi if not math.isnan(alpha) else float("nan")
        results.append(TwistDesignResult(
            section=section,
            radius_m=r,
            u_cruise_m_s=u,
            phi_cruise_deg=phi,
            alpha_opt_3d_cruise=alpha,
            beta_metal_deg=beta_metal,
            twist_from_tip_deg=float("nan"),  # filled below
        ))

    # Twist relative to tip
    tip_beta = next(
        (res.beta_metal_deg for res in results if res.section == "tip"), float("nan")
    )
    for res in results:
        if not math.isnan(res.beta_metal_deg) and not math.isnan(tip_beta):
            res.twist_from_tip_deg = res.beta_metal_deg - tip_beta

    return results


def compute_off_design_incidence(
    twist_results: List[TwistDesignResult],
    alpha_opt_3d_map: Dict[Tuple[str, str], float],
    cl_cd_max_3d_map: Dict[Tuple[str, str], float],
    polar_3d_map: Dict[Tuple[str, str], pd.DataFrame],
    axial_velocities: Dict[str, float],
    omega: float,
    radii: Dict[str, float],
    reference_condition: str = "cruise",
    hub_section: str = "mid_span",
) -> List[OffDesignIncidenceResult]:
    """Compute actual incidence and efficiency loss in off-design conditions.

    Actuator strategy: Δβ_hub is chosen to bring hub_section to its α_opt_3D.

    Parameters
    ----------
    twist_results : List[TwistDesignResult]
    alpha_opt_3d_map : dict[(condition, section), alpha_opt_3D]
    cl_cd_max_3d_map : dict[(condition, section), (CL/CD)_max_3D]
    polar_3d_map : dict[(condition, section), DataFrame with ld_3d]
    axial_velocities : dict[condition, Va_m_s]
    omega : float [rad/s]
    radii : dict[section, r_m]
    reference_condition : str — reference condition (cruise = Δβ=0)
    hub_section : str — section that the actuator optimises

    Returns
    -------
    List[OffDesignIncidenceResult]
    """
    beta_metal: Dict[str, float] = {r.section: r.beta_metal_deg for r in twist_results}

    results: List[OffDesignIncidenceResult] = []
    conditions = sorted(set(cond for cond, _ in alpha_opt_3d_map.keys()))

    for condition in conditions:
        va = axial_velocities.get(condition, float("nan"))

        # Δβ_hub: angle that brings hub_section to its α_opt_3D in this condition
        r_hub = radii.get(hub_section, float("nan"))
        u_hub = omega * r_hub
        phi_hub = math.degrees(math.atan2(va, u_hub)) if u_hub > 0 else 0.0
        alpha_hub_target = alpha_opt_3d_map.get((condition, hub_section), float("nan"))
        beta_metal_hub = beta_metal.get(hub_section, float("nan"))

        if not any(math.isnan(x) for x in [alpha_hub_target, phi_hub, beta_metal_hub]):
            # β_metal_hub + Δβ_hub − φ_hub = α_hub_target
            delta_beta_hub = alpha_hub_target + phi_hub - beta_metal_hub
        else:
            delta_beta_hub = 0.0

        # For the reference condition, Δβ = 0 by definition
        if condition == reference_condition:
            delta_beta_hub = 0.0

        for section, r in radii.items():
            u = omega * r
            phi = math.degrees(math.atan2(va, u)) if u > 0 else 0.0
            bm = beta_metal.get(section, float("nan"))

            if not math.isnan(bm):
                alpha_actual = bm + delta_beta_hub - phi
            else:
                alpha_actual = float("nan")

            alpha_opt = alpha_opt_3d_map.get((condition, section), float("nan"))
            delta_compromise = (
                alpha_actual - alpha_opt
                if not any(math.isnan(x) for x in [alpha_actual, alpha_opt])
                else float("nan")
            )

            cl_cd_max = cl_cd_max_3d_map.get((condition, section), float("nan"))
            cl_cd_actual = _lookup_ld_3d(polar_3d_map, condition, section, alpha_actual)
            loss = (
                100.0 * (1.0 - cl_cd_actual / cl_cd_max)
                if not any(math.isnan(x) for x in [cl_cd_actual, cl_cd_max]) and cl_cd_max > 0
                else float("nan")
            )

            results.append(OffDesignIncidenceResult(
                condition=condition,
                section=section,
                va_m_s=va,
                u_m_s=u,
                phi_flow_deg=phi,
                delta_beta_hub_deg=delta_beta_hub,
                alpha_opt_3d=alpha_opt,
                alpha_actual_deg=alpha_actual,
                delta_alpha_compromise_deg=delta_compromise,
                cl_cd_max_3d=cl_cd_max,
                cl_cd_actual=cl_cd_actual,
                efficiency_loss_pct=loss,
            ))

    return results


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _lookup_ld_3d(
    polar_map: Dict[Tuple[str, str], pd.DataFrame],
    condition: str,
    section: str,
    alpha: float,
    tol: float = 1.0,
) -> float:
    """Interpolate ld_3d at (condition, section, alpha)."""
    if math.isnan(alpha):
        return float("nan")
    df = polar_map.get((condition, section))
    if df is None or df.empty:
        return float("nan")
    ld_col = "ld_3d" if "ld_3d" in df.columns else "ld_cascade" if "ld_cascade" in df.columns else "ld"
    close = df[(df["alpha"] - alpha).abs() <= tol]
    if close.empty:
        return float("nan")
    idx = (close["alpha"] - alpha).abs().idxmin()
    val = float(close.loc[idx, ld_col])
    return val if not math.isnan(val) else float("nan")
