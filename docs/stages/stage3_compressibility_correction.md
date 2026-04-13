# Stage 3: Corrección de compresibilidad

## Propósito

Corregir las polares incompresibles de Stage 2 (generadas a `M = 0.2`) para aproximar el comportamiento aerodinámico real a los Mach de vuelo de cada condición. Se aplican dos modelos de corrección de CL, corrección del momento de cabeceo CM, arrastre de onda y estimación del Mach crítico.

## Entradas

- Polares de `results/stage2_xfoil_simulations/simulation_plots/{condition}/{section}/polar.csv`
- `config/analysis_config.yaml`:

`M_target` representa el **Mach relativo en mid-span** (W_rel/a), que es el valor físicamente
correcto para aplicar la corrección de compresibilidad 2D a la sección de álabe.
Con la geometría GE9X (r_mid=1.00 m, RPM=2200, U_mid=230.4 m/s):

| Condición | M_ref | M_target | W_mid [m/s] | a [m/s] | Zona       |
|-----------|------:|---------:|-------------|---------|------------|
| Takeoff   |   0.2 |     0.85 | 294         | 340     | Transónico |
| Climb     |   0.2 |     0.85 | 277         | 320     | Transónico |
| Cruise    |   0.2 |     0.93 | 274         | 295     | Transónico alto |
| Descent   |   0.2 |     0.80 | 262         | 328     | Transónico |

- Geometría del perfil: `thickness_ratio = 0.10`, `korn_kappa = 0.87` (NACA 65-series)

## Modelos aplicados

### 1. Prandtl-Glauert (PG)
Corrección lineal de primer orden, válida hasta ~M = 0.65:
```
β = sqrt(1 - M²)
CL_PG = CL_0 × (β_ref / β_target)
CM_PG = CM_0 × (β_ref / β_target)
```

### 2. Kármán-Tsien (K-T)
Corrección no lineal, más precisa para M > 0.5. Tiene en cuenta que el valor de CL modifica localmente la distribución de presiones:
```
denom(CL, M) = β + M²/(2(1+β)) × CL
CL_KT = CL_0 × denom(CL_0, M_ref) / denom(CL_0, M_target)
CM_KT = CM_0 × denom(CM_0, M_ref) / denom(CM_0, M_target)
```
K-T da valores de CL menores que PG para M alto — PG sobreestima el efecto en crucero (M=0.85).

### 3. Arrastre de onda — Ley de Lock (4ª potencia)
Corrección de CD activa cuando `M > Mdd`:
```
Mdd = κ/tc - CL/10 - tc/10        (ecuación de Korn)
ΔCD_wave = 20 × (M - Mdd)^4       (ley de Lock)
CD_corrected = CD_original + ΔCD_wave
```
Con `κ = 0.87` y `tc = 0.10` para NACA 65-series. El wave drag es significativo en crucero (M=0.85 > Mdd ≈ 0.79).

### 4. Mach crítico (Mcr)
Estimado con la fórmula empírica de Küchemann para NACA 6-series:
```
Mcr ≈ 0.87 − 0.108 × CL_operativo
```
Se anota en cada plot. Si `M_target > Mcr`, se marca como zona supercrítica.

## Metodología

1. Para cada uno de los 12 casos (condición × sección), se lee la polar de Stage 2.
2. Se aplica PG → se añaden columnas `cl_pg`, `cm_pg`.
3. Sobre el resultado de PG, se aplica K-T → se añaden `cl_kt`, `cm_kt`, `cd_corrected`, `ld_kt`.
4. Se recalcula `ld_pg` usando el `cd_corrected` (consistente con K-T).
5. Se guarda un único CSV con todos los datos y un plot comparativo de 2 paneles.
6. Se generan 3 plots de resumen (uno por sección) con las 4 condiciones superpuestas.

## Salidas

```text
results/stage3_compressibility_correction/
├── {condition}/{section}/
│   ├── corrected_polar.csv        ← alpha, cl, cl_pg, cl_kt, cd, cd_corrected,
│   │                                 ld_pg, ld_kt, mach_target, re, ncrit,
│   │                                 cm, cm_pg, cm_kt
│   └── corrected_plots.png        ← CL(α) y CL/CD(α): original vs PG vs K-T
├── figures/
│   ├── correction_comparison_root.png     ┐
│   ├── correction_comparison_mid_span.png ├── 4 condiciones superpuestas por sección
│   └── correction_comparison_tip.png      ┘
└── finalresults_stage3.txt
```

## Código relevante

- `src/vfp_analysis/stage3_compressibility_correction/application/run_compressibility_correction.py` — orquestador
- `src/vfp_analysis/stage3_compressibility_correction/correction_service.py`
- `src/vfp_analysis/stage3_compressibility_correction/prandtl_glauert.py`
- `src/vfp_analysis/stage3_compressibility_correction/karman_tsien.py`
- `src/vfp_analysis/stage3_compressibility_correction/critical_mach.py`
- `src/vfp_analysis/stage3_compressibility_correction/compressibility_case.py`
- `src/vfp_analysis/stage3_compressibility_correction/correction_result.py`
- `src/vfp_analysis/shared/plot_style.py`

## Observaciones

- Para takeoff (M=0.30), las diferencias entre PG y K-T son < 1% — ambos modelos convergen a bajos Mach.
- Para crucero (M=0.85), K-T da CL ~10-15% menor que PG. PG sobreestima el efecto de compresibilidad en régimen transónico bajo.
- Ambos modelos son correcciones 2D subcríticas. Por encima de Mcr (zona transónica), la precisión disminuye; para análisis más riguroso en crucero sería necesario CFD RANS.
- Los efectos 3D rotacionales (Snel) y de cascada (Weinig/Carter) no se aplican en esta etapa — se incorporan en Stage 5 (cinemática de pitch).

## Referencias

| Fuente | Descripción |
|--------|-------------|
| NACA TN-1135 (1953) | Ames Research Staff. "Equations, Tables, and Charts for Compressible Flow." NACA TN-1135, 1953. — fundamento teórico de las correcciones Prandtl-Glauert y Kármán-Tsien |
| Cumpsty (2004) | Cumpsty, N.A. *Compressor Aerodynamics*. Krieger Publishing, 2004. — Mach crítico, wave drag y ecuación de Korn en perfiles de compresor |
| Dixon & Hall (2013) | Dixon, S.L. & Hall, C.A. *Fluid Mechanics and Thermodynamics of Turbomachinery*, 7th ed. Butterworth-Heinemann, 2013. — velocidades relativas y triángulos de velocidad de fan |
| Drela (1989) | Drela, M. "XFOIL: An Analysis and Design System for Low Reynolds Number Airfoils." Springer, 1989. — polares incompresibles de referencia |
