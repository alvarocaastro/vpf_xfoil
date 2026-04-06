"""
Adapter for writing corrected results to filesystem.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from vfp_analysis.compressibility.ports.corrected_results_writer_port import (
    CorrectedResultsWriterPort,
)


class FilesystemResultsWriter(CorrectedResultsWriterPort):
    """Writes corrected results to CSV files."""

    def write_corrected_polar(
        self, df: pd.DataFrame, output_path: Path
    ) -> None:
        """Write corrected polar CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.6f")

    def write_corrected_cl_alpha(
        self, df: pd.DataFrame, output_path: Path
    ) -> None:
        """Write corrected CL vs alpha CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df[["alpha", "cl_corrected"]].to_csv(
            output_path, index=False, float_format="%.6f"
        )

    def write_corrected_efficiency(
        self, df: pd.DataFrame, output_path: Path
    ) -> None:
        """Write corrected efficiency CSV."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df[["alpha", "ld_corrected"]].to_csv(
            output_path, index=False, float_format="%.6f"
        )
