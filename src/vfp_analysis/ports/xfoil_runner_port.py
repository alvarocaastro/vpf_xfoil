from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from vfp_analysis.core.domain.simulation_condition import SimulationCondition


class XfoilRunnerPort(ABC):
    """Port for running XFOIL polars."""

    @abstractmethod
    def run_polar(
        self,
        airfoil_dat: Path,
        condition: SimulationCondition,
        output_file: Path,
    ) -> None:
        """Run a polar computation and write results to output_file."""


