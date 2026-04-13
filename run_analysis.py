"""
run_analysis.py
---------------
Punto de entrada del pipeline aerodinámico completo del análisis VPF.

Ejecuta 7 pasos en secuencia con I/O explícito entre stages:

  1. Limpiar resultados anteriores
  2. Stage 1 — Selección de perfil aerodinámico  → Stage1Result
  3. Stage 2 — Simulaciones XFOIL (12 polares)   → Stage2Result
  4. Stage 3 — Correcciones de compresibilidad   → Stage3Result
  5. Stage 4 — Métricas de rendimiento + figuras → Stage4Result
  6. Stage 5 — Pitch & Kinematics (3D completo)  → Stage5Result
  7. Stage 6 — Análisis SFC                      → Stage6Result

Cada step valida sus outputs antes de pasar al siguiente, garantizando
que ningún stage se ejecuta con datos incompletos o inconsistentes.

Uso:
    python run_analysis.py
"""

from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import pandas as pd

# Añadir src al path antes de cualquier import del paquete
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vfp_analysis import config as base_config
from vfp_analysis.adapters.xfoil.xfoil_runner_adapter import XfoilRunnerAdapter
from vfp_analysis.core.domain.airfoil import Airfoil
from vfp_analysis.core.domain.blade_section import BladeSection
from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.pipeline.contracts import (
    Stage1Result,
    Stage2Result,
    Stage3Result,
    Stage4Result,
    Stage5Result,
    Stage6Result,
)
from vfp_analysis.postprocessing.stage_summary_generator import (
    generate_stage1_summary,
    generate_stage2_summary,
    generate_stage3_summary,
    generate_stage4_summary,
    write_stage_summary,
)
from vfp_analysis.settings import get_settings
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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOGGER = logging.getLogger(__name__)

_SEPARATOR = "=" * 60


def _section(title: str) -> None:
    LOGGER.info(_SEPARATOR)
    LOGGER.info(title)
    LOGGER.info(_SEPARATOR)


# ---------------------------------------------------------------------------
# Paso 1 — Limpieza
# ---------------------------------------------------------------------------

def step_1_clean_results() -> None:
    """Elimina resultados de ejecuciones anteriores para partir de cero."""
    _section("PASO 1: Limpiando resultados anteriores")

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

def step_2_airfoil_selection() -> Stage1Result:
    """Stage 1: Selección automática de perfil aerodinámico.

    Returns
    -------
    Stage1Result
        Perfil seleccionado, rutas de salida y directorio del stage.
    """
    _section("PASO 2 / STAGE 1: Selección de perfil aerodinámico")

    cfg = get_settings()
    stage1_dir = base_config.get_stage_dir(1)
    stage1_dir.mkdir(parents=True, exist_ok=True)

    selection_condition = SimulationCondition(
        name="Selection",
        mach_rel=cfg.reference_mach,
        reynolds=cfg.selection_reynolds,
        alpha_min=cfg.selection_alpha_min,
        alpha_max=cfg.selection_alpha_max,
        alpha_step=cfg.selection_alpha_step,
        ncrit=cfg.selection_ncrit,
    )

    airfoils = []
    for spec in base_config.AIRFOILS:
        dat_path = base_config.AIRFOIL_DATA_DIR / spec["dat_file"]
        if dat_path.is_file():
            airfoils.append(
                Airfoil(name=spec["name"], family=spec["family"], dat_path=dat_path)
            )

    if not airfoils:
        raise RuntimeError(
            f"No se encontraron ficheros .dat en {base_config.AIRFOIL_DATA_DIR}. "
            "Verifica que la carpeta data/airfoils/ contiene los perfiles."
        )

    LOGGER.info("Candidatos encontrados: %d perfiles", len(airfoils))

    xfoil = XfoilRunnerAdapter(final_analysis=False)
    service = AirfoilSelectionService(xfoil_runner=xfoil, results_dir=stage1_dir)
    result = service.run_selection(airfoils, selection_condition)

    LOGGER.info("Perfil seleccionado: %s", result.best_airfoil.name)

    summary_text = generate_stage1_summary(stage1_dir, result.best_airfoil.name)
    write_stage_summary(1, summary_text, stage1_dir)

    s1 = Stage1Result(
        selected_airfoil_name=result.best_airfoil.name,
        selected_airfoil_dat=result.best_airfoil.dat_path,
        stage_dir=stage1_dir,
        selection_dir=stage1_dir / "airfoil_selection",
    )
    s1.validate()
    return s1


