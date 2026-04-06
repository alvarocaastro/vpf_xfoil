"""
Global configuration for Variable Pitch Fan airfoil analysis.

All constants and paths are defined here to keep the rest of the code clean.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final, TypedDict
import shutil


# Project root directory (tfg_vpf/)
ROOT_DIR: Final[Path] = Path(__file__).resolve().parents[2]
PROJECT_DIR: Final[Path] = ROOT_DIR / "src" / "vfp_analysis"

# Data and results paths (organized at project root level)
AIRFOIL_DATA_DIR: Final[Path] = ROOT_DIR / "data" / "airfoils"
RESULTS_DIR: Final[Path] = ROOT_DIR / "results"
POLARS_DIR: Final[Path] = RESULTS_DIR / "polars"


def _normalize_xfoil_candidate(raw_path: str | Path) -> Path:
    """Convert a candidate path into the executable path when possible."""

    candidate = Path(raw_path).expanduser()
    executable_name = "xfoil.exe" if os.name == "nt" else "xfoil"
    if candidate.name.lower() not in {"xfoil", "xfoil.exe"}:
        return candidate / executable_name
    return candidate


def _build_xfoil_search_paths() -> tuple[Path, ...]:
    """Return the ordered list of locations where XFOIL may exist."""

    raw_candidates: list[Path] = []
    env_path = os.getenv("XFOIL_EXE") or os.getenv("XFOIL_EXECUTABLE")
    if env_path:
        raw_candidates.append(_normalize_xfoil_candidate(env_path))

    raw_candidates.extend(
        [
            _normalize_xfoil_candidate(ROOT_DIR.parent / "XFOIL6.99"),
            _normalize_xfoil_candidate(ROOT_DIR / "XFOIL6.99"),
            _normalize_xfoil_candidate(Path.home() / "Downloads" / "XFOIL6.99"),
        ]
    )

    which_result = shutil.which("xfoil")
    if which_result:
        raw_candidates.append(Path(which_result))

    unique_candidates: list[Path] = []
    seen: set[str] = set()
    for candidate in raw_candidates:
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        unique_candidates.append(candidate)
    return tuple(unique_candidates)


def _resolve_xfoil_executable() -> Path:
    """Pick the first valid XFOIL executable, or the best local fallback."""

    for candidate in XFOIL_SEARCH_PATHS:
        if candidate.is_file():
            return candidate
    return XFOIL_SEARCH_PATHS[0]


XFOIL_SEARCH_PATHS: Final[tuple[Path, ...]] = _build_xfoil_search_paths()
XFOIL_EXECUTABLE: Final[Path] = _resolve_xfoil_executable()

# ---------------------------------------------------------------------------
# Airfoil definitions
# ---------------------------------------------------------------------------


class AirfoilSpec(TypedDict):
    """Specification of a single airfoil for the analysis."""

    name: str
    dat_file: str
    family: str
    comment: str


# NOTE: We only activate the airfoils for which a .dat file currently exists
# in `airfoil_data/`. The comments justify the selection based on standard
# turbomachinery literature (Bertin & Cummings, Saravanamuttoo, Farokhi,
# Drela/XFOIL docs).

AIRFOILS: Final[list[AirfoilSpec]] = [
    {
        "name": "NACA 65-210",
        "dat_file": "NACA 65-210.dat",
        "family": "NACA 65-series",
        "comment": (
            "Canonical controlled-diffusion compressor/fan profile with 2% "
            "camber and 10% thickness, widely used as reference for fan "
            "blades in the literature (Saravanamuttoo, Farokhi, Drela/XFOIL)."
        ),
    },
    {
        "name": "NACA 65-410",
        "dat_file": "naca 65-410.dat",
        "family": "NACA 65-series",
        "comment": (
            "Controlled-diffusion compressor/fan airfoil with 4% camber and "
            "10% thickness, representative of front-stage fan blades in "
            "high-bypass turbofans (see Saravanamuttoo, Farokhi)."
        ),
    },
    {
        "name": "NACA 63-215",
        "dat_file": "naca63215.dat",
        "family": "NACA 63-series",
        "comment": (
            "Low-drag laminar-flow section adapted to turbomachinery; useful "
            "baseline to compare classic laminar profiles with controlled-"
            "diffusion 65-series (Drela XFOIL docs, Bertin & Cummings)."
        ),
    },
    {
        "name": "NACA 0012",
        "dat_file": "naca0012.dat",
        "family": "NACA 00-series",
        "comment": (
            "Symmetric 12% thick section widely used as reference; serves as "
            "neutral baseline for assessing camber and thickness effects on "
            "fan-blade performance (Farokhi, Bertin & Cummings)."
        ),
    },
]


# ---------------------------------------------------------------------------
# XFOIL defaults
# ---------------------------------------------------------------------------

MACH_DEFAULT: Final[float] = 0.2
N_CRIT_DEFAULT: Final[float] = 9.0


def ensure_directories() -> None:
    """Create output directories if they do not already exist."""

    for directory in (AIRFOIL_DATA_DIR, RESULTS_DIR, POLARS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def clear_results() -> None:
    """
    Delete previous simulation outputs so that each run starts clean.

    This removes:
    - All files in POLARS_DIR (CSV y TXT de polares anteriores)
    - The summary CSV in RESULTS_DIR, if present
    """

    # Borrar polares (CSV/TXT)
    if POLARS_DIR.is_dir():
        for path in POLARS_DIR.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)

    # Borrar resumen
    summary_path = RESULTS_DIR / "summary_pitch_performance.csv"
    if summary_path.is_file():
        summary_path.unlink(missing_ok=True)
