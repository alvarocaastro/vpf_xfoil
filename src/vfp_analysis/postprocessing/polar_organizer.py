"""
Organize polar data into structured output directories.

This module copies and organizes polar CSV files from simulation results
into the standardized results/polars/ directory structure.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List


def organize_polars(
    source_dir: Path,
    target_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """
    Organize polar CSV files into results/polars/ directory.

    Parameters
    ----------
    source_dir : Path
        Source directory containing polar files (e.g., results/stage_2/final_analysis/).
    target_dir : Path
        Target directory (results/polars/).
    flight_conditions : List[str]
        List of flight condition names.
    blade_sections : List[str]
        List of blade section names.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    for flight in flight_conditions:
        for section in blade_sections:
            # Try to find polar CSV in source directory
            source_file = source_dir / flight.lower() / section / "polar.csv"
            if not source_file.exists():
                continue

            # Copy to target with standardized name
            target_file = target_dir / f"{flight}_{section}.csv"
            shutil.copy2(source_file, target_file)
