"""Stage 4 figures: aerodynamic efficiency and polar comparisons.

Reads corrected polars from Stage 3 (results/stage3_compressibility_correction/polars/)
and produces three essential figures per pipeline run:
  - polar_efficiency_{flight}_{section}.png  — Cl/Cd vs α with η_max annotation
  - lift_drag_curves_{flight}.png            — multi-section polar overlay
  - compressibility_comparison.png           — penalty overview across conditions
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vpf_analysis.config_loader import get_plot_settings
from vpf_analysis.postprocessing.aerodynamics_utils import (
    find_second_peak_row,
    resolve_efficiency_column,
    resolve_polar_file,
)
from vpf_analysis.shared.plot_style import (
    COLORS,
    FLIGHT_LABELS,
    SECTION_COLORS,
    SECTION_LABELS,
    apply_style,
)
from vpf_analysis.stage4_performance_metrics.metrics import AerodynamicMetrics

LOGGER = logging.getLogger(__name__)

_FLIGHT_ORDER = ["takeoff", "climb", "cruise", "descent"]
_SECTION_ORDER = ["root", "mid_span", "tip"]

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


def plot_efficiency_penalty_overview(
    metrics: List[AerodynamicMetrics],
    polars_dir: Path,
    output_path: Path,
    summary_section: str = "mid_span",
) -> None:
    """CL/CD vs α for all flight conditions with VPF vs fixed-pitch operating points.

    Saved as ``compressibility_comparison.png``.
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

            ax.plot(m.alpha_opt, m.max_efficiency, marker="o", markersize=8,
                    color=color, zorder=5)

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


def generate_efficiency_plots(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """Generate CL/CD vs α curves for each (condition, section) pair.

    Saved as ``polar_efficiency_{flight}_{section}.png``.
    """
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
            except (ValueError, KeyError):
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
            fig.savefig(figures_dir / f"polar_efficiency_{flight}_{section}.png")
            plt.close(fig)


def generate_section_polar_comparison(
    stage3_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: Optional[List[str]] = None,
) -> None:
    """Two-panel figure per condition: CL/CD and CL vs α for all sections.

    Saved as ``lift_drag_curves_{flight}.png``.
    """
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
            except (ValueError, KeyError):
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
        fig.savefig(figures_dir / f"lift_drag_curves_{flight}.png")
        plt.close(fig)


def plot_efficiency_map(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
    mach_map: Optional[Dict[str, float]] = None,
    metrics: Optional[List[AerodynamicMetrics]] = None,
) -> None:
    """Generate 2-D CL/CD contour maps in (α, Mach) space for each blade section.

    Each figure shows the aerodynamic envelope of the fan blade as a filled
    contour of CL/CD evaluated across all available flight conditions (Mach
    numbers) and angles of attack.  The four operating points — one per
    flight condition — are overlaid as scatter markers using the standard
    COLORS palette so the reader can immediately see where in the envelope
    the VPF operates.

    Output: ``figures_dir/efficiency_map_{section}.png`` (one per section).
    """
    alpha_grid = np.linspace(_ALPHA_MIN, _ALPHA_MAX, 120)
    flights_ordered = [f for f in _FLIGHT_ORDER if f in flight_conditions]

    for section in blade_sections:
        mach_vals: list[float] = []
        eff_rows: list[np.ndarray] = []

        for flight in flights_ordered:
            result = _load_efficiency_curve(polars_dir, flight, section)
            if result is None:
                continue
            alphas_raw, effs_raw = result
            if len(alphas_raw) < 2:
                continue
            eff_interp = np.interp(alpha_grid, alphas_raw, effs_raw,
                                    left=np.nan, right=np.nan)
            mach_val = mach_map.get(flight, float("nan")) if mach_map else float("nan")
            mach_vals.append(mach_val)
            eff_rows.append(eff_interp)

        if len(eff_rows) < 2:
            LOGGER.warning("Insufficient polars for efficiency map of section '%s' — skipping.", section)
            continue

        Z = np.array(eff_rows)        # shape (n_conditions, n_alpha)
        Y = np.array(mach_vals)       # Mach axis
        X = alpha_grid                # alpha axis

        vmin = float(np.nanpercentile(Z, 5))
        vmax = float(np.nanpercentile(Z, 95))
        levels = np.linspace(vmin, vmax, 14)

        with apply_style():
            fig, ax = plt.subplots(figsize=(8.0, 5.5))

            cf = ax.contourf(X, Y, Z, levels=levels, cmap="viridis", extend="both")
            ax.contour(X, Y, Z, levels=levels[::2], colors="black",
                       linewidths=0.5, alpha=0.4)

            cbar = fig.colorbar(cf, ax=ax, pad=0.02)
            cbar.set_label("CL/CD", fontsize=10)

            # Overlay operating points from metrics
            if metrics is not None:
                for m in metrics:
                    if m.blade_section != section or m.flight_condition not in flights_ordered:
                        continue
                    if mach_map is None or m.flight_condition not in mach_map:
                        continue
                    mach_op = mach_map[m.flight_condition]
                    label = FLIGHT_LABELS.get(m.flight_condition, m.flight_condition)
                    color = COLORS.get(m.flight_condition, "#555555")
                    ax.scatter(
                        m.alpha_opt, mach_op,
                        color=color, s=80, zorder=6,
                        edgecolors="white", linewidths=0.8, label=label,
                    )

            ax.set_xlabel("Angle of attack α (°)")
            ax.set_ylabel("Mach number")
            ax.set_title(
                f"Aerodynamic efficiency map — {SECTION_LABELS.get(section, section)}",
                fontweight="bold",
            )
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                ax.legend(handles, labels, bbox_to_anchor=(1.18, 1), loc="upper left",
                          fontsize=9, frameon=True)

            figures_dir.mkdir(parents=True, exist_ok=True)
            fig.savefig(figures_dir / f"efficiency_map_{section}.png",
                        bbox_inches="tight")
            plt.close(fig)
            LOGGER.info("Saved efficiency_map_%s.png", section)


def generate_all_stage4_figures(
    metrics: List[AerodynamicMetrics],
    figures_dir: Path,
    polars_dir: Optional[Path] = None,
    flight_conditions: Optional[List[str]] = None,
    blade_sections: Optional[List[str]] = None,
    stage3_dir: Optional[Path] = None,
    mach_map: Optional[Dict[str, float]] = None,
    **_kwargs,
) -> None:
    """Generate the essential Stage 4 figures.

    1. compressibility_comparison.png — fixed-pitch penalty overview (mid_span section)
    2. polar_efficiency_{flight}_{section}.png — CL/CD vs α per condition and section
    3. lift_drag_curves_{flight}.png — two-panel CL/CD + CL vs α, all sections per condition
    4. efficiency_map_{section}.png — 2-D CL/CD contour map in (α, Mach) space
    """
    figures_dir.mkdir(parents=True, exist_ok=True)

    if polars_dir is not None:
        plot_efficiency_penalty_overview(
            metrics, polars_dir,
            output_path=figures_dir / "compressibility_comparison.png",
        )

    if polars_dir is not None and flight_conditions and blade_sections:
        generate_efficiency_plots(polars_dir, figures_dir, flight_conditions, blade_sections)

    if stage3_dir is not None and stage3_dir.is_dir() and flight_conditions:
        generate_section_polar_comparison(
            stage3_dir, figures_dir, flight_conditions, blade_sections
        )

    if polars_dir is not None and flight_conditions and blade_sections:
        plot_efficiency_map(
            polars_dir, figures_dir, flight_conditions, blade_sections,
            mach_map=mach_map, metrics=metrics,
        )
