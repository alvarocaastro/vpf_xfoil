"""Stage 4 figures: design reference, efficiency comparisons, publication-quality plots."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis.config_loader import get_plot_settings
from vfp_analysis.postprocessing.aerodynamics_utils import (
    find_second_peak_row,
    resolve_efficiency_column,
    resolve_polar_file,
)
from vfp_analysis.shared.plot_style import (
    COLORS,
    FLIGHT_LABELS,
    SECTION_COLORS,
    SECTION_LABELS,
    apply_style,
)
from vfp_analysis.stage4_performance_metrics.metrics import AerodynamicMetrics

LOGGER = logging.getLogger(__name__)

_FLIGHT_ORDER = ["takeoff", "climb", "cruise", "descent"]
_SECTION_ORDER = ["root", "mid_span", "tip"]

# Alpha range for polar plots
_ALPHA_MIN = -2.0
_ALPHA_MAX = 14.0


def _load_efficiency_curve(
    polars_dir: Path, condition: str, section: str
) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """Return (alpha, efficiency) arrays for a given case, or None if unavailable."""
    polar_file = resolve_polar_file(polars_dir, condition, section)
    if polar_file is None:
        return None
    try:
        df = pd.read_csv(polar_file)
        eff_col = resolve_efficiency_column(df)
        df_clean = (
            df[["alpha", eff_col]]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
            .sort_values("alpha")
        )
        mask = (df_clean["alpha"] >= _ALPHA_MIN) & (df_clean["alpha"] <= _ALPHA_MAX)
        df_clean = df_clean[mask]
        if df_clean.empty:
            return None
        return df_clean["alpha"].to_numpy(), df_clean[eff_col].to_numpy()
    except Exception:
        return None


def _lookup_eff_at_alpha(
    polars_dir: Path, condition: str, section: str, alpha_target: float
) -> Optional[float]:
    """Return (CL/CD) at the nearest polar point to alpha_target."""
    result = _load_efficiency_curve(polars_dir, condition, section)
    if result is None:
        return None
    alphas, effs = result
    idx = int(np.argmin(np.abs(alphas - alpha_target)))
    return float(effs[idx])


def plot_design_reference_section(
    metrics: List[AerodynamicMetrics],
    polars_dir: Path,
    section: str,
    output_path: Path,
) -> None:
    """CL/CD vs α for all flight conditions of one blade section.

    Shows:
    - Full efficiency curves for each condition (coloured by condition)
    - Vertical dashed line at α_design (cruise α_opt for this section)
    - Filled marker at each curve's own α_opt (VPF operating point)
    - Open marker at α_design on each curve (fixed-pitch operating point)
    """
    # Extract alpha_design for this section from cruise metrics
    alpha_design: Optional[float] = None
    for m in metrics:
        if m.flight_condition == "cruise" and m.blade_section == section:
            alpha_design = m.alpha_design if m.alpha_design == m.alpha_design else m.alpha_opt
            break

    flights = [f for f in _FLIGHT_ORDER if any(
        m.flight_condition == f and m.blade_section == section for m in metrics
    )]
    metrics_map: Dict[str, AerodynamicMetrics] = {
        m.flight_condition: m for m in metrics if m.blade_section == section
    }

    with apply_style():
        fig, ax = plt.subplots(figsize=(7.5, 5.0))

        for flight in flights:
            curve = _load_efficiency_curve(polars_dir, flight, section)
            if curve is None:
                continue
            alphas, effs = curve
            color = COLORS.get(flight, "#BBBBBB")
            label = FLIGHT_LABELS.get(flight, flight)
            ax.plot(alphas, effs, color=color, label=label)

            m = metrics_map.get(flight)
            if m is None:
                continue

            # Filled marker: α_opt (VPF operating point)
            ax.plot(
                m.alpha_opt, m.max_efficiency,
                marker="o", markersize=8, color=color, zorder=5,
            )

            # Open marker: α_design (fixed-pitch operating point)
            if alpha_design is not None and flight != "cruise":
                eff_fixed = _lookup_eff_at_alpha(polars_dir, flight, section, alpha_design)
                if eff_fixed is not None:
                    ax.plot(
                        alpha_design, eff_fixed,
                        marker="o", markersize=8, color=color,
                        markerfacecolor="white", markeredgewidth=1.5, zorder=5,
                    )

        # Vertical line: design reference angle
        if alpha_design is not None:
            ax.axvline(
                alpha_design, color="#AAAAAA", linestyle="--", linewidth=1.2,
                label=f"$\\alpha_{{design}}$ = {alpha_design:.1f}°",
            )

        section_label = SECTION_LABELS.get(section, section)
        ax.set_xlabel(r"$\alpha$ (°)")
        ax.set_ylabel(r"$C_L/C_D$")
        ax.set_title(f"$C_L/C_D$ vs $\\alpha$ — {section_label} section")
        ax.legend(
            title="Condition",
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
            borderaxespad=0,
        )
        fig.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path)
        plt.close(fig)


def plot_efficiency_penalty_overview(
    metrics: List[AerodynamicMetrics],
    polars_dir: Path,
    output_path: Path,
    summary_section: str = "mid_span",
) -> None:
    """Compact thesis summary figure for one representative section.

    Shows all four efficiency curves on one axes with annotations for Δα and
    Δ(CL/CD) between the fixed-pitch and VPF operating points for non-cruise
    conditions.
    """
    alpha_design: Optional[float] = None
    for m in metrics:
        if m.flight_condition == "cruise" and m.blade_section == summary_section:
            alpha_design = m.alpha_design if m.alpha_design == m.alpha_design else m.alpha_opt
            break

    flights = [f for f in _FLIGHT_ORDER if any(
        m.flight_condition == f and m.blade_section == summary_section for m in metrics
    )]
    metrics_map: Dict[str, AerodynamicMetrics] = {
        m.flight_condition: m
        for m in metrics if m.blade_section == summary_section
    }

    with apply_style():
        fig, ax = plt.subplots(figsize=(8.0, 5.5))

        for flight in flights:
            curve = _load_efficiency_curve(polars_dir, flight, summary_section)
            if curve is None:
                continue
            alphas, effs = curve
            color = COLORS.get(flight, "#BBBBBB")
            label = FLIGHT_LABELS.get(flight, flight)
            ax.plot(alphas, effs, color=color, label=label)

            m = metrics_map.get(flight)
            if m is None:
                continue

            # Filled marker: α_opt
            ax.plot(m.alpha_opt, m.max_efficiency, marker="o", markersize=8,
                    color=color, zorder=5)

            # Open marker + annotation for non-cruise conditions
            if alpha_design is not None and flight != "cruise":
                eff_fixed = _lookup_eff_at_alpha(
                    polars_dir, flight, summary_section, alpha_design
                )
                if eff_fixed is not None:
                    ax.plot(
                        alpha_design, eff_fixed,
                        marker="o", markersize=8, color=color,
                        markerfacecolor="white", markeredgewidth=1.5, zorder=5,
                    )
                    # Annotation: Δα and Δ(CL/CD)
                    d_alpha = m.alpha_opt - alpha_design
                    d_eff = m.max_efficiency - eff_fixed
                    ax.annotate(
                        f"$\\Delta\\alpha$={d_alpha:.1f}°\n$\\Delta$(CL/CD)={d_eff:.1f}",
                        xy=(alpha_design, eff_fixed),
                        xytext=(alpha_design - 1.2, eff_fixed + 4),
                        fontsize=7.5,
                        color=color,
                        arrowprops=dict(arrowstyle="-", color=color, lw=0.8),
                    )

        if alpha_design is not None:
            ax.axvline(
                alpha_design, color="#AAAAAA", linestyle="--", linewidth=1.2,
                label=f"$\\alpha_{{design}}$ = {alpha_design:.1f}°",
            )

        section_label = SECTION_LABELS.get(summary_section, summary_section)
        ax.set_xlabel(r"$\alpha$ (°)")
        ax.set_ylabel(r"$C_L/C_D$")
        ax.set_title(f"Fixed-pitch penalty — Section {section_label}")
        ax.legend(
            title="Condition",
            bbox_to_anchor=(1.02, 1),
            loc="upper left",
            borderaxespad=0,
        )
        fig.tight_layout()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path)
        plt.close(fig)


def generate_stage4_figures(
    metrics: List[AerodynamicMetrics],
    figures_dir: Path,
    polars_dir: Optional[Path] = None,
) -> None:
    """Generate all Stage 4 figures and save them to *figures_dir*.

    Parameters
    ----------
    metrics:
        Enriched metrics list (output of ``enrich_with_cruise_reference``).
    figures_dir:
        Output directory for PNG files.
    polars_dir:
        Directory used to locate polar CSV files. If None, figures that require
        raw polar data are skipped.
    """
    figures_dir.mkdir(parents=True, exist_ok=True)

    if polars_dir is None:
        return

    sections = [s for s in _SECTION_ORDER if any(m.blade_section == s for m in metrics)]

    for section in sections:
        plot_design_reference_section(
            metrics, polars_dir, section,
            figures_dir / f"design_reference_{section}.png",
        )


# ---------------------------------------------------------------------------
# Publication figures (merged from publication_figures.py)
# ---------------------------------------------------------------------------

CONDITION_COLORS: Dict[str, str] = {
    "takeoff": "#E31A1C",
    "climb":   "#FF7F00",
    "cruise":  "#1F78B4",
    "descent": "#6A3D9A",
}

_ACADEMIC_STYLE: Dict = {
    "font.family":       "serif",
    "font.serif":        ["DejaVu Serif", "Times New Roman", "Palatino", "serif"],
    "font.size":         10,
    "axes.titlesize":    12,
    "axes.titleweight":  "bold",
    "axes.labelsize":    10,
    "axes.labelweight":  "normal",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "xtick.labelsize":   9,
    "ytick.labelsize":   9,
    "xtick.direction":   "in",
    "ytick.direction":   "in",
    "axes.grid":         True,
    "grid.linestyle":    ":",
    "grid.linewidth":    0.5,
    "grid.alpha":        0.65,
    "legend.fontsize":   9,
    "legend.framealpha": 0.85,
    "legend.edgecolor":  "0.6",
    "lines.linewidth":   1.8,
    "lines.markersize":  5,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "axes.prop_cycle":   mpl.cycler(color=[
        "#2166AC", "#D6604D", "#4DAC26", "#762A83",
    ]),
}

_ALPHA_CRUISE_REF: float = 5.0


def _alpha_cruise_reference(ax: plt.Axes, alpha_val: float = _ALPHA_CRUISE_REF) -> None:
    ax.axvline(
        alpha_val, color="0.45", linestyle="--", linewidth=0.9, alpha=0.7,
        label=rf"Cruise reference — $\alpha$ = {alpha_val:.1f}°", zorder=2,
    )


def _smart_annotation(
    ax: plt.Axes,
    x: float,
    y: float,
    label: str,
    x_range: float,
    y_range: float,
) -> None:
    dx = 0.06 * x_range
    dy = 0.06 * y_range
    ax.annotate(
        label, xy=(x, y), xytext=(x + dx, y + dy),
        arrowprops=dict(arrowstyle="->", color="#B22222", lw=1.2),
        fontsize=9, fontweight="bold", color="#B22222", zorder=7,
    )


def _load_corrected_polar(
    stage3_dir: Path,
    condition: str,
    section: str,
) -> Optional[pd.DataFrame]:
    path = stage3_dir / condition.lower() / section / "corrected_polar.csv"
    if not path.exists():
        LOGGER.warning("Corrected polar not found: %s", path)
        return None
    return pd.read_csv(path)


def _interpolate_ld_at_alpha(
    df: pd.DataFrame,
    eff_col: str,
    alpha_target: float,
) -> Optional[float]:
    df_clean = df.replace([np.inf, -np.inf], np.nan).dropna(subset=[eff_col, "alpha"])
    if df_clean.empty:
        return None
    below = df_clean[df_clean["alpha"] <= alpha_target]
    above = df_clean[df_clean["alpha"] >= alpha_target]
    if below.empty or above.empty:
        return None
    row_lo = below.iloc[-1]
    row_hi = above.iloc[0]
    if row_lo["alpha"] == row_hi["alpha"]:
        return float(row_lo[eff_col])
    t = (alpha_target - row_lo["alpha"]) / (row_hi["alpha"] - row_lo["alpha"])
    return float(row_lo[eff_col] + t * (row_hi[eff_col] - row_lo[eff_col]))


def _format_reynolds(re: float) -> str:
    exp = int(np.floor(np.log10(re)))
    coeff = re / 10 ** exp
    return rf"Re = {coeff:.1f}$\times 10^{{{exp}}}$"


def generate_efficiency_plots(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """Generate CL/CD vs α curves for each (condition, section) pair."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]

    for flight in flight_conditions:
        for section in blade_sections:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            df = pd.read_csv(polar_file)
            try:
                eff_col = resolve_efficiency_column(df)
            except ValueError:
                continue

            try:
                row_opt = find_second_peak_row(df, eff_col)
                alpha_opt = float(row_opt["alpha"])
                ld_max = float(row_opt[eff_col])
                has_opt = True
            except (ValueError, KeyError):
                has_opt = False
                alpha_opt = float("nan")
                ld_max = float("nan")

            fig, ax = plt.subplots(figsize=(w, h))
            color = SECTION_COLORS.get(section, "#2166AC")
            ax.plot(df["alpha"], df[eff_col], color=color, label=r"$C_L/C_D$", zorder=3)

            if has_opt:
                ax.plot(
                    alpha_opt, ld_max,
                    marker="*", color="#B22222", markersize=12,
                    markeredgecolor="darkred", markeredgewidth=0.8,
                    zorder=6, linestyle="none",
                )
                ax.axvline(alpha_opt, color="#B22222", linestyle="--",
                           linewidth=0.9, alpha=0.75, zorder=4)
                alpha_range = float(df["alpha"].max() - df["alpha"].min())
                ld_range = float(
                    df[eff_col].replace([np.inf, -np.inf], np.nan).dropna().max()
                    - df[eff_col].replace([np.inf, -np.inf], np.nan).dropna().min()
                )
                _smart_annotation(
                    ax, alpha_opt, ld_max,
                    rf"$\alpha_{{opt}}$ = {alpha_opt:.1f}°",
                    alpha_range, ld_range,
                )

            ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
            ax.set_ylabel(r"Lift-to-drag ratio $C_L/C_D$ [–]")
            section_label = section.replace("_", " ").title()
            ax.set_title(f"Aerodynamic efficiency — {flight.capitalize()} / {section_label}")
            ax.legend(loc="lower right")
            fig.tight_layout()
            fig.savefig(figures_dir / f"efficiency_{flight}_{section}.png")
            plt.close(fig)


