## Stage 2 — Análisis XFOIL con perfil seleccionado

### Objetivo

Una vez seleccionado el perfil óptimo (Stage 1), el análisis final usa **solo
ese perfil** para representar el álabe del fan en tres secciones radiales:

- `root` (pies de pala)
- `mid_span` (zona media)
- `tip` (punta)

Para cada sección se simulan varias condiciones de vuelo representativas:

- `Takeoff`
- `Climb`
- `Cruise`
- `Descent`

En total: `4 flight conditions × 3 blade sections = 12 simulaciones`.

### Hipótesis aerodinámicas

- El número de Mach relativo se fija en `M = 0.2` para cumplir con las
  limitaciones del solver XFOIL (formulación sub-sónica y compresibilidad
  tratada posteriormente).
- El número de Reynolds depende tanto de la condición de vuelo como de la
  sección radial (tabla final 12 simulaciones):

  | Condición | Root  | Mid   | Tip  |
  |-----------|-------|-------|------|
  | Takeoff   | 2.5e6 | 4.5e6 | 7.0e6 |
  | Climb     | 2.2e6 | 4.0e6 | 6.2e6 |
  | Cruise    | 1.8e6 | 3.2e6 | 5.0e6 |
  | Descent   | 2.0e6 | 3.6e6 | 5.6e6 |

  Esto refleja que la velocidad relativa (y por tanto el Reynolds) aumenta
  hacia el tip, y también varía ligeramente entre fases de vuelo.
- Rango de ángulo de ataque:
  - `alpha_min = -5°`
  - `alpha_max = 23°`
  - `alpha_step = 0.5°`

### Scripts y módulos implicados

- `core/domain/blade_section.py`  
  Define `BladeSection` con nombre de sección (`root`, `mid_span`, `tip`) y
  su Reynolds característico.

- `core/domain/simulation_condition.py`  
  Define `SimulationCondition` (Mach, Re, rango de alpha) reutilizado en todas
  las simulaciones.

- `core/services/final_analysis_service.py`  
  Servicio que:
  1. Lanza XFOIL a través del puerto `XfoilRunnerPort` para cada combinación
     (condición de vuelo, sección radial).
  2. Lee los ficheros `polar.dat` generados.
  3. Genera:
     - `cl_alpha.csv` (CL vs α)
     - `cd_alpha.csv` (CD vs α)
     - `polar_plot.png` (curva CL–CD)
  4. Organiza todos los resultados en:

     ```text
     results/stage_2/final_analysis/<flight>/<section>/
         polar.dat
         cl_alpha.csv
         cd_alpha.csv
         polar_plot.png
     ```

- `application/run_final_simulations.py`  
  Caso de uso que:
  1. Lee el perfil seleccionado desde  
     `results/stage_1/airfoil_selection/selected_airfoil.dat`.
  2. Construye las secciones `root`, `mid_span`, `tip` con sus Reynolds.
  3. Define las condiciones de vuelo (`Takeoff`, `Climb`, `Cruise`, `Descent`).
  4. Llama a `FinalAnalysisService` para ejecutar las 12 simulaciones.

### Cómo ejecutar el análisis final

1. Asegúrate de haber ejecutado antes la selección de perfil (Stage 1):

   ```bash
   cd C:\Users\Alvaro\Desktop\tfg_vpf
   .\.venv\Scripts\python -m vfp_analysis.application.run_airfoil_selection
   ```

2. Ejecuta el análisis final:

   ```bash
   cd C:\Users\Alvaro\Desktop\tfg_vpf
   .\.venv\Scripts\python -m vfp_analysis.application.run_final_simulations
   ```

3. Los resultados estarán en:

   ```text
   results/stage_2/final_analysis/
       takeoff/root/
       takeoff/mid_span/
       takeoff/tip/
       climb/root/
       ...
       descent/tip/
   ```

Estos ficheros (`cl_alpha.csv`, `cd_alpha.csv`, `polar_plot.png`) son los que
se utilizan como base para las figuras y tablas del TFG en los capítulos de
Metodología y Resultados.

