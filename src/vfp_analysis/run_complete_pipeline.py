"""
Pipeline completo integrado: Stage 1, Stage 2 y Stage 3.

Este script ejecuta secuencialmente:
- Stage 1: Determinación del perfil coherente de los .dat disponibles
- Stage 2: Análisis aerodinámico a Mach 0.2 con XFOIL
- Stage 3: Aplicación de corrección de compresibilidad

Resultados organizados en:
- vfp_analysis/results/stage_1/
- vfp_analysis/results/stage_2/
- vfp_analysis/results/stage_3/
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import pandas as pd

from vfp_analysis import config
from vfp_analysis.adapters.xfoil.xfoil_runner_adapter import XfoilRunnerAdapter
from vfp_analysis.compressibility.adapters.correction_models.prandtl_glauert_model import (
    PrandtlGlauertModel,
)
from vfp_analysis.compressibility.adapters.filesystem.corrected_results_writer import (
    FilesystemResultsWriter,
)
from vfp_analysis.compressibility.adapters.filesystem.polar_reader import (
    FilesystemPolarReader,
)
from vfp_analysis.compressibility.core.domain.compressibility_case import (
    CompressibilityCase,
)
from vfp_analysis.compressibility import config as comp_config
from vfp_analysis.compressibility.core.services.compressibility_correction_service import (
    CompressibilityCorrectionService,
)
from vfp_analysis.core.domain.airfoil import Airfoil
from vfp_analysis.core.domain.blade_section import BladeSection
from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.core.services.airfoil_selection_service import (
    AirfoilSelectionService,
)
from vfp_analysis.core.services.final_analysis_service import (
    FinalAnalysisService,
    FinalSimulationConfig,
)

LOGGER = logging.getLogger(__name__)

# Directorios de resultados por stage
STAGE_1_DIR = config.RESULTS_DIR / "stage_1"
STAGE_2_DIR = config.RESULTS_DIR / "stage_2"
STAGE_3_DIR = config.RESULTS_DIR / "stage_3"

# Configuración de compresibilidad (usar la del módulo)
TARGET_MACH = comp_config.TARGET_MACH
REFERENCE_MACH = comp_config.REFERENCE_MACH


def _clean_results() -> None:
    """
    Limpia TODOS los resultados anteriores para garantizar ejecución limpia.
    
    Elimina completamente la carpeta results/ y todas sus subcarpetas,
    incluyendo cualquier resultado residual de ejecuciones anteriores.
    """
    LOGGER.info("Limpiando resultados anteriores...")
    
    # Limpiar la carpeta results completa
    results_root = config.RESULTS_DIR
    if results_root.exists():
        LOGGER.info("Eliminando carpeta results/ completa...")
        shutil.rmtree(results_root, ignore_errors=True)
    
    # Asegurar que la carpeta results existe (vacía)
    results_root.mkdir(parents=True, exist_ok=True)
    
    # Crear estructura de carpetas para los stages
    for stage_dir in [STAGE_1_DIR, STAGE_2_DIR, STAGE_3_DIR]:
        stage_dir.mkdir(parents=True, exist_ok=True)
    
    LOGGER.info("Limpieza completada. Carpeta results/ lista para nuevos resultados.")


def _build_airfoils() -> list[Airfoil]:
    """Construye lista de perfiles desde los .dat disponibles."""
    airfoils: list[Airfoil] = []
    for spec in config.AIRFOILS:
        dat_path = config.AIRFOIL_DATA_DIR / spec["dat_file"]
        if dat_path.is_file():
            airfoils.append(
                Airfoil(
                    name=spec["name"],
                    family=spec["family"],
                    dat_path=dat_path,
                )
            )
    return airfoils


def stage_1_airfoil_selection() -> Airfoil:
    """
    Stage 1: Determina el perfil coherente de los .dat disponibles.

    Returns
    -------
    Airfoil
        Perfil seleccionado como mejor.
    """
    LOGGER.info("=== Stage 1: Determinación del perfil coherente ===")

    STAGE_1_DIR.mkdir(parents=True, exist_ok=True)

    selection_condition = SimulationCondition(
        name="Selection",
        mach_rel=config.MACH_DEFAULT,
        reynolds=3.0e6,
        alpha_min=-5.0,
        alpha_max=20.0,
        alpha_step=0.15,
        ncrit=7.0,
    )

    xfoil = XfoilRunnerAdapter()
    # Usar STAGE_1_DIR como directorio de resultados temporal
    service = AirfoilSelectionService(
        xfoil_runner=xfoil, results_dir=STAGE_1_DIR
    )

    airfoils = _build_airfoils()
    result = service.run_selection(airfoils, selection_condition)

    # Guardar perfil seleccionado
    selected_path = STAGE_1_DIR / "selected_airfoil.dat"
    selected_path.write_text(result.best_airfoil.name, encoding="utf8")

    LOGGER.info(f"Perfil seleccionado: {result.best_airfoil.name}")
    return result.best_airfoil


def stage_2_xfoil_analysis(selected_airfoil: Airfoil) -> None:
    """
    Stage 2: Análisis aerodinámico a Mach 0.2 con XFOIL.

    Parameters
    ----------
    selected_airfoil : Airfoil
        Perfil seleccionado en Stage 1.
    """
    LOGGER.info("=== Stage 2: Análisis aerodinámico a Mach 0.2 ===")

    STAGE_2_DIR.mkdir(parents=True, exist_ok=True)

    sections = [
        BladeSection(name="root", reynolds=0.0),
        BladeSection(name="mid_span", reynolds=0.0),
        BladeSection(name="tip", reynolds=0.0),
    ]

    flights = ["Takeoff", "Climb", "Cruise", "Descent"]

    re_table = {
        "Takeoff": {"root": 2.5e6, "mid_span": 4.5e6, "tip": 7.0e6},
        "Climb": {"root": 2.2e6, "mid_span": 4.0e6, "tip": 6.2e6},
        "Cruise": {"root": 1.8e6, "mid_span": 3.2e6, "tip": 5.0e6},
        "Descent": {"root": 2.0e6, "mid_span": 3.6e6, "tip": 5.6e6},
    }

    ncrit_table = {
        "Takeoff": 5.0,
        "Climb": 6.0,
        "Cruise": 7.0,
        "Descent": 6.0,
    }

    configs: List[FinalSimulationConfig] = []
    for flight in flights:
        for section in sections:
            re_value = re_table[flight][section.name]
            ncrit_value = ncrit_table[flight]
            cond = SimulationCondition(
                name=f"{flight}_{section.name}",
                mach_rel=config.MACH_DEFAULT,
                reynolds=re_value,
                alpha_min=-5.0,
                alpha_max=23.0,
                alpha_step=0.15,
                ncrit=ncrit_value,
            )
            configs.append(
                FinalSimulationConfig(
                    flight_name=flight,
                    section=section,
                    condition=cond,
                )
            )

    runner = XfoilRunnerAdapter()
    service = FinalAnalysisService(runner, STAGE_2_DIR)
    alpha_eff_map = service.run(selected_airfoil, configs)

    # Generar resumen de eficiencia máxima (segundo pico)
    summary_rows: list[dict] = []
    avg_eff_by_flight: Dict[str, pd.DataFrame] = {}

    for flight in flights:
        dfs = []
        for section in ["root", "mid_span", "tip"]:
            polar_csv = STAGE_2_DIR / "final_analysis" / flight.lower() / section / "polar.csv"
            if not polar_csv.is_file():
                continue
            df = pd.read_csv(polar_csv)

            # Segundo pico: ignoramos ángulos menores de 3º
            # El primer pico a bajo alpha es un artefacto de burbuja de separación
            # laminar no representativo de la operación de turbomaquinaria.
            df_second_peak = df[df["alpha"] >= 3.0]
            if not df_second_peak.empty:
                idx = df_second_peak["ld"].idxmax()
                row = df_second_peak.loc[idx]
                summary_rows.append(
                    {
                        "flight": flight,
                        "section": section,
                        "re": float(row.get("re", float("nan"))),
                        "ncrit": float(row.get("ncrit", float("nan"))),
                        "alpha_opt_deg": float(row["alpha"]),
                        "ld_max": float(row["ld"]),
                    }
                )

            dfs.append(df[["alpha", "ld"]].rename(columns={"ld": f"ld_{section}"}))

        if dfs:
            df_merged = dfs[0]
            for extra in dfs[1:]:
                df_merged = df_merged.merge(extra, on="alpha", how="inner")
            ld_cols = [c for c in df_merged.columns if c.startswith("ld_")]
            df_merged["ld_mean"] = df_merged[ld_cols].mean(axis=1)
            avg_eff_by_flight[flight] = df_merged[["alpha", "ld_mean"]]

            # Gráfica de eficiencia media por condición
            fig, ax = plt.subplots(figsize=(5.0, 4.0))
            ax.plot(df_merged["alpha"], df_merged["ld_mean"], linewidth=1.6)
            ax.set_xlabel(r"$\alpha$ [deg]")
            ax.set_ylabel(r"$C_L/C_D$ medio")
            ax.set_title(f"Eficiencia media $C_L/C_D$ – {flight}")
            ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
            flight_dir = STAGE_2_DIR / "final_analysis" / flight.lower()
            flight_dir.mkdir(parents=True, exist_ok=True)
            fig.tight_layout()
            fig.savefig(flight_dir / "efficiency_mean_plot.png", dpi=300, bbox_inches="tight")
            plt.close(fig)

    # Añadir medias por condición
    for flight in flights:
        flight_rows = [r for r in summary_rows if r["flight"] == flight]
        if len(flight_rows) == 3:  # root, mid_span, tip
            re_mean = sum(r["re"] for r in flight_rows) / 3.0
            ncrit_mean = flight_rows[0]["ncrit"]  # mismo para todas las secciones
            alpha_mean = sum(r["alpha_opt_deg"] for r in flight_rows) / 3.0
            ld_mean = sum(r["ld_max"] for r in flight_rows) / 3.0
            summary_rows.append(
                {
                    "flight": flight,
                    "section": "mean",
                    "re": re_mean,
                    "ncrit": ncrit_mean,
                    "alpha_opt_deg": alpha_mean,
                    "ld_max": ld_mean,
                }
            )

    # Guardar resumen
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_path = STAGE_2_DIR / "max_efficiency_summary.csv"
        summary_df.to_csv(summary_path, index=False, float_format="%.6f")

    # Figura global: eficiencia media vs alpha para todas las fases
    if avg_eff_by_flight:
        fig, ax = plt.subplots(figsize=(6.0, 4.5))
        for flight, df in avg_eff_by_flight.items():
            ax.plot(df["alpha"], df["ld_mean"], label=flight, linewidth=1.6)
        ax.set_xlabel(r"$\alpha$ [deg]")
        ax.set_ylabel(r"$C_L/C_D$ medio")
        ax.set_title("Eficiencia media $C_L/C_D$ por condición de vuelo")
        ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(STAGE_2_DIR / "efficiency_mean_all_flights.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

    LOGGER.info("Stage 2 completado. Resultados en: %s", STAGE_2_DIR)


def stage_3_compressibility_correction() -> None:
    """
    Stage 3: Aplicación de corrección de compresibilidad.
    """
    LOGGER.info("=== Stage 3: Corrección de compresibilidad ===")

    STAGE_3_DIR.mkdir(parents=True, exist_ok=True)

    # Inicializar adaptadores y servicio
    reader = FilesystemPolarReader()
    writer = FilesystemResultsWriter()
    model = PrandtlGlauertModel()
    service = CompressibilityCorrectionService(
        polar_reader=reader,
        results_writer=writer,
        correction_model=model,
        base_output_dir=STAGE_3_DIR,
    )

    # Procesar cada condición de vuelo
    base_input = STAGE_2_DIR / "final_analysis"
    flights = ["Takeoff", "Climb", "Cruise", "Descent"]
    sections = ["root", "mid_span", "tip"]

    all_results: list[dict] = []

    for flight in flights:
        target_mach = TARGET_MACH[flight]
        case = CompressibilityCase(
            flight_condition=flight,
            target_mach=target_mach,
            reference_mach=REFERENCE_MACH,
        )

        for section in sections:
            polar_path = base_input / flight.lower() / section / "polar.csv"
            if not polar_path.is_file():
                LOGGER.warning(f"Polar no encontrado: {polar_path}")
                continue

            LOGGER.info(f"Corrigiendo {flight} / {section} (M={target_mach:.2f})")
            result = service.correct_case(case, polar_path, section)

            # Extraer eficiencia máxima (segundo pico, alpha >= 3)
            df_corrected = pd.read_csv(result.corrected_polar_path)
            df_second = df_corrected[df_corrected["alpha"] >= 3.0]
            if not df_second.empty:
                idx = df_second["ld_corrected"].idxmax()
                row = df_second.loc[idx]
                all_results.append(
                    {
                        "flight": flight,
                        "section": section,
                        "mach_corrected": target_mach,
                        "alpha_opt_deg": float(row["alpha"]),
                        "ld_max_corrected": float(row["ld_corrected"]),
                    }
                )

    # Generar resumen CSV
    if all_results:
        summary_df = pd.DataFrame(all_results)
        summary_path = STAGE_3_DIR / "corrected_efficiency_summary.csv"
        summary_df.to_csv(summary_path, index=False, float_format="%.6f")
        LOGGER.info(f"Resumen guardado en: {summary_path}")

    # Gráfica global: eficiencia corregida vs alpha para todas las condiciones
    fig, ax = plt.subplots(figsize=(7.0, 5.0))
    for flight in flights:
        corrected_path = STAGE_3_DIR / flight.lower() / "mid_span" / "corrected_efficiency.csv"
        if corrected_path.is_file():
            df = pd.read_csv(corrected_path)
            ax.plot(df["alpha"], df["ld_corrected"], label=flight, linewidth=1.6)
    ax.set_xlabel(r"$\alpha$ [deg]")
    ax.set_ylabel(r"$C_L/C_D$ corregido")
    ax.set_title("Eficiencia corregida $C_L/C_D$ por condición de vuelo")
    ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(STAGE_3_DIR / "corrected_efficiency_all_flights.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    LOGGER.info("Stage 3 completado. Resultados en: %s", STAGE_3_DIR)


def main() -> None:
    """Ejecuta el pipeline completo: Stage 1, Stage 2, Stage 3."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    LOGGER.info("=== Iniciando pipeline completo ===")

    # Limpiar resultados anteriores
    _clean_results()

    # Stage 1: Determinación del perfil coherente
    selected_airfoil = stage_1_airfoil_selection()

    # Stage 2: Análisis a Mach 0.2
    stage_2_xfoil_analysis(selected_airfoil)

    # Stage 3: Corrección de compresibilidad
    stage_3_compressibility_correction()

    LOGGER.info("=== Pipeline completo finalizado ===")
    LOGGER.info("Resultados organizados en:")
    LOGGER.info("  - Stage 1: %s", STAGE_1_DIR)
    LOGGER.info("  - Stage 2: %s", STAGE_2_DIR)
    LOGGER.info("  - Stage 3: %s", STAGE_3_DIR)


if __name__ == "__main__":
    main()
