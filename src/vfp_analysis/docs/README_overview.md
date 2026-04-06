## Visión general del módulo `vfp_analysis`

Este módulo implementa el análisis aerodinámico basado en XFOIL para el TFG
del ventilador de paso variable (Variable Pitch Fan).

La arquitectura sigue un diseño **hexagonal**:

- `core/` — Lógica de dominio y servicios puros (sin dependencias de I/O).
- `ports/` — Interfaces (puertos) que definen cómo el dominio habla con el exterior.
- `adapters/` — Adaptadores concretos (XFOIL, sistema de archivos, etc.).
- `application/` — Casos de uso y scripts de orquestación.

Las fases principales del flujo son:

1. **Selección de perfil** (Stage 1): comparación de todos los perfiles `.dat`
   bajo condiciones idénticas y selección automática del mejor.
2. **Análisis XFOIL** (Stage 2): simulaciones para diferentes secciones de
   álabe y condiciones de vuelo representativas, usando solo el perfil
   seleccionado.
3. **Corrección de compresibilidad** (Stage 3): aplicación de corrección
   Prandtl-Glauert para Mach numbers representativos.
4. **Métricas y tablas** (Stage 4): cálculo de métricas de rendimiento y
   exportación de tablas CSV.
5. **Figuras** (Stage 5): generación de figuras de calidad para publicación.
6. **Análisis VPF** (Stage 6): análisis de Variable Pitch Fan.
7. **Análisis de cascadas** (Stage 7): análisis de teoría de cascadas.
8. **Análisis SFC** (Stage 8): análisis de impacto en consumo específico de combustible.

Todos los resultados se organizan en `results/stage_X/` correspondiente.

Cada fase tiene su propio README detallado en esta carpeta.

