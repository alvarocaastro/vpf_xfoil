"""
Application script for running SFC Impact Analysis.

This script orchestrates the SFC analysis stage, computing fuel consumption
improvements from aerodynamic efficiency gains.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis import config as base_config
from vfp_analysis.config_loader import get_output_dirs
from vfp_analysis.sfc_analysis.adapters.filesystem.data_loader_adapter import (
    FilesystemSfcDataLoader,
)
from vfp_analysis.sfc_analysis.adapters.filesystem.results_writer_adapter import (
    FilesystemSfcResultsWriter,
)
from vfp_analysis.sfc_analysis.core.services.sfc_analysis_service import (
    compute_sfc_analysis,
)
from vfp_analysis.sfc_analysis.core.services.summary_generator_service import (
    generate_sfc_summary,
)

LOGGER = logging.getLogger(__name__)


def generate_sfc_figures(
    sfc_results: list,
    figures_dir: Path,
) -> None:
    """Generate all SFC analysis figures."""
    figures_dir.mkdir(parents=True, exist_ok=True)

    # 1) SFC vs flight condition (baseline vs VPF)
    _plot_sfc_vs_condition(sfc_results, figures_dir)

    # 2) SFC reduction percentage vs condition
    _plot_sfc_reduction(sfc_results, figures_dir)

    # 3) Fan efficiency improvement vs condition
    _plot_fan_efficiency_improvement(sfc_results, figures_dir)

    # 4) Aerodynamic efficiency vs SFC relationship
    _plot_efficiency_vs_sfc(sfc_results, figures_dir)


def _plot_sfc_vs_condition(sfc_results: list, figures_dir: Path) -> None:
    """Plot SFC vs flight condition (baseline vs VPF)."""
    conditions = [r.condition for r in sfc_results]
    sfc_baseline = [r.sfc_baseline for r in sfc_results]
    sfc_new = [r.sfc_new for r in sfc_results]

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    x = np.arange(len(conditions))
    width = 0.35

    ax.bar(
        x - width / 2,
        sfc_baseline,
        width,
        label="Baseline",
        color="steelblue",
        edgecolor="black",
    )
    ax.bar(
        x + width / 2,
        sfc_new,
        width,
        label="VPF",
        color="green",
        edgecolor="black",
    )

    ax.set_xlabel("Flight Condition", fontsize=12)
    ax.set_ylabel("SFC [lb/(lbf·hr)]", fontsize=12)
    ax.set_title("Specific Fuel Consumption: Baseline vs VPF", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(
        figures_dir / "sfc_vs_condition.png", dpi=300, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_sfc_reduction(sfc_results: list, figures_dir: Path) -> None:
    """Plot SFC reduction percentage vs flight condition."""
    conditions = [r.condition for r in sfc_results]
    reductions = [r.sfc_reduction_percent for r in sfc_results]

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    ax.bar(conditions, reductions, color="green", edgecolor="black", width=0.6)

    ax.set_xlabel("Flight Condition", fontsize=12)
    ax.set_ylabel("SFC Reduction [%]", fontsize=12)
    ax.set_title("SFC Reduction Percentage by Flight Condition", fontsize=14)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(
        figures_dir / "sfc_reduction_percent.png", dpi=300, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_fan_efficiency_improvement(sfc_results: list, figures_dir: Path) -> None:
    """Plot fan efficiency improvement vs flight condition."""
    conditions = [r.condition for r in sfc_results]
    fan_baseline = [r.fan_efficiency_baseline * 100 for r in sfc_results]
    fan_new = [r.fan_efficiency_new * 100 for r in sfc_results]

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    x = np.arange(len(conditions))
    width = 0.35

    ax.bar(
        x - width / 2,
        fan_baseline,
        width,
        label="Baseline",
        color="steelblue",
        edgecolor="black",
    )
    ax.bar(
        x + width / 2,
        fan_new,
        width,
        label="VPF",
        color="green",
        edgecolor="black",
    )

    ax.set_xlabel("Flight Condition", fontsize=12)
    ax.set_ylabel("Fan Efficiency [%]", fontsize=12)
    ax.set_title("Fan Efficiency: Baseline vs VPF", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(
        figures_dir / "fan_efficiency_improvement.png", dpi=300, bbox_inches="tight"
    )
    plt.close(fig)


def _plot_efficiency_vs_sfc(sfc_results: list, figures_dir: Path) -> None:
    """Plot aerodynamic efficiency vs SFC relationship."""
    cl_cd_vpf = [r.cl_cd_vpf for r in sfc_results]
    sfc_new = [r.sfc_new for r in sfc_results]
    conditions = [r.condition for r in sfc_results]

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    scatter = ax.scatter(cl_cd_vpf, sfc_new, s=100, c=range(len(conditions)), 
                        cmap="viridis", edgecolors="black", linewidth=1.5)

    for i, condition in enumerate(conditions):
        ax.annotate(
            condition.title(),
            (cl_cd_vpf[i], sfc_new[i]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
        )

    ax.set_xlabel(r"Aerodynamic Efficiency $C_L/C_D$", fontsize=12)
    ax.set_ylabel("SFC [lb/(lbf·hr)]", fontsize=12)
    ax.set_title("Aerodynamic Efficiency vs Specific Fuel Consumption", fontsize=14)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(
        figures_dir / "efficiency_vs_sfc.png", dpi=300, bbox_inches="tight"
    )
    plt.close(fig)


def run_sfc_analysis() -> None:
    """Execute the complete SFC impact analysis stage."""
    LOGGER.info("=" * 70)
    LOGGER.info("STAGE 7: Specific Fuel Consumption (SFC) Impact Analysis")
    LOGGER.info("=" * 70)

    output_dirs = get_output_dirs()
    stage7_dir = base_config.RESULTS_DIR / "stage_7"
    stage7_dir.mkdir(parents=True, exist_ok=True)
    
    stage4_dir = base_config.RESULTS_DIR / "stage_4"
    tables_dir = stage4_dir / "tables"
    figures_sfc_dir = output_dirs["figures_sfc"]

    # Step 1: Load aerodynamic results
    LOGGER.info("Loading aerodynamic performance data...")
    loader = FilesystemSfcDataLoader()

    # Try to load from summary table first, fallback to optimal pitch
    performance_df = loader.load_performance_data(
        tables_dir / "summary_table.csv"
    )
    optimal_pitch_df = loader.load_optimal_pitch_data(
        tables_dir / "vpf_optimal_pitch.csv"
    )

    if optimal_pitch_df.empty:
        LOGGER.warning("No optimal pitch data found. Skipping SFC analysis.")
        return

    LOGGER.info(f"Loaded {len(optimal_pitch_df)} optimal pitch records")

    # Step 2 & 3: Load engine baseline
    LOGGER.info("Loading engine baseline parameters...")
    engine_config_path = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    engine_baseline = loader.load_engine_baseline(engine_config_path)
    LOGGER.info(f"Baseline SFC: {engine_baseline.baseline_sfc:.4f} lb/(lbf·hr)")

    # Step 4: Estimate SFC improvement
    LOGGER.info("Computing SFC improvements...")
    sfc_results = compute_sfc_analysis(
        optimal_pitch_df, engine_baseline, engine_config_path
    )
    LOGGER.info(f"Computed SFC analysis for {len(sfc_results)} conditions")

    # Step 5: Generate figures
    LOGGER.info("Generating SFC analysis figures...")
    generate_sfc_figures(sfc_results, figures_sfc_dir)

    # Step 6: Write results
    LOGGER.info("Writing SFC analysis results...")
    writer = FilesystemSfcResultsWriter()
    writer.write_sfc_table(sfc_results, tables_dir / "sfc_analysis.csv")

    # Generate and write summary
    summary_text = generate_sfc_summary(sfc_results)
    sfc_summary_path = output_dirs["sfc_analysis_summary"]
    writer.write_analysis_summary(
        summary_text, sfc_summary_path
    )

    # Generate Stage 7 summary
    from vfp_analysis.postprocessing.stage_summary_generator import (
        generate_stage7_summary,
        write_stage_summary,
    )
    
    summary_text_stage = generate_stage7_summary(stage7_dir)
    write_stage_summary(7, summary_text_stage, stage7_dir)
    LOGGER.info(f"Stage 7 summary written to: {stage7_dir / 'finalresults_stage7.txt'}")

    LOGGER.info("=" * 70)
    LOGGER.info("Stage 7 completed successfully!")
    LOGGER.info(f"Results saved in:")
    LOGGER.info(f"  - Tables: {tables_dir}")
    LOGGER.info(f"  - Figures: {figures_sfc_dir}")
    LOGGER.info(f"  - Summary: {sfc_summary_path}")
    LOGGER.info("=" * 70)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_sfc_analysis()
