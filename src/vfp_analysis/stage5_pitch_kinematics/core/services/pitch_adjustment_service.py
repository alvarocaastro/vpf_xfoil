"""
pitch_adjustment_service.py
---------------------------
Calcula el ajuste de paso aerodinámico relativo a la condición de referencia.

  Δα(condición, sección) = α_opt(condición, sección) − α_opt(crucero, sección)

Un Δα positivo significa que la pala debe girar hacia mayor ángulo de ataque
respecto al ajuste de crucero; negativo, hacia menor ángulo.
"""

from __future__ import annotations

from typing import List

from vfp_analysis.stage5_pitch_kinematics.core.domain.pitch_kinematics_result import (
    OptimalIncidence,
    PitchAdjustment,
)


def compute_pitch_adjustments(
    optimal_incidences: List[OptimalIncidence],
    reference_condition: str = "cruise",
) -> List[PitchAdjustment]:
    """
    Calcula los ajustes de paso relativos a una condición de referencia.

    Parameters
    ----------
    optimal_incidences : List[OptimalIncidence]
    reference_condition : str
        Condición de referencia (por defecto "cruise").

    Returns
    -------
    List[PitchAdjustment]
    """
    reference_alpha: dict[tuple[str, str], float] = {
        (inc.condition, inc.section): inc.alpha_opt
        for inc in optimal_incidences
        if inc.condition == reference_condition
    }

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
