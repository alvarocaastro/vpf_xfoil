"""
publication_figures.py
----------------------
Genera las figuras de publicación para la tesis.

Este módulo produce las figuras de calidad publicación que documentan los
resultados principales del análisis VPF. Estaba en stage5_publication_figures/;
ahora es un sub-módulo de stage4_performance_metrics/ porque no introduce
ninguna transformación de datos nueva — sólo visualiza los resultados de Stage 4.

Figuras generadas:
  1. efficiency_plots          — CL/CD vs α con α_opt marcado (una por caso)
  2. efficiency_by_section     — comparación por sección por condición de vuelo
  3. alpha_opt_vs_condition    — figura central de la tesis: matriz de α_opt

Figuras extendidas (requieren polares corregidas de Stage 3):
  A. section_polar_comparison  — polar de eficiencia + sustentación por condición
  B. cruise_penalty_figure     — prueba visual de la penalización de paso fijo
"""

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
from vfp_analysis.shared.plot_style import SECTION_COLORS
from vfp_analysis.stage4_performance_metrics.metrics import AerodynamicMetrics

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estilo académico — aplicado una vez al importar el módulo
# ---------------------------------------------------------------------------

# Paleta de colores por condición de vuelo (usada en comparaciones y alpha_opt)
CONDITION_COLORS: Dict[str, str] = {
    "takeoff": "#E31A1C",   # rojo
    "climb":   "#FF7F00",   # naranja
    "cruise":  "#1F78B4",   # azul (condición de referencia)
    "descent": "#6A3D9A",   # violeta
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
        "#2166AC",
        "#D6604D",
        "#4DAC26",
        "#762A83",
    ]),
}

mpl.rcParams.update(_ACADEMIC_STYLE)

# Ángulo de crucero de referencia — línea sobre los resúmenes
_ALPHA_CRUISE_REF: float = 5.0


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _alpha_cruise_reference(ax: plt.Axes, alpha_val: float = _ALPHA_CRUISE_REF) -> None:
    """Dibuja línea vertical discontinua en el ángulo de referencia de crucero."""
    ax.axvline(
        alpha_val,
        color="0.45",
        linestyle="--",
        linewidth=0.9,
        alpha=0.7,
        label=rf"Cruise ref. $\alpha$ = {alpha_val:.1f}°",
        zorder=2,
    )


def _smart_annotation(
    ax: plt.Axes,
    x: float,
    y: float,
    label: str,
    x_range: float,
    y_range: float,
) -> None:
    """Anota (x, y) con un offset proporcional al rango de datos del eje."""
    dx = 0.06 * x_range
    dy = 0.06 * y_range
    ax.annotate(
        label,
        xy=(x, y),
        xytext=(x + dx, y + dy),
        arrowprops=dict(arrowstyle="->", color="#B22222", lw=1.2),
        fontsize=9,
        fontweight="bold",
        color="#B22222",
        zorder=7,
    )


def _load_corrected_polar(
    stage3_dir: Path,
    condition: str,
    section: str,
) -> Optional[pd.DataFrame]:
    """Carga corrected_polar.csv de Stage 3. Devuelve None si no existe."""
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
    """Interpolación lineal de eficiencia en un ángulo dado."""
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
    """Formatea Reynolds como cadena LaTeX, p. ej. 'Re = 2.5×10⁶'."""
    exp = int(np.floor(np.log10(re)))
    coeff = re / 10 ** exp
    return rf"Re = {coeff:.1f}$\times 10^{{{exp}}}$"


# ---------------------------------------------------------------------------
# Figura 1 — CL/CD vs α por caso individual, α_opt marcado
# ---------------------------------------------------------------------------

def generate_efficiency_plots(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: List[str],
) -> None:
    """Genera curvas CL/CD vs α para cada par (condición, sección)."""
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
                row_opt  = find_second_peak_row(df, "ld")
                alpha_opt = float(row_opt["alpha"])
                ld_max    = float(row_opt["ld"])
                has_opt   = True
            except (ValueError, KeyError):
                has_opt   = False
                alpha_opt = float("nan")
                ld_max    = float("nan")

            fig, ax = plt.subplots(figsize=(w, h))
            color = SECTION_COLORS.get(section, "#2166AC")
            ax.plot(df["alpha"], df["ld"], color=color, label=r"$C_L/C_D$", zorder=3)

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
                    df["ld"].replace([np.inf, -np.inf], np.nan).dropna().max()
                    - df["ld"].replace([np.inf, -np.inf], np.nan).dropna().min()
                )
                _smart_annotation(
                    ax, alpha_opt, ld_max,
                    rf"$\alpha_{{opt}}$ = {alpha_opt:.1f}°",
                    alpha_range, ld_range,
                )

            ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
            ax.set_ylabel(r"Lift-to-drag ratio $C_L/C_D$ [–]")
            section_label = section.replace("_", " ").title()
            ax.set_title(f"Aerodynamic Efficiency — {flight.title()} / {section_label}")
            ax.legend(loc="lower right")
            fig.tight_layout()
            fig.savefig(figures_dir / f"efficiency_{flight}_{section}.png")
            plt.close(fig)


