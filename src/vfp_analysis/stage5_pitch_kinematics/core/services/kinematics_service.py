"""
kinematics_service.py
---------------------
Solves velocity triangles and computes the actual mechanical pitch angle.

For each (condition, section):
    Va    = axial velocity from config [m/s]             ← NOT Mach × a
    U     = ω × r                                        # blade tangential velocity [m/s]
    φ     = arctan(Va / U)                               # inflow angle [°]
    β     = α_opt_3D + φ                                 # mechanical pitch angle [°]
    Δβ    = β(condition) − β(cruise)                     # adjustment relative to reference [°]

Single source of truth: analysis_config.yaml (fan_geometry section).
Va, radii and RPM are read from there via config_loader to avoid duplication
with engine_parameters.yaml.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List

from vfp_analysis.config_loader import get_axial_velocities, get_blade_radii, get_fan_rpm
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
    Compute velocity triangles and mechanical pitch angle for each case.

    Parameters
    ----------
    pitch_adjustments : List[PitchAdjustment]
        Aerodynamic pitch adjustments from pitch_adjustment_service.
    engine_config_path : Path
        Ignored — kept for signature compatibility. Geometric parameters
        are read from analysis_config.yaml (single source of truth).
    reference_condition : str
        Reference condition for computing Δβ.

    Returns
    -------
    List[KinematicsResult]
    """
    rpm     = get_fan_rpm()
    radii   = get_blade_radii()
    va_dict = get_axial_velocities()
    omega   = rpm * (2.0 * math.pi / 60.0)   # [rad/s]

    results: List[KinematicsResult] = []
    reference_beta: Dict[str, float] = {}            # section → β_mech_ref

    # Pass 1: absolute β per case
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

    # Pass 2: Δβ relative to reference
    for res in results:
        ref_b = reference_beta.get(res.section, res.beta_mech_deg)
        res.delta_beta_mech_deg = res.beta_mech_deg - ref_b

    return results
