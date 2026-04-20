"""
propulsion_model_service.py
---------------------------
Physical sub-models for computing SFC improvements via VPF.

Profile-to-fan efficiency transfer model:
    ε_eff           = min(ε, EPSILON_CAP)
    Δη_profile(r)   = (ε_eff − 1) × τ
    Δη_fan          = mean_r(Δη_profile),  capped at ETA_FAN_DELTA_CAP
    η_fan,new       = min(η_base × (1 + Δη_fan), ETA_FAN_ABS_CAP)
    SFC_new         = SFC_base / (1 + k × Δη_applied / η_base)
    k = BPR/(1+BPR) (Saravanamuttoo 2017 eq. 5.14)

τ (profile_efficiency_transfer) damps the 3D losses that prevent the 2D
profile improvement from fully transferring to the complete fan.
EPSILON_CAP bounds ε to physically credible values in a 3D cascade.
"""

from __future__ import annotations

import logging
from typing import List, Tuple  # noqa: F401 — Tuple used in type comments

from vfp_analysis.stage7_sfc_analysis.core.domain.sfc_parameters import (
    EPSILON_CAP,
    ETA_FAN_ABS_CAP,
    ETA_FAN_COMBINED_CAP,
    ETA_FAN_DELTA_CAP,
    ETA_FAN_MAP_CAP,
    FAN_MAP_LOSS_COEFFICIENT,
)

LOGGER = logging.getLogger(__name__)


def compute_bypass_sensitivity_factor(bypass_ratio: float) -> float:
    """Net thrust fraction produced by the bypass (fan) stream.

    k = BPR / (1 + BPR)

    Derivation: for a separate-flow turbofan with bypass ratio BPR,
    neglecting hot-jet velocity differences, the fan produces
    k = BPR/(1+BPR) of the total momentum thrust. First-order perturbation
    of TSFC with δη_fan gives: ΔTSFC/TSFC ≈ −k · δη_fan / η_fan.

    Ref: Saravanamuttoo et al. (2017) *Gas Turbine Theory*, 7th ed., eq. 5.14.

    Parameters
    ----------
    bypass_ratio : float  Bypass ratio (BPR > 0).

    Returns
    -------
    float  Factor k ∈ (0, 1).
    """
    if bypass_ratio <= 0:
        raise ValueError("bypass_ratio must be positive.")
    return bypass_ratio / (1.0 + bypass_ratio)


def compute_propulsion_efficiency(v0: float, vj: float) -> float:
    """Propulsive efficiency: η_prop = 2 / (1 + V_j / V_0).

    Parameters
    ----------
    v0 : float  Flight speed [m/s].
    vj : float  Jet exit speed [m/s].
    """
    if v0 <= 0:
        raise ValueError("Flight speed must be positive.")
    if vj <= 0:
        raise ValueError("Jet speed must be positive.")
    return 2.0 / (1.0 + vj / v0)


