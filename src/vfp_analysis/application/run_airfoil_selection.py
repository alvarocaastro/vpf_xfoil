from __future__ import annotations

from pathlib import Path

from vfp_analysis import config
from vfp_analysis.adapters.xfoil.xfoil_runner_adapter import XfoilRunnerAdapter
from vfp_analysis.core.domain.airfoil import Airfoil
from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.core.services.airfoil_selection_service import (
    AirfoilSelectionService,
)


def _build_airfoils() -> list[Airfoil]:
    airfoils: list[Airfoil] = []
    for spec in config.AIRFOILS:
        dat_path = config.AIRFOIL_DATA_DIR / spec["dat_file"]
        airfoils.append(
            Airfoil(
                name=spec["name"],
                family=spec["family"],
                dat_path=dat_path,
            )
        )
    return airfoils


def main() -> None:
    config.ensure_directories()

    selection_condition = SimulationCondition(
        name="Selection",
        mach_rel=config.MACH_DEFAULT,
        reynolds=3.0e6,
        alpha_min=-5.0,
        alpha_max=20.0,
        alpha_step=0.15,
        ncrit=7.0,  # Valor representativo de entorno relativamente limpio (similar a crucero)
    )

    xfoil = XfoilRunnerAdapter()
    service = AirfoilSelectionService(xfoil_runner=xfoil, results_dir=config.RESULTS_DIR)

    airfoils = _build_airfoils()
    result = service.run_selection(airfoils, selection_condition)

    print(f"Best airfoil: {result.best_airfoil.name}")


if __name__ == "__main__":
    main()

