"""
Application script for running the intermediate Kinematics stage.

This stage takes the aerodynamic optimal pitch adjustments from Stage 6
and translates them into physical mechanical pitch commands by solving
the velocity triangles for each flight condition and blade section.
"""

from __future__ import annotations

import logging
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from vfp_analysis import config as base_config
from vfp_analysis.config_loader import get_output_dirs
from vfp_analysis.postprocessing.figure_generator import SECTION_COLORS
from vfp_analysis.vpf_analysis.core.domain.optimal_incidence import PitchAdjustment
from vfp_analysis.kinematics_analysis.core.services.kinematics_service import compute_kinematics

LOGGER = logging.getLogger(__name__)


def run_kinematics_stage() -> None:
    """Execute the intermediate Stage 7: Kinematic velocity triangles."""
    LOGGER.info("=" * 70)
    LOGGER.info("STAGE 7: Kinematic Velocity Triangles & Mechanical Pitch")
    LOGGER.info("=" * 70)

    stage7_dir = base_config.RESULTS_DIR / "stage_7"
    tables_dir = stage7_dir / "tables"
    figures_dir = stage7_dir / "figures"
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load VPF stage 6 data
    try:
        stage4_tables = base_config.RESULTS_DIR / "stage_4" / "tables"
        vpf_df = pd.read_csv(stage4_tables / "vpf_pitch_adjustment.csv")
    except FileNotFoundError:
        LOGGER.error("VPF Pitch Adjustment CSV not found. Run Stage 6 first.")
        return

    adjustments = []
    for _, row in vpf_df.iterrows():
        adjustments.append(
            PitchAdjustment(
                condition=row["condition"],
                section=row["section"],
                alpha_opt=row.get("alpha_opt", 0.0),
                delta_pitch=row["delta_pitch"],
            )
        )

    # 2. Compute kinematics
    engine_config = base_config.ROOT_DIR / "config" / "engine_parameters.yaml"
    kinematics_results = compute_kinematics(adjustments, engine_config)

    # 3. Export Tables
    rows = []
    for r in kinematics_results:
        rows.append({
            "condition": r.condition,
            "section": r.section,
            "axial_velocity_m_s": r.axial_velocity,
            "tangential_velocity_m_s": r.tangential_velocity,
            "inflow_angle_phi_deg": r.inflow_angle_deg,
            "alpha_aero_deg": r.alpha_aero_deg,
            "beta_mech_deg": r.beta_mech_deg,
            "delta_alpha_aero_deg": next(a.delta_pitch for a in adjustments if a.condition == r.condition and a.section == r.section),
            "delta_beta_mech_deg": r.delta_beta_mech_deg,
        })
    
    df_out = pd.DataFrame(rows)
    df_out.to_csv(tables_dir / "kinematics_analysis.csv", index=False, float_format="%.4f")

    # 4. Generate comparison figure
    _plot_kinematics_comparison(df_out, figures_dir)
    
    # 5. Summary
    from vfp_analysis.postprocessing.stage_summary_generator import write_stage_summary
    
    lines = [
        "Kinematics Analysis solves velocity triangles (V_ax, U) to compute actual mechanical pitch.",
        "delta_beta_mech = delta_alpha_aero + delta_phi",
        "",
        f"Cases solved: {len(kinematics_results)}",
        f"Tables output: {tables_dir / 'kinematics_analysis.csv'}",
        f"Figures output: {figures_dir}",
    ]
    write_stage_summary(7, "\n".join(lines), stage7_dir)

    LOGGER.info("Stage 7 completed successfully.")
    LOGGER.info("=" * 70)


def _plot_kinematics_comparison(df: pd.DataFrame, figures_dir: Path) -> None:
    """Plot aerodynamic delta vs required mechanical delta."""
    conditions = df["condition"].unique()
    sections = df["section"].unique()
    
    fig, axes = plt.subplots(1, 3, figsize=(14, 5), sharey=True)
    x = np.arange(len(conditions))
    width = 0.35
    
    for i, section in enumerate(sections):
        ax = axes[i]
        df_sec = df[df["section"] == section]
        
        # Ensure correct order
        ordered_cond = [c for c in ["takeoff", "climb", "cruise", "descent"] if c in conditions]
        
        val_aero = [df_sec[df_sec["condition"] == c]["delta_alpha_aero_deg"].values[0] for c in ordered_cond]
        val_mech = [df_sec[df_sec["condition"] == c]["delta_beta_mech_deg"].values[0] for c in ordered_cond]
        
        bars_aero = ax.bar(x - width/2, val_aero, width, label=r"Aerodynamic ($\Delta\alpha$)", color="#9ECAE1", edgecolor="white")
        bars_mech = ax.bar(x + width/2, val_mech, width, label=r"Mechanical ($\Delta\beta$)", color="#3182BD", edgecolor="white")
        
        ax.axhline(0, color="0.3", linestyle="--", linewidth=0.8)
        
        ax.set_title(f"Section: {section.replace('_', ' ').title()}")
        ax.set_xticks(x)
        ax.set_xticklabels([c.title() for c in ordered_cond])
        
        if i == 0:
            ax.set_ylabel("Adjustment Angle [°]")
            ax.legend(loc="lower right")
            
    fig.suptitle("Aerodynamic vs Required Mechanical Pitch Adjustment (Kinematic Velocity Triangles)", fontweight="bold")
    fig.tight_layout()
    fig.savefig(figures_dir / "kinematics_comparison.png", dpi=300)
    plt.close(fig)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_kinematics_stage()
