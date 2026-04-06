"""
Generate final results summary files for each stage.

This module creates comprehensive summary files (finalresults_stageX.txt) that
contain results, explanations, and key information for each analysis stage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from vfp_analysis import config as base_config
from vfp_analysis.config_loader import (
    get_alpha_range,
    get_blade_sections,
    get_flight_conditions,
    get_ncrit_table,
    get_reynolds_table,
    get_selection_alpha_range,
    get_target_mach,
)


def generate_stage1_summary(stage_dir: Path, selected_airfoil_name: str) -> str:
    """
    Generate summary for Stage 1: Airfoil Selection.

    Parameters
    ----------
    stage_dir : Path
        Directory where Stage 1 results are stored.
    selected_airfoil_name : str
        Name of the selected airfoil.

    Returns
    -------
    str
        Formatted summary text.
    """
    alpha_range = get_selection_alpha_range()
    selection_dir = stage_dir / "airfoil_selection"

    lines = [
        "=" * 80,
        "STAGE 1: AUTOMATED AIRFOIL SELECTION - FINAL RESULTS",
        "=" * 80,
        "",
        "OBJECTIVE",
        "--------",
        "Compare multiple airfoil candidates under identical reference conditions",
        "and automatically select the best performing airfoil for turbofan fan",
        "blade applications based on aerodynamic efficiency, stall characteristics,",
        "and drag performance.",
        "",
        "METHODOLOGY",
        "-----------",
        f"Reference Conditions:",
        f"  - Mach Number: 0.2 (incompressible, XFOIL limitation)",
        f"  - Reynolds Number: 3.0e6 (representative of fan blade conditions)",
        f"  - Angle of Attack Range: {alpha_range['min']:.1f}° to {alpha_range['max']:.1f}°",
        f"  - Alpha Step: {alpha_range['step']:.2f}°",
        f"  - Ncrit: 7.0 (clean flow conditions)",
        "",
        "Selection Criteria:",
        "  - Maximum aerodynamic efficiency (CL/CD)",
        "  - Stall angle (angle at which lift drops significantly)",
        "  - Average drag coefficient (lower is better)",
        "",
        "SELECTED AIRFOIL",
        "---------------",
        f"Selected Airfoil: {selected_airfoil_name}",
        "",
        "This airfoil was selected as the best candidate based on the combined",
        "scoring algorithm that weights maximum efficiency, stall characteristics,",
        "and drag performance.",
        "",
        "RESULTS LOCATION",
        "----------------",
        f"Selection results: {selection_dir}",
        f"Selected airfoil file: {selection_dir / 'selected_airfoil.dat'}",
        "",
        "FILES GENERATED",
        "--------------",
        "- airfoil_selection/*_polar.txt: Polar data for each candidate airfoil",
        "- airfoil_selection/selected_airfoil.dat: Name of selected airfoil",
        "",
        "=" * 80,
    ]

    return "\n".join(lines)


def generate_stage2_summary(stage_dir: Path, num_simulations: int) -> str:
    """
    Generate summary for Stage 2: XFOIL Simulations.

    Parameters
    ----------
    stage_dir : Path
        Directory where Stage 2 results are stored.
    num_simulations : int
        Number of XFOIL simulations executed.

    Returns
    -------
    str
        Formatted summary text.
    """
    flight_conditions = get_flight_conditions()
    blade_sections = get_blade_sections()
    reynolds_table = get_reynolds_table()
    ncrit_table = get_ncrit_table()
    alpha_range = get_alpha_range()

    lines = [
        "=" * 80,
        "STAGE 2: XFOIL AERODYNAMIC SIMULATIONS - FINAL RESULTS",
        "=" * 80,
        "",
        "OBJECTIVE",
        "--------",
        "Perform detailed aerodynamic analysis of the selected airfoil across",
        "multiple flight conditions and blade sections to characterize performance",
        "under realistic operating conditions.",
        "",
        "SIMULATION PARAMETERS",
        "---------------------",
        f"Mach Number: 0.2 (incompressible baseline, XFOIL limitation)",
        f"Angle of Attack Range: {alpha_range['min']:.1f}° to {alpha_range['max']:.1f}°",
        f"Alpha Step: {alpha_range['step']:.2f}°",
        "",
        "Flight Conditions Analyzed:",
    ]

    for flight in flight_conditions:
        lines.append(f"  - {flight.capitalize()}: Ncrit = {ncrit_table[flight]:.1f}")

    lines.extend([
        "",
        "Blade Sections Analyzed:",
    ])

    for section in blade_sections:
        lines.append(f"  - {section.replace('_', ' ').title()}")

    lines.extend([
        "",
        "REYNOLDS NUMBERS BY CONDITION AND SECTION",
        "------------------------------------------",
    ])

    for flight in flight_conditions:
        lines.append(f"\n{flight.capitalize()}:")
        for section in blade_sections:
            re = reynolds_table[flight][section]
            lines.append(f"  {section:12s}: Re = {re:.2e}")

    lines.extend([
        "",
        "SIMULATION RESULTS",
        "------------------",
        f"Total Simulations Executed: {num_simulations}",
        f"  - Flight Conditions: {len(flight_conditions)}",
        f"  - Blade Sections: {len(blade_sections)}",
        f"  - Total: {len(flight_conditions)} × {len(blade_sections)} = {num_simulations}",
        "",
        "RESULTS LOCATION",
        "----------------",
        f"Polar data: {stage_dir / 'polars'}",
        f"Detailed results: {stage_dir / 'final_analysis'}",
        "",
        "FILES GENERATED",
        "--------------",
        "For each flight condition × blade section combination:",
        "  - polar.csv: Complete polar data (alpha, CL, CD, CM, CL/CD)",
        "  - cl_alpha.csv: Lift coefficient vs angle of attack",
        "  - cd_alpha.csv: Drag coefficient vs angle of attack",
        "  - cl_alpha_plot.png: CL vs alpha plot",
        "  - cd_alpha_plot.png: CD vs alpha plot",
        "  - efficiency_plot.png: CL/CD vs alpha with maximum marked",
        "  - polar_plot.png: Polar curve (CL vs CD)",
        "",
        "Organized polar files:",
        "  - {condition}_{section}.csv in polars/ directory",
        "",
        "=" * 80,
    ])

    return "\n".join(lines)


def generate_stage3_summary(stage_dir: Path) -> str:
    """
    Generate summary for Stage 3: Compressibility Corrections.

    Parameters
    ----------
    stage_dir : Path
        Directory where Stage 3 results are stored.

    Returns
    -------
    str
        Formatted summary text.
    """
    flight_conditions = get_flight_conditions()
    blade_sections = get_blade_sections()
    target_mach = get_target_mach()

    lines = [
        "=" * 80,
        "STAGE 3: COMPRESSIBILITY CORRECTIONS - FINAL RESULTS",
        "=" * 80,
        "",
        "OBJECTIVE",
        "--------",
        "Apply compressibility corrections to incompressible XFOIL results to",
        "account for compressibility effects at representative flight Mach numbers.",
        "This stage uses the Prandtl-Glauert correction model to estimate",
        "aerodynamic coefficients at higher Mach numbers.",
        "",
        "METHODOLOGY",
        "-----------",
        "Correction Model: Prandtl-Glauert",
        "  - Valid for Mach numbers < 0.8 (subsonic flow)",
        "  - Correction factor: beta = sqrt(1 - M²)",
        "  - Corrected CL: CL_corrected = CL_incompressible / beta",
        "  - CD: Not corrected (conservative approach, CD effects are complex)",
        "",
        "Reference Conditions:",
        "  - Reference Mach: 0.2 (XFOIL simulation baseline)",
        "",
        "TARGET MACH NUMBERS",
        "-------------------",
    ]

    for flight in flight_conditions:
        lines.append(f"  - {flight.capitalize()}: M = {target_mach[flight]:.2f}")

    lines.extend([
        "",
        "CORRECTIONS APPLIED",
        "-------------------",
        f"Flight Conditions: {len(flight_conditions)}",
        f"Blade Sections: {len(blade_sections)}",
        f"Total Corrections: {len(flight_conditions)} × {len(blade_sections)} = {len(flight_conditions) * len(blade_sections)}",
        "",
        "RESULTS LOCATION",
        "----------------",
        f"Corrected data: {stage_dir}",
        "",
        "FILES GENERATED",
        "--------------",
        "For each flight condition × blade section:",
        "  - corrected_polar.csv: Complete corrected polar data",
        "  - corrected_cl_alpha.csv: Corrected CL vs alpha",
        "  - corrected_efficiency.csv: Corrected CL/CD vs alpha",
        "  - corrected_plots.png: Comparison plots (original vs corrected)",
        "",
        "NOTES",
        "-----",
        "- Corrections are applied to lift coefficient (CL) only.",
        "- Drag coefficient (CD) is not corrected (conservative approach).",
        "- Prandtl-Glauert is valid for subsonic flow (M < 0.8).",
        "- Higher Mach numbers show larger corrections (beta decreases).",
        "",
        "=" * 80,
    ])

    return "\n".join(lines)


def generate_stage4_summary(stage_dir: Path, metrics: List[Any]) -> str:
    """
    Generate summary for Stage 4: Performance Metrics and Tables.

    Parameters
    ----------
    stage_dir : Path
        Directory where Stage 4 results are stored.
    metrics : List[Any]
        List of computed aerodynamic metrics.

    Returns
    -------
    str
        Formatted summary text.
    """
    tables_dir = stage_dir / "tables"
    flight_conditions = get_flight_conditions()
    blade_sections = get_blade_sections()

    # Load summary table to get key statistics
    summary_file = tables_dir / "summary_table.csv"
    summary_stats = ""
    if summary_file.exists():
        try:
            df = pd.read_csv(summary_file)
            if not df.empty:
                max_eff = df["max_efficiency"].max()
                min_eff = df["max_efficiency"].min()
                avg_eff = df["max_efficiency"].mean()
                max_alpha_opt = df["alpha_opt_deg"].max()
                min_alpha_opt = df["alpha_opt_deg"].min()
                avg_alpha_opt = df["alpha_opt_deg"].mean()

                summary_stats = f"""
