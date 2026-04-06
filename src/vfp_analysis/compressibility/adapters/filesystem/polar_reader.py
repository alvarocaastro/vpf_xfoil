"""
Adapter for reading polar data from CSV files.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from vfp_analysis.compressibility.ports.polar_reader_port import PolarReaderPort


class FilesystemPolarReader(PolarReaderPort):
    """Reads polar data from CSV files on the filesystem."""

    def read_polar(self, polar_path: Path) -> pd.DataFrame:
        """Read polar CSV and return DataFrame."""
        if not polar_path.is_file():
            raise FileNotFoundError(f"Polar file not found: {polar_path}")
        return pd.read_csv(polar_path)
