"""
settings.py
-----------
Fuente única de verdad para todas las constantes físicas y parámetros de simulación
del pipeline VPF. Cero "magic numbers" repartidos por el código.

Organización
------------
PhysicsConstants   — coeficientes empíricos y límites físicos (invariantes)
XfoilSettings      — parámetros de la integración con XFOIL
PipelineSettings   — configuración completa cargada de los YAML

Uso típico
----------
    from vfp_analysis.settings import get_settings
    cfg = get_settings()
    print(cfg.physics.SNEL_A)          # → 3.0
    print(cfg.xfoil.TIMEOUT_FINAL_S)   # → 180.0
    print(cfg.flight_conditions)       # → ['takeoff', 'climb', ...]
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

from vfp_analysis import config as _base

# ---------------------------------------------------------------------------
# Constantes físicas / coeficientes empíricos (no cambian con el config YAML)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PhysicsConstants:
    """Coeficientes empíricos y límites físicos del análisis aerodinámico VPF.

    Todos los valores tienen referencia bibliográfica en el docstring del campo.
    """

    # ------------------------------------------------------------------
    # Detección de incidencia óptima (segundo pico de CL/CD)
    # ------------------------------------------------------------------
    ALPHA_MIN_OPT_DEG: float = 1.0
    """Ángulo mínimo para buscar el pico óptimo [°].
    Avoids the very-low-alpha (< 1°) laminar separation bubble artefact
    predicted by XFOIL while still allowing the true Mach-dependent peak
    (typically 2.2–3.5° across fan operating conditions) to be found.
    Using 3° was too conservative: it forced alpha_opt ≥ 3° even when the
    real 2D/KT peak at cruise M=0.93 lies near 2.35°.
    Ref: Drela (1989) XFOIL docs; Selig & McGranahan (2004)."""

    CL_MIN_3D: float = 0.30
    """CL mínimo para considerar un punto como operativo en polares 3D.
    Ref: criterio de diseño de fans de alto bypass (Cumpsty 2004, cap. 9)."""

    # ------------------------------------------------------------------
    # Correcciones de cascada
    # ------------------------------------------------------------------
    CARTER_M_NACA6: float = 0.23
    """Coeficiente m de la regla de Carter para NACA 6-series (a/c = 0.5).
    Ref: Carter (1950), NACA TN-2273, Table 1; ESDU 05017."""

    WEINIG_SIGMA_MIN: float = 0.10
    """Solidez mínima de validez del factor de Weinig.
    Ref: Weinig (1935); Dixon & Hall (2013), ec. 3.54."""

    WEINIG_SIGMA_MAX: float = 2.50
    """Solidez máxima de validez del factor de Weinig."""

    # ------------------------------------------------------------------
    # Correcciones rotacionales 3D (Snel et al.)
    # ------------------------------------------------------------------
    SNEL_A: float = 3.0
    """Coeficiente empírico a de la corrección rotacional de Snel para flujo adherido.
    ΔCL_rot = a · (c/r)² · CL_2D
    Ref: Snel, Houwink & Bosschers (1994), ECN-C--94-004, sec. 2.3."""

    # ------------------------------------------------------------------
    # Zona de diseño eficiente del fan (diagrama φ-ψ)
    # ------------------------------------------------------------------
    PHI_DESIGN_MIN: float = 0.35
    """Límite inferior del coeficiente de caudal φ en la zona de diseño.
    Ref: Dixon & Hall (2013), cap. 5; Cumpsty (2004), cap. 2."""

    PHI_DESIGN_MAX: float = 0.55
    """Límite superior del coeficiente de caudal φ en la zona de diseño."""

    PSI_DESIGN_MIN: float = 0.25
    """Límite inferior del coeficiente de trabajo ψ en la zona de diseño."""

    PSI_DESIGN_MAX: float = 0.50
    """Límite superior del coeficiente de trabajo ψ en la zona de diseño."""

    # ------------------------------------------------------------------
    # Calidad mínima de un polar válido
    # ------------------------------------------------------------------
    POLAR_MIN_ROWS: int = 10
    """Número mínimo de puntos para considerar un polar útil."""

    POLAR_CL_MAX_PHYSICAL: float = 2.5
    """CL máximo físicamente razonable para un perfil subsónico."""

    POLAR_CD_MIN_PHYSICAL: float = 1e-6
    """CD mínimo físicamente razonable (CD > 0 siempre)."""

    # ------------------------------------------------------------------
    # Rangos físicos de operación
    # ------------------------------------------------------------------
    REYNOLDS_MIN: float = 1e4
    """Reynolds mínimo para flujo viscoso significativo."""

    REYNOLDS_MAX: float = 1e9
    """Reynolds máximo físicamente razonable para perfiles delgados."""

    MACH_MAX_SUBSONIC: float = 0.99
    """Mach máximo para análisis subsónico (M < 1 estrictamente)."""


@dataclass(frozen=True)
class XfoilSettings:
    """Parámetros de configuración de la integración Python-XFOIL."""

    ITER: int = 200
    """Número máximo de iteraciones de viscoso por punto α.
    Ref: Drela (1989) XFOIL docs — valor por defecto aumentado para polares
    en condiciones de alta Re y Mach."""

    TIMEOUT_SELECTION_S: float = 60.0
    """Timeout en Stage 1 (selección de perfil): α range pequeño, single Re."""

    TIMEOUT_FINAL_S: float = 180.0
    """Timeout en Stage 2 (simulaciones finales): α range completo, 12 casos."""

    MAX_RETRIES: int = 3
    """Número máximo de reintentos ante fallo de XFOIL (timeout o código ≠ 0)."""

    RETRY_WAIT_S: float = 1.0
    """Espera entre reintentos [s]."""

    CONVERGENCE_WARN_KEYWORDS: tuple = (
        "VISCAL",
        "Convergence failed",
        "RMSBL",
        "MRCHDU",
        "MRCHD",
    )
    """Cadenas que identifican fallos de convergencia en el stdout de XFOIL."""


# ---------------------------------------------------------------------------
# Configuración completa del pipeline (cargada desde YAML)
# ---------------------------------------------------------------------------

@dataclass
class FanGeometry:
    """Geometría del fan de paso variable."""
    rpm: float
    omega_rad_s: float
    radii_m: Dict[str, float]
    axial_velocity_m_s: Dict[str, float]


@dataclass
class BladeGeometry:
    """Geometría de la pala (para correcciones de cascada y rotacionales)."""
    num_blades: int
    chord_m: Dict[str, float]
    theta_camber_deg: float


@dataclass
class AirfoilGeometry:
    """Parámetros geométricos del perfil para correcciones de compresibilidad."""
    thickness_ratio: float  # t/c
    korn_kappa: float       # factor κ de Korn (drag divergence)


@dataclass
class PipelineSettings:
    """Configuración completa del pipeline, cargada de los archivos YAML.

    Punto de entrada único para todos los parámetros de simulación.
    Usar ``get_settings()`` para obtener la instancia cacheada.
    """
    # Constantes físicas (invariantes)
    physics: PhysicsConstants = field(default_factory=PhysicsConstants)
    xfoil: XfoilSettings = field(default_factory=XfoilSettings)

    # Condiciones y secciones
    flight_conditions: List[str] = field(default_factory=list)
    blade_sections: List[str] = field(default_factory=list)

    # Parámetros de simulación por condición
    reynolds_table: Dict[str, Dict[str, float]] = field(default_factory=dict)
    ncrit_table: Dict[str, float] = field(default_factory=dict)
    target_mach: Dict[str, float] = field(default_factory=dict)
    reference_mach: float = 0.2

    # Rango de alpha para XFOIL
    alpha_min: float = -5.0
    alpha_max: float = 23.0
    alpha_step: float = 0.15

    # Alpha para Stage 1 (selección)
    selection_alpha_min: float = -5.0
    selection_alpha_max: float = 20.0
    selection_alpha_step: float = 0.15
    selection_reynolds: float = 3.0e6
    selection_ncrit: float = 7.0

    # Geometría
    fan: FanGeometry = field(default_factory=lambda: FanGeometry(
        rpm=4500.0, omega_rad_s=471.24, radii_m={}, axial_velocity_m_s={},
    ))
    blade: BladeGeometry = field(default_factory=lambda: BladeGeometry(
        num_blades=18, chord_m={}, theta_camber_deg=8.0,
    ))
    airfoil_geometry: AirfoilGeometry = field(default_factory=lambda: AirfoilGeometry(
        thickness_ratio=0.10, korn_kappa=0.87,
    ))

    # Rutas de salida
    results_dir: Path = field(default_factory=lambda: _base.RESULTS_DIR)


# ---------------------------------------------------------------------------
# Carga y caché
# ---------------------------------------------------------------------------

_SETTINGS_CACHE: PipelineSettings | None = None


def get_settings(
    analysis_config_path: Path | None = None,
) -> PipelineSettings:
    """Retorna la instancia cacheada de PipelineSettings.

    La primera llamada carga los archivos YAML; las siguientes son instantáneas.

    Parameters
    ----------
    analysis_config_path : Path, optional
        Ruta a ``analysis_config.yaml``. Por defecto usa ``config/analysis_config.yaml``.
    """
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE
    _SETTINGS_CACHE = _load_settings(analysis_config_path)
    return _SETTINGS_CACHE


def clear_settings_cache() -> None:
    """Invalida la caché de settings (útil en tests)."""
    global _SETTINGS_CACHE
    _SETTINGS_CACHE = None


def _load_settings(config_path: Path | None) -> PipelineSettings:
    """Carga y valida los parámetros desde los archivos YAML."""
    if config_path is None:
        config_path = _base.ROOT_DIR / "config" / "analysis_config.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Archivo de configuración no encontrado: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as f:
        raw: Dict[str, Any] = yaml.safe_load(f)

    # --- condiciones y secciones ---
    flight_conditions: List[str] = raw["flight_conditions"]
    blade_sections: List[str] = raw["blade_sections"]

    # --- tablas Re / Ncrit / Mach ---
    reynolds_table = {
        flight: {section: float(v) for section, v in sections.items()}
        for flight, sections in raw["reynolds"].items()
    }
    ncrit_table = {k: float(v) for k, v in raw["ncrit"].items()}
    target_mach = {k: float(v) for k, v in raw["target_mach"].items()}

    # --- alpha ranges ---
    alpha_cfg = raw["alpha"]
    sel_cfg = raw.get("selection_alpha", alpha_cfg)
    sel = raw.get("selection", {})

    # --- geometría fan ---
    fg = raw["fan_geometry"]
    rpm = float(fg["rpm"])
    fan = FanGeometry(
        rpm=rpm,
        omega_rad_s=rpm * 2.0 * math.pi / 60.0,
        radii_m={k: float(v) for k, v in fg["radius"].items()},
        axial_velocity_m_s={k: float(v) for k, v in fg["axial_velocity"].items()},
    )

    # --- geometría pala ---
    bg = raw["blade_geometry"]
    blade = BladeGeometry(
        num_blades=int(bg["num_blades"]),
        chord_m={k: float(v) for k, v in bg["chord"].items()},
        theta_camber_deg=float(bg["theta_camber_deg"]),
    )

    # --- geometría perfil ---
    ag = raw.get("airfoil_geometry", {})
    airfoil_geom = AirfoilGeometry(
        thickness_ratio=float(ag.get("thickness_ratio", 0.10)),
        korn_kappa=float(ag.get("korn_kappa", 0.87)),
    )

    # --- xfoil settings (optional section, falls back to hardcoded defaults) ---
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
        results_dir=_base.RESULTS_DIR,
    )
