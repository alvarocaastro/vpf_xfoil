"""
Adapter for loading SFC analysis data from filesystem.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from vfp_analysis.sfc_analysis.core.domain.sfc_parameters import EngineBaseline
from vfp_analysis.sfc_analysis.ports.data_loader_port import SfcDataLoaderPort


class FilesystemSfcDataLoader(SfcDataLoaderPort):
    """Loads SFC analysis data from CSV and YAML files."""

    def load_performance_data(self, performance_path: Path) -> pd.DataFrame:
        """Load aerodynamic performance data."""
        if not performance_path.exists():
            return pd.DataFrame()

        try:
            df = pd.read_csv(performance_path)
            return df
        except Exception:
            return pd.DataFrame()

    def load_optimal_pitch_data(self, optimal_pitch_path: Path) -> pd.DataFrame:
        """Load optimal pitch data from VPF analysis."""
        if not optimal_pitch_path.exists():
            return pd.DataFrame()

        try:
            df = pd.read_csv(optimal_pitch_path)
            return df
        except Exception:
            return pd.DataFrame()

    def load_engine_baseline(self, config_path: Path) -> EngineBaseline:
        """Load baseline engine parameters from configuration."""
        if not config_path.exists():
            raise FileNotFoundError(f"Engine configuration not found: {config_path}")

        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        return EngineBaseline(
            baseline_sfc=config["baseline_sfc"],
            fan_efficiency=config["fan_efficiency"],
            bypass_ratio=config["bypass_ratio"],
            cruise_velocity=config["cruise_velocity"],
            jet_velocity=config["jet_velocity"],
        )
