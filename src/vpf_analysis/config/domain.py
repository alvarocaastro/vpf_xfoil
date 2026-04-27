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
    ALPHA_MIN_OPT_DEG: float = 3.0
    """Minimum angle for second-peak search [°]. Below ~3° XFOIL shows a laminar-bubble artefact peak."""

    CL_MIN_3D: float = 0.30
    """Minimum CL for a point to be considered operational in 3D polars."""

    CL_MIN_VIABLE: float = 0.50
    """Minimum CL for a fan blade to be considered aerodynamically viable.
    Conservative lower bound allowing detection of the true CL/CD optimum in
    low-loading conditions (climb CL_opt ≈ 0.5–0.65).
    Ref: Cumpsty (2004) ch. 8 — fan blade CL design range 0.4–1.0.
    """

    # Cascade corrections
    CARTER_M_NACA6: float = 0.23
    """Carter's rule m coefficient for NACA 6-series (a/c = 0.5)."""

    WEINIG_SIGMA_MIN: float = 0.10
    """Minimum solidity for Weinig factor validity."""

    WEINIG_SIGMA_MAX: float = 2.50
    """Maximum solidity for Weinig factor validity."""

    # 3D rotational corrections
    SNEL_A: float = 3.0
    """Empirical coefficient *a* in Snel et al. (1994) rotational correction: ΔCL = a·(c/r)²·CL_2D.
    Originally derived for wind turbine rotors (attached flow, low Re). Applied here as an
    approximation for turbofan fan blades — no published validation for cascade conditions exists.
    Ref: Snel, H. et al. (1994), ECN-C-94-107. Sensitivity to a ∈ [2, 4] should be checked.
    """

    DU_SELIG_A: float = 1.6
    """Leading coefficient in Du & Selig (1998) rotational correction: ΔCL = 1.6·f(λ_r)·(c/r)^1.6.
    Alternative to Snel et al.; includes a tip-speed-ratio function f(λ_r) = λ_r²/(λ_r²+1).
    Also derived for wind turbines; applied here as a second independent estimate.
    Ref: Du, Z. & Selig, M. (1998), AIAA-1998-0021.
    """

    # Efficient fan design zone (φ-ψ diagram)
    # NOTE: Bounds from Dixon & Hall (2013) apply to low-speed fans at mid-span.
    # Hub/root sections (r=0.53 m) routinely show φ > 1.0 in cruise — this is expected
    # and does not indicate a design error. Use these limits as reference guides only.
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
    rpm: Dict[str, float]          # RPM per flight condition
    omega_rad_s: Dict[str, float]  # ω [rad/s] per flight condition
    radii_m: Dict[str, float]
    axial_velocity_m_s: Dict[str, float]


@dataclass
class BladeGeometry:
    """Blade geometry for cascade and rotational corrections.

    ``solidity`` is the primary input (σ = c·Z/2πr).  Actual chord in metres
    can be recovered as  c = σ · 2π · r / Z  when a dimensional value is needed
    (e.g. BEM thrust integration in Stage 6).
    """
    num_blades: int
    solidity: Dict[str, float]
    theta_camber_deg: float


@dataclass
class AirfoilGeometry:
    """Airfoil geometric parameters for compressibility corrections."""
    thickness_ratio: float
    korn_kappa: float


@dataclass(frozen=True)
class ResolvedSelectionCondition:
    """One airfoil-selection condition with Re and Ncrit already resolved from the config tables.

    Alpha range and reference Mach are shared across all conditions and live in PipelineSettings.
    ``weight`` is normalised to [0, 1] and the set of conditions sums to 1.0.
    """
    label: str                # e.g. "cruise_mid"
    flight_condition: str     # key in reynolds/ncrit tables, e.g. "cruise"
    section: str              # "root" | "mid_span" | "tip"
    reynolds: float
    ncrit: float
    weight: float


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

    # Shared alpha sweep used for all selection conditions
    selection_alpha_min: float = -2.0
    selection_alpha_max: float = 15.0
    selection_alpha_step: float = 0.15

    # Mission-weighted conditions evaluated during airfoil selection (Stage 1).
    # Populated by settings.py from analysis_config.yaml selection.conditions[].
    selection_conditions: List[ResolvedSelectionCondition] = field(default_factory=list)

    fan: FanGeometry = field(default_factory=lambda: FanGeometry(
        rpm={}, omega_rad_s={}, radii_m={}, axial_velocity_m_s={},
    ))
    blade: BladeGeometry = field(default_factory=lambda: BladeGeometry(
        num_blades=16, solidity={}, theta_camber_deg=8.0,
    ))
    airfoil_geometry: AirfoilGeometry = field(default_factory=lambda: AirfoilGeometry(
        thickness_ratio=0.10, korn_kappa=0.87,
    ))

    # Per-section minimum alpha for peak search at the cruise (design) condition.
    # Wave drag at M=0.93 shifts the polar peak structure; a lower alpha_min than
    # the global ALPHA_MIN_OPT_DEG is needed to capture the stabilised operating point.
    cruise_alpha_min: Dict[str, float] = field(default_factory=lambda: {
        "root": 2.5, "mid_span": 2.2, "tip": 2.0,
    })

    # When True, XFOIL runs are skipped if a cached polar with the same
    # (airfoil, Re, M, Ncrit, alpha range) key exists in results/.polar_cache/.
    xfoil_cache: bool = False

    results_dir: Path = field(default_factory=lambda: Path("results"))
