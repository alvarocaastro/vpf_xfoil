"""
Configuration loader for YAML-based analysis configuration.

This module loads simulation parameters from a YAML configuration file,
providing a centralized way to manage all analysis settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Final

import yaml

from vfp_analysis import config as base_config

_CONFIG_CACHE: Dict[str, Any] | None = None


def load_config(config_path: Path | None = None) -> Dict[str, Any]:
    """
    Load analysis configuration from YAML file.

    Parameters
    ----------
    config_path : Path, optional
        Path to the configuration file. If None, uses default location.

    Returns
    -------
    Dict[str, Any]
        Configuration dictionary with all analysis parameters.
    """
    global _CONFIG_CACHE

    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    if config_path is None:
        config_path = base_config.ROOT_DIR / "config" / "analysis_config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        _CONFIG_CACHE = yaml.safe_load(f)

    return _CONFIG_CACHE


def get_reynolds_table() -> Dict[str, Dict[str, float]]:
    """Get Reynolds numbers table from configuration."""
    cfg = load_config()
    reynolds_raw = cfg["reynolds"]
    # Convert all values to float (YAML may load scientific notation as strings)
    reynolds_typed: Dict[str, Dict[str, float]] = {}
    for flight, sections in reynolds_raw.items():
        reynolds_typed[flight] = {
            section: float(value) for section, value in sections.items()
        }
    return reynolds_typed


def get_ncrit_table() -> Dict[str, float]:
    """Get Ncrit values table from configuration."""
    cfg = load_config()
    ncrit_raw = cfg["ncrit"]
    # Convert all values to float
    return {flight: float(value) for flight, value in ncrit_raw.items()}


def get_target_mach() -> Dict[str, float]:
    """Get target Mach numbers from configuration."""
    cfg = load_config()
    mach_raw = cfg["target_mach"]
    # Convert all values to float
    return {flight: float(value) for flight, value in mach_raw.items()}


def get_alpha_range() -> Dict[str, float]:
    """Get angle of attack range from configuration."""
    cfg = load_config()
    alpha_raw = cfg["alpha"]
    # Convert all values to float
    return {key: float(value) for key, value in alpha_raw.items()}


def get_selection_alpha_range() -> Dict[str, float]:
    """Get angle of attack range for selection stage."""
    cfg = load_config()
    alpha_raw = cfg["selection_alpha"]
    # Convert all values to float
    return {key: float(value) for key, value in alpha_raw.items()}


def get_selection_reynolds() -> float:
    """Get Reynolds number used in the airfoil selection stage."""
    cfg = load_config()
    return float(cfg["selection"]["reynolds"])


def get_selection_ncrit() -> float:
    """Get Ncrit used in the airfoil selection stage."""
    cfg = load_config()
    return float(cfg["selection"]["ncrit"])


def get_plot_settings() -> Dict[str, Any]:
    """Get plotting settings from configuration."""
    cfg = load_config()
    return cfg["plotting"]


def get_reference_mach() -> float:
    """Get reference Mach number used for XFOIL simulations (incompressible baseline)."""
    cfg = load_config()
    return float(cfg["reference_mach"])


def get_flight_conditions() -> list[str]:
    """Get list of flight conditions from configuration."""
    cfg = load_config()
    return cfg["flight_conditions"]


def get_blade_sections() -> list[str]:
    """Get list of blade sections from configuration."""
    cfg = load_config()
    return cfg["blade_sections"]


def get_airfoil_thickness_ratio() -> float:
    """Get airfoil thickness ratio t/c for compressibility corrections."""
    cfg = load_config()
    return float(cfg["airfoil_geometry"]["thickness_ratio"])


def get_korn_kappa() -> float:
    """Get Korn's equation kappa factor for drag divergence estimation."""
    cfg = load_config()
    return float(cfg["airfoil_geometry"]["korn_kappa"])


def get_fan_rpm() -> float:
    """Get fan design rotational speed [RPM]."""
    cfg = load_config()
    return float(cfg["fan_geometry"]["rpm"])


def get_blade_radii() -> Dict[str, float]:
    """Get blade section radii [m] (root, mid_span, tip)."""
    cfg = load_config()
    return {k: float(v) for k, v in cfg["fan_geometry"]["radius"].items()}


def get_axial_velocities() -> Dict[str, float]:
    """Get axial flow velocity [m/s] per flight condition."""
    cfg = load_config()
    return {k: float(v) for k, v in cfg["fan_geometry"]["axial_velocity"].items()}


def get_blade_geometry() -> Dict[str, Any]:
    """Get blade geometry for cascade and rotational correction analysis.

    Returns a dict with:
        num_blades (int): number of fan blades Z
        chord (dict[str, float]): blade chord c [m] per section
        theta_camber_deg (float): camber angle θ [°] for Carter's rule
    """
    cfg = load_config()
    bg = cfg["blade_geometry"]
    return {
        "num_blades": int(bg["num_blades"]),
        "chord": {k: float(v) for k, v in bg["chord"].items()},
        "theta_camber_deg": float(bg["theta_camber_deg"]),
    }


def get_mission_profile() -> Dict[str, Any]:
    """Get mission profile parameters from engine_parameters.yaml.

    Returns a dict with:
        phases (dict): {condition: {duration_min, thrust_fraction}}
        design_thrust_kN (float): sea-level static thrust per engine [kN]
        fuel_price_usd_per_kg (float): jet-A1 price [USD/kg]
    """
    import yaml as _yaml
    engine_cfg_path = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    with engine_cfg_path.open("r", encoding="utf-8") as f:
        cfg = _yaml.safe_load(f)
    mission = cfg.get("mission", {})
    return {
        "phases": {
            k: {"duration_min": float(v["duration_min"]),
                "thrust_fraction": float(v["thrust_fraction"])}
            for k, v in mission.get("phases", {}).items()
        },
        "design_thrust_kN": float(mission.get("design_thrust_kN", 105.0)),
        "fuel_price_usd_per_kg": float(mission.get("fuel_price_usd_per_kg", 0.90)),
    }


def clear_cache() -> None:
    """Clear the configuration cache (useful for testing)."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
