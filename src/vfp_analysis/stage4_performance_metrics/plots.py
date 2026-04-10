"""
Stage 4 publication-quality figures.

Two figures based on the actual efficiency polars:

  - design_reference_{section}.png  (×3) — CL/CD vs α for all conditions on one
    axes per section, showing the design reference angle (cruise α_opt) as a
    vertical dashed line and marking both the optimal and fixed-pitch operating
    points on each curve.

  - efficiency_penalty_overview.png  (×1) — same concept for mid_span only,
    with annotations for Δα and Δ(CL/CD), serving as a compact thesis summary
    figure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis.postprocessing.aerodynamics_utils import (
    resolve_efficiency_column,
    resolve_polar_file,
)
from vfp_analysis.shared.plot_style import (
    COLORS,
    FLIGHT_LABELS,
    SECTION_LABELS,
    apply_style,
)
from vfp_analysis.stage4_performance_metrics.metrics import AerodynamicMetrics

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
        ax.set_title(
            f"Eficiencia aerodinámica — Sección {section_label}\n"
            r"$\bullet$ = $\alpha_{opt}$ (VPF)   $\circ$ = $\alpha_{design}$ (pala fija)"
        )
        ax.legend(
            title="Condición",
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
        ax.set_title(
            f"Penalización de eficiencia con pala fija — Sección {section_label}\n"
            r"$\bullet$ = $\alpha_{opt}$ (VPF)   $\circ$ = $\alpha_{design}$ (pala fija)"
        )
        ax.legend(
            title="Condición",
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
