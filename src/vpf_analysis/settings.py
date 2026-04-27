"""Paths, XFOIL discovery, airfoil catalogue, and settings loader. Use get_settings() for access."""

from __future__ import annotations

import math
import os
import shutil
from pathlib import Path
from typing import Any, Final, TypedDict

import yaml

from vpf_analysis.config.domain import (  # noqa: F401  (re-exported for backwards compat)
    AirfoilGeometry,
    BladeGeometry,
    FanGeometry,
    PhysicsConstants,
    PipelineSettings,
    XfoilSettings,
)


# Path constants

ROOT_DIR: Final[Path] = Path(__file__).resolve().parents[2]
AIRFOIL_DATA_DIR: Final[Path] = ROOT_DIR / "data" / "airfoils"
RESULTS_DIR: Final[Path] = ROOT_DIR / "results"

STAGE_DIR_NAMES: Final[dict[int, str]] = {
    1: "stage1_airfoil_selection",
    2: "stage2_xfoil_simulations",
    3: "stage3_compressibility_correction",
    4: "stage4_performance_metrics",
    5: "stage5_pitch_kinematics",
    6: "stage6_reverse_thrust",
    7: "stage7_sfc_analysis",
}


def get_stage_dir(stage_num: int) -> Path:
    """Return the canonical results directory for a numbered stage."""
    try:
        return RESULTS_DIR / STAGE_DIR_NAMES[stage_num]
    except KeyError as exc:
        raise ValueError(f"Unknown stage number: {stage_num}") from exc



# XFOIL executable discovery

def _normalize_xfoil_candidate(raw_path: str | Path) -> Path:
    candidate = Path(raw_path).expanduser()
    executable_name = "xfoil.exe" if os.name == "nt" else "xfoil"
    if candidate.name.lower() not in {"xfoil", "xfoil.exe"}:
        return candidate / executable_name
    return candidate


def _build_xfoil_search_paths() -> tuple[Path, ...]:
    raw_candidates: list[Path] = []
    env_path = os.getenv("XFOIL_EXE") or os.getenv("XFOIL_EXECUTABLE")
    if env_path:
        raw_candidates.append(_normalize_xfoil_candidate(env_path))
    raw_candidates.extend([
        _normalize_xfoil_candidate(ROOT_DIR.parent / "XFOIL6.99"),
        _normalize_xfoil_candidate(ROOT_DIR / "XFOIL6.99"),
        _normalize_xfoil_candidate(Path.home() / "Downloads" / "XFOIL6.99"),
    ])
    which_result = shutil.which("xfoil")
    if which_result:
        raw_candidates.append(Path(which_result))
    seen: set[str] = set()
    unique: list[Path] = []
    for c in raw_candidates:
        key = str(c).lower()
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return tuple(unique)


def _resolve_xfoil_executable() -> Path:
    for candidate in XFOIL_SEARCH_PATHS:
        if candidate.is_file():
            return candidate
    return XFOIL_SEARCH_PATHS[0]


XFOIL_SEARCH_PATHS: Final[tuple[Path, ...]] = _build_xfoil_search_paths()
XFOIL_EXECUTABLE: Final[Path] = _resolve_xfoil_executable()

MACH_DEFAULT: Final[float] = 0.2
N_CRIT_DEFAULT: Final[float] = 9.0


# Airfoil definitions


class AirfoilSpec(TypedDict):
    """Specification of a single airfoil for the analysis."""
    name: str
    dat_file: str
    family: str
    comment: str


def _load_airfoils() -> list[AirfoilSpec]:
    path = ROOT_DIR / "config" / "airfoils.yaml"
    with path.open("r", encoding="utf-8") as f:
        data: dict = yaml.safe_load(f)
    return data["airfoils"]


AIRFOILS: Final[list[AirfoilSpec]] = _load_airfoils()


# Settings cache

_SETTINGS_CACHE: PipelineSettings | None = None