KEY STATISTICS
--------------
Maximum Efficiency (CL/CD):
  - Maximum: {max_eff:.2f}
  - Minimum: {min_eff:.2f}
  - Average: {avg_eff:.2f}

Optimal Angle of Attack (alpha_opt):
  - Maximum: {max_alpha_opt:.2f}°
  - Minimum: {min_alpha_opt:.2f}°
  - Average: {avg_alpha_opt:.2f}°

Note: alpha_opt is computed using the SECOND efficiency peak (alpha >= 3°),
      which represents the relevant operating condition for turbomachinery.
      The first peak is typically an artifact of laminar separation bubble.
"""

        except Exception:
            pass

    lines = [
        "=" * 80,
        "STAGE 4: PERFORMANCE METRICS AND TABLES - FINAL RESULTS",
        "=" * 80,
        "",
        "OBJECTIVE",
        "--------",
        "Compute key aerodynamic performance metrics from simulation results and",
        "export comprehensive summary tables for analysis and LaTeX integration.",
        "",
        "METRICS COMPUTED",
        "---------------",
        "For each flight condition × blade section combination:",
        "  - Maximum Efficiency: (CL/CD)_max",
        "  - Optimal Angle of Attack: alpha_opt = argmax(CL/CD) for alpha >= 3°",
        "    (Second efficiency peak, relevant for turbomachinery)",
        "  - Maximum Lift Coefficient: CL_max",
        "  - Lift at Optimal Angle: CL_at_opt",
        "  - Drag at Optimal Angle: CD_at_opt",
        "",
        "IMPORTANT NOTE ON ALPHA_OPT",
        "---------------------------",
        "The optimal angle of attack is computed using the SECOND efficiency peak",
        "(ignoring alpha < 3°). This is because:",
        "  - The first CL/CD peak at low alpha is typically an artifact of",
        "    laminar separation bubble effects.",
        "  - The second peak represents the actual relevant operating condition",
        "    for turbomachinery applications.",
        "  - This approach ensures realistic optimal incidence angles for fan",
        "    blade design.",
        "",
    ]

    if summary_stats:
        lines.append(summary_stats)

    lines.extend([
        "TABLES GENERATED",
        "---------------",
        f"Location: {tables_dir}",
        "",
        "Generated Tables:",
        "  - summary_table.csv: Comprehensive summary with all metrics",
        "  - efficiency_by_condition.csv: Maximum efficiency by condition and section",
        "  - alpha_opt_by_condition.csv: Optimal angle of attack by condition",
        "  - alpha_opt_second_peak.csv: Optimal angle (second peak) with details",
        "  - clcd_max_by_section.csv: Maximum CL/CD by blade section",
        "",
        "METRICS SUMMARY",
        "--------------",
        f"Total Cases Analyzed: {len(metrics)}",
        f"  - Flight Conditions: {len(flight_conditions)}",
        f"  - Blade Sections: {len(blade_sections)}",
        "",
        "USAGE",
        "-----",
        "All tables are in CSV format and can be directly imported into LaTeX",
        "using packages such as csvsimple or pgfplotstable.",
        "",
        "=" * 80,
    ])

    return "\n".join(lines)


def generate_stage5_summary(stage_dir: Path) -> str:
    """
    Generate summary for Stage 5: Figure Generation.

    Parameters
    ----------
    stage_dir : Path
        Directory where Stage 5 results are stored.

    Returns
    -------
    str
        Formatted summary text.
    """
    figures_dir = stage_dir / "figures"
    flight_conditions = get_flight_conditions()
    blade_sections = get_blade_sections()

    # Count generated figures
    num_figures = 0
    if figures_dir.exists():
        num_figures = len(list(figures_dir.glob("*.png")))

    lines = [
        "=" * 80,
        "STAGE 5: PUBLICATION-QUALITY FIGURES - FINAL RESULTS",
        "=" * 80,
        "",
        "OBJECTIVE",
        "--------",
        "Generate high-quality figures suitable for inclusion in academic thesis",
        "and publications. All figures are created with professional formatting,",
        "clear labels, units, and legends.",
        "",
        "FIGURE SPECIFICATIONS",
        "---------------------",
        "  - Resolution: 300 DPI (publication quality)",
        "  - Format: PNG",
        "  - Size: 6.0 × 4.5 inches (standard academic format)",
        "  - Grid: Enabled for readability",
        "  - Labels: Clear axis labels with units",
        "  - Legends: Included for multi-curve plots",
        "",
        "FIGURES GENERATED",
        "----------------",
        f"Total Figures: {num_figures}",
        "",
        "Individual Plots (per flight condition × blade section):",
        "  - cl_alpha_{condition}_{section}.png: CL vs alpha",
        "  - cd_alpha_{condition}_{section}.png: CD vs alpha",
        "  - efficiency_{condition}_{section}.png: CL/CD vs alpha with maximum",
        "  - polar_{condition}_{section}.png: Polar curve (CL vs CD)",
        "",
        "Summary Plots:",
        "  - alpha_opt_vs_condition.png: Optimal angle vs flight condition",
        "  - efficiency_vs_reynolds_{condition}.png: Efficiency vs Reynolds",
        "  - efficiency_by_section_{condition}.png: Efficiency comparison by section",
        "",
        "RESULTS LOCATION",
        "----------------",
        f"All figures: {figures_dir}",
        "",
        "USAGE",
        "-----",
        "Figures can be directly included in LaTeX documents using:",
        "  \\includegraphics[width=0.8\\textwidth]{path/to/figure.png}",
        "",
        "=" * 80,
    ]

    return "\n".join(lines)


def generate_stage6_summary(stage_dir: Path) -> str:
    """
    Generate summary for Stage 6: Variable Pitch Fan Analysis.

    Parameters
    ----------
    stage_dir : Path
        Directory where Stage 6 results are stored.

    Returns
    -------
    str
        Formatted summary text.
    """
    tables_dir = stage_dir.parent / "stage_4" / "tables"
    figures_dir = stage_dir / "figures"

    # Try to load VPF results
    optimal_pitch_file = tables_dir / "vpf_optimal_pitch.csv"
    pitch_adjustment_file = tables_dir / "vpf_pitch_adjustment.csv"

    vpf_stats = ""
    if optimal_pitch_file.exists():
        try:
            df_opt = pd.read_csv(optimal_pitch_file)
            if not df_opt.empty:
                avg_alpha_opt = df_opt["alpha_opt"].mean()
                max_alpha_opt = df_opt["alpha_opt"].max()
                min_alpha_opt = df_opt["alpha_opt"].min()
                avg_clcd = df_opt["CL_CD_max"].mean()

                vpf_stats = f"""
