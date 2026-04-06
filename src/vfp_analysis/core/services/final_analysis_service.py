from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd

from vfp_analysis.core.domain.airfoil import Airfoil
from vfp_analysis.core.domain.blade_section import BladeSection
from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.ports.xfoil_runner_port import XfoilRunnerPort


@dataclass(frozen=True)
class FinalSimulationConfig:
    """Configuration for a single (flight condition, blade section) simulation."""

    flight_name: str
    section: BladeSection
    condition: SimulationCondition


class FinalAnalysisService:
    """
    Run final XFOIL simulations for the selected airfoil only.

    Results are organised under:

        results/final_analysis/<flight>/<section>/

    with:
        - polar.dat
        - cl_alpha.csv
        - cd_alpha.csv
        - polar_plot.png
    """

    def __init__(self, xfoil_runner: XfoilRunnerPort, base_results_dir: Path) -> None:
        self._xfoil = xfoil_runner
        self._base = base_results_dir / "final_analysis"

    def run(self, airfoil: Airfoil, configs: Iterable[FinalSimulationConfig]) -> Dict[Tuple[str, str], float]:
        """
        Execute all final simulations.

        Returns a mapping (flight_name, section_name) -> alpha_eff, where
        alpha_eff is the angle of attack that maximises CL/CD for that case.
        """

        alpha_eff_map: Dict[Tuple[str, str], float] = {}

        for cfg in configs:
            flight_dir = cfg.flight_name.lower()
            out_dir = self._base / flight_dir / cfg.section.name
            out_dir.mkdir(parents=True, exist_ok=True)

            polar_path = out_dir / "polar.dat"
            self._xfoil.run_polar(airfoil.dat_path, cfg.condition, polar_path)

            df = self._parse_polar_file(polar_path, airfoil, cfg)
            if df.empty:
                continue

            self._export_csv(df, out_dir)
            alpha_eff = self._plot_all(df, out_dir, airfoil, cfg)
            alpha_eff_map[(cfg.flight_name, cfg.section.name)] = alpha_eff

        return alpha_eff_map

    @staticmethod
    def _parse_polar_file(
        polar_path: Path,
        airfoil: Airfoil,
        cfg: FinalSimulationConfig,
    ) -> pd.DataFrame:
        rows: List[Dict[str, float | str]] = []
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
                rows.append(
                    {
                        "airfoil": airfoil.name,
                        "flight": cfg.flight_name,
                        "section": cfg.section.name,
                        "mach": cfg.condition.mach_rel,
                        "re": cfg.condition.reynolds,
                        "ncrit": cfg.condition.ncrit,
                        "alpha": alpha,
                        "cl": cl,
                        "cd": cd,
                        "cm": cm,
                        "ld": cl / cd if cd > 0.0 else float("nan"),
                    }
                )
        return pd.DataFrame(rows)

    @staticmethod
    def _export_csv(df: pd.DataFrame, out_dir: Path) -> None:
        cols = ["alpha", "cl", "cd", "cm", "ld", "re", "ncrit"]
        df[cols][["alpha", "cl"]].to_csv(
            out_dir / "cl_alpha.csv",
            index=False,
            float_format="%.6f",
        )
        df[cols][["alpha", "cd"]].to_csv(
            out_dir / "cd_alpha.csv",
            index=False,
            float_format="%.6f",
        )

        # Polar en formato CSV (CL, CD, CL/CD vs alpha)
        df[cols].to_csv(
            out_dir / "polar.csv",
            index=False,
            float_format="%.6f",
        )

    @staticmethod
    def _plot_all(
        df: pd.DataFrame,
        out_dir: Path,
        airfoil: Airfoil,
        cfg: FinalSimulationConfig,
    ) -> float:
        """Generate all plots and return alpha_eff (max CL/CD)."""

        # 1) CL vs alpha
        fig_cl, ax_cl = plt.subplots(figsize=(5.0, 4.0))
        ax_cl.plot(df["alpha"], df["cl"], marker="o", markersize=3, linewidth=1.2)
        ax_cl.set_xlabel(r"$\alpha$ [deg]")
        ax_cl.set_ylabel(r"$C_L$")
        ax_cl.set_title(f"$C_L$ vs $\\alpha$ – {cfg.flight_name} / {cfg.section.name}")
        ax_cl.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
        fig_cl.tight_layout()
        fig_cl.savefig(out_dir / "cl_alpha_plot.png", dpi=300, bbox_inches="tight")
        plt.close(fig_cl)

        # 2) CD vs alpha
        fig_cd, ax_cd = plt.subplots(figsize=(5.0, 4.0))
        ax_cd.plot(df["alpha"], df["cd"], marker="o", markersize=3, linewidth=1.2)
        ax_cd.set_xlabel(r"$\alpha$ [deg]")
        ax_cd.set_ylabel(r"$C_D$")
        ax_cd.set_title(f"$C_D$ vs $\\alpha$ – {cfg.flight_name} / {cfg.section.name}")
        ax_cd.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
        fig_cd.tight_layout()
        fig_cd.savefig(out_dir / "cd_alpha_plot.png", dpi=300, bbox_inches="tight")
        plt.close(fig_cd)

        # 3) CL/CD vs alpha (eficiencia) y alpha_eff
        #    Esta es la figura principal para el TFG.
        #    Usamos el SEGUNDO pico (alpha >= 3°) porque el primero es un artefacto
        #    de burbuja de separación laminar no representativo de turbomaquinaria.
        df_eff = df.copy()
        # Evitar infinidades o NaN en la búsqueda de máximo
        df_eff = df_eff.replace([float("inf"), float("-inf")], pd.NA).dropna(subset=["ld"])
        if df_eff.empty:
            alpha_eff = float("nan")
        else:
            # Focus on second peak (alpha >= 3°) for turbomachinery operation
            df_second_peak = df_eff[df_eff["alpha"] >= 3.0]
            if df_second_peak.empty:
                # Fallback to all data if no second peak
                df_second_peak = df_eff
            idx_max = df_second_peak["ld"].idxmax()
            alpha_eff = float(df_second_peak.loc[idx_max, "alpha"])

        fig_eff, ax_eff = plt.subplots(figsize=(5.0, 4.0))
        ax_eff.plot(df["alpha"], df["ld"], label=r"$C_L/C_D$", linewidth=1.4)
        if not pd.isna(alpha_eff):
            # Get efficiency value at optimal angle (from second peak)
            ld_eff = float(df_second_peak.loc[idx_max, "ld"])
            ax_eff.plot(
                alpha_eff,
                ld_eff,
                marker="X",
                color="red",
                markersize=10,
                markeredgecolor="darkred",
                markeredgewidth=1.5,
                label=f"$\\alpha_{{eff}}$ = {alpha_eff:.2f}° (2nd peak)",
                zorder=5,
            )
            ax_eff.axvline(
                alpha_eff,
                color="red",
                linestyle="--",
                linewidth=1.0,
                alpha=0.7,
                zorder=4,
            )
            ax_eff.annotate(
                f"$\\alpha_{{eff}}$ = {alpha_eff:.2f}°\n(2nd peak)",
                xy=(alpha_eff, ld_eff),
                xytext=(alpha_eff + 1.0, ld_eff + 5.0),
                arrowprops=dict(
                    facecolor="red",
                    shrink=0.05,
                    width=1.5,
                    headwidth=8,
                    alpha=0.7,
                ),
                fontsize=9,
                fontweight="bold",
                zorder=6,
            )
        ax_eff.set_xlabel(r"$\alpha$ [deg]")
        ax_eff.set_ylabel(r"$C_L/C_D$")
        ax_eff.set_title(
            f"Eficiencia aerodinámica $C_L/C_D$ – {cfg.flight_name} / {cfg.section.name}"
        )
        ax_eff.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
        ax_eff.legend(loc="best")
        fig_eff.tight_layout()
        fig_eff.savefig(out_dir / "efficiency_plot.png", dpi=300, bbox_inches="tight")
        plt.close(fig_eff)

        # 4) Polar CL–CD
        fig_pol, ax_pol = plt.subplots(figsize=(5.0, 4.0))
        ax_pol.plot(df["cd"], df["cl"], marker="o", markersize=3, linewidth=1.2)
        ax_pol.set_xlabel(r"$C_D$")
        ax_pol.set_ylabel(r"$C_L$")
        ax_pol.set_title(f"Polar {airfoil.name}\n{cfg.flight_name} – {cfg.section.name}")
        ax_pol.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
        fig_pol.tight_layout()
        fig_pol.savefig(out_dir / "polar_plot.png", dpi=300, bbox_inches="tight")
        plt.close(fig_pol)

        return alpha_eff


