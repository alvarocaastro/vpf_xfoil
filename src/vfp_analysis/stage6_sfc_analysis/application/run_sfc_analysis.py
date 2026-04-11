"""
run_sfc_analysis.py
-------------------
Orquestador del Stage 6: Análisis de Consumo Específico de Combustible (SFC).

Lee los resultados de incidencia óptima de Stage 5 y estima la reducción de SFC
que permite el fan de paso variable mediante el modelo de transferencia de
eficiencia de perfil a fan.

Inputs:
    results/stage5_pitch_kinematics/tables/optimal_incidence.csv
    config/engine_parameters.yaml

Outputs (en results/stage6_sfc_analysis/):
    tables/sfc_analysis.csv
    figures/sfc_vs_condition.png
    figures/sfc_reduction_percent.png
    figures/fan_efficiency_improvement.png
    figures/efficiency_vs_sfc.png
    sfc_analysis_summary.txt
    finalresults_stage6.txt
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from vfp_analysis import config as base_config
from vfp_analysis.shared.plot_style import SECTION_COLORS  # noqa: F401 (herencia de rcParams)
from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import EngineBaseline, SfcAnalysisResult
from vfp_analysis.stage6_sfc_analysis.core.services.sfc_analysis_service import (
    compute_sfc_analysis,
)
from vfp_analysis.stage6_sfc_analysis.core.services.summary_generator_service import (
    generate_sfc_summary,
)

LOGGER = logging.getLogger(__name__)

_COLOR_BASELINE = "#4393C3"   # azul medio
_COLOR_VPF      = "#4DAC26"   # verde


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------

def generate_sfc_figures(sfc_results: list, figures_dir: Path) -> None:
    """Genera las cuatro figuras del análisis SFC."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    _plot_sfc_vs_condition(sfc_results, figures_dir)
    _plot_sfc_reduction(sfc_results, figures_dir)
    _plot_fan_efficiency_improvement(sfc_results, figures_dir)
    _plot_efficiency_vs_sfc(sfc_results, figures_dir)


def _plot_sfc_vs_condition(sfc_results: list, figures_dir: Path) -> None:
    """SFC base vs VPF por condición de vuelo."""
    conditions   = [r.condition for r in sfc_results]
    sfc_baseline = [r.sfc_baseline for r in sfc_results]
    sfc_new      = [r.sfc_new for r in sfc_results]
    x = np.arange(len(conditions))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars_b = ax.bar(x - width / 2, sfc_baseline, width, label="Baseline (paso fijo)",
                    color=_COLOR_BASELINE, edgecolor="white", linewidth=0.6, zorder=3)
    bars_v = ax.bar(x + width / 2, sfc_new, width, label="VPF (paso variable)",
                    color=_COLOR_VPF, edgecolor="white", linewidth=0.6, zorder=3)
    ax.bar_label(bars_b, fmt="%.4f", padding=3, fontsize=7)
    ax.bar_label(bars_v, fmt="%.4f", padding=3, fontsize=7)
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel("Specific Fuel Consumption [lb/(lbf·hr)]")
    ax.set_title("SFC: Baseline paso fijo vs Fan Paso Variable", pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(figures_dir / "sfc_vs_condition.png")
    plt.close(fig)


def _plot_sfc_reduction(sfc_results: list, figures_dir: Path) -> None:
    """Porcentaje de reducción de SFC por condición."""
    conditions = [r.condition for r in sfc_results]
    reductions = [r.sfc_reduction_percent for r in sfc_results]
    x = np.arange(len(conditions))

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars = ax.bar(x, reductions, width=0.55, color=_COLOR_VPF,
                  edgecolor="white", linewidth=0.6, zorder=3)
    ax.bar_label(bars, fmt="%.2f %%", padding=3, fontsize=8, fontweight="bold")
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel("SFC Reduction [%]")
    ax.set_title("Reducción de SFC por Fan de Paso Variable", pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    fig.savefig(figures_dir / "sfc_reduction_percent.png")
    plt.close(fig)


def _plot_fan_efficiency_improvement(sfc_results: list, figures_dir: Path) -> None:
    """Eficiencia de fan base vs VPF por condición."""
    conditions   = [r.condition for r in sfc_results]
    fan_baseline = [r.fan_efficiency_baseline * 100 for r in sfc_results]
    fan_new      = [r.fan_efficiency_new * 100 for r in sfc_results]
    x = np.arange(len(conditions))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars_b = ax.bar(x - width / 2, fan_baseline, width, label="Baseline (paso fijo)",
                    color=_COLOR_BASELINE, edgecolor="white", linewidth=0.6, zorder=3)
    bars_v = ax.bar(x + width / 2, fan_new, width, label="VPF (paso variable)",
                    color=_COLOR_VPF, edgecolor="white", linewidth=0.6, zorder=3)
    ax.bar_label(bars_b, fmt="%.1f %%", padding=3, fontsize=7)
    ax.bar_label(bars_v, fmt="%.1f %%", padding=3, fontsize=7)
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel("Fan Isentropic Efficiency [%]")
    ax.set_title("Eficiencia de Fan: Baseline vs VPF", pad=8)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in conditions])
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(figures_dir / "fan_efficiency_improvement.png")
    plt.close(fig)


