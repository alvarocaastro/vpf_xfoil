"""
xfoil_runner.py
---------------
Servicio de integración con XFOIL: construcción del script interactivo,
ejecución del subproceso, reintentos y detección de convergencia.

Características
---------------
- Retry automático ante TimeoutExpired o código de salida distinto de cero
  (configurable vía ``max_retries``).
- Detección de fallos de convergencia desde el stdout de XFOIL, registrados
  como warnings sin detener el pipeline.
- Mensajes de error contextuales que indican perfil, condición y motivo del
  fallo, facilitando el diagnóstico.
- Separación clara entre la lógica de comunicación (este módulo) y el
  parseo del fichero de salida (``xfoil_parser.py``).
"""

from __future__ import annotations

import logging
import time
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, List

from .config import (
    AIRFOIL_DATA_DIR,
    MACH_DEFAULT,
    N_CRIT_DEFAULT,
    XFOIL_EXECUTABLE,
    XFOIL_SEARCH_PATHS,
)

LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tipos de datos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class XfoilPolarRequest:
    """Parámetros para calcular un polar en XFOIL."""

    airfoil_dat: Path
    re: float
    alpha_start: float
    alpha_end: float
    alpha_step: float
    mach: float = MACH_DEFAULT
    n_crit: float = N_CRIT_DEFAULT
    output_file: Path | None = None


@dataclass
class XfoilPolarResult:
    """Resultado de una ejecución de XFOIL."""

    success: bool
    output_file: Path | None = None
    n_retries_used: int = 0
    convergence_failures: int = 0
    convergence_rate: float = 1.0    # fracción de puntos convergidos [0–1]
    failed_alpha_values: List[float] = None  # type: ignore[assignment]
    error_message: str = ""

    def __post_init__(self) -> None:
        if self.failed_alpha_values is None:
            self.failed_alpha_values = []


class XfoilError(RuntimeError):
    """Levantado cuando XFOIL falla tras agotar todos los reintentos."""


# ---------------------------------------------------------------------------
# Construcción del script interactivo
# ---------------------------------------------------------------------------

def _build_command_script(request: XfoilPolarRequest) -> str:
    """Genera el script de comandos interactivos para XFOIL.

    El script sigue el flujo estándar de XFOIL para un polar viscoso:
      LOAD → PANE → OPER → VISC/MACH/ITER → VPAR/N → PACC → ASEQ → QUIT
    """
    from vfp_analysis.settings import get_settings
    xfoil_cfg = get_settings().xfoil

    cmds: List[str] = [
        f"LOAD {request.airfoil_dat.name}",
        "",         # aceptar nombre de perfil por defecto
        "PANE",     # re-panelado estándar
        "OPER",
        f"VISC {request.re:.3e}",
        f"MACH {request.mach:.3f}",
        f"ITER {xfoil_cfg.ITER}",
        "VPAR",
        f"N {request.n_crit:.1f}",
        "",         # salir de VPAR → volver a OPER
    ]

    if request.output_file is not None:
        cmds += [
            "PACC",
            request.output_file.name,  # fichero polar en cwd (AIRFOIL_DATA_DIR)
            "",                        # sin dump file
        ]

    cmds.append(
        f"ASEQ {request.alpha_start:.3f} {request.alpha_end:.3f} {request.alpha_step:.3f}"
    )

    if request.output_file is not None:
        cmds += ["PACC", ""]

    cmds.append("QUIT")
    return "\n".join(cmds) + "\n"


# ---------------------------------------------------------------------------
# Ejecución principal
# ---------------------------------------------------------------------------

