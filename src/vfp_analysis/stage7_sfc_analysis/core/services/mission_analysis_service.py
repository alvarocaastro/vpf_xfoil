"""
mission_analysis_service.py
---------------------------
Full mission integration: converts per-condition SFC reductions into actual
fuel savings, CO₂ reduction and economic cost saving over a typical mission.

Modelo físico:
    thrust(phase) = design_thrust_kN × thrust_fraction(phase)
    thrust_lbf    = thrust_kN × LB_PER_KN
    fuel_flow     = SFC(phase) × thrust_lbf                [lb/hr]
    fuel_kg(phase)= fuel_flow × duration_hr × LB_TO_KG
    saving        = fuel_baseline − fuel_vpf
    CO₂_saving    = saving × CO2_FACTOR                    [CORSIA, kg CO₂/kg fuel]
    cost_saving   = saving × fuel_price_usd_per_kg

Ref: IATA (2024). Jet Fuel Price Monitor.
     CORSIA (2022). Methodology for Calculating Actual Life Cycle Emissions Values.
     Saravanamuttoo et al. (2017) §5.3.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

from vfp_analysis.stage7_sfc_analysis.core.domain.sfc_parameters import (
    MissionFuelBurnResult,
    MissionSummary,
    SfcAnalysisResult,
)

LOGGER = logging.getLogger(__name__)

# Conversion factors
_LB_TO_KG: float = 0.453592          # 1 lb = 0.453592 kg
_LB_PER_KN: float = 224.809          # 1 kN = 224.809 lbf
_CO2_FACTOR: float = 3.16            # kg CO₂ per kg of Jet-A1 burned (CORSIA)
_MIN_TO_HR: float = 1.0 / 60.0


def compute_mission_fuel_burn(
    sfc_results: List[SfcAnalysisResult],
    mission_profile: dict,
) -> Tuple[MissionSummary, List[MissionFuelBurnResult]]:
    """Compute the total mission fuel saving with VPF.

    Parameters
    ----------
    sfc_results : list[SfcAnalysisResult]
        Resultados de Stage 6 — SFC base y VPF por condición de vuelo.
    mission_profile : dict
        Perfil de misión cargado por ``config_loader.get_mission_profile()``.
        Estructura: {phases: {cond: {duration_min, thrust_fraction}},
                     design_thrust_kN, fuel_price_usd_per_kg}

    Returns
    -------
    summary : MissionSummary
        Totales agregados de la misión completa.
    phase_results : list[MissionFuelBurnResult]
        Desglose por fase.
    """
    sfc_map = {r.condition: r for r in sfc_results}

    design_thrust_kN: float = float(mission_profile.get("design_thrust_kN", 105.0))
    fuel_price: float = float(mission_profile.get("fuel_price_usd_per_kg", 0.90))
    phases: dict = mission_profile.get("phases", {})

    phase_results: List[MissionFuelBurnResult] = []

    for phase, params in phases.items():
        duration_min = float(params["duration_min"])
        thrust_fraction = float(params["thrust_fraction"])

        duration_hr = duration_min * _MIN_TO_HR
        thrust_kN = design_thrust_kN * thrust_fraction
        thrust_lbf = thrust_kN * _LB_PER_KN

        sfc_res = sfc_map.get(phase)
        if sfc_res is None:
            LOGGER.warning(
                "No SFC result for phase '%s' — omitted from mission analysis.", phase
            )
            continue

        fuel_baseline_kg = sfc_res.sfc_baseline * thrust_lbf * duration_hr * _LB_TO_KG
        fuel_vpf_kg = sfc_res.sfc_new * thrust_lbf * duration_hr * _LB_TO_KG
        fuel_saving_kg = fuel_baseline_kg - fuel_vpf_kg
        co2_saving_kg = fuel_saving_kg * _CO2_FACTOR
        cost_saving_usd = fuel_saving_kg * fuel_price

        LOGGER.info(
            "%s: thrust=%.1f kN, dur=%.1f min, fuel_base=%.1f kg, "
            "fuel_vpf=%.1f kg, saving=%.1f kg (%.2f%%)",
            phase, thrust_kN, duration_min,
            fuel_baseline_kg, fuel_vpf_kg, fuel_saving_kg,
            100.0 * fuel_saving_kg / fuel_baseline_kg if fuel_baseline_kg > 0 else 0.0,
        )

        phase_results.append(MissionFuelBurnResult(
            phase=phase,
            duration_min=duration_min,
            thrust_kN=thrust_kN,
            sfc_baseline=sfc_res.sfc_baseline,
            sfc_vpf=sfc_res.sfc_new,
            fuel_baseline_kg=fuel_baseline_kg,
            fuel_vpf_kg=fuel_vpf_kg,
            fuel_saving_kg=fuel_saving_kg,
            co2_saving_kg=co2_saving_kg,
            cost_saving_usd=cost_saving_usd,
        ))

    if not phase_results:
        LOGGER.error("No mission phase could be computed.")
        empty = MissionSummary(0, 0, 0, 0, 0, 0, [])
        return empty, []

    total_baseline = sum(p.fuel_baseline_kg for p in phase_results)
    total_vpf = sum(p.fuel_vpf_kg for p in phase_results)
    total_saving = sum(p.fuel_saving_kg for p in phase_results)
    total_co2 = sum(p.co2_saving_kg for p in phase_results)
    total_cost = sum(p.cost_saving_usd for p in phase_results)
    saving_pct = 100.0 * total_saving / total_baseline if total_baseline > 0 else 0.0

    LOGGER.info(
        "MISSION TOTAL: base=%.1f kg, VPF=%.1f kg, saving=%.1f kg (%.2f%%), "
        "CO₂=%.1f kg, cost=$%.2f",
        total_baseline, total_vpf, total_saving, saving_pct, total_co2, total_cost,
    )

    summary = MissionSummary(
        total_fuel_baseline_kg=total_baseline,
        total_fuel_vpf_kg=total_vpf,
        total_fuel_saving_kg=total_saving,
        total_fuel_saving_pct=saving_pct,
        total_co2_saving_kg=total_co2,
        total_cost_saving_usd=total_cost,
        phase_results=phase_results,
    )
    return summary, phase_results
