"""
Main entrypoint for the complete aerodynamic analysis pipeline.

This script executes the full reproducible scientific pipeline:

1) Clean previous results
2) Run airfoil selection stage
3) Run XFOIL aerodynamic simulations
4) Apply compressibility corrections
5) Compute aerodynamic performance metrics
6) Export summary tables
7) Generate plots and figures
8) Variable Pitch Fan analysis
9) Specific Fuel Consumption Impact analysis

Usage:
    python run_analysis.py
"""

from __future__ import annotations

import logging

import pandas as pd
import shutil
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vfp_analysis import config as base_config
from vfp_analysis.adapters.xfoil.xfoil_runner_adapter import XfoilRunnerAdapter
from vfp_analysis.stage3_compressibility_correction.adapters.correction_models.prandtl_glauert_model import (
    PrandtlGlauertModel,
)
from vfp_analysis.stage3_compressibility_correction.adapters.correction_models.karman_tsien_model import (
    KarmanTsienModel,
)
from vfp_analysis.stage3_compressibility_correction.core.domain.compressibility_case import (
    CompressibilityCase,
)
from vfp_analysis.stage3_compressibility_correction.core.services.compressibility_correction_service import (
    CompressibilityCorrectionService,
)
from vfp_analysis.config_loader import (
    get_alpha_range,
    get_axial_velocities,
    get_blade_radii,
    get_blade_sections,
    get_fan_rpm,
    get_flight_conditions,
    get_ncrit_table,
    get_output_dirs,
    get_reynolds_table,
    get_selection_alpha_range,
    get_selection_ncrit,
    get_selection_reynolds,
    get_airfoil_thickness_ratio,
    get_korn_kappa,
    get_target_mach,
)
from vfp_analysis.core.domain.airfoil import Airfoil
from vfp_analysis.core.domain.blade_section import BladeSection
from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.stage1_airfoil_selection.airfoil_selection_service import (
    AirfoilSelectionService,
)
from vfp_analysis.stage2_xfoil_simulations.final_analysis_service import (
    FinalAnalysisService,
    FinalSimulationConfig,
)
from vfp_analysis.stage5_publication_figures.figure_generator import generate_all_figures
from vfp_analysis.stage4_performance_metrics.metrics import compute_all_metrics
from vfp_analysis.stage2_xfoil_simulations.polar_organizer import organize_polars
from vfp_analysis.stage2_xfoil_simulations.pitch_map import (
    compute_pitch_map,
    plot_alpha_opt_evolution,
    plot_pitch_map,
    plot_vpf_clcd_penalty,
    plot_vpf_efficiency_by_section,
    save_pitch_map_csv,
)
from vfp_analysis.postprocessing.stage_summary_generator import (
    generate_stage1_summary,
    generate_stage2_summary,
    generate_stage3_summary,
    generate_stage4_summary,
    generate_stage5_summary,
    generate_stage6_summary,
    generate_stage7_summary,
    write_stage_summary,
)
from vfp_analysis.stage4_performance_metrics.table_generator import (
    export_clcd_max_table,
    export_summary_table,
)
from vfp_analysis.stage6_vpf_analysis.application.run_vpf_analysis import run_vpf_analysis
from vfp_analysis.stage7_kinematics_analysis.application.run_kinematics_stage import run_kinematics_stage
from vfp_analysis.stage8_sfc_analysis.application.run_sfc_analysis import run_sfc_analysis

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

LOGGER = logging.getLogger(__name__)


def step_1_clean_results() -> None:
    """Step 1: Clean previous results."""
    LOGGER.info("=" * 60)
    LOGGER.info("STEP 1: Cleaning previous results")
    LOGGER.info("=" * 60)

    # Clean all stage directories (stages 1–8)
    for stage_num in sorted(base_config.STAGE_DIR_NAMES):
        stage_dir = base_config.get_stage_dir(stage_num)
        if stage_dir.exists():
            LOGGER.info(f"Removing: {stage_dir}")
            shutil.rmtree(stage_dir, ignore_errors=True)
        stage_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Cleanup completed.")


