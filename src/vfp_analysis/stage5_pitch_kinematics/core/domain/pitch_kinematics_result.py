"""
pitch_kinematics_result.py
--------------------------
Modelos de dominio para el análisis integrado de paso e incidencia.

Consolida los anteriores OptimalIncidence (Stage 6) y KinematicsResult (Stage 7)
en un módulo único que refleja que ambos análisis forman una cadena continua:
  OptimalIncidence → PitchAdjustment → KinematicsResult
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptimalIncidence:
    """Ángulo de ataque óptimo para una condición de vuelo y sección de pala."""

    condition: str
    section: str
    reynolds: float
    mach: float
    alpha_opt: float   # Ángulo óptimo (2º pico de CL/CD, α ≥ 3°)
    cl_cd_max: float   # Eficiencia máxima en el punto óptimo


@dataclass(frozen=True)
class PitchAdjustment:
    """Ajuste de paso requerido relativo a una condición de referencia (crucero)."""

    condition: str
    section: str
    alpha_opt: float
    delta_pitch: float  # Δα = α_opt(condición) − α_opt(crucero)


class KinematicsResult:
    """
    Resultado del análisis de triángulos de velocidad para una condición/sección.

    Traduce el Δα aerodinámico en el Δβ_mech que debe aplicar el actuador de paso.
    """

    def __init__(
        self,
        condition: str,
        section: str,
        axial_velocity: float,
        tangential_velocity: float,
        inflow_angle_deg: float,
        alpha_aero_deg: float,
        beta_mech_deg: float,
        delta_beta_mech_deg: float = 0.0,
    ) -> None:
        self.condition            = condition
        self.section              = section
        self.axial_velocity       = axial_velocity        # V_ax [m/s]
        self.tangential_velocity  = tangential_velocity   # U = ω·r [m/s]
        self.inflow_angle_deg     = inflow_angle_deg      # φ [°]
        self.alpha_aero_deg       = alpha_aero_deg        # α_opt [°]
        self.beta_mech_deg        = beta_mech_deg         # β = α + φ [°]
        self.delta_beta_mech_deg  = delta_beta_mech_deg   # Δβ respecto a crucero [°]
