"""
Core service for computing velocity triangles and mechanical pitch.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List
import yaml

from vfp_analysis.vpf_analysis.core.domain.optimal_incidence import PitchAdjustment


class KinematicsResult:
    """Stores the kinematic analysis for a specific condition/section."""

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
        self.condition = condition
        self.section = section
        self.axial_velocity = axial_velocity
        self.tangential_velocity = tangential_velocity
        self.inflow_angle_deg = inflow_angle_deg
        self.alpha_aero_deg = alpha_aero_deg
        self.beta_mech_deg = beta_mech_deg
        self.delta_beta_mech_deg = delta_beta_mech_deg


def compute_kinematics(
    pitch_adjustments: List[PitchAdjustment],
    engine_config_path: Path,
    reference_condition: str = "cruise",
) -> List[KinematicsResult]:
    """
    Compute velocity triangles and actual mechanical pitch required.
    """
    with engine_config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    kin = config.get("kinematics", {})
    rpm = kin.get("fan_rpm", 3000.0)
    a = kin.get("speed_of_sound_m_s", 340.0)
    mach_dict = kin.get("target_mach", {})
    radii = kin.get("radii_m", {})

    # Compute V_ax and U for all points
    results: List[KinematicsResult] = []
    
    # Store reference beta dict
    reference_beta: Dict[str, float] = {}  # section -> beta_mech_ref

    # First pass: compute absolute beta for all conditions
    for adj in pitch_adjustments:
        mach = mach_dict.get(adj.condition, 0.5)
        v_ax = mach * a
        
        radius = radii.get(adj.section, 1.0)
        u = rpm * (2 * math.pi / 60.0) * radius
        
        phi_rad = math.atan(v_ax / u) if u > 0 else 0.0
        phi_deg = math.degrees(phi_rad)
        
        # beta = alpha + phi
        beta_deg = adj.alpha_opt + phi_deg
        
        res = KinematicsResult(
            condition=adj.condition,
            section=adj.section,
            axial_velocity=v_ax,
            tangential_velocity=u,
            inflow_angle_deg=phi_deg,
            alpha_aero_deg=adj.alpha_opt,
            beta_mech_deg=beta_deg,
        )
        results.append(res)
        
        if adj.condition == reference_condition:
            reference_beta[adj.section] = beta_deg

    # Second pass: compute delta relative to reference
    for res in results:
        ref_b = reference_beta.get(res.section, res.beta_mech_deg)
        res.delta_beta_mech_deg = res.beta_mech_deg - ref_b

    return results
