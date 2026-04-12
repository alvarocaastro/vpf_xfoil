"""
cascade_correction_service.py
------------------------------
Correcciones de cascada para el fan de paso variable.

En un fan real, las palas no operan como perfiles aislados sino en cascada:
la interferencia mutua modifica la sustentación efectiva y el ángulo de salida
del flujo. La magnitud del efecto depende de la solidez σ = c/s, donde
s = 2πr/Z es la separación circunferencial entre palas.

Modelos implementados:

1. Factor de Weinig (corrección de la pendiente de sustentación en cascada)
   CL_cascade = CL_2D · K_weinig
   K_weinig = (π/2 · σ) / arctan(π · σ / 2)
   Referencia: Dixon & Hall (2013), ec. 3.54; Cumpsty (2004), cap. 3

2. Regla de Carter (ángulo de desviación de salida)
   δ_carter = m · θ / √σ
   m = 0.23  (para NACA 6-series con a/c = 0.5)
   θ = ángulo de combadura [°]
   Referencia: Carter (1950), NACA TN-2273; ESDU 05017

Outputs:
    CascadeResult por sección (geométrico, independiente de condición de vuelo)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


# Coeficiente m de la regla de Carter para NACA 6-series (a/c = 0.5)
# Se lee de PhysicsConstants para mantener consistencia con settings.py
from vfp_analysis.settings import get_settings as _get_settings
_CARTER_M_NACA6: float = _get_settings().physics.CARTER_M_NACA6


@dataclass
class CascadeResult:
    """Resultado de las correcciones de cascada para una sección de pala."""
    section: str
    radius_m: float
    chord_m: float
    blade_spacing_m: float       # s = 2πr / Z  [m]
    solidity: float              # σ = c / s     [—]
    k_weinig: float              # factor de corrección de CL en cascada  [—]
    delta_carter_deg: float      # ángulo de desviación de Carter  [°]
    cl_2d_at_alpha_opt: float    # CL_2D en α_opt (antes de corrección)  [—]
    cl_cascade_at_alpha_opt: float  # CL en cascada en α_opt  [—]


def _weinig_factor(sigma: float) -> float:
    """Factor de Weinig para la pendiente de sustentación en cascada.

    Aproximación analítica válida para 0.1 < σ < 2.5.

    K_weinig = (π/2 · σ) / arctan(π · σ / 2)

    Para σ → 0: K_weinig → 1  (perfil aislado)
    Para σ → ∞: K_weinig → σ / (π/2)  (cascada densa)

    Referencia: Dixon & Hall (2013), ec. 3.54
    """
    if sigma <= 0.0:
        return 1.0
    arg = math.pi * sigma / 2.0
    return arg / math.atan(arg)


def _carter_deviation(theta_deg: float, sigma: float, m: float = _CARTER_M_NACA6) -> float:
    """Ángulo de desviación de salida según la regla de Carter.

    δ = m · θ / √σ

    Parámetros
    ----------
    theta_deg : float
        Ángulo de combadura de la pala [°].
    sigma : float
        Solidez de la cascada σ = c/s [—].
    m : float
        Coeficiente de Carter (0.23 para NACA 6-series).

    Retorna
    -------
    float
        Ángulo de desviación δ [°].

    Referencia: Carter (1950), NACA TN-2273; ESDU 05017
    """
    if sigma <= 0.0:
        return 0.0
    return m * theta_deg / math.sqrt(sigma)


def compute_cascade_corrections(
    blade_geometry: dict,
    alpha_opt_by_section: Dict[str, float],
    df_polars: pd.DataFrame,
) -> List[CascadeResult]:
    """Calcula las correcciones de cascada para cada sección de pala.

    Las correcciones son geométricas (dependen de r, c, Z, θ) y no de la
    condición de vuelo. Se evalúan en el α_opt de crucero de cada sección.

    Parámetros
    ----------
    blade_geometry : dict
        Salida de config_loader.get_blade_geometry().
        Claves: num_blades, chord (dict), theta_camber_deg.
    alpha_opt_by_section : dict[str, float]
        α_opt en crucero por sección (para evaluar CL_2D de referencia).
    df_polars : pd.DataFrame
        DataFrame de polares (columnas: section, condition, alpha, CL_CD o ld,
        cl o cl_corrected, cd o cd_corrected).

    Retorna
    -------
    List[CascadeResult]
    """
    from vfp_analysis.config_loader import get_blade_radii

    Z = blade_geometry["num_blades"]
    chords: Dict[str, float] = blade_geometry["chord"]
    theta = blade_geometry["theta_camber_deg"]
    radii = get_blade_radii()  # {root: 0.20, mid_span: 0.42, tip: 0.65}

    results: List[CascadeResult] = []

    for section, r in radii.items():
        c = chords.get(section, 0.10)
        s = 2.0 * math.pi * r / Z          # separación circunferencial [m]
        sigma = c / s                        # solidez [—]

        k_w = _weinig_factor(sigma)
        delta_c = _carter_deviation(theta, sigma)

        # CL_2D en α_opt_cruise de esta sección
        alpha_ref = alpha_opt_by_section.get(section, float("nan"))
        cl_2d = _lookup_cl(df_polars, section, "cruise", alpha_ref)
        cl_cascade = cl_2d * k_w if not math.isnan(cl_2d) else float("nan")

        results.append(CascadeResult(
            section=section,
            radius_m=r,
            chord_m=c,
            blade_spacing_m=s,
            solidity=sigma,
            k_weinig=k_w,
            delta_carter_deg=delta_c,
            cl_2d_at_alpha_opt=cl_2d,
            cl_cascade_at_alpha_opt=cl_cascade,
        ))

    return results


def apply_weinig_to_polar(
    df: pd.DataFrame,
    k_weinig: float,
    cl_col: str = "cl",
) -> pd.DataFrame:
    """Aplica la corrección de Weinig a una polar completa.

    Crea columna ``cl_cascade`` = cl_col × K_weinig y recalcula
    ``ld_cascade`` = cl_cascade / cd.

    Parámetros
    ----------
    df : pd.DataFrame
        DataFrame de polar con columnas cl_col y 'cd'.
    k_weinig : float
        Factor de Weinig para esta sección.
    cl_col : str
        Nombre de la columna de CL de entrada.

    Retorna
    -------
    pd.DataFrame
        DataFrame con columnas añadidas: cl_cascade, ld_cascade.
    """
    df = df.copy()
    cd_col = "cd_corrected" if "cd_corrected" in df.columns else "cd"
    df["cl_cascade"] = df[cl_col] * k_weinig
    df["ld_cascade"] = df["cl_cascade"] / df[cd_col].replace(0, float("nan"))
    return df


# ---------------------------------------------------------------------------
# Helper interno
# ---------------------------------------------------------------------------

def _lookup_cl(
    df: pd.DataFrame,
    section: str,
    condition: str,
    alpha: float,
    tol: float = 0.5,
) -> float:
    """Devuelve CL interpolado en (section, condition, alpha) del DataFrame de polares."""
    if math.isnan(alpha):
        return float("nan")

    cl_col = "cl_corrected" if "cl_corrected" in df.columns else "cl"
    mask = (df["section"] == section) & (df["condition"] == condition)
    sub = df[mask].copy()
    if sub.empty:
        return float("nan")

    sub = sub.sort_values("alpha")
    close = sub[(sub["alpha"] - alpha).abs() <= tol]
    if close.empty:
        return float("nan")

    idx = (close["alpha"] - alpha).abs().idxmin()
    return float(close.loc[idx, cl_col])