# ---------------------------------------------------------------------------
# Figura 2 — Comparación por sección (curvas CL/CD superpuestas por condición)
# ---------------------------------------------------------------------------

def generate_efficiency_by_section(
    polars_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    alpha_cruise_ref: float = _ALPHA_CRUISE_REF,
) -> None:
    """Genera curvas CL/CD vs α comparando root, mid_span y tip por condición."""
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
                row_opt   = find_second_peak_row(df, "ld")
                alpha_opt = float(row_opt["alpha"])
                ld_max    = float(row_opt["ld"])
                legend_label = (
                    rf"{section.replace('_', ' ').title()} "
                    rf"($\alpha_{{opt}}$ = {alpha_opt:.1f}°)"
                )
            except (ValueError, KeyError):
                alpha_opt    = None
                legend_label = section.replace("_", " ").title()

            ax.plot(df["alpha"], df["ld"], color=color, label=legend_label, zorder=3)

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
        ax.set_title(f"Efficiency by Blade Section — {flight.title()}")
        ax.legend(loc="lower right")
        fig.tight_layout()
        fig.savefig(figures_dir / f"efficiency_by_section_{flight}.png")
        plt.close(fig)


# ---------------------------------------------------------------------------
# Figura 3 — Matriz α_opt: figura central de la tesis
# ---------------------------------------------------------------------------

