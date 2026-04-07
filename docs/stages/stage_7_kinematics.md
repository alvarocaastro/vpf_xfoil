# Stage 7: Cinemática de Flujo y Paso Físico (La Justificación del Proyecto)

Este documento atiende a la médula intelectual y analítica que permite aprobar formalmente este Trabajo de Fin de Grado. Corrobora el imperativo físico tras la aplicación mecatrónica del *Variable Pitch Fan*. Se ha programado para refutar la insuficiencia del modelado puramente 2D bidimensional.

## 1. El Marco Paramétrico: Triángulos de Velocidad
Ninguna pala operando en la realidad choca frontalmente contra el viento de avance inerte. Entra en combate angular por la composición vectorial transversal. Para abordar este suceso cinemático, invocamos los radios exactos medidos empíricamente desde el centro operativo asilado en el `engine_parameters.yaml` hacia la máquina evaluadora.
Con la premisa obligatoria de un motor asilado rotando a la máxima velocidad tangencial asintótica posible (Fijado a un restrictivo **$\approx 3000\text{ RPM}$**).

A cada tramo del vector direccional ($V_{in}$) se evalúa su deflexión de entrada (Inflow Angle $\phi$):
$$ \phi = \arctan\left(\frac{V_{ax}}{\Omega \cdot r}\right) $$
Donde $V_{ax}$ cae radicalmente (e.g., mach de crucero $0.85$ choca contra un despegue a mach transitorio de $0.25$).

## 2. El Contraste Dimensional y el Derrape Físico
Al estampar estos triángulos vectoriales parametrizados hacia nuestros óptimos basales deducidos en etapas precursoras, visibilizamos en el *script* el "Derrape de Inflow". 
Cuando un turbofán frena en el horizonte longitudinal (Takeoff), el viento deja de chocar fronto-axialmente para estrellarse abruptamente a través de un plano paralelo en diagonal por culpa de las incesantes e infernales $3000 \text{ RPM}$.
La rotación efectiva para atajarlo dicta la incidencia cinemática total requerida ($\Delta\beta_{mech}$), dada por la correlación fundamental:
$$ \Delta\beta_{mech} = \Delta\alpha_{aero} + \Delta\phi $$

## 3. Síntesis e Impacto Académico Generado
El algoritmo ancla matrices numéricas completas bajo `results/stage_7/tables/kinematics_analysis.csv` revelando ajustes masivos antagónicos originados por este derrape del eje principal. 
El despegue estipula desvíos mecatrónicos forzosos en torno al orden de los **$-26^\circ$ hasta los $-32^\circ$**.  Un desajuste físico abrumador y monumental de tal índole atrofia y asesinaría el flujo laminar en toda aspa tradicional rígida al ser golpeada por el flanco estático. 

Justificaciones como la expuesta arriba en el gráfico de barras azul binario documentado automáticamente, proporcionan solidez y credibilidad frente al diseño puramente aerodinámico de la Etapa 6, cerrando la pinza termodinámica al avalar con pruebas incontrovertibles la idoneidad extrema requerida de incorporar cojinetes esféricos variables a cada turbina anfitriona en el eje moderno frontal.
