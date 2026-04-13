"""
sfc_analysis_service.py
-----------------------
Orquesta el cálculo de reducción de SFC para todas las condiciones de vuelo
a partir de los datos de rendimiento aerodináimico de Stage 4.

Modelo físico (ver sfc_parameters.py para notación):
    ε(r, cond)      = max_efficiency / eff_at_design_alpha   [Stage 4]
    ε_eff           = min(ε, EPSILON_CAP)
    Δη_profile(r)   = (ε_eff − 1) × τ
    Δη_fan          = mean_r(Δη_profile)  capped at ETA_FAN_DELTA_CAP
    η_fan,new       = min(η_base × (1 + Δη_fan), ETA_FAN_ABS_CAP)
    SFC_new         = SFC_base / (1 + k × Δη_applied / η_base)
    k               = BPR / (1 + BPR)

Ref: Saravanamuttoo et al. (2017) §5.3; Cumpsty (2004) p. 280;
     Dixon & Hall (2013) §7.4.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import yaml

from vfp_analysis.config_loader import get_flight_conditions
from vfp_analysis.stage6_sfc_analysis.core.domain.sfc_parameters import (
    EPSILON_CAP,
    ETA_FAN_ABS_CAP,
    ETA_FAN_DELTA_CAP,
    EngineBaseline,
    SfcAnalysisResult,
    SfcSectionResult,
    SfcSensitivityPoint,
)
from vfp_analysis.stage6_sfc_analysis.core.services.propulsion_model_service import (
    compute_bypass_sensitivity_factor,
    compute_combined_fan_efficiency_improvement,
    compute_fan_map_efficiency_gain,
    compute_sfc_improvement,
    compute_sfc_reduction_percent,
)

LOGGER = logging.getLogger(__name__)

_DEFAULT_TAU_VALUES: List[float] = [0.30, 0.37, 0.43, 0.50, 0.57, 0.65, 0.73, 0.80]


# ---------------------------------------------------------------------------
# Análisis principal
# ---------------------------------------------------------------------------

def compute_sfc_analysis(
    metrics_df: pd.DataFrame,
    engine_baseline: EngineBaseline,
    config_path: Path | None = None,
) -> Tuple[List[SfcAnalysisResult], List[SfcSectionResult]]:
    """Calcula el análisis de SFC para todas las condiciones de vuelo.

    Integra dos mecanismos físicos independientes de mejora de eficiencia:

    **Mecanismo 1 — Perfil (2D → 3D vía τ)**:
        ε = CL/CD_vpf / CL/CD_fijo_real  (incidencia correcta por triángulos, Stage 4)
        Δη_profile = mean_r[(min(ε, ε_cap) − 1) × τ],  cap ≤ ETA_FAN_DELTA_CAP

    **Mecanismo 2 — Mapa del fan (coeficiente de flujo φ)**:
        φ(cond, sec) = Va_cond / U_sec   (cambia con condición de vuelo)
        Δη_map = k_map × ((φ − φ_opt) / φ_opt)²,  cap ≤ ETA_FAN_MAP_CAP

    **Combinado**:
        Δη_fan = min(Δη_profile + Δη_map, ETA_FAN_COMBINED_CAP)

    Parameters
    ----------
    metrics_df : pd.DataFrame
        Tabla de métricas de Stage 4 (``summary_table.csv``).
        Debe contener: ``flight_condition``, ``blade_section``,
        ``max_efficiency``, ``eff_at_design_alpha``, ``delta_alpha_deg``.
    engine_baseline : EngineBaseline
        Parámetros base del motor.
    config_path : Path, optional
        Ruta a ``engine_parameters.yaml`` (para τ y SFC multipliers).

    Returns
    -------
    sfc_results : list[SfcAnalysisResult]
        Resultados agregados por condición.
    section_results : list[SfcSectionResult]
        Resultados desagregados por condición × sección.
    """
    import math as _math

    tau, sfc_multipliers = _load_config(config_path)
    k = compute_bypass_sensitivity_factor(engine_baseline.bypass_ratio)
    flight_conditions = get_flight_conditions()

    # ── Cargar datos cinemáticos (Va, radii, RPM) para el mecanismo de mapa ─
    try:
        from vfp_analysis.config_loader import get_axial_velocities, get_blade_radii, get_fan_rpm
        _va = get_axial_velocities()
        _radii = get_blade_radii()
        _rpm = get_fan_rpm()
        _omega = _rpm * (2.0 * 3.141592653589793 / 60.0)
        _use_map = True
        # φ_design (crucero) por sección
        _va_cruise = _va.get("cruise", 150.0)
        _phi_design: dict = {sec: _va_cruise / (_omega * r) for sec, r in _radii.items()}
        LOGGER.info("Mecanismo de mapa activo: RPM=%.0f, Va_cruise=%.1f m/s", _rpm, _va_cruise)
    except Exception as exc:
        LOGGER.warning("No se pudo cargar datos cinemáticos para mapa: %s — solo mecanismo perfil.", exc)
        _use_map = False
        _va = {}
        _radii = {}
        _omega = 0.0
        _phi_design = {}

    section_results: List[SfcSectionResult] = []
    sfc_results: List[SfcAnalysisResult] = []

    for condition in flight_conditions:
        cond_df = metrics_df[metrics_df["flight_condition"] == condition]
        if cond_df.empty:
            LOGGER.warning("No hay datos de Stage 4 para condición '%s' — omitida.", condition)
            continue

        _va_cond = _va.get(condition, 0.0) if _use_map else 0.0

        # ── Nivel de sección ─────────────────────────────────────────────
        cond_sections: List[SfcSectionResult] = []
        for _, row in cond_df.iterrows():
            section = str(row.get("blade_section", "unknown"))

            # Mecanismo de perfil
            sr_base = _compute_section_result(condition, row, tau)

            # Mecanismo de mapa
            if _use_map and section in _radii and _omega > 0:
                u_sec = _omega * _radii[section]
                phi_cond = _va_cond / u_sec if u_sec > 0 else float("nan")
                phi_des  = _phi_design.get(section, float("nan"))
                delta_eta_map = (
                    compute_fan_map_efficiency_gain(phi_cond, phi_des)
                    if not _math.isnan(phi_cond) and not _math.isnan(phi_des)
                    else 0.0
                )
            else:
                phi_cond = float("nan")
                phi_des  = _phi_design.get(section, float("nan"))
                delta_eta_map = 0.0

            delta_eta_total = sr_base.delta_eta_profile + delta_eta_map

            import dataclasses as _dc
            sr = _dc.replace(
                sr_base,
                phi_condition=phi_cond,
                phi_design=phi_des,
                delta_eta_map=delta_eta_map,
                delta_eta_total=delta_eta_total,
            )
            cond_sections.append(sr)
        section_results.extend(cond_sections)

        # ── Agregación por condición ──────────────────────────────────────
        epsilon_values   = [s.epsilon for s in cond_sections]
        phi_values       = [s.phi_condition for s in cond_sections
                            if not _math.isnan(s.phi_condition)]
        phi_design_val   = _mean([s.phi_design for s in cond_sections
                                  if not _math.isnan(s.phi_design)])
        delta_alpha_vals = [s.delta_alpha_deg for s in cond_sections]
        cl_cd_fixed_vals = [s.cl_cd_fixed for s in cond_sections]
        cl_cd_vpf_vals   = [s.cl_cd_vpf for s in cond_sections]

        (eta_fan_new,
         delta_eta_profile,
         delta_eta_map_mean,
         delta_eta_applied) = compute_combined_fan_efficiency_improvement(
            epsilon_values=epsilon_values,
            phi_values=phi_values,
            phi_design=phi_design_val if not _math.isnan(phi_design_val) else 0.0,
            fan_efficiency_baseline=engine_baseline.fan_efficiency,
            tau=tau,
        )

        sfc_multiplier = sfc_multipliers.get(condition, 1.0)
        sfc_baseline = engine_baseline.baseline_sfc * sfc_multiplier
        sfc_new = compute_sfc_improvement(
            sfc_baseline=sfc_baseline,
            delta_eta_fan=delta_eta_applied,
            eta_fan_baseline=engine_baseline.fan_efficiency,
            k=k,
        )
        sfc_reduction = compute_sfc_reduction_percent(sfc_baseline, sfc_new)

        sfc_results.append(SfcAnalysisResult(
            condition=condition,
            cl_cd_fixed=_mean(cl_cd_fixed_vals),
            cl_cd_vpf=_mean(cl_cd_vpf_vals),
            epsilon_mean=_mean(epsilon_values),
            delta_alpha_mean_deg=_mean(delta_alpha_vals),
            fan_efficiency_baseline=engine_baseline.fan_efficiency,
            fan_efficiency_new=eta_fan_new,
            delta_eta_fan=delta_eta_applied,
            k_sensitivity=k,
            sfc_baseline=sfc_baseline,
            sfc_new=sfc_new,
            sfc_reduction_percent=sfc_reduction,
            delta_eta_profile=delta_eta_profile,
            delta_eta_map=delta_eta_map_mean,
            phi_design=phi_design_val if not _math.isnan(phi_design_val) else float("nan"),
            phi_condition=_mean(phi_values) if phi_values else float("nan"),
        ))

        LOGGER.info(
            "%s: ε_mean=%.3f  Δη_perfil=%.4f  Δη_mapa=%.4f  Δη_total=%.4f  "
            "η_new=%.4f  ΔSFC=%.2f%%",
            condition, _mean(epsilon_values),
            delta_eta_profile, delta_eta_map_mean, delta_eta_applied,
            eta_fan_new, sfc_reduction,
        )

    return sfc_results, section_results


# ---------------------------------------------------------------------------
# Análisis de sensibilidad a τ
# ---------------------------------------------------------------------------

def compute_sfc_sensitivity(
    metrics_df: pd.DataFrame,
    engine_baseline: EngineBaseline,
    tau_values: List[float] | None = None,
    config_path: Path | None = None,
) -> List[SfcSensitivityPoint]:
    """Barrido paramétrico de SFC sobre el coeficiente de transferencia τ.

    Parameters
    ----------
    metrics_df : pd.DataFrame
        Tabla de métricas de Stage 4 (misma que ``compute_sfc_analysis``).
    engine_baseline : EngineBaseline
        Parámetros base del motor.
    tau_values : list[float], optional
        Valores de τ a evaluar. Por defecto: [0.30, 0.37, 0.43, 0.50, 0.57, 0.65, 0.73, 0.80].
    config_path : Path, optional
        Ruta a ``engine_parameters.yaml`` (para SFC multipliers).

    Returns
    -------
    list[SfcSensitivityPoint]
        Puntos del barrido, ordenados por (tau, condition).
    """
    if tau_values is None:
        tau_values = _DEFAULT_TAU_VALUES

    _, sfc_multipliers = _load_config(config_path)
    k = compute_bypass_sensitivity_factor(engine_baseline.bypass_ratio)
    flight_conditions = get_flight_conditions()

    points: List[SfcSensitivityPoint] = []

    for tau in tau_values:
        for condition in flight_conditions:
            cond_df = metrics_df[metrics_df["flight_condition"] == condition]
            if cond_df.empty:
                continue

            epsilon_values = []
            for _, row in cond_df.iterrows():
                cl_cd_fixed = float(row.get("eff_at_design_alpha", 0.0))
                cl_cd_vpf = float(row.get("max_efficiency", 0.0))
                if cl_cd_fixed > 0:
                    epsilon_values.append(cl_cd_vpf / cl_cd_fixed)

            if not epsilon_values:
                continue

            eta_fan_new, _, _, delta_eta_applied = compute_combined_fan_efficiency_improvement(
                epsilon_values=epsilon_values,
                phi_values=[],
                phi_design=0.0,
                fan_efficiency_baseline=engine_baseline.fan_efficiency,
                tau=tau,
            )

            sfc_multiplier = sfc_multipliers.get(condition, 1.0)
            sfc_baseline = engine_baseline.baseline_sfc * sfc_multiplier
            sfc_new = compute_sfc_improvement(
                sfc_baseline=sfc_baseline,
                delta_eta_fan=delta_eta_applied,
                eta_fan_baseline=engine_baseline.fan_efficiency,
                k=k,
            )
            sfc_reduction = compute_sfc_reduction_percent(sfc_baseline, sfc_new)

            points.append(SfcSensitivityPoint(
                tau=tau,
                condition=condition,
                epsilon_mean=_mean(epsilon_values),
                delta_eta_fan=delta_eta_applied,
                eta_fan_new=eta_fan_new,
                sfc_baseline=sfc_baseline,
                sfc_new=sfc_new,
                sfc_reduction_pct=sfc_reduction,
            ))

    return points


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

def _compute_section_result(
    condition: str,
    row: pd.Series,
    tau: float,
) -> SfcSectionResult:
    """Calcula el resultado por sección para una fila de Stage 4.

    ``eff_at_design_alpha`` contiene CL/CD evaluado en la incidencia real
    sin VPF (α_fixed = β_cruise − φ_condition), calculada con triángulos de
    velocidad en Stage 4. ``delta_alpha_deg`` es el ajuste total de VPF.
    """
    cl_cd_fixed = float(row.get("eff_at_design_alpha", 0.0))
    cl_cd_vpf = float(row.get("max_efficiency", 0.0))
    delta_alpha = float(row.get("delta_alpha_deg", 0.0))
    section = str(row.get("blade_section", "unknown"))

    if cl_cd_fixed > 0:
        epsilon = cl_cd_vpf / cl_cd_fixed
    else:
        epsilon = 1.0
        LOGGER.warning("eff_at_design_alpha = 0 para %s/%s — asumiendo ε = 1.0", condition, section)

    epsilon_eff = min(epsilon, EPSILON_CAP)
    delta_eta_profile = (epsilon_eff - 1.0) * tau
    efficiency_gain_pct = (epsilon - 1.0) * 100.0

    return SfcSectionResult(
        condition=condition,
        blade_section=section,
        cl_cd_fixed=cl_cd_fixed,
        cl_cd_vpf=cl_cd_vpf,
        epsilon=epsilon,
        epsilon_eff=epsilon_eff,
        delta_eta_profile=delta_eta_profile,
        efficiency_gain_pct=efficiency_gain_pct,
        delta_alpha_deg=delta_alpha,
    )


def _load_config(config_path: Path | None) -> Tuple[float, dict]:
    """Lee τ y sfc_multipliers de engine_parameters.yaml."""
    tau = 0.65
    sfc_multipliers: dict = {}
    if config_path and config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            tau = float(cfg.get("profile_efficiency_transfer", tau))
            sfc_multipliers = cfg.get("sfc_multipliers", {})
        except Exception as exc:
            LOGGER.warning("No se pudo leer engine_parameters.yaml: %s — usando τ=%.2f", exc, tau)
    return tau, sfc_multipliers


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0
