"""
xfoil_parser.py
---------------
Parser robusto del fichero de polar XFOIL (texto plano con columnas separadas
por espacios).

Formato de salida XFOIL::

     alpha      CL      CD     CDp      CM   Top_Xtr  Bot_Xtr
    -------   ------  ------  ------  ------  -------  -------
     -5.000  -0.4991  0.0078  0.0020 -0.0524   0.5263   0.0000
     ...

El parser omite silenciosamente las cabeceras y líneas malformadas.
Después de parsear puede ejecutar comprobaciones de calidad mediante
``validate_polar_quality`` del módulo de validaciones.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import pandas as pd

from vfp_analysis.validation.validators import (
    PolarQualityWarning,
    validate_polar_df,
    validate_polar_quality,
)

LOGGER = logging.getLogger(__name__)


def parse_polar_file(
    polar_path: Path | str,
    context: str = "",
    run_quality_checks: bool = True,
) -> pd.DataFrame:
    """Parsea un fichero de polar XFOIL en un DataFrame.

    Columnas devueltas: ``alpha``, ``cl``, ``cd``, ``cm``, ``ld``.

    Parameters
    ----------
    polar_path : Path or str
        Ruta al fichero de salida de XFOIL.
    context : str
        Identificador del caso (ej. "cruise/root") para mensajes de log.
    run_quality_checks : bool
        Si True, ejecuta ``validate_polar_quality`` y registra los avisos.

    Returns
    -------
    pd.DataFrame
        DataFrame vacío si no se encontraron datos válidos.

    Notes
    -----
    - Las líneas con menos de 5 campos numéricos se omiten.
    - ``cd`` negativo o nulo produce ``ld = NaN`` (no divide por cero).
    - Si el fichero no existe lanza ``FileNotFoundError``.
    """
    polar_path = Path(polar_path)
    if not polar_path.exists():
        raise FileNotFoundError(
            f"Fichero polar no encontrado [{context}]: {polar_path}"
        )

    rows: List[dict] = []
    n_skipped = 0

    with polar_path.open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()

            # Primera columna debe ser un número (alpha)
            try:
                alpha = float(parts[0])
            except (ValueError, IndexError):
                continue

            # Necesitamos al menos alpha, CL, CD, CDp, CM (5 campos)
            if len(parts) < 5:
                n_skipped += 1
                continue

            try:
                cl = float(parts[1])
                cd = float(parts[2])
                cm = float(parts[4])
            except ValueError:
                n_skipped += 1
                continue

            ld = cl / cd if cd > 0.0 else float("nan")
            rows.append({"alpha": alpha, "cl": cl, "cd": cd, "cm": cm, "ld": ld})

    if n_skipped > 0:
        LOGGER.debug(
            "Parser XFOIL [%s]: %d líneas omitidas (cabeceras o malformadas)",
            context or polar_path.name,
            n_skipped,
        )

    df = pd.DataFrame(rows)

    if df.empty:
        LOGGER.warning(
            "Polar XFOIL vacío [%s]: %s — sin datos numéricos válidos.",
            context or "?",
            polar_path,
        )
        return df

    # Comprobaciones de calidad
    if run_quality_checks:
        warnings: List[PolarQualityWarning] = validate_polar_quality(
            df, context=context or polar_path.stem
        )
        for w in warnings:
            LOGGER.warning("Calidad polar [%s] %s: %s", w.context, w.code, w.message)

    LOGGER.debug(
        "Polar XFOIL parseado [%s]: %d puntos, α=[%.1f, %.1f], CL=[%.3f, %.3f]",
        context or polar_path.stem,
        len(df),
        df["alpha"].min(),
        df["alpha"].max(),
        df["cl"].min(),
        df["cl"].max(),
    )

    return df
