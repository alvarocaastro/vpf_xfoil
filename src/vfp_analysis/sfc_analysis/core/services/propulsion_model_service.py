"""
Service for computing propulsion efficiency and SFC improvements.
"""

from __future__ import annotations

from typing import Dict

from vfp_analysis.sfc_analysis.core.domain.sfc_parameters import EngineBaseline


def compute_propulsion_efficiency(v0: float, vj: float) -> float:
    """
    Compute propulsion efficiency from velocity ratio.

    Parameters
    ----------
    v0 : float
        Flight velocity.
    vj : float
        Jet velocity.

    Returns
    -------
    float
        Propulsion efficiency: eta_prop = 2 / (1 + V_j / V_0)
    """
    if v0 <= 0:
        raise ValueError("Flight velocity must be positive")
    if vj <= 0:
        raise ValueError("Jet velocity must be positive")

    velocity_ratio = vj / v0
    return 2.0 / (1.0 + velocity_ratio)


def compute_fan_efficiency_improvement(
    cl_cd_baseline: float,
    cl_cd_new: float,
    fan_efficiency_baseline: float,
) -> float:
    """
    Estimate improved fan efficiency from aerodynamic efficiency gain.

    Assumes that improvements in blade aerodynamic efficiency produce
    proportional improvements in fan efficiency.

    Parameters
    ----------
    cl_cd_baseline : float
        Baseline aerodynamic efficiency (CL/CD).
    cl_cd_new : float
        New aerodynamic efficiency with VPF (CL/CD).
    fan_efficiency_baseline : float
        Baseline fan efficiency.

    Returns
    -------
    float
        New fan efficiency.
    """
    if cl_cd_baseline <= 0:
        raise ValueError("Baseline CL/CD must be positive")

    # Efficiency gain ratio
    efficiency_ratio = cl_cd_new / cl_cd_baseline
    
    # Read the engine parameters config to get the transfer coefficient
    # For a quick fix, if it fails, default to 1.0 (legacy behaviour)
    transfer_coeff = 1.0
    import yaml
    from pathlib import Path
    try:
        cfg_path = Path(__file__).resolve().parents[5] / "config" / "engine_parameters.yaml"
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            transfer_coeff = float(cfg.get("profile_efficiency_transfer", 1.0))
    except Exception:
        pass

    # Apply proportional improvement to fan efficiency using dampening factor
    eff_gain = (efficiency_ratio - 1.0) * transfer_coeff
    fan_efficiency_new = fan_efficiency_baseline * (1.0 + eff_gain)

    # Cap at reasonable maximum (e.g., 0.96)
    fan_efficiency_new = min(fan_efficiency_new, 0.96)

    return fan_efficiency_new


def compute_sfc_improvement(
    sfc_baseline: float,
    efficiency_gain: float,
) -> float:
    """
    Estimate improved SFC from efficiency gain.

    Simplified relationship:
    SFC_new = SFC_baseline / (1 + efficiency_gain)

    Parameters
    ----------
    sfc_baseline : float
        Baseline Specific Fuel Consumption.
    efficiency_gain : float
        Efficiency improvement factor (0-1).

    Returns
    -------
    float
        New SFC value.
    """
    if efficiency_gain < 0:
        raise ValueError("Efficiency gain must be non-negative")

    sfc_new = sfc_baseline / (1.0 + efficiency_gain)
    return max(sfc_new, 0.0)  # Ensure non-negative


def compute_sfc_reduction_percent(
    sfc_baseline: float,
    sfc_new: float,
) -> float:
    """
    Compute SFC reduction percentage.

    Parameters
    ----------
    sfc_baseline : float
        Baseline SFC.
    sfc_new : float
        New SFC.

    Returns
    -------
    float
        Percentage reduction: ((SFC_baseline - SFC_new) / SFC_baseline) * 100
    """
    if sfc_baseline <= 0:
        raise ValueError("Baseline SFC must be positive")

    reduction = ((sfc_baseline - sfc_new) / sfc_baseline) * 100.0
    return reduction
