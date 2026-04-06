## Stage 1 — Selección automática del perfil aerodinámico

**Objetivo**  
Comparar varios perfiles aerodinámicos bajo condiciones idénticas y seleccionar automáticamente el que presente mejor comportamiento para su uso como álabe de fan en un turbofán.

**Qué se hace**  
- Se leen todos los ficheros de perfiles (`.dat`) de la carpeta `data/airfoils/`.  
- Para cada perfil se ejecutan simulaciones XFOIL en régimen prácticamente incompresible:  
  - Número de Mach: \( M = 0{,}2 \)  
  - Número de Reynolds: \( Re = 3{,}0 \times 10^{6} \)  
  - Rango de ángulo de ataque: \( \alpha \in [-5^\circ, 20^\circ] \)  
  - Paso de ángulo de ataque: \( \Delta\alpha = 0{,}15^\circ \)  
  - Parámetro de transición: \( N_{\text{crit}} = 7{,}0 \)  
- Se calcula para cada perfil la curva completa de \( C_L(\alpha) \), \( C_D(\alpha) \) y la eficiencia \( C_L/C_D \).  
- Se determina el ángulo de pérdida (stall) como el punto donde la sustentación cae bruscamente.

**Criterios y fórmulas principales**  
- **Eficiencia aerodinámica**:  
  \[
  \eta = \frac{C_L}{C_D}
  \]
- **Puntuación del perfil** (conceptual): se combinan  
  1. Máximo \( (C_L/C_D)_{\max} \)  
  2. Ángulo de pérdida \( \alpha_{\text{stall}} \)  
  3. Arrastre medio \( \overline{C_D} \)  
  dando más peso a perfiles eficientes, con stall retrasado y baja resistencia media.

**Salidas principales**  
- Polares XFOIL de cada candidato: `results/stage_1/airfoil_selection/*_polar.txt`.  
- Nombre del perfil seleccionado: `results/stage_1/airfoil_selection/selected_airfoil.dat`.  

