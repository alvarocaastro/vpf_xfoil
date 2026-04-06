from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationCondition:
    """
    Single aerodynamic simulation condition.

    Parameters
    ----------
    ncrit : float
        Transition parameter used by XFOIL (Ncrit).
        Lower values (4–6) represent more turbulent environments such as
        turbofan fans; higher values (~9) correspond to very clean tunnels.
    """

    name: str
    mach_rel: float
    reynolds: float
    alpha_min: float
    alpha_max: float
    alpha_step: float
    ncrit: float