def step_2_airfoil_selection() -> Airfoil:
    """Step 2: Automated airfoil selection."""
    LOGGER.info("=" * 60)
    LOGGER.info("STEP 2: Automated airfoil selection")
    LOGGER.info("=" * 60)

    stage1_dir = base_config.get_stage_dir(1)
    stage1_dir.mkdir(parents=True, exist_ok=True)

    alpha_range = get_selection_alpha_range()

    selection_condition = SimulationCondition(
        name="Selection",
        mach_rel=0.2,
        reynolds=get_selection_reynolds(),
        alpha_min=alpha_range["min"],
        alpha_max=alpha_range["max"],
        alpha_step=alpha_range["step"],
        ncrit=get_selection_ncrit(),
    )

    # Build airfoils from data directory
    airfoils = []
    for spec in base_config.AIRFOILS:
        dat_path = base_config.AIRFOIL_DATA_DIR / spec["dat_file"]
        if dat_path.is_file():
            airfoils.append(
                Airfoil(
                    name=spec["name"],
                    family=spec["family"],
                    dat_path=dat_path,
                )
            )

    LOGGER.info(f"Found {len(airfoils)} airfoils to compare")

    xfoil = XfoilRunnerAdapter()
    service = AirfoilSelectionService(xfoil_runner=xfoil, results_dir=stage1_dir)
    result = service.run_selection(airfoils, selection_condition)

    LOGGER.info(f"Selected airfoil: {result.best_airfoil.name}")
    
    # Generate Stage 1 summary
    summary_text = generate_stage1_summary(stage1_dir, result.best_airfoil.name)
    write_stage_summary(1, summary_text, stage1_dir)
    LOGGER.info(f"Stage 1 summary written to: {stage1_dir / 'finalresults_stage1.txt'}")
    
    return result.best_airfoil


def step_3_xfoil_simulations(selected_airfoil: Airfoil) -> Path:
    """Step 3: Run final XFOIL simulations."""
    LOGGER.info("=" * 60)
    LOGGER.info("STEP 3: Running XFOIL aerodynamic simulations")
    LOGGER.info("=" * 60)

    stage2_dir = base_config.get_stage_dir(2)
    stage2_dir.mkdir(parents=True, exist_ok=True)

    flight_conditions = get_flight_conditions()
    blade_sections = get_blade_sections()
    reynolds_table = get_reynolds_table()
    ncrit_table = get_ncrit_table()
    alpha_range = get_alpha_range()

    sections = [
        BladeSection(name=section, reynolds=0.0) for section in blade_sections
    ]

    configs = []
    for flight in flight_conditions:
        for section in sections:
            re_value = reynolds_table[flight][section.name]
            ncrit_value = ncrit_table[flight]
            cond = SimulationCondition(
                name=f"{flight}_{section.name}",
                mach_rel=0.2,
                reynolds=re_value,
                alpha_min=alpha_range["min"],
                alpha_max=alpha_range["max"],
                alpha_step=alpha_range["step"],
                ncrit=ncrit_value,
            )
            configs.append(
                FinalSimulationConfig(
                    flight_name=flight,
                    section=section,
                    condition=cond,
                )
            )

    LOGGER.info(f"Running {len(configs)} XFOIL simulations...")

    runner = XfoilRunnerAdapter()
    service = FinalAnalysisService(runner, stage2_dir)
    alpha_eff_map, stall_map = service.run(selected_airfoil, configs)

    LOGGER.info("XFOIL simulations completed.")

    # Polars are in the Stage 2 simulation_plots folder; flatten them into polars/.
    source_polars = stage2_dir / "simulation_plots"
    target_polars = stage2_dir / "polars"

    organize_polars(source_polars, target_polars, flight_conditions, blade_sections)
    LOGGER.info(f"Polar data organized in: {target_polars}")

    # Post-processing: alpha_opt evolution sweep and velocity triangle pitch map
    rpm = get_fan_rpm()
    radii = get_blade_radii()
    axial_velocities = get_axial_velocities()

    # All VPF post-processing outputs go into vpf_analysis/
    vpf_analysis_dir = stage2_dir / "vpf_analysis"
    vpf_analysis_dir.mkdir(parents=True, exist_ok=True)

    plot_alpha_opt_evolution(alpha_eff_map, configs, vpf_analysis_dir)
    LOGGER.info("alpha_opt evolution plot saved.")

    pitch_df, delta_beta = compute_pitch_map(alpha_eff_map, rpm, radii, axial_velocities)
    save_pitch_map_csv(pitch_df, vpf_analysis_dir)
    plot_pitch_map(pitch_df, delta_beta, vpf_analysis_dir)
    LOGGER.info(
        "Blade pitch map computed. Delta-beta per section: "
        + ", ".join(f"{s}={v:.1f}°" for s, v in delta_beta.items())
    )

    # VPF argument plots: load polar CSVs and generate comparison figures
    polar_dfs = {}
    for flight in flight_conditions:
        for section in blade_sections:
            csv_path = stage2_dir / "simulation_plots" / flight / section / "polar.csv"
            if csv_path.exists():
                polar_dfs[(flight, section)] = pd.read_csv(csv_path)

    plot_vpf_efficiency_by_section(polar_dfs, alpha_eff_map, vpf_analysis_dir)
    plot_vpf_clcd_penalty(polar_dfs, alpha_eff_map, vpf_analysis_dir)
    LOGGER.info("VPF comparison plots saved.")

    # Generate Stage 2 summary
    num_simulations = len(configs)
    summary_text = generate_stage2_summary(
        stage2_dir, num_simulations,
        delta_beta=delta_beta,
        alpha_eff_map=alpha_eff_map,
        stall_map=stall_map,
    )
    write_stage_summary(2, summary_text, stage2_dir)
    LOGGER.info(f"Stage 2 summary written to: {stage2_dir / 'finalresults_stage2.txt'}")

    return source_polars