def generate_alpha_opt_vs_condition(
    metrics: List[AerodynamicMetrics],
    figures_dir: Path,
    alpha_cruise_ref: float = _ALPHA_CRUISE_REF,
) -> None:
    """
    Genera la figura central de la tesis: α_opt agrupado por condición de vuelo
    y sección de pala. Muestra visualmente por qué el paso fijo de crucero no
    es óptimo en otras condiciones.
    """
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
    x     = np.arange(len(flight_conditions))
    width = 0.22

    for i, section in enumerate(sections):
        values = [data[fc].get(section, np.nan) for fc in flight_conditions]
        color  = SECTION_COLORS[section]
        bars   = ax.bar(
            x + i * width, values, width,
            label=section.replace("_", " ").title(),
            color=color, edgecolor="white", linewidth=0.6, zorder=3,
        )
        ax.bar_label(bars, fmt="%.1f°", padding=3, fontsize=8, fontweight="bold")

    ax.axhline(
        alpha_cruise_ref,
        color="0.35", linestyle="--", linewidth=1.0,
        label=rf"Cruise ref. $\alpha$ = {alpha_cruise_ref:.1f}°",
        zorder=2,
    )

    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"Optimal angle of attack $\alpha_{opt}$ [°]")
    ax.set_title(r"Optimal Angle of Attack by Flight Condition — Key Thesis Result", pad=10)
    ax.set_xticks(x + width)
    ax.set_xticklabels([fc.title() for fc in flight_conditions])
    ax.legend(loc="lower right")
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(figures_dir / "alpha_opt_vs_condition.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figura A — Comparación de polares por sección (eficiencia + sustentación)
# ---------------------------------------------------------------------------

def generate_section_polar_comparison(
    stage3_dir: Path,
    figures_dir: Path,
    flight_conditions: List[str],
    blade_sections: Optional[List[str]] = None,
) -> None:
    """
    Por cada condición de vuelo genera una figura de doble panel:
      - Izquierda: CL/CD_corrected vs α para root, mid_span, tip
      - Derecha:   CL_corrected vs α para root, mid_span, tip
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
            except ValueError:
                LOGGER.warning("No efficiency column in %s/%s corrected polar.", flight, section)
                continue

            cl_col = "cl_corrected" if "cl_corrected" in df.columns else "cl"
            color  = SECTION_COLORS.get(section, "#333333")
            section_label = section.replace("_", " ").title()

            try:
                row_opt   = find_second_peak_row(df, eff_col)
                alpha_opt = float(row_opt["alpha"])
                ld_opt    = float(row_opt[eff_col])
                cl_at_opt = float(row_opt[cl_col]) if cl_col in row_opt.index else None
                has_opt   = True
            except (ValueError, KeyError):
                has_opt = False
                alpha_opt = ld_opt = cl_at_opt = None

            legend_lbl = (
                rf"{section_label} ($\alpha_{{opt}}$ = {alpha_opt:.1f}°)"
                if has_opt else section_label
            )

            ax_eff.plot(df["alpha"], df[eff_col], color=color, label=legend_lbl, zorder=3)
            if has_opt:
                ax_eff.plot(alpha_opt, ld_opt, marker="*", color=color, markersize=11,
                            markeredgecolor="white", markeredgewidth=0.7, zorder=6, linestyle="none")
                ax_eff.axvline(alpha_opt, color=color, linestyle=":", linewidth=0.8, alpha=0.5)

            ax_cl.plot(df["alpha"], df[cl_col], color=color, label=legend_lbl, zorder=3)
            if has_opt and cl_at_opt is not None:
                ax_cl.plot(alpha_opt, cl_at_opt, marker="*", color=color, markersize=11,
                           markeredgecolor="white", markeredgewidth=0.7, zorder=6, linestyle="none")

            any_plotted = True

        if not any_plotted:
            plt.close(fig)
            continue

        ax_eff.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax_eff.set_ylabel(r"$C_L/C_D$ (Prandtl-Glauert corrected) [–]")
        ax_eff.set_title(f"Efficiency Polar — {flight.title()}\n"
                         r"(★ = 2nd peak, actual operating point)")
        ax_eff.legend(loc="lower right")

        ax_cl.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax_cl.set_ylabel(r"$C_L$ (Prandtl-Glauert corrected) [–]")
        ax_cl.set_title(f"Lift Polar — {flight.title()}\n"
                        r"(★ = $\alpha_{opt}$ from efficiency peak)")
        ax_cl.legend(loc="lower right")

        fig.suptitle(f"NACA 65-410 — Section Comparison — {flight.title()}",
                     fontsize=11, fontweight="bold")
        fig.tight_layout()
        fig.savefig(figures_dir / f"section_polar_comparison_{flight}.png")
        plt.close(fig)


# ---------------------------------------------------------------------------
# Figura B — Penalización de crucero (prueba visual del VPF)
# ---------------------------------------------------------------------------

def generate_cruise_penalty_figure(
    stage3_dir: Path,
    figures_dir: Path,
    non_cruise_conditions: Optional[List[str]] = None,
    blade_sections: Optional[List[str]] = None,
    reynolds_table: Optional[Dict[str, Dict[str, float]]] = None,
    alpha_min_second_peak: float = 3.0,
) -> None:
    """
    Por cada condición no-crucero genera una figura con:
      - Curvas CL/CD_corrected vs α para las tres secciones (con Re en leyenda)
      - Estrella verde en α_opt VPF por sección
      - Línea roja discontinua en α_cruise_design (paso fijo)
      - Anotación con el % de penalización en la sección mid_span
    """
    figures_dir.mkdir(parents=True, exist_ok=True)
    settings = get_plot_settings()
    w = settings["figure_size"]["width"]
    h = settings["figure_size"]["height"]

    sections  = blade_sections or ["root", "mid_span", "tip"]
    conditions = non_cruise_conditions or ["takeoff", "climb", "descent"]
    re_table  = reynolds_table or {}

    # Derivar alpha_cruise_design de los datos (no hardcodeado)
    alpha_cruise_design: float = _ALPHA_CRUISE_REF
    cruise_df = _load_corrected_polar(stage3_dir, "cruise", "mid_span")
    if cruise_df is not None:
        try:
            eff_col_cr = resolve_efficiency_column(cruise_df)
            row_cr     = find_second_peak_row(cruise_df, eff_col_cr, alpha_min_second_peak)
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
                row_opt   = find_second_peak_row(df, eff_col, alpha_min_second_peak)
                alpha_opt = float(row_opt["alpha"])
                ld_opt    = float(row_opt[eff_col])
                ax.plot(
                    alpha_opt, ld_opt,
                    marker="*", color="darkgreen", markersize=13,
                    markeredgecolor="white", markeredgewidth=1.0,
                    zorder=7, linestyle="none",
                    label=rf"  VPF opt. $\alpha$ = {alpha_opt:.1f}° [{section_label}]",
                )
                if section == "mid_span":
                    mid_span_ld_opt  = ld_opt
                    mid_span_eff_col = eff_col
                    mid_span_df      = df
            except (ValueError, KeyError):
                pass

            any_plotted = True

        if not any_plotted:
            plt.close(fig)
            continue

        ax.axvline(
            alpha_cruise_design,
            color="#B22222", linestyle="--", linewidth=1.4, zorder=5,
            label=rf"Fixed-pitch cruise $\alpha_{{design}}$ = {alpha_cruise_design:.1f}°",
        )

        if mid_span_ld_opt is not None:
            ld_at_cruise = _interpolate_ld_at_alpha(mid_span_df, mid_span_eff_col, alpha_cruise_design)
            if ld_at_cruise is not None and ld_at_cruise > 0:
                penalty_pct = 100.0 * (mid_span_ld_opt - ld_at_cruise) / mid_span_ld_opt
                eff_series  = mid_span_df[mid_span_eff_col].replace([np.inf, -np.inf], np.nan).dropna()
                ld_range    = float(eff_series.max() - eff_series.min()) if not eff_series.empty else 1.0
                alpha_range = float(mid_span_df["alpha"].max() - mid_span_df["alpha"].min())
                ax.annotate(
                    rf"Fixed-pitch loss $\approx${penalty_pct:.1f}%",
                    xy=(alpha_cruise_design, ld_at_cruise),
                    xytext=(alpha_cruise_design + 0.06 * alpha_range,
                            ld_at_cruise - 0.10 * ld_range),
                    arrowprops=dict(arrowstyle="->", color="#B22222", lw=1.1),
                    fontsize=9, color="#B22222", fontweight="bold",
                    zorder=8,
                )

        ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax.set_ylabel(r"$C_L/C_D$ (Prandtl-Glauert corrected) [–]")
        ax.set_title(
            f"VPF Efficiency Gain — {condition.title()} Condition\n"
            r"★ = VPF optimal $\alpha$   |   $\mathbf{-\,-}$ = fixed cruise pitch (penalty)",
            pad=8,
        )
        ax.legend(loc="lower right", fontsize=8)
        fig.tight_layout()
        fig.savefig(figures_dir / f"cruise_penalty_{condition}.png")
        plt.close(fig)


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

def generate_all_figures(
    polars_dir: Path,
    figures_dir: Path,
    metrics: List[AerodynamicMetrics],
    flight_conditions: List[str],
    blade_sections: List[str],
    stage3_dir: Optional[Path] = None,
    reynolds_table: Optional[Dict[str, Dict[str, float]]] = None,
) -> None:
    """
    Genera todas las figuras de publicación para la tesis.

    Figuras básicas (polares de Stage 2):
      1. generate_efficiency_plots
      2. generate_efficiency_by_section
      3. generate_alpha_opt_vs_condition

    Figuras extendidas (polares corregidas de Stage 3, requiere *stage3_dir*):
      A. generate_section_polar_comparison
      B. generate_cruise_penalty_figure
    """
    LOGGER.info("Generando curvas de eficiencia individuales...")
    generate_efficiency_plots(polars_dir, figures_dir, flight_conditions, blade_sections)

    LOGGER.info("Generando comparación por sección...")
    generate_efficiency_by_section(polars_dir, figures_dir, flight_conditions)

    LOGGER.info("Generando figura α_opt vs condición...")
    generate_alpha_opt_vs_condition(metrics, figures_dir)

    if stage3_dir is not None and stage3_dir.is_dir():
        LOGGER.info("Generando comparación de polares por sección (Figura A)...")
        generate_section_polar_comparison(
            stage3_dir, figures_dir, flight_conditions, blade_sections
        )
        LOGGER.info("Generando figuras de penalización de crucero (Figura B)...")
        non_cruise = [c for c in flight_conditions if c != "cruise"]
        generate_cruise_penalty_figure(
            stage3_dir, figures_dir,
            non_cruise_conditions=non_cruise,
            blade_sections=blade_sections,
            reynolds_table=reynolds_table,
        )
    else:
        LOGGER.info("stage3_dir no disponible — omitiendo Figuras A y B.")

    LOGGER.info("Todas las figuras generadas en: %s", figures_dir)
