# Stage 1: Selección automática del perfil aerodinámico

## Propósito

Comparar varios perfiles candidatos para el álabe del fan y escoger uno único que sirva como geometría base para el resto del pipeline.

## Entradas

- Geometrías en `data/airfoils/`
- Definición de candidatos en `src/vfp_analysis/config.py`
- Condición de referencia en `config/analysis_config.yaml`:
  - `Re = 3.0e6`, `M = 0.2`, `Ncrit = 7.0`
  - `alpha = [-5°, 20°]` con paso `0.15°`

## Perfiles evaluados

| Perfil      | Familia        | Adecuado para fan                                          |
|-------------|----------------|-----------------------------------------------------------|
| NACA 65-410 | NACA 65-series | ✅ Sí — estándar de compresores axiales                   |
| NACA 65-210 | NACA 65-series | ✅ Sí — menor carga, apto para tip                        |
| NACA 63-215 | NACA 63-series | ⚠️ Sí, pero literatura más orientada a turbinas eólicas   |
| NACA 0012   | Simétrico      | ❌ No recomendado — sin curvatura, baja eficiencia         |

## Metodología

1. XFOIL ejecutado para cada perfil bajo la misma condición de referencia.
2. Puntuación multicriterio calculada a partir de:
   - Eficiencia máxima en el segundo pico `(CL/CD)_2nd` — el primer pico (burbuja laminar) se ignora deliberadamente
   - Margen de estabilidad `α_stall − α_opt`
   - Robustez local: media de `CL/CD` en una ventana alrededor de `α_opt`
3. Se selecciona el perfil con mayor puntuación total.

El criterio de segundo pico garantiza que la selección queda alineada con el punto operativo real utilizado en el resto del pipeline.

## Resultado

- **Perfil seleccionado: `NACA 65-410`**

## Salidas

```text
results/stage1_airfoil_selection/
├── airfoil_selection/
│   ├── NACA_0012_polar.txt
│   ├── NACA_63-215_polar.txt
│   ├── NACA_65-210_polar.txt
│   ├── NACA_65-410_polar.txt
│   └── selected_airfoil.dat       ← geometría del perfil ganador
└── finalresults_stage1.txt
```

## Código relevante

- `src/vfp_analysis/stage1_airfoil_selection/application/run_airfoil_selection.py` — orquestador
- `src/vfp_analysis/stage1_airfoil_selection/airfoil_selection_service.py`
- `src/vfp_analysis/stage1_airfoil_selection/scoring.py`
- `src/vfp_analysis/adapters/xfoil/xfoil_runner_adapter.py`

## Referencias

| Fuente | Descripción |
|--------|-------------|
| Drela (1989) | Drela, M. "XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils." *Low Reynolds Number Aerodynamics*, Springer, 1989. — herramienta de simulación viscosa |
| NACA TN-1135 (1953) | Ames Research Staff. "Equations, Tables, and Charts for Compressible Flow." NACA TN-1135, 1953. — tablas de flujo compresible de referencia |
| Cumpsty (2004) | Cumpsty, N.A. *Compressor Aerodynamics*. Krieger Publishing, 2004. — criterios de selección de perfil para compresores/fans axiales |
| NASA Power for Flight | Gorn, M. *The Power for Flight: NASA's Contributions to Aircraft Propulsion*. NASA SP-2015-4548, 2015. [`docs/references/The_Power_for_Flight_-_NASA's_Contributions_to_Aircraft_Propulsion.pdf`] |
