from __future__ import annotations

from pathlib import Path
from typing import List, Dict

from vfp_analysis import config
from vfp_analysis.adapters.xfoil.xfoil_runner_adapter import XfoilRunnerAdapter
from vfp_analysis.core.domain.airfoil import Airfoil
from vfp_analysis.core.domain.blade_section import BladeSection
from vfp_analysis.core.domain.simulation_condition import SimulationCondition
from vfp_analysis.core.services.final_analysis_service import (
    FinalAnalysisService,
    FinalSimulationConfig,
)
import matplotlib.pyplot as plt
import pandas as pd


def _load_selected_airfoil() -> Airfoil:
    path = config.RESULTS_DIR / "airfoil_selection" / "selected_airfoil.dat"
    name = path.read_text(encoding="utf8").strip()

    spec = next(a for a in config.AIRFOILS if a["name"] == name)
    dat_path = config.AIRFOIL_DATA_DIR / spec["dat_file"]
    return Airfoil(name=spec["name"], family=spec["family"], dat_path=dat_path)


def _build_blade_sections() -> List[BladeSection]:
    return [
        BladeSection(name="root", reynolds=0.0),
        BladeSection(name="mid_span", reynolds=0.0),
        BladeSection(name="tip", reynolds=0.0),
    ]


def _build_flight_conditions() -> list[str]:
    return ["Takeoff", "Climb", "Cruise", "Descent"]


def _build_configs(sections: List[BladeSection]) -> List[FinalSimulationConfig]:
    configs: List[FinalSimulationConfig] = []
    flights = _build_flight_conditions()

    # Reynolds por condición y sección (tabla de 12 simulaciones)
    re_table = {
        "Takeoff": {"root": 2.5e6, "mid_span": 4.5e6, "tip": 7.0e6},
        "Climb": {"root": 2.2e6, "mid_span": 4.0e6, "tip": 6.2e6},
        "Cruise": {"root": 1.8e6, "mid_span": 3.2e6, "tip": 5.0e6},
        "Descent": {"root": 2.0e6, "mid_span": 3.6e6, "tip": 5.6e6},
    }

    # Ncrit por condición (flujo más turbulento en despegue, etc.)
    ncrit_table = {
        "Takeoff": 5.0,
        "Climb": 6.0,
        "Cruise": 7.0,
        "Descent": 6.0,
    }

    for flight in flights:
        for section in sections:
            re_value = re_table[flight][section.name]
            ncrit_value = ncrit_table[flight]
            cond = SimulationCondition(
                name=f"{flight}_{section.name}",
                mach_rel=config.MACH_DEFAULT,
                reynolds=re_value,
                alpha_min=-5.0,
                alpha_max=23.0,
                alpha_step=0.15,
                ncrit=ncrit_value,
            )
            configs.append(
                FinalSimulationConfig(
                    flight_name=flight,
                    section=section,
                    condition=cond,
                )
            )
    return configs


def main() -> None:
    config.ensure_directories()

    airfoil = _load_selected_airfoil()
    sections = _build_blade_sections()
    configs = _build_configs(sections)

    runner = XfoilRunnerAdapter()
    service = FinalAnalysisService(runner, config.RESULTS_DIR)
    alpha_eff_map = service.run(airfoil, configs)

    base = config.RESULTS_DIR / "final_analysis"
    flights = _build_flight_conditions()

    # 1) Resumen de eficiencia máxima (ignorando el primer pico laminar)
    #    y curvas de eficiencia media C_L/C_D vs alpha por condición de vuelo.
    avg_eff_by_flight: Dict[str, pd.DataFrame] = {}
    summary_rows: list[dict] = []

    for flight in flights:
        dfs = []
        for section in ["root", "mid_span", "tip"]:
            polar_csv = base / flight.lower() / section / "polar.csv"
            if not polar_csv.is_file():
                continue
            df = pd.read_csv(polar_csv)

            # Segundo pico: ignoramos ángulos menores de 3º (primer pico laminar)
            df_second = df[df["alpha"] >= 3.0]
            if not df_second.empty:
                idx = df_second["ld"].idxmax()
                row = df_second.loc[idx]
                summary_rows.append(
                    {
                        "flight": flight,
                        "section": section,
                        "re": float(row.get("re", float("nan"))),
                        "ncrit": float(row.get("ncrit", float("nan"))),
                        "alpha_opt_deg": float(row["alpha"]),
                        "ld_max": float(row["ld"]),
                    }
                )

            dfs.append(df[["alpha", "ld"]].rename(columns={"ld": f"ld_{section}"}))

        if not dfs:
            continue
        df_merged = dfs[0]
        for extra in dfs[1:]:
            df_merged = df_merged.merge(extra, on="alpha", how="inner")
        ld_cols = [c for c in df_merged.columns if c.startswith("ld_")]
        df_merged["ld_mean"] = df_merged[ld_cols].mean(axis=1)

        avg_eff_by_flight[flight] = df_merged[["alpha", "ld_mean"]]

        fig, ax = plt.subplots(figsize=(5.0, 4.0))
        ax.plot(df_merged["alpha"], df_merged["ld_mean"], linewidth=1.6)
        ax.set_xlabel(r"$\alpha$ [deg]")
        ax.set_ylabel(r"$C_L/C_D$ medio")
        ax.set_title(f"Eficiencia media $C_L/C_D$ – {flight}")
        ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)

        flight_dir = base / flight.lower()
        flight_dir.mkdir(parents=True, exist_ok=True)
        fig.tight_layout()
        fig.savefig(flight_dir / "efficiency_mean_plot.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

    # Guardar CSV resumen de eficiencia máxima (segundo pico) por polar
    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)

        # Añadir una fila "mean" por condición de vuelo (media de root/mid/tip)
        mean_rows: list[dict] = []
        for flight in flights:
            sub = summary_df[summary_df["flight"] == flight]
            if sub.empty:
                continue
            mean_rows.append(
                {
                    "flight": flight,
                    "section": "mean",
                    "re": sub["re"].mean(),
                    "ncrit": sub["ncrit"].iloc[0],
                    "alpha_opt_deg": sub["alpha_opt_deg"].mean(),
                    "ld_max": sub["ld_max"].mean(),
                }
            )

        if mean_rows:
            summary_df = pd.concat([summary_df, pd.DataFrame(mean_rows)], ignore_index=True)

        summary_path = base / "max_efficiency_summary.csv"
        summary_df.to_csv(summary_path, index=False, float_format="%.6f")

    # 2) Figura global: alpha_eff vs condición de vuelo (sección mid_span)
    mid_section_name = "mid_span"
    alphas = []
    labels = []
    for flight in flights:
        key = (flight, mid_section_name)
        alpha_eff = alpha_eff_map.get(key)
        if alpha_eff is None:
            continue
        alphas.append(alpha_eff)
        labels.append(flight)

    if alphas:
        fig, ax = plt.subplots(figsize=(5.0, 4.0))
        ax.plot(labels, alphas, marker="o", linewidth=1.4)
        ax.set_xlabel("Condición de vuelo")
        ax.set_ylabel(r"$\alpha_{eff}$ [deg]")
        ax.set_title(r"Ángulo de máxima eficiencia $\alpha_{eff}$ por condición de vuelo")
        ax.grid(True, linestyle=":", linewidth=0.5, alpha=0.7)
        fig.tight_layout()
        out_dir = base
        out_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_dir / "alpha_eff_vs_flight_condition.png", dpi=300, bbox_inches="tight")
        plt.close(fig)


if __name__ == "__main__":
    main()

