## Stage 4 — Cálculo de métricas aerodinámicas y tablas

**Objetivo**  
Condensar los resultados de las polares en un conjunto de métricas clave (eficiencia máxima, ángulo óptimo, etc.) y generar tablas resumen en formato CSV para el análisis y para la memoria.

**Qué se hace**  
- Para cada combinación condición de vuelo × sección de álabe se toma la polar \( C_L(\alpha), C_D(\alpha) \).  
- Se calcula la eficiencia en cada punto:
  \[
  \eta(\alpha) = \frac{C_L(\alpha)}{C_D(\alpha)}
  \]
- Se identifica el **segundo pico de eficiencia** (ignorando \( \alpha < 3^\circ \)):  
  - Se descarta el primer máximo local (asociado a la burbuja de separación laminar).  
  - Se busca el máximo de \( \eta(\alpha) \) para \( \alpha \geq 3^\circ \).  
- A partir de ese punto óptimo se obtienen:
  - \( (C_L/C_D)_{\max} \)  
  - \( \alpha_{\text{opt}} \)  
  - \( C_{L,\max} \) (máxima sustentación de la curva)  
  - \( C_{L,\text{opt}}, C_{D,\text{opt}} \) en el ángulo óptimo.

**Fórmulas clave**  
- Eficiencia: \( \eta = C_L / C_D \).  
- Ángulo óptimo:
  \[
  \alpha_{\text{opt}} = \arg\max_{\alpha \geq 3^\circ} \left( \frac{C_L}{C_D} \right)
  \]

**Salidas principales**  
Todas las tablas se guardan en `results/stage_4/tables/`:
- `summary_table.csv`: resumen completo.  
- `efficiency_by_condition.csv`: \( (C_L/C_D)_{\max} \) por condición y sección.  
- `alpha_opt_by_condition.csv`: \( \alpha_{\text{opt}} \) (primer pico).  
- `alpha_opt_second_peak.csv`: \( \alpha_{\text{opt}} \) usando el segundo pico (criterio turbomaquinaria).  
- `clcd_max_by_section.csv`: máxima eficiencia por sección (root, mid-span, tip).

