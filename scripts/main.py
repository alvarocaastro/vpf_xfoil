"""
Entrypoint principal del proyecto VFP Analysis.

Este script ejecuta el pipeline completo de análisis aerodinámico:
- Stage 1: Selección de perfil óptimo
- Stage 2: Análisis XFOIL a Mach 0.2
- Stage 3: Corrección de compresibilidad

Uso:
    python scripts/main.py
    o
    python -m scripts.main
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Añadir src/ al path para imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from vfp_analysis.run_complete_pipeline import main as run_complete_pipeline


def _configure_logging() -> None:
    """Configura logging para el pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    """Entrypoint principal: ejecuta el pipeline completo integrado."""
    _configure_logging()
    run_complete_pipeline()


if __name__ == "__main__":
    main()
