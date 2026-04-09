# Stage 4: Métricas de rendimiento y tablas consolidadas

## Propósito

Extraer métricas aerodinámicas comparables entre casos y exportarlas a CSV para análisis y redacción del TFG.

## Entradas

- Polares de `results/stage2_xfoil_simulations/final_analysis/`
- Reynolds y `Ncrit` desde `config/analysis_config.yaml`

## Qué calcula

Para cada caso se calcula:

- `max_efficiency`
- `alpha_opt`
- `cl_max`
- `cl_at_opt`
- `cd_at_opt`

El punto operativo se define como el segundo pico de eficiencia, descartando el primer máximo a bajo ángulo asociado al artefacto de burbuja laminar.

## Resultado resumido de la ejecución actual

- Casos analizados: `12`
- Rango de `alpha_opt`: `5.35°` a `7.30°`
- Rango de `(CL/CD)_max`: `89.05` a `121.06`

## Salidas

En el estado actual del pipeline corregido, esta etapa guarda sus tablas propias en `results/stage4_performance_metrics/tables/`.

```text
results/stage4_performance_metrics/
├── tables/
│   ├── summary_table.csv
│   ├── clcd_max_by_section.csv
└── finalresults_stage4.txt
```

## Código relevante

- `src/vfp_analysis/stage4_performance_metrics/metrics.py`
- `src/vfp_analysis/stage4_performance_metrics/table_generator.py`
- `src/vfp_analysis/postprocessing/aerodynamics_utils.py`

## Observaciones

- Las métricas exportadas por `summary_table.csv` se calculan actualmente sobre las polares de Stage 2.
- Las etapas 6, 7 y 8 ya tienen carpetas de resultados propias y separadas del bloque de métricas.
