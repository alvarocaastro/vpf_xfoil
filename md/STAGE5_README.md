## Stage 5 — Figuras de calidad para publicación

**Objetivo**  
Generar todas las figuras necesarias para la tesis a partir de las polares y las métricas calculadas: curvas \( C_L \), \( C_D \), eficiencia \( C_L/C_D \), polares \( C_L\text{–}C_D \) y gráficos resumen.

**Qué se hace**  
- A partir de `results/stage_2/polars/` y de las métricas de Stage 4 se generan:  
  - Para cada condición × sección:  
    - \( C_L(\alpha) \)  
    - \( C_D(\alpha) \)  
    - \( (C_L/C_D)(\alpha) \) marcando \( \alpha_{\text{opt}} \) (segundo pico)  
    - Polar \( C_L \) frente a \( C_D \).  
  - Gráficos resumen:  
    - \( \alpha_{\text{opt}} \) vs condición de vuelo.  
    - \( (C_L/C_D)_{\max} \) vs \( Re \).  
    - Comparación de eficiencia por sección de álabe.

**Especificaciones de las figuras**  
- Resolución: 300 dpi.  
- Formato: PNG.  
- Tamaño: \( 6{,}0 \times 4{,}5 \) pulgadas.  
- Ejes con unidades y leyenda clara.  
- Cuadrícula activada para facilitar la lectura.

**Relación con fórmulas**  
- Todas las curvas se basan en las relaciones ya usadas:  
  - Eficiencia: \( \eta = C_L / C_D \).  
  - Óptimo: \( \alpha_{\text{opt}} = \arg\max_{\alpha \geq 3^\circ} (C_L/C_D) \).  
- Los gráficos resumen muestran cómo cambian estas magnitudes con \( Re \) y con la condición de vuelo.

**Salidas principales**  
- Todas las figuras se guardan en `results/stage_5/figures/` listas para incluir en LaTeX mediante `\includegraphics`.

