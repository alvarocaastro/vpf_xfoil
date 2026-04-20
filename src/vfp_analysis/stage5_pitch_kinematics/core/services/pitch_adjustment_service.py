"""
pitch_adjustment_service.py
---------------------------
Computes the aerodynamic pitch adjustment relative to the reference condition.

  Δα(condition, section) = α_opt(condition, section) − α_opt(cruise, section)

A positive Δα means the blade must rotate toward a higher angle of attack
relative to the cruise setting; negative, toward a lower angle.
"""

from __future__ import annotations

import logging
import warnings
from typing import List

_LOG = logging.getLogger(__name__)

from vfp_analysis.stage5_pitch_kinematics.core.domain.pitch_kinematics_result import (
    OptimalIncidence,
    PitchAdjustment,
)


def compute_pitch_adjustments(
    optimal_incidences: List[OptimalIncidence],
    reference_condition: str = "cruise",
) -> List[PitchAdjustment]:
    """
    Compute pitch adjustments relative to a reference condition.

    Parameters
    ----------
    optimal_incidences : List[OptimalIncidence]
    reference_condition : str
        Reference condition (default: "cruise").

    Returns
    -------
    List[PitchAdjustment]
    """
    reference_alpha: dict[tuple[str, str], float] = {
        (inc.condition, inc.section): inc.alpha_opt
        for inc in optimal_incidences
        if inc.condition == reference_condition
    }

    if not reference_alpha:
        warnings.warn(
            f"compute_pitch_adjustments: no data found for reference_condition="
            f"'{reference_condition}'. All delta_pitch values will be 0.",
            RuntimeWarning,
            stacklevel=2,
        )
        _LOG.warning(
            "No optimal incidences found for reference condition '%s'; "
            "pitch adjustments will all be zero.",
            reference_condition,
        )

    adjustments: List[PitchAdjustment] = []
    for inc in optimal_incidences:
        key         = (reference_condition, inc.section)
        alpha_ref   = reference_alpha.get(key, inc.alpha_opt)
        delta_pitch = inc.alpha_opt - alpha_ref
        adjustments.append(
            PitchAdjustment(
                condition=inc.condition,
                section=inc.section,
                alpha_opt=inc.alpha_opt,
                delta_pitch=delta_pitch,
            )
        )

    return adjustments
