"""
kinematics_service.py
---------------------
Resuelve los triángulos de velocidad y calcula el paso mecánico real.

Para cada (condición, sección):
    V_ax  = M × a                      # velocidad axial [m/s]
    U     = ω × r                      # velocidad de pala [m/s]
    φ     = arctan(V_ax / U)           # ángulo de entrada de flujo [°]
    β     = α_opt + φ                  # ángulo de paso mecánico [°]
    Δβ    = β(condición) − β(crucero)  # ajuste respecto a referencia [°]

El resultado conecta la aerodinámica 2D (α_opt) con el comando real
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
    rpm      = kin.get("fan_rpm", 3000.0)
    a        = kin.get("speed_of_sound_m_s", 340.0)
    mach_dict = kin.get("target_mach", {})
    radii    = kin.get("radii_m", {})
    omega    = rpm * (2.0 * math.pi / 60.0)    # [rad/s]

    results: List[KinematicsResult] = []
    reference_beta: Dict[str, float] = {}      # section → β_mech_ref

    # Pasada 1: β absoluto por caso
    for adj in pitch_adjustments:
        mach  = mach_dict.get(adj.condition, 0.5)
        v_ax  = mach * a
        r     = radii.get(adj.section, 1.0)
        u     = omega * r
        phi   = math.degrees(math.atan(v_ax / u)) if u > 0 else 0.0
        beta  = adj.alpha_opt + phi

        results.append(KinematicsResult(
            condition=adj.condition,
            section=adj.section,
            axial_velocity=v_ax,
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
