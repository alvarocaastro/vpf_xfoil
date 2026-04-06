"""
Domain model for corrected aerodynamic polar data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CorrectedPolar:
    """Corrected aerodynamic polar data."""

    alpha: float
    cl_corrected: float
    cd_original: float
    cd_corrected: Optional[float]
    ld_corrected: float
    mach_corrected: float
