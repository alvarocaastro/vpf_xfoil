"""
propulsion_model_service.py
---------------------------
Sub-modelos físicos para el cálculo de mejoras de SFC mediante VPF.

Modelo de transferencia de eficiencia de perfil a fan:
    ε_eff           = min(ε, EPSILON_CAP)
    Δη_profile(r)   = (ε_eff − 1) × τ
    Δη_fan          = mean_r(Δη_profile),  capped at ETA_FAN_DELTA_CAP
    η_fan,new       = min(η_base × (1 + Δη_fan), ETA_FAN_ABS_CAP)
    SFC_new         = SFC_base / (1 + k × Δη_applied / η_base)
    k = BPR/(1+BPR) (Saravanamuttoo 2017 ec. 5.14)

τ (profile_efficiency_transfer) amortigua las pérdidas 3D que impiden que
la mejora 2D del perfil se transfiera íntegramente al fan completo.
EPSILON_CAP limita el ratio ε a valores físicamente creíbles en cascada 3D.
"""

from __future__ import annotations

import logging
from typing import List, Tuple  # noqa: F401 — Tuple used in type comments

from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import (
    EPSILON_CAP,
    ETA_FAN_ABS_CAP,
    ETA_FAN_COMBINED_CAP,
    ETA_FAN_DELTA_CAP,
    ETA_FAN_MAP_CAP,
    FAN_MAP_LOSS_COEFFICIENT,
)

LOGGER = logging.getLogger(__name__)


def compute_bypass_sensitivity_factor(bypass_ratio: float) -> float:
    """Fracción de empuje neto producida por el flujo de derivación (fan).

    k = BPR / (1 + BPR)

    Derivación: para un turbofan de flujos separados con relación de derivación BPR,
    ignorando diferencias de velocidad del chorro caliente, el fan produce
    k = BPR/(1+BPR) del empuje total de momento. La perturbación de 1er orden
    de TSFC con δη_fan da: ΔTSFC/TSFC ≈ −k · δη_fan / η_fan.

    Ref: Saravanamuttoo et al. (2017) *Gas Turbine Theory*, 7ª ed., ec. 5.14.

    Parameters
    ----------
    bypass_ratio : float  Relación de derivación (BPR > 0).

    Returns
    -------
    float  Factor k ∈ (0, 1).
    """
    if bypass_ratio <= 0:
        raise ValueError("bypass_ratio debe ser positivo.")
    return bypass_ratio / (1.0 + bypass_ratio)


def compute_propulsion_efficiency(v0: float, vj: float) -> float:
    """Eficiencia propulsiva: η_prop = 2 / (1 + V_j / V_0).

    Parameters
    ----------
    v0 : float  Velocidad de vuelo [m/s].
    vj : float  Velocidad de salida del chorro [m/s].
    """
    if v0 <= 0:
        raise ValueError("La velocidad de vuelo debe ser positiva.")
    if vj <= 0:
        raise ValueError("La velocidad del chorro debe ser positiva.")
    return 2.0 / (1.0 + vj / v0)


def compute_fan_efficiency_improvement(
    epsilon_values: List[float],
    fan_efficiency_baseline: float,
    tau: float = 0.65,
    epsilon_cap: float = EPSILON_CAP,
    eta_fan_delta_cap: float = ETA_FAN_DELTA_CAP,
    eta_fan_abs_cap: float = ETA_FAN_ABS_CAP,
) -> Tuple[float, float, float]:
    """Estima la mejora de eficiencia de fan a partir de los ratios ε por sección.

    Proceso:
        1. Para cada sección: ε_eff = min(ε, epsilon_cap)
        2. Δη_profile(r) = (ε_eff − 1) × τ
        3. Δη_fan_raw = mean(Δη_profile)
        4. Δη_fan_capped = min(Δη_fan_raw, eta_fan_delta_cap)
        5. η_fan,new = min(η_base × (1 + Δη_fan_capped), eta_fan_abs_cap)

    Parameters
    ----------
    epsilon_values : list[float]
        Ratios ε por sección [–] (= CL/CD_vpf / CL/CD_fixed).
    fan_efficiency_baseline : float
        η_fan base [–].
    tau : float
        Coeficiente de transferencia 2D→3D (default: 0.65).
        Ref: Cumpsty (2004) §8; Peretz & Gany (1992).
    epsilon_cap : float
        Límite físico para ε antes de aplicar τ (default: EPSILON_CAP = 1.10).
        Ref: Cumpsty (2004) p. 280; Wisler (1998) VKI.
    eta_fan_delta_cap : float
        Mejora absoluta máxima de η_fan (default: ETA_FAN_DELTA_CAP = 0.04).
        Ref: Cumpsty (2004) p. 280.
    eta_fan_abs_cap : float
        Límite absoluto de η_fan (default: ETA_FAN_ABS_CAP = 0.96).
        Ref: Cumpsty (2004) ch. 8.

    Returns
    -------
    eta_fan_new : float     Nueva eficiencia de fan tras aplicar todos los caps.
    delta_eta_raw : float   Δη_fan calculado antes del cap de delta.
    delta_eta_applied : float  Δη_fan realmente aplicado (= η_fan_new − η_base).
    """
    if fan_efficiency_baseline <= 0:
        raise ValueError("fan_efficiency_baseline debe ser positivo.")
    if not epsilon_values:
        raise ValueError("epsilon_values no puede estar vacío.")

    delta_etas = [(min(eps, epsilon_cap) - 1.0) * tau for eps in epsilon_values]
    delta_eta_raw = sum(delta_etas) / len(delta_etas)
    delta_eta_capped = min(delta_eta_raw, eta_fan_delta_cap)

    eta_fan_new = min(
        fan_efficiency_baseline * (1.0 + delta_eta_capped),
        eta_fan_abs_cap,
    )
    delta_eta_applied = eta_fan_new - fan_efficiency_baseline

    return eta_fan_new, delta_eta_raw, delta_eta_applied