def run_xfoil_polar(
    request: XfoilPolarRequest,
    timeout: float = 60.0,
    max_retries: int | None = None,
) -> XfoilPolarResult:
    """Ejecuta XFOIL para calcular un polar con reintentos automáticos.

    Parameters
    ----------
    request : XfoilPolarRequest
        Parámetros del polar (perfil, Re, Mach, alpha sweep, etc.).
    timeout : float
        Tiempo máximo por intento [s]. Por defecto 60 s.
    max_retries : int, optional
        Número máximo de reintentos tras un fallo. Por defecto lee de
        ``PipelineSettings.xfoil.MAX_RETRIES``.

    Returns
    -------
    XfoilPolarResult
        Siempre retorna (no lanza salvo que XFOIL no esté instalado o el
        .dat no exista). El campo ``success`` indica el resultado final.

    Raises
    ------
    XfoilError
        Si el ejecutable de XFOIL no existe.
        Si el fichero .dat del perfil no existe.
        Si se agotaron todos los reintentos.
    """
    # --- comprobaciones previas ---
    if not XFOIL_EXECUTABLE.is_file():
        checked = "\n".join(f"  - {p}" for p in XFOIL_SEARCH_PATHS)
        raise XfoilError(
            "Ejecutable XFOIL no encontrado. Rutas comprobadas:\n"
            f"{checked}\n"
            "Ajusta la variable de entorno XFOIL_EXE o XFOIL_EXECUTABLE."
        )

    if not request.airfoil_dat.is_file():
        raise XfoilError(
            f"Fichero de perfil no encontrado: {request.airfoil_dat}"
        )

    # --- número de reintentos ---
    if max_retries is None:
        from vfp_analysis.settings import get_settings
        max_retries = get_settings().xfoil.MAX_RETRIES

    from vfp_analysis.settings import get_settings
    wait_s = get_settings().xfoil.RETRY_WAIT_S

    cwd: Path = AIRFOIL_DATA_DIR

    # Preparar rutas de salida
    if request.output_file is not None:
        request.output_file.parent.mkdir(parents=True, exist_ok=True)
        (cwd / request.output_file.name).unlink(missing_ok=True)
        request.output_file.unlink(missing_ok=True)

    script = _build_command_script(request)
    LOGGER.debug("XFOIL script para %s:\n%s", request.airfoil_dat.name, script)

    context = (
        f"{request.airfoil_dat.name} | Re={request.re:.2e} M={request.mach:.2f} "
        f"α=[{request.alpha_start:.1f}, {request.alpha_end:.1f}]"
    )

    last_error = ""
    for attempt in range(max_retries + 1):
        if attempt > 0:
            LOGGER.warning(
                "XFOIL reintento %d/%d para %s", attempt, max_retries, context
            )
            time.sleep(wait_s)

            # Limpiar residuo del intento anterior
            if request.output_file is not None:
                (cwd / request.output_file.name).unlink(missing_ok=True)

        try:
            proc = subprocess.run(
                [str(XFOIL_EXECUTABLE)],
                input=script.encode("ascii", errors="ignore"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
                cwd=str(cwd),
            )
        except subprocess.TimeoutExpired:
            last_error = f"Timeout tras {timeout:.0f}s (intento {attempt + 1})"
            LOGGER.warning("XFOIL timeout [%s] — %s", context, last_error)
            continue
        except OSError as exc:
            raise XfoilError(f"Error al lanzar XFOIL: {exc}") from exc

        stdout_text = proc.stdout.decode(errors="ignore")
        stderr_text = proc.stderr.decode(errors="ignore")

        # Analizar convergencia desde el stdout
        from vfp_analysis.validation.validators import check_xfoil_convergence
        conv_info = check_xfoil_convergence(stdout_text)

        if conv_info.has_failures:
            LOGGER.warning(
                "XFOIL reportó %d fallo(s) de convergencia para %s "
                "(tasa convergencia: %.0f%%)",
                conv_info.n_convergence_failures,
                context,
                conv_info.convergence_rate * 100,
            )

        if proc.returncode != 0:
            last_error = f"Código de salida {proc.returncode} (intento {attempt + 1})"
            LOGGER.warning(
                "XFOIL salida no cero [%s] — %s\nstdout (últimas 10 líneas):\n%s",
                context,
                last_error,
                "\n".join(stdout_text.splitlines()[-10:]),
            )
            if stderr_text.strip():
                LOGGER.debug("XFOIL stderr:\n%s", stderr_text)
            continue

        # Mover fichero polar al destino final
        if request.output_file is not None:
            src = cwd / request.output_file.name
            if not src.is_file():
                last_error = (
                    f"XFOIL no generó el polar esperado en {src} (intento {attempt + 1})"
                )
                LOGGER.warning("[%s] %s", context, last_error)
                continue
            src.replace(request.output_file)

        LOGGER.info(
            "XFOIL OK: %s (reintentos=%d, fallos-conv=%d)",
            context,
            attempt,
            conv_info.n_convergence_failures,
        )

        return XfoilPolarResult(
            success=True,
            output_file=request.output_file,
            n_retries_used=attempt,
            convergence_failures=conv_info.n_convergence_failures,
            convergence_rate=conv_info.convergence_rate,
            failed_alpha_values=conv_info.failed_alpha_values,
        )

    # Todos los reintentos fallaron
    raise XfoilError(
        f"XFOIL falló tras {max_retries + 1} intentos para {context}.\n"
        f"Último error: {last_error}"
    )


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

def quick_smoke_test(airfoil_dat: Path) -> bool:
    """Ejecuta un polar mínimo para verificar que el binario de XFOIL funciona."""
    out_path = airfoil_dat.with_suffix(".test_polar.txt")
    req = XfoilPolarRequest(
        airfoil_dat=airfoil_dat,
        re=1.0e6,
        alpha_start=0.0,
        alpha_end=4.0,
        alpha_step=2.0,
        output_file=out_path,
    )
    try:
        result = run_xfoil_polar(req, timeout=30.0, max_retries=1)
        return result.success and out_path.is_file()
    except XfoilError as exc:
        LOGGER.error("Smoke test XFOIL fallido: %s", exc)
        return False
    finally:
        out_path.unlink(missing_ok=True)
