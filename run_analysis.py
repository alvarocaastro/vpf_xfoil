"""
run_analysis.py
---------------
Punto de entrada del pipeline aerodinámica completo del análisis VPF.

Ejecuta 7 pasos en secuencia:

  1. Limpiar resultados anteriores
  2. Stage 1 — Selección de perfil aerodinámico
  3. Stage 2 — Simulaciones XFOIL (12 polares + mapa de paso)
  4. Stage 3 — Correcciones de compresibilidad (PG + K-T + wave drag)
  5. Stage 4 — Métricas de rendimiento + figuras de publicación
  6. Stage 5 — Análisis de paso e incidencia + cinemática (fusión Stage 6 + Stage 7)
  7. Stage 6 — Análisis de consumo específico de combustible (SFC)

Uso:
    python run_analysis.py
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import pandas as pd

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vfp_analysis import config as base_config
from vfp_analysis.adapters.xfoil.xfoil_runner_adapter import XfoilRunnerAdapter
from vfp_analysis.config_loader import (
    get_airfoil_thickness_ratio,
    get_alpha_range,
    get_axial_velocities,
    get_blade_radii,
    get_blade_sections,
    get_fan_rpm,
    get_flight_conditions,
    get_korn_kappa,
    get_ncrit_table,
    get_output_dirs,
    get_reynolds_table,
    get_selection_alpha_range,
    get_selection_ncrit,
    get_selection_reynolds,
    get_target_mach,
)
from vfp_analysis.core.domain.airfoil import Airfoil
from vfp_analysis.core.domain.blade_section import BladeSection
from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.postprocessing.stage_summary_generator import (
    generate_stage1_summary,
    generate_stage2_summary,
    generate_stage3_summary,
    generate_stage4_summary,
    write_stage_summary,
)
from vfp_analysis.stage1_airfoil_selection.airfoil_selection_service import (
    AirfoilSelectionService,
)
from vfp_analysis.stage2_xfoil_simulations.final_analysis_service import (
    FinalAnalysisService,
    FinalSimulationConfig,
)
from vfp_analysis.stage2_xfoil_simulations.pitch_map import (
    compute_pitch_map,
    plot_alpha_opt_evolution,
    plot_pitch_map,
    plot_vpf_clcd_penalty,
    plot_vpf_efficiency_by_section,
    save_pitch_map_csv,
)
from vfp_analysis.stage2_xfoil_simulations.polar_organizer import organize_polars
from vfp_analysis.stage3_compressibility_correction.compressibility_case import (
    CompressibilityCase,
)
from vfp_analysis.stage3_compressibility_correction.correction_service import (
    CompressibilityCorrectionService,
)
from vfp_analysis.stage3_compressibility_correction.karman_tsien import KarmanTsienModel
from vfp_analysis.stage3_compressibility_correction.prandtl_glauert import PrandtlGlauertModel
from vfp_analysis.stage4_performance_metrics.metrics import (
    compute_all_metrics,
    enrich_with_cruise_reference,
)
from vfp_analysis.stage4_performance_metrics.plots import generate_stage4_figures
from vfp_analysis.stage4_performance_metrics.publication_figures import generate_all_figures
from vfp_analysis.stage4_performance_metrics.table_generator import (
    export_clcd_max_table,
    export_summary_table,
)
from vfp_analysis.stage5_pitch_kinematics.application.run_pitch_kinematics import (
    run_pitch_kinematics,
)
from vfp_analysis.stage6_sfc_analysis.application.run_sfc_analysis import run_sfc_analysis

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Paso 1
# ---------------------------------------------------------------------------

def step_1_clean_results() -> None:
    """Limpia los resultados de ejecuciones anteriores."""
    LOGGER.info("=" * 60)
    LOGGER.info("PASO 1: Limpiando resultados anteriores")
    LOGGER.info("=" * 60)

    for stage_num in sorted(base_config.STAGE_DIR_NAMES):
        stage_dir = base_config.get_stage_dir(stage_num)
        if stage_dir.exists():
            LOGGER.info("Eliminando: %s", stage_dir)
            shutil.rmtree(stage_dir, ignore_errors=True)
        stage_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Limpieza completada.")


# ---------------------------------------------------------------------------
# Paso 2 — Stage 1
# ---------------------------------------------------------------------------

def step_2_airfoil_selection() -> Airfoil:
    """Stage 1: Selección automática de perfil aerodinámico."""
    LOGGER.info("=" * 60)
    LOGGER.info("PASO 2 / STAGE 1: Selección de perfil aerodinámico")
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

    airfoils = []
    for spec in base_config.AIRFOILS:
        dat_path = base_config.AIRFOIL_DATA_DIR / spec["dat_file"]
        if dat_path.is_file():
            airfoils.append(Airfoil(name=spec["name"], family=spec["family"], dat_path=dat_path))

    LOGGER.info("Perfiles candidatos: %d", len(airfoils))
    xfoil   = XfoilRunnerAdapter()
    service = AirfoilSelectionService(xfoil_runner=xfoil, results_dir=stage1_dir)
    result  = service.run_selection(airfoils, selection_condition)
    LOGGER.info("Perfil seleccionado: %s", result.best_airfoil.name)

    summary_text = generate_stage1_summary(stage1_dir, result.best_airfoil.name)
    write_stage_summary(1, summary_text, stage1_dir)

    return result.best_airfoil


# ---------------------------------------------------------------------------
# Paso 3 — Stage 2
# ---------------------------------------------------------------------------

def step_3_xfoil_simulations(selected_airfoil: Airfoil) -> Path:
    """Stage 2: Simulaciones XFOIL del perfil seleccionado."""
    LOGGER.info("=" * 60)
    LOGGER.info("PASO 3 / STAGE 2: Simulaciones XFOIL")
    LOGGER.info("=" * 60)

    stage2_dir      = base_config.get_stage_dir(2)
    stage2_dir.mkdir(parents=True, exist_ok=True)

    flight_conditions = get_flight_conditions()
    blade_sections    = get_blade_sections()
    reynolds_table    = get_reynolds_table()
    ncrit_table       = get_ncrit_table()
    alpha_range       = get_alpha_range()

    sections = [BladeSection(name=s, reynolds=0.0) for s in blade_sections]

    configs = []
    for flight in flight_conditions:
        for section in sections:
            cond = SimulationCondition(
                name=f"{flight}_{section.name}",
                mach_rel=0.2,
                reynolds=reynolds_table[flight][section.name],
                alpha_min=alpha_range["min"],
                alpha_max=alpha_range["max"],
                alpha_step=alpha_range["step"],
                ncrit=ncrit_table[flight],
            )
            configs.append(FinalSimulationConfig(
                flight_name=flight, section=section, condition=cond,
            ))

    LOGGER.info("Ejecutando %d simulaciones XFOIL...", len(configs))
    runner  = XfoilRunnerAdapter()
    service = FinalAnalysisService(runner, stage2_dir)
    alpha_eff_map, stall_map = service.run(selected_airfoil, configs)

    # Aplanar polares en polars/
    source_polars = stage2_dir / "simulation_plots"
    target_polars = stage2_dir / "polars"
    organize_polars(source_polars, target_polars, flight_conditions, blade_sections)

    # Mapa de paso (triángulos de velocidad preliminares) → pitch_map/
    rpm  = get_fan_rpm()
    radii = get_blade_radii()
    axial_velocities = get_axial_velocities()

    pitch_map_dir = stage2_dir / "pitch_map"
    pitch_map_dir.mkdir(parents=True, exist_ok=True)

    plot_alpha_opt_evolution(alpha_eff_map, configs, pitch_map_dir)
    pitch_df, delta_beta = compute_pitch_map(alpha_eff_map, rpm, radii, axial_velocities)
    save_pitch_map_csv(pitch_df, pitch_map_dir)
    plot_pitch_map(pitch_df, delta_beta, pitch_map_dir)

    LOGGER.info(
        "Rango Δβ por sección: %s",
        ", ".join(f"{s}={v:.1f}°" for s, v in delta_beta.items()),
    )

    # Figuras de argumento VPF
    polar_dfs = {}
    for flight in flight_conditions:
        for section in blade_sections:
            csv_path = source_polars / flight / section / "polar.csv"
            if csv_path.exists():
                polar_dfs[(flight, section)] = pd.read_csv(csv_path)

    plot_vpf_efficiency_by_section(polar_dfs, alpha_eff_map, pitch_map_dir)
    plot_vpf_clcd_penalty(polar_dfs, alpha_eff_map, pitch_map_dir)

    summary_text = generate_stage2_summary(
        stage2_dir, len(configs),
        delta_beta=delta_beta,
        alpha_eff_map=alpha_eff_map,
        stall_map=stall_map,
    )
    write_stage_summary(2, summary_text, stage2_dir)

    return source_polars


# ---------------------------------------------------------------------------
# Paso 4 — Stage 3
# ---------------------------------------------------------------------------

def step_4_compressibility_correction(source_polars: Path) -> None:
    """Stage 3: Correcciones de compresibilidad (PG + Kármán-Tsien + wave drag)."""
    LOGGER.info("=" * 60)
    LOGGER.info("PASO 4 / STAGE 3: Correcciones de compresibilidad")
    LOGGER.info("=" * 60)

    stage3_dir = base_config.get_stage_dir(3)
    stage3_dir.mkdir(parents=True, exist_ok=True)

    flight_conditions = get_flight_conditions()
    blade_sections    = get_blade_sections()
    target_mach       = get_target_mach()
    tc                = get_airfoil_thickness_ratio()
    kappa             = get_korn_kappa()

    pg_model = PrandtlGlauertModel()
    kt_model = KarmanTsienModel(thickness_ratio=tc, korn_kappa=kappa)
    service  = CompressibilityCorrectionService(
        pg_model=pg_model, kt_model=kt_model, base_output_dir=stage3_dir,
    )

    for flight in flight_conditions:
        mach = target_mach[flight]
        case = CompressibilityCase(
            flight_condition=flight, target_mach=mach, reference_mach=0.2,
        )
        for section in blade_sections:
            polar_path = source_polars / flight.lower() / section / "polar.csv"
            if not polar_path.exists():
                LOGGER.warning("Polar no encontrado: %s", polar_path)
                continue
            LOGGER.info("Corrigiendo %s/%s (M=%.2f)", flight, section, mach)
            try:
                service.correct_case(case, polar_path, section)
            except Exception as e:
                LOGGER.warning("Error en %s/%s: %s", flight, section, e)

    service.plot_section_summary(stage3_dir, flight_conditions, blade_sections)

    summary_text = generate_stage3_summary(stage3_dir)
    write_stage_summary(3, summary_text, stage3_dir)


# ---------------------------------------------------------------------------
# Paso 5 — Stage 4
# ---------------------------------------------------------------------------

def step_5_metrics_and_figures() -> list:
    """Stage 4: Métricas de rendimiento + figuras de publicación."""
    LOGGER.info("=" * 60)
    LOGGER.info("PASO 5 / STAGE 4: Métricas de rendimiento + figuras")
    LOGGER.info("=" * 60)

    stage2_dir = base_config.get_stage_dir(2)
    stage3_dir = base_config.get_stage_dir(3)
    polars_dir = stage3_dir if stage3_dir.exists() else stage2_dir / "simulation_plots"
    LOGGER.info("Leyendo polares desde: %s", polars_dir)

    flight_conditions = get_flight_conditions()
    blade_sections    = get_blade_sections()
    reynolds_table    = get_reynolds_table()
    ncrit_table       = get_ncrit_table()

    metrics = compute_all_metrics(
        polars_dir, flight_conditions, blade_sections, reynolds_table, ncrit_table,
    )
    metrics = enrich_with_cruise_reference(metrics, polars_dir)
    LOGGER.info("Métricas calculadas: %d casos", len(metrics))

    stage4_dir  = base_config.get_stage_dir(4)
    output_dirs = get_output_dirs()
    tables_dir  = output_dirs["tables"]

    export_summary_table(metrics, tables_dir / "summary_table.csv")
    export_clcd_max_table(metrics, tables_dir / "clcd_max_by_section.csv")

    # Figuras analíticas de Stage 4
    figures_dir = stage4_dir / "figures"
    generate_stage4_figures(metrics, figures_dir, polars_dir=polars_dir)

    # Figuras de publicación (antes Stage 5)
    pub_figures_dir = output_dirs["figures"]  # stage4/figures/publication
    generate_all_figures(
        polars_dir=output_dirs["polars"],
        figures_dir=pub_figures_dir,
        metrics=metrics,
        flight_conditions=flight_conditions,
        blade_sections=blade_sections,
        stage3_dir=stage3_dir,
        reynolds_table=reynolds_table,
    )
    LOGGER.info("Figuras de publicación generadas en: %s", pub_figures_dir)

    summary_text = generate_stage4_summary(stage4_dir, metrics)
    write_stage_summary(4, summary_text, stage4_dir)

    return metrics


# ---------------------------------------------------------------------------
# Paso 6 — Stage 5
# ---------------------------------------------------------------------------

def step_6_pitch_kinematics() -> None:
    """Stage 5: Análisis de paso óptimo, ajuste aerodinámico y cinemática."""
    LOGGER.info("=" * 60)
    LOGGER.info("PASO 6 / STAGE 5: Pitch & Kinematics Analysis")
    LOGGER.info("=" * 60)
    run_pitch_kinematics()


# ---------------------------------------------------------------------------
# Paso 7 — Stage 6
# ---------------------------------------------------------------------------

def step_7_sfc_analysis() -> None:
    """Stage 6: Análisis de consumo específico de combustible (SFC)."""
    LOGGER.info("=" * 60)
    LOGGER.info("PASO 7 / STAGE 6: SFC Impact Analysis")
    LOGGER.info("=" * 60)
    run_sfc_analysis()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Ejecuta el pipeline completo de análisis aerodinámico."""
    LOGGER.info("=" * 60)
    LOGGER.info("Pipeline VPF — Análisis Aerodinámico Completo")
    LOGGER.info("=" * 60)

    try:
        step_1_clean_results()
        selected_airfoil  = step_2_airfoil_selection()
        source_polars     = step_3_xfoil_simulations(selected_airfoil)
        step_4_compressibility_correction(source_polars)
        step_5_metrics_and_figures()
        step_6_pitch_kinematics()
        step_7_sfc_analysis()

        LOGGER.info("=" * 80)
        LOGGER.info("Pipeline completado con éxito.")
        LOGGER.info("Resultados disponibles en:")
        for stage_num, stage_name in base_config.STAGE_DIR_NAMES.items():
            LOGGER.info("  Stage %d: %s", stage_num, base_config.RESULTS_DIR / stage_name)
        LOGGER.info("=" * 80)

    except Exception as exc:
        LOGGER.error("El pipeline falló: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