KEY RESULTS
-----------
Optimal Angle of Attack (alpha_opt):",
  - Average: {avg_alpha_opt:.2f}°",
  - Range: {min_alpha_opt:.2f}° to {max_alpha_opt:.2f}°",
  - Maximum Efficiency (CL/CD): {avg_clcd:.2f} (average)",
"""

        except Exception:
            pass

    lines = [
        "=" * 80,
        "STAGE 6: VARIABLE PITCH FAN (VPF) ANALYSIS - FINAL RESULTS",
        "=" * 80,
        "",
        "OBJECTIVE",
        "--------",
        "Analyze how optimal aerodynamic incidence varies across flight conditions",
        "and demonstrate how a Variable Pitch Fan (VPF) could maintain optimal",
        "efficiency by adjusting blade pitch to match changing flow conditions.",
        "",
        "PHYSICAL PRINCIPLE",
        "-----------------",
        "In a turbofan fan, the optimal angle of attack (alpha_opt) varies with:",
        "  - Flight condition (altitude, velocity, engine power)",
        "  - Blade section (root, mid-span, tip)",
        "  - Reynolds number",
        "",
        "A Variable Pitch Fan can adjust blade pitch to maintain optimal",
        "incidence, maximizing aerodynamic efficiency (CL/CD) across all",
        "operating conditions.",
        "",
        "METHODOLOGY",
        "-----------",
        "  - Compute optimal incidence (alpha_opt) for each condition/section",
        "    using the SECOND efficiency peak (alpha >= 3°)",
        "  - Use cruise condition as reference",
        "  - Calculate pitch adjustment: delta_pitch = alpha_opt_condition - alpha_opt_cruise",
        "  - Analyze efficiency improvements from optimal pitch",
        "",
    ]

    if vpf_stats:
        lines.append(vpf_stats)

    lines.extend([
        "RESULTS LOCATION",
        "----------------",
        f"Figures: {figures_dir}",
        f"Tables: {tables_dir}",
        "",
        "FILES GENERATED",
        "--------------",
        "Tables:",
        "  - vpf_optimal_pitch.csv: Optimal angle of attack for each condition",
        "  - vpf_pitch_adjustment.csv: Required pitch adjustments relative to cruise",
        "",
        "Figures:",
        "  - alpha_opt_vs_condition.png: Optimal angle vs flight condition",
        "  - pitch_adjustment_vs_condition.png: Required pitch adjustment",
        "  - efficiency_curves_with_opt.png: Efficiency curves with optimal points",
        "  - section_comparison.png: Comparison across blade sections",
        "",
        "INTERPRETATION",
        "-------------",
        "Positive pitch adjustment indicates the blade should be rotated to",
        "increase angle of attack relative to cruise condition.",
        "",
        "Negative pitch adjustment indicates the blade should be rotated to",
        "decrease angle of attack relative to cruise condition.",
        "",
        "The magnitude of adjustment shows how much pitch change is needed to",
        "maintain optimal efficiency.",
        "",
        "=" * 80,
    ])

    return "\n".join(lines)


def generate_stage7_summary(stage_dir: Path) -> str:
    """
    Generate summary for Stage 8: SFC Impact Analysis.

    Parameters
    ----------
    stage_dir : Path
        Directory where Stage 8 results are stored.

    Returns
    -------
    str
        Formatted summary text.
    """
    tables_dir = stage_dir.parent / "stage_4" / "tables"
    figures_dir = stage_dir / "figures"
    summary_file = stage_dir / "sfc_analysis_summary.txt"

    # Try to load SFC results
    sfc_file = tables_dir / "sfc_analysis.csv"
    sfc_stats = ""
    if sfc_file.exists():
        try:
            df = pd.read_csv(sfc_file)
            if not df.empty and "sfc_reduction_percent" in df.columns:
                avg_reduction = df["sfc_reduction_percent"].mean()
                max_reduction = df["sfc_reduction_percent"].max()
                sfc_stats = f"""
