## Stage 2 — Simulaciones aerodinámicas XFOIL

**Objetivo**  
Analizar en detalle el perfil seleccionado en Stage 1 para todas las condiciones de vuelo (despegue, ascenso, crucero, descenso) y secciones radiales del álabe (root, mid-span, tip), generando las polares aerodinámicas necesarias para el resto del estudio.

**Qué se hace**  
- Se toma el perfil elegido en Stage 1 (`selected_airfoil.dat`).  
- Se definen las combinaciones de **condición de vuelo** y **sección de álabe** con sus Reynolds característicos.  
- Para cada combinación se ejecuta XFOIL con:  
  - Mach: \( M = 0{,}2 \)  
  - Rango de ángulo de ataque: \( \alpha \in [-5^\circ, 23^\circ] \)  
  - Paso: \( \Delta\alpha = 0{,}15^\circ \)  
  - Valor de \( N_{\text{crit}} \) según condición (5, 6 o 7).  
- Se obtienen, para cada caso, las curvas \( C_L(\alpha) \), \( C_D(\alpha) \), \( C_M(\alpha) \) y la eficiencia \( C_L/C_D \).

**Formulación básica**  
- Número de Reynolds (ya pre‑calculado en el código, pero físicamente):  
  \[
  Re = \frac{\rho V c}{\mu}
  \]
  donde \( \rho \) es la densidad, \( V \) la velocidad característica, \( c \) la cuerda y \( \mu \) la viscosidad dinámica.
- Eficiencia aerodinámica en cada punto de la polar:  
  \[
  \eta(\alpha) = \frac{C_L(\alpha)}{C_D(\alpha)}
  \]

**Salidas principales**  
- Para cada condición × sección en `results/stage_2/final_analysis/`:  
  - `polar.csv`: \( \alpha, C_L, C_D, C_M, C_L/C_D \)  
  - `cl_alpha.csv`, `cd_alpha.csv`  
  - Gráficas `*_plot.png` (CL‑α, CD‑α, eficiencia, polar).  
- Ficheros organizados en `results/stage_2/polars/{condición}_{sección}.csv` para el postprocesado posterior.

