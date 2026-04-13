# Stage 5: Cinemática de pitch — análisis 3D de fan

## Propósito

Traducir las polares 2D de XFOIL a un análisis realista de fan en cascada 3D. El stage aplica cuatro capas de análisis sobre los resultados de Stage 4, cuantifica el beneficio del VPF frente al paso fijo y calcula la carga de etapa.

## Entradas

- Polares corregidas de `results/stage3_compressibility_correction/`
- Métricas de `results/stage4_performance_metrics/tables/summary_table.csv`
- `config/analysis_config.yaml`: geometría del fan (RPM, radios, cuerdas, número de álabes Z)
- `config/engine_parameters.yaml`: velocidades axiales por condición

## Cuatro módulos de análisis

### A — Corrección de cascada (Weinig + Carter)

Los perfiles de un fan operan en cascada, no como perfiles aislados. La solidez `σ = c/s` (donde `s = 2πr/Z`) determina la magnitud del efecto interpaleta.

```
s(r)        = 2πr / Z
σ(r)        = c(r) / s(r)

K_weinig(σ) = (π/2·σ) / arctan(π·σ/2)   — factor de pendiente de CL en cascada
CL_cascade  = CL_2D × K_weinig

δ_carter(r) = m · θ / √σ(r)              — desviación de salida del flujo [°]
  m = 0.23  (NACA 6-series, a/c = 0.5)
```

Ref: Dixon & Hall (2013) ec. 3.54; Carter (1950) NACA TN-2273.

### B — Corrección rotacional 3D (Snel + Du-Selig)

La rotación crea fuerzas de Coriolis y gradientes centrífugos que incrementan CL y retrasan el stall. El efecto es proporcional a (c/r)² y decrece hacia el tip.

**Snel (lineal):**
```
ΔCL_rot(r) = a · (c/r)² · CL_2D     a = 3.0  [Snel et al. 1994]
CL_3D      = CL_cascade + ΔCL_rot
CD_3D      ≈ CD_cascade               (corrección de drag < 2%, despreciable)
```

**Du-Selig (no lineal, con saturación):** corrección adicional que limita el incremento de CL al aproximarse a la condición de stall, más precisa en root donde (c/r) es mayor.

Magnitudes estimadas (modelo Snel): root ≈ +8% CL, mid-span ≈ +1.7%, tip ≈ +0.5%.

### C — Twist de diseño y compromiso off-design

Con un único actuador que gira toda la pala uniformemente, root, mid-span y tip no pueden estar simultáneamente en su α_opt individual fuera de la condición de diseño (crucero).

```
φ_flow(r, cond)  = arctan(Va(cond) / U(r))          — ángulo de flujo
β_metal(r)       = α_opt_3D_cruise(r) + φ_flow(r, cruise)  — ángulo mecánico de diseño
twist_total      = β_metal(root) − β_metal(tip)              [°]

# Off-design: actuador mueve Δβ_hub para optimizar mid-span
α_actual(r, cond)      = β_metal(r) + Δβ_hub(cond) − φ_flow(r, cond)
Δα_compromise(r, cond) = α_actual − α_opt_3D(r, cond)
loss_pct(r, cond)      = 1 − (CL/CD)[α_actual] / (CL/CD)_max_3D
```

### D — Carga de etapa (Euler, φ, ψ)

```
φ(r)   = Va(cond) / U(r)                   — coeficiente de caudal
V_θ(r) = U − Va / tan(β_mech_3D)           — velocidad tangencial impartida
ψ(r)   = V_θ / U                            — coeficiente de trabajo
W_spec = U · V_θ  [J/kg]                   — trabajo específico (ec. de Euler)
```

Zona de diseño fan alto bypass: φ ∈ [0.35, 0.55], ψ ∈ [0.25, 0.50].  
Ref: Dixon & Hall (2013) cap. 5.

## Salidas

