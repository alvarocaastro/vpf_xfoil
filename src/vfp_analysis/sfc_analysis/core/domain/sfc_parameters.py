"""
Domain models for SFC impact analysis.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EngineBaseline:
    """Baseline engine parameters for SFC analysis."""

    baseline_sfc: float  # lb/(lbf·hr) or kg/(kN·hr)
    fan_efficiency: float  # Baseline fan efficiency (0-1)
    bypass_ratio: float
    cruise_velocity: float  # m/s
    jet_velocity: float  # m/s


@dataclass(frozen=True)
class SfcAnalysisResult:
    """SFC analysis result for a flight condition."""

    condition: str
    cl_cd_baseline: float  # Baseline aerodynamic efficiency
    cl_cd_vpf: float  # VPF aerodynamic efficiency
    fan_efficiency_baseline: float
    fan_efficiency_new: float
    sfc_baseline: float
    sfc_new: float
    sfc_reduction_percent: float