def _plot_efficiency_vs_sfc(sfc_results: list, figures_dir: Path) -> None:
    """Scatter: CL/CD vs SFC — muestra la relación inversa."""
    cl_cd_vpf  = [r.cl_cd_vpf for r in sfc_results]
    sfc_new    = [r.sfc_new for r in sfc_results]
    conditions = [r.condition for r in sfc_results]
    cond_colors = ["#E31A1C", "#FF7F00", "#1F78B4", "#6A3D9A"]

    fig, ax = plt.subplots(figsize=(6.5, 5.0))
    for i, condition in enumerate(conditions):
        color = cond_colors[i % len(cond_colors)]
        ax.scatter(cl_cd_vpf[i], sfc_new[i], s=120, color=color,
                   edgecolors="white", linewidths=0.8, label=condition.title(), zorder=4)
        ax.annotate(condition.title(), (cl_cd_vpf[i], sfc_new[i]),
                    xytext=(6, 4), textcoords="offset points", fontsize=8)

    ax.set_xlabel(r"Aerodynamic lift-to-drag ratio $C_L/C_D$ [–]")
    ax.set_ylabel("Specific Fuel Consumption [lb/(lbf·hr)]")
    ax.set_title(r"$C_L/C_D$ vs SFC — Puntos de operación VPF", pad=8)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(figures_dir / "efficiency_vs_sfc.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _write_sfc_table(sfc_results: list, output_path: Path) -> None:
    """Escribe los resultados SFC en CSV."""
    rows = [
        {
            "condition":               r.condition,
            "CL_CD_baseline":          r.cl_cd_baseline,
            "CL_CD_vpf":               r.cl_cd_vpf,
            "fan_efficiency_baseline": r.fan_efficiency_baseline,
            "fan_efficiency_new":      r.fan_efficiency_new,
            "SFC_baseline":            r.sfc_baseline,
            "SFC_new":                 r.sfc_new,
            "SFC_reduction_percent":   r.sfc_reduction_percent,
        }
        for r in sfc_results
    ]
    df = pd.DataFrame(rows).sort_values("condition")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def run_sfc_analysis() -> None:
    """Ejecuta el Stage 6 completo: análisis de SFC."""
    LOGGER.info("=" * 70)
    LOGGER.info("STAGE 6: Specific Fuel Consumption (SFC) Impact Analysis")
    LOGGER.info("=" * 70)

    stage6_dir  = base_config.get_stage_dir(6)
    stage6_dir.mkdir(parents=True, exist_ok=True)
    tables_dir  = stage6_dir / "tables"
    figures_dir = stage6_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # ── 1. Cargar incidencias óptimas de Stage 5 ─────────────────────────────
    stage5_tables   = base_config.get_stage_dir(5) / "tables"
    optimal_path    = stage5_tables / "optimal_incidence.csv"
    if not optimal_path.exists():
        LOGGER.warning("No se encontró optimal_incidence.csv — omitiendo Stage 6.")
        return
    optimal_df = pd.read_csv(optimal_path)
    LOGGER.info("Incidencias óptimas cargadas: %d registros", len(optimal_df))

    # ── 2. Cargar parámetros base del motor ─────────────────────────────────
    engine_config_path = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    with engine_config_path.open("r", encoding="utf-8") as f:
        _cfg = yaml.safe_load(f)
    engine_baseline = EngineBaseline(
        baseline_sfc=_cfg["baseline_sfc"],
        fan_efficiency=_cfg["fan_efficiency"],
        bypass_ratio=_cfg["bypass_ratio"],
        cruise_velocity=_cfg["cruise_velocity"],
        jet_velocity=_cfg["jet_velocity"],
    )
    LOGGER.info("SFC base: %.4f lb/(lbf·hr)", engine_baseline.baseline_sfc)

    # ── 3. Calcular mejoras de SFC ───────────────────────────────────────────
    sfc_results = compute_sfc_analysis(optimal_df, engine_baseline, engine_config_path)
    LOGGER.info("Análisis SFC calculado para %d condiciones", len(sfc_results))

    # ── 4. Figuras ───────────────────────────────────────────────────────────
    generate_sfc_figures(sfc_results, figures_dir)

    # ── 5. Tablas y resúmenes ────────────────────────────────────────────────
    _write_sfc_table(sfc_results, tables_dir / "sfc_analysis.csv")

    summary_text   = generate_sfc_summary(sfc_results)
    summary_path   = stage6_dir / "sfc_analysis_summary.txt"
    summary_path.write_text(summary_text, encoding="utf-8")

    from vfp_analysis.postprocessing.stage_summary_generator import (
        generate_stage6_summary,
        write_stage_summary,
    )
    stage6_summary = generate_stage6_summary(stage6_dir)
    write_stage_summary(6, stage6_summary, stage6_dir)
    LOGGER.info("Resumen escrito en: %s", stage6_dir / "finalresults_stage6.txt")

    LOGGER.info("=" * 70)
    LOGGER.info("Stage 6 completado.")
    LOGGER.info("  Tablas:  %s", tables_dir)
    LOGGER.info("  Figuras: %s", figures_dir)
    LOGGER.info("=" * 70)


if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO,
                         format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    run_sfc_analysis()
