"""
Pytest configuration and shared fixtures.

This module provides reusable fixtures for all tests.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

import pandas as pd
import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vfp_analysis.core.domain.airfoil import Airfoil
from vfp_analysis.core.domain.simulation_condition import SimulationCondition


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def data_dir(project_root: Path) -> Path:
    """Return the data directory path."""
    return project_root / "data" / "airfoils"


@pytest.fixture
def sample_airfoil_dat(data_dir: Path) -> Path:
    """Return path to a sample airfoil .dat file."""
    naca0012_path = data_dir / "naca0012.dat"
    if not naca0012_path.exists():
        pytest.skip(f"Sample airfoil file not found: {naca0012_path}")
    return naca0012_path


@pytest.fixture
def sample_airfoil(sample_airfoil_dat: Path) -> Airfoil:
    """Create a sample Airfoil instance."""
    return Airfoil(
        name="NACA 0012",
        family="NACA 00-series",
        dat_path=sample_airfoil_dat,
    )


@pytest.fixture
def sample_simulation_condition() -> SimulationCondition:
    """Create a sample simulation condition."""
    return SimulationCondition(
        name="Test",
        mach_rel=0.2,
        reynolds=3.0e6,
        alpha_min=-5.0,
        alpha_max=20.0,
        alpha_step=0.5,
        ncrit=7.0,
    )


@pytest.fixture
def sample_polar_data() -> pd.DataFrame:
    """Create sample polar data for testing."""
    return pd.DataFrame(
        {
            "alpha": [-5.0, 0.0, 5.0, 10.0, 15.0],
            "cl": [0.1, 0.3, 0.6, 0.9, 1.1],
            "cd": [0.01, 0.02, 0.03, 0.05, 0.08],
            "cm": [-0.05, -0.02, 0.0, 0.02, 0.05],
            "ld": [10.0, 15.0, 20.0, 18.0, 13.75],
        }
    )


@pytest.fixture
def empty_polar_data() -> pd.DataFrame:
    """Create an empty polar DataFrame."""
    return pd.DataFrame(columns=["alpha", "cl", "cd", "cm", "ld"])
