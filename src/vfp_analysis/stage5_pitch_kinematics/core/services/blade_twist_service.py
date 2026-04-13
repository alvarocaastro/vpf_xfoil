"""
blade_twist_service.py
-----------------------
Análisis de twist de diseño y compromiso aerodinámico off-design.

En un fan de paso variable, la pala tiene un twist de diseño (variación de
β_metal a lo largo del radio) que centra α en su óptimo individual en cada
sección durante el punto de diseño (crucero). En condiciones off-design, el
único actuador mecánico gira toda la pala el mismo ángulo Δβ_hub, de modo
que las secciones root y tip se desvían de su α_opt individual.

Este módulo cuantifica:

1. Twist de diseño en crucero:
   φ_flow(r) = arctan(Va_cruise / U(r))
   β_metal(r) = α_opt_3D_cruise(r) + φ_flow(r)
   twist_total = β_metal(root) − β_metal(tip)

2. Off-design con un solo actuador (estrategia: optimizar mid_span):
   Δβ_hub(cond) = Δβ calculado para que mid_span alcance su α_opt_3D
   α_actual(r, cond) = β_metal(r) + Δβ_hub(cond) − φ_flow(r, cond)

3. Penalización por compromiso span-wise:
   loss_pct(r, cond) = 1 − (CL_3D/CD)[α_actual] / (CL/CD)_max_3D(r, cond)

Referencias:
- Dixon & Hall (2013), cap. 5 — Velocity triangles and blade design
- Saravanamuttoo et al. (2017), cap. 5 — Fan design and off-design performance
- Cumpsty (2004), cap. 9 — Three-dimensional flows and blade twist
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class TwistDesignResult:
    """Twist de diseño de la pala en la condición de crucero."""
    section: str
    radius_m: float
    u_cruise_m_s: float          # velocidad tangencial de pala [m/s]
    phi_cruise_deg: float         # ángulo de flujo en crucero φ = arctan(Va/U) [°]
    alpha_opt_3d_cruise: float    # α_opt_3D en crucero para esta sección [°]
    beta_metal_deg: float         # ángulo metal de diseño β_metal = α_opt + φ [°]
    twist_from_tip_deg: float     # twist relativo a la punta (β_metal − β_metal_tip) [°]


@dataclass
class OffDesignIncidenceResult:
    """Incidencia real y penalización de eficiencia en condición off-design."""
    condition: str
    section: str
    va_m_s: float                # velocidad axial [m/s]
    u_m_s: float                 # velocidad tangencial de pala [m/s]
    phi_flow_deg: float          # ángulo de flujo φ en esta condición [°]
    delta_beta_hub_deg: float    # comando único del actuador [°]
    alpha_opt_3d: float          # α_opt_3D individual de esta sección [°]
    alpha_actual_deg: float      # α real con el actuador único [°]
    delta_alpha_compromise_deg: float  # α_actual − α_opt_3D (desvío) [°]
    cl_cd_max_3d: float          # (CL/CD)_max_3D si estuviera en α_opt [—]
    cl_cd_actual: float          # (CL/CD)_3D en α_actual [—]
    efficiency_loss_pct: float   # pérdida de eficiencia [%]


def compute_blade_twist(
    alpha_opt_3d_cruise: Dict[str, float],
    va_cruise: float,
    omega: float,
    radii: Dict[str, float],
) -> List[TwistDesignResult]:
    """Calcula el twist de diseño de la pala en crucero.

    Parámetros
    ----------
    alpha_opt_3d_cruise : dict[section, alpha_opt_3D_cruise]
    va_cruise : float — velocidad axial en crucero [m/s]
    omega : float — velocidad angular del fan [rad/s]
    radii : dict[section, r_m]

    Retorna
    -------
    List[TwistDesignResult] ordenado por radio (root → tip)
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
            twist_from_tip_deg=float("nan"),  # se rellena abajo
        ))

    # Twist relativo a la punta
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
    """Calcula la incidencia real y la pérdida de eficiencia en condiciones off-design.

    Estrategia del actuador: Δβ_hub se elige para llevar hub_section a su α_opt_3D.

    Parámetros
    ----------
    twist_results : List[TwistDesignResult]
    alpha_opt_3d_map : dict[(condition, section), alpha_opt_3D]
    cl_cd_max_3d_map : dict[(condition, section), (CL/CD)_max_3D]
    polar_3d_map : dict[(condition, section), DataFrame con ld_3d]
    axial_velocities : dict[condition, Va_m_s]
    omega : float [rad/s]
    radii : dict[section, r_m]
    reference_condition : str — condición de referencia (crucero = Δβ=0)
    hub_section : str — sección que el actuador optimiza

    Retorna
    -------
    List[OffDesignIncidenceResult]
    """
    beta_metal: Dict[str, float] = {r.section: r.beta_metal_deg for r in twist_results}

    results: List[OffDesignIncidenceResult] = []
    conditions = sorted(set(cond for cond, _ in alpha_opt_3d_map.keys()))

    for condition in conditions:
        va = axial_velocities.get(condition, float("nan"))

        # Δβ_hub: ángulo que lleva hub_section a su α_opt_3D en esta condición
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

        # Para la condición de referencia, Δβ = 0 por definición
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
    """Interpolación de ld_3d en (condition, section, alpha)."""
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
