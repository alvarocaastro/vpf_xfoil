# Síntesis Analítica y Resultados del Variable Pitch Fan

Este documento recopila la metodología matemática, los resultados numéricos de las simulaciones y las conclusiones obtenidas en el Trabajo de Fin de Grado (TFG) referentes al análisis aerodinámico de un sistema de paso variable (Variable Pitch Fan).

---

## 1. Fundamentos Científicos y Selección Aerodinámica (Stages 1 a 4)

### 1.1 Selección del Perfil: NACA 65-410
El algoritmo evaluó de forma iterativa varios perfiles aerodinámicos a un número de Reynolds base de **Re = 3.0e6**. El perfil que ofreció el mejor rendimiento global fue el **NACA 65-410**. 
* **Justificación:** Su curvatura (camber) del 4% y la geometría de su borde de ataque permiten un comportamiento adecuado en regímenes compresibles, comunes en rotores de turbofán.

### 1.2 Simulación Panel-Vórtex (XFOIL)
Las simulaciones evaluaron ángulos de ataque $\alpha \in [-5.0^\circ, 23.0^\circ]$ con incrementos de $0.15^\circ$. La eficiencia aerodinámica ($E$) se define como el cociente entre el coeficiente de sustentación ($C_L$) y el coeficiente de resistencia ($C_D$):
$$ E = \frac{C_L(\alpha)}{C_D(\alpha)} $$
Las simulaciones se dividieron en tres secciones circulares representativas del álabe:
* **Root** (Raíz): Evaluado a bajo Reynolds (1.8e6).
* **Mid Span** (Sección media): Evaluado a Reynolds medio (3.2e6 a 4.5e6).
* **Tip** (Punta): Evaluado a alto Reynolds (5.0e6 a 7.0e6).

### 1.3 Efectos Térmicos y Compresibilidad
Puesto que las simulaciones base se resolvieron a Mach 0.2 para evitar problemas de convergencia, los resultados fueron adaptados a las condiciones de vuelo reales aplicando la corrección escalar de Prandtl-Glauert para flujos subsónicos:
$$ C_{L, compresible} = \frac{C_{L, incompresible}}{\sqrt{1 - M_{flight}^2}} $$
Esto adapta los parámetros de sustentación obtenidos a las condiciones de crucero y de ascenso.

---

## 2. Análisis Cinemático (Stage 7)

El estudio preliminar (Stage 6) determinó que la optimización puramente aerodinámica requería desviaciones muy pequeñas del ángulo de ataque óptimo interpolares ($\Delta\alpha < 1.0^\circ$). Sin embargo, la incidencia real de la pala está dominada por los efectos del triángulo de velocidades.

### 2.1 Ecuaciones Roto-Dinámicas
El campo de flujo incidente sobre el rotor giratorio se caracteriza por:
1. **Velocidad Tangencial ($U$):** 
   $$U(r) = \frac{2\pi \cdot \text{RPM}}{60} \cdot r$$
2. **Velocidad Axial ($V_{ax}$):** 
   $$V_{ax} = M_{flight} \cdot \sqrt{\gamma R T} \approx M_{flight} \cdot 340 \, m/s$$
3. **Ángulo de Flujo o Inflow Angle ($\phi$):**
   $$ \phi = \arctan\left(\frac{V_{ax}}{U}\right) $$

### 2.2 Variación del Triángulo de Velocidades
Al variar el régimen de vuelo de Crucero (289 m/s) a Despegue (85 m/s) manteniendo revoluciones de 3000 RPM, el ángulo $\phi$ sufre una alteración significativa:
* En la sección `mid_span`, el ángulo de flujo incidente desciende de $42.61^\circ$ a $15.13^\circ$.
* En la sección `root`, la desviación transitoria reduce el ángulo de $61.4^\circ$ a $28.4^\circ$.

El ajuste mecánico real que requiere la raíz de la pala ($\beta$) obedece a la siguiente ecuación:
$$ \Delta\beta_{mech} = \Delta\alpha_{aero} + \Delta\phi $$

Para mantener la pala trabajando en el $C_L/C_D$ máximo hallado por XFOIL, el mecanismo debe contrarrestar esta variación temporal:

| Condición | Actuación Root ($\Delta\beta$) | Actuación Mid ($\Delta\beta$) | Actuación Tip ($\Delta\beta$) |
|:---:|:---:|:---:|:---:|
| **Takeoff** (M 0.25) | $-32.16^\circ$ | $-26.57^\circ$ | $-21.29^\circ$ |
| **Climb** (M 0.65) | $-6.13^\circ$ | $-7.79^\circ$ | $-6.39^\circ$ |
| **Descent** (M 0.75) | $-2.51^\circ$ | $-3.55^\circ$ | $-3.25^\circ$ |

Esta variación notable entre $\sim 15^\circ$ y $30^\circ$ bajo condición estática constata la inviabilidad aerodinámica en estatores Ultra-High-Bypass bajo variaciones rápidas de Mach, validando conceptualmente la implementación del sistema variable.

---

## 3. Impacto en el Consumo Específico y Propulsión (Stage 8)

Las mejoras locales bidimensionales obtenidas no se traducen uno a uno en eficiencia rotacional total. Se procedió al estudio termodinámico del consumo, estimando el $SFC$ (Specific Fuel Consumption), el cual obedece: $SFC \propto 1/\eta_{total}$.

### 3.1 Atenuación de Flujos Secundarios
Para mantener el rigor de la simulación, se implementó un factor de atenuación ($\tau_{transfer} = 0.65$) que penaliza las mejoras aerodinámicas al trasladarlas al entorno 3D, simulando pérdidas por fugas de rotor (Tip Clearance) y vórtices secundarios.
$$ \eta_{fan,new} = \eta_{fan,base} \cdot \left[ 1 + 0.65 \times \left( \frac{(C_L/C_D)_{nuevo}}{(C_L/C_D)_{base}} - 1 \right) \right] $$

### 3.2 Resultados de Reducción SFC
Aplicando este filtro de severidad en toda la envolvente, se calcularon las mejoras asociativas siguientes respecto a un ventilador fijo de referencia optimizado a crucero:

* **Crucero:** 0.00% de mejora (base).
* **Descenso:** Reducción calculada en 1.72%.
* **Ascenso (Climb):** Reducción calculada en 3.16%.
* **Despegue (Takeoff):** Picos transitorios de reducción del SFC en torno al **4.96%**.

Promedio acumulado de la envolvente global: 2.46%.

## 4. Conclusión Analítica
Este estudio numérico constata formalmente que la incorporación del mecanismo VPF evita caídas severas de eficiencia generadas por el vector de inflow en regímenes de baja velocidad subsónica. La reducción transitoria de hasta 5% de SFC promete compensaciones relevantes para ciclos comerciales.  Los estudios venideros deberán analizar las tensiones centrífugas hidráulicas del actuador en el buje central (spinbox) para garantizar que el peso añadido en gramos por el engranaje no derogue el beneficio termodinámico aquí proyectado.
