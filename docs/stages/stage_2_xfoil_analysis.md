# Stage 2: Ejecución de Simulaciones con Perfil Seleccionado

Este documento profundiza en la Etapa 2 del proyecto, donde se somete al perfil vencedor del "Stage 1" a la matriz completa de operaciones del motor, calculando el espectro aerodinámico total a bajas velocidades incompresibles.

## 1. El Objetivo del Análisis Bidimensional de Alta Frecuencia
Tener un perfil ganador es inútil sin definir su espectro paramétrico sobre toda la pala (desde su base lenta hasta su punta hiperveloz). La Etapa 2 emplea la topología de la nave para calcular doce envolventes diferentes: tres secciones de aspa bajo cuatro regímenes operacionales de aviónética.

## 2. Marco Paramétrico

El simulador se apoya en el archivo maestro de constantes `analysis_config.yaml`. Las condiciones impuestas emulan las de un motor turbofan comercial estandarizado (Ej: CFM56 o LEAP-1A).

### 2.1 Condiciones de Vuelo Analizadas
1. **Takeoff (Despegue):** Alta inestabilidad, gran flujo cruzado.
2. **Climb (Ascenso):** Mayor densidad de potencia sostenida.
3. **Cruise (Crucero):** Máxima economía exigida a altitud sostenida, siendo la base del diseño geométrico clásico.
4. **Descent (Descenso/Aproximación):** Potencia en ralentí para planeo controlado, flujos incidentes alterados.

### 2.2 Segmentación del Álabe y Efectos Viscosos (Reynolds)
Dado que un aspa gira mucho más rápido por la punta que en la raíz, los efectos viscosos de la capa límite (gobernados por el número de Reynolds) varían drásticamente a lo largo de un mismo hilo radial:
* **Root (Raíz):** $Re = 1.8 \times 10^6$ (Flujo espeso, capa límite inestable muy sensible al gradiente adverso).
* **Mid Span:** $Re = \sim 3.2 \times 10^6$ (Flujo transicional aerodinámicamente maduro).
* **Tip (Punta):** $Re = \sim 5.0 - 7.0 \times 10^6$ (Flujo supersónico viscoso de escasa turbulencia por cizalladura inercial).

## 3. Flujo Computacional Subyacente
El orquestador enruta iterativamente **12 hilos** hacia el motor de XFOIL. Debido a que el solucionador visco-inviscid de XFOIL no lidia termodinámicamente con las ondas de choque, el bucle en esta etapa **fuerza el número de Mach a un constante de cálculo incompresible ($M \approx 0.2$)**, garantizando la estabilización de los determinantes de las matrices del kernel.

### Robustez Implementada
Para los ángulos superes del barrido (donde $\alpha > 15^\circ$), la capa de contorno de Karman-Tsien en el extradós frecuentemente revienta en la malla virtual. El script está provisto de heurísticas en Python para bajar el iterador escalar, refinar los nodos (*panelear o "ppar"*) e iterar iteraciones de Newton extendidas para exprimir la matemática de post-pérdida hasta forzar al solver a converger los desprendimientos violentos.

## 4. Estructura de Resultados
Los resultados se encapsulan directamente en `results/stage_2/<flight_condition>/<section>/`.  
Allí residen las polar gráficas en crudo con datos de empuje, contorno interactivo, resistencia de fricción de contorno y resistencia pura de gradiente de presiones, sentando las matrices base para la posterior asimilación de la teoría Mach transónica en la Etapa 3.
