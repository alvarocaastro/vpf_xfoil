# Stage 2: XFOIL aerodynamic simulations

## Purpose

Generate aerodynamic polars for the selected aerofoil across a matrix of 12 cases: 4 flight conditions × 3 radial blade sections. Includes velocity triangle analysis and VPF argument visualisation.

## Inputs

- Aerofoil selected in Stage 1 (`selected_airfoil.dat`)
- `config/analysis_config.yaml`:
  - Conditions: `takeoff`, `climb`, `cruise`, `descent`
  - Sections: `root`, `mid_span`, `tip`
  - Angle-of-attack range: `alpha = [-5°, 23°]` with step `0.15°`
  - `M = 0.2` as incompressible reference for XFOIL
  - Reynolds and Ncrit per condition/section (full table below)
  - Fan geometry: RPM, radii per section, axial velocities per phase

## Simulation matrix

| Condition | Ncrit | Root Re  | Mid-span Re | Tip Re   |
|-----------|------:|---------:|------------:|---------:|
| Takeoff   |   5.0 | 2.50e6   | 4.50e6      | 7.00e6   |
| Climb     |   6.0 | 2.20e6   | 4.00e6      | 6.20e6   |
| Cruise    |   7.0 | 1.80e6   | 3.20e6      | 5.00e6   |
| Descent   |   6.0 | 2.00e6   | 3.60e6      | 5.60e6   |

## Methodology

1. XFOIL run for each condition × section combination.
2. Automatic detection of the optimal angle `α_opt` (second CL/CD efficiency peak) and stall angle `α_stall` (CL peak for α > 0).
3. **Velocity triangle analysis**: `α_opt` is converted to blade pitch angle `β = α_opt + φ`, where `φ = arctan(Va / ωr)`, for the three radial sections.
4. Computation of the required pitch variation range `Δβ` to cover all phases — quantitative argument for the variable-pitch fan.
5. Generation of comparative plots to visualise the efficiency penalty of fixing pitch at cruise.

## Outputs

```text
results/stage2_xfoil_simulations/
├── simulation_plots/
│   └── {condition}/{section}/
│       ├── polar.csv              ← full polar (α, CL, CD, CM, Re, Ncrit)
│       ├── polar_plot.png
│       └── cl_alpha_stall.png     ← CL(α) with stall marker
├── polars/
│   └── {condition}_{section}.csv  ← flat copy for quick access
├── pitch_map/
│   ├── alpha_opt_evolution.png    ← α_opt vs flight phase per section
│   ├── pitch_map.png              ← β angle per condition and section
│   ├── pitch_map.csv
│   ├── vpf_efficiency_{section}.png   ← CL/CD(α) for all 4 phases overlaid
│   └── vpf_clcd_penalty.png       ← efficiency penalty from fixing pitch at cruise
└── finalresults_stage2.txt
```

## Stall margin (current results)

| Condition / Section | α_opt  | α_stall | CL_max | Margin |
|---------------------|-------:|--------:|-------:|-------:|
| Takeoff / root      |  6.25° |  14.05° |  1.568 |  7.80° |
| Takeoff / mid_span  |  7.15° |  14.65° |  1.652 |  7.50° |
| Takeoff / tip       |  7.30° |  15.25° |  1.706 |  7.95° |
| Cruise / root       |  5.35° |  13.15° |  1.489 |  7.80° |
| Cruise / tip        |  7.30° |  14.65° |  1.667 |  7.35° |

## Variable pitch range Δβ

| Section  | Required Δβ |
|----------|------------:|
| Root     |        6.1° |
| Mid-span |        8.4° |
| Tip      |        8.8° |

## Relevant code

- `src/vfp_analysis/stage2_xfoil_simulations/application/run_xfoil_simulations.py` — orchestrator
- `src/vfp_analysis/stage2_xfoil_simulations/final_analysis_service.py`
- `src/vfp_analysis/stage2_xfoil_simulations/pitch_map.py`
- `src/vfp_analysis/stage2_xfoil_simulations/polar_organizer.py`
- `src/vfp_analysis/shared/plot_style.py`
- `src/vfp_analysis/adapters/xfoil/xfoil_runner_adapter.py`

## Notes

- All simulations are incompressible at `M = 0.2`. Real Mach effects are applied in Stage 3.
- The velocity triangle assumes pure axial flow (no pre-swirl). 3D rotational effects (Snel) and cascade effects (Weinig/Carter) are applied in Stage 5.

## References

| Source | Description |
|--------|-------------|
| Drela (1989) | Drela, M. "XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils." *Low Reynolds Number Aerodynamics*, Springer, 1989. — viscous simulation tool |
| Dixon & Hall (2013) | Dixon, S.L. & Hall, C.A. *Fluid Mechanics and Thermodynamics of Turbomachinery*, 7th ed. Butterworth-Heinemann, 2013. — velocity triangles, eq. 5.2 |
| Cumpsty (2004) | Cumpsty, N.A. *Compressor Aerodynamics*. Krieger Publishing, 2004. — axial fan fundamentals |
| GT2010-22148 | ASME GT2010-22148 — paper on variable-pitch fan aerodynamics. [`docs/references/GT2010-22148_final_correctformat.pdf`] |
| Rolls-Royce UltraFan | Rolls-Royce. *UltraFan Fact Sheet*. [`docs/references/ultrafan-fact-sheet.pdf`] — reference geometry and parameters for high-bypass fan |
