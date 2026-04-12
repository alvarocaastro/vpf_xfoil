"""
sfc_parameters.py
-----------------
Modelos de dominio para el análisis de consumo específico de combustible (SFC).

Modelo físico:
    ε(r, cond)      = CL/CD_vpf / CL/CD_fixed    (Stage 4: max_eff / eff_at_design_alpha)
    ε_eff           = min(ε, EPSILON_CAP)         (cap 3D — Cumpsty 2004 p.280)
    Δη_profile      = (ε_eff − 1) × τ
    η_fan,new       = min(η_base × (1 + Δη_fan), ETA_FAN_ABS_CAP)
    SFC_new         = SFC_base / (1 + k × Δη_applied / η_base)
    k               = BPR / (1 + BPR)             (Saravanamuttoo 2017 §5.14)
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Constantes físicas documentadas
# ---------------------------------------------------------------------------

#: Límite máximo del ratio de mejora 2D→3D en cascada.
#: Por encima de este valor, pérdidas 3D (separación de esquina, flujos secundarios,
#: interacción pala-endwall) impiden aprovechar la ganancia 2D adicional.
#: Ref: Cumpsty (2004) *Compressor Aerodynamics*, p. 280;
#:      Wisler (1998) VKI lecture series.
EPSILON_CAP: float = 1.10

#: Eficiencia isentrópica de fan máxima (estado del arte tecnología actual).
#: Ref: Cumpsty (2004) ch. 8.
ETA_FAN_ABS_CAP: float = 0.96

#: Mejora absoluta máxima de η_fan atribuible al VPF en condiciones reales.
#: Ref: Cumpsty (2004) p. 280, datos empíricos de fans de paso variable.
ETA_FAN_DELTA_CAP: float = 0.04


# ---------------------------------------------------------------------------
# Dominio de parámetros de motor
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EngineBaseline:
    """Parámetros de motor de referencia para el análisis de SFC."""

    baseline_sfc: float      # SFC de crucero base [lb/(lbf·hr)]
    fan_efficiency: float    # Eficiencia isentrópica de fan base [0–1]
    bypass_ratio: float      # Relación de derivación (bypass ratio)
    cruise_velocity: float   # Velocidad de crucero [m/s]
    jet_velocity: float      # Velocidad de salida del chorro [m/s]


# ---------------------------------------------------------------------------
# Resultados por condición (nivel de etapa)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SfcAnalysisResult:
    """Resultado del análisis SFC para una condición de vuelo (agregado span-wise)."""

    condition: str
    # Eficiencia aerodinámica media entre secciones
    cl_cd_fixed: float              # CL/CD paso fijo (eff_at_design_alpha, Stage 4) [media]
    cl_cd_vpf: float                # CL/CD VPF (max_efficiency, Stage 4) [media]
    epsilon_mean: float             # ε medio entre secciones [–]
    delta_alpha_mean_deg: float     # Ajuste de pitch medio requerido [°]
    # Eficiencia de fan
    fan_efficiency_baseline: float  # η_fan base [–]
    fan_efficiency_new: float       # η_fan mejorado con VPF [–]
    delta_eta_fan: float            # Δη_fan aplicado (tras caps) [–]
    k_sensitivity: float            # k = BPR/(1+BPR), fracción de empuje del fan [–]
    # SFC
    sfc_baseline: float             # SFC base para esta condición [lb/(lbf·hr)]
    sfc_new: float                  # SFC mejorado con VPF [lb/(lbf·hr)]
    sfc_reduction_percent: float    # Reducción porcentual de SFC [%]


# ---------------------------------------------------------------------------
# Resultados por sección (nivel de perfil)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SfcSectionResult:
    """Ratio de mejora por perfil para una sección × condición concreta.

    Compara CL/CD al ángulo de diseño (paso fijo) vs CL/CD óptimo (VPF),
    ambos evaluados a idéntico Mach y Reynolds por XFOIL en Stage 4.
    """

    condition: str
    blade_section: str
    cl_cd_fixed: float          # eff_at_design_alpha (Stage 4) [–]
    cl_cd_vpf: float            # max_efficiency (Stage 4) [–]
    epsilon: float              # cl_cd_vpf / cl_cd_fixed [–]
    epsilon_eff: float          # min(epsilon, EPSILON_CAP) [–]
    delta_eta_profile: float    # (epsilon_eff − 1) × τ [–]
    efficiency_gain_pct: float  # (epsilon − 1) × 100 [%]
    delta_alpha_deg: float      # alpha_opt − alpha_design [°]


# ---------------------------------------------------------------------------
# Resultados de sensibilidad a τ
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SfcSensitivityPoint:
    """Un punto del barrido de sensibilidad sobre el coeficiente τ."""

    tau: float               # Coeficiente de transferencia de eficiencia de perfil [–]
    condition: str
    epsilon_mean: float      # ε medio entre secciones [–]
    delta_eta_fan: float     # Δη_fan aplicado (tras caps) [–]
    eta_fan_new: float       # η_fan resultante [–]
    sfc_baseline: float      # SFC base de la condición [lb/(lbf·hr)]
    sfc_new: float           # SFC mejorado [lb/(lbf·hr)]
    sfc_reduction_pct: float # Reducción porcentual [%]