def step_4_compressibility_correction(source_polars: Path) -> None:
    """Step 4: Apply compressibility corrections."""
    LOGGER.info("=" * 60)
    LOGGER.info("STEP 4: Applying compressibility corrections")
    LOGGER.info("=" * 60)

    stage3_dir = base_config.get_stage_dir(3)
    stage3_dir.mkdir(parents=True, exist_ok=True)

    flight_conditions = get_flight_conditions()
    blade_sections = get_blade_sections()
    target_mach = get_target_mach()

    tc    = get_airfoil_thickness_ratio()
    kappa = get_korn_kappa()

    pg_model = PrandtlGlauertModel()
    kt_model = KarmanTsienModel(thickness_ratio=tc, korn_kappa=kappa)
    service  = CompressibilityCorrectionService(
        pg_model=pg_model,
        kt_model=kt_model,
        base_output_dir=stage3_dir,
    )

    for flight in flight_conditions:
        mach = target_mach[flight]
        case = CompressibilityCase(
            flight_condition=flight,
            target_mach=mach,
            reference_mach=0.2,
        )

        for section in blade_sections:
            polar_path = source_polars / flight.lower() / section / "polar.csv"
            if not polar_path.exists():
                LOGGER.warning(f"Polar not found: {polar_path}")
                continue

            LOGGER.info(f"Correcting {flight}/{section} (M={mach:.2f})  [PG + K-T]")
            try:
                service.correct_case(case, polar_path, section)
            except Exception as e:
                LOGGER.warning(f"Failed to correct {flight}/{section}: {e}")
                continue

    LOGGER.info("Compressibility corrections completed (PG + Kármán-Tsien + wave drag).")

    # Summary comparison plots: one per section, all flight conditions overlaid
    service.plot_section_summary(stage3_dir, flight_conditions, blade_sections)
    LOGGER.info("Section summary plots saved.")
    
    # Generate Stage 3 summary
    summary_text = generate_stage3_summary(stage3_dir)
    write_stage_summary(3, summary_text, stage3_dir)
    LOGGER.info(f"Stage 3 summary written to: {stage3_dir / 'finalresults_stage3.txt'}")


def step_5_compute_metrics() -> list:
    """Step 5: Compute aerodynamic performance metrics."""
    LOGGER.info("=" * 60)
    LOGGER.info("STEP 5: Computing aerodynamic performance metrics")
    LOGGER.info("=" * 60)

    stage2_dir = base_config.get_stage_dir(2)
    polars_dir = stage2_dir / "simulation_plots"
    flight_conditions = get_flight_conditions()
    blade_sections = get_blade_sections()
    reynolds_table = get_reynolds_table()
    ncrit_table = get_ncrit_table()

    metrics = compute_all_metrics(
        polars_dir, flight_conditions, blade_sections, reynolds_table, ncrit_table
    )

    LOGGER.info(f"Computed metrics for {len(metrics)} cases")
    
    # Generate Stage 4 summary
    stage4_dir = base_config.get_stage_dir(4)
    summary_text = generate_stage4_summary(stage4_dir, metrics)
    write_stage_summary(4, summary_text, stage4_dir)
    LOGGER.info(f"Stage 4 summary written to: {stage4_dir / 'finalresults_stage4.txt'}")
    
    return metrics


