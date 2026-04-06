"""
Port interface for loading SFC analysis data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from vfp_analysis.sfc_analysis.core.domain.sfc_parameters import EngineBaseline


class SfcDataLoaderPort(ABC):
    """Interface for loading data for SFC analysis."""

    @abstractmethod
    def load_performance_data(self, performance_path: Path) -> pd.DataFrame:
        """
        Load aerodynamic performance data.

        Parameters
        ----------
        performance_path : Path
            Path to performance summary CSV.

        Returns
        -------
        pd.DataFrame
            Performance data with efficiency metrics.
        """
        pass

    @abstractmethod
    def load_optimal_pitch_data(self, optimal_pitch_path: Path) -> pd.DataFrame:
        """
        Load optimal pitch data from VPF analysis.

        Parameters
        ----------
        optimal_pitch_path : Path
            Path to vpf_optimal_pitch.csv

        Returns
        -------
        pd.DataFrame
            Optimal pitch data with CL_CD_max values.
        """
        pass

    @abstractmethod
    def load_engine_baseline(self, config_path: Path) -> EngineBaseline:
        """
        Load baseline engine parameters from configuration.

        Parameters
        ----------
        config_path : Path
            Path to engine_parameters.yaml

        Returns
        -------
        EngineBaseline
            Baseline engine parameters.
        """
        pass