# ---------------------------------------------------------------------------
# Paso 3 — Stage 2
# ---------------------------------------------------------------------------

def step_3_xfoil_simulations(s1: Stage1Result) -> Stage2Result:
    """Stage 2: Simulaciones XFOIL del perfil seleccionado.

    Parameters
    ----------
    s1 : Stage1Result
        Resultado del stage anterior (perfil seleccionado).

    Returns
    -------
    Stage2Result
        Directorio de polares, mapa de alpha óptimo y estadísticas.
    """
    _section("PASO 3 / STAGE 2: Simulaciones XFOIL")

    cfg = get_settings()
    stage2_dir = base_config.get_stage_dir(2)
    stage2_dir.mkdir(parents=True, exist_ok=True)

    sections = [BladeSection(name=s, reynolds=0.0) for s in cfg.blade_sections]

    configs = []
    for flight in cfg.flight_conditions:
        for section in sections:
            cond = SimulationCondition(
                name=f"{flight}_{section.name}",
                mach_rel=cfg.reference_mach,
                reynolds=cfg.reynolds_table[flight][section.name],
                alpha_min=cfg.alpha_min,
                alpha_max=cfg.alpha_max,
                alpha_step=cfg.alpha_step,
                ncrit=cfg.ncrit_table[flight],
            )
            configs.append(
                FinalSimulationConfig(flight_name=flight, section=section, condition=cond)
            )

    LOGGER.info(
        "Ejecutando %d simulaciones XFOIL para %s...",
        len(configs),
        s1.selected_airfoil_name,
    )

    airfoil = Airfoil(
        name=s1.selected_airfoil_name,
        family="",
        dat_path=s1.selected_airfoil_dat,
    )

    runner = XfoilRunnerAdapter(final_analysis=True)
    service = FinalAnalysisService(runner, stage2_dir)
    alpha_eff_map, stall_map = service.run(airfoil, configs)

    n_conv_warnings = getattr(service, "_total_convergence_warnings", 0)

    # Organizar polares en estructura plana
    source_polars = stage2_dir / "simulation_plots"
    target_polars = stage2_dir / "polars"
    organize_polars(
        source_polars, target_polars, cfg.flight_conditions, cfg.blade_sections
    )

    # Mapa de paso (cinemática preliminar de Stage 2)
    pitch_map_dir = stage2_dir / "pitch_map"
    pitch_map_dir.mkdir(parents=True, exist_ok=True)

    plot_alpha_opt_evolution(alpha_eff_map, configs, pitch_map_dir)
    pitch_df, delta_beta = compute_pitch_map(
        alpha_eff_map,
        cfg.fan.rpm,
        cfg.fan.radii_m,
        cfg.fan.axial_velocity_m_s,
    )
    save_pitch_map_csv(pitch_df, pitch_map_dir)
    plot_pitch_map(pitch_df, delta_beta, pitch_map_dir)

    LOGGER.info(
        "Δβ por sección: %s",
        ", ".join(f"{s}={v:.1f}°" for s, v in delta_beta.items()),
    )

    # Figuras de argumento VPF
    polar_dfs = {}
    for flight in cfg.flight_conditions:
        for section in cfg.blade_sections:
            csv_path = source_polars / flight / section / "polar.csv"
            if csv_path.exists():
                polar_dfs[(flight, section)] = pd.read_csv(csv_path)

    plot_vpf_efficiency_by_section(polar_dfs, alpha_eff_map, pitch_map_dir)
    plot_vpf_clcd_penalty(polar_dfs, alpha_eff_map, pitch_map_dir)

    summary_text = generate_stage2_summary(
        stage2_dir,
        len(configs),
        delta_beta=delta_beta,
        alpha_eff_map=alpha_eff_map,
        stall_map=stall_map,
    )
    write_stage_summary(2, summary_text, stage2_dir)

    s2 = Stage2Result(
        source_polars=source_polars,
        alpha_eff_map=alpha_eff_map,
        stall_map=stall_map,
        n_simulations=len(configs),
        n_convergence_warnings=n_conv_warnings,
        stage_dir=stage2_dir,
    )
    s2.validate()

    if n_conv_warnings > 0:
        LOGGER.warning(
            "Stage 2: %d aviso(s) de convergencia XFOIL — "
            "revisa los polares afectados antes de continuar.",
            n_conv_warnings,
        )

    return s2


