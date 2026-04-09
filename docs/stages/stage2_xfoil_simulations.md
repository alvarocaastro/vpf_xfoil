# Stage 2: Simulaciones aerodinámicas con XFOIL

## Propósito

Generar las polares aerodinámicas del perfil seleccionado para una matriz de 12 casos: 4 condiciones de vuelo × 3 secciones radiales del álabe. Incluye análisis de triángulos de velocidad y visualización del argumento VPF.

## Entradas

- Perfil seleccionado en Stage 1 (`selected_airfoil.dat`)
- `config/analysis_config.yaml`:
  - Condiciones: `takeoff`, `climb`, `cruise`, `descent`
  - Secciones: `root`, `mid_span`, `tip`
  - Rango de ataque: `alpha = [-5°, 23°]` con paso `0.15°`
  - `M = 0.2` como referencia incompresible para XFOIL
  - Reynolds y Ncrit por condición/sección (tabla completa abajo)
  - Geometría del fan: RPM, radios por sección, velocidades axiales por fase

## Matriz de simulaciones

| Condición | Ncrit | Root Re  | Mid-span Re | Tip Re   |
|-----------|------:|---------:|------------:|---------:|
| Takeoff   |   5.0 | 2.50e6   | 4.50e6      | 7.00e6   |
| Climb     |   6.0 | 2.20e6   | 4.00e6      | 6.20e6   |
| Cruise    |   7.0 | 1.80e6   | 3.20e6      | 5.00e6   |
| Descent   |   6.0 | 2.00e6   | 3.60e6      | 5.60e6   |

## Metodología

1. XFOIL ejecutado sobre el perfil para cada combinación condición × sección.
2. Detección automática del ángulo óptimo `α_opt` (segundo pico de eficiencia CL/CD) y del ángulo de entrada en pérdidas `α_stall` (pico de CL para α > 0).
3. **Análisis de triángulos de velocidad**: se convierte `α_opt` al ángulo de pitch de álabe `β = α_opt + φ`, donde `φ = arctan(Va / ωr)`, para las tres secciones radiales.
4. Cálculo del rango de variación de pitch `Δβ` necesario para cubrir todas las fases — argumento cuantitativo del fan de paso variable.
5. Generación de plots comparativos para visualizar la penalización de eficiencia al fijar el paso en crucero.

## Salidas

```text
results/stage2_xfoil_simulations/
├── simulation_plots/
│   └── {condition}/{section}/
│       ├── polar.csv              ← polar completa (α, CL, CD, CM, Re, Ncrit)
│       ├── polar_plot.png
│       └── cl_alpha_stall.png     ← CL(α) con marcador de stall
├── polars/
│   └── {condition}_{section}.csv  ← copia plana para acceso rápido
├── vpf_analysis/
│   ├── alpha_opt_evolution.png    ← α_opt vs fase de vuelo por sección
│   ├── pitch_map.png              ← ángulo β por condición y sección
│   ├── pitch_map.csv
│   ├── vpf_efficiency_{section}.png   ← CL/CD(α) de las 4 fases superpuestas
│   └── vpf_clcd_penalty.png       ← penalización de eficiencia al fijar pitch en crucero
└── finalresults_stage2.txt
```

## Margen de stall (resultados actuales)

| Condición / Sección | α_opt  | α_stall | CL_max | Margen |
|---------------------|-------:|--------:|-------:|-------:|
| Takeoff / root      |  6.25° |  14.05° |  1.568 |  7.80° |
| Takeoff / mid_span  |  7.15° |  14.65° |  1.652 |  7.50° |
| Takeoff / tip       |  7.30° |  15.25° |  1.706 |  7.95° |
| Cruise / root       |  5.35° |  13.15° |  1.489 |  7.80° |
| Cruise / tip        |  7.30° |  14.65° |  1.667 |  7.35° |

## Rango de pitch variable Δβ

| Sección  | Δβ requerido |
|----------|-------------:|
| Root     |         6.1° |
| Mid-span |         8.4° |
| Tip      |         8.8° |

## Código relevante

- `src/vfp_analysis/stage2_xfoil_simulations/final_analysis_service.py`
- `src/vfp_analysis/stage2_xfoil_simulations/pitch_map.py`
- `src/vfp_analysis/stage2_xfoil_simulations/polar_organizer.py`
- `src/vfp_analysis/shared/plot_style.py`
- `src/vfp_analysis/adapters/xfoil/xfoil_runner_adapter.py`

## Observaciones

- Todas las simulaciones son incompresibles a `M = 0.2`. Los efectos de Mach real se aplican en Stage 3.
- El triángulo de velocidades asume flujo axial puro (sin pre-swirl). Los efectos 3D rotacionales (Snel/Du-Selig) y de cascada (Weinig/Carter) se incorporarán en Stage 7.
