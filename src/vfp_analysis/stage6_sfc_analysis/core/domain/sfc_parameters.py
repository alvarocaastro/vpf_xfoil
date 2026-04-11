"""
sfc_parameters.py
-----------------
Modelos de dominio para el análisis de consumo específico de combustible (SFC).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineBaseline:
    """Parámetros de motor de referencia para el análisis de SFC."""

    baseline_sfc: float      # SFC de crucero base [lb/(lbf·hr)]
    fan_efficiency: float    # Eficiencia isentrópica de fan base [0-1]
    bypass_ratio: float      # Relación de derivación (bypass ratio)
    cruise_velocity: float   # Velocidad de crucero [m/s]
    jet_velocity: float      # Velocidad de salida del chorro [m/s]


@dataclass(frozen=True)
class SfcAnalysisResult:
    """Resultado del análisis SFC para una condición de vuelo."""

    condition: str
    cl_cd_baseline: float          # CL/CD de referencia (crucero)
    cl_cd_vpf: float               # CL/CD con VPF (condición optimizada)
    fan_efficiency_baseline: float # η_fan base
    fan_efficiency_new: float      # η_fan mejorado con VPF
    sfc_baseline: float            # SFC base para esta condición [lb/(lbf·hr)]
    sfc_new: float                 # SFC mejorado con VPF [lb/(lbf·hr)]
    sfc_reduction_percent: float   # Reducción porcentual de SFC [%]
