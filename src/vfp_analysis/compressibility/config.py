"""
Configuration for compressibility correction postprocessing.

This module defines target Mach numbers per flight condition and correction
model parameters. The original XFOIL results were generated at Mach 0.2 due
to solver limitations; compressibility corrections are applied afterward.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from vfp_analysis import config as base_config

# Target Mach numbers for each flight condition
TARGET_MACH: Final[dict[str, float]] = {
    "Takeoff": 0.30,
    "Climb": 0.70,
    "Cruise": 0.85,
    "Descent": 0.75,
}

# Reference Mach from XFOIL simulations
REFERENCE_MACH: Final[float] = 0.2

# Output directory for corrected results
CORRECTED_RESULTS_DIR: Final[Path] = base_config.RESULTS_DIR / "compressibility_correction"