def generate_efficiency_by_section(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    alpha_cruise_ref: float = _ALPHA_CRUISE_REF,
) -> None:
    """Generate CL/CD vs α comparing root, mid_span and tip per condition."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]
    sections = ["root", "mid_span", "tip"]

    for flight in flight_conditions:
        fig, ax = plt.subplots(figsize=(w, h))
        plotted = False

        for section in sections:
            polar_file = resolve_polar_file(polars_dir, flight, section)
            if polar_file is None:
                continue

            df = pd.read_csv(polar_file)
            color = SECTION_COLORS[section]
            try:
                eff_col = resolve_efficiency_column(df)
            except ValueError:
                continue

            try:
                row_opt = find_second_peak_row(df, eff_col)
                alpha_opt = float(row_opt["alpha"])
                ld_max = float(row_opt[eff_col])
                legend_label = (
                    rf"{section.replace('_', ' ').title()} "
                    rf"($\alpha_{{opt}}$ = {alpha_opt:.1f}°)"
                )
            except (ValueError, KeyError):
                alpha_opt = None
                ld_max = float("nan")
                legend_label = section.replace("_", " ").title()

            ax.plot(df["alpha"], df[eff_col], color=color, label=legend_label, zorder=3)

            if alpha_opt is not None:
                ax.plot(
                    alpha_opt, ld_max,
                    marker="*", color=color, markersize=10,
                    markeredgecolor="white", markeredgewidth=0.6,
                    zorder=5, linestyle="none",
                )
            plotted = True

        if not plotted:
            plt.close(fig)
            continue

        _alpha_cruise_reference(ax, alpha_cruise_ref)
        ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax.set_ylabel(r"Lift-to-drag ratio $C_L/C_D$ [–]")
        ax.set_title(f"$C_L/C_D$ by blade section — {flight.capitalize()}")
        ax.legend(loc="lower right")
        fig.tight_layout()
        fig.savefig(figures_dir / f"efficiency_by_section_{flight}.png")
        plt.close(fig)


def generate_alpha_opt_vs_condition(
    metrics: List[AerodynamicMetrics],
    figures_dir: Path,
    alpha_cruise_ref: float = _ALPHA_CRUISE_REF,
) -> None:
    """Generate central thesis figure: α_opt grouped by flight condition and blade section."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]

    data: Dict[str, Dict[str, float]] = {}
    for m in metrics:
        data.setdefault(m.flight_condition, {})[m.blade_section] = m.alpha_opt

    flight_conditions = sorted(
        data.keys(),
        key=lambda c: ["takeoff", "climb", "cruise", "descent"].index(c)
        if c in ["takeoff", "climb", "cruise", "descent"] else 99
    )
    sections = ["root", "mid_span", "tip"]

    fig, ax = plt.subplots(figsize=(w + 1.5, h))
    x = np.arange(len(flight_conditions))
    width = 0.22

    for i, section in enumerate(sections):
        values = [data[fc].get(section, np.nan) for fc in flight_conditions]
        color = SECTION_COLORS[section]
        bars = ax.bar(
            x + i * width, values, width,
            label=section.replace("_", " ").title(),
            color=color, edgecolor="white", linewidth=0.6, zorder=3,
        )
        ax.bar_label(bars, fmt="%.1f°", padding=3, fontsize=8, fontweight="bold")

    ax.axhline(
        alpha_cruise_ref,
        color="0.35", linestyle="--", linewidth=1.0,
        label=rf"Cruise reference — $\alpha$ = {alpha_cruise_ref:.1f}°", zorder=2,
    )

    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"Optimal angle of attack $\alpha_{opt}$ [°]")
    ax.set_title(r"$\alpha_{opt}$ by flight condition and blade section", pad=10)
    ax.set_xticks(x + width)
    ax.set_xticklabels([fc.title() for fc in flight_conditions])
    ax.legend(loc="lower right")
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(figures_dir / "alpha_opt_vs_condition.png")
    plt.close(fig)


