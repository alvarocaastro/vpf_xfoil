# Stage 6: Análisis de impacto en SFC

## Propósito

Cuantificar la reducción de consumo específico de combustible (SFC) que permite el VPF frente al paso fijo, usando un modelo de transferencia de eficiencia de perfil a fan derivado de primeros principios. Incluye análisis de misión con estimación de combustible y emisiones CO₂ por fase de vuelo.

## Entradas

- `results/stage4_performance_metrics/tables/summary_table.csv`  
  Columnas clave: `max_efficiency`, `eff_at_design_alpha`, `delta_alpha_deg`
- `config/engine_parameters.yaml`  
  `baseline_sfc`, `fan_efficiency`, `bypass_ratio`, `profile_efficiency_transfer` (τ), `sfc_multipliers`

## Modelo físico

El beneficio del VPF es la diferencia entre operar la pala a su ángulo óptimo (α_opt) frente a mantenerla fijada en el ángulo de diseño de crucero (α_design). Ambos valores son evaluados por XFOIL en las mismas condiciones de Mach/Re, garantizando una comparación apples-to-apples.

### Paso 1 — Ratio de eficiencia por sección

```
ε(r, cond) = CL/CD_vpf(r, cond) / CL/CD_fixed(r, cond)
           = max_efficiency     / eff_at_design_alpha    [Stage 4]
```

Por definición: ε = 1.00 en crucero (punto de diseño, sin beneficio VPF).

### Paso 2 — Ganancia de eficiencia de perfil

```
ε_eff(r)        = min(ε(r), 1.10)          — cap 3D (Cumpsty 2004 p. 280)
Δη_profile(r)   = (ε_eff − 1) × τ          τ = 0.65 (profile_efficiency_transfer)
```

El cap `ε_eff ≤ 1.10` refleja que pérdidas 3D (separación de esquina, flujos secundarios, interacción pala-endwall) limitan la transferencia de ganancias 2D en cascada real.

### Paso 3 — Agregación span-wise y caps físicos

```
Δη_fan_raw    = mean_r(Δη_profile)
Δη_fan_capped = min(Δη_fan_raw, 0.04)     — mejora absoluta máxima (Cumpsty 2004 p. 280)
η_fan,new     = min(η_fan,base × (1 + Δη_fan_capped),  0.96)
Δη_applied    = η_fan,new − η_fan,base
```

### Paso 4 — Reducción de SFC

```
k = BPR / (1 + BPR) = 10/11 ≈ 0.909       — fracción de empuje del fan (Saravanamuttoo 2017 ec. 5.14)

SFC_new = SFC_base / (1 + k × Δη_applied / η_fan,base)
ΔSFC[%] = (SFC_base − SFC_new) / SFC_base × 100
```

### Paso 5 — Análisis de misión

Estimación de combustible quemado y emisiones CO₂ por fase:

```
fuel_kg(fase) = SFC [lb/(lbf·h)] × thrust_lbf × duration_h × LB_TO_KG
CO₂_kg(fase)  = fuel_kg × 3.16        (factor CORSIA, kerosene)
```

### Análisis de sensibilidad

Se barre τ ∈ [0.30, 0.80] (7 valores) para acotar el rango de incertidumbre del modelo.

## Parámetros del motor de referencia

| Parámetro | Valor | Fuente |
|-----------|------:|--------|
| `baseline_sfc` | 0.55 lb/(lbf·hr) | Típico turbofan alto bypass (Rolls-Royce Trent, GE90) |
| `fan_efficiency` | 0.88 | Valor representativo de diseño |
| `bypass_ratio` | 10.0 | Alto bypass moderno |
| `profile_efficiency_transfer` τ | 0.65 | Juicio ingenieril; Peretz & Gany (1992) |
| `sfc_multipliers` | takeoff 1.15, climb 1.05, cruise 1.00, descent 0.95 | Escalado relativo al crucero |

## Resultados de la ejecución actual

| Condición | ε medio | Δη_fan | η_fan,new | ΔSFC    |
|-----------|--------:|-------:|----------:|--------:|
| Crucero   | 1.000   | 0.0000 | 0.8800    | 0.00%   |
| Descenso  | 1.053   | 0.0303 | 0.9103    | 3.04%   |
| Ascenso   | 1.130   | 0.0352 | 0.9152    | 3.51%   |
| Despegue  | 1.273   | 0.0352 | 0.9152    | 3.51%   |
| **Media** |         |        |           | **2.51%** |

Rango de referencia para VPF: 2–5% (Cumpsty 2004, p. 280). ✓

## Salidas

```text
results/stage6_sfc_analysis/
├── tables/
│   ├── sfc_section_breakdown.csv  — ε, ε_eff, Δη por condición × sección
│   ├── sfc_analysis.csv           — resultados agregados por condición
│   └── sfc_sensitivity.csv        — barrido de τ × condición
├── figures/
│   ├── fixed_vs_vpf_efficiency.png  — CL/CD_fijo vs CL/CD_vpf por sección (2×2 subplots)
│   ├── epsilon_spanwise.png         — ε(r) por sección, con cap en 1.10
│   ├── sfc_sensitivity_tau.png      — ΔSFC vs τ para cada condición
│   ├── sfc_combined.png             — ΔSFC por condición (barras) + resumen
│   └── mission_fuel_burn.png        — combustible y CO₂ ahorrado por fase de misión
├── sfc_analysis_summary.txt         — resumen con tabla ε y referencias
└── finalresults_stage6.txt
```

