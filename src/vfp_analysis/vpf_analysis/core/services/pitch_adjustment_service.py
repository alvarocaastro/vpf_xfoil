"""
Service for computing pitch adjustments relative to a reference condition.
"""

from __future__ import annotations

from typing import List

from vfp_analysis.vpf_analysis.core.domain.optimal_incidence import (
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
        List of optimal incidence angles for all conditions.
    reference_condition : str
        Reference condition (typically "cruise").

    Returns
    -------
    List[PitchAdjustment]
        List of pitch adjustments for all conditions.
    """
    # Build lookup: (condition, section) -> alpha_opt
    reference_alpha: dict[tuple[str, str], float] = {}

    for inc in optimal_incidences:
        if inc.condition == reference_condition:
            reference_alpha[(inc.condition, inc.section)] = inc.alpha_opt

    adjustments: List[PitchAdjustment] = []

    for inc in optimal_incidences:
        key = (reference_condition, inc.section)
        if key in reference_alpha:
            alpha_ref = reference_alpha[key]
            delta_pitch = inc.alpha_opt - alpha_ref
        else:
            # If no reference for this section, use 0
            delta_pitch = 0.0

        adjustments.append(
            PitchAdjustment(
                condition=inc.condition,
                section=inc.section,
                alpha_opt=inc.alpha_opt,
                delta_pitch=delta_pitch,
            )
        )

    return adjustments
