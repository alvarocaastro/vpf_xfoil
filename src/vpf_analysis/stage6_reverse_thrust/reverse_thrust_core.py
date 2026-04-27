"""Pure functions for reverse thrust: kinematics, BEM sweep, mechanism weight."""

from __future__ import annotations

import logging
import math
from typing import List, Tuple

LOGGER = logging.getLogger(__name__)

import numpy as np
import pandas as pd

from vpf_analysis.stage6_reverse_thrust.core.domain.reverse_thrust_result import (
    MechanismWeightResult,
    ReverseKinematicsSection,
    ReverseOptimalResult,
    ReverseSweepPoint,
)

_G = 9.81
_ALPHA_STALL_NEG_DEFAULT_DEG = -12.0
_SECTIONS = ["root", "mid_span", "tip"]

# ---------------------------------------------------------------------------
# Reverse kinematics (reverse_kinematics_service)
# ---------------------------------------------------------------------------


def compute_reverse_kinematics(
    blade_twist_df: pd.DataFrame,
    chord_map: dict[str, float],
    n1_fraction: float,
    va_landing_m_s: float,
) -> List[ReverseKinematicsSection]:
    """Compute reverse-mode velocity triangles for all blade sections."""
    rows: dict[str, dict] = {}
    for _, row in blade_twist_df.iterrows():
        sec = str(row["section"])
        if sec in _SECTIONS:
            rows[sec] = {
                "radius_m": float(row["radius_m"]),
                "u_cruise": float(row["U_cruise_m_s"]),
            }

    radii = [rows[s]["radius_m"] for s in _SECTIONS if s in rows]
    r_hub = radii[0] - (radii[1] - radii[0]) / 2.0

    boundaries = (
        [r_hub]
        + [(radii[i] + radii[i + 1]) / 2.0 for i in range(len(radii) - 1)]
        + [radii[-1]]
    )
    delta_r = [boundaries[i + 1] - boundaries[i] for i in range(len(radii))]

    results: List[ReverseKinematicsSection] = []
    for idx, sec in enumerate([s for s in _SECTIONS if s in rows]):
        r = rows[sec]["radius_m"]
        u_c = rows[sec]["u_cruise"]
        c = chord_map.get(sec, 0.46)

        u_rev = n1_fraction * u_c
        w_rel = math.sqrt(va_landing_m_s**2 + u_rev**2)
        phi_rev = math.degrees(math.atan2(va_landing_m_s, u_rev))

        results.append(ReverseKinematicsSection(
            section=sec,
            radius_m=r,
            chord_m=c,
            u_rev_m_s=u_rev,
            w_rel_m_s=w_rel,
            phi_rev_deg=phi_rev,
            delta_r_m=delta_r[idx],
        ))

    return results


# ---------------------------------------------------------------------------
# BEM reverse thrust (reverse_thrust_service)
# ---------------------------------------------------------------------------


def _viterna_extrapolate(
    alpha_deg: float,
    cl_stall: float,
    cd_stall: float,
    alpha_stall_deg: float,
) -> Tuple[float, float]:
    """Viterna-Corrigan (1982) post-stall model for deep-stall / reverse-pitch.

    Valid for |α| > α_stall.  Based on:
      Viterna, L.A. & Corrigan, R.D. (1982). "Fixed Pitch Rotor Performance of
      Large Horizontal Axis Wind Turbines." DOE/NASA Workshop on Large Horizontal
      Axis Wind Turbines, NASA CP-2230.

    The model anchors to the last known polar point (cl_stall, cd_stall at
    alpha_stall) and extends with sinusoidal relations derived from the aspect-
    ratio-limited maximum drag coefficient cd_max ≈ 1.11 + 0.018·AR_eff.
    AR_eff is solved by one fixed-point iteration from cd_max·AR_eff = 2.
    """
    alpha_rad = math.radians(alpha_deg)
    alpha_s = math.radians(alpha_stall_deg)

    # Aspect-ratio-limited max drag (one fixed-point iteration from AR_eff=2/cd_max)
    cd_max = min(1.11 + 0.018 * (2.0 / max(cd_stall, 0.01)), 2.0)

    sin_s = math.sin(alpha_s)
    cos_s = math.cos(alpha_s)

    # Viterna coefficients
    A1 = cd_max / 2.0
    # Guard division by cos²(α_s) when α_stall ≈ ±90°
    if abs(cos_s) < 1e-6:
        A2 = 0.0
    else:
        A2 = (cl_stall - cd_max * sin_s * cos_s) * sin_s / (cos_s ** 2)

    B1 = cd_max
    if abs(cos_s) < 1e-6:
        B2 = 0.0
    else:
        B2 = (cd_stall - cd_max * sin_s ** 2) / cos_s

    sin_a = math.sin(alpha_rad)
    cos_a = math.cos(alpha_rad)

    # Guard CL formula division by sin α (zero at α = 0°)
    if abs(sin_a) < 1e-6:
        cl = A1 * math.sin(2.0 * alpha_rad)
    else:
        cl = 0.5 * A1 * math.sin(2.0 * alpha_rad) + A2 * cos_a ** 2 / sin_a

    cd = B1 * sin_a ** 2 + B2 * cos_a

    # Physical bounds: CL ∈ [−2, 2], CD ∈ [0, cd_max]
    cl = float(np.clip(cl, -2.0, 2.0))
    cd = float(np.clip(cd, 0.0, cd_max))
    return cl, cd


