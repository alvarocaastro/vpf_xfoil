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
from vfp_analysis.stage2_xfoil_simulations.plot_style import apply_style


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

        results/simulation_plots/<flight>/<section>/

    with:
        - polar.dat
        - cl_alpha.csv
        - cd_alpha.csv
        - polar_plot.png
    """

    def __init__(self, xfoil_runner: XfoilRunnerPort, base_results_dir: Path) -> None:
        self._xfoil = xfoil_runner
        self._base = base_results_dir / "simulation_plots"

    def run(
        self,
        airfoil: Airfoil,
        configs: Iterable[FinalSimulationConfig],
    ) -> Tuple[Dict[Tuple[str, str], float], Dict[Tuple[str, str], Tuple[float, float]]]:
        """
        Execute all final simulations.

        Returns
        -------
        alpha_eff_map : (flight, section) -> alpha_opt
        stall_map     : (flight, section) -> (alpha_stall, cl_max)
        """
        alpha_eff_map: Dict[Tuple[str, str], float] = {}
        stall_map: Dict[Tuple[str, str], Tuple[float, float]] = {}

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
            alpha_eff, alpha_stall, cl_max = self._plot_all(df, out_dir, airfoil, cfg)
            alpha_eff_map[(cfg.flight_name, cfg.section.name)] = alpha_eff
            stall_map[(cfg.flight_name, cfg.section.name)] = (alpha_stall, cl_max)

        return alpha_eff_map, stall_map

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
        df[cols].to_csv(out_dir / "polar.csv", index=False, float_format="%.6f")

    @staticmethod
    def _plot_all(
        df: pd.DataFrame,
        out_dir: Path,
        airfoil: Airfoil,
        cfg: FinalSimulationConfig,
    ) -> float:
        """Generate all plots and return alpha_eff (max CL/CD)."""

        # 1) CL/CD vs alpha (eficiencia) y alpha_eff
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

        # Stall detection: CL peak (only for alpha > 0 to avoid pre-stall artefacts)
        df_pos = df[df["alpha"] > 0.0].copy()
        if not df_pos.empty:
            idx_stall = df_pos["cl"].idxmax()
            alpha_stall = float(df_pos.loc[idx_stall, "alpha"])
            cl_stall    = float(df_pos.loc[idx_stall, "cl"])
        else:
            alpha_stall = float("nan")
            cl_stall    = float("nan")

        with apply_style():
            # 1) CL/CD vs alpha (eficiencia)
            fig_eff, ax_eff = plt.subplots(figsize=(5.5, 4.2))
            ax_eff.plot(df["alpha"], df["ld"], color="#4477AA", label=r"$C_L/C_D$")
            if not pd.isna(alpha_eff):
                ld_eff = float(df_second_peak.loc[idx_max, "ld"])
                ax_eff.scatter(alpha_eff, ld_eff, color="#EE6677", s=80, zorder=5,
                               edgecolors="white", linewidths=1.2,
                               label=rf"$\alpha_{{opt}}$ = {alpha_eff:.2f}°")
                ax_eff.axvline(alpha_eff, color="#EE6677", linestyle="--",
                               linewidth=1.4, alpha=0.8, zorder=4)

            ax_eff.set_xlabel(r"$\alpha$ [°]")
            ax_eff.set_ylabel(r"$C_L/C_D$")
            ax_eff.set_title(
                f"Eficiencia — {cfg.flight_name.capitalize()} / {cfg.section.name.replace('_', ' ')}"
            )
            ax_eff.legend(loc="lower right")
            fig_eff.tight_layout()
            fig_eff.savefig(out_dir / "efficiency_plot.png")
            plt.close(fig_eff)

            # 2) CL vs alpha con marca de entrada en pérdidas
            fig_cl, ax_cl = plt.subplots(figsize=(5.5, 4.2))
            ax_cl.plot(df["alpha"], df["cl"], color="#4477AA", label=r"$C_L$")

            if not pd.isna(alpha_stall):
                # Marker at CL_max (stall onset)
                ax_cl.scatter(alpha_stall, cl_stall, color="#EE6677", s=90, zorder=5,
                              edgecolors="white", linewidths=1.2,
                              label=rf"Entrada en pérdidas: $\alpha_{{stall}}$ = {alpha_stall:.1f}°,  $C_{{L,max}}$ = {cl_stall:.3f}")
                ax_cl.axvline(alpha_stall, color="#EE6677", linestyle="--",
                              linewidth=1.4, alpha=0.8, zorder=4)
                # Horizontal reference at CL_max
                ax_cl.axhline(cl_stall, color="#EE6677", linestyle=":",
                              linewidth=1.0, alpha=0.6, zorder=3)
                # Annotation inside the plot
                ax_cl.annotate(
                    rf"$C_{{L,max}}$ = {cl_stall:.3f}",
                    xy=(alpha_stall, cl_stall),
                    xytext=(-45, 10), textcoords="offset points",
                    fontsize=8, color="#EE6677",
                    arrowprops=dict(arrowstyle="->", color="#EE6677", lw=1.0),
                )

            ax_cl.set_xlabel(r"$\alpha$ [°]")
            ax_cl.set_ylabel(r"$C_L$")
            ax_cl.set_title(
                f"Curva de sustentación — {cfg.flight_name.capitalize()} / {cfg.section.name.replace('_', ' ')}"
            )
            ax_cl.legend(
                bbox_to_anchor=(0.5, -0.22), loc="upper center",
                borderaxespad=0, ncol=1,
            )
            fig_cl.tight_layout()
            fig_cl.savefig(out_dir / "cl_alpha_stall.png")
            plt.close(fig_cl)

            # 3) Polar CL–CD
            fig_pol, ax_pol = plt.subplots(figsize=(5.5, 4.2))
            ax_pol.plot(df["cd"], df["cl"], color="#4477AA", linewidth=1.8)
            ax_pol.set_xlabel(r"$C_D$")
            ax_pol.set_ylabel(r"$C_L$")
            ax_pol.set_title(
                f"Polar aerodinámica — {cfg.flight_name.capitalize()} / {cfg.section.name.replace('_', ' ')}"
            )
            fig_pol.tight_layout()
            fig_pol.savefig(out_dir / "polar_plot.png")
            plt.close(fig_pol)

        return alpha_eff, alpha_stall, cl_stall


