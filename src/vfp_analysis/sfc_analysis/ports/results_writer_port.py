"""
Port interface for writing SFC analysis results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from vfp_analysis.sfc_analysis.core.domain.sfc_parameters import SfcAnalysisResult


class SfcResultsWriterPort(ABC):
    """Interface for writing SFC analysis results."""

    @abstractmethod
    def write_sfc_table(
        self, sfc_results: List[SfcAnalysisResult], output_path: Path
    ) -> None:
        """Write SFC analysis table to CSV."""
        pass

    @abstractmethod
    def write_analysis_summary(
        self, summary_text: str, output_path: Path
    ) -> None:
        """Write SFC analysis summary to text file."""
        pass
