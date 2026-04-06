## Stage 1 — Selección automática de perfil

### Objetivo

Comparar todos los perfiles contenidos en `airfoil_data/` bajo **las mismas
condiciones de referencia** y seleccionar automáticamente el más adecuado para
las palas del fan.

Condiciones de simulación:

- Mach: `M = 0.2`
- Reynolds de referencia: `Re = 3e6`
- Rango de ángulo de ataque: `alpha ∈ [-5, 20]` con paso `0.5` grados

### Scripts y módulos implicados

- `core/domain/airfoil.py`  
  Define la entidad `Airfoil` (nombre, familia, ruta al `.dat`).

- `core/domain/simulation_condition.py`  
  Define `SimulationCondition` (Mach, Re, rango de alpha).

- `core/domain/scoring.py`  
  Implementa `score_airfoil(df)` y la clase `AirfoilScore`.  
  La puntuación combina:
  - `max(CL/CD)` (eficiencia máxima)
  - ángulo de pérdida aproximado (stall angle)
  - `avg(CD)` (resistencia media)

- `ports/xfoil_runner_port.py`  
  Puerto abstracto `XfoilRunnerPort` para lanzar polares con XFOIL.

- `adapters/xfoil/xfoil_runner_adapter.py`  
  Adaptador que usa el módulo existente `xfoil_runner.py` y la configuración
  de `config.py` para ejecutar XFOIL de verdad.

- `core/services/airfoil_selection_service.py`  
  Servicio de dominio que:
  1. Lanza XFOIL para cada perfil usando el puerto `XfoilRunnerPort`.
  2. Lee las polares generadas y construye un `DataFrame` con:
     `airfoil, condition, mach, re, alpha, cl, cd, cm, ld`.
  3. Calcula un `AirfoilScore` por perfil y selecciona el mejor.
  4. Guarda el nombre del perfil ganador en:
     `results/airfoil_selection/selected_airfoil.dat`.

- `application/run_airfoil_selection.py`  
  Caso de uso de alto nivel. Construye la lista de `Airfoil` a partir de
  `config.AIRFOILS`, define la condición de selección y llama al servicio.

### Resultado de Stage 1

Al ejecutar:

```bash
cd C:\Users\Alvaro\Desktop\tfg_vpf
.\.venv\Scripts\python -m vfp_analysis.application.run_airfoil_selection
```

el sistema:

1. Simula todos los perfiles definidos en `config.AIRFOILS`.
2. Calcula la puntuación de cada perfil.
3. Escribe el perfil seleccionado en:
   `results/stage_1/airfoil_selection/selected_airfoil.dat`.

En la última ejecución, el mejor perfil seleccionado fue:

- **NACA 65-410**

