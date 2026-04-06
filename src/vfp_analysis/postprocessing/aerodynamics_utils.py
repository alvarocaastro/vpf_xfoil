"""
Shared aerodynamic utilities used across postprocessing and VPF analysis.

Centralises three pieces of logic that were previously duplicated across
multiple modules:

  - resolve_efficiency_column  — find the correct CL/CD column in a DataFrame
  - find_second_peak_row       — locate the optimal operating point (2nd peak)
  - resolve_polar_file         — find a polar CSV in hierarchical or flat layout
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

# Priority-ordered list of known efficiency column names.
_EFFICIENCY_COLUMNS: tuple[str, ...] = (
    "ld_corrected",
    "CL_CD_corrected",
    "ld",
    "CL_CD",
)


def resolve_efficiency_column(df: pd.DataFrame) -> str:
    """Return the name of the first available efficiency column in *df*.

    Raises
    ------
    ValueError
        If none of the expected columns is present.
    """
    for col in _EFFICIENCY_COLUMNS:
        if col in df.columns:
            return col
    raise ValueError(
        f"No efficiency column found in DataFrame. "
        f"Expected one of: {list(_EFFICIENCY_COLUMNS)}. "
        f"Available columns: {list(df.columns)}"
    )


def find_second_peak_row(
    df: pd.DataFrame,
    efficiency_col: str,
    alpha_min: float = 3.0,
) -> pd.Series:
    """Return the row at maximum efficiency in the second aerodynamic peak.

    The first CL/CD peak predicted by XFOIL at very low alpha (typically < 3°)
    is associated with laminar separation bubble effects and is not
    representative of real turbomachinery operation. This function focuses on
    the second peak (alpha >= *alpha_min*) which corresponds to the actual fan
    blade operating range.

    Falls back to the full data range if no valid points exist above *alpha_min*,
    logging a warning in that case.

    Parameters
    ----------
    df:
        Polar data. Must contain columns ``alpha`` and *efficiency_col*.
    efficiency_col:
        Name of the efficiency column to maximise.
    alpha_min:
        Lower bound for the second-peak search (degrees).

    Raises
    ------
    ValueError
        If *df* contains no valid (non-inf, non-nan) rows.
    """
    df_clean = df.replace([np.inf, -np.inf], np.nan).dropna(
        subset=[efficiency_col, "alpha"]
    )
    if df_clean.empty:
        raise ValueError(
            f"No valid data after removing inf/nan values "
            f"(efficiency column: '{efficiency_col}')."
        )

    df_peak = df_clean[df_clean["alpha"] >= alpha_min]
    if df_peak.empty:
        LOGGER.warning(
            "No data at alpha >= %.1f°. Falling back to full data range.", alpha_min
        )
        df_peak = df_clean

    return df_peak.loc[df_peak[efficiency_col].idxmax()]


def resolve_polar_file(base_dir: Path, condition: str, section: str) -> Path | None:
    """Locate a polar CSV file supporting two directory layouts.

    Checks in order:

    1. ``base_dir / condition / section / polar.csv``  (hierarchical layout)
    2. ``base_dir / condition_section.csv``            (flat layout)

    Returns ``None`` if neither location contains the file.
    """
    hierarchical = base_dir / condition.lower() / section / "polar.csv"
    if hierarchical.exists():
        return hierarchical

    flat = base_dir / f"{condition}_{section}.csv"
    if flat.exists():
        return flat

    return None
