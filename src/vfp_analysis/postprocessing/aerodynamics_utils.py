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
    "ld_kt",
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


def compute_stall_alpha(df: pd.DataFrame, cl_col: str) -> float:
    """Estimate the stall angle from a polar DataFrame.

    Stall is defined as the angle of attack where CL drops by more than
    5 % of CL_max after the CL_max point. This threshold is consistent
    with the soft-stall detection approach used for NACA 6-series profiles
    (see NACA TN-1135 / Jacobs & Sherman 1937).

    If no clear drop is detected (e.g. polar ends before stall), the last
    available alpha is returned and a warning is logged.

    Parameters
    ----------
    df:
        Polar data. Must contain ``alpha`` and *cl_col* columns.
    cl_col:
        Name of the lift-coefficient column.

    Returns
    -------
    float
        Estimated stall angle in degrees.
    """
    df_clean = (
        df[["alpha", cl_col]]
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
        .sort_values("alpha")
        .reset_index(drop=True)
    )

    if df_clean.empty:
        raise ValueError(f"No valid data in polar for stall detection (column: '{cl_col}').")

    idx_clmax = int(df_clean[cl_col].idxmax())
    cl_max = float(df_clean[cl_col].iloc[idx_clmax])
    threshold = 0.05 * cl_max

    post_peak = df_clean.iloc[idx_clmax + 1 :]
    stall_rows = post_peak[post_peak[cl_col] < (cl_max - threshold)]

    if stall_rows.empty:
        alpha_stall = float(df_clean["alpha"].iloc[-1])
        LOGGER.warning(
            "No clear stall detected (CL never drops %.0f%% below CL_max=%.3f). "
            "Using last alpha=%.2f° as stall estimate.",
            5,
            cl_max,
            alpha_stall,
        )
        return alpha_stall

    return float(stall_rows["alpha"].iloc[0])


def lookup_efficiency_at_alpha(
    df: pd.DataFrame,
    efficiency_col: str,
    alpha_target: float,
) -> float:
    """Return the efficiency value at the polar point closest to *alpha_target*.

    Used to evaluate (CL/CD) at the design reference angle (α_opt_cruise) in
    non-cruise conditions, quantifying the fixed-pitch efficiency penalty.

    Parameters
    ----------
    df:
        Polar DataFrame. Must contain ``alpha`` and *efficiency_col*.
    efficiency_col:
        Name of the efficiency column.
    alpha_target:
        Target angle of attack in degrees.

    Returns
    -------
    float
        Efficiency at the nearest available alpha point.
    """
    df_clean = (
        df[["alpha", efficiency_col]]
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    if df_clean.empty:
        return float("nan")
    idx = (df_clean["alpha"] - alpha_target).abs().idxmin()
    return float(df_clean.loc[idx, efficiency_col])


def resolve_polar_file(base_dir: Path, condition: str, section: str) -> Path | None:
    """Locate a polar CSV file supporting two directory layouts and two file names.

    Checks in order:

    1. ``base_dir / condition / section / corrected_polar.csv`` (Stage 3 output)
    2. ``base_dir / condition / section / polar.csv``           (Stage 2 hierarchical)
    3. ``base_dir / condition_section.csv``                     (flat layout)

    Returns ``None`` if none of the locations exist.
    """
    base = base_dir / condition.lower() / section
    for name in ("corrected_polar.csv", "polar.csv"):
        candidate = base / name
        if candidate.exists():
            return candidate

    flat = base_dir / f"{condition}_{section}.csv"
    if flat.exists():
        return flat

    return None
