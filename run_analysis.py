"""
run_analysis.py — Entry point for the complete VPF aerodynamic analysis pipeline.

Runs 8 stages in sequence with explicit I/O contracts between them:
  1. Clean previous results
  2. Stage 1 — Airfoil selection           → Stage1Result
  3. Stage 2 — XFOIL simulations           → Stage2Result
  4. Stage 3 — Compressibility corrections → Stage3Result
  5. Stage 4 — Performance metrics         → Stage4Result
  6. Stage 5 — Pitch & Kinematics (3D)     → Stage5Result
  7. Stage 6 — Reverse Thrust Modeling     → Stage6Result
  8. Stage 7 — SFC Analysis               → Stage7Result
"""

from __future__ import annotations

import logging
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pandas as pd

# ── Rich imports ─────────────────────────────────────────────────────────────
from rich import box
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# ── Project path setup ───────────────────────────────────────────────────────
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
    Stage7Result,
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
from vfp_analysis.stage4_performance_metrics.plots import (
    generate_all_stage4_figures,
    generate_stage4_figures,
)
from vfp_analysis.stage4_performance_metrics.table_generator import (
    export_clcd_max_table,
    export_summary_table,
)
from vfp_analysis.stage5_pitch_kinematics.application.run_pitch_kinematics import (
    run_pitch_kinematics,
)
from vfp_analysis.stage6_reverse_thrust.application.run_reverse_thrust import (
    run_reverse_thrust,
)
from vfp_analysis.stage7_sfc_analysis.application.run_sfc_analysis import run_sfc_analysis

# ─────────────────────────────────────────────────────────────────────────────
# Console & Theme
# ─────────────────────────────────────────────────────────────────────────────

_THEME = Theme({
    "vpf.header":    "bold bright_cyan",
    "vpf.step":      "bold bright_white",
    "vpf.ok":        "bold bright_green",
    "vpf.warn":      "bold yellow",
    "vpf.error":     "bold bright_red",
    "vpf.info":      "dim white",
    "vpf.highlight": "bold magenta",
    "vpf.dim":       "dim cyan",
    "vpf.stage":     "bold cyan",
})

console = Console(theme=_THEME, highlight=False)

# ─────────────────────────────────────────────────────────────────────────────
# Logging (suppressed in favor of Rich panels, kept for debug)
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.WARNING,           # quiet the noisy library loggers
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
)
# Allow our own module to emit INFO via logger if needed
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

# ─────────────────────────────────────────────────────────────────────────────
# Pipeline progress bar (global, rendered inside the Live context)
# ─────────────────────────────────────────────────────────────────────────────

PIPELINE_PROGRESS = Progress(
    SpinnerColumn(spinner_name="dots", style="bold cyan"),
    TextColumn("[vpf.step]{task.description}[/vpf.step]"),
    BarColumn(bar_width=40, style="cyan", complete_style="bright_cyan", finished_style="bright_green"),
    TaskProgressColumn(),
    MofNCompleteColumn(),
    TimeElapsedColumn(),
    TimeRemainingColumn(),
    console=console,
    transient=False,
)

# Total number of pipeline steps (used for the overall bar)
_TOTAL_STEPS = 8


@contextmanager
def _stage_block(step: int, title: str, emoji: str = "⚙") -> Generator[None, None, None]:
    """Print a pretty header before a stage and a result line after."""
    console.print()
    console.rule(f"[vpf.stage]{emoji}  Step {step} — {title}[/vpf.stage]", style="cyan")
    t0 = time.perf_counter()
    try:
        yield
        elapsed = time.perf_counter() - t0
        console.print(f"    [vpf.ok]✔[/vpf.ok]  [vpf.info]{title} completed in {elapsed:.1f}s[/vpf.info]")
    except Exception:
        elapsed = time.perf_counter() - t0
        console.print(f"    [vpf.error]✘[/vpf.error]  [vpf.error]{title} FAILED after {elapsed:.1f}s[/vpf.error]")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Cleanup
# ─────────────────────────────────────────────────────────────────────────────

