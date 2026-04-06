"""
Port interface for writing corrected results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class CorrectedResultsWriterPort(ABC):
    """Interface for writing corrected aerodynamic results."""

    @abstractmethod
    def write_corrected_polar(
        self, df: pd.DataFrame, output_path: Path
    ) -> None:
        """Write corrected polar data to CSV."""
        pass

    @abstractmethod
    def write_corrected_cl_alpha(
        self, df: pd.DataFrame, output_path: Path
    ) -> None:
        """Write corrected CL vs alpha to CSV."""
        pass

    @abstractmethod
    def write_corrected_efficiency(
        self, df: pd.DataFrame, output_path: Path
    ) -> None:
        """Write corrected efficiency (CL/CD) to CSV."""
        pass