# ---------------------------------------------------------------------------
# Paso 4 — Stage 3
# ---------------------------------------------------------------------------

def step_4_compressibility_correction(s2: Stage2Result) -> Stage3Result:
    """Stage 3: Correcciones de compresibilidad (PG + Kármán-Tsien + wave drag).

    Parameters
    ----------
    s2 : Stage2Result
        Resultado de Stage 2 (directorio de polares fuente).

    Returns
    -------
    Stage3Result
        Directorio de polares corregidos y estadísticas.
    """
    _section("PASO 4 / STAGE 3: Correcciones de compresibilidad")

    cfg = get_settings()
    stage3_dir = base_config.get_stage_dir(3)
    stage3_dir.mkdir(parents=True, exist_ok=True)

    pg_model = PrandtlGlauertModel()
    kt_model = KarmanTsienModel(
        thickness_ratio=cfg.airfoil_geometry.thickness_ratio,
        korn_kappa=cfg.airfoil_geometry.korn_kappa,
    )
    service = CompressibilityCorrectionService(
        pg_model=pg_model, kt_model=kt_model, base_output_dir=stage3_dir,
    )

    n_ok = 0
    n_fail = 0
    for flight in cfg.flight_conditions:
        mach = cfg.target_mach[flight]
        case = CompressibilityCase(
            flight_condition=flight,
            target_mach=mach,
            reference_mach=cfg.reference_mach,
        )
        for section in cfg.blade_sections:
            polar_path = s2.source_polars / flight.lower() / section / "polar.csv"
            if not polar_path.exists():
                LOGGER.warning("Polar no encontrado, omitiendo: %s", polar_path)
                n_fail += 1
                continue
            LOGGER.info("Corrigiendo %s/%s (M=%.2f)", flight, section, mach)
            try:
                service.correct_case(case, polar_path, section)
                n_ok += 1
            except Exception as exc:
                LOGGER.warning("Error corrigiendo %s/%s: %s", flight, section, exc)
                n_fail += 1

    service.plot_section_summary(stage3_dir, cfg.flight_conditions, cfg.blade_sections)

    summary_text = generate_stage3_summary(stage3_dir)
    write_stage_summary(3, summary_text, stage3_dir)

    s3 = Stage3Result(
        corrected_dir=stage3_dir,
        n_cases_corrected=n_ok,
        n_cases_failed=n_fail,
        stage_dir=stage3_dir,
    )
    s3.validate()

    LOGGER.info(
        "Stage 3: %d/%d casos corregidos (%.0f%% éxito)",
        n_ok, n_ok + n_fail, s3.success_rate * 100,
    )
    return s3


# ---------------------------------------------------------------------------
# Paso 5 — Stage 4
# ---------------------------------------------------------------------------

