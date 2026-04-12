"""
validators.py
-------------
Validaciones centralizadas para el pipeline VPF.

Divide la lógica en tres grupos:
  1. Validaciones de archivos/directorios  — existencia y formato
  2. Validaciones físicas                  — rangos razonables de Re, Mach, etc.
  3. Validaciones de polares               — calidad y convergencia XFOIL

Todos los checks de "existencia obligatoria" lanzan excepciones con mensajes
que indican claramente QUÉ falta y DÓNDE se espera encontrarlo.
Los checks de "calidad/advertencia" devuelven listas de strings para que el
llamador decida si detener o solo registrar.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence

import pandas as pd

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Validaciones de archivos y directorios
# ---------------------------------------------------------------------------

def require_file(path: Path, label: str = "") -> None:
    """Levanta FileNotFoundError con contexto si *path* no existe o no es fichero.

    Parameters
    ----------
    path : Path
        Ruta a verificar.
    label : str
        Descripción legible para el mensaje de error (ej. "polar de crucero/root").
    """
    ctx = f" [{label}]" if label else ""
    if not path.exists():
        raise FileNotFoundError(
            f"Archivo requerido no encontrado{ctx}: {path}"
        )
    if not path.is_file():
        raise FileNotFoundError(
            f"La ruta existe pero no es un fichero{ctx}: {path}"
        )


def require_dir(path: Path, label: str = "") -> None:
    """Levanta FileNotFoundError si *path* no existe o no es directorio."""
    ctx = f" [{label}]" if label else ""
    if not path.exists():
        raise FileNotFoundError(
            f"Directorio requerido no encontrado{ctx}: {path}"
        )
    if not path.is_dir():
        raise FileNotFoundError(
            f"La ruta existe pero no es un directorio{ctx}: {path}"
        )


def require_csv_columns(
    df: pd.DataFrame,
    required: Sequence[str],
    context: str = "",
) -> None:
    """Levanta ValueError si faltan columnas esperadas en un DataFrame.

    Parameters
    ----------
    df : DataFrame
    required : columnas que deben estar presentes
    context : descripción para el mensaje de error
    """
    missing = sorted(set(required) - set(df.columns))
    if missing:
        ctx = f" [{context}]" if context else ""
        raise ValueError(
            f"Columnas faltantes en DataFrame{ctx}: {missing}. "
            f"Columnas presentes: {sorted(df.columns.tolist())}"
        )


# ---------------------------------------------------------------------------
# 2. Validaciones físicas
# ---------------------------------------------------------------------------

def validate_physical_ranges(
    re: float,
    mach: float,
    context: str = "",
) -> None:
    """Valida que Re y Mach estén en rangos físicamente razonables.

    Parameters
    ----------
    re : float
        Número de Reynolds.
    mach : float
        Número de Mach.
    context : str
        Identificador del caso (ej. "cruise/root") para mensajes de error.

    Raises
    ------
    ValueError
        Si algún parámetro está fuera del rango físico.
    """
    ctx = f" [{context}]" if context else ""
    from vfp_analysis.settings import get_settings
    p = get_settings().physics

    if re <= 0 or re > p.REYNOLDS_MAX:
        raise ValueError(
            f"Reynolds fuera de rango{ctx}: Re={re:.3e} "
            f"(esperado: 0 < Re ≤ {p.REYNOLDS_MAX:.0e})"
        )
    if re < p.REYNOLDS_MIN:
        LOGGER.warning(
            "Reynolds bajo%s: Re=%.2e (mínimo recomendado: %.0e)",
            ctx, re, p.REYNOLDS_MIN,
        )
    if mach < 0 or mach >= p.MACH_MAX_SUBSONIC:
        raise ValueError(
            f"Mach fuera de rango{ctx}: M={mach:.3f} "
            f"(esperado: 0 ≤ M < {p.MACH_MAX_SUBSONIC})"
        )


def validate_alpha_range(
    alpha_min: float,
    alpha_max: float,
    alpha_step: float,
    context: str = "",
) -> None:
    """Valida coherencia del rango de ángulo de ataque."""
    ctx = f" [{context}]" if context else ""
    if alpha_min >= alpha_max:
        raise ValueError(
            f"Rango alpha incoherente{ctx}: min={alpha_min}° ≥ max={alpha_max}°"
        )
    if alpha_step <= 0:
        raise ValueError(
            f"Paso de alpha inválido{ctx}: step={alpha_step}° debe ser > 0"
        )
    n_points = (alpha_max - alpha_min) / alpha_step
    if n_points < 10:
        LOGGER.warning(
            "Rango alpha%s produce solo %.0f puntos (min=%.1f, max=%.1f, step=%.2f) — "
            "polar puede ser insuficiente.",
            ctx, n_points, alpha_min, alpha_max, alpha_step,
        )


# ---------------------------------------------------------------------------
# 3. Validaciones de polares
# ---------------------------------------------------------------------------

def validate_polar_df(
    df: pd.DataFrame,
    context: str = "",
    min_rows: int | None = None,
) -> None:
    """Valida que un polar tenga suficientes datos y columnas mínimas.

    Parameters
    ----------
    df : DataFrame
        Polar a validar (debe tener al menos alpha, cl, cd).
    context : str
        Identificador del caso para mensajes de error.
    min_rows : int, optional
        Número mínimo de filas. Por defecto usa ``PhysicsConstants.POLAR_MIN_ROWS``.

    Raises
    ------
    ValueError
        Si el polar está vacío, tiene pocas filas o le faltan columnas clave.
    """
    from vfp_analysis.settings import get_settings
    p = get_settings().physics

    if min_rows is None:
        min_rows = p.POLAR_MIN_ROWS

    ctx = f" [{context}]" if context else ""

    if df is None or df.empty:
        raise ValueError(f"Polar vacío{ctx}")

    if len(df) < min_rows:
        raise ValueError(
            f"Polar insuficiente{ctx}: {len(df)} filas (mínimo {min_rows}). "
            "Posible fallo de convergencia XFOIL o rango de alpha demasiado estrecho."
        )

    require_csv_columns(df, ["alpha", "cl", "cd"], context)


@dataclass
class PolarQualityWarning:
    """Aviso de calidad sobre un polar aerodinámico."""
    context: str
    code: str          # identificador corto del aviso
    message: str       # descripción legible


def validate_polar_quality(
    df: pd.DataFrame,
    context: str = "",
) -> List[PolarQualityWarning]:
    """Comprueba indicadores de calidad aerodinámica del polar.

    No lanza excepciones; devuelve una lista de avisos para que el llamador
    decida si detener el pipeline o registrar como advertencia.

    Checks realizados
    -----------------
    - CL_max sospechosamente bajo (< 0.3): puede indicar polar no convergido
    - CD_min ≤ 0: valor no físico
    - CD_min sospechosamente alto (> 0.05): perfil en región de alta resistencia
    - Cobertura de alpha insuficiente (rango < 10°)
    - CL monótonamente creciente sin pico de stall (puede ser polar truncado)

    Returns
    -------
    List[PolarQualityWarning]
    """
    from vfp_analysis.settings import get_settings
    p = get_settings().physics

    warnings: List[PolarQualityWarning] = []

    if df.empty:
        return warnings

    cl_max = df["cl"].max()
    cd_min = df["cd"].min()
    cd_max = df["cd"].max()
    alpha_range = df["alpha"].max() - df["alpha"].min()

    if cl_max < 0.3:
        warnings.append(PolarQualityWarning(
            context=context, code="LOW_CL_MAX",
            message=f"CL_max={cl_max:.3f} < 0.3 — polar posiblemente no convergido",
        ))

    if cd_min <= 0:
        warnings.append(PolarQualityWarning(
            context=context, code="NON_PHYSICAL_CD",
            message=f"CD_min={cd_min:.4f} ≤ 0 — valor no físico",
        ))

    if cd_min > 0.05:
        warnings.append(PolarQualityWarning(
            context=context, code="HIGH_CD_MIN",
            message=f"CD_min={cd_min:.4f} > 0.05 — arrastre base elevado (¿alta Re o Mach?)",
        ))

    if alpha_range < 10.0:
        warnings.append(PolarQualityWarning(
            context=context, code="NARROW_ALPHA_RANGE",
            message=(
                f"Rango alpha = {alpha_range:.1f}° < 10° — "
                "puede no cubrir el pico de CL ni el stall"
            ),
        ))

    # Detectar si CL crece monótonamente sin punto de stall (polar truncado)
    if len(df) > 5:
        sorted_df = df.sort_values("alpha")
        positive_alpha = sorted_df[sorted_df["alpha"] > 5.0]
        if not positive_alpha.empty:
            cl_diff = positive_alpha["cl"].diff().dropna()
            if (cl_diff > 0).all():
                warnings.append(PolarQualityWarning(
                    context=context, code="NO_STALL_DETECTED",
                    message=(
                        "CL monótonamente creciente en α > 5° — "
                        "posible polar truncado antes del stall"
                    ),
                ))

    return warnings


# ---------------------------------------------------------------------------
# 4. Convergencia XFOIL
# ---------------------------------------------------------------------------

@dataclass
class XfoilConvergenceInfo:
    """Resultado del análisis de convergencia del stdout de XFOIL."""
    n_convergence_failures: int = 0
    n_points_computed: int = 0
    failed_alpha_values: List[float] = field(default_factory=list)
    raw_warnings: List[str] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return self.n_convergence_failures > 0

    @property
    def convergence_rate(self) -> float:
        """Fracción de puntos convergidos (0–1)."""
        total = self.n_convergence_failures + self.n_points_computed
        if total == 0:
            return 0.0
        return self.n_points_computed / total


def check_xfoil_convergence(stdout: str) -> XfoilConvergenceInfo:
    """Analiza el stdout de XFOIL y extrae información de convergencia.

    XFOIL imprime líneas como::

        VISCAL:  Convergence failed
        a =  12.500   CL =  1.234  CD = ...   (línea de punto convergido)

    Parameters
    ----------
    stdout : str
        Salida estándar del proceso XFOIL.

    Returns
    -------
    XfoilConvergenceInfo
    """
    failures = 0
    computed = 0
    failed_alphas: List[float] = []
    raw_warnings: List[str] = []
    last_alpha: float | None = None

    # Patrones de XFOIL
    _re_alpha_attempt = re.compile(r"a\s*=\s*([-\d.]+)", re.IGNORECASE)
    _re_converged    = re.compile(r"CL\s*=\s*[-\d.]+.*CD\s*=", re.IGNORECASE)
    _re_failure      = re.compile(r"convergence\s+failed", re.IGNORECASE)

    for line in stdout.splitlines():
        # Intento de nuevo alpha
        m_alpha = _re_alpha_attempt.search(line)
        if m_alpha:
            try:
                last_alpha = float(m_alpha.group(1))
            except ValueError:
                pass

        # Punto convergido (tiene CL= y CD=)
        if _re_converged.search(line):
            computed += 1
            last_alpha = None

        # Fallo de convergencia
        if _re_failure.search(line):
            failures += 1
            raw_warnings.append(line.strip())
            if last_alpha is not None:
                failed_alphas.append(last_alpha)
                last_alpha = None

    return XfoilConvergenceInfo(
        n_convergence_failures=failures,
        n_points_computed=computed,
        failed_alpha_values=failed_alphas,
        raw_warnings=raw_warnings,
    )
