# Stage 4: Métricas de rendimiento y tablas consolidadas

## Propósito

Extraer métricas aerodinámicas comparables entre casos y exportarlas a CSV para análisis y redacción del TFG. A partir de esta etapa el pipeline utiliza las polares corregidas de Stage 3 (Kármán-Tsien + wave drag), lo que garantiza que las métricas reflejan los efectos de compresibilidad reales en cada condición de vuelo.

## Entradas

- Polares corregidas de `results/stage3_compressibility_correction/{condición}/{sección}/corrected_polar.csv`
  - Fallback automático a `results/stage2_xfoil_simulations/simulation_plots/` si Stage 3 no existe
- Reynolds y `Ncrit` desde `config/analysis_config.yaml`

## Qué calcula

Para cada caso (12 = 4 condiciones × 3 secciones) se calculan:

| Métrica | Descripción |
|---|---|
| `max_efficiency` | $(C_L/C_D)_{max}$ — segundo pico de eficiencia ($\alpha \geq 3°$) |
| `alpha_opt` | Ángulo de ataque en el punto de máxima eficiencia |
| `cl_max` | Coeficiente de sustentación máximo (rango completo del polar) |
| `cl_at_opt` | $C_L$ en el punto óptimo |
| `cd_at_opt` | $C_D$ en el punto óptimo |
| `stall_margin` | $\alpha_{stall} - \alpha_{opt}$ (deg) — margen de seguridad frente a pérdida |
| `cm_at_opt` | Coeficiente de momento de cabeceo en el punto óptimo |
| `alpha_design` | α_opt en crucero para la misma sección (ángulo de diseño de paso fijo) |
| `delta_alpha` | α_opt − α_design: ajuste de pitch requerido por el VPF [°] |
| `eff_at_design_alpha` | (CL/CD) evaluado en α_design (rendimiento con paso fijo en esta condición) |
| `eff_gain_pct` | (max_efficiency − eff_at_design_alpha) / eff_at_design_alpha × 100 [%] |

El punto operativo se define como el segundo pico de eficiencia, descartando el primer máximo a bajo ángulo asociado al artefacto de burbuja laminar de XFOIL.

El margen de pérdida `stall_margin` se estima detectando el primer $\alpha$ donde $C_L$ cae más de un 5 % por debajo de $C_{L,max}$ tras el pico (metodología NACA TN-1135).

## Resultado resumido de la ejecución actual

- Casos analizados: `12`
- Rango de `alpha_opt`: `5.35°` a `7.30°`
- Rango de `(CL/CD)_max`: `89.05` a `121.06`

## Salidas

```text
results/stage4_performance_metrics/
├── tables/
│   ├── summary_table.csv          — tabla completa con las 9 métricas
│   └── clcd_max_by_section.csv    — tabla centrada en el punto operativo CL/CD
├── figures/
│   ├── efficiency_heatmap.png     — mapa de calor (CL/CD)_max por condición × sección
│   ├── alpha_opt_comparison.png   — barras agrupadas de alpha_opt por condición/sección
│   └── stall_margin_overview.png  — margen de pérdida por caso con umbral de 3°
└── finalresults_stage4.txt
```

## Código relevante

- `src/vfp_analysis/stage4_performance_metrics/metrics.py`
- `src/vfp_analysis/stage4_performance_metrics/table_generator.py`
- `src/vfp_analysis/stage4_performance_metrics/plots.py`
- `src/vfp_analysis/postprocessing/aerodynamics_utils.py`
  - `resolve_efficiency_column` — prioridad: `ld_corrected` > `ld_kt` > `ld` > `CL_CD`
  - `find_second_peak_row` — segundo pico ($\alpha \geq 3°$)
  - `compute_stall_alpha` — detección de pérdida por caída del 5 % en $C_L$

## Observaciones

- Las métricas se calculan ahora sobre las polares de Stage 3 (columna `ld_kt` para eficiencia, `cl_kt` para sustentación y `cd_corrected` para resistencia con wave drag incluido).
- Si Stage 3 no ha sido ejecutado, el fallback lee automáticamente las polares de Stage 2.
- `cm_at_opt` es `NaN` cuando la polar de Stage 3 no incluye columna `cm` (columna presente en Stage 2 pero no exportada por Stage 3 por defecto).