def compute_fan_efficiency_improvement(
    epsilon_values: List[float],
    fan_efficiency_baseline: float,
    tau: float = 0.65,
    epsilon_cap: float = EPSILON_CAP,
    eta_fan_delta_cap: float = ETA_FAN_DELTA_CAP,
    eta_fan_abs_cap: float = ETA_FAN_ABS_CAP,
) -> Tuple[float, float, float]:
    """Estimate the fan efficiency improvement from the per-section ε ratios.

    Procedure:
        1. Per section: ε_eff = min(ε, epsilon_cap)
        2. Δη_profile(r) = (ε_eff − 1) × τ
        3. Δη_fan_raw = mean(Δη_profile)
        4. Δη_fan_capped = min(Δη_fan_raw, eta_fan_delta_cap)
        5. η_fan,new = min(η_base × (1 + Δη_fan_capped), eta_fan_abs_cap)

    Parameters
    ----------
    epsilon_values : list[float]
        Per-section ε ratios [–] (= CL/CD_vpf / CL/CD_fixed).
    fan_efficiency_baseline : float
        Baseline η_fan [–].
    tau : float
        2D→3D transfer coefficient (default: 0.65).
        Ref: Cumpsty (2004) §8; Peretz & Gany (1992).
    epsilon_cap : float
        Physical cap on ε before applying τ (default: EPSILON_CAP = 1.10).
        Ref: Cumpsty (2004) p. 280; Wisler (1998) VKI.
    eta_fan_delta_cap : float
        Maximum absolute η_fan improvement (default: ETA_FAN_DELTA_CAP = 0.04).
        Ref: Cumpsty (2004) p. 280.
    eta_fan_abs_cap : float
        Absolute η_fan upper bound (default: ETA_FAN_ABS_CAP = 0.96).
        Ref: Cumpsty (2004) ch. 8.

    Returns
    -------
    eta_fan_new : float     Nueva eficiencia de fan tras aplicar todos los caps.
    delta_eta_raw : float   Δη_fan calculado antes del cap de delta.
    delta_eta_applied : float  Δη_fan realmente aplicado (= η_fan_new − η_base).
    """
    if fan_efficiency_baseline <= 0:
        raise ValueError("fan_efficiency_baseline must be positive.")
    if not epsilon_values:
        raise ValueError("epsilon_values cannot be empty.")

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
    """Fan efficiency gain from the fan-map mechanism (flow coefficient φ).

    A fixed-pitch fan is forced to operate at points where φ = Va/U ≠ φ_opt
    when the flight condition changes (Va varies between phases). This deviation
    introduces quadratic losses in the fan map that VPF partially recovers
    by maintaining optimal incidence.

        Δη_map = k_map × ((φ − φ_opt) / φ_opt)²    [simple parabolic model]
        Δη_map_capped = min(Δη_map, map_cap)

    This gain is **independent and additive** to the profile mechanism (τ-mediated):
    the map loss does not pass through the 2D→3D τ chain — it is a system
    loss directly recoverable by adjusting the pitch schedule.

    Ref: Cumpsty (2004) *Compressor Aerodynamics*, ch. 8 (fig. 8.10);
         Dickens & Day (2011). "The Design of Highly Loaded Axial Compressors".
         J. Turbomach. 133(3):031007.

    Parameters
    ----------
    phi_condition : float
        Flow coefficient at the off-design condition: Va_cond / U_section.
    phi_design : float
        Design flow coefficient (cruise): Va_cruise / U_section.
    k_map : float
        Quadratic map-loss coefficient (default: FAN_MAP_LOSS_COEFFICIENT).
    map_cap : float
        Upper bound on this gain (default: ETA_FAN_MAP_CAP).

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
    """Fan efficiency improvement combining profile and map mechanisms.

    Mechanism 1 — Profile (existing):
        Δη_profile = mean_r[(min(ε, ε_cap) − 1) × τ],  cap ≤ ETA_FAN_DELTA_CAP

    Mechanism 2 — Fan map (new):
        Δη_map = mean_r[k_map × ((φ_r − φ_opt) / φ_opt)²],  cap ≤ ETA_FAN_MAP_CAP

    Combined:
        Δη_combined = min(Δη_profile + Δη_map, ETA_FAN_COMBINED_CAP)
        η_fan,new = min(η_base × (1 + Δη_combined), ETA_FAN_ABS_CAP)

    Parameters
    ----------
    epsilon_values : list[float]   Per-section ε ratios (profile mechanism).
    phi_values : list[float]       Per-section flow coefficients φ.
    phi_design : float             Design φ (cruise, averaged across sections).
    fan_efficiency_baseline : float  Baseline η_fan.
    tau : float                    2D→3D transfer coefficient.
    epsilon_cap, eta_fan_delta_cap, eta_fan_combined_cap, eta_fan_abs_cap,
    k_map, map_cap : see parameters of each sub-function.

    Returns
    -------
    eta_fan_new : float         Nueva eficiencia de fan.
    delta_eta_profile : float   Δη del mecanismo de perfil (antes del cap combinado).
    delta_eta_map : float       Δη del mecanismo de mapa (antes del cap combinado).
    delta_eta_applied : float   Δη total aplicado (= η_fan_new − η_base).
    """
    if fan_efficiency_baseline <= 0:
        raise ValueError("fan_efficiency_baseline must be positive.")
    if not epsilon_values:
        raise ValueError("epsilon_values cannot be empty.")

    # Mechanism 1: profile
    profile_deltas = [(min(eps, epsilon_cap) - 1.0) * tau for eps in epsilon_values]
    delta_eta_profile = min(
        sum(profile_deltas) / len(profile_deltas),
        eta_fan_delta_cap,
    )

    # Mechanism 2: fan map
    if phi_values and phi_design > 0:
        map_deltas = [compute_fan_map_efficiency_gain(phi, phi_design, k_map, map_cap)
                      for phi in phi_values]
        delta_eta_map = min(
            sum(map_deltas) / len(map_deltas),
            map_cap,
        )
    else:
        delta_eta_map = 0.0

    # Combined with global cap
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
    """Estimate the improved SFC via first-order perturbation.

    SFC_new = SFC_base / (1 + k × Δη_fan / η_fan_base)

    Derivation: if η_fan increases by δη, the fan work decreases by the same
    proportion for equal thrust. The fraction k = BPR/(1+BPR) weights the
    fan contribution to total thrust (Saravanamuttoo 2017 §5.3).

    Parameters
    ----------
    sfc_baseline : float     Baseline SFC [lb/(lbf·hr)].
    delta_eta_fan : float    Applied Δη_fan [–] (should be ≥ 0).
    eta_fan_baseline : float Baseline η_fan [–].
    k : float                Sensitivity factor BPR/(1+BPR) (default: 1.0).

    Returns
    -------
    float  Improved SFC ≥ 0.
    """
    if sfc_baseline <= 0:
        raise ValueError("sfc_baseline must be positive.")
    if eta_fan_baseline <= 0:
        raise ValueError("eta_fan_baseline must be positive.")
    if delta_eta_fan < 0:
        LOGGER.debug("delta_eta_fan < 0 (%.4f) — SFC will increase slightly.", delta_eta_fan)
    sensitivity = k * delta_eta_fan / eta_fan_baseline
    return max(sfc_baseline / (1.0 + sensitivity), 0.0)


def compute_sfc_reduction_percent(sfc_baseline: float, sfc_new: float) -> float:
    """Percentage SFC reduction: [(SFC_base − SFC_new) / SFC_base] × 100."""
    if sfc_baseline <= 0:
        raise ValueError("Baseline SFC must be positive.")
    return ((sfc_baseline - sfc_new) / sfc_baseline) * 100.0
