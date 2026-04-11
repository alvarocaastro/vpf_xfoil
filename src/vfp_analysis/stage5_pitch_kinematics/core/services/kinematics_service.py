"""
kinematics_service.py
---------------------
Resuelve los triángulos de velocidad y calcula el paso mecánico real.

Para cada (condición, sección):
    Va    = velocidad axial explícita del config [m/s]   ← NO Mach × a
    U     = ω × r                                        # velocidad de pala [m/s]
    φ     = arctan(Va / U)                               # ángulo de entrada de flujo [°]
    β     = α_opt_3D + φ                                 # ángulo de paso mecánico [°]
    Δβ    = β(condición) − β(crucero)                    # ajuste respecto a referencia [°]

NOTA: La velocidad axial Va se lee directamente de engine_parameters.yaml
(sección kinematics.axial_velocity_m_s) para mantener coherencia con
analysis_config.yaml (fan_geometry.axial_velocity). NO se deriva de Mach × a.

El resultado conecta la aerodinámica 3D (α_opt_3D) con el comando real
del actuador de paso de la pala variable.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List

import yaml

from vfp_analysis.stage5_pitch_kinematics.core.domain.pitch_kinematics_result import (
    KinematicsResult,
    PitchAdjustment,
)


def compute_kinematics(
    pitch_adjustments: List[PitchAdjustment],
    engine_config_path: Path,
    reference_condition: str = "cruise",
) -> List[KinematicsResult]:
    """
    Calcula triángulos de velocidad y paso mecánico para cada caso.

    Parameters
    ----------
    pitch_adjustments : List[PitchAdjustment]
        Ajustes de paso aerodinámico de pitch_adjustment_service.
    engine_config_path : Path
        Ruta a engine_parameters.yaml (sección ``kinematics``).
    reference_condition : str
        Condición de referencia para calcular Δβ.

    Returns
    -------
    List[KinematicsResult]
    """
    with engine_config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    kin      = config.get("kinematics", {})
    rpm      = kin.get("fan_rpm", 4500.0)
    radii    = kin.get("radii_m", {})
    va_dict  = kin.get("axial_velocity_m_s", {})   # Va explícita por condición
    omega    = rpm * (2.0 * math.pi / 60.0)         # [rad/s]

    results: List[KinematicsResult] = []
    reference_beta: Dict[str, float] = {}            # section → β_mech_ref

    # Pasada 1: β absoluto por caso
    for adj in pitch_adjustments:
        va    = va_dict.get(adj.condition, float("nan"))
        r     = radii.get(adj.section, float("nan"))
        u     = omega * r if not math.isnan(r) else float("nan")
        phi   = math.degrees(math.atan2(va, u)) if (u > 0 and not math.isnan(va)) else 0.0
        beta  = adj.alpha_opt + phi

        results.append(KinematicsResult(
            condition=adj.condition,
            section=adj.section,
            axial_velocity=va,
            tangential_velocity=u,
            inflow_angle_deg=phi,
            alpha_aero_deg=adj.alpha_opt,
            beta_mech_deg=beta,
        ))

        if adj.condition == reference_condition:
            reference_beta[adj.section] = beta

    # Pasada 2: Δβ respecto a la referencia
    for res in results:
        ref_b = reference_beta.get(res.section, res.beta_mech_deg)
        res.delta_beta_mech_deg = res.beta_mech_deg - ref_b

    return results