def generate_section_polar_comparison(
    stage3_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: Optional[List[str]] = None,
) -> None:
    """Generate two-panel figure per condition: CL/CD_corrected and CL_corrected vs α."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]
    sections = blade_sections or ["root", "mid_span", "tip"]

    for flight in flight_conditions:
        fig, (ax_eff, ax_cl) = plt.subplots(1, 2, figsize=(w * 2 + 0.5, h))
        any_plotted = False

        for section in sections:
            df = _load_corrected_polar(stage3_dir, flight, section)
            if df is None:
                continue

            try:
                eff_col = resolve_efficiency_column(df)
            except ValueError:
                LOGGER.warning(
                    "No efficiency column in %s/%s corrected polar.", flight, section
                )
                continue

            cl_col = "cl_corrected" if "cl_corrected" in df.columns else "cl"
            color = SECTION_COLORS.get(section, "#333333")
            section_label = section.replace("_", " ").title()

            try:
                row_opt = find_second_peak_row(df, eff_col)
                alpha_opt = float(row_opt["alpha"])
                ld_opt = float(row_opt[eff_col])
                cl_at_opt = float(row_opt[cl_col]) if cl_col in row_opt.index else None
                has_opt = True
            except (ValueError, KeyError):
                has_opt = False
                alpha_opt = ld_opt = cl_at_opt = None

            legend_lbl = (
                rf"{section_label} ($\alpha_{{opt}}$ = {alpha_opt:.1f}°)"
                if has_opt else section_label
            )

            ax_eff.plot(df["alpha"], df[eff_col], color=color, label=legend_lbl, zorder=3)
            if has_opt:
                ax_eff.plot(
                    alpha_opt, ld_opt, marker="*", color=color, markersize=11,
                    markeredgecolor="white", markeredgewidth=0.7, zorder=6, linestyle="none",
                )
                ax_eff.axvline(alpha_opt, color=color, linestyle=":", linewidth=0.8, alpha=0.5)

            ax_cl.plot(df["alpha"], df[cl_col], color=color, label=legend_lbl, zorder=3)
            if has_opt and cl_at_opt is not None:
                ax_cl.plot(
                    alpha_opt, cl_at_opt, marker="*", color=color, markersize=11,
                    markeredgecolor="white", markeredgewidth=0.7, zorder=6, linestyle="none",
                )

            any_plotted = True

        if not any_plotted:
            plt.close(fig)
            continue

        ax_eff.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax_eff.set_ylabel(r"$C_L/C_D$ (Prandtl-Glauert corrected) [–]")
        ax_eff.set_title(f"Efficiency polar — {flight.capitalize()}")
        ax_eff.legend(loc="lower right")

        ax_cl.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax_cl.set_ylabel(r"$C_L$ (Prandtl-Glauert corrected) [–]")
        ax_cl.set_title(f"Lift polar — {flight.capitalize()}")
        ax_cl.legend(loc="lower right")

        fig.suptitle(
            f"Blade section comparison — {flight.capitalize()}", fontsize=11, fontweight="bold"
        )
        fig.tight_layout()
        fig.savefig(figures_dir / f"section_polar_comparison_{flight}.png")
        plt.close(fig)


def generate_cruise_penalty_figure(
    stage3_dir: Path,
    figures_dir: Path,
    non_cruise_conditions: Optional[List[str]] = None,
    blade_sections: Optional[List[str]] = None,
    reynolds_table: Optional[Dict[str, Dict[str, float]]] = None,
    alpha_min_second_peak: float = 3.0,
) -> None:
    """Generate VPF efficiency gain figure for each non-cruise condition."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]

    sections = blade_sections or ["root", "mid_span", "tip"]
    conditions = non_cruise_conditions or ["takeoff", "climb", "descent"]
    re_table = reynolds_table or {}

    alpha_cruise_design: float = _ALPHA_CRUISE_REF
    cruise_df = _load_corrected_polar(stage3_dir, "cruise", "mid_span")
    if cruise_df is not None:
        try:
            eff_col_cr = resolve_efficiency_column(cruise_df)
            row_cr = find_second_peak_row(cruise_df, eff_col_cr, alpha_min_second_peak)
            alpha_cruise_design = float(row_cr["alpha"])
        except (ValueError, KeyError):
            pass

    for condition in conditions:
        fig, ax = plt.subplots(figsize=(w + 1.0, h + 0.5))
        any_plotted = False
        mid_span_ld_opt: Optional[float] = None

        for section in sections:
            df = _load_corrected_polar(stage3_dir, condition, section)
            if df is None:
                continue

            try:
                eff_col = resolve_efficiency_column(df)
            except ValueError:
                continue

            color = SECTION_COLORS.get(section, "#333333")
            section_label = section.replace("_", " ").title()
            re_val = re_table.get(condition, {}).get(section)
            re_str = _format_reynolds(re_val) if re_val else ""
            curve_label = f"{section_label}  ({re_str})" if re_str else section_label

            ax.plot(df["alpha"], df[eff_col], color=color, label=curve_label, zorder=3)

            try:
                row_opt = find_second_peak_row(df, eff_col, alpha_min_second_peak)
                alpha_opt = float(row_opt["alpha"])
                ld_opt = float(row_opt[eff_col])
                ax.plot(
                    alpha_opt, ld_opt,
                    marker="*", color="darkgreen", markersize=13,
                    markeredgecolor="white", markeredgewidth=1.0,
                    zorder=7, linestyle="none",
                    label=rf"$\alpha_{{opt}}$ VPF = {alpha_opt:.1f}° [{section_label}]",
                )
                if section == "mid_span":
                    mid_span_ld_opt = ld_opt
                    mid_span_eff_col = eff_col
                    mid_span_df = df
            except (ValueError, KeyError):
                pass

            any_plotted = True

        if not any_plotted:
            plt.close(fig)
            continue

        ax.axvline(
            alpha_cruise_design,
            color="#B22222", linestyle="--", linewidth=1.4, zorder=5,
            label=rf"Fixed cruise pitch — $\alpha_{{design}}$ = {alpha_cruise_design:.1f}°",
        )

        if mid_span_ld_opt is not None:
            ld_at_cruise = _interpolate_ld_at_alpha(
                mid_span_df, mid_span_eff_col, alpha_cruise_design
            )
            if ld_at_cruise is not None and ld_at_cruise > 0:
                penalty_pct = 100.0 * (mid_span_ld_opt - ld_at_cruise) / mid_span_ld_opt
                eff_series = mid_span_df[mid_span_eff_col].replace([np.inf, -np.inf], np.nan).dropna()
                ld_range = float(eff_series.max() - eff_series.min()) if not eff_series.empty else 1.0
                alpha_range = float(mid_span_df["alpha"].max() - mid_span_df["alpha"].min())
                ax.annotate(
                    rf"Fixed-pitch loss $\approx${penalty_pct:.1f}%",
                    xy=(alpha_cruise_design, ld_at_cruise),
                    xytext=(
                        alpha_cruise_design + 0.06 * alpha_range,
                        ld_at_cruise - 0.10 * ld_range,
                    ),
                    arrowprops=dict(arrowstyle="->", color="#B22222", lw=1.1),
                    fontsize=9, color="#B22222", fontweight="bold", zorder=8,
                )

        ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax.set_ylabel(r"$C_L/C_D$ (Prandtl-Glauert corrected) [–]")
        ax.set_title(f"VPF efficiency gain — {condition.capitalize()}", pad=8)
        ax.legend(loc="lower right", fontsize=8)
        fig.tight_layout()
        fig.savefig(figures_dir / f"cruise_penalty_{condition}.png")
        plt.close(fig)


