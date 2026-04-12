"""
stage_loading_service.py
-------------------------
Análisis de carga de etapa mediante la ecuación de Euler y coeficientes
adimensionales φ (caudal) y ψ (trabajo) del fan de paso variable.

La ecuación de Euler de turbomaquinaria (Dixon & Hall, ec. 5.2):

    W_especifico = U · ΔV_θ   [J/kg]

Para un fan sin giro de entrada (V_θ_entrada ≈ 0):

    V_θ = U − Va / tan(β_mech)      [m/s]
    ψ   = V_θ / U  = 1 − φ·cot(β)  [—]
    φ   = Va / U                    [—]
    W   = U · V_θ = U² · ψ         [J/kg]

Zona de diseño eficiente (fan de alto bypass):
    φ ∈ [0.35, 0.55],  ψ ∈ [0.25, 0.50]

El diagrama φ-ψ (también llamado "diagrama de Smith" o "mapa de etapa")
permite verificar que todos los puntos de operación del VPF caen dentro de
la zona de rendimiento aceptable.

Referencias:
- Dixon & Hall (2013), cap. 5 — Euler turbine equation and velocity diagrams
- Cumpsty (2004), cap. 2 — Thermodynamic and aerodynamic fundamentals
- Saravanamuttoo et al. (2017), cap. 5 — Axial flow compressors and fans
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


# Zona de diseño eficiente — leída de PhysicsConstants (settings.py)
# Referencias: Dixon & Hall (2013), Cumpsty (2004)
from vfp_analysis.settings import get_settings as _get_settings
_p = _get_settings().physics
_PHI_MIN_DESIGN = _p.PHI_DESIGN_MIN
_PHI_MAX_DESIGN = _p.PHI_DESIGN_MAX
_PSI_MIN_DESIGN = _p.PSI_DESIGN_MIN
_PSI_MAX_DESIGN = _p.PSI_DESIGN_MAX


@dataclass
class StageLoadingResult:
    """Resultado del análisis de carga de etapa para un caso (condition, section)."""
    condition: str
    section: str
    va_m_s: float               # velocidad axial Va [m/s]
    u_m_s: float                # velocidad tangencial de pala U = ωr [m/s]
    alpha_opt_3d_deg: float     # ángulo de ataque óptimo 3D [°]
    beta_mech_deg: float        # ángulo mecánico β = α_opt_3D + φ_flow [°]
    phi_flow_deg: float         # ángulo de flujo φ = arctan(Va/U) [°]
    phi_coeff: float            # coeficiente de caudal φ = Va/U [—]
    v_theta_m_s: float          # velocidad tangencial impartida V_θ [m/s]
    psi_loading: float          # coeficiente de trabajo ψ = V_θ/U [—]
    w_specific_kj_kg: float     # trabajo específico W = U·V_θ [kJ/kg]
    in_design_zone: bool        # True si (φ, ψ) cae en la zona de diseño


def _in_design_zone(phi: float, psi: float) -> bool:
    return (
        _PHI_MIN_DESIGN <= phi <= _PHI_MAX_DESIGN
        and _PSI_MIN_DESIGN <= psi <= _PSI_MAX_DESIGN
    )


def compute_stage_loading(
    alpha_opt_3d_map: Dict[Tuple[str, str], float],
    axial_velocities: Dict[str, float],
    omega: float,
    radii: Dict[str, float],
) -> List[StageLoadingResult]:
    """Calcula la carga de etapa para cada (condition, section).

    Parámetros
    ----------
    alpha_opt_3d_map : dict[(condition, section), alpha_opt_3D [°]]
    axial_velocities : dict[condition, Va [m/s]]
    omega : float — velocidad angular ω [rad/s]
    radii : dict[section, r_m]

    Retorna
    -------
    List[StageLoadingResult]
    """
    results: List[StageLoadingResult] = []

    for (condition, section), alpha_3d in alpha_opt_3d_map.items():
        va = axial_velocities.get(condition, float("nan"))
        r = radii.get(section, float("nan"))

        if any(math.isnan(x) for x in [va, r, alpha_3d]):
            continue

        u = omega * r
        phi_flow = math.degrees(math.atan2(va, u))
        beta_mech = alpha_3d + phi_flow
        phi_coeff = va / u if u > 0 else float("nan")

        # V_θ = U − Va / tan(β_mech)
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
            alpha_opt_3d_deg=alpha_3d,
            beta_mech_deg=beta_mech,
            phi_flow_deg=phi_flow,
            phi_coeff=phi_coeff,
            v_theta_m_s=v_theta,
            psi_loading=psi,
            w_specific_kj_kg=w_spec,
            in_design_zone=in_zone,
        ))

    return results