def compute_fan_map_efficiency_gain(
    phi_condition: float,
    phi_design: float,
    k_map: float = FAN_MAP_LOSS_COEFFICIENT,
    map_cap: float = ETA_FAN_MAP_CAP,
) -> float:
    """Ganancia de eficiencia del fan por el mecanismo de mapa (coef. de flujo φ).

    Un fan de paso fijo se ve forzado a operar en puntos donde φ = Va/U ≠ φ_opt
    cuando la condición de vuelo cambia (Va varía entre fases). Esta desviación
    introduce pérdidas cuadráticas en el mapa del fan que VPF recupera parcialmente
    al mantener la incidencia óptima.

        Δη_map = k_map × ((φ − φ_opt) / φ_opt)²    [modelo parabólico simple]
        Δη_map_capped = min(Δη_map, map_cap)

    Esta ganancia es **independiente y aditiva** al mecanismo de perfil (τ-mediado):
    la pérdida de mapa no pasa por la cadena 2D→3D de τ — es una pérdida de
    sistema directamente recuperable ajustando la ley de paso.

    Ref: Cumpsty (2004) *Compressor Aerodynamics*, ch. 8 (fig. 8.10);
         Dickens & Day (2011). "The Design of Highly Loaded Axial Compressors".
         J. Turbomach. 133(3):031007.

    Parameters
    ----------
    phi_condition : float
        Coeficiente de flujo en la condición off-design: Va_cond / U_section.
    phi_design : float
        Coeficiente de flujo en diseño (crucero): Va_cruise / U_section.
    k_map : float
        Coeficiente de pérdida cuadrática de mapa (default: FAN_MAP_LOSS_COEFFICIENT).
    map_cap : float
        Límite superior de esta ganancia (default: ETA_FAN_MAP_CAP).

    Returns
    -------
    float
        Δη_map ≥ 0 (ganancia de eficiencia de fan del mecanismo de mapa).
    """
    if phi_design <= 0:
        return 0.0
    delta_phi_rel = (phi_condition - phi_design) / phi_design
    delta_eta_map = k_map * delta_phi_rel ** 2
    return min(delta_eta_map, map_cap)


