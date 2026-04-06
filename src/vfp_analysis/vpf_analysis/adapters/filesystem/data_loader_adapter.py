"""
Adapter for loading aerodynamic data from filesystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from vfp_analysis.vpf_analysis.ports.data_loader_port import DataLoaderPort


class FilesystemDataLoader(DataLoaderPort):
    """Loads aerodynamic data from CSV files on the filesystem."""

    def load_polar_data(self, polars_dir: Path) -> pd.DataFrame:
        """
        Load all polar data from the polars directory.

        Files are expected to be named: {condition}_{section}.csv
        """
        all_data: List[pd.DataFrame] = []

        if not polars_dir.exists():
            return pd.DataFrame()

        for polar_file in polars_dir.glob("*.csv"):
            # Parse filename: condition_section.csv
            name_parts = polar_file.stem.split("_", 1)
            if len(name_parts) < 2:
                continue

            condition = name_parts[0]
            section = name_parts[1]

            try:
                df = pd.read_csv(polar_file)
                # Add metadata columns
                df["condition"] = condition
                df["section"] = section
                # Standardize efficiency column name (use CL_CD for consistency)
                if "ld" in df.columns and "CL_CD" not in df.columns:
                    df["CL_CD"] = df["ld"]
                all_data.append(df)
            except Exception:
                continue

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        return combined

    def load_compressibility_data(self, compressibility_dir: Path) -> pd.DataFrame:
        """
        Load compressibility-corrected data.

        Expected structure: compressibility_dir/{condition}/{section}/corrected_polar.csv
        """
        all_data: List[pd.DataFrame] = []

        if not compressibility_dir.exists():
            return pd.DataFrame()

        for condition_dir in compressibility_dir.iterdir():
            if not condition_dir.is_dir():
                continue

            condition = condition_dir.name

            for section_dir in condition_dir.iterdir():
                if not section_dir.is_dir():
                    continue

                section = section_dir.name
                corrected_file = section_dir / "corrected_polar.csv"

                if not corrected_file.exists():
                    continue

                try:
                    df = pd.read_csv(corrected_file)
                    # Add metadata
                    df["condition"] = condition
                    df["section"] = section
                    all_data.append(df)
                except Exception:
                    continue

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        return combined
