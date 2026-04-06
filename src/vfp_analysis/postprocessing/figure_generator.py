"""
Figure generation for thesis publication.

This module generates all required publication-quality plots.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis.config_loader import get_plot_settings
from vfp_analysis.postprocessing.aerodynamics_utils import (
    find_second_peak_row,
    resolve_polar_file,
)
from vfp_analysis.postprocessing.metrics import AerodynamicMetrics

LOGGER = logging.getLogger(__name__)


def _apply_plot_style(ax: plt.Axes) -> None:
    """Apply consistent plot styling from configuration."""
    settings = get_plot_settings()
    style = settings["style"]

    if style["grid"]:
        ax.grid(
            True,
            linestyle=style["grid_linestyle"],
            linewidth=0.5,
            alpha=style["grid_alpha"],
        )


def generate_cl_vs_alpha_plots(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """Generate CL vs alpha plots for all cases."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()

    for flight in flight_conditions:
        for section in blade_sections:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            df = pd.read_csv(polar_file)
            fig, ax = plt.subplots(
                figsize=(settings["figure_size"]["width"], settings["figure_size"]["height"])
            )
            ax.plot(
                df["alpha"],
                df["cl"],
                linewidth=settings["style"]["linewidth"],
                marker="o",
                markersize=3,
            )
            ax.set_xlabel(r"$\alpha$ [deg]")
            ax.set_ylabel(r"$C_L$")
            ax.set_title(f"$C_L$ vs $\\alpha$ – {flight.title()} / {section}")
            _apply_plot_style(ax)
            fig.tight_layout()
            fig.savefig(
                figures_dir / f"cl_alpha_{flight}_{section}.png",
                dpi=settings["dpi"],
                bbox_inches="tight",
            )
            plt.close(fig)


