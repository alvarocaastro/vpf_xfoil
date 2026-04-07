# Stage 6: El Concepto "Variable Pitch Fan" Píldoro Aero-Dinámico

La Etapa 6 inaugura el verdadero bloque integrativo de análisis de la solución del TFG. Pasado el ecuador de la validación matemática individual (Stages 1 a 5), se abre paso al estudio de acoplamiento diferencial denominado: **Variable Pitch**.

## 1. La Inmovilidad del Diseño Actual (Punto de Referencia)
La industria propulsora sitúa el anclaje físico de la pala dictaminado rígidamente hacia su punto de máximo empuje estático sostenido: la fase de **Crucero** (Condición nominal basal).  
Bajo la condición de Crucero extraemos paramétricamente en el *Stage 4* nuestro $\alpha_{optimal}$ transversal a la longitud de la envergadura del estator. Para el caso puramente teórico evaluado: `Cruise Alpha Opt = ~6.25°`.

A lo largo del espectro evaluado, la pregunta capital del *Stage 6* es: ¿Cuánto se desvía el ángulo mágico de la eficiencia si variamos radicalmente las demandas aerodinámicas del conjunto?

## 2. Extracción de Lógicas Diferenciales Aerodinámicas ($\Delta\alpha_{aero}$)
Se define un tensor puramente diferencial: evaluamos el $\Delta\alpha$ absoluto requerido contra nuestro basal.
*   Por ejemplo, si la fase transicional de Elevación/Ascenso (*Climb*) localiza el nuevo pico efímero en $\alpha_{climb} = 5.95^\circ$, el requerimiento aerodinámico puro local reportaría un ajuste transigente de: 
$\Delta\alpha = (5.95) - (6.25) = -0.30^\circ$.

En estricta lógica teórica, un alabe rígido que fuera forzado a este régimen sólo sufriría una desviación infima y despreciable de 0.3 grados, mitigando aparentemente la extrema pesadez e hiper-complejidad hidráulica necesaria para insertar ejes dinámicos al ensamble central de la espina del motor.
El *Stage 6* consolida formalmente todos estos $\Delta\alpha_{aero}$ menores demostrando su poca rentabilidad productiva aislada en Tablas exportables hacia la carpeta operativa `results/stage_6/`.

Estos resultados engañosamente optimistas (pues obvian el vector derivativo cruzado en tres dimensiones) serán ferozmente desacreditados, alterados y revertidos en peso físico durante el módulo de la Etapa 7 (Cinemática Tri-dimensional del Viento).
