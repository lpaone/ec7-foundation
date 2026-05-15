"""Esempio realistico: plinto in zona sismica su stratigrafia con falda.

Caso tipico Italia centro-meridionale:
  - Plinto 2.5 x 3.5 x 1.5 m
  - Sabbia limosa allentata (0-2 m), sabbia densa (2-8 m), ghiaia (>8 m)
  - Falda a 3 m
  - Sito sismico: a_max/g = 0.25, kh = 0.06 (β_m=0.24 per cat. C, NTC 2018)
  - Pilastro: V = 1500 kN, M_y = 200 kN m
  - Combinazione sismica: H_x = 300 kN dovuta al sisma
"""

from ec7 import (
    NTC2018_A2,
    DesignActions,
    NTC2018_Seismic,
    NTC2018_Seismic_Reduced,
    RectangularFooting,
    SeismicAction,
    ShallowFoundation,
    Soil,
    SoilLayer,
    SoilProfile,
)

# --- Stratigrafia ---
profile = SoilProfile(
    layers=[
        SoilLayer(
            top=0,
            bottom=2.0,
            soil=Soil(
                phi_k=28, c_k=0, gamma=18, gamma_sat=19.5, E=15_000, nu=0.3, name="Sabbia limosa"
            ),
        ),
        SoilLayer(
            top=2.0,
            bottom=8.0,
            soil=Soil(
                phi_k=34, c_k=0, gamma=19, gamma_sat=20, E=30_000, nu=0.3, name="Sabbia densa"
            ),
        ),
        SoilLayer(
            top=8.0,
            bottom=30.0,
            soil=Soil(phi_k=36, c_k=0, gamma=20, gamma_sat=21, E=50_000, nu=0.3, name="Ghiaia"),
        ),
    ],
    water_depth=3.0,
)

footing = RectangularFooting(B=2.5, L=3.5, D=1.5)

# Combinazione SLU statica
actions_static = DesignActions(V=1500, M_y=200)
# Combinazione sismica
actions_seismic = DesignActions(V=1500, H_x=300, M_y=200)
seismic = SeismicAction(kh=0.06, kv=0.03)

print("\n" + "#" * 70)
print("# COMBINAZIONE SLU STATICA - NTC 2018 A2")
print("#" * 70)
f1 = ShallowFoundation(footing, profile=profile, actions=actions_static, code=NTC2018_A2())
print(f1.verify_all(s_limit=0.025))

print("\n" + "#" * 70)
print("# COMBINAZIONE SISMICA - NTC 2018 γR = 2.3 (senza fattori inerziali sul cuneo)")
print("#" * 70)
f2 = ShallowFoundation(footing, profile=profile, actions=actions_seismic, code=NTC2018_Seismic())
print(f2.verify_all(s_limit=0.025))

print("\n" + "#" * 70)
print("# COMBINAZIONE SISMICA - NTC 2018 γR = 1.8 (con Paolucci & Pecker)")
print("#" * 70)
f3 = ShallowFoundation(
    footing,
    profile=profile,
    actions=actions_seismic,
    seismic=seismic,
    code=NTC2018_Seismic_Reduced(),
)
print(f3.verify_all(s_limit=0.025))