def generate_cd_vs_alpha_plots(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """Generate CD vs alpha plots for all cases."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()

    for flight in flight_conditions:
        for section in blade_sections:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            df = pd.read_csv(polar_file)
            fig, ax = plt.subplots(
                figsize=(settings["figure_size"]["width"], settings["figure_size"]["height"])
            )
            ax.plot(
                df["alpha"],
                df["cd"],
                linewidth=settings["style"]["linewidth"],
                marker="o",
                markersize=3,
            )
            ax.set_xlabel(r"$\alpha$ [deg]")
            ax.set_ylabel(r"$C_D$")
            ax.set_title(f"$C_D$ vs $\\alpha$ – {flight.title()} / {section}")
            _apply_plot_style(ax)
            fig.tight_layout()
            fig.savefig(
                figures_dir / f"cd_alpha_{flight}_{section}.png",
                dpi=settings["dpi"],
                bbox_inches="tight",
            )
            plt.close(fig)


def generate_efficiency_plots(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """Generate CL/CD vs alpha plots for all cases, marking the optimal point."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()

    for flight in flight_conditions:
        for section in blade_sections:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            df = pd.read_csv(polar_file)

            try:
                row_opt = find_second_peak_row(df, "ld")
                alpha_opt = float(row_opt["alpha"])
                ld_max = float(row_opt["ld"])
                has_optimum = True
            except (ValueError, KeyError):
                has_optimum = False
                alpha_opt = float("nan")
                ld_max = float("nan")

            fig, ax = plt.subplots(
                figsize=(settings["figure_size"]["width"], settings["figure_size"]["height"])
            )
            ax.plot(
                df["alpha"],
                df["ld"],
                linewidth=settings["style"]["linewidth"],
                label=r"$C_L/C_D$",
            )

            if has_optimum:
                ax.plot(
                    alpha_opt,
                    ld_max,
                    marker="X",
                    color="red",
                    markersize=10,
                    markeredgecolor="darkred",
                    markeredgewidth=1.5,
                    label=f"$\\alpha_{{opt}}$ = {alpha_opt:.2f}° (2nd peak)",
                    zorder=5,
                )
                ax.axvline(
                    alpha_opt,
                    color="red",
                    linestyle="--",
                    linewidth=1.0,
                    alpha=0.7,
                    zorder=4,
                )
                ax.annotate(
                    f"$\\alpha_{{opt}}$ = {alpha_opt:.2f}°",
                    xy=(alpha_opt, ld_max),
                    xytext=(alpha_opt + 1.5, ld_max + 2.0),
                    arrowprops=dict(
                        facecolor="red",
                        shrink=0.05,
                        width=1.5,
                        headwidth=8,
                        alpha=0.7,
                    ),
                    fontsize=10,
                    fontweight="bold",
                    zorder=6,
                )

            ax.set_xlabel(r"$\alpha$ [deg]")
            ax.set_ylabel(r"$C_L/C_D$")
            ax.set_title(f"Eficiencia aerodinámica – {flight.title()} / {section}")
            _apply_plot_style(ax)
            ax.legend(loc="best")
            fig.tight_layout()
            fig.savefig(
                figures_dir / f"efficiency_{flight}_{section}.png",
                dpi=settings["dpi"],
                bbox_inches="tight",
            )
            plt.close(fig)


def generate_polar_plots(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """Generate CL vs CD polar plots for all cases."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()

    for flight in flight_conditions:
        for section in blade_sections:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            df = pd.read_csv(polar_file)
            fig, ax = plt.subplots(
                figsize=(settings["figure_size"]["width"], settings["figure_size"]["height"])
            )
            ax.plot(
                df["cd"],
                df["cl"],
                linewidth=settings["style"]["linewidth"],
                marker="o",
                markersize=3,
            )
            ax.set_xlabel(r"$C_D$")
            ax.set_ylabel(r"$C_L$")
            ax.set_title(f"Polar $C_L$-$C_D$ – {flight.title()} / {section}")
            _apply_plot_style(ax)
            fig.tight_layout()
            fig.savefig(
                figures_dir / f"polar_{flight}_{section}.png",
                dpi=settings["dpi"],
                bbox_inches="tight",
            )
            plt.close(fig)


def generate_alpha_opt_vs_condition(
    metrics: List[AerodynamicMetrics],
    figures_dir: Path,
) -> None:
    """Generate optimal angle of attack vs flight condition plot."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()

    data: Dict[str, Dict[str, float]] = {}
    for m in metrics:
        if m.flight_condition not in data:
            data[m.flight_condition] = {}
        data[m.flight_condition][m.blade_section] = m.alpha_opt

    flight_conditions = sorted(data.keys())
    sections = ["root", "mid_span", "tip"]

    fig, ax = plt.subplots(
        figsize=(settings["figure_size"]["width"], settings["figure_size"]["height"])
    )
    x = np.arange(len(flight_conditions))
    width = 0.25

    for i, section in enumerate(sections):
        values = [data[flight].get(section, np.nan) for flight in flight_conditions]
        ax.bar(
            x + i * width,
            values,
            width,
            label=section.replace("_", " ").title(),
        )

    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"$\alpha_{opt}$ [deg]")
    ax.set_title("Optimal Angle of Attack by Flight Condition")
    ax.set_xticks(x + width)
    ax.set_xticklabels([f.title() for f in flight_conditions])
    ax.legend()
    _apply_plot_style(ax)
    fig.tight_layout()
    fig.savefig(
        figures_dir / "alpha_opt_vs_condition.png",
        dpi=settings["dpi"],
        bbox_inches="tight",
    )
    plt.close(fig)


def generate_efficiency_vs_reynolds(
    metrics: List[AerodynamicMetrics],
    figures_dir: Path,
) -> None:
    """Generate (CL/CD)_max vs Reynolds number plot."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()

    for flight in sorted(set(m.flight_condition for m in metrics)):
        flight_metrics = [m for m in metrics if m.flight_condition == flight]
        if not flight_metrics:
            continue

        reynolds = [m.reynolds for m in flight_metrics]
        efficiency = [m.max_efficiency for m in flight_metrics]
        sections = [m.blade_section for m in flight_metrics]

        fig, ax = plt.subplots(
            figsize=(settings["figure_size"]["width"], settings["figure_size"]["height"])
        )
        ax.plot(reynolds, efficiency, marker="o", linewidth=settings["style"]["linewidth"])
        for i, section in enumerate(sections):
            ax.annotate(
                section.replace("_", " "),
                (reynolds[i], efficiency[i]),
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=9,
            )
        ax.set_xlabel(r"Reynolds Number")
        ax.set_ylabel(r"$(C_L/C_D)_{max}$")
        ax.set_title(f"Maximum Efficiency vs Reynolds – {flight.title()}")
        _apply_plot_style(ax)
        fig.tight_layout()
        fig.savefig(
            figures_dir / f"efficiency_vs_reynolds_{flight}.png",
            dpi=settings["dpi"],
            bbox_inches="tight",
        )
        plt.close(fig)


def generate_efficiency_by_section(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
) -> None:
    """Generate CL/CD vs alpha plots comparing root, mid_span, tip."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()

    for flight in flight_conditions:
        fig, ax = plt.subplots(
            figsize=(settings["figure_size"]["width"], settings["figure_size"]["height"])
        )

        plotted = False
        for section in ["root", "mid_span", "tip"]:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            df = pd.read_csv(polar_file)
            ax.plot(
                df["alpha"],
                df["ld"],
                linewidth=settings["style"]["linewidth"],
                label=section.replace("_", " ").title(),
            )
            plotted = True

        if not plotted:
            plt.close(fig)
            continue

        ax.set_xlabel(r"$\alpha$ [deg]")
        ax.set_ylabel(r"$C_L/C_D$")
        ax.set_title(f"Efficiency by Blade Section – {flight.title()}")
        ax.legend()
        _apply_plot_style(ax)
        fig.tight_layout()
        fig.savefig(
            figures_dir / f"efficiency_by_section_{flight}.png",
            dpi=settings["dpi"],
            bbox_inches="tight",
        )
        plt.close(fig)


def generate_all_figures(
    polars_dir: Path,
    figures_dir: Path,
    metrics: List[AerodynamicMetrics],
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """Generate all required figures for the thesis."""
    LOGGER.info("Generating all figures...")

    generate_cl_vs_alpha_plots(polars_dir, figures_dir, flight_conditions, blade_sections)
    generate_cd_vs_alpha_plots(polars_dir, figures_dir, flight_conditions, blade_sections)
    generate_efficiency_plots(polars_dir, figures_dir, flight_conditions, blade_sections)
    generate_polar_plots(polars_dir, figures_dir, flight_conditions, blade_sections)
    generate_alpha_opt_vs_condition(metrics, figures_dir)
    generate_efficiency_vs_reynolds(metrics, figures_dir)
    generate_efficiency_by_section(polars_dir, figures_dir, flight_conditions)

    LOGGER.info("All figures generated in: %s", figures_dir)
