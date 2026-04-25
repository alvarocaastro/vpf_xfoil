"""SFC improvement model: Cl/Cd efficiency gain → fuel burn reduction.

Hypothesis: F_required ∝ 1/(Cl/Cd). A higher Cl/Cd reduces drag per unit lift,
so the motor runs at reduced throttle → slight SFC degradation at part power,
but net fuel burn falls because less thrust is needed.

Reference: Walsh & Fletcher, Gas Turbine Performance (Blackwell, 2004),
Chapter 8 — part-power SFC behaviour.
"""

from __future__ import annotations


def compute_sfc_improvement(
    ClCd_ref: float,
    ClCd_new: float,
    SFC_design: float,
    k_throttle: float = 0.08,
) -> dict:
    """Estimate fuel burn improvement when Cl/Cd increases from ref to new.

    Parameters
    ----------
    ClCd_ref : float
        Reference Cl/Cd (fixed-pitch or unoptimised operating point).
    ClCd_new : float
        Improved Cl/Cd (variable-pitch optimised).
    SFC_design : float
        Engine SFC at design (cruise) point [kg/N·s].
    k_throttle : float
        Part-power SFC degradation coefficient (default 0.08 per W&F).
        SFC at partial throttle = SFC_design * (1 + k_throttle * (1 - F_ratio)).

    Returns
    -------
    dict with keys:
        ClCd_ref, ClCd_new, F_ratio,
        SFC_design_kgNs, SFC_new_kgNs,
        SFC_improvement_pct  — pure SFC change at new throttle setting
        fuel_saving_pct      — net change in fuel mass flow (SFC × F)
        delta_SFC_kgNs
    """
    F_ratio   = ClCd_ref / ClCd_new          # F_new / F_ref (<1 if Cl/Cd improved)
    SFC_new   = SFC_design * (1.0 + k_throttle * (1.0 - F_ratio))

    mdot_ref  = SFC_design * 1.0             # normalised: F_ref = 1 N
    mdot_new  = SFC_new * F_ratio

    fuel_saving_pct      = (1.0 - mdot_new / mdot_ref) * 100.0
    SFC_improvement_pct  = (1.0 - SFC_new / SFC_design) * 100.0

    return {
        "ClCd_ref":           ClCd_ref,
        "ClCd_new":           ClCd_new,
        "F_ratio":            F_ratio,
        "SFC_design_kgNs":    SFC_design,
        "SFC_new_kgNs":       SFC_new,
        "SFC_improvement_pct": SFC_improvement_pct,
        "fuel_saving_pct":    fuel_saving_pct,
        "delta_SFC_kgNs":     SFC_new - SFC_design,
    }
