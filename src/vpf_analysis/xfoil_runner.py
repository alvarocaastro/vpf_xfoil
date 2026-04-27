"""XFOIL subprocess integration: script build, retry logic, convergence detection."""

from __future__ import annotations

import hashlib
import logging
import shutil
import time
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .settings import (
    AIRFOIL_DATA_DIR,
    MACH_DEFAULT,
    N_CRIT_DEFAULT,
    XFOIL_EXECUTABLE,
    XFOIL_SEARCH_PATHS,
)

LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


@dataclass(frozen=True)
class XfoilPolarRequest:
    """Parameters for an XFOIL polar computation."""

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
    """Result of an XFOIL run."""

    success: bool
    output_file: Path | None = None
    n_retries_used: int = 0
    convergence_failures: int = 0
    convergence_rate: float = 1.0    # fraction of converged points [0–1]
    failed_alpha_values: list[float] = None  # type: ignore[assignment]
    error_message: str = ""

    def __post_init__(self) -> None:
        if self.failed_alpha_values is None:
            self.failed_alpha_values = []


class XfoilError(RuntimeError):
    """Raised when XFOIL fails after exhausting all retries."""


def _build_command_script(request: XfoilPolarRequest) -> str:
    """Build the interactive XFOIL command script.

    Flow: LOAD → PANE → OPER → VISC/MACH/ITER → VPAR/N → PACC → ASEQ → QUIT
    """
    from vpf_analysis.settings import get_settings
    xfoil_cfg = get_settings().xfoil

    cmds: list[str] = [
        f"LOAD {request.airfoil_dat.name}",
        "",         # accept default airfoil name
        "PANE",     # standard re-paneling
        "OPER",
        f"VISC {request.re:.3e}",
        f"MACH {request.mach:.3f}",
        f"ITER {xfoil_cfg.ITER}",
        "VPAR",
        f"N {request.n_crit:.1f}",
        "",         # exit VPAR → back to OPER
    ]

    if request.output_file is not None:
        cmds += [
            "PACC",
            request.output_file.name,  # polar file in cwd (AIRFOIL_DATA_DIR)
            "",                        # no dump file
        ]

    cmds.append(
        f"ASEQ {request.alpha_start:.3f} {request.alpha_end:.3f} {request.alpha_step:.3f}"
    )

    if request.output_file is not None:
        cmds += ["PACC", ""]

    cmds.append("QUIT")
    return "\n".join(cmds) + "\n"


def _polar_cache_key(request: XfoilPolarRequest) -> str:
    """Compute a 12-character SHA-256 hex digest for the polar request parameters."""
    key_parts = repr(sorted({
        "airfoil": request.airfoil_dat.name,
        "re":          round(request.re, 0),
        "alpha_start": round(request.alpha_start, 3),
        "alpha_end":   round(request.alpha_end, 3),
        "alpha_step":  round(request.alpha_step, 4),
        "mach":        round(request.mach, 4),
        "n_crit":      round(request.n_crit, 2),
    }.items()))
    return hashlib.sha256(key_parts.encode()).hexdigest()[:12]


def _polar_cache_dir() -> Path:
    from vpf_analysis import settings as _s
    return _s.RESULTS_DIR / ".polar_cache"


