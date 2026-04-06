## Stage 3 — Corrección de compresibilidad (Prandtl–Glauert)

**Objetivo**  
Corregir los resultados incompresibles de XFOIL (Mach 0,2) para aproximarlos a los números de Mach reales de operación del fan, utilizando el modelo clásico de Prandtl–Glauert.

**Qué se hace**  
- Se parte de las polares de Stage 2.  
- Para cada condición de vuelo se fija un Mach objetivo:  
  - Despegue: \( M = 0{,}30 \)  
  - Ascenso: \( M = 0{,}70 \)  
  - Crucero: \( M = 0{,}85 \)  
  - Descenso: \( M = 0{,}75 \)  
- Se aplica la corrección de Prandtl–Glauert al coeficiente de sustentación:  
  - Se calcula el factor
    \[
    \beta = \sqrt{1 - M^2}
    \]
  - Se corrige la sustentación:
    \[
    C_{L,\text{corr}} = \frac{C_{L,\text{inc}}}{\beta}
    \]
- El coeficiente de resistencia \( C_D \) se mantiene sin corregir (criterio conservador).

**Notas físicas**  
- El modelo es válido para flujo subsónico \( M \lesssim 0{,}8 \).  
- A medida que \( M \) aumenta, \( \beta \) disminuye y la sustentación corregida crece.  
- No se modelan efectos transónicos (ondas de choque, separación asociada, etc.).

**Salidas principales**  
- Para cada condición × sección en `results/stage_3/`:  
  - `corrected_polar.csv`: polar corregida.  
  - `corrected_cl_alpha.csv`: \( C_{L,\text{corr}}(\alpha) \).  
  - `corrected_efficiency.csv`: \( (C_L/C_D)_{\text{corr}}(\alpha) \).  
  - `corrected_plots.png`: comparativa original vs corregido.

