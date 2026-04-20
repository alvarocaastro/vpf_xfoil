"""
stage_loading_service.py
-------------------------
Stage loading analysis using the Euler equation and dimensionless coefficients
φ (flow) and ψ (work) for the variable pitch fan.

Euler turbomachinery equation (Dixon & Hall, eq. 5.2):

    W_specific = U · ΔV_θ   [J/kg]

For a fan without inlet swirl (V_θ_inlet ≈ 0):

    V_θ = U − Va / tan(β_mech)      [m/s]
    ψ   = V_θ / U  = 1 − φ·cot(β)  [—]
    φ   = Va / U                    [—]
    W   = U · V_θ = U² · ψ         [J/kg]

Efficient design zone (high-bypass fan):
    φ ∈ [0.35, 0.55],  ψ ∈ [0.25, 0.50]

The φ-ψ diagram (also called "Smith chart" or "stage map") verifies that
all VPF operating points fall within the acceptable performance zone.

References:
- Dixon & Hall (2013), ch. 5 — Euler turbine equation and velocity diagrams
- Cumpsty (2004), ch. 2 — Thermodynamic and aerodynamic fundamentals
- Saravanamuttoo et al. (2017), ch. 5 — Axial flow compressors and fans
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


# Efficient design zone — read from PhysicsConstants (settings.py)
# References: Dixon & Hall (2013), Cumpsty (2004)
from vfp_analysis.settings import get_settings as _get_settings
_p = _get_settings().physics
_PHI_MIN_DESIGN = _p.PHI_DESIGN_MIN
_PHI_MAX_DESIGN = _p.PHI_DESIGN_MAX
_PSI_MIN_DESIGN = _p.PSI_DESIGN_MIN
_PSI_MAX_DESIGN = _p.PSI_DESIGN_MAX


@dataclass
class StageLoadingResult:
    """Stage loading analysis result for a (condition, section) case."""
    condition: str
    section: str
    va_m_s: float               # axial velocity Va [m/s]
    u_m_s: float                # blade tangential velocity U = ωr [m/s]
    alpha_opt_3d_deg: float     # 3D optimal angle of attack [°]
    beta_mech_deg: float        # mechanical angle β = α_opt_3D + φ_flow [°]
    phi_flow_deg: float         # inflow angle φ = arctan(Va/U) [°]
    phi_coeff: float            # flow coefficient φ = Va/U [—]
    v_theta_m_s: float          # imparted tangential velocity V_θ [m/s]
    psi_loading: float          # work coefficient ψ = V_θ/U [—]
    w_specific_kj_kg: float     # specific work W = U·V_θ [kJ/kg]
    in_design_zone: bool        # True if (φ, ψ) falls in the design zone


def _in_design_zone(phi: float, psi: float) -> bool:
    return (
        _PHI_MIN_DESIGN <= phi <= _PHI_MAX_DESIGN
        and _PSI_MIN_DESIGN <= psi <= _PSI_MAX_DESIGN
    )


def compute_stage_loading(
    alpha_map_deg: Dict[Tuple[str, str], float],
    axial_velocities: Dict[str, float],
    omega: float,
    radii: Dict[str, float],
) -> List[StageLoadingResult]:
    """Compute stage loading for each (condition, section).

    The function is agnostic to the source of the incidence angle: it can be
    fed with α_opt_3D (ideal pitch free per condition, aerodynamically optimal
    scenario) or α_actual (single actuator command, real physical VPF scenario).
    In both cases the coefficients φ, ψ and W_spec are derived from
    β_mech = α + arctan(Va/U).

    Note on the design zone: the PHI_DESIGN and PSI_DESIGN limits
    (Dixon & Hall, 2013, ch. 5) correspond to the design point of a fixed-pitch
    fan sized for a target PR. A VPF operating at aerodynamic α_opt generates
    lower ψ (less turning) in exchange for higher CL/CD — the `in_design_zone`
    check is informative, not prescriptive.

    Parameters
    ----------
    alpha_map_deg : dict[(condition, section), alpha_deg]
        Incidence map per case (α_opt_3D or α_actual depending on strategy).
    axial_velocities : dict[condition, Va [m/s]]
    omega : float — angular velocity ω [rad/s]
    radii : dict[section, r_m]

    Returns
    -------
    List[StageLoadingResult]
    """
    results: List[StageLoadingResult] = []

    for (condition, section), alpha_deg in alpha_map_deg.items():
        va = axial_velocities.get(condition, float("nan"))
        r = radii.get(section, float("nan"))

        if any(math.isnan(x) for x in [va, r, alpha_deg]):
            continue

        u = omega * r
        if u <= 0:
            continue
        phi_flow = math.degrees(math.atan2(va, u))
        beta_mech = alpha_deg + phi_flow
        phi_coeff = va / u

        # V_θ = U − Va / tan(β_mech)  [tangential velocity imparted to flow]
        beta_rad = math.radians(beta_mech)
        tan_beta = math.tan(beta_rad)
        if abs(tan_beta) < 1e-6:
            v_theta = float("nan")
        else:
            v_theta = u - va / tan_beta

        psi = v_theta / u if u > 0 and not math.isnan(v_theta) else float("nan")
        w_spec = u * v_theta / 1000.0 if not math.isnan(v_theta) else float("nan")

        in_zone = (
            _in_design_zone(phi_coeff, psi)
            if not any(math.isnan(x) for x in [phi_coeff, psi])
            else False
        )

        results.append(StageLoadingResult(
            condition=condition,
            section=section,
            va_m_s=va,
            u_m_s=u,
            alpha_opt_3d_deg=alpha_deg,
            beta_mech_deg=beta_mech,
            phi_flow_deg=phi_flow,
            phi_coeff=phi_coeff,
            v_theta_m_s=v_theta,
            psi_loading=psi,
            w_specific_kj_kg=w_spec,
            in_design_zone=in_zone,
        ))

    return results