```text
results/stage5_pitch_kinematics/
├── tables/
│   ├── cascade_corrections.csv           — σ, s, K_weinig, δ_carter, CL_2D vs CL_cascade
│   ├── rotational_corrections.csv        — c/r, ΔCL_snel, α_opt_2D vs α_opt_3D
│   ├── rotational_corrections_du_selig.csv — ídem con modelo Du-Selig (no lineal)
│   ├── kinematics_analysis.csv           — tabla resumen cinemática completa por caso
│   ├── optimal_incidence.csv             — α_opt_3D por condición × sección  ← usado por Stage 6
│   ├── pitch_adjustment.csv              — Δα_3D, Δβ_mech_3D por condición
│   ├── blade_twist_design.csv            — β_metal(r), φ_flow(r), twist_from_tip
│   ├── off_design_incidence.csv          — α_actual, Δα_compromise, efficiency_loss_pct
│   └── stage_loading.csv                 — φ, ψ, W_spec, in_design_zone
├── figures/
│   ├── cascade_solidity_profile.png
│   ├── cascade_cl_correction.png
│   ├── deviation_angle_carter.png
│   ├── polars_2d_vs_3d_root.png          — efecto combinado cascada + Snel en root
│   ├── snel_correction_spanwise.png
│   ├── rotational_model_comparison.png   — Snel vs Du-Selig por sección
│   ├── blade_twist_profile.png
│   ├── off_design_incidence_heatmap.png
│   ├── pitch_adjustment.png              — Δβ requerido por condición y sección
│   ├── pitch_compromise_loss.png
│   ├── phi_psi_operating_map.png         — diagrama φ-ψ con banda de diseño
│   ├── work_distribution.png
│   ├── loading_profile_spanwise.png
│   ├── alpha_opt_2d_vs_3d.png
│   ├── alpha_opt_by_condition.png        — α_opt_3D agrupado por condición
│   ├── efficiency_curves_{condition}.png — CL/CD 3D por sección (×4)
│   └── kinematics_comparison.png
└── finalresults_stage5.txt
```

## Código relevante

- `src/vfp_analysis/stage5_pitch_kinematics/application/run_pitch_kinematics.py` — orquestador
- `src/vfp_analysis/stage5_pitch_kinematics/core/services/cascade_correction_service.py`
- `src/vfp_analysis/stage5_pitch_kinematics/core/services/rotational_correction_service.py`
  - Modelos Snel y Du-Selig implementados en paralelo
- `src/vfp_analysis/stage5_pitch_kinematics/core/services/blade_twist_service.py`
- `src/vfp_analysis/stage5_pitch_kinematics/core/services/stage_loading_service.py`
- `src/vfp_analysis/stage5_pitch_kinematics/core/services/optimal_incidence_service.py`
- `src/vfp_analysis/stage5_pitch_kinematics/core/services/pitch_adjustment_service.py`
- `src/vfp_analysis/stage5_pitch_kinematics/core/services/kinematics_service.py`
- `src/vfp_analysis/stage5_pitch_kinematics/adapters/filesystem/data_loader.py`
- `src/vfp_analysis/stage5_pitch_kinematics/adapters/filesystem/results_writer.py`

## Observaciones

- El análisis 3D de Stage 5 es complementario al 2D de compresibilidad de Stage 3: Stage 3 corrige el Mach del perfil aislado, Stage 5 añade los efectos de cascada y rotación.
- La tabla `optimal_incidence.csv` contiene los valores 3D que alimentan directamente Stage 6 para el cálculo de SFC.
- El twist total β_metal(root) − β_metal(tip) ≈ 30–40° es físicamente consistente con fans de alto bypass (Cumpsty 2004, ch. 3).

## Referencias

| Fuente | Descripción |
|--------|-------------|
| Dixon & Hall (2013) | Dixon, S.L. & Hall, C.A. *Fluid Mechanics and Thermodynamics of Turbomachinery*, 7th ed. Butterworth-Heinemann, 2013. — ec. Euler, diagrama φ-ψ (cap. 5), factor Weinig (ec. 3.54) |
| Cumpsty (2004) | Cumpsty, N.A. *Compressor Aerodynamics*. Krieger Publishing, 2004. — twist de diseño, flows secundarios, zona de diseño fan (ch. 3 y 8) |
| Saravanamuttoo et al. (2017) | Saravanamuttoo, H.I.H., Rogers, G.F.C., Cohen, H. & Straznicky, P. *Gas Turbine Theory*, 7th ed. Pearson, 2017. — fundamentos de turbomáquinas de flujo axial (cap. 5) |
| Snel et al. (1994) | Snel, H., Houwink, R. & Bosschers, J. "Sectional prediction of lift coefficients on rotating wind turbine blades in stall." ECN-C--93-052, 1994. — coeficiente a = 3.0 para corrección rotacional |
| Carter (1950) | Carter, A.D.S. "The low speed performance of related aerofoils in cascade." NACA TN-2273, 1950. — regla de desviación de Carter (m = 0.23 para NACA 6-series) |
| GT2010-22148 | ASME GT2010-22148 — aerodinámica de fans de paso variable. [`docs/references/GT2010-22148_final_correctformat.pdf`] |
