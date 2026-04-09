# Stage 6: Análisis VPF

## Propósito

Calcular el ángulo de ataque óptimo de operación para cada condición y sección, y obtener el ajuste aerodinámico de pitch necesario respecto al caso de crucero.

## Entradas

- Polares de Stage 2
- Polares corregidas de Stage 3
- Condición de referencia: `cruise`

## Metodología

1. Se cargan los datos de Stage 2 y, si existen, los corregidos de Stage 3.
2. Para cada caso, se localiza el segundo pico de eficiencia.
3. Se guarda:
   - `alpha_opt`
   - `(CL/CD)_max`
   - `delta_pitch = alpha_opt(condición) - alpha_opt(cruise)`

## Resultado resumido de la ejecución actual

- `alpha_opt` entre `5.35°` y `7.30°`
- media de `(CL/CD)_max`: `105.16`

## Salidas

La implementación actual reparte salidas entre tablas consolidadas y carpeta propia de figuras:

```text
results/stage6_vpf_analysis/
├── tables/
│   ├── vpf_optimal_pitch.csv
│   └── vpf_pitch_adjustment.csv
├── figures/
│   ├── vpf_alpha_opt_vs_condition.png
│   ├── vpf_pitch_adjustment.png
│   ├── vpf_efficiency_curves_{condition}.png
│   └── vpf_section_comparison.png
├── vpf_analysis_summary.txt
└── finalresults_stage6.txt
```

## Código relevante

- `src/vfp_analysis/stage6_vpf_analysis/application/run_vpf_analysis.py`
- `src/vfp_analysis/stage6_vpf_analysis/core/services/optimal_incidence_service.py`
- `src/vfp_analysis/stage6_vpf_analysis/core/services/pitch_adjustment_service.py`
- `src/vfp_analysis/stage6_vpf_analysis/core/services/summary_generator_service.py`

## Observaciones

- Esta etapa prioriza los datos corregidos por compresibilidad cuando están disponibles.
- Las tablas y figuras de VPF quedan ahora agrupadas dentro de su propia carpeta de stage.
