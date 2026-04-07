"""
Service for performing complete SFC impact analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd
import yaml

from vfp_analysis.config_loader import get_flight_conditions
from vfp_analysis.sfc_analysis.core.domain.sfc_parameters import (
    EngineBaseline,
    SfcAnalysisResult,
)
from vfp_analysis.sfc_analysis.core.services.propulsion_model_service import (
    compute_fan_efficiency_improvement,
    compute_sfc_improvement,
    compute_sfc_reduction_percent,
)


def compute_sfc_analysis(
    optimal_pitch_df: pd.DataFrame,
    engine_baseline: EngineBaseline,
    config_path: Path | None = None,
) -> List[SfcAnalysisResult]:
    """
    Compute SFC analysis for all flight conditions.

    Parameters
    ----------
    optimal_pitch_df : pd.DataFrame
        Optimal pitch data with CL_CD_max values.
    engine_baseline : EngineBaseline
        Baseline engine parameters.
    config_path : Path, optional
        Path to engine configuration for SFC multipliers.

    Returns
    -------
    List[SfcAnalysisResult]
        SFC analysis results for all conditions.
    """
    # Load SFC multipliers if available
    sfc_multipliers: dict[str, float] = {}
    if config_path and config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            sfc_multipliers = config.get("sfc_multipliers", {})

    flight_conditions = get_flight_conditions()

    # Compute baseline CL/CD (use cruise as reference)
    reference_condition = "cruise"
    baseline_cl_cd = _get_baseline_cl_cd(optimal_pitch_df, reference_condition)

    results: List[SfcAnalysisResult] = []

    for condition in flight_conditions:
        # Get VPF CL/CD for this condition (average across sections)
        vpf_cl_cd = _get_vpf_cl_cd(optimal_pitch_df, condition)

        if vpf_cl_cd <= 0 or baseline_cl_cd <= 0:
            continue

        # Compute fan efficiency improvement
        fan_efficiency_new = compute_fan_efficiency_improvement(
            baseline_cl_cd,
            vpf_cl_cd,
            engine_baseline.fan_efficiency,
        )

        # Compute efficiency gain factor (based on dampened fan efficiency, NOT raw 2D profile)
        efficiency_gain = (fan_efficiency_new - engine_baseline.fan_efficiency) / engine_baseline.fan_efficiency

        # Get SFC baseline for this condition
        sfc_multiplier = sfc_multipliers.get(condition, 1.0)
        sfc_baseline = engine_baseline.baseline_sfc * sfc_multiplier

        # Compute improved SFC
        sfc_new = compute_sfc_improvement(sfc_baseline, efficiency_gain)

        # Compute reduction percentage
        sfc_reduction = compute_sfc_reduction_percent(sfc_baseline, sfc_new)

        results.append(
            SfcAnalysisResult(
                condition=condition,
                cl_cd_baseline=baseline_cl_cd,
                cl_cd_vpf=vpf_cl_cd,
                fan_efficiency_baseline=engine_baseline.fan_efficiency,
                fan_efficiency_new=fan_efficiency_new,
                sfc_baseline=sfc_baseline,
                sfc_new=sfc_new,
                sfc_reduction_percent=sfc_reduction,
            )
        )

    return results


def _get_baseline_cl_cd(df: pd.DataFrame, reference_condition: str) -> float:
    """Get baseline CL/CD from reference condition (average across sections)."""
    ref_data = df[df["condition"] == reference_condition]
    if ref_data.empty:
        # Fallback: use overall average
        if "CL_CD_max" in df.columns:
            return float(df["CL_CD_max"].mean())
        elif "ld_max" in df.columns:
            return float(df["ld_max"].mean())
        return 0.0

    if "CL_CD_max" in ref_data.columns:
        return float(ref_data["CL_CD_max"].mean())
    elif "ld_max" in ref_data.columns:
        return float(ref_data["ld_max"].mean())
    return 0.0


def _get_vpf_cl_cd(df: pd.DataFrame, condition: str) -> float:
    """Get VPF CL/CD for a condition (average across sections)."""
    cond_data = df[df["condition"] == condition]
    if cond_data.empty:
        return 0.0

    if "CL_CD_max" in cond_data.columns:
        return float(cond_data["CL_CD_max"].mean())
    elif "ld_max" in cond_data.columns:
        return float(cond_data["ld_max"].mean())
    return 0.0
