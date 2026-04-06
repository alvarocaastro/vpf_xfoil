"""
Port interface for reading aerodynamic polar data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class PolarReaderPort(ABC):
    """Interface for reading polar data from filesystem."""

    @abstractmethod
    def read_polar(self, polar_path: Path) -> pd.DataFrame:
        """
        Read polar data from a CSV file.

        Parameters
        ----------
        polar_path : Path
            Path to the polar CSV file.

        Returns
        -------
        pd.DataFrame
            DataFrame with columns: alpha, cl, cd, cm, ld, etc.
        """
        pass
