"""
Adapter for writing VPF analysis results to filesystem.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd

from vfp_analysis.vpf_analysis.core.domain.optimal_incidence import (
    OptimalIncidence,
    PitchAdjustment,
)
from vfp_analysis.vpf_analysis.ports.results_writer_port import VpfResultsWriterPort


class FilesystemVpfResultsWriter(VpfResultsWriterPort):
    """Writes VPF analysis results to CSV and text files."""

    def write_optimal_pitch_table(
        self, optimal_incidences: List[OptimalIncidence], output_path: Path
    ) -> None:
        """Write optimal pitch table to CSV."""
        rows = []
        for inc in optimal_incidences:
            rows.append(
                {
                    "condition": inc.condition,
                    "section": inc.section,
                    "Re": inc.reynolds,
                    "Mach": inc.mach,
                    "alpha_opt": inc.alpha_opt,
                    "CL_CD_max": inc.cl_cd_max,
                }
            )

        df = pd.DataFrame(rows)
        df = df.sort_values(["condition", "section"])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.6f")

    def write_pitch_adjustment_table(
        self, adjustments: List[PitchAdjustment], output_path: Path
    ) -> None:
        """Write pitch adjustment table to CSV."""
        rows = []
        for adj in adjustments:
            rows.append(
                {
                    "condition": adj.condition,
                    "section": adj.section,
                    "alpha_opt": adj.alpha_opt,
                    "delta_pitch": adj.delta_pitch,
                }
            )

        df = pd.DataFrame(rows)
        df = df.sort_values(["condition", "section"])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.6f")

    def write_analysis_summary(
        self, summary_text: str, output_path: Path
    ) -> None:
        """Write analysis summary to text file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(summary_text, encoding="utf-8")