def generate_all_figures(
    polars_dir: Path,
    figures_dir: Path,
    metrics: List[AerodynamicMetrics],
    flight_conditions: List[str],
    blade_sections: List[str],
    stage3_dir: Optional[Path] = None,
    reynolds_table: Optional[Dict[str, Dict[str, float]]] = None,
) -> None:
    """Generate all publication figures. Stage 3 figures require *stage3_dir*."""
    LOGGER.info("Generating efficiency comparison by section...")
    generate_efficiency_by_section(polars_dir, figures_dir, flight_conditions)

    LOGGER.info("Generating alpha_opt vs condition figure...")
    generate_alpha_opt_vs_condition(metrics, figures_dir)

    if stage3_dir is not None and stage3_dir.is_dir():
        LOGGER.info("Generating section polar comparison (Figure A)...")
        generate_section_polar_comparison(
            stage3_dir, figures_dir, flight_conditions, blade_sections
        )
        LOGGER.info("Generating cruise penalty figures (Figure B)...")
        non_cruise = [c for c in flight_conditions if c != "cruise"]
        generate_cruise_penalty_figure(
            stage3_dir, figures_dir,
            non_cruise_conditions=non_cruise,
            blade_sections=blade_sections,
            reynolds_table=reynolds_table,
        )
    else:
        LOGGER.info("stage3_dir not available — skipping Figures A and B.")

    LOGGER.info("All figures generated in: %s", figures_dir)


def generate_all_stage4_figures(
    metrics: List[AerodynamicMetrics],
    figures_dir: Path,
    polars_dir: Optional[Path] = None,
    flight_conditions: Optional[List[str]] = None,
    blade_sections: Optional[List[str]] = None,
    stage3_dir: Optional[Path] = None,
    reynolds_table: Optional[Dict[str, Dict[str, float]]] = None,
) -> None:
    """Single entry point: generate all Stage 4 figures."""
    generate_stage4_figures(metrics, figures_dir, polars_dir=polars_dir)
    if polars_dir is not None and flight_conditions is not None and blade_sections is not None:
        generate_all_figures(
            polars_dir=polars_dir,
            figures_dir=figures_dir,
            metrics=metrics,
            flight_conditions=flight_conditions,
            blade_sections=blade_sections,
            stage3_dir=stage3_dir,
            reynolds_table=reynolds_table,
        )
