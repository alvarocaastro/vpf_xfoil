# Stage 1: Selección automática del perfil aerodinámico

## Propósito

Comparar varios perfiles candidatos para la pala del fan y escoger uno único que sirva como geometría base para el resto del pipeline.

## Entradas

- Geometrías en `data/airfoils/`
- Definición de candidatos en `src/vfp_analysis/config.py`
- Condición de referencia de selección en `config/analysis_config.yaml`
  - `Re = 3.0e6`
  - `M = 0.2`
  - `Ncrit = 7.0`
  - `alpha = [-5°, 20°]` con paso `0.15°`

## Perfiles evaluados

- `NACA 65-210`
- `NACA 65-410`
- `NACA 63-215`
- `NACA 0012`

## Metodología

1. Se ejecuta XFOIL para cada perfil bajo la misma condición de referencia.
2. Se calcula una puntuación multicriterio a partir de:
   - eficiencia máxima en el segundo pico `(CL/CD)_2nd`
   - margen de estabilidad `stall_alpha - alpha_opt`
   - robustez local del punto operativo, medida como la media de `CL/CD` en una ventana alrededor de `alpha_opt`
3. Se selecciona el perfil con mayor puntuación total.

El criterio evita que el primer pico de eficiencia de XFOIL a bajo ángulo, asociado a la burbuja laminar, domine la selección. Así Stage 1 queda alineada con el resto del pipeline, que también trabaja con el segundo pico de eficiencia como punto operativo real.

La lógica de scoring está en `src/vfp_analysis/stage1_airfoil_selection/scoring.py`.

## Resultado principal

- Perfil seleccionado en la ejecución actual: `NACA 65-410`

## Salidas

Los artefactos de esta etapa se escriben en `results/stage1_airfoil_selection/airfoil_selection/`.

```text
results/stage1_airfoil_selection/
├── airfoil_selection/
│   ├── NACA_0012_polar.txt
│   ├── NACA_63-215_polar.txt
│   ├── NACA_65-210_polar.txt
│   ├── NACA_65-410_polar.txt
│   └── selected_airfoil.dat
└── finalresults_stage1.txt
```

## Código relevante

- `src/vfp_analysis/stage1_airfoil_selection/airfoil_selection_service.py`
- `src/vfp_analysis/stage1_airfoil_selection/scoring.py`
- `src/vfp_analysis/adapters/xfoil/xfoil_runner_adapter.py`
- `src/vfp_analysis/xfoil_runner.py`

## Observaciones

- Esta etapa no exporta actualmente un CSV de scores; el resultado persistente es el perfil seleccionado y las polares crudas de cada candidato.
- El perfil elegido alimenta directamente la Stage 2.
