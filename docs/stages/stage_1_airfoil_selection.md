# Stage 1: Selección Automática de Perfil Óptimo

Este documento detalla la metodología y ejecución de la Etapa 1 del análisis aerodinámico del proyecto. Constituye la fase de inicialización, donde el algoritmo procesa un banco de datos geométrico para dictaminar cuál es el perfil alar idóneo para el estator y rotor del turbofán.

## 1. Objetivo del Módulo
Seleccionar de forma empírica y justificada el perfil aerodinámico que ofrezca las mejores prestaciones termodinámicas iniciales, evitando una elección manual sujeta a sesgos por parte del alumno. El entorno se asegura de maximizar el rango operativo para retrasar la pérdida (*stall*) en las complejas condiciones transitorias de un motor comercial.

## 2. Metodología de Selección

El algoritmo (`run_airfoil_selection.main()`) acude al directorio `data/airfoils/`, el cual contiene múltiples geometrías matriculadas (archivos `.dat`). Se configura a un número de Reynolds base representativo de la sección media de baja velocidad:
* **Reynolds de evaluación ($Re$):** $3.0 \times 10^6$
* **Criterio de Amplificación (N_crit):** 7.0 (Simulando un entorno turbulento típico de túnel de viento industrial o entrada al fan).

### 2.1 Criterios Numéricos (Scoring)
La evaluación de mérito de cada perfil no se basa en una métrica unidimensional. El algoritmo computa una media ponderada que incluye:
1. **Eficiencia Máxima ($C_L/C_D$ máximo):** Ponderación más alta. Garantiza economía de combustible (menor SFC).
2. **Resistencia Pura Promedio ($C_D$ media):** Para los regímenes donde el aspa vuela fuera de su óptimo.
3. **Ángulo de Pérdida Transitorio (Stall Angle $\alpha_{stall}$):** Vital para las grandes alteraciones de vector en flujo cruzado. Cuanto más retrase el perfil la de-laminación, más puntuación recibe.

## 3. Implementación Práctica
El script orquesta múltiples instancias en paralelo de `xfoil_runner.py` utilizando la técnica de paneles. Este proceso envía secuencias de comandos invisibles al kernel de XFOIL.

Si XFOIL converge para el rango de ángulos solicitado ($\alpha = [-5^\circ, 23^\circ]$), se extraen sus polares en archivos vectoriales de comportamiento. En caso de divergencia inestable provocada por geometrías mal malladas, el perfil se descarta del análisis automáticamente protegiendo la integridad del simulador final.

## 4. Resultados Extraídos
Al concluir el barrido de base de datos, el perfil victorioso se aisla físicamente:
* El archivo físico ganador se clona bajo el nombre `selected_airfoil.dat` en la carpeta `results/stage_1/`.
* Se extrae un `.txt` tabulado resumiendo la curva comparativa respecto a los perfiles derrotados.

En la actual configuración, el modelo **NACA 65-410** resulta elegido por su resistencia endémica al desprendimiento gracias al control estricto que ofrecen los *Controlled Diffusion Airfoils* (CDA) bajo Mach compresible temprano.
