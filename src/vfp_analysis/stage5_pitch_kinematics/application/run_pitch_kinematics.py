"""
run_pitch_kinematics.py
-----------------------
Orquestador del Stage 5: Análisis de Paso e Incidencia + Cinemática.

Fusión de los anteriores Stage 6 (VPF Analysis) y Stage 7 (Kinematics Analysis):

  1. Carga polares de Stage 2 y polares corregidos de Stage 3
  2. Calcula α_opt por condición/sección (second-peak method)
  3. Calcula Δα relativo a crucero (ajuste de paso aerodinámico)
  4. Convierte Δα en Δβ_mech mediante triángulos de velocidad
  5. Exporta 3 tablas CSV + 5 figuras + resumen de texto

Outputs (en results/stage5_pitch_kinematics/):
    tables/optimal_incidence.csv     — α_opt, CL/CD_max, Re, Mach por caso
    tables/pitch_adjustment.csv      — Δα relativo a crucero por caso
    tables/kinematics_analysis.csv   — V_ax, U, φ, β, Δβ_mech por caso
    figures/alpha_opt_by_condition.png
    figures/pitch_adjustment.png
    figures/efficiency_curves_{cond}.png  (×4, una por condición)
    figures/section_comparison.png
    figures/kinematics_comparison.png
    pitch_kinematics_summary.txt
    finalresults_stage5.txt
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis import config as base_config
from vfp_analysis.config_loader import get_output_dirs
from vfp_analysis.shared.plot_style import SECTION_COLORS
from vfp_analysis.stage5_pitch_kinematics.adapters.filesystem.data_loader import (
    FilesystemDataLoader,
)
from vfp_analysis.stage5_pitch_kinematics.adapters.filesystem.results_writer import (
    FilesystemPitchKinematicsWriter,
)
from vfp_analysis.stage5_pitch_kinematics.core.services.kinematics_service import (
    compute_kinematics,
)
from vfp_analysis.stage5_pitch_kinematics.core.services.optimal_incidence_service import (
    compute_all_optimal_incidences,
)
from vfp_analysis.stage5_pitch_kinematics.core.services.pitch_adjustment_service import (
    compute_pitch_adjustments,
)

LOGGER = logging.getLogger(__name__)

_SECTIONS: List[str] = ["root", "mid_span", "tip"]


# ---------------------------------------------------------------------------
# Helpers de figuras
# ---------------------------------------------------------------------------

def _build_condition_section_table(
    items: list,
    value_attr: str,
) -> Dict[str, Dict[str, float]]:
    """Construye un lookup ``{condition: {section: value}}`` de una lista de dataclasses."""
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
    """Dibuja barras agrupadas usando la paleta de sección compartida."""
    x     = np.arange(len(conditions))
    width = 0.22

    for i, section in enumerate(sections):
        values = [data.get(cond, {}).get(section, np.nan) for cond in conditions]
        bars   = ax.bar(
            x + i * width, values, width,
            label=section.replace("_", " ").title(),
            color=SECTION_COLORS[section],
            edgecolor="white", linewidth=0.6, zorder=3,
        )
        ax.bar_label(bars, fmt="%.2f°", padding=3, fontsize=8)

    if zero_line:
        ax.axhline(0, color="0.35", linestyle="--", linewidth=0.9)

    n_sections = len(sections)
    ax.set_xticks(x + width * (n_sections - 1) / 2)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.legend(loc="lower right")


def _plot_alpha_opt_by_condition(
    optimal_incidences: list,
    figures_dir: Path,
) -> None:
    """Barras agrupadas de α_opt por condición de vuelo y sección."""
    data       = _build_condition_section_table(optimal_incidences, "alpha_opt")
    conditions = sorted(data.keys())
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    _plot_grouped_bars(ax, data, conditions, _SECTIONS)
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"Optimal angle of attack $\alpha_{opt}$ [°]")
    ax.set_title("Optimal Angle of Attack by Flight Condition", pad=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "alpha_opt_by_condition.png")
    plt.close(fig)


def _plot_pitch_adjustment(
    pitch_adjustments: list,
    figures_dir: Path,
) -> None:
    """Barras agrupadas del ajuste de paso relativo a crucero."""
    data       = _build_condition_section_table(pitch_adjustments, "delta_pitch")
    conditions = sorted(data.keys())
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    _plot_grouped_bars(ax, data, conditions, _SECTIONS, zero_line=True)
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"Required pitch adjustment $\Delta\alpha$ [°]")
    ax.set_title("Required Pitch Adjustment Relative to Cruise", pad=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "pitch_adjustment.png")
    plt.close(fig)


def _plot_efficiency_curves(
    df_polars: pd.DataFrame,
    optimal_incidences: list,
    figures_dir: Path,
) -> None:
    """Curvas de eficiencia con puntos óptimos marcados, una figura por condición."""
    opt_lookup: Dict[tuple, tuple] = {
        (inc.condition, inc.section): (inc.alpha_opt, inc.cl_cd_max)
        for inc in optimal_incidences
    }

    eff_col: str | None = None
    for candidate in ("CL_CD", "ld"):
        if candidate in df_polars.columns:
            eff_col = candidate
            break

    if eff_col is None:
        LOGGER.warning("Sin columna de eficiencia — omitiendo curvas.")
        return

    for condition in df_polars["condition"].unique():
        df_cond = df_polars[df_polars["condition"] == condition]
        fig, ax = plt.subplots(figsize=(7.5, 5.0))

        for section in _SECTIONS:
            df_section = df_cond[df_cond["section"] == section]
            if df_section.empty:
                continue
            color = SECTION_COLORS[section]
            ax.plot(
                df_section["alpha"], df_section[eff_col],
                color=color, label=section.replace("_", " ").title(), zorder=3,
            )
            key = (condition, section)
            if key in opt_lookup:
                alpha_opt, eff_max = opt_lookup[key]
                ax.plot(
                    alpha_opt, eff_max,
                    marker="*", color=color, markersize=12,
                    markeredgecolor="white", markeredgewidth=0.6,
                    zorder=5, linestyle="none",
                )

        ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax.set_ylabel(r"Lift-to-drag ratio $C_L/C_D$ [–]")
        ax.set_title(f"Efficiency Curves — {condition.title()}", pad=8)
        ax.legend(loc="lower right")
        fig.tight_layout()
        fig.savefig(figures_dir / f"efficiency_curves_{condition}.png")
        plt.close(fig)


def _plot_section_comparison(
    optimal_incidences: list,
    figures_dir: Path,
) -> None:
    """Comparación de α_opt por sección de pala y condición de vuelo."""
    conditions = sorted(set(inc.condition for inc in optimal_incidences))
    by_section: Dict[str, Dict[str, float]] = {}
    for inc in optimal_incidences:
        by_section.setdefault(inc.section, {})[inc.condition] = inc.alpha_opt

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    x     = np.arange(len(_SECTIONS))
    width = 0.18
    cond_colors = ["#E31A1C", "#FF7F00", "#1F78B4", "#6A3D9A"]

    for i, condition in enumerate(conditions):
        values = [by_section.get(section, {}).get(condition, np.nan) for section in _SECTIONS]
        color  = cond_colors[i % len(cond_colors)]
        bars   = ax.bar(
            x + i * width, values, width,
            label=condition.title(), color=color,
            edgecolor="white", linewidth=0.6, zorder=3,
        )
        ax.bar_label(bars, fmt="%.1f°", padding=3, fontsize=7)

    ax.set_xlabel("Blade Section")
    ax.set_ylabel(r"Optimal angle of attack $\alpha_{opt}$ [°]")
    ax.set_title("Optimal Angle of Attack by Blade Section", pad=8)
    ax.set_xticks(x + width * (len(conditions) - 1) / 2)
    ax.set_xticklabels([s.replace("_", " ").title() for s in _SECTIONS])
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(figures_dir / "section_comparison.png")
    plt.close(fig)


def _plot_kinematics_comparison(
    df: pd.DataFrame,
    figures_dir: Path,
) -> None:
    """Panel triple: Δα aerodinámico vs Δβ mecánico por sección."""
    conditions = df["condition"].unique()
    sections   = df["section"].unique()

    fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=True)
    x     = np.arange(len(conditions))
    width = 0.35

    for i, section in enumerate(sections):
        ax     = axes[i]
        df_sec = df[df["section"] == section]
        ordered_cond = [c for c in ["takeoff", "climb", "cruise", "descent"] if c in conditions]

        val_aero = [
            df_sec[df_sec["condition"] == c]["delta_alpha_aero_deg"].values[0]
            for c in ordered_cond
        ]
        val_mech = [
            df_sec[df_sec["condition"] == c]["delta_beta_mech_deg"].values[0]
            for c in ordered_cond
        ]

        ax.bar(x - width / 2, val_aero, width,
               label=r"Aerodynamic ($\Delta\alpha$)", color="#9ECAE1", edgecolor="white")
        ax.bar(x + width / 2, val_mech, width,
               label=r"Mechanical ($\Delta\beta$)", color="#3182BD", edgecolor="white")
        ax.axhline(0, color="0.3", linestyle="--", linewidth=0.8)
        ax.set_title(f"Section: {section.replace('_', ' ').title()}")
        ax.set_xticks(x)
        ax.set_xticklabels([c.title() for c in ordered_cond])

        if i == 0:
            ax.set_ylabel("Adjustment Angle [°]")
            ax.legend(loc="lower right")

    fig.suptitle(
        "Aerodynamic vs Required Mechanical Pitch Adjustment (Velocity Triangles)",
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(figures_dir / "kinematics_comparison.png", dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------

def run_pitch_kinematics() -> None:
    """Ejecuta el Stage 5 completo: incidencia óptima + ajuste de paso + cinemática."""
    LOGGER.info("=" * 70)
    LOGGER.info("STAGE 5: Pitch & Kinematics Analysis")
    LOGGER.info("=" * 70)

    output_dirs      = get_output_dirs()
    polars_dir       = output_dirs["polars"]
    compressibility_dir = output_dirs["compressibility"]
    stage5_dir       = base_config.get_stage_dir(5)
    tables_dir       = stage5_dir / "tables"
    figures_dir      = stage5_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Cargar datos ──────────────────────────────────────────────────────
    LOGGER.info("Cargando datos aerodinámicos...")
    loader       = FilesystemDataLoader()
    df_polars    = loader.load_polar_data(polars_dir)
    df_corrected = loader.load_compressibility_data(compressibility_dir)

    if df_polars.empty:
        LOGGER.warning("Sin datos de polares — omitiendo Stage 5.")
        return

    LOGGER.info("Polares cargados: %d filas", len(df_polars))
    if not df_corrected.empty:
        LOGGER.info("Polares corregidos: %d filas", len(df_corrected))

    # ── 2. Incidencia óptima ─────────────────────────────────────────────────
    LOGGER.info("Calculando incidencias óptimas...")
    optimal_incidences = compute_all_optimal_incidences(df_polars, df_corrected)
    LOGGER.info("Incidencias calculadas: %d casos", len(optimal_incidences))

    # ── 3. Ajuste de paso aerodinámico ───────────────────────────────────────
    LOGGER.info("Calculando ajustes de paso relativo a crucero...")
    pitch_adjustments = compute_pitch_adjustments(optimal_incidences, reference_condition="cruise")
    LOGGER.info("Ajustes calculados: %d casos", len(pitch_adjustments))

    # ── 4. Cinemática (triángulos de velocidad) ──────────────────────────────
    LOGGER.info("Resolviendo triángulos de velocidad...")
    engine_config = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    kinematics_results = compute_kinematics(pitch_adjustments, engine_config)
    LOGGER.info("Cinemática resuelta: %d casos", len(kinematics_results))

    # ── 5. Figuras ───────────────────────────────────────────────────────────
    LOGGER.info("Generando figuras...")
    _plot_alpha_opt_by_condition(optimal_incidences, figures_dir)
    _plot_pitch_adjustment(pitch_adjustments, figures_dir)
    _plot_efficiency_curves(df_polars, optimal_incidences, figures_dir)
    _plot_section_comparison(optimal_incidences, figures_dir)

    # Figura cinemática (necesita DataFrame)
    kin_rows = [
        {
            "condition":           r.condition,
            "section":             r.section,
            "delta_alpha_aero_deg": next(
                a.delta_pitch for a in pitch_adjustments
                if a.condition == r.condition and a.section == r.section
            ),
            "delta_beta_mech_deg": r.delta_beta_mech_deg,
        }
        for r in kinematics_results
    ]
    df_kin = pd.DataFrame(kin_rows)
    _plot_kinematics_comparison(df_kin, figures_dir)

    # ── 6. Tablas ────────────────────────────────────────────────────────────
    LOGGER.info("Escribiendo tablas...")
    writer = FilesystemPitchKinematicsWriter()
    writer.write_optimal_incidence_table(
        optimal_incidences,
        tables_dir / "optimal_incidence.csv",
    )
    writer.write_pitch_adjustment_table(
        pitch_adjustments,
        tables_dir / "pitch_adjustment.csv",
    )
    writer.write_kinematics_table(
        kinematics_results, pitch_adjustments,
        tables_dir / "kinematics_analysis.csv",
    )

    # ── 7. Resúmenes ─────────────────────────────────────────────────────────
    summary_lines = [
        "Análisis integrado de incidencia óptima, ajuste de paso y cinemática.",
        "Δβ_mech = Δα_aero + Δφ  (triángulo de velocidades)",
        "",
        f"Casos calculados: {len(optimal_incidences)}",
        f"Tablas:  {tables_dir}",
        f"Figuras: {figures_dir}",
    ]
    writer.write_text_summary(
        "\n".join(summary_lines),
        stage5_dir / "pitch_kinematics_summary.txt",
    )

    from vfp_analysis.postprocessing.stage_summary_generator import (
        generate_stage5_summary,
        write_stage_summary,
    )
    stage5_summary = generate_stage5_summary(stage5_dir)
    write_stage_summary(5, stage5_summary, stage5_dir)
    LOGGER.info("Resumen escrito en: %s", stage5_dir / "finalresults_stage5.txt")

    LOGGER.info("=" * 70)
    LOGGER.info("Stage 5 completado.")
    LOGGER.info("  Tablas:  %s", tables_dir)
    LOGGER.info("  Figuras: %s", figures_dir)
    LOGGER.info("=" * 70)


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO,
                         format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    run_pitch_kinematics()