def compute_combined_fan_efficiency_improvement(
    epsilon_values: List[float],
    phi_values: List[float],
    phi_design: float,
    fan_efficiency_baseline: float,
    tau: float = 0.65,
    epsilon_cap: float = EPSILON_CAP,
    eta_fan_delta_cap: float = ETA_FAN_DELTA_CAP,
    eta_fan_combined_cap: float = ETA_FAN_COMBINED_CAP,
    eta_fan_abs_cap: float = ETA_FAN_ABS_CAP,
    k_map: float = FAN_MAP_LOSS_COEFFICIENT,
    map_cap: float = ETA_FAN_MAP_CAP,
) -> tuple:
    """Mejora de eficiencia de fan combinando mecanismo de perfil y de mapa.

    Mecanismo 1 — Perfil (ya existente):
        Δη_profile = mean_r[(min(ε, ε_cap) − 1) × τ],  cap ≤ ETA_FAN_DELTA_CAP

    Mecanismo 2 — Mapa del fan (nuevo):
        Δη_map = mean_r[k_map × ((φ_r − φ_opt) / φ_opt)²],  cap ≤ ETA_FAN_MAP_CAP

    Combinado:
        Δη_combined = min(Δη_profile + Δη_map, ETA_FAN_COMBINED_CAP)
        η_fan,new = min(η_base × (1 + Δη_combined), ETA_FAN_ABS_CAP)

    Parameters
    ----------
    epsilon_values : list[float]   Ratios ε por sección (mecanismo de perfil).
    phi_values : list[float]       Coeficientes de flujo φ por sección.
    phi_design : float             φ de diseño (crucero, mismo para todas las secciones como media).
    fan_efficiency_baseline : float  η_fan base.
    tau : float                    Coeficiente de transferencia 2D→3D.
    epsilon_cap, eta_fan_delta_cap, eta_fan_combined_cap, eta_fan_abs_cap,
    k_map, map_cap : ver parámetros de cada sub-función.

    Returns
    -------
    eta_fan_new : float         Nueva eficiencia de fan.
    delta_eta_profile : float   Δη del mecanismo de perfil (antes del cap combinado).
    delta_eta_map : float       Δη del mecanismo de mapa (antes del cap combinado).
    delta_eta_applied : float   Δη total aplicado (= η_fan_new − η_base).
    """
    if fan_efficiency_baseline <= 0:
        raise ValueError("fan_efficiency_baseline debe ser positivo.")
    if not epsilon_values:
        raise ValueError("epsilon_values no puede estar vacío.")

    # Mecanismo 1: perfil
    profile_deltas = [(min(eps, epsilon_cap) - 1.0) * tau for eps in epsilon_values]
    delta_eta_profile = min(
        sum(profile_deltas) / len(profile_deltas),
        eta_fan_delta_cap,
    )

    # Mecanismo 2: mapa del fan
    if phi_values and phi_design > 0:
        map_deltas = [compute_fan_map_efficiency_gain(phi, phi_design, k_map, map_cap)
                      for phi in phi_values]
        delta_eta_map = min(
            sum(map_deltas) / len(map_deltas),
            map_cap,
        )
    else:
        delta_eta_map = 0.0

    # Combinado con cap global
    delta_eta_combined = min(delta_eta_profile + delta_eta_map, eta_fan_combined_cap)

    eta_fan_new = min(
        fan_efficiency_baseline * (1.0 + delta_eta_combined),
        eta_fan_abs_cap,
    )
    delta_eta_applied = eta_fan_new - fan_efficiency_baseline

    return eta_fan_new, delta_eta_profile, delta_eta_map, delta_eta_applied


def compute_sfc_improvement(
    sfc_baseline: float,
    delta_eta_fan: float,
    eta_fan_baseline: float,
    k: float = 1.0,
) -> float:
    """Estima el SFC mejorado mediante perturbación de 1er orden.

    SFC_new = SFC_base / (1 + k × Δη_fan / η_fan_base)

    Derivación: si η_fan aumenta en δη, el trabajo del fan disminuye en la misma
    proporción para igual empuje. La fracción k = BPR/(1+BPR) pondera la
    contribución del fan al empuje total (Saravanamuttoo 2017 §5.3).

    Parameters
    ----------
    sfc_baseline : float     SFC base [lb/(lbf·hr)].
    delta_eta_fan : float    Δη_fan aplicado [–] (debe ser ≥ 0).
    eta_fan_baseline : float η_fan base [–].
    k : float                Factor de sensibilidad BPR/(1+BPR) (default: 1.0).

    Returns
    -------
    float  SFC mejorado ≥ 0.
    """
    if sfc_baseline <= 0:
        raise ValueError("sfc_baseline debe ser positivo.")
    if eta_fan_baseline <= 0:
        raise ValueError("eta_fan_baseline debe ser positivo.")
    if delta_eta_fan < 0:
        LOGGER.debug("delta_eta_fan < 0 (%.4f) — SFC aumentará ligeramente.", delta_eta_fan)
    sensitivity = k * delta_eta_fan / eta_fan_baseline
    return max(sfc_baseline / (1.0 + sensitivity), 0.0)


def compute_sfc_reduction_percent(sfc_baseline: float, sfc_new: float) -> float:
    """Porcentaje de reducción de SFC: [(SFC_base − SFC_new) / SFC_base] × 100."""
    if sfc_baseline <= 0:
        raise ValueError("SFC base debe ser positivo.")
    return ((sfc_baseline - sfc_new) / sfc_baseline) * 100.0
