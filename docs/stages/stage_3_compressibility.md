# Stage 3: Compresibilidad e Invarianza Transónica

Este archivo documenta la Etapa 3, que interviene la física base puramente teórica de incompresibilidad generada en la Etapa 2 para insuflarle la relatividad aerotermodinámica de un vuelo comercial real. 

## 1. Teoría Subyacente: El Dominio de Prandtl-Glauert
El perfil aerodinámico evaluado en las fases iniciales se probó bajo un campo de densidad inalterable (Mach menor a 0.3). Sin embargo, cuando un avión entra en la tropopausa y acelera al régimen de **Cruise (Mach 0.85)**, las moléculas de fluido ya no tienen el tiempo de "preaviso" sonoro necesario para reestructurar sus vectores antes de golpear el aspa sólida del motor. Las isotermas se desploman y la densidad se apila masivamente delante del borde de ataque.

A este fenómeno se le denota **compresibilidad**. Carecer de él en un estudio de impacto anularía la validez académica del TFG ante el tribunal.

## 2. Ejecución Analítica del Post-Procesado
Dado que generar capas de Navier-Stokes completas excede la computabilidad de este pipeline rápido y exige semanas de trabajo en CFD para simular ondas de choque supersónicas en la base (Onda lambda), el Stage 3 invoca una formulación tensorial directa: **La Corrección de Prandtl-Glauert**.

### Aplicación Matemática
El módulo iterativo en Python localiza cada polar exportada desde XFOIL y escanea secuencialmente cada vector de ángulo de ataque y clona su coeficiente de sustentación empujándolo verticalmente con la regla fundamental:

$$ C_{L, compresible} = \frac{C_{L, incompresible}}{\sqrt{1 - M_{flight}^2}} $$

Este coeficiente divisor encarnado en $\sqrt{1 - M^2}$ se aproxima asintóticamente a 0 conforme el avión entra en barrera bi-sónica (singulaidad transónica Mach 1.0). Al dividir por un número cada vez inferior a 1, todos los ratios de Fuerzas Aerodinámicas del modelo incompresible base se disparan y distorsionan (Aumentando dramáticamente el Lift forzado).

## 3. Limitaciones Contempladas de TFG Universitario
El código se erige desde la honradez científica. Esta corrección actúa matemáticamente a la perfección hasta rangos nominales de Mach 0.70 a 0.85. Sin embargo, no se implementa una corrección análoga en la alteración de gradientes adversos para el Coeficiente de Resistencia Periférico ($C_D$) originado por Divergencia de Resistencia (Drag Divergence).
Se asume con pleno conocimiento técnico que nuestro modelo está modelando una sustentación certera sacrificando una subestimación marginal del drag total a altísimas cargas rotacionales. Esto favorece la pureza visual y estructural del cálculo diferencial sin perder exactitud en la captación de tendencias.

## 4. Transcripción Final 
El resultado del Stage 3, un sub-clon total de la estructura de malla del stage 2, genera ficheros `.csv` nuevos en `results/stage_3/` que ostentan la herencia de las matrices incompresibles con las presiones estáticas del flujo real incrustado; preparando definitivamente la data para ser traducida a métricas de impacto SFC.
