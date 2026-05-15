"""Test del modulo ec7.

Test rapidi: includono valori di riferimento per terreno granulare
classico (phi=30°, c=0) confrontati con i fattori di Vesic noti dalla letteratura.
"""

import math

import pytest

from ec7 import (
    EC7_DA1_C1,
    EC7_DA2,
    EC7_DA3,
    NTC2018_A2,
    CircularFooting,
    DesignActions,
    RectangularFooting,
    ShallowFoundation,
    Soil,
    StripFooting,
)
from ec7.bearing import _bearing_capacity_coefficients, compute_bearing_capacity

# ---------------------------------------------------------------------------
# 1) Fattori N di Vesic - confronto con valori tabellari da letteratura
# ---------------------------------------------------------------------------


def test_N_factors_phi_30():
    """phi=30° -> Nq=18.40, Nc=30.14, Ngamma=22.40 (Vesic)."""
    Nc, Nq, Ngamma = _bearing_capacity_coefficients(math.radians(30))
    assert Nq == pytest.approx(18.40, rel=0.01)
    assert Nc == pytest.approx(30.14, rel=0.01)
    assert Ngamma == pytest.approx(22.40, rel=0.02)


def test_N_factors_phi_0():
    """Caso limite phi=0: Nc=5.14, Nq=1, Ngamma=0."""
    Nc, Nq, Ngamma = _bearing_capacity_coefficients(0.0)
    assert Nc == pytest.approx(5.14, rel=0.01)
    assert Nq == pytest.approx(1.0)
    assert Ngamma == 0.0


def test_N_factors_phi_35():
    """phi=35° -> Nq=33.30, Nc=46.12, Ngamma=48.03 (Vesic)."""
    Nc, Nq, Ngamma = _bearing_capacity_coefficients(math.radians(35))
    assert Nq == pytest.approx(33.30, rel=0.01)
    assert Nc == pytest.approx(46.12, rel=0.01)
    assert Ngamma == pytest.approx(48.03, rel=0.02)


# ---------------------------------------------------------------------------
# 2) Caso "scolastico" centrato verticale - confronto con Terzaghi semplificato
# ---------------------------------------------------------------------------


def test_strip_centered_drained():
    """Plinto nastriforme 2 m, D=1 m, terreno phi=30°, c=0, gamma=18.
    Stima ordine di grandezza q_ult ≈ 0.5*18*2*22.4 + 18*1*18.4 ≈ 734 kPa.
    """
    footing = StripFooting(B=2.0, D=1.0)
    soil = Soil(phi_k=30, c_k=0, gamma=18, gamma_sat=20, drained=True)
    actions = DesignActions(V=200)  # piccola carico, solo per geometria

    from ec7.bearing import compute_bearing_capacity

    # parametri caratteristici, fattori parziali = 1 -> q_ult atteso ~ 734 kPa
    comp = compute_bearing_capacity(footing, soil, actions)
    # nastro -> sq, sgamma = 1
    assert comp.factors.sq == pytest.approx(1.0, abs=0.01)
    # q_ult ordine di grandezza
    expected = 0.5 * 18 * 2 * 22.4 + 18 * 1 * 18.4
    assert comp.q_ult == pytest.approx(expected, rel=0.05)


# ---------------------------------------------------------------------------
# 3) Eccentricità: area efficace ridotta correttamente
# ---------------------------------------------------------------------------


def test_eccentricity_meyerhof():
    f = RectangularFooting(B=2.0, L=3.0, D=1.0)
    # V=1000 kN, M_y=200 kN m -> e_B = 0.2 m
    actions = DesignActions(V=1000, M_y=200)
    e_B, e_L = actions.eccentricities()
    assert e_B == pytest.approx(0.2)
    assert e_L == pytest.approx(0.0)
    eff = f.effective_geometry(e_B, e_L)
    assert eff.B_eff == pytest.approx(2.0 - 0.4)
    assert eff.L_eff == pytest.approx(3.0)
    assert eff.A_eff == pytest.approx(1.6 * 3.0)


