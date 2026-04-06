"""
Domain models for optimal incidence analysis.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptimalIncidence:
    """Optimal angle of attack for a specific flight condition and blade section."""

    condition: str
    section: str
    reynolds: float
    mach: float
    alpha_opt: float  # Optimal angle of attack (from second efficiency peak)
    cl_cd_max: float  # Maximum efficiency at optimal angle


@dataclass(frozen=True)
class PitchAdjustment:
    """Pitch adjustment required relative to a reference condition."""

    condition: str
    section: str
    alpha_opt: float
    delta_pitch: float  # Pitch adjustment relative to reference (typically cruise)
