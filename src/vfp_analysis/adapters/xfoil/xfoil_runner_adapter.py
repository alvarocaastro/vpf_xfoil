"""
xfoil_runner_adapter.py
------------------------
Adaptador entre el dominio (SimulationCondition) y el servicio de XFOIL.

Convierte un SimulationCondition en XfoilPolarRequest y delega a
run_xfoil_polar. Los timeouts y número de reintentos se leen de
PipelineSettings para no tener valores dispersos por el código.
"""

from __future__ import annotations

import logging
from pathlib import Path

from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.settings import get_settings
from vfp_analysis.xfoil_runner import XfoilPolarRequest, XfoilPolarResult, run_xfoil_polar

LOGGER = logging.getLogger(__name__)


class XfoilRunnerAdapter:
    """Adaptador XFOIL con timeouts y reintentos leídos de PipelineSettings.

    Parameters
    ----------
    timeout_override : float, optional
        Timeout por intento [s]. Si se omite se usa el valor del stage:
        - Stage 1 (selección) → ``XfoilSettings.TIMEOUT_SELECTION_S``
        - Stage 2 (análisis final) → ``XfoilSettings.TIMEOUT_FINAL_S``
    max_retries_override : int, optional
        Anula el valor de ``XfoilSettings.MAX_RETRIES``.
    final_analysis : bool
        True → usa TIMEOUT_FINAL_S (Stage 2); False → TIMEOUT_SELECTION_S.
    """

    def __init__(
        self,
        timeout_override: float | None = None,
        max_retries_override: int | None = None,
        final_analysis: bool = True,
    ) -> None:
        cfg = get_settings().xfoil
        if timeout_override is not None:
            self._timeout = timeout_override
        elif final_analysis:
            self._timeout = cfg.TIMEOUT_FINAL_S
        else:
            self._timeout = cfg.TIMEOUT_SELECTION_S

        self._max_retries = (
            max_retries_override
            if max_retries_override is not None
            else cfg.MAX_RETRIES
        )

    def run_polar(
        self,
        airfoil_dat: Path,
        condition: SimulationCondition,
        output_file: Path,
    ) -> XfoilPolarResult:
        """Calcula el polar para la condición dada.

        Parameters
        ----------
        airfoil_dat : Path
            Fichero .dat del perfil aerodinámico.
        condition : SimulationCondition
            Re, Mach, Ncrit, rango de alpha.
        output_file : Path
            Destino del fichero polar XFOIL (.dat texto).

        Returns
        -------
        XfoilPolarResult
            Incluye tasa de convergencia y lista de alpha fallidos.
        """
        request = XfoilPolarRequest(
            airfoil_dat=airfoil_dat,
            re=condition.reynolds,
            alpha_start=condition.alpha_min,
            alpha_end=condition.alpha_max,
            alpha_step=condition.alpha_step,
            mach=condition.mach_rel,
            n_crit=condition.ncrit,
            output_file=output_file,
        )
        result = run_xfoil_polar(
            request,
            timeout=self._timeout,
            max_retries=self._max_retries,
        )
        if result.convergence_failures > 0:
            LOGGER.warning(
                "Polar %s/%s: %d puntos no convergidos (tasa=%.0f%%)",
                getattr(condition, "name", "?"),
                output_file.stem,
                result.convergence_failures,
                result.convergence_rate * 100,
            )
        return result
