## Stage 7 — Análisis de impacto en consumo específico de combustible (SFC)

**Objetivo**  
Estimar cómo las mejoras aerodinámicas debidas al VPF (aumento de \( C_L/C_D \)) podrían traducirse en una reducción del consumo específico de combustible (SFC) de un turbofán representativo.

**Qué se hace**  
- Se parte de los resultados de eficiencia máxima de Stage 4 y de los óptimos VPF de Stage 6.  
- Se leen parámetros de motor baseline desde `config/engine_parameters.yaml`:
  - SFC de referencia en crucero \( \text{SFC}_{\text{baseline}} \).  
  - Eficiencia de fan baseline \( \eta_{\text{fan,baseline}} \).  
  - Bypass ratio, velocidades de referencia, etc.  
- Para cada condición de vuelo se calcula la mejora relativa de eficiencia aerodinámica:
  \[
  \text{gain}_{\text{aero}} = \frac{(C_L/C_D)_{\text{VPF}} - (C_L/C_D)_{\text{baseline}}}{(C_L/C_D)_{\text{baseline}}}
  \]
- Se estima la nueva eficiencia de fan:
  \[
  \eta_{\text{fan,new}} = \eta_{\text{fan,baseline}} \times \frac{(C_L/C_D)_{\text{VPF}}}{(C_L/C_D)_{\text{baseline}}}
  \]
- Y la nueva SFC:
  \[
  \text{SFC}_{\text{new}} = \frac{\text{SFC}_{\text{baseline}}}{1 + \text{gain}_{\text{aero}}}
  \]
- Finalmente se calcula la reducción porcentual:
  \[
  \Delta \text{SFC}[\%] = \frac{\text{SFC}_{\text{baseline}} - \text{SFC}_{\text{new}}}{\text{SFC}_{\text{baseline}}} \times 100
  \]
- Se generan gráficos SFC vs condición, reducción porcentual y mejora de eficiencia de fan.

**Limitaciones**  
- El modelo es intencionadamente simplificado: asume una relación proporcional entre eficiencia aerodinámica de fan y SFC global.  
- No sustituye a un cálculo termodinámico completo, pero da una **estimación de orden de magnitud** del beneficio potencial del VPF.

**Salidas principales**  
- Tabla `results/stage_4/tables/sfc_analysis.csv` con SFC baseline, SFC nueva y reducción por condición.  
- Figuras en `results/stage_7/figures/`:  
  - `sfc_vs_condition.png`, `sfc_reduction_percent.png`, `fan_efficiency_improvement.png`, `efficiency_vs_sfc.png`.  
- Resumen textual: `results/stage_7/sfc_analysis_summary.txt`.

