"""
Adapter for writing SFC analysis results to filesystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from vfp_analysis.sfc_analysis.core.domain.sfc_parameters import SfcAnalysisResult
from vfp_analysis.sfc_analysis.ports.results_writer_port import SfcResultsWriterPort


class FilesystemSfcResultsWriter(SfcResultsWriterPort):
    """Writes SFC analysis results to CSV and text files."""

    def write_sfc_table(
        self, sfc_results: List[SfcAnalysisResult], output_path: Path
    ) -> None:
        """Write SFC analysis table to CSV."""
        rows = []
        for result in sfc_results:
            rows.append(
                {
                    "condition": result.condition,
                    "CL_CD_baseline": result.cl_cd_baseline,
                    "CL_CD_vpf": result.cl_cd_vpf,
                    "fan_efficiency_baseline": result.fan_efficiency_baseline,
                    "fan_efficiency_new": result.fan_efficiency_new,
                    "SFC_baseline": result.sfc_baseline,
                    "SFC_new": result.sfc_new,
                    "SFC_reduction_percent": result.sfc_reduction_percent,
                }
            )

        df = pd.DataFrame(rows)
        df = df.sort_values("condition")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.6f")

    def write_analysis_summary(
        self, summary_text: str, output_path: Path
    ) -> None:
        """Write SFC analysis summary to text file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(summary_text, encoding="utf-8")