def test_eccentricity_out_of_core():
    f = RectangularFooting(B=2.0, L=3.0, D=1.0)
    with pytest.raises(ValueError):
        f.effective_geometry(e_B=1.5, e_L=0)


# ---------------------------------------------------------------------------
# 4) Differenze tra approcci: DA2 deve essere più gravoso di DA1-C1 sul lato R
# ---------------------------------------------------------------------------


def test_codes_relative_severity():
    footing = RectangularFooting(B=2.0, L=3.0, D=1.5)
    soil = Soil(phi_k=32, c_k=5, gamma=19, gamma_sat=20, drained=True)
    actions = DesignActions(V=1200, H_x=80, M_y=50)

    r_da1c1 = ShallowFoundation(footing, soil, actions, EC7_DA1_C1()).check_bearing()
    r_da2 = ShallowFoundation(footing, soil, actions, EC7_DA2()).check_bearing()
    r_da3 = ShallowFoundation(footing, soil, actions, EC7_DA3()).check_bearing()
    r_ntc2 = ShallowFoundation(footing, soil, actions, NTC2018_A2()).check_bearing()

    # DA2 ha gamma_Rv=1.4 vs DA1-C1 = 1.0 -> R_d minore
    assert r_da2.R_d < r_da1c1.R_d
    # NTC A2 con gamma_R=2.3 è il più gravoso sul lato resistenza
    assert r_ntc2.R_d < r_da2.R_d
    # DA3 ha M2 (riduce phi) ma R3=1.0
    assert r_da3.R_d < r_da1c1.R_d


# ---------------------------------------------------------------------------
# 5) Verifica non drenata
# ---------------------------------------------------------------------------


def test_undrained_bearing():
    footing = RectangularFooting(B=2.0, L=2.0, D=1.0)
    soil = Soil(phi_k=0, c_k=0, cu_k=80, gamma=18, gamma_sat=20, drained=False)
    actions = DesignActions(V=500)
    comp = compute_bearing_capacity(footing, soil, actions)
    # q_ult ≈ (π+2)*cu*sc + q = 5.14 * 80 * (1+0.2) + 18 = 493 + 18
    expected = (math.pi + 2) * 80 * (1 + 0.2 * 1.0) + 18 * 1.0
    assert comp.q_ult == pytest.approx(expected, rel=0.02)


# ---------------------------------------------------------------------------
# 6) Test integrazione: report completo
# ---------------------------------------------------------------------------


def test_full_report():
    footing = RectangularFooting(B=2.5, L=3.5, D=1.5)
    soil = Soil(phi_k=32, c_k=5, gamma=19, gamma_sat=20, drained=True, E=25_000, nu=0.3)
    actions = DesignActions(V=1200, H_x=150, M_y=100)
    f = ShallowFoundation(footing, soil, actions, code=NTC2018_A2())
    report = f.verify_all(s_limit=0.025)
    # tutti i risultati presenti
    assert report.bearing is not None
    assert report.sliding is not None
    assert report.overturning is not None
    assert report.settlement is not None
    # check coerenza
    assert report.bearing.R_d > 0
    assert report.bearing.q_ult > 0
    # il report deve essere stringificabile
    s = str(report)
    assert "NTC 2018" in s
    assert "Capacità portante" in s


# ---------------------------------------------------------------------------
# 7) Fondazione circolare
# ---------------------------------------------------------------------------


def test_circular_footing():
    footing = CircularFooting(R=1.5, D=1.0)
    soil = Soil(phi_k=30, c_k=0, gamma=18, gamma_sat=20, drained=True, E=20000)
    actions = DesignActions(V=800, M_y=100)
    f = ShallowFoundation(footing, soil, actions, code=EC7_DA2())
    bearing = f.check_bearing()
    assert bearing.R_d > 0
    assert bearing.A_eff < footing.area  # eccentricità riduce area


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
