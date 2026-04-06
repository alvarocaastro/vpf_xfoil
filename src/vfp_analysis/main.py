from __future__ import annotations

import logging

from . import config
from .application.run_airfoil_selection import main as run_airfoil_selection
from .application.run_final_simulations import main as run_final_simulations
from .compressibility.application.run_compressibility_stage import main as run_compressibility_stage


def _configure_logging() -> None:
    """Configure a simple console logger suitable for development."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    """
    Orquesta el flujo completo:
    1) Selección automática de perfil.
    2) Análisis final con el perfil seleccionado.
    3) Corrección de compresibilidad (postprocesado).
    """

    _configure_logging()
    config.ensure_directories()

    logging.info("=== Stage 1: Selección de perfil ===")
    run_airfoil_selection()

    logging.info("=== Stage 2–4: Análisis final con perfil seleccionado ===")
    run_final_simulations()

    logging.info("=== Stage 5: Corrección de compresibilidad ===")
    run_compressibility_stage()


if __name__ == "__main__":
    main()

