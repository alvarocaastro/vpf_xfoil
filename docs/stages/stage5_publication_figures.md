# Stage 5: Generación de figuras

## Propósito

Construir las figuras del proyecto con formato homogéneo para memoria, presentación y comparación rápida entre condiciones.

## Entradas

- Polares base de Stage 2
- Métricas calculadas en Stage 4
- Opcionalmente, polares corregidas de Stage 3 para figuras ampliadas

## Figuras principales

Las figuras base del pipeline son:

- `efficiency_{condition}_{section}.png`
- `efficiency_by_section_{condition}.png`
- `alpha_opt_vs_condition.png`

## Figuras ampliadas soportadas por el código

Si Stage 3 está disponible, `figure_generator.py` también puede producir:

- `section_polar_comparison_{condition}.png`
- `cruise_penalty_{condition}.png`

Estas figuras usan las polares corregidas para reforzar la comparación entre operación con paso fijo y operación con VPF.

## Salidas

En la instantánea actual del repositorio se observan las 17 figuras base:

```text
results/stage5_publication_figures/
├── figures/
│   ├── efficiency_{condition}_{section}.png
│   ├── efficiency_by_section_{condition}.png
│   └── alpha_opt_vs_condition.png
└── finalresults_stage5.txt
```

## Código relevante

- `src/vfp_analysis/stage5_publication_figures/figure_generator.py`
- `src/vfp_analysis/postprocessing/aerodynamics_utils.py`

## Observaciones

- El estilo gráfico se centraliza en `figure_generator.py` mediante `matplotlib.rcParams`.
- Si faltan las figuras ampliadas en `results/stage5_publication_figures/figures/`, basta con regenerar el pipeline con Stage 3 disponible.
