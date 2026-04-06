"""
Port interface for writing VPF analysis results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from vfp_analysis.vpf_analysis.core.domain.optimal_incidence import (
    OptimalIncidence,
    PitchAdjustment,
)


class VpfResultsWriterPort(ABC):
    """Interface for writing VPF analysis results."""

    @abstractmethod
    def write_optimal_pitch_table(
        self, optimal_incidences: List[OptimalIncidence], output_path: Path
    ) -> None:
        """Write optimal pitch table to CSV."""
        pass

    @abstractmethod
    def write_pitch_adjustment_table(
        self, adjustments: List[PitchAdjustment], output_path: Path
    ) -> None:
        """Write pitch adjustment table to CSV."""
        pass

    @abstractmethod
    def write_analysis_summary(
        self, summary_text: str, output_path: Path
    ) -> None:
        """Write analysis summary to text file."""
        pass
