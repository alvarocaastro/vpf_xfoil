"""
Port interface for loading aerodynamic data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class DataLoaderPort(ABC):
    """Interface for loading aerodynamic polar data."""

    @abstractmethod
    def load_polar_data(self, polars_dir: Path) -> pd.DataFrame:
        """
        Load all polar data from the polars directory.

        Parameters
        ----------
        polars_dir : Path
            Directory containing polar CSV files.

        Returns
        -------
        pd.DataFrame
            Combined polar data with columns: condition, section, Re, alpha, CL, CD, CL_CD
        """
        pass

    @abstractmethod
    def load_compressibility_data(self, compressibility_dir: Path) -> pd.DataFrame:
        """
        Load compressibility-corrected data.

        Parameters
        ----------
        compressibility_dir : Path
            Directory containing corrected polar CSV files.

        Returns
        -------
        pd.DataFrame
            Corrected data with columns: condition, section, alpha, CL_corrected, CL_CD_corrected
        """
        pass
