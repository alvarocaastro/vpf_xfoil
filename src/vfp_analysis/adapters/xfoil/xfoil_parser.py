"""
xfoil_parser.py
---------------
Shared utility for parsing XFOIL polar output files into DataFrames.

Used by stage1_airfoil_selection and stage2_xfoil_simulations to avoid
duplicating the same text-parsing logic.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def parse_polar_file(polar_path: Path | str) -> pd.DataFrame:
    """Parse an XFOIL plain-text polar file into a DataFrame.

    Returns a DataFrame with columns:
        alpha, cl, cd, cm, ld

    Lines that cannot be parsed as numeric data are silently skipped.
    The caller is responsible for adding any metadata columns
    (airfoil name, flight condition, section, Re, Ncrit, Mach, …).

    Parameters
    ----------
    polar_path:
        Path to the XFOIL output file (space-separated values).

    Returns
    -------
    pd.DataFrame
        Empty DataFrame if no valid data rows were found.
    """
    rows = []
    with Path(polar_path).open("r", encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            try:
                alpha = float(parts[0])
            except (ValueError, IndexError):
                continue
            if len(parts) < 5:
                continue
            try:
                cl = float(parts[1])
                cd = float(parts[2])
                cm = float(parts[4])
            except ValueError:
                continue
            ld = cl / cd if cd > 0.0 else float("nan")
            rows.append({"alpha": alpha, "cl": cl, "cd": cd, "cm": cm, "ld": ld})
    return pd.DataFrame(rows)
