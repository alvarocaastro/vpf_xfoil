from __future__ import annotations

import logging
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


@dataclass(frozen=True)
class XfoilPolarRequest:
    """Request for a polar computation in XFOIL."""

    airfoil_dat: Path
    re: float
    alpha_start: float
    alpha_end: float
    alpha_step: float
    mach: float = MACH_DEFAULT
    n_crit: float = N_CRIT_DEFAULT
    output_file: Path | None = None


class XfoilError(RuntimeError):
    """Raised when XFOIL fails or returns a non-zero exit status."""


def _build_command_script(request: XfoilPolarRequest) -> str:
    """
    Build the XFOIL command script for a simple alpha sweep at fixed Re, M.
    """

    cmds: List[str] = []

    # Trabajamos en AIRFOIL_DATA_DIR, así LOAD <nombre.dat> funciona.
    cmds.append(f"LOAD {request.airfoil_dat.name}")
    cmds.append("")  # aceptar nombre por defecto
    cmds.append("PANE")

    # Menú OPER para cálculo viscoso
    cmds.append("OPER")
    cmds.append(f"VISC {request.re:.3e}")
    cmds.append(f"MACH {request.mach:.3f}")
    cmds.append("ITER 200")

    # Ajustar el parámetro de transición Ncrit. En XFOIL se controla desde el
    # submenú VPAR usando el comando 'N <valor>'.
    cmds.append("VPAR")
    cmds.append(f"N {request.n_crit:.1f}")
    cmds.append("")  # volver a OPER

    if request.output_file is not None:
        cmds.append("PACC")
        # Escribimos en el cwd (AIRFOIL_DATA_DIR) con nombre simple
        cmds.append(request.output_file.name)
        cmds.append("")  # sin dump file

    cmds.append(
        "ASEQ "
        f"{request.alpha_start:.3f} "
        f"{request.alpha_end:.3f} "
        f"{request.alpha_step:.3f}"
    )

    if request.output_file is not None:
        cmds.append("PACC")
        cmds.append("")

    cmds.append("QUIT")

    return "\n".join(cmds) + "\n"


def run_xfoil_polar(request: XfoilPolarRequest, timeout: float = 60.0) -> None:
    """Run XFOIL for a given polar request."""

    if not XFOIL_EXECUTABLE.is_file():
        checked_paths = "\n".join(f"  - {path}" for path in XFOIL_SEARCH_PATHS)
        raise XfoilError(
            "XFOIL executable not found. Checked these locations:\n"
            f"{checked_paths}\n"
            "You can also set XFOIL_EXE or XFOIL_EXECUTABLE."
        )

    if not request.airfoil_dat.is_file():
        raise XfoilError(f"Airfoil .dat file not found: {request.airfoil_dat}")

    cwd: Path = AIRFOIL_DATA_DIR
    if request.output_file is not None:
        # Ensure output directories exist and remove any old polar file with the
        # same name, both in the XFOIL working directory and in the final
        # destination, to avoid interactive "save file" prompts.
        request.output_file.parent.mkdir(parents=True, exist_ok=True)
        (cwd / request.output_file.name).unlink(missing_ok=True)
        request.output_file.unlink(missing_ok=True)

    script: str = _build_command_script(request)
    LOGGER.debug("XFOIL script:\n%s", script)

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
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise XfoilError(f"Failed to run XFOIL: {exc}") from exc

    if proc.returncode != 0:
        LOGGER.error("XFOIL stdout:\n%s", proc.stdout.decode(errors="ignore"))
        LOGGER.error("XFOIL stderr:\n%s", proc.stderr.decode(errors="ignore"))
        raise XfoilError(
            f"XFOIL exited with code {proc.returncode} "
            f"for airfoil {request.airfoil_dat.name}"
        )

    LOGGER.debug("XFOIL stdout:\n%s", proc.stdout.decode(errors="ignore"))

    if request.output_file is not None:
        src = cwd / request.output_file.name
        if not src.is_file():
            raise XfoilError(
                f"XFOIL did not create expected polar file {src}"
            )
        src.replace(request.output_file)

    LOGGER.info(
        "XFOIL polar computed for %s at Re=%.2e, M=%.2f, "
        "alpha=[%.1f, %.1f]",
        request.airfoil_dat.name,
        request.re,
        request.mach,
        request.alpha_start,
        request.alpha_end,
    )


def quick_smoke_test(airfoil_dat: Path) -> bool:
    """Run a very small XFOIL job to check that the binary works."""

    out_path: Path = airfoil_dat.with_suffix(".test_polar.txt")
    req = XfoilPolarRequest(
        airfoil_dat=airfoil_dat,
        re=1.0e6,
        alpha_start=0.0,
        alpha_end=4.0,
        alpha_step=2.0,
        output_file=out_path,
    )

    try:
        run_xfoil_polar(req, timeout=30.0)
    except XfoilError as exc:
        LOGGER.error("XFOIL smoke test failed: %s", exc)
        return False

    return out_path.is_file()
