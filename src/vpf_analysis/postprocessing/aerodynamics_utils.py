"""Shared aerodynamic utilities: efficiency column resolution, peak finding, polar file lookup."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

# Priority-ordered list of known efficiency column names.
_EFFICIENCY_COLUMNS: tuple[str, ...] = (
    "ld_corrected",
    "ld",
)


def resolve_efficiency_column(df: pd.DataFrame) -> str:
    """Return the first available efficiency column (``ld_corrected`` → ``ld``).

    Raises ``KeyError`` if none is present.
    """
    for col in _EFFICIENCY_COLUMNS:
        if col in df.columns:
            return col
    raise KeyError(
        f"No efficiency column found. Available: {list(df.columns)}"
    )


def find_second_peak_row(
    df: pd.DataFrame,
    efficiency_col: str,
    alpha_min: float | None = None,
    cl_min: float | None = None,
    cl_col: str = "cl",
) -> pd.Series:
    """Return the row at maximum efficiency above *alpha_min* (second aerodynamic peak).

    The first XFOIL peak at very low alpha is a laminar-bubble artefact; this
    function skips it by requiring alpha >= alpha_min AND (optionally) cl >= cl_min.
    The CL filter is the more robust guard: it excludes the laminar-bubble regardless
    of whether convergence at high alpha was achieved.

    Falls back to the CL-only filter if the combined filter is empty, then raises
    ``ValueError`` if *df* has no valid rows at all.
    """
    if alpha_min is None:
        from vpf_analysis.settings import get_settings
        alpha_min = get_settings().physics.ALPHA_MIN_OPT_DEG

    df_clean = df.replace([np.inf, -np.inf], np.nan).dropna(
        subset=[efficiency_col, "alpha"]
    )
    if df_clean.empty:
        raise ValueError(
            f"No valid data after removing inf/nan values "
            f"(efficiency column: '{efficiency_col}')."
        )

    alpha_mask = df_clean["alpha"] >= alpha_min
    if cl_min is not None and cl_col in df_clean.columns:
        cl_mask = df_clean[cl_col] >= cl_min
        df_peak = df_clean[alpha_mask & cl_mask]
        # Relax alpha but keep CL filter to exclude laminar bubble
        if df_peak.empty:
            df_peak = df_clean[cl_mask]
            if not df_peak.empty:
                LOGGER.warning(
                    "No data at alpha >= %.1f° with CL >= %.2f. "
                    "Relaxing alpha constraint (CL filter kept).",
                    alpha_min, cl_min,
                )
    else:
        df_peak = df_clean[alpha_mask]

    if df_peak.empty:
        if cl_min is not None:
            # When a CL filter was requested and still no data found, do NOT fall
            # back to the full range — that would select the laminar bubble.
            raise ValueError(
                f"No data with CL >= {cl_min} (column '{cl_col}') in polar. "
                "Cannot determine second aerodynamic peak."
            )
        LOGGER.warning(
            "No data at alpha >= %.1f°. Falling back to full data range.", alpha_min
        )
        df_peak = df_clean

    return df_peak.loc[df_peak[efficiency_col].idxmax()]


def compute_stall_alpha(df: pd.DataFrame, cl_col: str) -> float:
    """Estimate the stall angle: first alpha where CL drops >5 % below CL_max.

    Returns the last available alpha if no clear stall is detected.
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
    """Return efficiency at the polar point closest to *alpha_target*."""
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
    """Locate a polar CSV: hierarchical Stage-3/Stage-2 layout, then flat fallback."""
    base = base_dir / condition.lower() / section
    for name in ("corrected_polar.csv", "polar.csv"):
        candidate = base / name
        if candidate.exists():
            return candidate

    flat = base_dir / f"{condition}_{section}.csv"
    if flat.exists():
        return flat

    return None
