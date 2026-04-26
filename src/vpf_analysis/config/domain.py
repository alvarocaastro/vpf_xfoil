"""Configuration dataclasses for the VPF analysis pipeline.

Contains all typed configuration objects. Loaded and cached by settings.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class PhysicsConstants:
    """Empirical coefficients and physical limits for the VPF aerodynamic pipeline."""

    # Optimal incidence detection (second CL/CD peak)
    ALPHA_MIN_OPT_DEG: float = 1.0
    """Minimum angle for optimal peak search [°]."""

    CL_MIN_3D: float = 0.30
    """Minimum CL for a point to be considered operational in 3D polars."""

    # Cascade corrections
    CARTER_M_NACA6: float = 0.23
    """Carter's rule m coefficient for NACA 6-series (a/c = 0.5)."""

    WEINIG_SIGMA_MIN: float = 0.10
    """Minimum solidity for Weinig factor validity."""

    WEINIG_SIGMA_MAX: float = 2.50
    """Maximum solidity for Weinig factor validity."""

    # 3D rotational corrections (Snel et al.)
    SNEL_A: float = 3.0
    """Empirical coefficient a in Snel's rotational correction for attached flow."""

    # Efficient fan design zone (φ-ψ diagram)
    PHI_DESIGN_MIN: float = 0.35
    PHI_DESIGN_MAX: float = 0.55
    PSI_DESIGN_MIN: float = 0.25
    PSI_DESIGN_MAX: float = 0.50

    # Minimum quality of a valid polar
    POLAR_MIN_ROWS: int = 10
    POLAR_CL_MAX_PHYSICAL: float = 2.5
    POLAR_CD_MIN_PHYSICAL: float = 1e-6

    # Physical operating ranges
    REYNOLDS_MIN: float = 1e4
    REYNOLDS_MAX: float = 1e9
    MACH_MAX_SUBSONIC: float = 0.99
    MACH_KT_VALID_MAX: float = 0.87


@dataclass(frozen=True)
class XfoilSettings:
    """XFOIL integration configuration."""

    ITER: int = 200
    TIMEOUT_SELECTION_S: float = 60.0
    TIMEOUT_FINAL_S: float = 180.0
    MAX_RETRIES: int = 3
    RETRY_WAIT_S: float = 1.0
    CONVERGENCE_WARN_KEYWORDS: tuple = (
        "VISCAL",
        "Convergence failed",
        "RMSBL",
        "MRCHDU",
        "MRCHD",
    )


@dataclass
class FanGeometry:
    """Variable-pitch fan geometry."""
    rpm: float
    omega_rad_s: float
    radii_m: Dict[str, float]
    axial_velocity_m_s: Dict[str, float]


@dataclass
class BladeGeometry:
    """Blade geometry for cascade and rotational corrections."""
    num_blades: int
    chord_m: Dict[str, float]
    theta_camber_deg: float


@dataclass
class AirfoilGeometry:
    """Airfoil geometric parameters for compressibility corrections."""
    thickness_ratio: float
    korn_kappa: float


@dataclass
class PipelineSettings:
    """Full pipeline configuration loaded from YAML files.

    Use ``get_settings()`` from settings.py for the cached singleton.
    """
    physics: PhysicsConstants = field(default_factory=PhysicsConstants)
    xfoil: XfoilSettings = field(default_factory=XfoilSettings)

    flight_conditions: List[str] = field(default_factory=list)
    blade_sections: List[str] = field(default_factory=list)

    reynolds_table: Dict[str, Dict[str, float]] = field(default_factory=dict)
    ncrit_table: Dict[str, float] = field(default_factory=dict)
    target_mach: Dict[str, float] = field(default_factory=dict)
    reference_mach: float = 0.2

    alpha_min: float = -5.0
    alpha_max: float = 23.0
    alpha_step: float = 0.15

    selection_alpha_min: float = -5.0
    selection_alpha_max: float = 20.0
    selection_alpha_step: float = 0.15
    selection_reynolds: float = 3.0e6
    selection_ncrit: float = 4.0   # turbomachinery Tu~0.5-1% → Ncrit~4

    fan: FanGeometry = field(default_factory=lambda: FanGeometry(
        rpm=2200.0, omega_rad_s=230.4, radii_m={}, axial_velocity_m_s={},
    ))
    blade: BladeGeometry = field(default_factory=lambda: BladeGeometry(
        num_blades=16, chord_m={}, theta_camber_deg=8.0,
    ))
    airfoil_geometry: AirfoilGeometry = field(default_factory=lambda: AirfoilGeometry(
        thickness_ratio=0.10, korn_kappa=0.87,
    ))

    results_dir: Path = field(default_factory=lambda: Path("results"))
