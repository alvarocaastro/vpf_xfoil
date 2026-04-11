"""
stage6_sfc_analysis
-------------------
Estima la reducción de consumo específico de combustible (SFC) derivada de
las mejoras aerodinámicas que permite el fan de paso variable (VPF).

Modelo:
    η_fan,new = η_base · [1 + τ · ((CL/CD)_VPF / (CL/CD)_base − 1)]
    SFC_new   = SFC_base / (1 + Δη_fan / η_base)

donde τ = profile_efficiency_transfer (factor de amortiguamiento, por defecto 0.65)
que recoge las pérdidas 3D (huelgo en punta, flujos secundarios, ondas de choque).

Era el Stage 8 en la numeración anterior.
"""
