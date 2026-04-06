from __future__ import annotations

from pathlib import Path
from typing import Iterable


def _remove_dir_if_exists(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        # Borrar recursivamente el contenido y la carpeta
        for child in path.rglob("*"):
            if child.is_file():
                child.unlink(missing_ok=True)
        # Borrar subdirectorios vacíos de dentro hacia fuera
        for child in sorted(path.rglob("*"), reverse=True):
            if child.is_dir():
                try:
                    child.rmdir()
                except OSError:
                    # Si queda algo (por permisos), lo dejamos
                    pass
        try:
            path.rmdir()
        except OSError:
            pass
    else:
        path.unlink(missing_ok=True)


def clean_all_results(project_root: Path) -> None:
    """
    Remove all previously generated results to guarantee reproducibility.

    This function deletes:
    - project_root / "results" (all stages)

    It does NOT touch `data/airfoils/`.
    """

    results_dir = project_root / "results"
    _remove_dir_if_exists(results_dir)