def step_5_metrics_and_figures(s3: Stage3Result) -> Stage4Result:
    """Stage 4: Métricas aerodinámicas + figuras de publicación.

    Parameters
    ----------
    s3 : Stage3Result
        Resultado de Stage 3 (polares corregidos).

    Returns
    -------
    Stage4Result
        Métricas calculadas y rutas a tablas/figuras.
    """
    _section("PASO 5 / STAGE 4: Métricas de rendimiento + figuras")

    cfg = get_settings()
    stage2_dir = base_config.get_stage_dir(2)
    polars_dir = s3.corrected_dir if s3.corrected_dir.exists() else stage2_dir / "simulation_plots"

    LOGGER.info("Leyendo polares desde: %s", polars_dir)

    metrics = compute_all_metrics(
        polars_dir,
        cfg.flight_conditions,
        cfg.blade_sections,
        cfg.reynolds_table,
        cfg.ncrit_table,
    )
    metrics = enrich_with_cruise_reference(
        metrics,
        polars_dir,
        axial_velocities=cfg.fan.axial_velocity_m_s,
        blade_radii=cfg.fan.radii_m,
        fan_rpm=cfg.fan.rpm,
    )
    LOGGER.info("Métricas calculadas: %d casos", len(metrics))

    stage4_dir = base_config.get_stage_dir(4)
    tables_dir  = stage4_dir / "tables"
    figures_dir = stage4_dir / "figures"

    export_summary_table(metrics, tables_dir / "summary_table.csv")
    export_clcd_max_table(metrics, tables_dir / "clcd_max_by_section.csv")

    # publication_figures usa los polares planos de Stage 2 (columna 'ld')
    stage2_polars_flat = base_config.get_stage_dir(2) / "polars"

    generate_stage4_figures(metrics, stage4_dir / "figures", polars_dir=polars_dir)
    generate_all_figures(
        polars_dir=stage2_polars_flat,
        figures_dir=figures_dir,
        metrics=metrics,
        flight_conditions=cfg.flight_conditions,
        blade_sections=cfg.blade_sections,
        stage3_dir=s3.corrected_dir,
        reynolds_table=cfg.reynolds_table,
    )

    LOGGER.info("Figuras de publicación generadas en: %s", figures_dir)

    summary_text = generate_stage4_summary(stage4_dir, metrics)
    write_stage_summary(4, summary_text, stage4_dir)

    s4 = Stage4Result(
        metrics=metrics,
        tables_dir=tables_dir,
        figures_dir=figures_dir,  # stage4_dir / "figures"
        stage_dir=stage4_dir,
    )
    s4.validate()
    return s4


# ---------------------------------------------------------------------------
# Paso 6 — Stage 5
# ---------------------------------------------------------------------------

def step_6_pitch_kinematics() -> Stage5Result:
    """Stage 5: Análisis completo de paso, incidencia y cinemática (3D).

    Returns
    -------
    Stage5Result
        Directorios de tablas/figuras y métricas clave.
    """
    _section("PASO 6 / STAGE 5: Pitch & Kinematics Analysis")

    run_pitch_kinematics()

    stage5_dir  = base_config.get_stage_dir(5)
    tables_dir  = stage5_dir / "tables"
    figures_dir = stage5_dir / "figures"
    n_tables    = len(list(tables_dir.glob("*.csv"))) if tables_dir.exists() else 0
    n_figures   = len(list(figures_dir.glob("*.png"))) if figures_dir.exists() else 0

    # Extraer métricas clave del CSV de twist
    twist_total = float("nan")
    max_loss    = float("nan")
    twist_file  = tables_dir / "blade_twist_design.csv"
    if twist_file.exists():
        import pandas as _pd
        df_tw = _pd.read_csv(twist_file)
        if "beta_metal_deg" in df_tw.columns and not df_tw.empty:
            bm = df_tw["beta_metal_deg"].dropna()
            twist_total = float(bm.max() - bm.min()) if len(bm) >= 2 else float("nan")

    offdesign_file = tables_dir / "off_design_incidence.csv"
    if offdesign_file.exists():
        import pandas as _pd
        df_od = _pd.read_csv(offdesign_file)
        if "efficiency_loss_pct" in df_od.columns:
            max_loss = float(df_od["efficiency_loss_pct"].max(skipna=True))

    s5 = Stage5Result(
        tables_dir=tables_dir,
        figures_dir=figures_dir,
        n_tables=n_tables,
        n_figures=n_figures,
        twist_total_deg=twist_total,
        max_off_design_loss_pct=max_loss,
        stage_dir=stage5_dir,
    )
    s5.validate()
    return s5