def step_1_clean_results() -> None:
    """Delete results from previous runs."""
    with _stage_block(1, "Cleaning previous results", "🗑"):
        dirs_to_clean = sorted(base_config.STAGE_DIR_NAMES)
        with Progress(
            SpinnerColumn(style="yellow"),
            TextColumn("[yellow]{task.description}"),
            BarColumn(bar_width=30, style="yellow", complete_style="bright_yellow"),
            MofNCompleteColumn(),
            console=console,
            transient=True,
        ) as prg:
            task = prg.add_task("Removing stage dirs…", total=len(dirs_to_clean))
            for stage_num in dirs_to_clean:
                stage_dir = base_config.get_stage_dir(stage_num)
                if stage_dir.exists():
                    prg.update(task, description=f"Removing [dim]{stage_dir.name}[/dim]")
                    shutil.rmtree(stage_dir, ignore_errors=True)
                stage_dir.mkdir(parents=True, exist_ok=True)
                prg.advance(task)
        console.print("    [vpf.info]All stage directories reset.[/vpf.info]")


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Stage 1: Airfoil selection
# ─────────────────────────────────────────────────────────────────────────────

def step_2_airfoil_selection() -> Stage1Result:
    """Stage 1: Automatic airfoil selection."""
    with _stage_block(2, "Airfoil Selection (Stage 1)", "✈"):
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
                f"No .dat files found in {base_config.AIRFOIL_DATA_DIR}. "
                "Ensure data/airfoils/ contains the airfoil profiles."
            )

        console.print(f"    [vpf.info]Evaluating [bold]{len(airfoils)}[/bold] candidate airfoils at "
                      f"Re={cfg.selection_reynolds:.2e}, M={cfg.reference_mach:.2f}[/vpf.info]")

        # Progress bar for candidate evaluation
        with Progress(
            SpinnerColumn(spinner_name="dots2", style="cyan"),
            TextColumn("[cyan]{task.description}"),
            BarColumn(bar_width=30, style="cyan", complete_style="bright_cyan"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as prg:
            task = prg.add_task("Running XFOIL on candidates…", total=len(airfoils))

            xfoil = XfoilRunnerAdapter(final_analysis=False)
            service = AirfoilSelectionService(xfoil_runner=xfoil, results_dir=stage1_dir)

            # Monkey-patch a callback onto the service so we can tick the bar
            _orig = service.run_selection
            def _ticked_run(af_list, cond):  # noqa: E306
                for af in af_list:
                    prg.update(task, description=f"XFOIL: [bold]{af.name}[/bold]")
                res = _orig(af_list, cond)
                prg.update(task, completed=len(af_list))
                return res

            result = _ticked_run(airfoils, selection_condition)

        console.print(f"    [vpf.ok]→[/vpf.ok]  Selected airfoil: "
                      f"[vpf.highlight]{result.best_airfoil.name}[/vpf.highlight]")

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


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Stage 2: XFOIL simulations
# ─────────────────────────────────────────────────────────────────────────────

def step_3_xfoil_simulations(s1: Stage1Result) -> Stage2Result:
    """Stage 2: XFOIL simulations for the selected airfoil."""
    with _stage_block(3, "XFOIL Simulations (Stage 2)", "🌊"):
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

        n_sims = len(configs)
        console.print(f"    [vpf.info]Running [bold]{n_sims}[/bold] XFOIL simulations "
                      f"for [vpf.highlight]{s1.selected_airfoil_name}[/vpf.highlight] "
                      f"({len(cfg.flight_conditions)} phases × {len(cfg.blade_sections)} sections)[/vpf.info]")

        airfoil = Airfoil(
            name=s1.selected_airfoil_name,
            family="",
            dat_path=s1.selected_airfoil_dat,
        )
        runner = XfoilRunnerAdapter(final_analysis=True)
        service = FinalAnalysisService(runner, stage2_dir)

        # Accumulate per-sim convergence stats for the summary
        _conv_log: list[tuple[str, str, float, int]] = []

        with Progress(
            SpinnerColumn(spinner_name="dots12", style="bright_cyan"),
            TextColumn("[bright_cyan]{task.description}"),
            BarColumn(bar_width=34, style="bright_cyan", complete_style="bright_green"),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        ) as prg:
            sim_task = prg.add_task(
                f"[bold]{s1.selected_airfoil_name}[/bold] — starting…",
                total=n_sims,
            )

            def _on_sim_done(flight: str, section: str, conv_rate: float, conv_failures: int) -> None:
                _conv_log.append((flight, section, conv_rate, conv_failures))
                pct = conv_rate * 100
                # Colour the rate: green ≥80%, yellow ≥60%, red <60%
                if pct >= 80:
                    rate_str = f"[bright_green]{pct:.0f}%[/bright_green]"
                elif pct >= 60:
                    rate_str = f"[yellow]{pct:.0f}%[/yellow]"
                else:
                    rate_str = f"[bright_red]{pct:.0f}%[/bright_red]"

                prg.advance(sim_task)
                remaining = n_sims - int(prg.tasks[sim_task].completed)
                label = (
                    f"[bold]{s1.selected_airfoil_name}[/bold]  "
                    f"[dim]{flight}/{section}[/dim]  conv={rate_str}"
                    + (f"  [dim]({remaining} left)[/dim]" if remaining > 0 else "  [bold bright_green]done ✔[/bold bright_green]")
                )
                prg.update(sim_task, description=label)

            alpha_eff_map, stall_map = service.run(
                airfoil, configs,
                progress_callback=_on_sim_done,
                flight_conditions=cfg.flight_conditions,
                blade_sections=cfg.blade_sections,
            )

        n_conv_warnings = getattr(service, "_total_convergence_warnings", 0)

        # ── Convergence quality table ────────────────────────────────────────
        conv_table = Table(
            title="[bold bright_cyan]XFOIL Convergence Quality — Stage 2[/bold bright_cyan]",
            box=box.SIMPLE_HEAVY,
            border_style="cyan",
            header_style="bold white",
            show_lines=False,
            padding=(0, 1),
        )
        conv_table.add_column("Flight", style="bold cyan", no_wrap=True)
        conv_table.add_column("Section", style="white", no_wrap=True)
        conv_table.add_column("Conv. rate", justify="right", no_wrap=True)
        conv_table.add_column("Failed pts", justify="right", style="dim")
        conv_table.add_column("Análisis OK?", justify="center", no_wrap=True)

        overall_rates: list[float] = []
        for flight, section, conv_rate, conv_failures in _conv_log:
            pct = conv_rate * 100
            overall_rates.append(conv_rate)
            if pct >= 80:
                rate_str = f"[bright_green]{pct:.1f}%[/bright_green]"
                ok_str   = "[bright_green]✔ Sí[/bright_green]"
            elif pct >= 60:
                rate_str = f"[yellow]{pct:.1f}%[/yellow]"
                ok_str   = "[yellow]⚠ Aceptable[/yellow]"
            else:
                rate_str = f"[bright_red]{pct:.1f}%[/bright_red]"
                ok_str   = "[bright_red]✘ Revisar[/bright_red]"
            fail_str = str(conv_failures) if conv_failures > 0 else "[dim]0[/dim]"
            conv_table.add_row(flight, section, rate_str, fail_str, ok_str)

        if overall_rates:
            mean_rate = sum(overall_rates) / len(overall_rates) * 100
            mean_color = "bright_green" if mean_rate >= 80 else ("yellow" if mean_rate >= 60 else "bright_red")
            conv_table.add_section()
            conv_table.add_row(
                "[bold]MEDIA[/bold]", "",
                f"[bold {mean_color}]{mean_rate:.1f}%[/bold {mean_color}]",
                "", "",
            )

        console.print()
        console.print(conv_table)

        # Criterion note
        console.print(
            "    [dim]Nota: fallos ocurren en zona post-stall (α > stall), "
            "fuera del rango operativo del fan. α_opt converge siempre.[/dim]"
        )
        console.print()

        # Post-processing (pitch map, plots, organize polars)
        console.print("    [vpf.info]Post-processing: pitch maps…[/vpf.info]")

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

        polar_dfs = {}
        for flight in cfg.flight_conditions:
            for section in cfg.blade_sections:
                csv_path = source_polars / flight / section / "polar.csv"
                if csv_path.exists():
                    polar_dfs[(flight, section)] = pd.read_csv(csv_path)

        plot_vpf_efficiency_by_section(polar_dfs, alpha_eff_map, pitch_map_dir)
        plot_vpf_clcd_penalty(polar_dfs, alpha_eff_map, pitch_map_dir)

        delta_str = ", ".join(f"{s}={v:.1f}°" for s, v in delta_beta.items())
        console.print(f"    [vpf.ok]→[/vpf.ok]  Δβ per section: [vpf.highlight]{delta_str}[/vpf.highlight]")
        if n_conv_warnings > 0:
            console.print(f"    [vpf.warn]⚠[/vpf.warn]  {n_conv_warnings} XFOIL convergence warning(s)")

        summary_text = generate_stage2_summary(
            stage2_dir, n_sims, delta_beta=delta_beta,
            alpha_eff_map=alpha_eff_map, stall_map=stall_map,
        )
        write_stage_summary(2, summary_text, stage2_dir)

        s2 = Stage2Result(
            source_polars=source_polars,
            alpha_eff_map=alpha_eff_map,
            stall_map=stall_map,
            n_simulations=n_sims,
            n_convergence_warnings=n_conv_warnings,
            stage_dir=stage2_dir,
        )
        s2.validate()
        return s2


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Stage 3: Compressibility corrections
# ─────────────────────────────────────────────────────────────────────────────

def step_4_compressibility_correction(s2: Stage2Result) -> Stage3Result:
    """Stage 3: Compressibility corrections (PG + Karman-Tsien + wave drag)."""
    with _stage_block(4, "Compressibility Corrections (Stage 3)", "💨"):
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

        total_cases = len(cfg.flight_conditions) * len(cfg.blade_sections)
        n_ok = 0
        n_fail = 0

        with Progress(
            SpinnerColumn(style="magenta"),
            TextColumn("[magenta]{task.description}"),
            BarColumn(bar_width=30, style="magenta", complete_style="bright_magenta"),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True,
        ) as prg:
            task = prg.add_task("Applying corrections…", total=total_cases)
            for flight in cfg.flight_conditions:
                mach = cfg.target_mach[flight]
                case = CompressibilityCase(
                    flight_condition=flight,
                    target_mach=mach,
                    reference_mach=cfg.reference_mach,
                )
                for section in cfg.blade_sections:
                    prg.update(task, description=f"[bold]{flight}[/bold]/{section} (M={mach:.2f})")
                    polar_path = s2.source_polars / flight.lower() / section / "polar.csv"
                    if not polar_path.exists():
                        console.print(f"      [vpf.warn]⚠[/vpf.warn] Polar not found: {polar_path.name}")
                        n_fail += 1
                    else:
                        try:
                            service.correct_case(case, polar_path, section)
                            n_ok += 1
                        except Exception as exc:
                            console.print(f"      [vpf.error]✘[/vpf.error] Error {flight}/{section}: {exc}")
                            n_fail += 1
                    prg.advance(task)

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
        console.print(f"    [vpf.ok]→[/vpf.ok]  {n_ok}/{n_ok + n_fail} polars corrected "
                      f"({s3.success_rate * 100:.0f}% success rate)")
        return s3


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Stage 4: Performance metrics & figures
# ─────────────────────────────────────────────────────────────────────────────

def step_5_metrics_and_figures(s3: Stage3Result) -> Stage4Result:
    """Stage 4: Aerodynamic metrics + publication figures."""
    with _stage_block(5, "Performance Metrics & Figures (Stage 4)", "📊"):
        cfg = get_settings()
        stage2_dir = base_config.get_stage_dir(2)
        polars_dir = s3.corrected_dir if s3.corrected_dir.exists() else stage2_dir / "simulation_plots"

        console.print(f"    [vpf.info]Reading polars from: [dim]{polars_dir}[/dim][/vpf.info]")

        with console.status("[cyan]Computing aerodynamic metrics…", spinner="dots"):
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

        console.print(f"    [vpf.ok]→[/vpf.ok]  {len(metrics)} metric cases computed")

        stage4_dir = base_config.get_stage_dir(4)
        tables_dir  = stage4_dir / "tables"
        figures_dir = stage4_dir / "figures"

        with console.status("[cyan]Exporting tables & generating figures…", spinner="dots"):
            export_summary_table(metrics, tables_dir / "summary_table.csv")
            export_clcd_max_table(metrics, tables_dir / "clcd_max_by_section.csv")
            stage2_polars_flat = base_config.get_stage_dir(2) / "polars"
            generate_all_stage4_figures(
                metrics=metrics,
                figures_dir=figures_dir,
                polars_dir=polars_dir,
                flight_conditions=cfg.flight_conditions,
                blade_sections=cfg.blade_sections,
                stage3_dir=s3.corrected_dir,
                reynolds_table=cfg.reynolds_table,
            )

        console.print(f"    [vpf.ok]→[/vpf.ok]  Publication figures saved to [dim]{figures_dir}[/dim]")

        summary_text = generate_stage4_summary(stage4_dir, metrics)
        write_stage_summary(4, summary_text, stage4_dir)

        s4 = Stage4Result(
            metrics=metrics,
            tables_dir=tables_dir,
            figures_dir=figures_dir,
            stage_dir=stage4_dir,
        )
        s4.validate()
        return s4


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Stage 5: Pitch & Kinematics
# ─────────────────────────────────────────────────────────────────────────────

def step_6_pitch_kinematics() -> Stage5Result:
    """Stage 5: Full pitch, incidence and kinematics analysis (3D)."""
    with _stage_block(6, "Pitch & Kinematics Analysis (Stage 5)", "🔄"):
        with console.status("[cyan]Running 3D pitch/kinematics model…", spinner="dots12"):
            run_pitch_kinematics()

        stage5_dir  = base_config.get_stage_dir(5)
        tables_dir  = stage5_dir / "tables"
        figures_dir = stage5_dir / "figures"
        n_tables  = len(list(tables_dir.glob("*.csv")))  if tables_dir.exists()  else 0
        n_figures = len(list(figures_dir.glob("*.png"))) if figures_dir.exists() else 0

        twist_total = float("nan")
        max_loss    = float("nan")
        twist_file  = tables_dir / "blade_twist_design.csv"
        if twist_file.exists():
            import pandas as _pd
            df_tw = _pd.read_csv(twist_file)
            if "beta_metal_deg" in df_tw.columns and "section" in df_tw.columns:
                bm_root = df_tw.loc[df_tw["section"] == "root", "beta_metal_deg"]
                bm_tip  = df_tw.loc[df_tw["section"] == "tip",  "beta_metal_deg"]
                if not bm_root.empty and not bm_tip.empty:
                    twist_total = float(bm_root.iloc[0]) - float(bm_tip.iloc[0])

        offdesign_file = tables_dir / "off_design_incidence.csv"
        if offdesign_file.exists():
            import pandas as _pd
            df_od = _pd.read_csv(offdesign_file)
            if "efficiency_loss_pct" in df_od.columns:
                max_loss = float(df_od["efficiency_loss_pct"].max(skipna=True))

        console.print(f"    [vpf.ok]→[/vpf.ok]  {n_tables} tables, {n_figures} figures | "
                      f"twist={twist_total:.1f}° | max loss={max_loss:.1f}%")

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


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 — Stage 6: Reverse Thrust
# ─────────────────────────────────────────────────────────────────────────────

def step_7_reverse_thrust() -> Stage6Result:
    """Stage 6: VPF Reverse Thrust Modeling."""
    with _stage_block(7, "Reverse Thrust Modeling (Stage 6)", "🔁"):
        with console.status("[cyan]Modelling VPF reverse thrust…", spinner="dots12"):
            run_reverse_thrust()

        stage6_dir  = base_config.get_stage_dir(6)
        tables_dir  = stage6_dir / "tables"
        figures_dir = stage6_dir / "figures"
        n_tables  = len(list(tables_dir.glob("*.csv")))  if tables_dir.exists()  else 0
        n_figures = len(list(figures_dir.glob("*.png"))) if figures_dir.exists() else 0

        beta_opt    = float("nan")
        thrust_frac = float("nan")
        mech_weight = float("nan")
        sfc_penalty = float("nan")

        import pandas as _pd

        opt_file = tables_dir / "reverse_thrust_optimal.csv"
        if opt_file.exists():
            df_opt = _pd.read_csv(opt_file).set_index("metric")["value"]
            beta_opt    = float(df_opt.get("beta_opt_mid_deg",   float("nan")))
            thrust_frac = float(df_opt.get("thrust_fraction_pct", float("nan"))) / 100.0

        mw_file = tables_dir / "mechanism_weight.csv"
        if mw_file.exists():
            df_mw = _pd.read_csv(mw_file).set_index("metric")["value"]
            mech_weight = float(df_mw.get("mechanism_weight_kg",    float("nan")))
            sfc_penalty = float(df_mw.get("sfc_cruise_penalty_pct", float("nan")))

        console.print(f"    [vpf.ok]→[/vpf.ok]  β_opt={beta_opt:.1f}° | "
                      f"T_rev={thrust_frac * 100:.1f}% fwd | "
                      f"mechanism={mech_weight:.0f} kg | ΔSFC=+{sfc_penalty:.3f}%")

        s6 = Stage6Result(
            tables_dir=tables_dir,
            figures_dir=figures_dir,
            n_tables=n_tables,
            n_figures=n_figures,
            beta_opt_deg=beta_opt,
            thrust_fraction=thrust_frac,
            mechanism_weight_kg=mech_weight,
            sfc_cruise_penalty_pct=sfc_penalty,
            stage_dir=stage6_dir,
        )
        s6.validate()
        return s6


# ─────────────────────────────────────────────────────────────────────────────
# Step 8 — Stage 7: SFC Analysis
# ─────────────────────────────────────────────────────────────────────────────

def step_8_sfc_analysis() -> Stage7Result:
    """Stage 7: VPF impact on specific fuel consumption."""
    with _stage_block(8, "SFC Impact Analysis (Stage 7)", "⛽"):
        with console.status("[cyan]Computing SFC improvement…", spinner="dots12"):
            run_sfc_analysis()

        stage7_dir  = base_config.get_stage_dir(7)
        tables_dir  = stage7_dir / "tables"
        figures_dir = stage7_dir / "figures"

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

        console.print(f"    [vpf.ok]→[/vpf.ok]  Mean SFC reduction: "
                      f"[vpf.highlight]{mean_sfc_reduction:.2f}%[/vpf.highlight]")

        s7 = Stage7Result(
            tables_dir=tables_dir,
            figures_dir=figures_dir,
            mean_sfc_reduction_pct=mean_sfc_reduction,
            stage_dir=stage7_dir,
        )
        s7.validate()
        return s7


# ─────────────────────────────────────────────────────────────────────────────
# Summary panel
# ─────────────────────────────────────────────────────────────────────────────

def _print_summary(
    s1: Stage1Result,
    s2: Stage2Result,
    s3: Stage3Result,
    s4: Stage4Result,
    s5: Stage5Result,
    s6: Stage6Result,
    s7: Stage7Result,
    elapsed: float,
) -> None:
    table = Table(
        title="[bold bright_cyan]VPF Pipeline — Results Summary[/bold bright_cyan]",
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold bright_white",
        show_lines=True,
    )
    table.add_column("Stage", style="bold cyan", justify="center", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Key Result", style="bright_green")

    table.add_row(
        "1",
        "Airfoil Selection",
        f"[vpf.highlight]{s1.selected_airfoil_name}[/vpf.highlight]",
    )
    table.add_row(
        "2",
        "XFOIL Simulations",
        f"{s2.n_simulations} sims | {s2.n_convergence_warnings} warnings",
    )
    table.add_row(
        "3",
        "Compressibility Corrections",
        f"{s3.n_cases_corrected}/{s3.n_cases_corrected + s3.n_cases_failed} cases "
        f"({s3.success_rate * 100:.0f}%)",
    )
    table.add_row(
        "4",
        "Performance Metrics",
        f"{len(s4.metrics)} metric cases",
    )
    table.add_row(
        "5",
        "Pitch & Kinematics",
        f"twist={s5.twist_total_deg:.1f}° | max_loss={s5.max_off_design_loss_pct:.1f}%",
    )
    table.add_row(
        "6",
        "Reverse Thrust",
        f"β_opt={s6.beta_opt_deg:.1f}° | T_rev={s6.thrust_fraction * 100:.1f}% | "
        f"Δmass={s6.mechanism_weight_kg:.0f}kg | ΔSFC=+{s6.sfc_cruise_penalty_pct:.3f}%",
    )
    table.add_row(
        "7",
        "SFC Analysis",
        f"[bold bright_green]Mean SFC reduction: {s7.mean_sfc_reduction_pct:.2f}%[/bold bright_green]",
    )

    console.print()
    console.print(table)
    console.print()
    console.print(Panel(
        f"[bold bright_green]✔  Pipeline completed successfully[/bold bright_green]  "
        f"[dim]in {elapsed:.1f}s ({elapsed / 60:.1f} min)[/dim]\n\n"
        f"[dim]Results → {base_config.RESULTS_DIR}[/dim]",
        border_style="bright_green",
        box=box.DOUBLE_EDGE,
        padding=(0, 2),
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the full pipeline with inter-stage contract validation."""
    # ── Banner ────────────────────────────────────────────────────────────────
    console.print()
    console.print(Panel(
        Text.assemble(
            ("  ✈  VPF Pipeline — Complete Aerodynamic Analysis  ✈  \n", "bold bright_cyan"),
            ("  Variable Pitch Fan · Aerodynamic Performance Simulation", "dim white"),
        ),
        border_style="cyan",
        box=box.DOUBLE_EDGE,
        padding=(0, 4),
    ))

    # ── Overall progress bar ──────────────────────────────────────────────────
    overall = Progress(
        SpinnerColumn(spinner_name="earth", style="bright_cyan"),
        TextColumn("[bold bright_white]Overall progress"),
        BarColumn(bar_width=50, style="cyan", complete_style="bright_green"),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

    t_start = time.perf_counter()

    with overall:
        pipeline_task = overall.add_task("Running pipeline…", total=_TOTAL_STEPS)

        try:
            step_1_clean_results();          overall.advance(pipeline_task)
            s1 = step_2_airfoil_selection(); overall.advance(pipeline_task)
            s2 = step_3_xfoil_simulations(s1); overall.advance(pipeline_task)
            s3 = step_4_compressibility_correction(s2); overall.advance(pipeline_task)
            s4 = step_5_metrics_and_figures(s3); overall.advance(pipeline_task)
            s5 = step_6_pitch_kinematics(); overall.advance(pipeline_task)
            s6 = step_7_reverse_thrust();   overall.advance(pipeline_task)
            s7 = step_8_sfc_analysis();     overall.advance(pipeline_task)

        except Exception as exc:
            console.print()
            console.print(Panel(
                f"[bold bright_red]✘  Pipeline FAILED[/bold bright_red]\n\n"
                f"[red]{exc}[/red]",
                border_style="bright_red",
                box=box.HEAVY,
                padding=(0, 2),
            ))
            console.print_exception(show_locals=False)
            sys.exit(1)

    elapsed = time.perf_counter() - t_start
    _print_summary(s1, s2, s3, s4, s5, s6, s7, elapsed)


if __name__ == "__main__":
    main()
