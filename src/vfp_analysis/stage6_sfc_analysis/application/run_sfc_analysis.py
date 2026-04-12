"""
run_sfc_analysis.py
-------------------
Orquestador del Stage 6: Análisis de Consumo Específico de Combustible (SFC).

Lee los datos de rendimiento aerodináimico de Stage 4 y estima la reducción de SFC
que permite el fan de paso variable, comparando VPF (α_opt) vs paso fijo (α_design).

Inputs:
    results/stage4_performance_metrics/tables/summary_table.csv
    config/engine_parameters.yaml

Outputs (en results/stage6_sfc_analysis/):
    tables/sfc_section_breakdown.csv     — ε, Δη por condición × sección
    tables/sfc_analysis.csv              — resultados agregados por condición
    tables/sfc_sensitivity.csv           — barrido de τ × condición
    figures/fixed_vs_vpf_efficiency.png    — CL/CD_fixed vs CL/CD_vpf por sección
    figures/epsilon_spanwise.png           — ε_eff(r) capeado por sección y condición
    figures/sfc_sensitivity_tau.png        — sensibilidad de ΔSFC a τ
    figures/sfc_combined.png               — SFC base/VPF (izq.) + % reducción (der.)
    figures/fan_efficiency_improvement.png — η_fan base vs VPF por condición
    figures/efficiency_mechanism_breakdown.png — desglose Δη perfil vs mapa por condición
    sfc_analysis_summary.txt
    finalresults_stage6.txt
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

from vfp_analysis import config as base_config
from vfp_analysis.shared.plot_style import (
    COLORS,
    FLIGHT_LABELS,
    SECTION_COLORS,
    SECTION_LABELS,
    apply_style,
)
from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import (
    EngineBaseline,
    SfcAnalysisResult,
    SfcSectionResult,
    SfcSensitivityPoint,
)
from vfp_analysis.stage6_sfc_analysis.core.services.sfc_analysis_service import (
    compute_sfc_analysis,
    compute_sfc_sensitivity,
)
from vfp_analysis.stage6_sfc_analysis.core.services.summary_generator_service import (
    generate_sfc_summary,
)

LOGGER = logging.getLogger(__name__)

_COLOR_BASELINE = "#4393C3"
_COLOR_VPF      = "#4DAC26"

_CONDITIONS_ORDER = ["takeoff", "climb", "cruise", "descent"]
_SECTIONS_ORDER   = ["root", "mid_span", "tip"]


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------

def generate_sfc_figures(
    sfc_results: List[SfcAnalysisResult],
    section_results: List[SfcSectionResult],
    sensitivity_results: List[SfcSensitivityPoint],
    figures_dir: Path,
) -> None:
    """Genera las seis figuras del análisis SFC."""
    figures_dir.mkdir(parents=True, exist_ok=True)
    with apply_style():
        _plot_fixed_vs_vpf_efficiency(section_results, figures_dir)
        _plot_epsilon_spanwise(section_results, figures_dir)
        _plot_sfc_sensitivity_tau(sensitivity_results, figures_dir)
        _plot_sfc_combined(sfc_results, figures_dir)
        _plot_fan_efficiency_improvement(sfc_results, figures_dir)
        _plot_efficiency_mechanism_breakdown(sfc_results, figures_dir)


def _plot_fixed_vs_vpf_efficiency(
    section_results: List[SfcSectionResult],
    figures_dir: Path,
) -> None:
    """2×2 subplots: CL/CD paso fijo vs VPF por sección, para cada condición."""
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharey=False)
    conditions = [c for c in _CONDITIONS_ORDER]

    for ax, cond in zip(axes.flat, conditions):
        subset = [r for r in section_results if r.condition == cond]
        x = np.arange(len(_SECTIONS_ORDER))
        fixed = [next((r.cl_cd_fixed for r in subset if r.blade_section == s), 0.0)
                 for s in _SECTIONS_ORDER]
        vpf   = [next((r.cl_cd_vpf   for r in subset if r.blade_section == s), 0.0)
                 for s in _SECTIONS_ORDER]

        bars_f = ax.bar(x - 0.20, fixed, 0.35, label="Paso fijo (α_diseño)",
                        color=_COLOR_BASELINE, edgecolor="white", linewidth=0.5, zorder=3)
        bars_v = ax.bar(x + 0.20, vpf,   0.35, label="VPF (α_opt)",
                        color=_COLOR_VPF,      edgecolor="white", linewidth=0.5, zorder=3)
        ax.bar_label(bars_f, fmt="%.0f", padding=2, fontsize=7)
        ax.bar_label(bars_v, fmt="%.0f", padding=2, fontsize=7)
        ax.set_xticks(x)
        ax.set_xticklabels([SECTION_LABELS[s] for s in _SECTIONS_ORDER])
        ax.set_title(FLIGHT_LABELS.get(cond, cond), fontsize=10, fontweight="bold")
        ax.set_ylabel(r"$C_L/C_D$ [–]", fontsize=8)
        ax.legend(fontsize=7, loc="lower right")
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle(
        r"Eficiencia de perfil: Paso fijo (α_diseño) vs VPF (α_opt) por sección",
        fontsize=11, fontweight="bold", y=1.01,
    )
    fig.tight_layout()
    fig.savefig(figures_dir / "fixed_vs_vpf_efficiency.png")
    plt.close(fig)


def _plot_epsilon_spanwise(
    section_results: List[SfcSectionResult],
    figures_dir: Path,
) -> None:
    """Barras agrupadas: ε_eff capeado por sección y condición.

    Las barras muestran epsilon_eff = min(ε, 1.10), que es el valor que realmente
    se transfiere a la eficiencia del fan.  Cuando ε_bruto > 1.10 se anota el valor
    real sobre la barra correspondiente para evidenciar la magnitud de la ganancia.
    """
    from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import EPSILON_CAP

    conditions = _CONDITIONS_ORDER
    x = np.arange(len(conditions))
    width = 0.22

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for i, sec in enumerate(_SECTIONS_ORDER):
        eps_eff = [
            next((r.epsilon_eff for r in section_results
                  if r.condition == c and r.blade_section == sec), 1.0)
            for c in conditions
        ]
        eps_raw = [
            next((r.epsilon for r in section_results
                  if r.condition == c and r.blade_section == sec), 1.0)
            for c in conditions
        ]
        offset = (i - 1) * width
        bars = ax.bar(x + offset, eps_eff, width,
                      label=SECTION_LABELS[sec], color=SECTION_COLORS[sec],
                      edgecolor="white", linewidth=0.5, zorder=3)

        # Anotar valor bruto cuando supera el cap
        for bar, raw in zip(bars, eps_raw):
            if raw > EPSILON_CAP + 0.01:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.003,
                    f"ε={raw:.1f}",
                    ha="center", va="bottom", fontsize=6.5, color="0.3",
                    rotation=90,
                )

    ax.axhline(1.0,  ls="-",  color="black",   lw=1.0, label="ε = 1  (sin beneficio)", zorder=4)
    ax.axhline(EPSILON_CAP, ls="--", color="#EE6677", lw=1.2,
               label=f"ε cap = {EPSILON_CAP:.2f}  (Cumpsty 2004)", zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels([FLIGHT_LABELS.get(c, c) for c in conditions])
    ax.set_ylabel(r"Ratio de eficiencia ε$_{eff}$ = min(ε, cap) [–]")
    ax.set_title(
        "Beneficio span-wise del VPF por condición de vuelo\n"
        "(barras = ε capeado; anotaciones = ε bruto cuando excede el cap)",
        fontweight="bold",
    )
    ax.set_ylim(0, 1.22)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(figures_dir / "epsilon_spanwise.png")
    plt.close(fig)


def _plot_sfc_sensitivity_tau(
    sensitivity_results: List[SfcSensitivityPoint],
    figures_dir: Path,
) -> None:
    """Líneas de reducción de SFC vs τ para cada condición."""
    if not sensitivity_results:
        return

    tau_vals = sorted(set(p.tau for p in sensitivity_results))
    fig, ax = plt.subplots(figsize=(8, 5.5))

    for cond in _CONDITIONS_ORDER:
        pts = sorted(
            [p for p in sensitivity_results if p.condition == cond],
            key=lambda p: p.tau,
        )
        if not pts:
            continue
        y = [p.sfc_reduction_pct for p in pts]
        ax.plot(tau_vals, y, marker="o", color=COLORS[cond],
                label=FLIGHT_LABELS.get(cond, cond), linewidth=2, markersize=5)

    ax.axvline(0.65, ls="--", color="gray", lw=1.2, alpha=0.8, label="τ nominal = 0.65")
    ax.axhspan(2.0, 5.0, alpha=0.08, color="#228833",
               label="Rango literario 2–5% (Cumpsty 2004)")
    ax.set_xlabel("Coeficiente de transferencia de eficiencia τ [–]")
    ax.set_ylabel("Reducción de SFC [%]")
    ax.set_title("Sensibilidad del impacto en SFC al coeficiente τ", fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(figures_dir / "sfc_sensitivity_tau.png")
    plt.close(fig)


def _plot_sfc_combined(
    sfc_results: List[SfcAnalysisResult],
    figures_dir: Path,
) -> None:
    """Figura combinada de dos paneles:
      - Izquierdo: SFC absoluto baseline vs VPF por condición.
      - Derecho:   % reducción de SFC por condición con banda literaria 2–5%.
    """
    ordered    = [r for c in _CONDITIONS_ORDER for r in sfc_results if r.condition == c]
    conditions = [r.condition for r in ordered]
    labels     = [FLIGHT_LABELS.get(c, c) for c in conditions]
    sfc_base   = [r.sfc_baseline for r in ordered]
    sfc_new    = [r.sfc_new for r in ordered]
    reductions = [r.sfc_reduction_percent for r in ordered]
    x = np.arange(len(conditions))
    width = 0.35

    fig, (ax_sfc, ax_pct) = plt.subplots(1, 2, figsize=(13, 5.5))

    # ── Panel izquierdo: SFC absoluto ───────────────────────────────────────
    bars_b = ax_sfc.bar(x - width / 2, sfc_base, width, label="Paso fijo (baseline)",
                        color=_COLOR_BASELINE, edgecolor="white", linewidth=0.6, zorder=3)
    bars_v = ax_sfc.bar(x + width / 2, sfc_new,  width, label="VPF (paso variable)",
                        color=_COLOR_VPF,      edgecolor="white", linewidth=0.6, zorder=3)
    ax_sfc.bar_label(bars_b, fmt="%.4f", padding=3, fontsize=7)
    ax_sfc.bar_label(bars_v, fmt="%.4f", padding=3, fontsize=7)
    ax_sfc.set_xlabel("Condición de vuelo")
    ax_sfc.set_ylabel("SFC [lb/(lbf·hr)]")
    ax_sfc.set_title("SFC: Baseline vs VPF", fontweight="bold")
    ax_sfc.set_xticks(x)
    ax_sfc.set_xticklabels(labels)
    ax_sfc.legend(loc="lower right", fontsize=8)
    ax_sfc.grid(axis="y", alpha=0.3)

    # ── Panel derecho: % reducción ──────────────────────────────────────────
    bar_colors = [COLORS.get(c, _COLOR_VPF) for c in conditions]
    bars_r = ax_pct.bar(x, reductions, width=0.55, color=bar_colors,
                        edgecolor="white", linewidth=0.6, zorder=3)
    ax_pct.bar_label(bars_r, fmt="%.2f%%", padding=3, fontsize=8, fontweight="bold")
    ax_pct.axhspan(2.0, 5.0, alpha=0.10, color="#228833",
                   label="Rango literario 2–5%\n(Cumpsty 2004, p. 280)")
    ax_pct.axhline(0, color="0.4", lw=0.8)
    ax_pct.set_xlabel("Condición de vuelo")
    ax_pct.set_ylabel("Reducción de SFC [%]")
    ax_pct.set_title("Reducción de SFC — VPF vs Paso Fijo", fontweight="bold")
    ax_pct.set_xticks(x)
    ax_pct.set_xticklabels(labels)
    ax_pct.legend(fontsize=8)
    ax_pct.grid(axis="y", alpha=0.3)

    fig.suptitle("Impacto del Fan de Paso Variable en el SFC", fontsize=12,
                 fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(figures_dir / "sfc_combined.png")
    plt.close(fig)


def _plot_fan_efficiency_improvement(
    sfc_results: List[SfcAnalysisResult],
    figures_dir: Path,
) -> None:
    """Eficiencia de fan base vs VPF por condición."""
    ordered = [r for c in _CONDITIONS_ORDER for r in sfc_results if r.condition == c]
    conditions   = [r.condition for r in ordered]
    fan_baseline = [r.fan_efficiency_baseline * 100 for r in ordered]
    fan_new      = [r.fan_efficiency_new * 100 for r in ordered]
    x = np.arange(len(conditions))
    width = 0.35

    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    bars_b = ax.bar(x - width / 2, fan_baseline, width, label="Baseline (paso fijo)",
                    color=_COLOR_BASELINE, edgecolor="white", linewidth=0.6, zorder=3)
    bars_v = ax.bar(x + width / 2, fan_new, width, label="VPF (paso variable)",
                    color=_COLOR_VPF, edgecolor="white", linewidth=0.6, zorder=3)
    ax.bar_label(bars_b, fmt="%.1f%%", padding=3, fontsize=7)
    ax.bar_label(bars_v, fmt="%.1f%%", padding=3, fontsize=7)
    ax.set_xlabel("Condición de vuelo")
    ax.set_ylabel("Eficiencia isentrópica de fan [%]")
    ax.set_title("Eficiencia de Fan: Baseline vs VPF", fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([FLIGHT_LABELS.get(c, c) for c in conditions])
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=0.3)
    # Set y-axis to show differences clearly
    y_min = max(0, min(fan_baseline) - 2)
    ax.set_ylim(y_min, min(100, max(fan_new) + 3))
    fig.tight_layout()
    fig.savefig(figures_dir / "fan_efficiency_improvement.png")
    plt.close(fig)


def _plot_efficiency_mechanism_breakdown(
    sfc_results: List[SfcAnalysisResult],
    figures_dir: Path,
) -> None:
    """Barras apiladas: desglose de Δη_fan en contribución de perfil y de mapa φ.

    Muestra visualmente que el mecanismo de perfil (optimización 2D CL/CD via τ)
    y el mecanismo de mapa del fan (recuperación de pérdidas por φ ≠ φ_opt) son
    independientes y aditivos, reforzando la justificación del VPF.
    """
    import math as _math

    ordered = [r for c in _CONDITIONS_ORDER for r in sfc_results if r.condition == c]
    if not ordered:
        return

    # Filtrar condiciones con datos válidos
    conditions   = [r.condition for r in ordered]
    labels       = [FLIGHT_LABELS.get(c, c) for c in conditions]
    d_eta_prof   = [r.delta_eta_profile * 100 if not _math.isnan(r.delta_eta_profile) else 0.0
                    for r in ordered]
    d_eta_map    = [r.delta_eta_map * 100 if not _math.isnan(r.delta_eta_map) else 0.0
                    for r in ordered]
    d_eta_total  = [r.delta_eta_fan * 100 for r in ordered]
    x = np.arange(len(conditions))

    _COLOR_PROFILE = "#4393C3"   # azul — mecanismo de perfil
    _COLOR_MAP     = "#74C476"   # verde — mecanismo de mapa

    fig, (ax_eta, ax_sfc) = plt.subplots(1, 2, figsize=(13, 5.5))

    # ── Panel izquierdo: Δη desglosado (barras apiladas) ────────────────
    bars_p = ax_eta.bar(x, d_eta_prof, 0.55, label="Mecanismo de perfil\n(CL/CD → fan vía τ)",
                        color=_COLOR_PROFILE, edgecolor="white", linewidth=0.6, zorder=3)
    bars_m = ax_eta.bar(x, d_eta_map, 0.55, bottom=d_eta_prof,
                        label="Mecanismo de mapa\n(recuperación pérdida φ)",
                        color=_COLOR_MAP, edgecolor="white", linewidth=0.6, zorder=3)

    # Etiqueta del total
    for xi, tot in zip(x, d_eta_total):
        ax_eta.text(xi, tot + 0.03, f"{tot:.2f}%", ha="center", va="bottom",
                    fontsize=8, fontweight="bold", color="0.2")

    ax_eta.axhline(0, color="0.4", lw=0.8)
    ax_eta.set_xticks(x)
    ax_eta.set_xticklabels(labels)
    ax_eta.set_ylabel("Mejora de eficiencia de fan Δη [pp]")
    ax_eta.set_title("Desglose por mecanismo físico VPF", fontweight="bold")
    ax_eta.legend(fontsize=8, loc="upper right")
    ax_eta.grid(axis="y", alpha=0.3)

    # ── Panel derecho: fracción de cada mecanismo (%) ───────────────────
    frac_prof = []
    frac_map  = []
    for p, m in zip(d_eta_prof, d_eta_map):
        tot = p + m
        if tot > 0:
            frac_prof.append(p / tot * 100)
            frac_map.append(m / tot * 100)
        else:
            frac_prof.append(0.0)
            frac_map.append(0.0)

    ax_sfc.bar(x, frac_prof, 0.55, label="Perfil", color=_COLOR_PROFILE,
               edgecolor="white", linewidth=0.6, zorder=3)
    ax_sfc.bar(x, frac_map, 0.55, bottom=frac_prof, label="Mapa φ",
               color=_COLOR_MAP, edgecolor="white", linewidth=0.6, zorder=3)
    ax_sfc.set_xticks(x)
    ax_sfc.set_xticklabels(labels)
    ax_sfc.set_ylim(0, 115)
    ax_sfc.set_ylabel("Fracción de la ganancia total [%]")
    ax_sfc.set_title("Contribución relativa de cada mecanismo", fontweight="bold")
    ax_sfc.legend(fontsize=8, loc="upper right")
    ax_sfc.grid(axis="y", alpha=0.3)

    fig.suptitle(
        "Dos mecanismos independientes de beneficio del Fan de Paso Variable (VPF)",
        fontsize=11, fontweight="bold", y=1.01,
    )
    fig.tight_layout()
    fig.savefig(figures_dir / "efficiency_mechanism_breakdown.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _write_section_table(
    section_results: List[SfcSectionResult],
    output_path: Path,
) -> None:
    rows = [
        {
            "condition":           r.condition,
            "blade_section":       r.blade_section,
            "CL_CD_fixed":         r.cl_cd_fixed,
            "CL_CD_vpf":           r.cl_cd_vpf,
            "epsilon":             r.epsilon,
            "epsilon_eff":         r.epsilon_eff,
            "delta_eta_profile":   r.delta_eta_profile,
            "efficiency_gain_pct": r.efficiency_gain_pct,
            "delta_alpha_deg":     r.delta_alpha_deg,
        }
        for r in section_results
    ]
    df = pd.DataFrame(rows).sort_values(["condition", "blade_section"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")


def _write_sfc_table(
    sfc_results: List[SfcAnalysisResult],
    output_path: Path,
) -> None:
    rows = [
        {
            "condition":                r.condition,
            "CL_CD_fixed_mean":         r.cl_cd_fixed,
            "CL_CD_vpf_mean":           r.cl_cd_vpf,
            "epsilon_mean":             r.epsilon_mean,
            "delta_alpha_mean_deg":     r.delta_alpha_mean_deg,
            "k_sensitivity":            r.k_sensitivity,
            "delta_eta_fan":            r.delta_eta_fan,
            "fan_efficiency_baseline":  r.fan_efficiency_baseline,
            "fan_efficiency_new":       r.fan_efficiency_new,
            "SFC_baseline":             r.sfc_baseline,
            "SFC_new":                  r.sfc_new,
            "SFC_reduction_percent":    r.sfc_reduction_percent,
        }
        for r in sfc_results
    ]
    df = pd.DataFrame(rows).sort_values("condition")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, float_format="%.6f")


def _write_sensitivity_table(
    sensitivity_results: List[SfcSensitivityPoint],
    output_path: Path,
) -> None:
    rows = [
        {
            "tau":               p.tau,
            "condition":         p.condition,
            "epsilon_mean":      p.epsilon_mean,
            "delta_eta_fan":     p.delta_eta_fan,
            "eta_fan_new":       p.eta_fan_new,
            "SFC_baseline":      p.sfc_baseline,
            "SFC_new":           p.sfc_new,
            "SFC_reduction_pct": p.sfc_reduction_pct,
        }
        for p in sensitivity_results
    ]
    df = pd.DataFrame(rows).sort_values(["tau", "condition"])
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

    # ── 1. Cargar métricas de Stage 4 (fuente primaria) ──────────────────
    stage4_tables = base_config.get_stage_dir(4) / "tables"
    metrics_path  = stage4_tables / "summary_table.csv"
    if not metrics_path.exists():
        LOGGER.error(
            "summary_table.csv no encontrado en %s — Stage 4 debe ejecutarse primero.",
            stage4_tables,
        )
        return
    metrics_df = pd.read_csv(metrics_path)
    LOGGER.info("Métricas de Stage 4 cargadas: %d filas", len(metrics_df))

    # Verificar columnas requeridas
    required_cols = {"flight_condition", "blade_section", "max_efficiency", "eff_at_design_alpha"}
    missing = required_cols - set(metrics_df.columns)
    if missing:
        LOGGER.error("Columnas faltantes en summary_table.csv: %s", missing)
        return

    # Filtrar crucero con delta_alpha = 0 (referencia, sin mejora VPF)
    n_cruise_valid = (metrics_df["flight_condition"] == "cruise").sum()
    LOGGER.info("Condición de referencia 'cruise': %d secciones", n_cruise_valid)

    # ── 2. Cargar parámetros base del motor ─────────────────────────────
    engine_config_path = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    with engine_config_path.open("r", encoding="utf-8") as f:
        _cfg = yaml.safe_load(f)
    engine_baseline = EngineBaseline(
        baseline_sfc=_cfg["baseline_sfc"],
        fan_efficiency=_cfg["fan_efficiency"],
        bypass_ratio=_cfg["bypass_ratio"],
    )
    LOGGER.info(
        "Motor: SFC_base=%.4f, η_fan=%.3f, BPR=%.1f",
        engine_baseline.baseline_sfc, engine_baseline.fan_efficiency, engine_baseline.bypass_ratio,
    )

    # ── 3. Calcular mejoras de SFC ───────────────────────────────────────
    sfc_results, section_results = compute_sfc_analysis(
        metrics_df, engine_baseline, engine_config_path,
    )
    LOGGER.info("Análisis SFC: %d condiciones, %d secciones", len(sfc_results), len(section_results))

    # ── 4. Análisis de sensibilidad a τ ─────────────────────────────────
    sensitivity_results = compute_sfc_sensitivity(
        metrics_df, engine_baseline, config_path=engine_config_path,
    )
    LOGGER.info("Sensibilidad: %d puntos (τ × condición)", len(sensitivity_results))

    # ── 5. Figuras ───────────────────────────────────────────────────────
    generate_sfc_figures(sfc_results, section_results, sensitivity_results, figures_dir)

    # ── 6. Tablas ────────────────────────────────────────────────────────
    _write_section_table(section_results, tables_dir / "sfc_section_breakdown.csv")
    _write_sfc_table(sfc_results,         tables_dir / "sfc_analysis.csv")
    _write_sensitivity_table(sensitivity_results, tables_dir / "sfc_sensitivity.csv")

    # ── 7. Resúmenes de texto ────────────────────────────────────────────
    summary_text = generate_sfc_summary(sfc_results, section_results)
    (stage6_dir / "sfc_analysis_summary.txt").write_text(summary_text, encoding="utf-8")

    from vfp_analysis.postprocessing.stage_summary_generator import (
        generate_stage6_summary,
        write_stage_summary,
    )
    stage6_summary = generate_stage6_summary(stage6_dir)
    write_stage_summary(6, stage6_summary, stage6_dir)

    # ── 8. Log resumen ───────────────────────────────────────────────────
    if sfc_results:
        mean_reduction = sum(r.sfc_reduction_percent for r in sfc_results) / len(sfc_results)
        max_reduction  = max(r.sfc_reduction_percent for r in sfc_results)
        LOGGER.info("Reducción media de SFC: %.2f%%", mean_reduction)
        LOGGER.info("Reducción máxima de SFC: %.2f%%", max_reduction)

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
