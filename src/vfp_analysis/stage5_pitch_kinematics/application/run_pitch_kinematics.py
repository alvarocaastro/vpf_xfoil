"""
run_pitch_kinematics.py
-----------------------
Orquestador del Stage 5: Aerodinámica completa del fan de paso variable.

Cadena de análisis:
  1. Cargar polares Stage 2 + corregidos Stage 3
  2. [A] Correcciones de cascada (Weinig + Carter)
  3. [B] Correcciones rotacionales 3D (Snel) → polares 3D
  4. Incidencia óptima 3D (segundo pico de CL_3D/CD en α ≥ 3°)
  5. Ajuste de paso Δα relativo a crucero
  6. Cinemática: triángulos de velocidad con Va explícita → Δβ_mech
  7. [C] Twist de diseño + compromiso off-design span-wise
  8. [D] Carga de etapa (Euler: φ, ψ, W_spec)
  9. 14 figuras + 7 tablas CSV + resúmenes de texto

Outputs (en results/stage5_pitch_kinematics/):
    tables/
        cascade_corrections.csv
        rotational_corrections.csv
        optimal_incidence.csv
        pitch_adjustment.csv
        blade_twist_design.csv
        off_design_incidence.csv
        stage_loading.csv
        kinematics_analysis.csv
    figures/  (14 PNG)
    pitch_kinematics_summary.txt
    finalresults_stage5.txt
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vfp_analysis import config as base_config
from vfp_analysis.config_loader import (
    get_axial_velocities,
    get_blade_geometry,
    get_blade_radii,
    get_fan_rpm,
    get_output_dirs,
)
from vfp_analysis.shared.plot_style import SECTION_COLORS, apply_style
from vfp_analysis.stage5_pitch_kinematics.adapters.filesystem.data_loader import (
    FilesystemDataLoader,
)
from vfp_analysis.stage5_pitch_kinematics.adapters.filesystem.results_writer import (
    FilesystemPitchKinematicsWriter,
)
from vfp_analysis.stage5_pitch_kinematics.core.services.blade_twist_service import (
    OffDesignIncidenceResult,
    TwistDesignResult,
    compute_blade_twist,
    compute_off_design_incidence,
)
from vfp_analysis.stage5_pitch_kinematics.core.services.cascade_correction_service import (
    CascadeResult,
    apply_weinig_to_polar,
    compute_cascade_corrections,
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
from vfp_analysis.stage5_pitch_kinematics.core.services.rotational_correction_service import (
    RotationalCorrectionResult,
    build_3d_polar_map,
    compute_rotational_corrections,
)
from vfp_analysis.stage5_pitch_kinematics.core.services.stage_loading_service import (
    StageLoadingResult,
    compute_stage_loading,
)

LOGGER = logging.getLogger(__name__)

_SECTIONS: List[str] = ["root", "mid_span", "tip"]
_CONDITIONS_ORDER: List[str] = ["takeoff", "climb", "cruise", "descent"]

apply_style()


# ---------------------------------------------------------------------------
# Helpers de estilo compartidos
# ---------------------------------------------------------------------------

def _cond_colors() -> Dict[str, str]:
    return {
        "takeoff": "#E31A1C",
        "climb":   "#FF7F00",
        "cruise":  "#1F78B4",
        "descent": "#6A3D9A",
    }


def _ordered_conditions(conditions) -> List[str]:
    present = set(conditions)
    return [c for c in _CONDITIONS_ORDER if c in present]


# ---------------------------------------------------------------------------
# A — Figuras de cascada
# ---------------------------------------------------------------------------

def _fig_cascade_solidity(cascade: List[CascadeResult], figures_dir: Path) -> None:
    """σ(r) con zonas de régimen marcadas."""
    sections = [r.section for r in cascade]
    radii    = [r.radius_m for r in cascade]
    sigmas   = [r.solidity for r in cascade]

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.axhspan(0.0, 0.5,  alpha=0.12, color="#4CAF50", label="Isolated airfoil (σ < 0.5)")
    ax.axhspan(0.5, 1.0,  alpha=0.12, color="#FF9800", label="Moderate cascade (0.5–1.0)")
    ax.axhspan(1.0, 3.0,  alpha=0.12, color="#F44336", label="High solidity (σ > 1.0)")

    for res in cascade:
        ax.scatter(res.radius_m, res.solidity,
                   s=120, color=SECTION_COLORS[res.section],
                   zorder=5, edgecolors="white", linewidths=0.8)
        ax.annotate(
            f"{res.section.replace('_',' ').title()}\nσ={res.solidity:.2f}",
            (res.radius_m, res.solidity),
            xytext=(6, 6), textcoords="offset points", fontsize=8,
        )

    ax.set_xlabel("Blade radius r [m]")
    ax.set_ylabel(r"Solidity $\sigma = c/s$ [—]")
    ax.set_title("Cascade Solidity Profile — Fan Blade Sections", pad=8)
    ax.set_xlim(0, max(radii) * 1.3)
    ax.set_ylim(0, max(sigmas) * 1.5)
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "cascade_solidity_profile.png")
    plt.close(fig)


def _fig_cascade_cl_correction(cascade: List[CascadeResult], figures_dir: Path) -> None:
    """CL_2D vs CL_cascade (en α_opt_cruise) por sección."""
    sections = [r.section for r in cascade]
    cl_2d    = [r.cl_2d_at_alpha_opt for r in cascade]
    cl_casc  = [r.cl_cascade_at_alpha_opt for r in cascade]
    x = np.arange(len(sections))
    width = 0.35

    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    bars_2d = ax.bar(x - width/2, cl_2d, width, label=r"$C_L$ isolated 2D",
                     color="#4393C3", edgecolor="white", linewidth=0.6, zorder=3)
    bars_c  = ax.bar(x + width/2, cl_casc, width, label=r"$C_L$ cascade (Weinig)",
                     color="#D6604D", edgecolor="white", linewidth=0.6, zorder=3)
    ax.bar_label(bars_2d, fmt="%.3f", padding=3, fontsize=8)
    ax.bar_label(bars_c,  fmt="%.3f", padding=3, fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels([s.replace("_", " ").title() for s in sections])
    ax.set_xlabel("Blade Section")
    ax.set_ylabel(r"Lift coefficient $C_L$ at $\alpha_{opt}$ [—]")
    ax.set_title("Cascade CL Correction (Weinig) at Cruise Design Point", pad=8)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / "cascade_cl_correction.png")
    plt.close(fig)


def _fig_deviation_carter(cascade: List[CascadeResult], figures_dir: Path) -> None:
    """Ángulo de desviación de Carter δ por sección."""
    sections = [r.section for r in cascade]
    deltas   = [r.delta_carter_deg for r in cascade]
    solidities = [r.solidity for r in cascade]
    colors   = [SECTION_COLORS[s] for s in sections]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

    # Panel 1: barras δ por sección
    ax = axes[0]
    bars = ax.bar(range(len(sections)), deltas, color=colors, edgecolor="white",
                  linewidth=0.6, zorder=3)
    ax.bar_label(bars, fmt="%.2f°", padding=3, fontsize=9, fontweight="bold")
    ax.set_xticks(range(len(sections)))
    ax.set_xticklabels([s.replace("_", " ").title() for s in sections])
    ax.set_ylabel(r"Carter deviation angle $\delta$ [°]")
    ax.set_title("Carter's Rule — Flow Deviation per Section", pad=8)
    ax.set_xlabel("Blade Section")

    # Panel 2: δ vs σ con anotaciones
    ax2 = axes[1]
    sigma_range = np.linspace(0.1, 2.5, 200)
    delta_curve = 0.23 * 8.0 / np.sqrt(sigma_range)
    ax2.plot(sigma_range, delta_curve, "k--", lw=1.2, label=r"Carter: $\delta=0.23\theta/\sqrt{\sigma}$")
    for res in cascade:
        ax2.scatter(res.solidity, res.delta_carter_deg,
                    s=100, color=SECTION_COLORS[res.section],
                    zorder=5, edgecolors="white", linewidths=0.8,
                    label=res.section.replace("_", " ").title())
    ax2.set_xlabel(r"Solidity $\sigma$ [—]")
    ax2.set_ylabel(r"Deviation angle $\delta$ [°]")
    ax2.set_title("Deviation vs Solidity — Carter's Rule", pad=8)
    ax2.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(figures_dir / "deviation_angle_carter.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# B — Figuras de correcciones 3D Snel
# ---------------------------------------------------------------------------

def _fig_polars_2d_vs_3d_root(
    df_polars: pd.DataFrame,
    polar_3d_map: Dict[tuple, pd.DataFrame],
    figures_dir: Path,
) -> None:
    """Comparativa polar 2D vs 3D en root section (efecto máximo de Snel)."""
    cl_col = "cl_corrected" if "cl_corrected" in df_polars.columns else "cl"
    cd_col = "cd_corrected" if "cd_corrected" in df_polars.columns else "cd"

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    for condition in _CONDITIONS_ORDER:
        mask_2d = (df_polars["condition"] == condition) & (df_polars["section"] == "root")
        df_2d = df_polars[mask_2d].sort_values("alpha")
        df_3d = polar_3d_map.get((condition, "root"), pd.DataFrame())
        if df_2d.empty:
            continue

        ld_2d = df_2d[cl_col] / df_2d[cd_col].replace(0, float("nan"))
        color = _cond_colors().get(condition, "gray")

        axes[0].plot(df_2d["alpha"], ld_2d, "--", color=color,
                     lw=1.2, label=f"{condition.title()} 2D")
        if not df_3d.empty and "ld_3d" in df_3d.columns:
            axes[0].plot(df_3d["alpha"], df_3d["ld_3d"], "-", color=color,
                         lw=1.8, label=f"{condition.title()} 3D")
        if not df_3d.empty and "cl_3d" in df_3d.columns:
            axes[1].plot(df_3d["alpha"], df_3d["cl_3d"], "-", color=color,
                         lw=1.8, label=f"{condition.title()} 3D")
            axes[1].plot(df_2d["alpha"], df_2d[cl_col], "--", color=color,
                         lw=1.2, label=f"{condition.title()} 2D")

    axes[0].set_xlabel(r"$\alpha$ [°]")
    axes[0].set_ylabel(r"$C_L/C_D$ [—]")
    axes[0].set_title("Root Section — L/D: 2D vs 3D (Snel)", pad=8)
    axes[0].legend(fontsize=7, ncol=2)

    axes[1].set_xlabel(r"$\alpha$ [°]")
    axes[1].set_ylabel(r"$C_L$ [—]")
    axes[1].set_title("Root Section — CL: 2D vs 3D (Snel)", pad=8)
    axes[1].legend(fontsize=7, ncol=2)

    fig.tight_layout()
    fig.savefig(figures_dir / "polars_2d_vs_3d_root.png")
    plt.close(fig)


def _fig_snel_correction_spanwise(
    rot_results: List[RotationalCorrectionResult],
    figures_dir: Path,
) -> None:
    """ΔCL_snel vs (c/r)² — muestra la dependencia span-wise."""
    cruise_pts = [r for r in rot_results if r.condition == "cruise"]
    if not cruise_pts:
        cruise_pts = rot_results[:3]

    c_over_r_sq = [r.c_over_r ** 2 for r in cruise_pts]
    delta_cl    = [r.delta_cl_snel_at_opt for r in cruise_pts]
    sections    = [r.section for r in cruise_pts]

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    # Panel 1: scatter (c/r)² vs ΔCL
    ax = axes[0]
    cr_range = np.linspace(0, max(c_over_r_sq) * 1.3, 100)
    a = 3.0
    cl_typical = 0.8
    ax.plot(cr_range, a * cr_range * cl_typical, "k--", lw=1.2,
            label=r"Snel: $\Delta C_L = 3.0 \cdot (c/r)^2 \cdot C_L$")
    for pt in cruise_pts:
        ax.scatter(pt.c_over_r ** 2, pt.delta_cl_snel_at_opt,
                   s=120, color=SECTION_COLORS[pt.section], zorder=5,
                   edgecolors="white", linewidths=0.8,
                   label=pt.section.replace("_", " ").title())
        ax.annotate(
            f"{pt.cl_gain_pct:.1f}%",
            (pt.c_over_r ** 2, pt.delta_cl_snel_at_opt),
            xytext=(5, 5), textcoords="offset points", fontsize=8,
        )
    ax.set_xlabel(r"$(c/r)^2$ [—]")
    ax.set_ylabel(r"$\Delta C_L$ Snel [—]")
    ax.set_title("Rotational Lift Gain — Snel Correction", pad=8)
    ax.legend(fontsize=8)

    # Panel 2: ganancia porcentual por sección y condición
    ax2 = axes[1]
    all_sections = sorted(set(r.section for r in rot_results),
                          key=lambda s: ["root", "mid_span", "tip"].index(s))
    all_conds = _ordered_conditions(set(r.condition for r in rot_results))
    x = np.arange(len(all_sections))
    width = 0.2
    cc = _cond_colors()
    for i, cond in enumerate(all_conds):
        pts = {r.section: r.cl_gain_pct for r in rot_results if r.condition == cond}
        vals = [pts.get(s, 0.0) for s in all_sections]
        ax2.bar(x + i * width, vals, width, label=cond.title(),
                color=cc.get(cond, "gray"), edgecolor="white", linewidth=0.6, zorder=3)
    ax2.set_xticks(x + width * (len(all_conds) - 1) / 2)
    ax2.set_xticklabels([s.replace("_", " ").title() for s in all_sections])
    ax2.set_ylabel(r"$C_L$ gain [%]")
    ax2.set_title("Snel CL Gain by Section and Condition", pad=8)
    ax2.legend(fontsize=8)

    fig.tight_layout()
    fig.savefig(figures_dir / "snel_correction_spanwise.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# C — Figuras de twist y compromiso
# ---------------------------------------------------------------------------

def _fig_blade_twist_profile(
    twist_results: List[TwistDesignResult],
    figures_dir: Path,
) -> None:
    """β_metal(r) y φ_flow(r) en crucero — perfil de twist de diseño."""
    radii    = [r.radius_m for r in twist_results]
    betas    = [r.beta_metal_deg for r in twist_results]
    phis     = [r.phi_cruise_deg for r in twist_results]
    alphas   = [r.alpha_opt_3d_cruise for r in twist_results]
    sections = [r.section for r in twist_results]

    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    ax.plot(radii, betas, "s-", color="#1F78B4", lw=2.0, ms=9,
            label=r"$\beta_{metal}(r)$ — blade metal angle")
    ax.plot(radii, phis, "^--", color="#FF7F00", lw=1.5, ms=8,
            label=r"$\phi_{flow}(r)$ — cruise inflow angle")
    ax.plot(radii, alphas, "o:", color="#4DAC26", lw=1.5, ms=8,
            label=r"$\alpha_{opt,3D,cruise}(r)$")

    for i, (r, bm, sec) in enumerate(zip(radii, betas, sections)):
        ax.annotate(
            f"{sec.replace('_',' ').title()}\nβ={bm:.1f}°",
            (r, bm), xytext=(6, 4), textcoords="offset points", fontsize=8,
        )

    twist_total = betas[0] - betas[-1] if len(betas) >= 2 else 0.0
    ax.set_xlabel("Blade radius r [m]")
    ax.set_ylabel("Angle [°]")
    ax.set_title(
        f"Blade Twist Profile at Cruise Design Point\n"
        f"Total twist = {twist_total:.1f}°  (root − tip)",
        pad=8,
    )
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(figures_dir / "blade_twist_profile.png")
    plt.close(fig)


def _fig_off_design_heatmap(
    off_design: List[OffDesignIncidenceResult],
    figures_dir: Path,
) -> None:
    """Heatmap α_actual(sección × condición) con iso-líneas de α_opt_3D."""
    conds    = _ordered_conditions(set(r.condition for r in off_design))
    sections = [s for s in _SECTIONS if s in set(r.section for r in off_design)]

    alpha_actual = np.full((len(sections), len(conds)), float("nan"))
    alpha_opt    = np.full((len(sections), len(conds)), float("nan"))

    for r in off_design:
        if r.section in sections and r.condition in conds:
            si = sections.index(r.section)
            ci = conds.index(r.condition)
            alpha_actual[si, ci] = r.alpha_actual_deg
            alpha_opt[si, ci]    = r.alpha_opt_3d

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

    for ax, data, title, cmap in zip(
        axes,
        [alpha_actual, alpha_actual - alpha_opt],
        [r"$\alpha_{actual}$ [°]", r"Compromise $\Delta\alpha = \alpha_{actual} - \alpha_{opt,3D}$ [°]"],
        ["RdYlGn_r", "RdBu_r"],
    ):
        im = ax.imshow(data, aspect="auto", cmap=cmap)
        ax.set_xticks(range(len(conds)))
        ax.set_xticklabels([c.title() for c in conds])
        ax.set_yticks(range(len(sections)))
        ax.set_yticklabels([s.replace("_", " ").title() for s in sections])
        ax.set_title(title, pad=8)
        plt.colorbar(im, ax=ax)
        for si in range(len(sections)):
            for ci in range(len(conds)):
                v = data[si, ci]
                if not math.isnan(v):
                    ax.text(ci, si, f"{v:.1f}°", ha="center", va="center",
                            fontsize=9, fontweight="bold",
                            color="white" if abs(v) > np.nanstd(data) else "black")

    fig.suptitle("Off-Design Incidence Map — Single Actuator Pitch Compromise", fontweight="bold")
    fig.tight_layout()
    fig.savefig(figures_dir / "off_design_incidence_heatmap.png")
    plt.close(fig)


def _fig_pitch_compromise_loss(
    off_design: List[OffDesignIncidenceResult],
    figures_dir: Path,
) -> None:
    """Pérdida de eficiencia por sección × condición (excluye crucero)."""
    non_cruise = [r for r in off_design if r.condition != "cruise"]
    conds    = _ordered_conditions(set(r.condition for r in non_cruise))
    sections = [s for s in _SECTIONS if s in set(r.section for r in non_cruise)]

    x = np.arange(len(conds))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 5))

    for i, section in enumerate(sections):
        losses = []
        for cond in conds:
            row = next(
                (r for r in non_cruise if r.condition == cond and r.section == section), None
            )
            losses.append(row.efficiency_loss_pct if row and not math.isnan(row.efficiency_loss_pct) else 0.0)
        bars = ax.bar(
            x + i * width, losses, width,
            label=section.replace("_", " ").title(),
            color=SECTION_COLORS[section],
            edgecolor="white", linewidth=0.6, zorder=3,
        )
        ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8)

    ax.axhline(0, color="0.4", lw=0.8)
    ax.set_xticks(x + width * (len(sections) - 1) / 2)
    ax.set_xticklabels([c.title() for c in conds])
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel("Efficiency loss [%]")
    ax.set_title(
        "Pitch Compromise Efficiency Loss — Single Actuator vs Individual Optimum",
        pad=8,
    )
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / "pitch_compromise_loss.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# D — Figuras de carga de etapa
# ---------------------------------------------------------------------------

def _fig_phi_psi_map(
    loading: List[StageLoadingResult],
    figures_dir: Path,
) -> None:
    """Diagrama φ-ψ con puntos de operación y zona de diseño."""
    fig, ax = plt.subplots(figsize=(7.0, 6.0))

    # Zona de diseño
    ax.axvspan(0.35, 0.55, alpha=0.10, color="#4CAF50")
    ax.axhspan(0.25, 0.50, alpha=0.10, color="#4CAF50")
    ax.fill_betweenx([0.25, 0.50], 0.35, 0.55, alpha=0.18, color="#4CAF50",
                     label="Design zone (Dixon & Hall, 2013)")

    # Puntos de operación
    cmap = _cond_colors()
    for res in loading:
        if math.isnan(res.phi_coeff) or math.isnan(res.psi_loading):
            continue
        color = SECTION_COLORS.get(res.section, "gray")
        marker = {"takeoff": "o", "climb": "s", "cruise": "^", "descent": "D"}.get(res.condition, "o")
        ax.scatter(res.phi_coeff, res.psi_loading,
                   s=120, color=color, marker=marker,
                   edgecolors="white", linewidths=0.8, zorder=5)
        ax.annotate(
            f"{res.condition[:2].title()}/{res.section[:3]}",
            (res.phi_coeff, res.psi_loading),
            xytext=(5, 4), textcoords="offset points", fontsize=7,
        )

    # Leyendas manuales
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=SECTION_COLORS["root"],
               markersize=9, label="Root"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=SECTION_COLORS["mid_span"],
               markersize=9, label="Mid span"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=SECTION_COLORS["tip"],
               markersize=9, label="Tip"),
        Line2D([0], [0], color="#4CAF50", lw=8, alpha=0.35, label="Design zone"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8)
    ax.set_xlabel(r"Flow coefficient $\phi = V_a/U$ [—]")
    ax.set_ylabel(r"Work coefficient $\psi = \Delta V_\theta/U$ [—]")
    ax.set_title("Stage Loading Map — VPF Operating Points\n"
                 r"(Dixon & Hall, 2013 — high-bypass fan design zone)", pad=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "phi_psi_operating_map.png")
    plt.close(fig)


def _fig_work_distribution(
    loading: List[StageLoadingResult],
    figures_dir: Path,
) -> None:
    """W_spec [kJ/kg] por sección × condición."""
    conds    = _ordered_conditions(set(r.condition for r in loading))
    sections = [s for s in _SECTIONS if s in set(r.section for r in loading)]
    x        = np.arange(len(conds))
    width    = 0.25

    fig, ax = plt.subplots(figsize=(8, 5))
    for i, section in enumerate(sections):
        vals = []
        for cond in conds:
            row = next((r for r in loading if r.condition == cond and r.section == section), None)
            vals.append(row.w_specific_kj_kg if row and not math.isnan(row.w_specific_kj_kg) else 0.0)
        bars = ax.bar(x + i * width, vals, width,
                      label=section.replace("_", " ").title(),
                      color=SECTION_COLORS[section],
                      edgecolor="white", linewidth=0.6, zorder=3)
        ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=8)

    ax.set_xticks(x + width * (len(sections) - 1) / 2)
    ax.set_xticklabels([c.title() for c in conds])
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"Specific work $W = U \cdot \Delta V_\theta$ [kJ/kg]")
    ax.set_title("Stage Specific Work Distribution (Euler Equation)", pad=8)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / "work_distribution.png")
    plt.close(fig)


def _fig_loading_profile_spanwise(
    loading: List[StageLoadingResult],
    figures_dir: Path,
) -> None:
    """ψ(r) en crucero vs takeoff vs climb — perfil radial de carga."""
    radii_map = {"root": 0.20, "mid_span": 0.42, "tip": 0.65}
    conds_to_plot = [c for c in ["cruise", "climb", "takeoff"] if c in set(r.condition for r in loading)]

    fig, ax = plt.subplots(figsize=(6.5, 5.0))
    cc = _cond_colors()
    for cond in conds_to_plot:
        pts = sorted(
            [r for r in loading if r.condition == cond],
            key=lambda r: radii_map.get(r.section, 0),
        )
        radii = [radii_map[r.section] for r in pts]
        psis  = [r.psi_loading for r in pts]
        ax.plot(radii, psis, "o-", color=cc.get(cond, "gray"),
                lw=2.0, ms=8, label=cond.title())

    ax.axhspan(0.25, 0.50, alpha=0.10, color="#4CAF50", label="Design zone")
    ax.set_xlabel("Blade radius r [m]")
    ax.set_ylabel(r"Work coefficient $\psi$ [—]")
    ax.set_title("Spanwise Loading Profile — VPF vs Design Zone", pad=8)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / "loading_profile_spanwise.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figuras heredadas (actualizadas con α_opt_3D)
# ---------------------------------------------------------------------------

def _fig_efficiency_curves(
    df_polars: pd.DataFrame,
    polar_3d_map: Dict[tuple, pd.DataFrame],
    alpha_opt_3d_map: Dict[tuple, float],
    cl_cd_max_3d_map: Dict[tuple, float],
    figures_dir: Path,
) -> None:
    """CL_3D/CD vs α con α_opt_3D marcado, una figura por condición."""
    for condition in _ordered_conditions(df_polars["condition"].unique()):
        fig, ax = plt.subplots(figsize=(7.5, 5.0))
        for section in _SECTIONS:
            df_3d = polar_3d_map.get((condition, section), pd.DataFrame())
            if df_3d.empty or "ld_3d" not in df_3d.columns:
                continue
            color = SECTION_COLORS[section]
            ax.plot(df_3d["alpha"], df_3d["ld_3d"],
                    color=color, label=section.replace("_", " ").title(), zorder=3)
            alpha_opt = alpha_opt_3d_map.get((condition, section), float("nan"))
            ld_max    = cl_cd_max_3d_map.get((condition, section), float("nan"))
            if not math.isnan(alpha_opt) and not math.isnan(ld_max):
                ax.plot(alpha_opt, ld_max, marker="*", color=color,
                        markersize=13, markeredgecolor="white", markeredgewidth=0.6,
                        zorder=5, linestyle="none")

        ax.set_xlabel(r"Angle of attack $\alpha$ [°]")
        ax.set_ylabel(r"$C_{L,3D}/C_D$ [—]")
        ax.set_title(f"3D-Corrected Efficiency Curves — {condition.title()}", pad=8)
        ax.legend(loc="lower right")
        fig.tight_layout()
        fig.savefig(figures_dir / f"efficiency_curves_{condition}.png")
        plt.close(fig)


def _fig_alpha_opt_2d_vs_3d(
    rot_results: List[RotationalCorrectionResult],
    figures_dir: Path,
) -> None:
    """α_opt_2D vs α_opt_3D por caso — muestra la ganancia de las correcciones."""
    conds    = _ordered_conditions(set(r.condition for r in rot_results))
    sections = [s for s in _SECTIONS if s in set(r.section for r in rot_results)]
    x = np.arange(len(conds))
    width = 0.12

    fig, ax = plt.subplots(figsize=(10, 5))
    for i, section in enumerate(sections):
        alpha_2d = [
            next((r.alpha_opt_2d for r in rot_results if r.condition == c and r.section == section), float("nan"))
            for c in conds
        ]
        alpha_3d = [
            next((r.alpha_opt_3d for r in rot_results if r.condition == c and r.section == section), float("nan"))
            for c in conds
        ]
        offset = (i - len(sections)/2 + 0.5) * width * 2
        ax.bar(x + offset - width/2, alpha_2d, width,
               color=SECTION_COLORS[section], alpha=0.5,
               edgecolor="white", linewidth=0.5, zorder=3,
               label=f"{section.replace('_',' ').title()} 2D" if i == 0 else "")
        ax.bar(x + offset + width/2, alpha_3d, width,
               color=SECTION_COLORS[section],
               edgecolor="white", linewidth=0.5, zorder=3,
               label=f"{section.replace('_',' ').title()} 3D" if i == 0 else "")

    from matplotlib.patches import Patch
    handles = []
    for sec in sections:
        handles.append(Patch(facecolor=SECTION_COLORS[sec],
                             label=sec.replace("_", " ").title()))
    handles += [
        Patch(facecolor="gray", alpha=0.5, label="2D (compressibility corrected)"),
        Patch(facecolor="gray", label="3D (cascade + Snel corrected)"),
    ]
    ax.legend(handles=handles, fontsize=8, ncol=2)
    ax.set_xticks(x)
    ax.set_xticklabels([c.title() for c in conds])
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"$\alpha_{opt}$ [°]")
    ax.set_title(r"$\alpha_{opt}$ Comparison: 2D vs 3D Corrected", pad=8)
    fig.tight_layout()
    fig.savefig(figures_dir / "alpha_opt_2d_vs_3d.png")
    plt.close(fig)


def _fig_kinematics_comparison(
    df: pd.DataFrame,
    figures_dir: Path,
) -> None:
    """Panel triple: Δα_3D aerodinámico vs Δβ_mech_3D por sección."""
    conditions = _ordered_conditions(df["condition"].unique())
    sections   = [s for s in _SECTIONS if s in df["section"].unique()]

    fig, axes = plt.subplots(1, len(sections), figsize=(5 * len(sections), 5), sharey=True)
    if len(sections) == 1:
        axes = [axes]
    x = np.arange(len(conditions))
    width = 0.35

    for i, section in enumerate(sections):
        ax = axes[i]
        df_sec = df[df["section"] == section]

        val_aero = [
            df_sec[df_sec["condition"] == c]["delta_alpha_aero_deg"].values[0]
            if len(df_sec[df_sec["condition"] == c]) > 0 else 0.0
            for c in conditions
        ]
        val_mech = [
            df_sec[df_sec["condition"] == c]["delta_beta_mech_deg"].values[0]
            if len(df_sec[df_sec["condition"] == c]) > 0 else 0.0
            for c in conditions
        ]

        ax.bar(x - width/2, val_aero, width,
               label=r"Aerodynamic ($\Delta\alpha_{3D}$)", color="#9ECAE1", edgecolor="white")
        ax.bar(x + width/2, val_mech, width,
               label=r"Mechanical ($\Delta\beta_{mech}$)", color="#3182BD", edgecolor="white")
        ax.axhline(0, color="0.3", linestyle="--", linewidth=0.8)
        ax.set_title(f"Section: {section.replace('_', ' ').title()}")
        ax.set_xticks(x)
        ax.set_xticklabels([c.title() for c in conditions])
        if i == 0:
            ax.set_ylabel("Adjustment Angle [°]")
            ax.legend(loc="lower right", fontsize=8)

    fig.suptitle(
        "Aerodynamic (3D) vs Mechanical Pitch Adjustment — Velocity Triangles",
        fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(figures_dir / "kinematics_comparison.png", dpi=300)
    plt.close(fig)


def _fig_alpha_opt_by_condition(
    rot_results: List[RotationalCorrectionResult],
    figures_dir: Path,
) -> None:
    """α_opt_3D por condición y sección (barras agrupadas)."""
    conds = _ordered_conditions(set(r.condition for r in rot_results))
    x = np.arange(len(conds))
    width = 0.25
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    for i, section in enumerate(_SECTIONS):
        vals = [
            next((r.alpha_opt_3d for r in rot_results if r.condition == c and r.section == section),
                 float("nan"))
            for c in conds
        ]
        bars = ax.bar(x + i * width, vals, width,
                      label=section.replace("_", " ").title(),
                      color=SECTION_COLORS[section],
                      edgecolor="white", linewidth=0.6, zorder=3)
        ax.bar_label(bars, fmt="%.1f°", padding=3, fontsize=8)
    ax.set_xticks(x + width)
    ax.set_xticklabels([c.title() for c in conds])
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"$\alpha_{opt,3D}$ [°]")
    ax.set_title("3D-Corrected Optimal Angle of Attack by Condition", pad=8)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / "alpha_opt_by_condition.png")
    plt.close(fig)


def _fig_pitch_adjustment(
    pitch_adjustments,
    figures_dir: Path,
) -> None:
    """Δα_3D relativo a crucero por condición y sección."""
    conds = _ordered_conditions(set(p.condition for p in pitch_adjustments))
    x = np.arange(len(conds))
    width = 0.25
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    for i, section in enumerate(_SECTIONS):
        vals = [
            next((p.delta_pitch for p in pitch_adjustments
                  if p.condition == c and p.section == section), float("nan"))
            for c in conds
        ]
        bars = ax.bar(x + i * width, vals, width,
                      label=section.replace("_", " ").title(),
                      color=SECTION_COLORS[section],
                      edgecolor="white", linewidth=0.6, zorder=3)
        ax.bar_label(bars, fmt="%.2f°", padding=3, fontsize=8)
    ax.axhline(0, color="0.35", linestyle="--", linewidth=0.9)
    ax.set_xticks(x + width)
    ax.set_xticklabels([c.title() for c in conds])
    ax.set_xlabel("Flight Condition")
    ax.set_ylabel(r"Required pitch adjustment $\Delta\alpha_{3D}$ [°]")
    ax.set_title("Required Pitch Adjustment Relative to Cruise (3D Corrected)", pad=8)
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures_dir / "pitch_adjustment.png")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Escritura de tablas
# ---------------------------------------------------------------------------

def _write_cascade_table(cascade: List[CascadeResult], path: Path) -> None:
    rows = [
        {
            "section":           r.section,
            "radius_m":          r.radius_m,
            "chord_m":           r.chord_m,
            "blade_spacing_m":   r.blade_spacing_m,
            "solidity":          r.solidity,
            "K_weinig":          r.k_weinig,
            "delta_carter_deg":  r.delta_carter_deg,
            "CL_2D_at_alpha_opt": r.cl_2d_at_alpha_opt,
            "CL_cascade_at_alpha_opt": r.cl_cascade_at_alpha_opt,
        }
        for r in cascade
    ]
    pd.DataFrame(rows).to_csv(path, index=False, float_format="%.6f")


def _write_rotational_table(rot: List[RotationalCorrectionResult], path: Path) -> None:
    rows = [
        {
            "condition":          r.condition,
            "section":            r.section,
            "radius_m":           r.radius_m,
            "chord_m":            r.chord_m,
            "c_over_r":           r.c_over_r,
            "snel_factor":        r.snel_factor,
            "alpha_opt_2D_deg":   r.alpha_opt_2d,
            "CL_CD_max_2D":       r.cl_cd_max_2d,
            "alpha_opt_3D_deg":   r.alpha_opt_3d,
            "CL_CD_max_3D":       r.cl_cd_max_3d,
            "delta_CL_snel":      r.delta_cl_snel_at_opt,
            "CL_gain_pct":        r.cl_gain_pct,
        }
        for r in rot
    ]
    pd.DataFrame(rows).sort_values(["condition", "section"]).to_csv(
        path, index=False, float_format="%.6f"
    )


def _write_twist_table(twist: List[TwistDesignResult], path: Path) -> None:
    rows = [
        {
            "section":               r.section,
            "radius_m":              r.radius_m,
            "U_cruise_m_s":          r.u_cruise_m_s,
            "phi_cruise_deg":        r.phi_cruise_deg,
            "alpha_opt_3D_cruise_deg": r.alpha_opt_3d_cruise,
            "beta_metal_deg":        r.beta_metal_deg,
            "twist_from_tip_deg":    r.twist_from_tip_deg,
        }
        for r in twist
    ]
    pd.DataFrame(rows).to_csv(path, index=False, float_format="%.6f")


def _write_off_design_table(od: List[OffDesignIncidenceResult], path: Path) -> None:
    rows = [
        {
            "condition":                   r.condition,
            "section":                     r.section,
            "Va_m_s":                      r.va_m_s,
            "U_m_s":                       r.u_m_s,
            "phi_flow_deg":                r.phi_flow_deg,
            "delta_beta_hub_deg":          r.delta_beta_hub_deg,
            "alpha_opt_3D_deg":            r.alpha_opt_3d,
            "alpha_actual_deg":            r.alpha_actual_deg,
            "delta_alpha_compromise_deg":  r.delta_alpha_compromise_deg,
            "CL_CD_max_3D":                r.cl_cd_max_3d,
            "CL_CD_actual":                r.cl_cd_actual,
            "efficiency_loss_pct":         r.efficiency_loss_pct,
        }
        for r in od
    ]
    pd.DataFrame(rows).sort_values(["condition", "section"]).to_csv(
        path, index=False, float_format="%.6f"
    )


def _write_stage_loading_table(loading: List[StageLoadingResult], path: Path) -> None:
    rows = [
        {
            "condition":         r.condition,
            "section":           r.section,
            "Va_m_s":            r.va_m_s,
            "U_m_s":             r.u_m_s,
            "alpha_opt_3D_deg":  r.alpha_opt_3d_deg,
            "beta_mech_deg":     r.beta_mech_deg,
            "phi_flow_deg":      r.phi_flow_deg,
            "phi_coeff":         r.phi_coeff,
            "V_theta_m_s":       r.v_theta_m_s,
            "psi_loading":       r.psi_loading,
            "W_specific_kJ_kg":  r.w_specific_kj_kg,
            "in_design_zone":    r.in_design_zone,
        }
        for r in loading
    ]
    pd.DataFrame(rows).sort_values(["condition", "section"]).to_csv(
        path, index=False, float_format="%.6f"
    )


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------

def run_pitch_kinematics() -> None:
    """Ejecuta el Stage 5 completo: análisis aerodinámico riguroso del VPF."""
    LOGGER.info("=" * 70)
    LOGGER.info("STAGE 5: Pitch & Kinematics Analysis (Cascade + Snel + Twist + Loading)")
    LOGGER.info("=" * 70)

    output_dirs     = get_output_dirs()
    polars_dir      = output_dirs["polars"]
    comp_dir        = output_dirs["compressibility"]
    stage5_dir      = base_config.get_stage_dir(5)
    tables_dir      = stage5_dir / "tables"
    figures_dir     = stage5_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    engine_config = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"

    # ── 1. Cargar datos ──────────────────────────────────────────────────────
    LOGGER.info("Cargando datos aerodinámicos...")
    loader       = FilesystemDataLoader()
    df_polars    = loader.load_polar_data(polars_dir)
    df_corrected = loader.load_compressibility_data(comp_dir)

    if df_polars.empty:
        LOGGER.warning("Sin datos de polares — omitiendo Stage 5.")
        return

    # Preferir polares corregidos por compresibilidad si están disponibles
    df_work = df_corrected if not df_corrected.empty else df_polars
    LOGGER.info("Polares de trabajo: %d filas", len(df_work))

    # ── 2. Geometría ─────────────────────────────────────────────────────────
    blade_geom   = get_blade_geometry()
    radii        = get_blade_radii()
    axial_vels   = get_axial_velocities()
    rpm          = get_fan_rpm()
    omega        = rpm * (2.0 * math.pi / 60.0)

    # ── 3. [A] Correcciones de cascada ───────────────────────────────────────
    LOGGER.info("[A] Calculando correcciones de cascada (Weinig + Carter)...")

    # α_opt_2D en crucero para referencia de cascada (se obtiene de la búsqueda simple)
    from vfp_analysis.stage5_pitch_kinematics.core.services.optimal_incidence_service import (
        compute_all_optimal_incidences,
    )
    opt_2d_all = compute_all_optimal_incidences(df_polars, df_corrected)
    alpha_opt_cruise_2d = {
        r.section: r.alpha_opt
        for r in opt_2d_all if r.condition == "cruise"
    }
    alpha_opt_2d_map  = {(r.condition, r.section): r.alpha_opt  for r in opt_2d_all}
    cl_cd_max_2d_map  = {(r.condition, r.section): r.cl_cd_max  for r in opt_2d_all}

    cascade_results = compute_cascade_corrections(
        blade_geom, alpha_opt_cruise_2d, df_work,
    )
    LOGGER.info("Cascada calculada: %d secciones", len(cascade_results))

    # Aplicar Weinig a los polares de trabajo
    k_weinig_by_section = {r.section: r.k_weinig for r in cascade_results}
    cl_col_work = "cl_corrected" if "cl_corrected" in df_work.columns else "cl"

    df_cascade_list = []
    for section, df_sec in df_work.groupby("section"):
        k = k_weinig_by_section.get(section, 1.0)
        df_cascade_list.append(apply_weinig_to_polar(df_sec.copy(), k, cl_col_work))
    df_cascade = pd.concat(df_cascade_list, ignore_index=True)

    # ── 4. [B] Correcciones rotacionales 3D (Snel) ───────────────────────────
    LOGGER.info("[B] Calculando correcciones rotacionales 3D (Snel)...")
    rot_results = compute_rotational_corrections(
        df_cascade, blade_geom, alpha_opt_2d_map, cl_cd_max_2d_map,
    )
    polar_3d_map = build_3d_polar_map(df_cascade, blade_geom)
    LOGGER.info("Correcciones 3D calculadas: %d casos", len(rot_results))

    # ── 5. Incidencia óptima 3D ──────────────────────────────────────────────
    LOGGER.info("Calculando incidencias óptimas 3D...")
    alpha_opt_3d_map = {(r.condition, r.section): r.alpha_opt_3d for r in rot_results}
    cl_cd_max_3d_map = {(r.condition, r.section): r.cl_cd_max_3d for r in rot_results}

    # Construir OptimalIncidence con α_opt_3D para el pipeline existente
    from vfp_analysis.stage5_pitch_kinematics.core.domain.pitch_kinematics_result import (
        OptimalIncidence,
    )
    from vfp_analysis.config_loader import get_reynolds_table, get_target_mach

    reynolds_table = get_reynolds_table()
    mach_table     = get_target_mach()
    optimal_incidences = [
        OptimalIncidence(
            condition=r.condition,
            section=r.section,
            reynolds=reynolds_table.get(r.condition, {}).get(r.section, 0.0),
            mach=mach_table.get(r.condition, 0.0),
            alpha_opt=r.alpha_opt_3d,
            cl_cd_max=r.cl_cd_max_3d,
        )
        for r in rot_results
        if not math.isnan(r.alpha_opt_3d)
    ]
    LOGGER.info("Incidencias 3D: %d casos", len(optimal_incidences))

    # ── 6. Ajuste de paso ────────────────────────────────────────────────────
    LOGGER.info("Calculando ajustes de paso (Δα_3D relativo a crucero)...")
    from vfp_analysis.stage5_pitch_kinematics.core.services.pitch_adjustment_service import (
        compute_pitch_adjustments,
    )
    pitch_adjustments = compute_pitch_adjustments(optimal_incidences, reference_condition="cruise")
    LOGGER.info("Ajustes calculados: %d casos", len(pitch_adjustments))

    # ── 7. Cinemática (triángulos de velocidad con Va explícita) ─────────────
    LOGGER.info("Resolviendo triángulos de velocidad...")
    kinematics_results = compute_kinematics(pitch_adjustments, engine_config)
    LOGGER.info("Cinemática resuelta: %d casos", len(kinematics_results))

    # ── 8. [C] Twist de diseño + compromiso off-design ───────────────────────
    LOGGER.info("[C] Calculando twist de diseño y compromiso off-design...")
    alpha_opt_3d_cruise = {
        s: alpha_opt_3d_map.get(("cruise", s), float("nan"))
        for s in radii.keys()
    }
    va_cruise = axial_vels.get("cruise", 250.0)

    twist_results = compute_blade_twist(alpha_opt_3d_cruise, va_cruise, omega, radii)
    off_design_results = compute_off_design_incidence(
        twist_results,
        alpha_opt_3d_map,
        cl_cd_max_3d_map,
        polar_3d_map,
        axial_vels,
        omega,
        radii,
    )
    LOGGER.info("Twist + off-design: %d casos", len(off_design_results))

    # ── 9. [D] Carga de etapa ────────────────────────────────────────────────
    LOGGER.info("[D] Calculando carga de etapa (Euler: φ, ψ, W_spec)...")
    loading_results = compute_stage_loading(alpha_opt_3d_map, axial_vels, omega, radii)
    in_zone = sum(1 for r in loading_results if r.in_design_zone)
    LOGGER.info("Carga de etapa: %d casos, %d en zona de diseño", len(loading_results), in_zone)

    # ── 10. Figuras ──────────────────────────────────────────────────────────
    LOGGER.info("Generando figuras...")

    # Cascada
    _fig_cascade_solidity(cascade_results, figures_dir)
    _fig_cascade_cl_correction(cascade_results, figures_dir)
    _fig_deviation_carter(cascade_results, figures_dir)

    # Snel
    _fig_polars_2d_vs_3d_root(df_work, polar_3d_map, figures_dir)
    _fig_snel_correction_spanwise(rot_results, figures_dir)

    # Twist + off-design
    _fig_blade_twist_profile(twist_results, figures_dir)
    _fig_off_design_heatmap(off_design_results, figures_dir)
    _fig_pitch_compromise_loss(off_design_results, figures_dir)

    # Carga de etapa
    _fig_phi_psi_map(loading_results, figures_dir)
    _fig_work_distribution(loading_results, figures_dir)
    _fig_loading_profile_spanwise(loading_results, figures_dir)

    # Heredadas / actualizadas
    _fig_efficiency_curves(df_work, polar_3d_map, alpha_opt_3d_map, cl_cd_max_3d_map, figures_dir)
    _fig_alpha_opt_2d_vs_3d(rot_results, figures_dir)
    _fig_alpha_opt_by_condition(rot_results, figures_dir)
    _fig_pitch_adjustment(pitch_adjustments, figures_dir)

    # Cinemática
    kin_rows = [
        {
            "condition":            r.condition,
            "section":              r.section,
            "delta_alpha_aero_deg": next(
                (a.delta_pitch for a in pitch_adjustments
                 if a.condition == r.condition and a.section == r.section), float("nan"),
            ),
            "delta_beta_mech_deg":  r.delta_beta_mech_deg,
        }
        for r in kinematics_results
    ]
    _fig_kinematics_comparison(pd.DataFrame(kin_rows), figures_dir)

    LOGGER.info("Figuras generadas en: %s", figures_dir)

    # ── 11. Tablas ───────────────────────────────────────────────────────────
    LOGGER.info("Escribiendo tablas CSV...")
    _write_cascade_table(cascade_results, tables_dir / "cascade_corrections.csv")
    _write_rotational_table(rot_results,  tables_dir / "rotational_corrections.csv")
    _write_twist_table(twist_results,     tables_dir / "blade_twist_design.csv")
    _write_off_design_table(off_design_results, tables_dir / "off_design_incidence.csv")
    _write_stage_loading_table(loading_results, tables_dir / "stage_loading.csv")

    writer = FilesystemPitchKinematicsWriter()
    writer.write_optimal_incidence_table(
        optimal_incidences, tables_dir / "optimal_incidence.csv",
    )
    writer.write_pitch_adjustment_table(
        pitch_adjustments, tables_dir / "pitch_adjustment.csv",
    )
    writer.write_kinematics_table(
        kinematics_results, pitch_adjustments,
        tables_dir / "kinematics_analysis.csv",
    )

    # ── 12. Resúmenes ────────────────────────────────────────────────────────
    twist_total = (
        twist_results[0].twist_from_tip_deg
        if twist_results and not math.isnan(twist_results[0].twist_from_tip_deg)
        else float("nan")
    )
    avg_loss = (
        sum(r.efficiency_loss_pct for r in off_design_results
            if r.condition != "cruise" and not math.isnan(r.efficiency_loss_pct))
        / max(1, sum(1 for r in off_design_results
                     if r.condition != "cruise" and not math.isnan(r.efficiency_loss_pct)))
    )
    summary_lines = [
        "Stage 5: Rigorous aerodynamic analysis of the Variable Pitch Fan.",
        "",
        f"[A] Cascade (Weinig + Carter):",
        f"    Solidity range: {min(r.solidity for r in cascade_results):.2f} (tip) "
        f"– {max(r.solidity for r in cascade_results):.2f} (root)",
        f"    Carter deviation: {cascade_results[-1].delta_carter_deg:.2f}° (tip) "
        f"– {cascade_results[0].delta_carter_deg:.2f}° (root)",
        "",
        f"[B] Rotational corrections (Snel):",
        f"    Root (c/r)² = {cascade_results[0].chord_m / cascade_results[0].radius_m:.3f}² → "
        f"CL gain ≈ +{3.0 * (cascade_results[0].chord_m / cascade_results[0].radius_m)**2 * 100:.1f}%",
        "",
        f"[C] Blade twist design:",
        f"    Total twist: {twist_total:.1f}°  (root − tip)",
        f"    Average pitch compromise loss (off-design): {avg_loss:.2f}%",
        "",
        f"[D] Stage loading (Euler equation):",
        f"    Points in design zone: {in_zone}/{len(loading_results)}",
        "",
        f"Tables:  {tables_dir}",
        f"Figures: {figures_dir}",
    ]
    writer.write_text_summary(
        "\n".join(summary_lines),
        stage5_dir / "pitch_kinematics_summary.txt",
    )

    from vfp_analysis.postprocessing.stage_summary_generator import (
        generate_stage5_summary,
        write_stage_summary,
    )
    write_stage_summary(5, generate_stage5_summary(stage5_dir), stage5_dir)
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
