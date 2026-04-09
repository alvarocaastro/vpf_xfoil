# Stage 8: Impacto en consumo específico de combustible (SFC)

## Propósito

Estimar cuánto puede mejorar el consumo específico del motor si el fan opera cerca del punto óptimo de incidencia habilitado por el concepto Variable Pitch Fan.

## Entradas

- `results/stage6_vpf_analysis/tables/vpf_optimal_pitch.csv`
- Parámetros de motor en `config/engine_parameters.yaml`
  - `baseline_sfc`
  - `fan_efficiency`
  - `bypass_ratio`
  - `profile_efficiency_transfer`
  - `sfc_multipliers`

## Metodología

1. Se parte de una eficiencia aerodinámica baseline y de la eficiencia con VPF.
2. La mejora 2D se amortigua con un factor de transferencia hacia eficiencia de fan:

```text
eta_fan,new = eta_base * [1 + tau * ((CL/CD)_VPF / (CL/CD)_base - 1)]
```

3. A partir de esa nueva eficiencia se estima el cambio en SFC por condición de vuelo.

## Resultado resumido de la ejecución actual

| Condición | Reducción estimada de SFC |
|---|---:|
| Takeoff | 4.96 % |
| Climb | 3.16 % |
| Cruise | 0.00 % |
| Descent | 1.72 % |

Media simple del envolvente analizado: `2.46 %`.

## Salidas

La salida de esta etapa queda agrupada en su propia carpeta de resultados.

```text
results/stage8_sfc_analysis/
├── tables/
│   └── sfc_analysis.csv
├── figures/
│   ├── sfc_vs_condition.png
│   ├── sfc_reduction_percent.png
│   ├── fan_efficiency_improvement.png
│   └── efficiency_vs_sfc.png
└── sfc_analysis_summary.txt
```

## Código relevante

- `src/vfp_analysis/stage8_sfc_analysis/application/run_sfc_analysis.py`
- `src/vfp_analysis/stage8_sfc_analysis/core/services/sfc_analysis_service.py`
- `src/vfp_analysis/stage8_sfc_analysis/core/services/propulsion_model_service.py`
- `config/engine_parameters.yaml`

## Observaciones

- En la versión actualizada del pipeline, Stage 8 ya escribe directamente en `results/stage8_sfc_analysis/`.
