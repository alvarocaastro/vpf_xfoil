"""
Application script for running Variable Pitch Fan analysis.

This script orchestrates the VPF analysis stage, computing optimal incidence
angles and pitch adjustments from previous aerodynamic simulation results.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis import config as base_config
from vfp_analysis.config_loader import get_output_dirs
from vfp_analysis.postprocessing.figure_generator import _apply_plot_style
from vfp_analysis.vpf_analysis.adapters.filesystem.data_loader_adapter import (
    FilesystemDataLoader,
)
from vfp_analysis.vpf_analysis.adapters.filesystem.results_writer_adapter import (
    FilesystemVpfResultsWriter,
)
from vfp_analysis.vpf_analysis.core.services.optimal_incidence_service import (
    compute_all_optimal_incidences,
)
from vfp_analysis.vpf_analysis.core.services.pitch_adjustment_service import (
    compute_pitch_adjustments,
)
from vfp_analysis.vpf_analysis.core.services.summary_generator_service import (
    generate_analysis_summary,
)

LOGGER = logging.getLogger(__name__)

# Canonical colors for each blade section — consistent across all VPF figures.
_SECTION_COLORS: Dict[str, str] = {
    "root": "#1f77b4",     # blue
    "mid_span": "#ff7f0e", # orange
    "tip": "#2ca02c",      # green
}
_SECTIONS: List[str] = ["root", "mid_span", "tip"]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_condition_section_table(
    items: list,
    value_attr: str,
) -> Dict[str, Dict[str, float]]:
    """Build a ``{condition: {section: value}}`` lookup from a list of dataclass items."""
    table: Dict[str, Dict[str, float]] = {}
    for item in items:
        table.setdefault(item.condition, {})[item.section] = getattr(item, value_attr)
    return table


def _plot_grouped_bars(
    ax: plt.Axes,
    data: Dict[str, Dict[str, float]],
    conditions: List[str],
    sections: List[str],
    zero_line: bool = False,
) -> None:
    """Render grouped bar chart on *ax* and optionally add a zero reference line.

    Parameters
    ----------
    ax:
        Target axes.
    data:
        Nested ``{condition: {section: value}}`` mapping.
    conditions:
        Ordered list of flight conditions (x-axis groups).
    sections:
        Ordered list of blade sections (bars within each group).
    zero_line:
        When True, draw a dashed horizontal line at y = 0.
    """
    x = np.arange(len(conditions))
    width = 0.25

    for i, section in enumerate(sections):
        values = [data.get(cond, {}).get(section, np.nan) for cond in conditions]
        bars = ax.bar(
            x + i * width,
            values,
            width,
            label=section.replace("_", " ").title(),
            color=_SECTION_COLORS[section],
        )
        ax.bar_label(bars, fmt="%.2f", padding=3, fontsize=8)

    if zero_line:
        ax.axhline(0, color="black", linestyle="--", linewidth=0.8)

    n_sections = len(sections)
    ax.set_xticks(x + width * (n_sections - 1) / 2)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.legend()
    _apply_plot_style(ax)


# ---------------------------------------------------------------------------
# Figure functions
# ---------------------------------------------------------------------------

def generate_vpf_figures(
    optimal_incidences: list,
    pitch_adjustments: list,
    df_polars: pd.DataFrame,
    figures_dir: Path,
) -> None:
    """Generate all VPF analysis figures."""
    figures_dir.mkdir(parents=True, exist_ok=True)

    _plot_alpha_opt_vs_condition(optimal_incidences, figures_dir)
    _plot_pitch_adjustment(pitch_adjustments, figures_dir)
    _plot_efficiency_curves_with_optimum(df_polars, optimal_incidences, figures_dir)
    _plot_section_comparison(optimal_incidences, figures_dir)


def _plot_alpha_opt_vs_condition(optimal_incidences: list, figures_dir: Path) -> None:
    """Plot optimal angle of attack per flight condition, grouped by blade section."""
    data = _build_condition_section_table(optimal_incidences, "alpha_opt")
    conditions = sorted(data.keys())

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    _plot_grouped_bars(ax, data, conditions, _SECTIONS)
    ax.set_xlabel("Flight Condition", fontsize=12)
    ax.set_ylabel(r"$\alpha_{opt}$ [deg]", fontsize=12)
    ax.set_title("Optimal Angle of Attack by Flight Condition", fontsize=14)
    fig.tight_layout()
    fig.savefig(
        figures_dir / "vpf_alpha_opt_vs_condition.png", dpi=300, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_pitch_adjustment(pitch_adjustments: list, figures_dir: Path) -> None:
    """Plot required pitch adjustment relative to cruise per condition."""
    data = _build_condition_section_table(pitch_adjustments, "delta_pitch")
    conditions = sorted(data.keys())

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    _plot_grouped_bars(ax, data, conditions, _SECTIONS, zero_line=True)
    ax.set_xlabel("Flight Condition", fontsize=12)
    ax.set_ylabel(r"$\Delta$ Pitch [deg]", fontsize=12)
    ax.set_title("Required Pitch Adjustment Relative to Cruise", fontsize=14)
    fig.tight_layout()
    fig.savefig(
        figures_dir / "vpf_pitch_adjustment.png", dpi=300, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_efficiency_curves_with_optimum(
    df_polars: pd.DataFrame,
    optimal_incidences: list,
    figures_dir: Path,
) -> None:
    """Plot efficiency curves with optimal operating points highlighted."""
    opt_lookup: Dict[tuple, tuple] = {
        (inc.condition, inc.section): (inc.alpha_opt, inc.cl_cd_max)
        for inc in optimal_incidences
    }

    # Determine efficiency column (prefer CL_CD, fallback to ld)
    eff_col: Optional[str] = None
    for candidate in ("CL_CD", "ld"):
        if candidate in df_polars.columns:
            eff_col = candidate
            break

    if eff_col is None:
        LOGGER.warning("No efficiency column found in polar data — skipping efficiency curves.")
        return

    for condition in df_polars["condition"].unique():
        df_cond = df_polars[df_polars["condition"] == condition]

        fig, ax = plt.subplots(figsize=(7.0, 5.0))

        for section in _SECTIONS:
            df_section = df_cond[df_cond["section"] == section]
            if df_section.empty:
                continue

            ax.plot(
                df_section["alpha"],
                df_section[eff_col],
                label=section.replace("_", " ").title(),
                linewidth=1.6,
                color=_SECTION_COLORS[section],
            )

            key = (condition, section)
            if key in opt_lookup:
                alpha_opt, eff_max = opt_lookup[key]
                ax.plot(
                    alpha_opt,
                    eff_max,
                    marker="X",
                    color="red",
                    markersize=10,
                    markeredgecolor="darkred",
                    markeredgewidth=1.5,
                    zorder=5,
                )

        ax.set_xlabel(r"$\alpha$ [deg]", fontsize=12)
        ax.set_ylabel(r"$C_L/C_D$", fontsize=12)
        ax.set_title(
            f"Efficiency Curves with Optimal Points – {condition.title()}", fontsize=14
        )
        ax.legend()
        _apply_plot_style(ax)
        fig.tight_layout()
        fig.savefig(
            figures_dir / f"vpf_efficiency_curves_{condition}.png",
            dpi=300,
            bbox_inches="tight",
        )
        plt.close(fig)


def _plot_section_comparison(optimal_incidences: list, figures_dir: Path) -> None:
    """Plot optimal angle comparison across blade sections for each condition."""
    conditions = sorted(set(inc.condition for inc in optimal_incidences))

    # Invert structure to {section: {condition: alpha_opt}}
    by_section: Dict[str, Dict[str, float]] = {}
    for inc in optimal_incidences:
        by_section.setdefault(inc.section, {})[inc.condition] = inc.alpha_opt

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    x = np.arange(len(_SECTIONS))
    width = 0.2

    for i, condition in enumerate(conditions):
        values = [by_section.get(section, {}).get(condition, np.nan) for section in _SECTIONS]
        ax.bar(x + i * width, values, width, label=condition.title())

    ax.set_xlabel("Blade Section", fontsize=12)
    ax.set_ylabel(r"$\alpha_{opt}$ [deg]", fontsize=12)
    ax.set_title("Optimal Angle of Attack by Blade Section", fontsize=14)
    ax.set_xticks(x + width * (len(conditions) - 1) / 2)
    ax.set_xticklabels([s.replace("_", " ").title() for s in _SECTIONS])
    ax.legend()
    _apply_plot_style(ax)
    fig.tight_layout()
    fig.savefig(figures_dir / "vpf_section_comparison.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_vpf_analysis() -> None:
    """Execute the complete VPF analysis stage."""
    LOGGER.info("=" * 70)
    LOGGER.info("STAGE 6: Variable Pitch Fan Aerodynamic Analysis")
    LOGGER.info("=" * 70)

    output_dirs = get_output_dirs()
    polars_dir = output_dirs["polars"]
    compressibility_dir = output_dirs["compressibility"]
    tables_dir = output_dirs["tables"]
    figures_vpf_dir = output_dirs["figures_vpf"]
    stage6_dir = base_config.RESULTS_DIR / "stage_6"
    stage6_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Load data
    LOGGER.info("Loading aerodynamic data...")
    loader = FilesystemDataLoader()
    df_polars = loader.load_polar_data(polars_dir)
    df_corrected = loader.load_compressibility_data(compressibility_dir)

    if df_polars.empty:
        LOGGER.warning("No polar data found. Skipping VPF analysis.")
        return

    LOGGER.info("Loaded %d polar data points", len(df_polars))
    if not df_corrected.empty:
        LOGGER.info("Loaded %d corrected data points", len(df_corrected))

    # Step 2: Compute optimal incidence
    LOGGER.info("Computing optimal incidence angles...")
    optimal_incidences = compute_all_optimal_incidences(df_polars, df_corrected)
    LOGGER.info("Computed optimal incidence for %d cases", len(optimal_incidences))

    # Step 3: Compute pitch adjustments
    LOGGER.info("Computing pitch adjustments relative to cruise...")
    pitch_adjustments = compute_pitch_adjustments(optimal_incidences, reference_condition="cruise")
    LOGGER.info("Computed pitch adjustments for %d cases", len(pitch_adjustments))

    # Step 4: Generate figures
    LOGGER.info("Generating VPF analysis figures...")
    generate_vpf_figures(optimal_incidences, pitch_adjustments, df_polars, figures_vpf_dir)

    # Step 5: Write results
    LOGGER.info("Writing analysis results...")
    writer = FilesystemVpfResultsWriter()
    writer.write_optimal_pitch_table(
        optimal_incidences, tables_dir / "vpf_optimal_pitch.csv"
    )
    writer.write_pitch_adjustment_table(
        pitch_adjustments, tables_dir / "vpf_pitch_adjustment.csv"
    )

    # Generate and write VPF-specific summary
    vpf_summary = generate_analysis_summary(optimal_incidences, pitch_adjustments)
    writer.write_analysis_summary(vpf_summary, output_dirs["vpf_analysis_summary"])

    # Generate and write Stage 6 summary
    from vfp_analysis.postprocessing.stage_summary_generator import (
        generate_stage6_summary,
        write_stage_summary,
    )

    stage6_summary = generate_stage6_summary(stage6_dir)
    write_stage_summary(6, stage6_summary, stage6_dir)
    LOGGER.info("Stage 6 summary written to: %s", stage6_dir / "finalresults_stage6.txt")

    LOGGER.info("=" * 70)
    LOGGER.info("Stage 6 completed successfully!")
    LOGGER.info("Results saved in:")
    LOGGER.info("  - Tables:  %s", tables_dir)
    LOGGER.info("  - Figures: %s", figures_vpf_dir)
    LOGGER.info("  - Summary: %s", output_dirs["vpf_analysis_summary"])
    LOGGER.info("=" * 70)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_vpf_analysis()
