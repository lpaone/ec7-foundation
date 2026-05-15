"""Esempio d'uso completo del modulo ec7.

Caso: plinto rettangolare 2.5 x 3.5 m, posa a -1.5 m, su terreno granulare
limoso (phi=32°, c'=5 kPa, gamma=19), pilastro che trasmette V=1200 kN,
H_x=150 kN (orizzontale lungo lato corto), M_y=100 kN m.
Falda assente, modulo elastico E=25 MPa.
"""

from ec7 import (
    EC7_DA2,
    NTC2018_A2,
    DesignActions,
    RectangularFooting,
    ShallowFoundation,
    Soil,
)

footing = RectangularFooting(B=2.5, L=3.5, D=1.5)
soil = Soil(
    phi_k=32,
    c_k=5,
    gamma=19,
    gamma_sat=20,
    drained=True,
    E=25_000,
    nu=0.3,
)
actions = DesignActions(V=1200, H_x=150, M_y=100)

print("\n" + "#" * 70)
print("# CONFRONTO TRA APPROCCI NORMATIVI")
print("#" * 70)

for code in (EC7_DA2(), NTC2018_A2()):
    f = ShallowFoundation(footing, soil, actions, code=code)
    report = f.verify_all(s_limit=0.025, delta_over_phi=1.0)
    print()
    print(report)