def _get_aero_coeffs(
    polar_df: pd.DataFrame,
    alpha_deg: float,
) -> Tuple[float, float, bool]:
    df = polar_df.dropna(subset=["cl_kt", "cd_corrected", "alpha"]).sort_values("alpha")
    alpha_min = float(df["alpha"].iloc[0])
    alpha_max = float(df["alpha"].iloc[-1])

    if alpha_min <= alpha_deg <= alpha_max:
        cl = float(np.interp(alpha_deg, df["alpha"], df["cl_kt"]))
        cd = float(np.interp(alpha_deg, df["alpha"], df["cd_corrected"]))
        return cl, cd, True

    LOGGER.warning(
        "alpha=%.1f° outside polar range [%.1f°, %.1f°] by %.1f° — "
        "using Viterna-Corrigan extrapolation; in_range flag set to False.",
        alpha_deg, alpha_min, alpha_max, abs(alpha_deg - alpha_min),
    )

    # Anchor Viterna model to the negative-alpha end of the polar (closest side
    # for reverse-thrust operation where α < alpha_min ≈ −5°).
    cl_stall = float(df["cl_kt"].iloc[0])
    cd_stall = float(df["cd_corrected"].iloc[0])
    cl, cd = _viterna_extrapolate(alpha_deg, cl_stall, cd_stall, alpha_min)

    return cl, cd, False


def _stall_margin(alpha_rev_deg: float, polar_df: pd.DataFrame) -> float:
    df = polar_df.dropna(subset=["cl_kt", "alpha"]).sort_values("alpha")
    neg_part = df[df["alpha"] <= 0]
    alpha_stall_neg = _ALPHA_STALL_NEG_DEFAULT_DEG
    if len(neg_part) >= 3:
        cls = neg_part["cl_kt"].values
        alphas = neg_part["alpha"].values
        # Smooth before differentiating to suppress XFOIL polar noise that
        # creates spurious sign changes in the gradient.
        from scipy.ndimage import uniform_filter1d
        cls_smooth = uniform_filter1d(cls, size=3) if len(cls) >= 5 else cls
        grads = np.diff(cls_smooth) / np.diff(alphas)
        sign_changes = np.where(np.diff(np.sign(grads)))[0]
        if len(sign_changes) > 0:
            alpha_stall_neg = float(alphas[sign_changes[-1] + 1])
    return float((alpha_stall_neg - alpha_rev_deg) / abs(alpha_stall_neg))


