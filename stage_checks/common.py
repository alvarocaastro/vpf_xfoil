from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import run_analysis
from vfp_analysis import config as base_config


def _existing_count(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0


def _validate_stage_outputs(stage_num: int) -> list[str]:
    stage_dir = base_config.get_stage_dir(stage_num)
    checks: list[tuple[Path, str]] = []

    if stage_num == 1:
        checks = [
            (stage_dir / "airfoil_selection" / "selected_airfoil.dat", "selected airfoil"),
        ]
    elif stage_num == 2:
        checks = [
            (stage_dir / "final_analysis", "final analysis directory"),
            (stage_dir / "polars", "organized polar directory"),
        ]
    elif stage_num == 3:
        checks = [
            (stage_dir, "compressibility output directory"),
        ]
    elif stage_num == 4:
        checks = [
            (stage_dir / "tables" / "summary_table.csv", "summary table"),
            (stage_dir / "tables" / "clcd_max_by_section.csv", "section metrics table"),
        ]
    elif stage_num == 5:
        checks = [
            (stage_dir / "figures", "figure directory"),
        ]
    elif stage_num == 6:
        checks = [
            (stage_dir / "tables" / "vpf_optimal_pitch.csv", "optimal pitch table"),
            (stage_dir / "tables" / "vpf_pitch_adjustment.csv", "pitch adjustment table"),
            (stage_dir / "figures", "VPF figure directory"),
        ]
    elif stage_num == 7:
        checks = [
            (stage_dir / "tables" / "kinematics_analysis.csv", "kinematics table"),
            (stage_dir / "figures", "kinematics figure directory"),
        ]
    elif stage_num == 8:
        checks = [
            (stage_dir / "tables" / "sfc_analysis.csv", "SFC table"),
            (stage_dir / "figures", "SFC figure directory"),
        ]

    messages: list[str] = []
    for path, label in checks:
        status = "OK" if path.exists() else "MISSING"
        messages.append(f"[{status}] {label}: {path}")

    if stage_num == 2:
        polars_dir = stage_dir / "polars"
        messages.append(f"[INFO] Stage 2 flat polars: {_existing_count(polars_dir, '*.csv')}")
    elif stage_num == 3:
        corrected = _existing_count(stage_dir, "*/*/corrected_polar.csv")
        messages.append(f"[INFO] Stage 3 corrected polars: {corrected}")
    elif stage_num == 5:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Stage 5 figures: {_existing_count(figures_dir, '*.png')}")
    elif stage_num == 6:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Stage 6 figures: {_existing_count(figures_dir, '*.png')}")
    elif stage_num == 8:
        figures_dir = stage_dir / "figures"
        messages.append(f"[INFO] Stage 8 figures: {_existing_count(figures_dir, '*.png')}")

    return messages


def run_stage_check(stage_num: int, clean: bool = True) -> None:
    if stage_num < 1 or stage_num > 8:
        raise ValueError("stage_num must be between 1 and 8")

    print("=" * 80)
    print(f"Stage check requested: Stage {stage_num}")
    print("=" * 80)

    if clean:
        print("[RUN] Cleaning previous results")
        run_analysis.step_1_clean_results()

    selected_airfoil = None
    source_polars = None
    metrics = None

    if stage_num >= 1:
        print("[RUN] Stage 1 - airfoil selection")
        selected_airfoil = run_analysis.step_2_airfoil_selection()
        print(f"[INFO] Selected airfoil: {selected_airfoil.name}")

    if stage_num >= 2:
        print("[RUN] Stage 2 - XFOIL simulations")
        source_polars = run_analysis.step_3_xfoil_simulations(selected_airfoil)
        print(f"[INFO] Stage 2 source polars: {source_polars}")

    if stage_num >= 3:
        print("[RUN] Stage 3 - compressibility correction")
        run_analysis.step_4_compressibility_correction(source_polars)

    if stage_num >= 4:
        print("[RUN] Stage 4 - metrics and tables")
        metrics = run_analysis.step_5_compute_metrics()
        run_analysis.step_6_export_tables(metrics)
        print(f"[INFO] Metric cases computed: {len(metrics)}")

    if stage_num >= 5:
        print("[RUN] Stage 5 - publication figures")
        if metrics is None:
            metrics = run_analysis.step_5_compute_metrics()
            run_analysis.step_6_export_tables(metrics)
        run_analysis.step_7_generate_figures(metrics)

    if stage_num >= 6:
        print("[RUN] Stage 6 - VPF analysis")
        run_analysis.step_8_vpf_analysis()

    if stage_num >= 7:
        print("[RUN] Stage 7 - kinematics analysis")
        run_analysis.step_9_kinematics_analysis()

    if stage_num >= 8:
        print("[RUN] Stage 8 - SFC analysis")
        run_analysis.step_10_sfc_analysis()

    print("-" * 80)
    for line in _validate_stage_outputs(stage_num):
        print(line)
    print("=" * 80)


def build_parser(stage_num: int) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"Run and validate the pipeline up to Stage {stage_num}."
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not remove previous results before running.",
    )
    return parser
