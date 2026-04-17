"""
sfc_analysis_service.py
-----------------------
Orquesta el cálculo de reducción de SFC para todas las condiciones de vuelo
usando los resultados 3D de Stage 5 (cascada + Snel) como fuente de epsilon.

Modelo físico (ver sfc_parameters.py para notación):
    ε(r, cond)      = CL/CD_vpf_3D / CL/CD_fijo_3D
      CL/CD_vpf_3D  = Stage5 optimal_incidence.csv → CL_CD_max  (cascada + Snel)
      CL/CD_fijo_3D = K_weinig × interp(Stage3 polar KT, alpha_fixed)
      alpha_fixed   = beta_metal[sec] − phi_inflow[cond, sec]
                      (triángulo de velocidades con beta_metal de Stage 5)
      K_weinig      = Stage5 cascade_corrections.csv → K_weinig
    Para crucero: ε = 1.0 por definición (pala diseñada para este punto)

    ε_eff           = min(ε, EPSILON_CAP)    (EPSILON_CAP = 3.0)
    Δη_profile(r)   = (ε_eff − 1) × τ
    Δη_fan          = weighted_mean_r(Δη_profile)   [ponderado por área anular]
                      capped at ETA_FAN_DELTA_CAP
    η_fan,new       = min(η_base × (1 + Δη_fan), ETA_FAN_ABS_CAP)
    SFC_new         = SFC_base / (1 + k × Δη_applied / η_base)
    k               = BPR / (1 + BPR)

Ref: Saravanamuttoo et al. (2017) §5.3; Cumpsty (2004) p. 280;
     Dixon & Hall (2013) §7.4.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
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
    stage5_dir: Path | None = None,
    stage3_dir: Path | None = None,
) -> Tuple[List[SfcAnalysisResult], List[SfcSectionResult]]:
    """Calcula el análisis de SFC para todas las condiciones de vuelo.

    Integra dos mecanismos físicos independientes de mejora de eficiencia:

    **Mecanismo 1 — Perfil (3D, Stage 5)**:
        ε = CL/CD_vpf_3D / CL/CD_fijo_3D
          CL/CD_vpf_3D  de Stage5 optimal_incidence.csv (cascada + Snel)
          CL/CD_fijo_3D = K_weinig × interp(Stage3 polar KT, alpha_fixed)
          alpha_fixed   = beta_metal[sec] − phi_inflow[cond, sec]
        Δη_profile = weighted_mean_r[(min(ε, ε_cap) − 1) × τ],  cap ≤ ETA_FAN_DELTA_CAP
        Ponderación por área anular de cada sección.

    **Mecanismo 2 — Mapa del fan (coeficiente de flujo φ)**:
        φ(cond, sec) = Va_cond / U_sec   (cambia con condición de vuelo)
        Δη_map = k_map × ((φ − φ_opt) / φ_opt)²,  cap ≤ ETA_FAN_MAP_CAP

    **Combinado**:
        Δη_fan = min(Δη_profile + Δη_map, ETA_FAN_COMBINED_CAP)

    Parameters
    ----------
    metrics_df : pd.DataFrame
        Tabla de métricas de Stage 4 (``summary_table.csv``).
    engine_baseline : EngineBaseline
        Parámetros base del motor.
    config_path : Path, optional
        Ruta a ``engine_parameters.yaml`` (para τ y SFC multipliers).
    stage5_dir : Path, optional
        Directorio raíz de Stage 5 (contiene ``tables/``).
        Si se proporciona, se usan datos 3D de Stage 5 para epsilon.
        Si es None, se hace fallback a Stage 4 (comportamiento anterior).
    stage3_dir : Path, optional
        Directorio raíz de Stage 3 (contiene ``{cond}/{sec}/corrected_polar.csv``).
        Requerido si stage5_dir se proporciona.

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

    # ── Cargar datos 3D de Stage 5 ────────────────────────────────────────
    _s5: Optional[Dict] = None
    if stage5_dir is not None and stage5_dir.is_dir():
        try:
            _s5 = _load_stage5_tables(stage5_dir)
            LOGGER.info("Datos 3D de Stage 5 cargados desde %s", stage5_dir)
        except Exception as exc:
            LOGGER.warning("No se pudo cargar Stage 5: %s — fallback a Stage 4.", exc)

    # ── Pesos por área anular (para media ponderada de epsilon) ───────────
    _annular_w = _annular_weights(_radii) if _radii else {}

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

            # Mecanismo de perfil: usar Stage 5 si disponible, sino Stage 4
            if _s5 is not None and stage3_dir is not None:
                sr_base = _compute_section_result_stage5(condition, row, tau, _s5, stage3_dir)
            else:
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

        # ── Agregación por condición (media ponderada por área anular) ────
        epsilon_values   = [s.epsilon for s in cond_sections]
        epsilon_w_values = [
            (s.epsilon, _annular_w.get(s.blade_section, 1.0))
            for s in cond_sections
        ]
        phi_values       = [s.phi_condition for s in cond_sections
                            if not _math.isnan(s.phi_condition)]
        phi_design_val   = _mean([s.phi_design for s in cond_sections
                                  if not _math.isnan(s.phi_design)])
        delta_alpha_vals = [s.delta_alpha_deg for s in cond_sections]
        cl_cd_fixed_vals = [s.cl_cd_fixed for s in cond_sections]
        cl_cd_vpf_vals   = [s.cl_cd_vpf for s in cond_sections]

        # Usar media ponderada de epsilon para el mecanismo de perfil
        epsilon_weighted = _weighted_mean(epsilon_w_values) if epsilon_w_values else _mean(epsilon_values)

        (eta_fan_new,
         delta_eta_profile,
         delta_eta_map_mean,
         delta_eta_applied) = compute_combined_fan_efficiency_improvement(
            epsilon_values=[epsilon_weighted] * len(epsilon_values),  # ponderado spanwise
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
            epsilon_mean=epsilon_weighted,
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
            "%s: ε_pond=%.3f  Δη_perfil=%.4f  Δη_mapa=%.4f  Δη_total=%.4f  "
            "η_new=%.4f  ΔSFC=%.2f%%",
            condition, epsilon_weighted,
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


def _compute_section_result_stage5(
    condition: str,
    row: pd.Series,
    tau: float,
    s5: Dict,
    stage3_dir: Path,
) -> SfcSectionResult:
    """Calcula el resultado por sección usando Stage 5 (triángulos) + Stage 3 (polar KT).

    Modelo correcto de epsilon:
        ε = CL/CD_2D(alpha_opt, cond/sec) / CL/CD_2D(alpha_fixed, cond/sec)

    Ambos valores salen del mismo polar Stage 3 (mismas condiciones Re/Mach).
    K_weinig y Snel se cancelan en el ratio: son iguales para VPF y paso fijo
    ya que ambas opciones usan el mismo álabe en la misma cascada.

    alpha_opt   = ángulo de diseño VPF (de kinematics_analysis, alpha_aero_deg)
    alpha_fixed = beta_metal_cruise - phi_cond  (pala fija en ángulo de crucero)
    """
    section = str(row.get("blade_section", "unknown"))
    delta_alpha = float(row.get("delta_alpha_deg", 0.0))

    # ── Obtener alpha_opt y alpha_fixed ──────────────────────────────────
    btd = s5["blade_twist_design"]
    kin = s5["kinematics"]

    row_btd = btd[btd["section"] == section]
    row_kin_cond  = kin[(kin["condition"] == condition)  & (kin["section"] == section)]

    if row_btd.empty or row_kin_cond.empty:
        LOGGER.warning("Datos cinemáticos Stage 5 incompletos para %s/%s — fallback.", condition, section)
        return _compute_section_result(condition, row, tau)

    beta_metal = float(row_btd["beta_metal_deg"].iloc[0])
    phi_cond   = float(row_kin_cond["inflow_angle_phi_deg"].iloc[0])
    alpha_opt  = float(row_kin_cond["alpha_aero_deg"].iloc[0])   # VPF siempre opera aquí
    alpha_fixed = beta_metal - phi_cond

    # ── Cargar polar Stage 3 de la condición/sección ─────────────────────
    polar_path = stage3_dir / condition.lower() / section / "corrected_polar.csv"
    if not polar_path.is_file():
        LOGGER.warning("Polar Stage 3 no encontrado: %s — fallback Stage 4.", polar_path)
        return _compute_section_result(condition, row, tau)

    polar_df = pd.read_csv(polar_path)
    alphas = polar_df["alpha"].values
    cl_kt_arr  = polar_df["cl_kt"].values
    cd_arr     = polar_df["cd_corrected"].values

    def _interp_cl_cd(alpha: float) -> float:
        a = float(np.clip(alpha, alphas.min(), alphas.max()))
        cl = float(np.interp(a, alphas, cl_kt_arr))
        cd = float(np.interp(a, alphas, cd_arr))
        return cl / cd if cd > 0.0 else float("nan")

    cl_cd_vpf   = _interp_cl_cd(alpha_opt)
    cl_cd_fixed = _interp_cl_cd(alpha_fixed)

    if alpha_fixed < alphas.min() - 0.5 or alpha_fixed > alphas.max() + 0.5:
        LOGGER.warning(
            "alpha_fixed=%.2f° fuera del rango polar [%.1f, %.1f] para %s/%s — clamped.",
            alpha_fixed, alphas.min(), alphas.max(), condition, section,
        )

    # ── Epsilon ──────────────────────────────────────────────────────────
    import math as _m
    if cl_cd_fixed > 0.0 and not _m.isnan(cl_cd_fixed) and not _m.isnan(cl_cd_vpf):
        epsilon = cl_cd_vpf / cl_cd_fixed
    else:
        epsilon = 1.0
        LOGGER.warning("CL/CD_fixed inválido para %s/%s — epsilon=1.", condition, section)

    epsilon_eff = min(epsilon, EPSILON_CAP)
    delta_eta_profile = (epsilon_eff - 1.0) * tau
    efficiency_gain_pct = (epsilon - 1.0) * 100.0

    LOGGER.debug(
        "%s/%s: β_metal=%.2f° φ=%.2f° α_opt=%.2f° α_fixed=%.2f° "
        "CL/CD_vpf=%.1f CL/CD_fixed=%.1f ε=%.3f",
        condition, section, beta_metal, phi_cond, alpha_opt, alpha_fixed,
        cl_cd_vpf, cl_cd_fixed, epsilon,
    )

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


def _load_stage5_tables(stage5_dir: Path) -> Dict:
    """Carga las tablas necesarias de Stage 5."""
    td = stage5_dir / "tables"
    return {
        "optimal_incidence": pd.read_csv(td / "optimal_incidence.csv"),
        "blade_twist_design": pd.read_csv(td / "blade_twist_design.csv"),
        "kinematics": pd.read_csv(td / "kinematics_analysis.csv"),
        "cascade": pd.read_csv(td / "cascade_corrections.csv"),
    }


def _annular_weights(radii: Dict[str, float]) -> Dict[str, float]:
    """Pesos proporcionales al área anular de cada sección de pala.

    Aproxima el área del anillo representado por cada punto de control
    usando los puntos medios entre secciones adyacentes como fronteras.
    La sección más interna (root) se extiende hasta el radio de cubo (estimado).
    """
    sections = ["root", "mid_span", "tip"]
    r = [radii.get(s, 0.0) for s in sections]
    if any(v <= 0 for v in r):
        return {}

    # Fronteras del anillo: punto medio entre secciones adyacentes
    # Hub estimado como root - (mid - root)/2, con mínimo de 0.
    r_hub = max(r[0] - (r[1] - r[0]) / 2.0, 0.0)
    boundaries = [
        r_hub,
        (r[0] + r[1]) / 2.0,
        (r[1] + r[2]) / 2.0,
        r[2],
    ]
    areas = [boundaries[i + 1] ** 2 - boundaries[i] ** 2 for i in range(3)]
    total = sum(areas)
    if total <= 0:
        return {}
    return {s: a / total for s, a in zip(sections, areas)}


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


def _weighted_mean(values_weights: List[Tuple[float, float]]) -> float:
    """Media ponderada: [(valor, peso), ...]."""
    total_w = sum(w for _, w in values_weights)
    if total_w <= 0:
        return _mean([v for v, _ in values_weights])
    return sum(v * w for v, w in values_weights) / total_w