def step_6_export_tables(metrics: list) -> None:
    """Step 6: Export summary tables."""
    LOGGER.info("=" * 60)
    LOGGER.info("STEP 6: Exporting summary tables")
    LOGGER.info("=" * 60)

    output_dirs = get_output_dirs()
    tables_dir = output_dirs["tables"]

    # summary_table.csv — comprehensive table with all metrics
    export_summary_table(metrics, tables_dir / "summary_table.csv")
    # clcd_max_by_section.csv — CL, CD at optimum (complementary detail)
    export_clcd_max_table(metrics, tables_dir / "clcd_max_by_section.csv")

    LOGGER.info(f"Tables exported to: {tables_dir}")


def step_7_generate_figures(metrics: list) -> None:
    """Step 7: Generate all figures for thesis."""
    LOGGER.info("=" * 60)
    LOGGER.info("STEP 7: Generating publication-quality figures")
    LOGGER.info("=" * 60)

    output_dirs = get_output_dirs()
    figures_dir = output_dirs["figures"]
    polars_dir = output_dirs["polars"]
    flight_conditions = get_flight_conditions()
    blade_sections = get_blade_sections()
    reynolds_table = get_reynolds_table()
    stage3_dir = base_config.get_stage_dir(3)

    generate_all_figures(
        polars_dir, figures_dir, metrics, flight_conditions, blade_sections,
        stage3_dir=stage3_dir,
        reynolds_table=reynolds_table,
    )

    LOGGER.info(f"All figures generated in: {figures_dir}")
    
    # Generate Stage 5 summary
    stage5_dir = base_config.get_stage_dir(5)
    summary_text = generate_stage5_summary(stage5_dir)
    write_stage_summary(5, summary_text, stage5_dir)
    LOGGER.info(f"Stage 5 summary written to: {stage5_dir / 'finalresults_stage5.txt'}")


def step_8_vpf_analysis() -> None:
    """Step 8: Variable Pitch Fan aerodynamic analysis."""
    LOGGER.info("=" * 60)
    LOGGER.info("STEP 8: Variable Pitch Fan Aerodynamic Analysis")
    LOGGER.info("=" * 60)

    run_vpf_analysis()


def step_9_kinematics_analysis() -> None:
    """Step 9: Kinematic Velocity Triangles & Mechanical Pitch."""
    run_kinematics_stage()


def step_10_sfc_analysis() -> None:
    """Step 10: Specific Fuel Consumption Impact analysis."""
    LOGGER.info("=" * 60)
    LOGGER.info("STEP 10: Specific Fuel Consumption (SFC) Impact Analysis")
    LOGGER.info("=" * 60)

    run_sfc_analysis()


def main() -> None:
    """Execute the complete aerodynamic analysis pipeline."""
    LOGGER.info("=" * 60)
    LOGGER.info("Starting Complete Aerodynamic Analysis Pipeline")
    LOGGER.info("=" * 60)

    try:
        # Step 1: Clean previous results
        step_1_clean_results()

        # Step 2: Airfoil selection
        selected_airfoil = step_2_airfoil_selection()

        # Step 3: XFOIL simulations
        source_polars = step_3_xfoil_simulations(selected_airfoil)

        # Step 4: Compressibility corrections
        step_4_compressibility_correction(source_polars)

        # Step 5: Compute metrics
        metrics = step_5_compute_metrics()

        # Step 6: Export tables
        step_6_export_tables(metrics)

        # Step 7: Generate figures
        step_7_generate_figures(metrics)

        # Step 8: Variable Pitch Fan analysis
        step_8_vpf_analysis()

        # Step 9: Kinematic analysis (Velocity Triangles)
        step_9_kinematics_analysis()

        # Step 10: SFC impact analysis
        step_10_sfc_analysis()

        LOGGER.info("=" * 80)
        LOGGER.info("Pipeline completed successfully!")
        LOGGER.info("=" * 60)
        LOGGER.info("Results available in:")
        for stage_num, stage_name in base_config.STAGE_DIR_NAMES.items():
            LOGGER.info(f"  Stage {stage_num}: {base_config.RESULTS_DIR / stage_name}")
        LOGGER.info("=" * 80)

    except Exception as e:
        LOGGER.error(f"Pipeline failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
