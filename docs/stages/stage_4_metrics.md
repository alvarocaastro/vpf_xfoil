# Stage 4: Extracción de Métricas de Rendimiento Analítico

El documento actual relata la Etapa 4. Atrás quedó el terreno numérico e hiper-térmico; esta fase representa el umbral donde un chorro masivo de datos polares (`.csv` corregidos de miles de filas) se destila en hallazgos empíricos inteligibles organizados en las tablas finales de tu memoria en LaTeX.

## 1. Fundamentación de las Métricas de Operativa Estática (Turbomaquinaria)

Cuando se diseña un ala recta normal de avión, el único punto que interesa es el punto de mínimo drag en vuelo plano. Cuando se diseña un aspa rotativa de *turbofan*, el enfoque de diseño pivota hacia lidiar con el colapso del conducto masivo (inflow loss). 
El módulo extrae, para los 12 escenarios paramétricos, los siguientes vectores nodales:

### A. $C_{L,max}$ (Sustentación Máxima y Riesgo de Stall)
Localizar paramétricamente la cota donde la derivada entra en caída negativa ($\frac{\partial C_L}{\partial \alpha} < 0$). Marcar este punto es crucial para la viabilidad circuncéntrica del buje porque nos avisa, en despegues muy pronunciados y pesados, de cuándo las aspas "tosen" por separación estancada del flujo.

### B. El $E_{max}$ Táctico (La Gran Dificultad)
Un perfil de aspa suele poseer dos grandes picos de eficiencia aerodinámica ($C_L/C_D$). Uno casi en régimen negativo ($\alpha \approx -1^\circ$) y otro tardío. En rotores tridimensionales masivos, se debe descartar el primer pico porque no produce el componente primario necesario de *Lift*. Por tanto, el código incluye una función condicional determinista purificadora que prohíbe localizar eficiencia debajo de una banda inmovilista impuesta:
* `Cálculo Táctico: Alpha Limit > 3.0°`
Es decir, el programa barre recursivamente todas las iteraciones buscando maximizar eficiencia, excluyendo la falsa promesa termodinámica de álabes estancados a bajo ángulo.

## 2. Proceso de Exportación Automatizada (Lógica de Datamarts)
Todo el volumen analizado por la CPU no se vierte caóticamente. A través de la librería `pandas`, el *script* pivota los metadatos y modela DataFrames.

1. Tabula en un índice dual jerárquico el `condition` y el `section`.
2. Extensa los hiper-resultados hallados de forma transversal.
3. Lo serializa en texto legible para un compilador de macros en TeX en la ruta `results/stage_4/tables/` (`summary_table.csv`, `efficiency_matrix.csv`).

Dichos archivos en estado incoloro y denso suponen el *framework* principal del que beben indirectamente los trazadores hipergráficos (Stage 5) y los algoritmos termodinámicos evaluadores en la Cinemática post-analítica.
