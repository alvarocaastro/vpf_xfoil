"""
rotational_correction_service.py
---------------------------------
3D rotational corrections for rotating fan blades.

In a rotating blade, Coriolis forces and the centrifugal pressure gradient
modify the boundary layer, increasing lift and delaying stall relative to
2D XFOIL data. The effect is most pronounced near the root (where c/r is
large) and negligible at the tip.

Models implemented:

  Snel (1994):
    ΔCL_rot(r) = a · (c/r)² · CL_2D(α)         a = 3.0

  Du-Selig (2000):
    Λ_r        = ω·r / Va                        [local tip-speed-ratio]
    f(Λ_r)     = Λ_r² / (Λ_r² + 1)              [0 → 1 with Λ_r]
    ΔCL_DS(r)  = A_ds · f(Λ_r) · (c/r)^1.6 · CL_2D(α)   A_ds = 1.6

  Physical difference: Du-Selig weights the correction with f(Λ_r), which
  decreases at low Λ_r (takeoff, root). Snel uses a fixed coefficient.
  Du-Selig is more accurate when Λ_r varies significantly between phases
  (GE9X range: Λ_r ≈ 0.68–2.4 at root, 1.28–4.5 at tip).

  CL_3D(α)   = CL_2D(α) + ΔCL_rot(α)
  CD_3D(α)   ≈ CD_2D(α)   (CD correction < 2 %, negligible)

α_opt_3D is found by searching for the second peak of (CL_3D/CD) at α ≥ 3°.

Referencias:
- Snel, H., Houwink, R. & Bosschers, J. (1994). Sectional prediction of 3D
  effects for stalled flow on rotating blades and comparison with measurements.
  Proc. European Wind Energy Conference.
- Du, Z. & Selig, M.S. (2000). The effect of rotation on the aerodynamic
  properties of airfoils. J. Energy Engineering, 126(2), 57–63.
- Dixon & Hall (2013), cap. 9 — Three-dimensional flows in turbomachines.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import pandas as pd


# Physical constants read from PhysicsConstants (settings.py) — not hardcoded here
from vfp_analysis.settings import get_settings as _get_settings
_physics = _get_settings().physics
_SNEL_A         = _physics.SNEL_A            # empirical Snel coefficient (attached flow)
_ALPHA_MIN_OPT  = _physics.ALPHA_MIN_OPT_DEG # minimum α for α_opt search
_CL_MIN_VIABLE  = _physics.CL_MIN_3D         # minimum viable CL in 3D

# Du-Selig coefficient (calibrated Du & Selig 2000, eq. 11)
_DU_SELIG_A: float = 1.6


@dataclass
class DuSeligCorrectionResult:
    """3D rotational correction results using the Du-Selig (2000) model."""
    condition: str
    section: str
    radius_m: float
    chord_m: float
    c_over_r: float              # chord-to-radius ratio [—]
    lambda_r: float              # local tip-speed-ratio Λ_r = ω·r / Va [—]
    du_selig_factor: float       # A_ds · f(Λ_r) · (c/r)^1.6 [—]
    alpha_opt_2d: float          # α_opt from 2D polar [°]
    cl_cd_max_2d: float          # (CL/CD)_max from 2D polar [—]
    alpha_opt_3d: float          # α_opt from 3D polar (Du-Selig) [°]
    cl_cd_max_3d: float          # (CL/CD)_max from 3D polar [—]
    delta_cl_du_selig_at_opt: float  # ΔCL_du_selig at α_opt_3D [—]
    cl_gain_pct: float           # percentage CL gain at α_opt_3D [%]


@dataclass
class RotationalCorrectionResult:
    """3D rotational correction results for a (condition, section) case."""
    condition: str
    section: str
    radius_m: float
    chord_m: float
    c_over_r: float              # chord-to-radius ratio [—]
    snel_factor: float           # a · (c/r)² [—]
    alpha_opt_2d: float          # α_opt from 2D polar (compressibility-corrected) [°]
    cl_cd_max_2d: float          # (CL/CD)_max from 2D polar [—]
    alpha_opt_3d: float          # α_opt from 3D polar (with Snel correction) [°]
    cl_cd_max_3d: float          # (CL/CD)_max from 3D polar [—]
    delta_cl_snel_at_opt: float  # ΔCL_snel at α_opt_3D [—]
    cl_gain_pct: float           # percentage CL gain at α_opt_3D [%]


def _apply_snel(df: pd.DataFrame, c_over_r: float, cl_col: str) -> pd.DataFrame:
    """Add cl_3d and ld_3d columns to the polar DataFrame.

    ΔCL_rot = a · (c/r)² · CL_2D
    CL_3D   = CL_2D + ΔCL_rot
    ld_3d   = CL_3D / CD
    """
    df = df.copy()
    snel_factor = _SNEL_A * c_over_r ** 2
    cd_col = "cd_corrected" if "cd_corrected" in df.columns else "cd"
    df["delta_cl_snel"] = snel_factor * df[cl_col]
    df["cl_3d"] = df[cl_col] + df["delta_cl_snel"]
    df["ld_3d"] = df["cl_3d"] / df[cd_col].replace(0.0, float("nan"))
    return df


def _find_second_peak_3d(df: pd.DataFrame) -> tuple[float, float]:
    """Find the second peak of ld_3d at α ≥ _ALPHA_MIN_OPT.

    Returns (alpha_opt, ld_max). If no data, returns (nan, nan).
    """
    sub = df[df["alpha"] >= _ALPHA_MIN_OPT].copy()
    if sub.empty:
        return float("nan"), float("nan")
    # Minimum viable CL filter
    sub = sub[sub["cl_3d"] >= _CL_MIN_VIABLE]
    if sub.empty:
        return float("nan"), float("nan")
    idx = sub["ld_3d"].idxmax()
    return float(sub.loc[idx, "alpha"]), float(sub.loc[idx, "ld_3d"])


def compute_rotational_corrections(
    df_polars: pd.DataFrame,
    blade_geometry: dict,
    alpha_opt_2d_map: Dict[tuple, float],
    cl_cd_max_2d_map: Dict[tuple, float],
) -> List[RotationalCorrectionResult]:
    """Compute Snel 3D corrections for each (condition, section).

    Parameters
    ----------
    df_polars : pd.DataFrame
        Polars DataFrame with columns: condition, section, alpha,
        cl/cl_corrected, cd/cd_corrected.
    blade_geometry : dict
        Output of config_loader.get_blade_geometry().
    alpha_opt_2d_map : dict[(condition, section), float]
        Reference 2D α_opt (to compute the gain).
    cl_cd_max_2d_map : dict[(condition, section), float]
        Reference 2D (CL/CD)_max.

    Returns
    -------
    List[RotationalCorrectionResult]
    """
    from vfp_analysis.config_loader import get_blade_radii

    chords: Dict[str, float] = blade_geometry["chord"]
    radii = get_blade_radii()

    # Prefer cascade-corrected CL (Weinig applied upstream), then compressibility-corrected,
    # then raw XFOIL. This ensures the cascade correction propagates into the 3D model.
    if "cl_cascade" in df_polars.columns:
        cl_col = "cl_cascade"
    elif "cl_corrected" in df_polars.columns:
        cl_col = "cl_corrected"
    else:
        cl_col = "cl"

    results: List[RotationalCorrectionResult] = []

    conditions = df_polars["condition"].unique()
    sections = list(radii.keys())

    for condition in conditions:
        for section in sections:
            r = radii.get(section, float("nan"))
            c = chords.get(section, 0.10)
            c_over_r = c / r if r > 0 else 0.0
            snel_factor = _SNEL_A * c_over_r ** 2

            mask = (df_polars["condition"] == condition) & (df_polars["section"] == section)
            df_sub = df_polars[mask].sort_values("alpha").reset_index(drop=True)
            if df_sub.empty:
                continue

            df_3d = _apply_snel(df_sub, c_over_r, cl_col)
            alpha_3d, ld_3d = _find_second_peak_3d(df_3d)

            alpha_2d = alpha_opt_2d_map.get((condition, section), float("nan"))
            ld_2d = cl_cd_max_2d_map.get((condition, section), float("nan"))

            # ΔCL_snel evaluated at α_opt_3D
            if not math.isnan(alpha_3d):
                close = df_3d[(df_3d["alpha"] - alpha_3d).abs() < 0.5]
                if not close.empty:
                    idx = (close["alpha"] - alpha_3d).abs().idxmin()
                    delta_cl = float(close.loc[idx, "delta_cl_snel"])
                    cl_base = float(close.loc[idx, cl_col])
                    gain_pct = 100.0 * delta_cl / cl_base if cl_base > 0 else 0.0
                else:
                    delta_cl = float("nan")
                    gain_pct = float("nan")
            else:
                delta_cl = float("nan")
                gain_pct = float("nan")

            results.append(RotationalCorrectionResult(
                condition=condition,
                section=section,
                radius_m=r,
                chord_m=c,
                c_over_r=c_over_r,
                snel_factor=snel_factor,
                alpha_opt_2d=alpha_2d,
                cl_cd_max_2d=ld_2d,
                alpha_opt_3d=alpha_3d,
                cl_cd_max_3d=ld_3d,
                delta_cl_snel_at_opt=delta_cl,
                cl_gain_pct=gain_pct,
            ))

    return results


def _apply_du_selig(
    df: pd.DataFrame,
    c_over_r: float,
    lambda_r: float,
    cl_col: str,
) -> pd.DataFrame:
    """Añade columnas Du-Selig al DataFrame de polar.

    f(Λ_r)     = Λ_r² / (Λ_r² + 1)
    ΔCL_DS     = A_ds · f(Λ_r) · (c/r)^1.6 · CL_2D
    CL_3D_ds   = CL_2D + ΔCL_DS
    ld_3d_ds   = CL_3D_ds / CD
    """
    df = df.copy()
    cd_col = "cd_corrected" if "cd_corrected" in df.columns else "cd"
    f_lambda = lambda_r ** 2 / (lambda_r ** 2 + 1.0) if lambda_r >= 0 else 0.0
    du_selig_factor = _DU_SELIG_A * f_lambda * (c_over_r ** 1.6)
    df["delta_cl_du_selig"] = du_selig_factor * df[cl_col]
    df["cl_3d_ds"] = df[cl_col] + df["delta_cl_du_selig"]
    df["ld_3d_ds"] = df["cl_3d_ds"] / df[cd_col].replace(0.0, float("nan"))
    return df


def _find_second_peak_du_selig(df: pd.DataFrame) -> tuple[float, float]:
    """Encuentra el segundo pico de ld_3d_ds en α ≥ _ALPHA_MIN_OPT."""
    sub = df[df["alpha"] >= _ALPHA_MIN_OPT].copy()
    if sub.empty:
        return float("nan"), float("nan")
    sub = sub[sub["cl_3d_ds"] >= _CL_MIN_VIABLE]
    if sub.empty:
        return float("nan"), float("nan")
    idx = sub["ld_3d_ds"].idxmax()
    return float(sub.loc[idx, "alpha"]), float(sub.loc[idx, "ld_3d_ds"])


def compute_rotational_corrections_du_selig(
    df_polars: pd.DataFrame,
    blade_geometry: dict,
    alpha_opt_2d_map: Dict[tuple, float],
    cl_cd_max_2d_map: Dict[tuple, float],
) -> List[DuSeligCorrectionResult]:
    """Compute Du-Selig 3D corrections for each (condition, section).

    Requires Va and RPM from config to compute Λ_r = ω·r / Va per condition.

    Parameters
    ----------
    df_polars : pd.DataFrame
        DataFrame de polares (condition, section, alpha, cl/cl_corrected, cd/cd_corrected).
    blade_geometry : dict
        Salida de config_loader.get_blade_geometry().
    alpha_opt_2d_map : dict[(condition, section), float]
        α_opt 2D de referencia.
    cl_cd_max_2d_map : dict[(condition, section), float]
        (CL/CD)_max 2D de referencia.

    Returns
    -------
    List[DuSeligCorrectionResult]
    """
    from vfp_analysis.config_loader import get_axial_velocities, get_blade_radii, get_fan_rpm

    chords: Dict[str, float] = blade_geometry["chord"]
    radii = get_blade_radii()
    va_map = get_axial_velocities()
    rpm = get_fan_rpm()
    omega = rpm * (2.0 * math.pi / 60.0)

    if "cl_cascade" in df_polars.columns:
        cl_col = "cl_cascade"
    elif "cl_corrected" in df_polars.columns:
        cl_col = "cl_corrected"
    else:
        cl_col = "cl"

    results: List[DuSeligCorrectionResult] = []

    conditions = df_polars["condition"].unique()
    sections = list(radii.keys())

    for condition in conditions:
        va = va_map.get(condition, 150.0)
        for section in sections:
            r = radii.get(section, float("nan"))
            c = chords.get(section, 0.10)
            c_over_r = c / r if r > 0 else 0.0
            u = omega * r
            lambda_r = u / va if va > 0 else 0.0

            mask = (df_polars["condition"] == condition) & (df_polars["section"] == section)
            df_sub = df_polars[mask].sort_values("alpha").reset_index(drop=True)
            if df_sub.empty:
                continue

            df_3d = _apply_du_selig(df_sub, c_over_r, lambda_r, cl_col)
            alpha_3d, ld_3d = _find_second_peak_du_selig(df_3d)

            alpha_2d = alpha_opt_2d_map.get((condition, section), float("nan"))
            ld_2d = cl_cd_max_2d_map.get((condition, section), float("nan"))

            f_lambda = lambda_r ** 2 / (lambda_r ** 2 + 1.0) if lambda_r >= 0 else 0.0
            du_selig_factor = _DU_SELIG_A * f_lambda * (c_over_r ** 1.6)

            if not math.isnan(alpha_3d):
                close = df_3d[(df_3d["alpha"] - alpha_3d).abs() < 0.5]
                if not close.empty:
                    idx = (close["alpha"] - alpha_3d).abs().idxmin()
                    delta_cl = float(close.loc[idx, "delta_cl_du_selig"])
                    cl_base = float(close.loc[idx, cl_col])
                    gain_pct = 100.0 * delta_cl / cl_base if cl_base > 0 else 0.0
                else:
                    delta_cl = float("nan")
                    gain_pct = float("nan")
            else:
                delta_cl = float("nan")
                gain_pct = float("nan")

            results.append(DuSeligCorrectionResult(
                condition=condition,
                section=section,
                radius_m=r,
                chord_m=c,
                c_over_r=c_over_r,
                lambda_r=lambda_r,
                du_selig_factor=du_selig_factor,
                alpha_opt_2d=alpha_2d,
                cl_cd_max_2d=ld_2d,
                alpha_opt_3d=alpha_3d,
                cl_cd_max_3d=ld_3d,
                delta_cl_du_selig_at_opt=delta_cl,
                cl_gain_pct=gain_pct,
            ))

    return results


def build_3d_polar_map(
    df_polars: pd.DataFrame,
    blade_geometry: dict,
) -> Dict[tuple, pd.DataFrame]:
    """Build a map of Snel-corrected 3D polars.

    Returns {(condition, section): DataFrame with cl_3d, ld_3d}.
    """
    from vfp_analysis.config_loader import get_blade_radii

    chords = blade_geometry["chord"]
    radii = get_blade_radii()
    if "cl_cascade" in df_polars.columns:
        cl_col = "cl_cascade"
    elif "cl_corrected" in df_polars.columns:
        cl_col = "cl_corrected"
    else:
        cl_col = "cl"

    polar_map: Dict[tuple, pd.DataFrame] = {}
    for condition in df_polars["condition"].unique():
        for section, r in radii.items():
            c = chords.get(section, 0.10)
            c_over_r = c / r if r > 0 else 0.0
            mask = (df_polars["condition"] == condition) & (df_polars["section"] == section)
            df_sub = df_polars[mask].sort_values("alpha").reset_index(drop=True)
            if df_sub.empty:
                continue
            df_3d = _apply_snel(df_sub, c_over_r, cl_col)
            polar_map[(condition, section)] = df_3d

    return polar_map