def get_settings(
    analysis_config_path: Path | None = None,
) -> PipelineSettings:
    """Return cached PipelineSettings. First call loads YAML; subsequent calls are instant."""
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE
    _SETTINGS_CACHE = _load_settings(analysis_config_path)
    return _SETTINGS_CACHE


def clear_settings_cache() -> None:
    """Invalidate the settings cache (useful in tests)."""
    global _SETTINGS_CACHE
    _SETTINGS_CACHE = None


def _load_settings(config_path: Path | None) -> PipelineSettings:
    """Load and validate parameters from YAML files."""
    if config_path is None:
        config_path = ROOT_DIR / "config" / "analysis_config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f)

    flight_conditions: list[str] = raw["flight_conditions"]
    blade_sections: list[str] = raw["blade_sections"]

    reynolds_table = {
        flight: {section: float(v) for section, v in sections.items()}
        for flight, sections in raw["reynolds"].items()
    }
    ncrit_table = {k: float(v) for k, v in raw["ncrit"].items()}
    target_mach = {k: float(v) for k, v in raw["target_mach"].items()}

    alpha_cfg = raw["alpha"]
    sel_cfg = raw.get("selection_alpha", alpha_cfg)
    sel = raw.get("selection", {})

    fg = raw["fan_geometry"]
    rpm = float(fg["rpm"])
    fan = FanGeometry(
        rpm=rpm,
        omega_rad_s=rpm * 2.0 * math.pi / 60.0,
        radii_m={k: float(v) for k, v in fg["radius"].items()},
        axial_velocity_m_s={k: float(v) for k, v in fg["axial_velocity"].items()},
    )

    bg = raw["blade_geometry"]
    blade = BladeGeometry(
        num_blades=int(bg["num_blades"]),
        solidity={k: float(v) for k, v in bg["solidity"].items()},
        theta_camber_deg=float(bg["theta_camber_deg"]),
    )

    ag = raw.get("airfoil_geometry", {})
    airfoil_geom = AirfoilGeometry(
        thickness_ratio=float(ag.get("thickness_ratio", 0.10)),
        korn_kappa=float(ag.get("korn_kappa", 0.87)),
    )

    # xfoil settings (optional section, falls back to hardcoded defaults)
    xf_raw = raw.get("xfoil", {})
    import dataclasses as _dc
    xfoil_settings = _dc.replace(
        XfoilSettings(),
        **{k: v for k, v in {
            "ITER":                 xf_raw.get("iter"),
            "TIMEOUT_SELECTION_S":  xf_raw.get("timeout_selection_s"),
            "TIMEOUT_FINAL_S":      xf_raw.get("timeout_final_s"),
            "MAX_RETRIES":          xf_raw.get("max_retries"),
            "RETRY_WAIT_S":         xf_raw.get("retry_wait_s"),
        }.items() if v is not None}
    )

    cruise_alpha_min_raw = raw.get("cruise_alpha_min", {})
    cruise_alpha_min = {k: float(v) for k, v in cruise_alpha_min_raw.items()}

    xfoil_cache = bool(raw.get("xfoil_cache", False))

    return PipelineSettings(
        physics=PhysicsConstants(),
        xfoil=xfoil_settings,
        flight_conditions=flight_conditions,
        blade_sections=blade_sections,
        reynolds_table=reynolds_table,
        ncrit_table=ncrit_table,
        target_mach=target_mach,
        reference_mach=float(raw.get("reference_mach", 0.2)),
        alpha_min=float(alpha_cfg["min"]),
        alpha_max=float(alpha_cfg["max"]),
        alpha_step=float(alpha_cfg["step"]),
        selection_alpha_min=float(sel_cfg["min"]),
        selection_alpha_max=float(sel_cfg["max"]),
        selection_alpha_step=float(sel_cfg["step"]),
        selection_reynolds=float(sel.get("reynolds", 3.0e6)),
        selection_ncrit=float(sel.get("ncrit", 7.0)),
        fan=fan,
        blade=blade,
        airfoil_geometry=airfoil_geom,
        cruise_alpha_min=cruise_alpha_min,
        xfoil_cache=xfoil_cache,
        results_dir=RESULTS_DIR,
    )