KEY RESULTS
-----------
Average SFC Reduction: {avg_reduction:.2f}%",
Maximum SFC Reduction: {max_reduction:.2f}%",
"""
        except Exception:
            pass

    lines = [
        "=" * 80,
        "STAGE 7: SPECIFIC FUEL CONSUMPTION (SFC) IMPACT ANALYSIS - FINAL RESULTS",
        "=" * 80,
        "",
        "OBJECTIVE",
        "--------",
        "Estimate the impact of Variable Pitch Fan (VPF) aerodynamic improvements",
        "on overall turbofan engine Specific Fuel Consumption (SFC). This stage",
        "connects fan blade aerodynamic efficiency with engine-level fuel",
        "consumption performance.",
        "",
        "PHYSICAL PRINCIPLE",
        "-----------------",
        "Specific Fuel Consumption (SFC) = fuel_flow / thrust",
        "",
        "Lower SFC indicates better propulsion efficiency. Improving fan",
        "aerodynamic efficiency (CL/CD) can improve:",
        "  - Fan efficiency",
        "  - Propulsive efficiency",
        "  - Overall engine SFC",
        "",
        "METHODOLOGY",
        "-----------",
        "Simplified Propulsion Model:",
        "  - Fan efficiency improvement: eta_fan_new = eta_fan_baseline × (CL_CD_new / CL_CD_baseline)",
        "  - SFC reduction: SFC_new = SFC_baseline / (1 + efficiency_gain)",
        "",
        "Baseline Engine Parameters:",
        "  - Baseline SFC (cruise): ~0.55 lb/(lbf·hr)",
        "  - Baseline fan efficiency: ~0.88",
        "  - Bypass ratio: ~10.0",
        "",
    ]

    if sfc_stats:
        lines.append(sfc_stats)

    lines.extend([
        "RESULTS LOCATION",
        "----------------",
        f"Figures: {figures_dir}",
        f"Tables: {tables_dir}",
        f"Summary: {summary_file}",
        "",
        "FILES GENERATED",
        "--------------",
        "Tables:",
        "  - sfc_analysis.csv: SFC analysis results for all flight conditions",
        "",
        "Figures:",
        "  - sfc_vs_condition.png: SFC comparison (baseline vs VPF)",
        "  - sfc_reduction_percent.png: Percentage SFC reduction",
        "  - fan_efficiency_improvement.png: Fan efficiency gains",
        "  - efficiency_vs_sfc.png: Aerodynamic efficiency vs SFC relationship",
        "",
        "INTERPRETATION",
        "-------------",
        "The analysis shows estimated SFC reductions achievable through VPF",
        "implementation. These are simplified estimates based on:",
        "  - Proportional relationship between aerodynamic and fan efficiency",
        "  - Simplified propulsion model",
        "  - Representative baseline engine parameters",
        "",
        "Actual SFC improvements would depend on:",
        "  - Engine design details",
        "  - Operating point",
        "  - Integration with other engine systems",
        "",
        "=" * 80,
    ])

    return "\n".join(lines)


def write_stage_summary(stage_num: int, summary_text: str, stage_dir: Path) -> None:
    """
    Write stage summary to finalresults_stageX.txt file.

    Parameters
    ----------
    stage_num : int
        Stage number (1-8).
    summary_text : str
        Summary text content.
    stage_dir : Path
        Directory where the summary file should be written.
    """
    stage_dir.mkdir(parents=True, exist_ok=True)
    summary_file = stage_dir / f"finalresults_stage{stage_num}.txt"
    summary_file.write_text(summary_text, encoding="utf-8")
