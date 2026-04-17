"""
Service for applying compressibility corrections to aerodynamic polars.

Applies both Prandtl-Glauert (PG) and Kármán-Tsien (K-T) corrections so that
results can be compared.  Wave drag (Lock's law) is included via the K-T model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import math
import matplotlib.pyplot as plt
import pandas as pd

from vfp_analysis.stage3_compressibility_correction.prandtl_glauert import (
    PrandtlGlauertModel,
)
from vfp_analysis.stage3_compressibility_correction.karman_tsien import (
    KarmanTsienModel,
)
from vfp_analysis.stage3_compressibility_correction.compressibility_case import (
    CompressibilityCase,
)
from vfp_analysis.stage3_compressibility_correction.correction_result import (
    CorrectionResult,
)
from vfp_analysis.stage3_compressibility_correction.critical_mach import (
    estimate_mcr,
)
from vfp_analysis.shared.plot_style import (
    COLORS,
    FLIGHT_LABELS,
    SECTION_LABELS,
    apply_style,
)


class CompressibilityCorrectionService:
    """Orchestrates PG + K-T compressibility corrections for one (flight, section) case."""

    def __init__(
        self,
        pg_model: PrandtlGlauertModel,
        kt_model: KarmanTsienModel,
        base_output_dir: Path,
    ) -> None:
        self._pg = pg_model
        self._kt = kt_model
        self._base_output = base_output_dir

    def correct_case(
        self,
        case: CompressibilityCase,
        input_polar_path: Path,
        section: Optional[str] = None,
    ) -> CorrectionResult:
        """Apply PG + K-T corrections to one polar file."""
        if not input_polar_path.is_file():
            raise FileNotFoundError(f"Polar file not found: {input_polar_path}")

        df_original = pd.read_csv(input_polar_path)

        # Step 1: Prandtl-Glauert correction (adds cl_pg, ld_pg, cd_corrected, mach_target)
        df_pg = self._pg.correct_polar(df_original, case)

        # Step 2: Kármán-Tsien correction (adds cl_kt, ld_kt; updates cd_corrected with wave drag)
        df_corrected = self._kt.correct_polar(df_pg, case)

        output_dir = self._base_output / case.flight_condition.lower()
        if section:
            output_dir = output_dir / section
        output_dir.mkdir(parents=True, exist_ok=True)

        # Single CSV with all correction data
        polar_path = output_dir / "corrected_polar.csv"
        export_cols = ["alpha", "cl", "cl_pg", "cl_kt",
                       "cd", "cd_corrected", "ld_pg", "ld_kt",
                       "mach_target", "re", "ncrit", "cm", "cm_pg", "cm_kt"]
        export_cols = [c for c in export_cols if c in df_corrected.columns]
        df_corrected[export_cols].to_csv(polar_path, index=False, float_format="%.6f")

        plot_path = output_dir / "corrected_plots.png"
        self._plot_comparison(df_original, df_corrected, case, section, plot_path)

        case_name = f"{case.flight_condition}_{section}" if section else case.flight_condition
        return CorrectionResult(
            case=case_name,
            section=section,
            output_dir=output_dir,
            corrected_polar_path=polar_path,
            corrected_cl_alpha_path=polar_path,      # kept for interface compatibility
            corrected_efficiency_path=polar_path,
            corrected_plot_path=plot_path,
        )

    @staticmethod
    def _plot_comparison(
        df_original: pd.DataFrame,
        df_corrected: pd.DataFrame,
        case: CompressibilityCase,
        section: Optional[str],
        output_path: Path,
    ) -> None:
        """
        Plot CL(α) and CL/CD(α) showing three curves:
          - Original XFOIL at M_ref (grey dashed)
          - Prandtl-Glauert at M_target (colour dashed)
          - Kármán-Tsien at M_target (colour solid)
        with Mcr annotated.
        """
        flight = case.flight_condition.lower()
        color  = COLORS.get(flight, "#4477AA")
        flight_label = FLIGHT_LABELS.get(flight, flight.capitalize())
        section_label = SECTION_LABELS.get(section or "", section or "")

        # Estimate Mcr from median operating CL (alpha 3-10°)
        df_op = df_original[(df_original["alpha"] >= 3) & (df_original["alpha"] <= 10)]
        cl_op = float(df_op["cl"].median()) if not df_op.empty else 0.6
        mcr = estimate_mcr(cl_op)
        is_supercritical = case.target_mach > mcr

        with apply_style():
            fig, (ax_cl, ax_eff) = plt.subplots(2, 1, figsize=(6.5, 8.0),
                                                  gridspec_kw={"hspace": 0.35})

            alpha = df_original["alpha"]

            # ── CL vs α ──────────────────────────────────────────────────────
            ax_cl.plot(alpha, df_original["cl"],
                       color="#BBBBBB", linewidth=1.4, linestyle="--",
                       label=f"XFOIL  M = {case.reference_mach:.2f}")
            ax_cl.plot(alpha, df_corrected["cl_pg"],
                       color=color, linewidth=1.6, linestyle="--",
                       label=f"Prandtl-Glauert  M = {case.target_mach:.2f}")
            ax_cl.plot(alpha, df_corrected["cl_kt"],
                       color=color, linewidth=2.2,
                       label=f"Kármán-Tsien  M = {case.target_mach:.2f}")

            # Mcr annotation
            mcr_label = (f"$M_{{cr}}$ ≈ {mcr:.3f}"
                         + ("  ⚠ supercrítico" if is_supercritical else ""))
            ax_cl.axvline(0, color="none")  # placeholder
            ax_cl.annotate(
                mcr_label,
                xy=(0.97, 0.05), xycoords="axes fraction",
                ha="right", fontsize=8,
                color="#E53935" if is_supercritical else "#228833",
                bbox=dict(boxstyle="round,pad=0.3",
                          facecolor="#FFEBEE" if is_supercritical else "#E8F5E9",
                          edgecolor="none", alpha=0.9),
            )

            ax_cl.set_xlabel(r"$\alpha$ [°]")
            ax_cl.set_ylabel(r"$C_L$")
            ax_cl.set_title(
                f"Corrección de compresibilidad — {flight_label} / {section_label}"
            )
            ax_cl.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0)

            # ── CL/CD vs α ───────────────────────────────────────────────────
            ld_orig = df_original["cl"] / df_original["cd"]
            ax_eff.plot(alpha, ld_orig,
                        color="#BBBBBB", linewidth=1.4, linestyle="--",
                        label=f"XFOIL  M = {case.reference_mach:.2f}")
            ax_eff.plot(alpha, df_corrected["ld_pg"],
                        color=color, linewidth=1.6, linestyle="--",
                        label=f"Prandtl-Glauert  M = {case.target_mach:.2f}")
            ax_eff.plot(alpha, df_corrected["ld_kt"],
                        color=color, linewidth=2.2,
                        label=f"Kármán-Tsien  M = {case.target_mach:.2f}")

            ax_eff.set_xlabel(r"$\alpha$ [°]")
            ax_eff.set_ylabel(r"$C_L / C_D$")
            ax_eff.set_title(r"$C_L/C_D$ vs $\alpha$")
            ax_eff.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0)

            fig.savefig(output_path, bbox_inches="tight")
            plt.close(fig)

    @staticmethod
    def plot_section_summary(
        base_output_dir: Path,
        flight_conditions: list[str],
        sections: list[str],
    ) -> None:
        """
        For each blade section, plot CL(α) and CL/CD(α) for all flight conditions
        using the K-T corrected data — one PNG per section saved at base_output_dir level.
        """
        for section in sections:
            with apply_style():
                fig, (ax_cl, ax_eff) = plt.subplots(2, 1, figsize=(7.0, 8.5),
                                                      gridspec_kw={"hspace": 0.38})

                section_label = SECTION_LABELS.get(section, section)
                has_data = False

                for flight in flight_conditions:
                    polar_path = base_output_dir / flight.lower() / section / "corrected_polar.csv"
                    if not polar_path.is_file():
                        continue

                    df = pd.read_csv(polar_path)
                    if "cl_kt" not in df.columns or "ld_kt" not in df.columns:
                        continue

                    color = COLORS.get(flight.lower(), "#4477AA")
                    flight_label = FLIGHT_LABELS.get(flight.lower(), flight.capitalize())
                    mach = float(df["mach_target"].iloc[0]) if "mach_target" in df.columns else 0.0

                    ax_cl.plot(df["alpha"], df["cl_kt"],
                               color=color, linewidth=2.0,
                               label=f"{flight_label}  M = {mach:.2f}")
                    ax_eff.plot(df["alpha"], df["ld_kt"],
                                color=color, linewidth=2.0,
                                label=f"{flight_label}  M = {mach:.2f}")
                    has_data = True

                if not has_data:
                    plt.close(fig)
                    continue

                ax_cl.set_xlabel(r"$\alpha$ [°]")
                ax_cl.set_ylabel(r"$C_L$  (Kármán-Tsien)")
                ax_cl.set_title(f"$C_L$ vs $\\alpha$ por condición — Sección {section_label}")
                ax_cl.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0)

                ax_eff.set_xlabel(r"$\alpha$ [°]")
                ax_eff.set_ylabel(r"$C_L / C_D$  (Kármán-Tsien)")
                ax_eff.set_title(r"$C_L/C_D$ vs $\alpha$ por condición")
                ax_eff.legend(bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0)

                figures_dir = base_output_dir / "figures"
                figures_dir.mkdir(parents=True, exist_ok=True)
                out_path = figures_dir / f"correction_comparison_{section}.png"
                fig.savefig(out_path, bbox_inches="tight")
                plt.close(fig)
