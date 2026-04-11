"""
propulsion_model_service.py
---------------------------
Sub-modelos físicos para el cálculo de mejoras de SFC mediante VPF.

Modelo principal de transferencia de eficiencia de perfil a fan:
    ε            = CL_CD_vpf / CL_CD_base
    Δη_profile   = (ε − 1) × τ
    η_fan,new    = η_fan,base × (1 + Δη_profile)
    SFC_new      = SFC_base / (1 + Δη_fan / η_fan,base)

τ (profile_efficiency_transfer) amortígua las pérdidas 3D que impiden que
la mejora 2D del perfil se transfiera íntegramente al fan completo.
"""

from __future__ import annotations

import yaml
from pathlib import Path

from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import EngineBaseline  # noqa: F401 (referencia futura)


def compute_propulsion_efficiency(v0: float, vj: float) -> float:
    """
    Eficiencia propulsiva: η_prop = 2 / (1 + V_j / V_0).

    Parameters
    ----------
    v0 : float  Velocidad de vuelo [m/s]
    vj : float  Velocidad de salida del chorro [m/s]
    """
    if v0 <= 0:
        raise ValueError("La velocidad de vuelo debe ser positiva.")
    if vj <= 0:
        raise ValueError("La velocidad del chorro debe ser positiva.")
    return 2.0 / (1.0 + vj / v0)


def compute_fan_efficiency_improvement(
    cl_cd_baseline: float,
    cl_cd_new: float,
    fan_efficiency_baseline: float,
) -> float:
    """
    Estima la mejora de eficiencia de fan a partir de la mejora aerodinàmica.

    Aplica el factor de transferencia τ leído de engine_parameters.yaml.

    Parameters
    ----------
    cl_cd_baseline : float  CL/CD de referencia.
    cl_cd_new : float       CL/CD con VPF.
    fan_efficiency_baseline : float  η_fan base.

    Returns
    -------
    float  Nueva eficiencia de fan (acotada a 0.96).
    """
    if cl_cd_baseline <= 0:
        raise ValueError("CL/CD de referencia debe ser positivo.")

    efficiency_ratio = cl_cd_new / cl_cd_baseline
    transfer_coeff = 1.0
    try:
        cfg_path = Path(__file__).resolve().parents[5] / "config" / "engine_parameters.yaml"
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            transfer_coeff = float(cfg.get("profile_efficiency_transfer", 1.0))
    except Exception:
        pass

    eff_gain = (efficiency_ratio - 1.0) * transfer_coeff
    fan_efficiency_new = fan_efficiency_baseline * (1.0 + eff_gain)
    return min(fan_efficiency_new, 0.96)


def compute_sfc_improvement(
    sfc_baseline: float,
    efficiency_gain: float,
) -> float:
    """
    Estima SFC mejorado: SFC_new = SFC_base / (1 + efficiency_gain).

    Parameters
    ----------
    sfc_baseline : float    SFC base.
    efficiency_gain : float Factor de mejora de eficiencia [0-1].
    """
    if efficiency_gain < 0:
        raise ValueError("El factor de mejora debe ser no negativo.")
    return max(sfc_baseline / (1.0 + efficiency_gain), 0.0)


def compute_sfc_reduction_percent(
    sfc_baseline: float,
    sfc_new: float,
) -> float:
    """
    Porcentaje de reducción de SFC: [(SFC_base − SFC_new) / SFC_base] × 100.
    """
    if sfc_baseline <= 0:
        raise ValueError("SFC base debe ser positivo.")
    return ((sfc_baseline - sfc_new) / sfc_baseline) * 100.0
