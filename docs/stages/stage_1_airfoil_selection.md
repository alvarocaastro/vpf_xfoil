# Stage 1: Selección Automática de Perfil Óptimo

Este documento detalla la metodología y ejecución de la Etapa 1 del análisis aerodinámico. Constituye la fase de inicialización, donde el algoritmo procesa un banco de geometrías para determinar cuál es el perfil alar idóneo para el rotor del turbofán con paso variable.

## 1. Objetivo del Módulo

Seleccionar de forma empírica y justificada el perfil aerodinámico que ofrezca las mejores prestaciones para un álabe de fan de ultraelevada dilución (*Ultra-High-Bypass*), evitando una elección manual sujeta a sesgos. El criterio de mérito maximiza simultáneamente la eficiencia aerodinámica en punto de diseño, el margen frente al desprendimiento de capa límite y la resistencia media en fuera-de-diseño.

## 2. Perfiles Candidatos

Los cuatro perfiles evaluados están en `data/airfoils/`:

| Perfil         | Familia    | Curvatura | Espesor | Justificación |
|:---------------|:-----------|:---------:|:-------:|:--------------|
| NACA 65-210    | NACA 65    | 2 %       | 10 %    | Referencia CDA (*Controlled-Diffusion Airfoil*) de baja curvatura; base de comparación estándar en la literatura (Saravanamuttoo, Farokhi). |
| **NACA 65-410**| **NACA 65**| **4 %**   | **10 %**| **Perfil seleccionado.** Curvatura moderada que combina alta eficiencia a Mach compresible incipiente con buen margen de pérdida en regímenes transitorios. |
| NACA 63-215    | NACA 63    | 2 %       | 15 %    | Sección laminar de menor resistencia de presión; referencia de comparación para cuantificar el beneficio de la serie 65. |
| NACA 0012      | NACA 00    | 0 %       | 12 %    | Perfil simétrico sin curvatura; establece la línea base de cero-curvatura para evaluar el efecto del *camber*. |

## 3. Condición de Evaluación

Todos los perfiles se simulan bajo una condición común en XFOIL:

| Parámetro | Valor | Fuente |
|:----------|:-----:|:-------|
| Reynolds de referencia $Re$ | $3{,}0 \times 10^6$ | `config/analysis_config.yaml → selection.reynolds` |
| Mach de cálculo $M_{ref}$ | 0,20 | Incompresible; corrección Prandtl-Glauert aplicada en Stage 3 |
| Criterio de amplificación $N_{crit}$ | 7,0 | `config/analysis_config.yaml → selection.ncrit`; representa entorno de túnel industrial / entrada de fan |
| Rango de ángulo de ataque $\alpha$ | $[-5{,}0°,\; 20{,}0°]$, paso $0{,}15°$ | `config/analysis_config.yaml → selection_alpha` |

> **Nota:** El rango de barrido en la selección $[-5°, 20°]$ es más conservador que el rango de las simulaciones finales $[-5°, 23°]$ (`alpha`). Esto evita que la convergencia de XFOIL en ángulos muy elevados distorsione la puntuación comparativa entre candidatos.

## 4. Criterio de Puntuación Multicriterio

La evaluación de mérito no se basa en una única métrica. El módulo `scoring.score_airfoil()` calcula una puntuación compuesta $S$ ponderada:

$$
S = w_1 \cdot \left(\frac{C_L}{C_D}\right)_{\max} + w_2 \cdot \alpha_{\text{stall}} - w_3 \cdot \bar{C}_D
$$

donde los pesos están calibrados para que cada término contribuya rangos dinámicos comparables para perfiles NACA de la serie 65:

| Término | Peso | Rango típico | Contribución a $S$ |
|:--------|:----:|:------------:|:------------------:|
| $(C_L/C_D)_{\max}$ | $w_1 = 1{,}0$ | 60 – 120 | 60 – 120 |
| $\alpha_{\text{stall}}$ [°] | $w_2 = 5{,}0$ | 12° – 22° | 60 – 110 |
| $\bar{C}_D$ | $w_3 = 5000$ | 0,006 – 0,015 | 30 – 75 (penalización) |

### 4.1 Definición de $\alpha_{\text{stall}}$

$\alpha_{\text{stall}}$ se define como el **ángulo de ataque en el que $C_L$ alcanza su máximo absoluto**. Este es el ángulo en el que comienza el desprendimiento de capa límite y marca la frontera operativa del álabe. No debe confundirse con el ángulo en el que se maximiza $C_L/C_D$, que ocurre a ángulos sensiblemente menores.

Un mayor $\alpha_{\text{stall}}$ es especialmente valioso en aplicaciones VPF porque el triángulo de velocidades puede inducir desviaciones de incidencia de hasta $\Delta\phi \sim 30°$ entre crucero y despegue (véase Stage 7).

### 4.2 Interpretación de la Ponderación

- **$(C_L/C_D)_{\max}$:** primer criterio de mérito, directamente proporcional al rendimiento en punto de diseño y, por tanto, al SFC en crucero.
- **$\alpha_{\text{stall}}$:** segundo criterio; cuantifica el margen de operación segura fuera de diseño. Crítico en turbofanes UHBR, donde la gran variación del ángulo de flujo en bajas velocidades exige que el perfil soporte incidencias elevadas sin desprender.
- **$\bar{C}_D$:** tercer criterio (penalización); captura el coste aerodinámico promedio en toda la polar, más allá del punto óptimo.

## 5. Implementación

El orquestador `run_analysis.py → step_2_airfoil_selection()` instancia un `AirfoilSelectionService` que:

1. Lee los cuatro archivos `.dat` desde `data/airfoils/`.
2. Lanza XFOIL para cada perfil con la condición de selección descrita en §3.
3. Parsea la polar de salida y computa `score_airfoil(df)`.
4. Selecciona el perfil con mayor $S$.
5. Escribe el nombre del ganador en `results/stage_1/airfoil_selection/selected_airfoil.dat`.

Si XFOIL no converge para un perfil (e.g., geometría mal mallada), ese candidato se descarta automáticamente, preservando la integridad del pipeline.

## 6. Resultado

En la configuración actual, el perfil ganador es el **NACA 65-410**:

- Su curvatura del 4 % genera mayor $C_L$ a incidencias moderadas sin incrementar significativamente $C_D$.
- La geometría CDA retrasa el desprendimiento hasta ángulos más altos que la serie 63, favoreciendo el margen de pérdida.
- Su $(C_L/C_D)_{\max}$ supera al NACA 0012 y al 65-210 en el rango de Reynolds de fan ($Re \sim 10^6$–$10^7$).

Las polares comparativas de todos los candidatos quedan archivadas en `results/stage_1/airfoil_selection/` para trazabilidad.
