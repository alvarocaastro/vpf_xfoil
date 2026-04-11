"""
results_writer.py
-----------------
Persiste las tablas y resúmenes de texto del análisis de pitch y cinemática.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class FilesystemPitchKinematicsWriter:
    """Escribe los CSV y resúmenes de Stage 5 en disco."""

    @staticmethod
    def write_optimal_incidence_table(
        optimal_incidences: list,
        output_path: Path,
    ) -> None:
        """
        Guarda la tabla de incidencias óptimas.

        Columnas: condition, section, Re, Mach, alpha_opt, CL_CD_max
        """
        rows = [
            {
                "condition": item.condition,
                "section":   item.section,
                "Re":        item.reynolds,
                "Mach":      item.mach,
                "alpha_opt": item.alpha_opt,
                "CL_CD_max": item.cl_cd_max,
            }
            for item in optimal_incidences
        ]
        df = pd.DataFrame(rows).sort_values(["condition", "section"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.6f")

    @staticmethod
    def write_pitch_adjustment_table(
        pitch_adjustments: list,
        output_path: Path,
    ) -> None:
        """
        Guarda la tabla de ajustes de paso aerodinámico.

        Columnas: condition, section, alpha_opt, delta_pitch
        """
        rows = [
            {
                "condition":   item.condition,
                "section":     item.section,
                "alpha_opt":   item.alpha_opt,
                "delta_pitch": item.delta_pitch,
            }
            for item in pitch_adjustments
        ]
        df = pd.DataFrame(rows).sort_values(["condition", "section"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.6f")

    @staticmethod
    def write_kinematics_table(
        kinematics_results: list,
        pitch_adjustments: list,
        output_path: Path,
    ) -> None:
        """
        Guarda la tabla de resultados cinemáticos completos.

        Columnas: condition, section, axial_velocity_m_s, tangential_velocity_m_s,
                  inflow_angle_phi_deg, alpha_aero_deg, beta_mech_deg,
                  delta_alpha_aero_deg, delta_beta_mech_deg
        """
        adj_lookup = {
            (a.condition, a.section): a.delta_pitch for a in pitch_adjustments
        }
        rows = [
            {
                "condition":                r.condition,
                "section":                  r.section,
                "axial_velocity_m_s":       r.axial_velocity,
                "tangential_velocity_m_s":  r.tangential_velocity,
                "inflow_angle_phi_deg":     r.inflow_angle_deg,
                "alpha_aero_deg":           r.alpha_aero_deg,
                "beta_mech_deg":            r.beta_mech_deg,
                "delta_alpha_aero_deg":     adj_lookup.get((r.condition, r.section), 0.0),
                "delta_beta_mech_deg":      r.delta_beta_mech_deg,
            }
            for r in kinematics_results
        ]
        df = pd.DataFrame(rows).sort_values(["condition", "section"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, index=False, float_format="%.4f")

    @staticmethod
    def write_text_summary(summary_text: str, output_path: Path) -> None:
        """Escribe un resumen de texto en el path indicado."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(summary_text, encoding="utf-8")
