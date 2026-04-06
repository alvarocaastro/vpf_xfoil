"""
Service for applying compressibility corrections to aerodynamic results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

from vfp_analysis.compressibility.adapters.correction_models.prandtl_glauert_model import (
    PrandtlGlauertModel,
)
from vfp_analysis.compressibility.core.domain.compressibility_case import (
    CompressibilityCase,
)
from vfp_analysis.compressibility.core.domain.correction_result import (
    CorrectionResult,
)
from vfp_analysis.compressibility.ports.corrected_results_writer_port import (
    CorrectedResultsWriterPort,
)
from vfp_analysis.compressibility.ports.polar_reader_port import PolarReaderPort


class CompressibilityCorrectionService:
    """Service that orchestrates compressibility correction."""

    def __init__(
        self,
        polar_reader: PolarReaderPort,
        results_writer: CorrectedResultsWriterPort,
        correction_model: PrandtlGlauertModel,
        base_output_dir: Path,
    ) -> None:
        self._reader = polar_reader
        self._writer = results_writer
        self._model = correction_model
        self._base_output = base_output_dir

    def correct_case(
        self,
        case: CompressibilityCase,
        input_polar_path: Path,
        section: Optional[str] = None,
    ) -> CorrectionResult:
        """
        Apply compressibility correction to one case.

        Parameters
        ----------
        case : CompressibilityCase
            Correction case (flight condition, target Mach).
        input_polar_path : Path
            Path to original polar CSV from XFOIL.
        section : Optional[str]
            Blade section name (root, mid_span, tip) if applicable.

        Returns
        -------
        CorrectionResult
            Paths to generated corrected files.
        """
        # Read original polar
        df_original = self._reader.read_polar(input_polar_path)

        # Apply correction
        df_corrected = self._model.correct_polar(df_original, case)

        # Build output directory
        output_dir = self._base_output / case.flight_condition.lower()
        if section:
            output_dir = output_dir / section
        output_dir.mkdir(parents=True, exist_ok=True)

        # Write corrected CSVs
        polar_path = output_dir / "corrected_polar.csv"
        cl_alpha_path = output_dir / "corrected_cl_alpha.csv"
        efficiency_path = output_dir / "corrected_efficiency.csv"
        plot_path = output_dir / "corrected_plots.png"

        self._writer.write_corrected_polar(df_corrected, polar_path)
        self._writer.write_corrected_cl_alpha(df_corrected, cl_alpha_path)
        self._writer.write_corrected_efficiency(df_corrected, efficiency_path)

        # Generate comparison plots
        self._plot_comparison(df_original, df_corrected, case, plot_path)

        case_name = f"{case.flight_condition}_{section}" if section else case.flight_condition

        return CorrectionResult(
            case=case_name,
            section=section,
            output_dir=output_dir,
            corrected_polar_path=polar_path,
            corrected_cl_alpha_path=cl_alpha_path,
            corrected_efficiency_path=efficiency_path,
            corrected_plot_path=plot_path,
        )

    @staticmethod
    def _plot_comparison(
        df_original: pd.DataFrame,
        df_corrected: pd.DataFrame,
        case: CompressibilityCase,
        output_path: Path,
    ) -> None:
        """Generate comparison plots: original vs corrected."""
        fig, axes = plt.subplots(2, 1, figsize=(6.0, 8.0))

        # Plot 1: CL vs alpha
        ax1 = axes[0]
        ax1.plot(
            df_original["alpha"],
            df_original["cl"],
            label=f"Original (M={case.reference_mach:.2f})",
            linewidth=1.4,
            linestyle="--",
        )
        ax1.plot(
            df_corrected["alpha"],
            df_corrected["cl_corrected"],
            label=f"Corrected (M={case.target_mach:.2f})",
            linewidth=1.6,
        )
        ax1.set_xlabel(r"$\alpha$ [deg]")
        ax1.set_ylabel(r"$C_L$")
        ax1.set_title(f"$C_L$ vs $\\alpha$ – {case.flight_condition}")
        ax1.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
        ax1.legend(loc="best")

        # Plot 2: CL/CD vs alpha
        ax2 = axes[1]
        ld_original = df_original["cl"] / df_original["cd"]
        ax2.plot(
            df_original["alpha"],
            ld_original,
            label=f"Original (M={case.reference_mach:.2f})",
            linewidth=1.4,
            linestyle="--",
        )
        ax2.plot(
            df_corrected["alpha"],
            df_corrected["ld_corrected"],
            label=f"Corrected (M={case.target_mach:.2f})",
            linewidth=1.6,
        )
        ax2.set_xlabel(r"$\alpha$ [deg]")
        ax2.set_ylabel(r"$C_L/C_D$")
        ax2.set_title(f"Eficiencia $C_L/C_D$ vs $\\alpha$ – {case.flight_condition}")
        ax2.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
        ax2.legend(loc="best")

        fig.tight_layout()
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
