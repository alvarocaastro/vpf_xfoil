"""YAML configuration loader with a module-level cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from vpf_analysis import settings as base_config

_CONFIG_CACHE: dict[str, Any] | None = None


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load and cache analysis_config.yaml. Subsequent calls return the cache."""
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


def get_reynolds_table() -> dict[str, dict[str, float]]:
    """Reynolds numbers per (flight condition, blade section)."""
    return {
        flight: {section: float(v) for section, v in sections.items()}
        for flight, sections in load_config()["reynolds"].items()
    }


def get_ncrit_table() -> dict[str, float]:
    return {k: float(v) for k, v in load_config()["ncrit"].items()}


def get_target_mach() -> dict[str, float]:
    return {k: float(v) for k, v in load_config()["target_mach"].items()}


def get_alpha_range() -> dict[str, float]:
    return {k: float(v) for k, v in load_config()["alpha"].items()}


def get_selection_alpha_range() -> dict[str, float]:
    return {k: float(v) for k, v in load_config()["selection_alpha"].items()}


def get_selection_reynolds() -> float:
    return float(load_config()["selection"]["reynolds"])


def get_selection_ncrit() -> float:
    return float(load_config()["selection"]["ncrit"])


def get_plot_settings() -> dict[str, Any]:
    return load_config()["plotting"]


def get_reference_mach() -> float:
    return float(load_config()["reference_mach"])


def get_flight_conditions() -> list[str]:
    return load_config()["flight_conditions"]


def get_blade_sections() -> list[str]:
    return load_config()["blade_sections"]


def get_airfoil_thickness_ratio() -> float:
    return float(load_config()["airfoil_geometry"]["thickness_ratio"])


def get_korn_kappa() -> float:
    return float(load_config()["airfoil_geometry"]["korn_kappa"])


def get_fan_rpm() -> float:
    return float(load_config()["fan_geometry"]["rpm"])


def get_blade_radii() -> dict[str, float]:
    return {k: float(v) for k, v in load_config()["fan_geometry"]["radius"].items()}


def get_axial_velocities() -> dict[str, float]:
    return {k: float(v) for k, v in load_config()["fan_geometry"]["axial_velocity"].items()}


def get_blade_geometry() -> dict[str, Any]:
    """Blade cascade geometry: num_blades, solidity per section, theta_camber_deg."""
    bg = load_config()["blade_geometry"]
    return {
        "num_blades": int(bg["num_blades"]),
        "solidity": {k: float(v) for k, v in bg["solidity"].items()},
        "theta_camber_deg": float(bg["theta_camber_deg"]),
    }


def get_mission_profile() -> dict[str, Any]:
    """Mission profile from engine_parameters.yaml: phases, design_thrust_kN, fuel_price."""
    engine_cfg_path = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    with engine_cfg_path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    mission = cfg.get("mission", {})
    return {
        "phases": {
            k: {"duration_min": float(v["duration_min"]), "thrust_fraction": float(v["thrust_fraction"])}
            for k, v in mission.get("phases", {}).items()
        },
        "design_thrust_kN": float(mission.get("design_thrust_kN", 105.0)),
        "fuel_price_usd_per_kg": float(mission.get("fuel_price_usd_per_kg", 0.90)),
    }


def clear_cache() -> None:
    """Invalidate the config cache (useful in tests)."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