def run_xfoil_polar(
    request: XfoilPolarRequest,
    timeout: float = 60.0,
    max_retries: int | None = None,
) -> XfoilPolarResult:
    """Run XFOIL to compute a polar with automatic retries.

    When ``xfoil_cache: true`` is set in analysis_config.yaml, polars with
    identical (airfoil, Re, M, Ncrit, alpha range) parameters are served from
    ``results/.polar_cache/<hash>.csv`` without invoking XFOIL.  The cache is
    populated automatically after each successful run.  Delete the
    ``results/.polar_cache/`` directory to force a full re-computation.

    Always returns; raises XfoilError only if the executable or .dat file is
    missing, or all retries are exhausted. Check ``result.success`` for status.
    """
    # ── Cache check ───────────────────────────────────────────────────────────
    from vpf_analysis.settings import get_settings as _gs
    _use_cache = _gs().xfoil_cache
    _cache_hit_file: Path | None = None
    if _use_cache and request.output_file is not None:
        cache_key = _polar_cache_key(request)
        cache_file = _polar_cache_dir() / f"{cache_key}.csv"
        if cache_file.is_file():
            request.output_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cache_file, request.output_file)
            LOGGER.info("XFOIL cache hit [%s] → %s", cache_key, cache_file.name)
            return XfoilPolarResult(
                success=True,
                output_file=request.output_file,
                n_retries_used=0,
                convergence_failures=0,
                convergence_rate=1.0,
            )
        _cache_hit_file = cache_file

    if not XFOIL_EXECUTABLE.is_file():
        checked = "\n".join(f"  - {p}" for p in XFOIL_SEARCH_PATHS)
        raise XfoilError(
            "XFOIL executable not found. Checked paths:\n"
            f"{checked}\n"
            "Set the XFOIL_EXE or XFOIL_EXECUTABLE environment variable."
        )

    if not request.airfoil_dat.is_file():
        raise XfoilError(
            f"Airfoil file not found: {request.airfoil_dat}"
        )

    if max_retries is None:
        from vpf_analysis.settings import get_settings
        max_retries = get_settings().xfoil.MAX_RETRIES

    from vpf_analysis.settings import get_settings
    wait_s = get_settings().xfoil.RETRY_WAIT_S

    cwd: Path = AIRFOIL_DATA_DIR

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
                "XFOIL retry %d/%d for %s", attempt, max_retries, context
            )
            time.sleep(wait_s)

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
            last_error = f"Timeout after {timeout:.0f}s (attempt {attempt + 1})"
            LOGGER.warning("XFOIL timeout [%s] — %s", context, last_error)
            continue
        except OSError as exc:
            raise XfoilError(f"Failed to launch XFOIL: {exc}") from exc

        stdout_text = proc.stdout.decode(errors="ignore")
        stderr_text = proc.stderr.decode(errors="ignore")

        from vpf_analysis.validation.validators import check_xfoil_convergence
        conv_info = check_xfoil_convergence(stdout_text)

        if conv_info.has_failures:
            LOGGER.warning(
                "XFOIL reported %d convergence failure(s) for %s "
                "(convergence rate: %.0f%%)",
                conv_info.n_convergence_failures,
                context,
                conv_info.convergence_rate * 100,
            )

        if proc.returncode != 0:
            last_error = f"Exit code {proc.returncode} (attempt {attempt + 1})"
            LOGGER.warning(
                "XFOIL non-zero exit [%s] — %s\nstdout (last 10 lines):\n%s",
                context,
                last_error,
                "\n".join(stdout_text.splitlines()[-10:]),
            )
            if stderr_text.strip():
                LOGGER.debug("XFOIL stderr:\n%s", stderr_text)
            continue

        if request.output_file is not None:
            src = cwd / request.output_file.name
            if not src.is_file():
                last_error = (
                    f"XFOIL did not generate expected polar at {src} (attempt {attempt + 1})"
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

        # ── Cache write ───────────────────────────────────────────────────────
        if _use_cache and _cache_hit_file is not None and request.output_file is not None:
            if request.output_file.is_file():
                try:
                    _cache_hit_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(request.output_file, _cache_hit_file)
                    LOGGER.debug("XFOIL cache stored → %s", _cache_hit_file.name)
                except Exception as _exc:
                    LOGGER.warning("Could not write XFOIL cache: %s", _exc)

        return XfoilPolarResult(
            success=True,
            output_file=request.output_file,
            n_retries_used=attempt,
            convergence_failures=conv_info.n_convergence_failures,
            convergence_rate=conv_info.convergence_rate,
            failed_alpha_values=conv_info.failed_alpha_values,
        )

    raise XfoilError(
        f"XFOIL failed after {max_retries + 1} attempts for {context}.\n"
        f"Last error: {last_error}"
    )



def quick_smoke_test(airfoil_dat: Path) -> bool:
    """Run a minimal polar to verify the XFOIL binary works."""
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
        LOGGER.error("XFOIL smoke test failed: %s", exc)
        return False
    finally:
        out_path.unlink(missing_ok=True)