# ---------------------------------------------------------------------------
# Paso 7 — Stage 6
# ---------------------------------------------------------------------------

def step_7_sfc_analysis() -> Stage6Result:
    """Stage 6: Impacto del VPF en el consumo específico de combustible.

    Returns
    -------
    Stage6Result
        Directorios y reducción media de SFC.
    """
    _section("PASO 7 / STAGE 6: SFC Impact Analysis")

    run_sfc_analysis()

    stage6_dir  = base_config.get_stage_dir(6)
    tables_dir  = stage6_dir / "tables"
    figures_dir = stage6_dir / "figures"

    mean_sfc_reduction = float("nan")
    sfc_file = tables_dir / "sfc_analysis.csv"
    if sfc_file.exists():
        import pandas as _pd
        df_sfc = _pd.read_csv(sfc_file)
        col = next(
            (c for c in df_sfc.columns if "sfc_reduction" in c.lower()), None
        )
        if col:
            mean_sfc_reduction = float(df_sfc[col].mean(skipna=True))

    s6 = Stage6Result(
        tables_dir=tables_dir,
        figures_dir=figures_dir,
        mean_sfc_reduction_pct=mean_sfc_reduction,
        stage_dir=stage6_dir,
    )
    s6.validate()
    return s6


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Ejecuta el pipeline completo con validación de contratos entre stages."""
    LOGGER.info("=" * 80)
    LOGGER.info("Pipeline VPF — Análisis Aerodinámico Completo")
    LOGGER.info("=" * 80)

    try:
        step_1_clean_results()
        s1 = step_2_airfoil_selection()
        s2 = step_3_xfoil_simulations(s1)
        s3 = step_4_compressibility_correction(s2)
        s4 = step_5_metrics_and_figures(s3)
        s5 = step_6_pitch_kinematics()
        s6 = step_7_sfc_analysis()

        LOGGER.info("=" * 80)
        LOGGER.info("Pipeline completado con éxito.")
        LOGGER.info("")
        LOGGER.info("Resumen de outputs:")
        LOGGER.info("  Stage 1: %s (perfil: %s)", s1.stage_dir, s1.selected_airfoil_name)
        LOGGER.info("  Stage 2: %d simulaciones, %d avisos convergencia",
                    s2.n_simulations, s2.n_convergence_warnings)
        LOGGER.info("  Stage 3: %d/%d polares corregidos",
                    s3.n_cases_corrected, s3.n_cases_corrected + s3.n_cases_failed)
        LOGGER.info("  Stage 4: %d métricas calculadas", len(s4.metrics))
        LOGGER.info("  Stage 5: %d tablas, %d figuras | twist=%.1f° | pérdida_max=%.1f%%",
                    s5.n_tables, s5.n_figures, s5.twist_total_deg, s5.max_off_design_loss_pct)
        LOGGER.info("  Stage 6: reducción SFC media = %.2f%%", s6.mean_sfc_reduction_pct)
        LOGGER.info("")
        LOGGER.info("Resultados en:")
        for stage_num, stage_name in base_config.STAGE_DIR_NAMES.items():
            LOGGER.info("  Stage %d: %s", stage_num, base_config.RESULTS_DIR / stage_name)
        LOGGER.info("=" * 80)

    except Exception as exc:
        LOGGER.error("El pipeline falló: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
