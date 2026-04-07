# Stage 5: Generación de Entornos Gráficos Académicos

Este documento establece la metodología gráfica aplicada en la Etapa 5. Una vez las métricas han sido decodificadas y depuradas en los DataFrames del `Stage 4`, el proyecto exige su exportación visual masiva hacia resoluciones cualificadas para su superposición en entornos de presentación y edición LaTeX (300 DPI, control *rcParams* de fuentes Serif estandarizadas).

## 1. Filtrado Científico de Salidas

Originalmente, los algoritmos numéricos de iteración arrojan polares ineficientes repletas de ruido de cálculo post-pérdida. Exhibir dichos barridos mancharía el documento base del TFG. 
Para mitigarlo, el generador localiza el módulo estético (`figure_generator.py`) acotando tres espectros cardinales:

1. **Eficiencia Base (E vs Alpha):** Gráfico principal que dicta la validación aerodinámica. Mágica correlativa visual donde el pico del segundo escalón marca el "Optimal Point" y la cota `X` delimita la franja operativa sin sobreescribir leyendas repetitivas que ensucian la legibilidad de la grilla principal.
2. **Distribución Comparativa por Condición:** Contraste cruzado evaluativo donde las tres curvas (Takeoff, Climb, Cruise) se intersecan, demostrando de forma ilustrativa cómo el mach altera paramétricamente la pendiente global.

## 2. Unificación Visual

Un TFG de alto nivel exige la misma paleta y coherencia en cada figura, para que su inclusión en la memoria parezca orquestada bajo el paraguas unificado. En este sentido, la Etapa 5 inyecta el `rcParams`:

*   Se restringen y censuran los "Spines" top y right de todos los ploteos; desnudando el lienzo a su versión limpia científica.
*   Se unifica obligatoriamente la locación de las Cajas de Leyenda a `lower right`, marginando el contenido al fondo para no disturbar bajo ninguna circunstancia las puntas de los escalones termodinámicos vitales en el `upper center`.
*   Carga de diccionario unificado general `SECTION_COLORS` (Raíz=Azul Mar, Medio=Tierra Claro, Punta=Aire Ligero), de modo que toda la tesis es unificada y rastreable visualmente sin leer las leyendas.

Los outputs matriculados terminan limpios y segmentados por régimen en la carpeta raíz `results/stage_5/`.