## Código relevante

- `src/vfp_analysis/stage6_sfc_analysis/application/run_sfc_analysis.py` — orquestador
- `src/vfp_analysis/stage6_sfc_analysis/core/services/sfc_analysis_service.py`
  - `compute_sfc_analysis()` — modelo principal, retorna `(List[SfcAnalysisResult], List[SfcSectionResult])`
  - `compute_sfc_sensitivity()` — barrido paramétrico de τ
- `src/vfp_analysis/stage6_sfc_analysis/core/services/propulsion_model_service.py`
  - `compute_bypass_sensitivity_factor()` — k = BPR/(1+BPR)
  - `compute_sfc_improvement()` — perturbación de 1er orden
- `src/vfp_analysis/stage6_sfc_analysis/core/services/mission_analysis_service.py`
  - Cálculo de combustible y CO₂ por fase usando SFC y thrust por condición
- `src/vfp_analysis/stage6_sfc_analysis/core/services/summary_generator_service.py`
- `src/vfp_analysis/stage6_sfc_analysis/core/domain/sfc_parameters.py`
  - Constantes: `EPSILON_CAP = 1.10`, `ETA_FAN_DELTA_CAP = 0.04`, `ETA_FAN_ABS_CAP = 0.96`

## Referencias

| Ecuación | Fuente |
|----------|--------|
| ε = CL/CD_vpf / CL/CD_fixed | Stage 4 (XFOIL, mismo Mach/Re) |
| ε_eff ≤ 1.10 | Cumpsty (2004) p. 280; Wisler (1998) VKI |
| Δη = (ε_eff−1)×τ | Dixon & Hall (2013) §2.6 |
| k = BPR/(1+BPR) | Saravanamuttoo et al. (2017) ec. 5.14 |
| SFC_new = SFC_base/(1+k·Δη/η_base) | Saravanamuttoo (2017) §5.3 |
| Δη_fan,max = 0.04 | Cumpsty (2004) p. 280 |
| η_fan,new ≤ 0.96 | Cumpsty (2004) ch. 8 |
| CO₂/kerosene = 3.16 kg/kg | ICAO CORSIA (2022) |

### Bibliografía completa

| Clave | Cita completa |
|-------|--------------|
| Cumpsty (2004) | Cumpsty, N.A. *Compressor Aerodynamics*. Krieger Publishing, 2004. [`docs/references/`] |
| Dixon & Hall (2013) | Dixon, S.L. & Hall, C.A. *Fluid Mechanics and Thermodynamics of Turbomachinery*, 7th ed. Butterworth-Heinemann, 2013. |
| Saravanamuttoo (2017) | Saravanamuttoo, H.I.H., Rogers, G.F.C., Cohen, H. & Straznicky, P. *Gas Turbine Theory*, 7th ed. Pearson, 2017. |
| Snel et al. (1994) | Snel, H., Houwink, R. & Bosschers, J. "Sectional prediction of lift coefficients on rotating wind turbine blades in stall." ECN-C--93-052, 1994. |
| Carter (1950) | Carter, A.D.S. "The low speed performance of related aerofoils in cascade." NACA TN-2273, 1950. |
| Drela (1989) | Drela, M. "XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils." *Low Reynolds Number Aerodynamics*, Springer, 1989. |
| NACA TN-1135 (1953) | Ames Research Staff. "Equations, Tables, and Charts for Compressible Flow." NACA TN-1135, 1953. |
| CORSIA (2022) | ICAO. *CORSIA Eligible Fuels — Life Cycle Assessment Methodology*, 4th ed. 2022. |
| GT2010-22148 | ASME GT2010-22148 — aerodinámica de fans de paso variable. [`docs/references/GT2010-22148_final_correctformat.pdf`] |
| Rolls-Royce UltraFan | Rolls-Royce. *UltraFan Fact Sheet*. [`docs/references/ultrafan-fact-sheet.pdf`] |
| NASA Power for Flight | Gorn, M. *The Power for Flight: NASA's Contributions to Aircraft Propulsion*. NASA SP-2015-4548, 2015. [`docs/references/The_Power_for_Flight_-_NASA's_Contributions_to_Aircraft_Propulsion.pdf`] |
| Bentley (2018) | Bentley, D. *Principles of Measurement Systems*, 4th ed. Pearson, 2018. [`docs/references/Bentley_D_2018.pdf`] |

## Limitaciones del modelo

- Modelo 1D de transferencia de eficiencia — no incluye efectos de estrangulamiento, purgas, válvulas de derivación ni enfriamiento.
- τ = 0.65 es un valor de ingeniería; el análisis de sensibilidad (figura `sfc_sensitivity_tau.png`) acota el rango [2%, 5%] para τ ∈ [0.30, 0.80].
- SFC_multipliers son escalados relativos al crucero, sin modelo termodinámico del ciclo completo. Para mayor rigor sería necesario un modelo de ciclo Brayton completo (entalpías, relaciones de presión por etapa).