def _bem_forces(
    kin: ReverseKinematicsSection,
    beta_metal_deg: float,
    delta_beta_deg: float,
    polar_df: pd.DataFrame,
    rho: float,
    n_blades: int,
) -> Tuple[float, float, float, float, float, float, bool, bool]:
    beta_rev_deg = beta_metal_deg + delta_beta_deg
    alpha_rev_deg = beta_rev_deg - kin.phi_rev_deg

    cl, cd, in_range = _get_aero_coeffs(polar_df, alpha_rev_deg)

    phi_rad = math.radians(kin.phi_rev_deg)
    sin_phi = math.sin(phi_rad)
    cos_phi = math.cos(phi_rad)

    q = 0.5 * rho * kin.w_rel_m_s**2
    thrust_coeff = cl * sin_phi - cd * cos_phi
    torque_coeff = cl * cos_phi + cd * sin_phi

    dT_dr = n_blades * q * kin.chord_m * thrust_coeff
    dQ_dr = n_blades * q * kin.chord_m * kin.radius_m * torque_coeff

    sm = _stall_margin(alpha_rev_deg, polar_df)

    return cl, cd, dT_dr, dQ_dr, sm, alpha_rev_deg, in_range, beta_rev_deg


def compute_reverse_sweep(
    kinematics: List[ReverseKinematicsSection],
    blade_twist_df: pd.DataFrame,
    polar_map: dict[str, pd.DataFrame],
    delta_beta_values: np.ndarray,
    rho: float,
    n_blades: int,
    t_forward_takeoff_kN: float,
    stall_margin_min_threshold: float,
) -> Tuple[List[ReverseSweepPoint], float]:
    """Run the full pitch sweep and return sweep results plus design RPM ω."""
    beta_metal: dict[str, float] = {}
    for _, row in blade_twist_df.iterrows():
        sec = str(row["section"])
        beta_metal[sec] = float(row["beta_metal_deg"])

    mid_kin = next(k for k in kinematics if k.section == "mid_span")
    omega_rev = mid_kin.u_rev_m_s / mid_kin.radius_m

    sections = ["root", "mid_span", "tip"]
    kin_map = {k.section: k for k in kinematics}

    sweep_points: List[ReverseSweepPoint] = []

    for db in delta_beta_values:
        sec_data: dict[str, dict] = {}
        for sec in sections:
            if sec not in kin_map or sec not in polar_map:
                continue
            cl, cd, dT_dr, dQ_dr, sm, alpha_rev, in_range, beta_rev = _bem_forces(
                kin=kin_map[sec],
                beta_metal_deg=beta_metal.get(sec, 30.0),
                delta_beta_deg=float(db),
                polar_df=polar_map[sec],
                rho=rho,
                n_blades=n_blades,
            )
            sec_data[sec] = dict(
                cl=cl, cd=cd, dT_dr=dT_dr, dQ_dr=dQ_dr,
                stall_margin=sm, alpha_rev=alpha_rev,
                in_range=in_range, beta_rev=beta_rev,
            )

        if len(sec_data) < 3:
            continue

        T_total = sum(
            sec_data[s]["dT_dr"] * kin_map[s].delta_r_m
            for s in sections if s in sec_data
        )
        Q_total = sum(
            sec_data[s]["dQ_dr"] * kin_map[s].delta_r_m
            for s in sections if s in sec_data
        )

        T_kN = T_total / 1000.0
        thrust_fraction = abs(T_kN) / t_forward_takeoff_kN if t_forward_takeoff_kN > 0 else 0.0

        va = math.sqrt(mid_kin.w_rel_m_s**2 - mid_kin.u_rev_m_s**2)
        p_thrust = abs(T_total) * va
        p_shaft = abs(Q_total * omega_rev)
        eta_rev = min(p_thrust / p_shaft if p_shaft > 1.0 else 0.0, 0.99)

        stall_margins = [sec_data[s]["stall_margin"] for s in sections if s in sec_data]
        sm_min = min(stall_margins)
        valid = sm_min >= stall_margin_min_threshold

        sweep_points.append(ReverseSweepPoint(
            delta_beta_deg=float(db),
            beta_rev_root_deg=sec_data["root"]["beta_rev"],
            beta_rev_mid_deg=sec_data["mid_span"]["beta_rev"],
            beta_rev_tip_deg=sec_data["tip"]["beta_rev"],
            alpha_rev_root_deg=sec_data["root"]["alpha_rev"],
            alpha_rev_mid_deg=sec_data["mid_span"]["alpha_rev"],
            alpha_rev_tip_deg=sec_data["tip"]["alpha_rev"],
            cl_root=sec_data["root"]["cl"], cd_root=sec_data["root"]["cd"],
            cl_mid=sec_data["mid_span"]["cl"], cd_mid=sec_data["mid_span"]["cd"],
            cl_tip=sec_data["tip"]["cl"], cd_tip=sec_data["tip"]["cd"],
            in_polar_range_root=sec_data["root"]["in_range"],
            in_polar_range_mid=sec_data["mid_span"]["in_range"],
            in_polar_range_tip=sec_data["tip"]["in_range"],
            dT_dr_root_N_m=sec_data["root"]["dT_dr"],
            dT_dr_mid_N_m=sec_data["mid_span"]["dT_dr"],
            dT_dr_tip_N_m=sec_data["tip"]["dT_dr"],
            thrust_kN=T_kN,
            thrust_fraction=thrust_fraction,
            eta_fan_rev=eta_rev,
            stall_margin_root=sec_data["root"]["stall_margin"],
            stall_margin_mid=sec_data["mid_span"]["stall_margin"],
            stall_margin_tip=sec_data["tip"]["stall_margin"],
            stall_margin_min=sm_min,
            aerodynamically_valid=valid,
        ))

    return sweep_points, omega_rev


