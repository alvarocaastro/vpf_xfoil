# Stage 1: Automatic aerofoil selection

## Purpose

Compare several candidate aerofoils for the fan blade and choose a single one to serve as the base geometry for the rest of the pipeline.

## Inputs

- Geometries in `data/airfoils/`
- Candidate definition in `src/vfp_analysis/config.py`
- Reference condition in `config/analysis_config.yaml`:
  - `Re = 3.0e6`, `M = 0.2`, `Ncrit = 7.0`
  - `alpha = [-5°, 20°]` with step `0.15°`

## Aerofoils evaluated

| Aerofoil    | Family         | Suitable for fan                                              |
|-------------|----------------|---------------------------------------------------------------|
| NACA 65-410 | NACA 65-series | ✅ Yes — standard for axial compressors                       |
| NACA 65-210 | NACA 65-series | ✅ Yes — lower loading, suitable for tip                      |
| NACA 63-215 | NACA 63-series | ⚠️ Yes, but literature more oriented towards wind turbines    |
| NACA 0012   | Symmetric      | ❌ Not recommended — no camber, low efficiency                |

## Methodology

1. XFOIL run for each aerofoil under the same reference condition.
2. Multi-criterion score calculated from:
   - Maximum efficiency at the second peak `(CL/CD)_2nd` — the first peak (laminar bubble) is deliberately ignored
   - Stability margin `α_stall − α_opt`
   - Local robustness: mean `CL/CD` in a window around `α_opt`
3. The aerofoil with the highest total score is selected.

The second-peak criterion ensures that the selection is aligned with the actual operating point used throughout the rest of the pipeline.

## Result

- **Selected aerofoil: `NACA 65-410`**

## Outputs

```text
results/stage1_airfoil_selection/
├── airfoil_selection/
│   ├── NACA_0012_polar.txt
│   ├── NACA_63-215_polar.txt
│   ├── NACA_65-210_polar.txt
│   ├── NACA_65-410_polar.txt
│   └── selected_airfoil.dat       ← geometry of the winning aerofoil
└── finalresults_stage1.txt
```

## Relevant code

- `src/vfp_analysis/stage1_airfoil_selection/application/run_airfoil_selection.py` — orchestrator
- `src/vfp_analysis/stage1_airfoil_selection/airfoil_selection_service.py`
- `src/vfp_analysis/stage1_airfoil_selection/scoring.py`
- `src/vfp_analysis/adapters/xfoil/xfoil_runner_adapter.py`

## References

| Source | Description |
|--------|-------------|
| Drela (1989) | Drela, M. "XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils." *Low Reynolds Number Aerodynamics*, Springer, 1989. — viscous simulation tool |
| NACA TN-1135 (1953) | Ames Research Staff. "Equations, Tables, and Charts for Compressible Flow." NACA TN-1135, 1953. — reference compressible flow tables |
| Cumpsty (2004) | Cumpsty, N.A. *Compressor Aerodynamics*. Krieger Publishing, 2004. — aerofoil selection criteria for axial compressors/fans |
| NASA Power for Flight | Gorn, M. *The Power for Flight: NASA's Contributions to Aircraft Propulsion*. NASA SP-2015-4548, 2015. [`docs/references/The_Power_for_Flight_-_NASA's_Contributions_to_Aircraft_Propulsion.pdf`] |
