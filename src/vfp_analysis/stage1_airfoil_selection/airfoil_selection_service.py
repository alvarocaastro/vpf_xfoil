from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

import pandas as pd

from vfp_analysis.core.domain.airfoil import Airfoil
from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.ports.xfoil_runner_port import XfoilRunnerPort
from vfp_analysis.stage1_airfoil_selection.scoring import AirfoilScore, score_airfoil

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AirfoilSelectionResult:
    best_airfoil: Airfoil
    scores: List[AirfoilScore]
    polars: pd.DataFrame


class AirfoilSelectionService:
    """Compare all candidate airfoils and select the best one."""

    def __init__(self, xfoil_runner: XfoilRunnerPort, results_dir: Path) -> None:
        self._xfoil = xfoil_runner
        self._results_dir = results_dir

    def run_selection(
        self,
        airfoils: Sequence[Airfoil],
        condition: SimulationCondition,
    ) -> AirfoilSelectionResult:
        """Run XFOIL for all airfoils at a single reference condition."""

        all_rows: List[pd.DataFrame] = []
        scores: List[AirfoilScore] = []

        out_dir = self._results_dir / "airfoil_selection"
        out_dir.mkdir(parents=True, exist_ok=True)

        LOGGER.info(
            "Evaluating %d airfoil candidates at Re=%.2e, M=%.2f, Ncrit=%.1f",
            len(airfoils),
            condition.reynolds,
            condition.mach_rel,
            condition.ncrit,
        )

        for airfoil in airfoils:
            out_file = out_dir / f"{airfoil.name.replace(' ', '_')}_polar.txt"
            LOGGER.info("  Running XFOIL: %s", airfoil.name)

            try:
                self._xfoil.run_polar(airfoil.dat_path, condition, out_file)
            except Exception as exc:
                LOGGER.warning("  XFOIL failed for %s: %s - skipping.", airfoil.name, exc)
                continue

            df = self._parse_polar_file(out_file, airfoil, condition)
            if df.empty:
                LOGGER.warning("  Polar empty for %s - skipping.", airfoil.name)
                continue

            score = score_airfoil(df)
            LOGGER.info(
                "  %s -> (CL/CD)_2nd=%.2f  alpha_opt=%.1f deg  stall=%.1f deg  margin=%.1f deg  robustness=%.2f  score=%.3f",
                airfoil.name,
                score.max_ld,
                score.alpha_opt,
                score.stall_alpha,
                score.stability_margin,
                score.robustness_ld,
                score.total_score,
            )
            all_rows.append(df)
            scores.append(score)

        polars = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()

        if not scores:
            raise RuntimeError(
                "No airfoil could be scored (all XFOIL runs failed or produced empty polars)."
            )

        best = max(scores, key=lambda s: s.total_score)
        LOGGER.info("Selected airfoil: %s (score=%.3f)", best.airfoil, best.total_score)

        selected_path = out_dir / "selected_airfoil.dat"
        selected_path.write_text(best.airfoil, encoding="utf-8")

        best_airfoil = next(a for a in airfoils if a.name == best.airfoil)

        return AirfoilSelectionResult(best_airfoil=best_airfoil, scores=scores, polars=polars)

    @staticmethod
    def _parse_polar_file(
        polar_path: Path,
        airfoil: Airfoil,
        condition: SimulationCondition,
    ) -> pd.DataFrame:
        rows = []
        with polar_path.open("r", encoding="utf8", errors="ignore") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                parts = stripped.split()
                try:
                    alpha = float(parts[0])
                except (ValueError, IndexError):
                    continue
                if len(parts) < 5:
                    continue
                try:
                    cl = float(parts[1])
                    cd = float(parts[2])
                    cm = float(parts[4])
                except ValueError:
                    continue
                ld = cl / cd if cd > 0.0 else float("nan")
                rows.append(
                    {
                        "airfoil": airfoil.name,
                        "condition": condition.name,
                        "mach": condition.mach_rel,
                        "re": condition.reynolds,
                        "alpha": alpha,
                        "cl": cl,
                        "cd": cd,
                        "cm": cm,
                        "ld": ld,
                    }
                )
        return pd.DataFrame(rows)
