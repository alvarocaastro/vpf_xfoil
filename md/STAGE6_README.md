## Stage 6 — Análisis de Variable Pitch Fan (VPF)

**Objetivo**  
Estudiar cómo varía el ángulo de ataque óptimo \( \alpha_{\text{opt}} \) entre condiciones de vuelo y secciones del álabe, y cuantificar qué ajuste de pitch necesitaría un Variable Pitch Fan para mantener siempre la eficiencia máxima.

**Qué se hace**  
- Se combinan los datos aerodinámicos (polares) y las métricas de Stage 4.  
- Para cada condición y sección se toma \( \alpha_{\text{opt}} \) calculado con el **segundo pico de eficiencia** (\( \alpha \geq 3^\circ \)).  
- Se elige la condición de **crucero** como referencia.  
- Se calcula el ajuste de pitch necesario:
  \[
  \Delta\text{pitch} = \alpha_{\text{opt, condición}} - \alpha_{\text{opt, crucero}}
  \]
- Se generan curvas de eficiencia donde se marca \( \alpha_{\text{opt}} \) y gráficos de:  
  - \( \alpha_{\text{opt}} \) vs condición de vuelo.  
  - \( \Delta\text{pitch} \) vs condición.  
  - Comparación de \( \alpha_{\text{opt}} \) entre secciones (root, mid‑span, tip).

**Interpretación física**  
- \( \alpha_{\text{opt}} \) indica la incidencia aerodinámica que maximiza \( C_L/C_D \).  
- Un VPF puede girar los álabes para seguir ese ángulo óptimo en cada fase del vuelo.  
- \( \Delta\text{pitch} > 0 \): el álabe debe girarse para aumentar incidencia respecto a crucero.  
- \( \Delta\text{pitch} < 0 \): el álabe debe girarse para reducir incidencia.

**Salidas principales**  
- Tablas (`results/stage_6` / `results/stage_4/tables/`):  
  - `vpf_optimal_pitch.csv`: \( \alpha_{\text{opt}} \) por condición y sección.  
  - `vpf_pitch_adjustment.csv`: \( \Delta\text{pitch} \) relativo a crucero.  
- Figuras: `results/stage_6/figures/` con los gráficos de \( \alpha_{\text{opt}} \), \( \Delta\text{pitch} \) y eficiencia.