def select_optimal_point(
    sweep: List[ReverseSweepPoint],
    target_thrust_fraction: float,
    n1_fraction: float,
    va_landing_m_s: float,
) -> ReverseOptimalResult:
    """Select the best operating point from the sweep."""
    reverse_points = [p for p in sweep if p.thrust_kN < 0.0]
    if not reverse_points:
        reverse_points = sweep

    valid_pts = [p for p in reverse_points if p.aerodynamically_valid]
    candidate_pool = valid_pts if valid_pts else reverse_points

    best = min(candidate_pool, key=lambda p: abs(p.thrust_fraction - target_thrust_fraction))

    return ReverseOptimalResult(
        delta_beta_opt_deg=best.delta_beta_deg,
        beta_opt_root_deg=best.beta_rev_root_deg,
        beta_opt_mid_deg=best.beta_rev_mid_deg,
        beta_opt_tip_deg=best.beta_rev_tip_deg,
        thrust_net_kN=best.thrust_kN,
        thrust_fraction=best.thrust_fraction,
        eta_fan_rev=best.eta_fan_rev,
        n1_fraction=n1_fraction,
        va_landing_m_s=va_landing_m_s,
        stall_margin_min=best.stall_margin_min,
        aerodynamically_valid=best.aerodynamically_valid,
    )


# ---------------------------------------------------------------------------
# Mechanism weight (mechanism_weight_service)
# ---------------------------------------------------------------------------


def compute_mechanism_weight(
    engine_dry_weight_kg: float,
    mechanism_weight_fraction: float,
    conventional_reverser_fraction: float,
    design_thrust_kN: float,
    cruise_thrust_fraction: float,
    aircraft_L_D: float,
    n_engines: int = 2,
) -> MechanismWeightResult:
    """Compute VPF mechanism weight and its cruise SFC impact."""
    mechanism_weight_kg = n_engines * engine_dry_weight_kg * mechanism_weight_fraction
    conventional_weight_kg = n_engines * engine_dry_weight_kg * conventional_reverser_fraction
    weight_saving_kg = conventional_weight_kg - mechanism_weight_kg

    t_cruise_total_N = n_engines * design_thrust_kN * 1000.0 * cruise_thrust_fraction

    delta_t_mechanism_N = mechanism_weight_kg * _G / aircraft_L_D
    sfc_penalty_pct = (delta_t_mechanism_N / t_cruise_total_N) * 100.0

    delta_t_saving_N = weight_saving_kg * _G / aircraft_L_D
    sfc_benefit_pct = (delta_t_saving_N / t_cruise_total_N) * 100.0

    return MechanismWeightResult(
        mechanism_weight_kg=mechanism_weight_kg,
        conventional_reverser_weight_kg=conventional_weight_kg,
        weight_saving_vs_conventional_kg=weight_saving_kg,
        sfc_cruise_penalty_pct=sfc_penalty_pct,
        sfc_benefit_vs_conventional_pct=sfc_benefit_pct,
    )
