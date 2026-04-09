# Stage 7: Cinemática y triángulos de velocidad

## Propósito

Traducir el ajuste aerodinámico calculado en Stage 6 a un ajuste mecánico real de pala, usando velocidades axial y tangencial en cada radio.

## Entradas

- `results/stage6_vpf_analysis/tables/vpf_pitch_adjustment.csv`
- Parámetros del motor en `config/engine_parameters.yaml`
  - `fan_rpm`
  - `speed_of_sound_m_s`
  - `radii_m`
  - `target_mach`

## Modelo usado

La etapa resuelve, para cada condición y sección:

- velocidad axial `V_ax`
- velocidad tangencial `U`
- ángulo de entrada `phi`
- pitch mecánico requerido `beta_mech`

La relación clave es:

```text
delta_beta_mech = delta_alpha_aero + delta_phi
```

## Resultado resumido de la ejecución actual

- 12 casos resueltos
- los mayores ajustes mecánicos aparecen en `takeoff`, con deltas mucho más grandes que los puramente aerodinámicos

## Salidas

```text
results/stage7_kinematics_analysis/
├── tables/
│   └── kinematics_analysis.csv
├── figures/
│   └── kinematics_comparison.png
└── finalresults_stage7.txt
```

## Código relevante

- `src/vfp_analysis/stage7_kinematics_analysis/application/run_kinematics_stage.py`
- `src/vfp_analysis/stage7_kinematics_analysis/core/services/kinematics_service.py`
- `config/engine_parameters.yaml`

## Observaciones

- Esta etapa no reemplaza las tablas de VPF; las complementa con la interpretación mecánica.
- En la práctica, es la prueba de que pequeñas variaciones de incidencia aerodinámica pueden traducirse en cambios mecánicos bastante mayores.
