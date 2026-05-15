"""Test per profilo stratigrafico, falda e sismica."""

import math

import pytest

from ec7 import (
    EC7_DA2,
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

# ===========================================================================
# 1) SoilProfile - calcolo delle pressioni di sovraccarico
# ===========================================================================


def test_overburden_homogeneous_no_water():
    """Profilo omogeneo senza falda: sigma_v = gamma * z."""
    profile = SoilProfile(
        layers=[
            SoilLayer(top=0, bottom=10, soil=Soil(phi_k=30, c_k=0, gamma=18, gamma_sat=20)),
        ]
    )
    assert profile.total_overburden_at(5.0) == pytest.approx(18 * 5)
    assert profile.effective_overburden_at(5.0) == pytest.approx(18 * 5)


def test_overburden_with_water():
    """Profilo con falda a 2 m: sopra usa gamma, sotto usa gamma_sat.
    Sigma efficace = sigma totale - u."""
    profile = SoilProfile(
        layers=[SoilLayer(top=0, bottom=10, soil=Soil(phi_k=30, c_k=0, gamma=18, gamma_sat=20))],
        water_depth=2.0,
    )
    # sigma totale a z=5: 18*2 + 20*3 = 96
    assert profile.total_overburden_at(5.0) == pytest.approx(96.0)
    # u a z=5: 9.81 * (5-2) = 29.43
    # sigma' = 96 - 29.43 = 66.57
    assert profile.effective_overburden_at(5.0) == pytest.approx(66.57, rel=0.01)


def test_overburden_layered():
    """Profilo a 3 strati senza falda."""
    profile = SoilProfile(
        layers=[
            SoilLayer(top=0, bottom=2, soil=Soil(phi_k=28, c_k=0, gamma=17, gamma_sat=19)),
            SoilLayer(top=2, bottom=5, soil=Soil(phi_k=32, c_k=0, gamma=19, gamma_sat=20)),
            SoilLayer(top=5, bottom=20, soil=Soil(phi_k=35, c_k=0, gamma=20, gamma_sat=21)),
        ]
    )
    # sigma a z=4: 17*2 + 19*2 = 72
    assert profile.total_overburden_at(4.0) == pytest.approx(72.0)
    # sigma a z=8: 17*2 + 19*3 + 20*3 = 151
    assert profile.total_overburden_at(8.0) == pytest.approx(151.0)


def test_overburden_water_between_layers():
    """Falda al confine tra strati."""
    profile = SoilProfile(
        layers=[
            SoilLayer(top=0, bottom=2, soil=Soil(phi_k=28, c_k=0, gamma=17, gamma_sat=19)),
            SoilLayer(top=2, bottom=10, soil=Soil(phi_k=32, c_k=0, gamma=19, gamma_sat=20)),
        ],
        water_depth=2.0,
    )
    # a z=5: 17*2 (sopra falda) + 20*3 (sotto, saturo) = 94
    assert profile.total_overburden_at(5.0) == pytest.approx(94.0)
    # sigma' = 94 - 9.81*3 = 64.57
    assert profile.effective_overburden_at(5.0) == pytest.approx(64.57, rel=0.01)


# ===========================================================================
# 2) Soil equivalente nel volume di influenza
# ===========================================================================


def test_equivalent_soil_layered():
    """Profilo a 2 strati, fondazione a D=1, B=2 -> media nei 2 m sotto la base
    che attraversano entrambi gli strati."""
    profile = SoilProfile(
        layers=[
            SoilLayer(
                top=0, bottom=2, soil=Soil(phi_k=28, c_k=0, gamma=17, gamma_sat=19, E=10_000)
            ),
            SoilLayer(
                top=2, bottom=20, soil=Soil(phi_k=36, c_k=0, gamma=20, gamma_sat=21, E=40_000)
            ),
        ]
    )
    eq = profile.equivalent_soil(D=1.0, B=2.0)
    # zona di influenza: z=1 a z=3
    # 1 m nello strato sup (phi=28), 1 m nello strato inf (phi=36) -> media 32
    assert eq.phi_k == pytest.approx(32.0, rel=0.01)
    # gamma: media = 18.5
    assert eq.gamma == pytest.approx(18.5, rel=0.01)
    # E: media = 25000
    assert eq.E == pytest.approx(25_000, rel=0.01)


# ===========================================================================
# 3) Capacità portante - profilo monostrato deve coincidere con il caso senza profilo
# ===========================================================================


def test_profile_monolayer_matches_simple():
    """Stessa risposta tra Soil singolo e SoilProfile monostrato (no falda)."""
    soil = Soil(phi_k=32, c_k=5, gamma=19, gamma_sat=20, E=25_000, drained=True)
    profile = SoilProfile(layers=[SoilLayer(top=0, bottom=20, soil=soil)])
    footing = RectangularFooting(B=2.0, L=3.0, D=1.5)
    actions = DesignActions(V=1200, H_x=100, M_y=80)
    code = NTC2018_A2()

    r_simple = ShallowFoundation(footing, soil, actions, code).check_bearing()
    r_profile = ShallowFoundation(
        footing, profile=profile, actions=actions, code=code
    ).check_bearing()

    assert r_simple.R_d == pytest.approx(r_profile.R_d, rel=0.01)
    assert r_simple.q_ult == pytest.approx(r_profile.q_ult, rel=0.01)


# ===========================================================================
# 4) Effetto della falda: deve ridurre la capacità portante
# ===========================================================================


def test_water_reduces_bearing():
    """Falda alta riduce significativamente la capacità portante (gamma' invece di gamma)."""
    soil = Soil(phi_k=32, c_k=0, gamma=19, gamma_sat=20, drained=True)
    footing = RectangularFooting(B=2.0, L=2.0, D=1.5)
    actions = DesignActions(V=500)

    # senza falda
    profile_dry = SoilProfile(layers=[SoilLayer(top=0, bottom=20, soil=soil)])
    # con falda al piano di posa
    profile_wet = SoilProfile(
        layers=[SoilLayer(top=0, bottom=20, soil=soil)],
        water_depth=1.5,
    )
    code = EC7_DA2()
    r_dry = ShallowFoundation(
        footing, profile=profile_dry, actions=actions, code=code
    ).check_bearing()
    r_wet = ShallowFoundation(
        footing, profile=profile_wet, actions=actions, code=code
    ).check_bearing()

    # la falda riduce sia q' (no, q' è uguale qui perché falda al piano di posa)
    # sia il peso di volume nel termine 0.5*gamma'*B'*Ngamma
    # quindi q_ult dovrebbe essere significativamente minore
    assert r_wet.q_ult < r_dry.q_ult
    # il termine gamma è circa dimezzato (~10 vs ~19), riduce significativamente
    # il termine N_gamma; per phi=32° il termine N_gamma è circa il 25% del totale,
    # quindi la riduzione globale attesa è di ordine 12-15%
    assert r_wet.q_ult < 0.90 * r_dry.q_ult


# ===========================================================================
# 5) SeismicAction - fattori di Paolucci & Pecker
# ===========================================================================


def test_seismic_factors_kh_zero():
    """kh=0 -> tutti i fattori sismici uguali a 1."""
    s = SeismicAction(kh=0)
    zc, zq, zg = s.seismic_factors(math.radians(30))
    assert zc == 1.0 and zq == 1.0 and zg == 1.0


def test_seismic_factors_drained():
    """kh=0.15, phi=30°: zq = (1 - 0.15/tan(30))^0.35 ≈ 0.892."""
    s = SeismicAction(kh=0.15)
    zc, zq, zg = s.seismic_factors(math.radians(30))
    expected = (1 - 0.15 / math.tan(math.radians(30))) ** 0.35
    assert zq == pytest.approx(expected, rel=0.01)
    assert zg == pytest.approx(expected, rel=0.01)


def test_seismic_factors_undrained():
    """kh=0.2, non drenata: zc = 1 - 0.32*0.2 = 0.936."""
    s = SeismicAction(kh=0.2)
    zc, zq, zg = s.seismic_factors(0.0, drained=False)
    assert zc == pytest.approx(1 - 0.32 * 0.2, rel=0.01)


def test_seismic_reduces_bearing():
    """Una capacità portante calcolata in sismica deve essere minore di quella statica."""
    soil = Soil(phi_k=32, c_k=5, gamma=19, gamma_sat=20, E=25_000)
    footing = RectangularFooting(B=2.5, L=3.5, D=1.5)
    actions = DesignActions(V=1200, H_x=150)
    seismic = SeismicAction(kh=0.15, kv=0.075)

    r_static = ShallowFoundation(footing, soil, actions, code=NTC2018_Seismic()).check_bearing()
    r_seismic = ShallowFoundation(
        footing, soil, actions, seismic=seismic, code=NTC2018_Seismic()
    ).check_bearing()
    assert r_seismic.q_ult < r_static.q_ult
    # i fattori z devono essere < 1
    f = r_seismic.factors
    assert f.zq < 1.0
    assert f.zgamma < 1.0


def test_seismic_reduced_gamma_R():
    """NTC2018_Seismic_Reduced applica γR=1.8 invece di 2.3 -> R_d maggiore."""
    soil = Soil(phi_k=32, c_k=5, gamma=19, gamma_sat=20)
    footing = RectangularFooting(B=2.5, L=3.5, D=1.5)
    actions = DesignActions(V=1200, H_x=150)
    seismic = SeismicAction(kh=0.15)

    r_full = ShallowFoundation(
        footing, soil, actions, seismic=seismic, code=NTC2018_Seismic()
    ).check_bearing()
    r_red = ShallowFoundation(
        footing, soil, actions, seismic=seismic, code=NTC2018_Seismic_Reduced()
    ).check_bearing()
    # stesso R_k, ma γR diverso (2.3 vs 1.8)
    assert r_red.R_d == pytest.approx(r_full.R_d * 2.3 / 1.8, rel=0.001)


# ===========================================================================
# 6) Cedimento Steinbrenner multistrato
# ===========================================================================


def test_settlement_steinbrenner_decreases_with_stiffness():
    """Aumentando E in profondità, il cedimento totale diminuisce."""
    soft_then_stiff = SoilProfile(
        layers=[
            SoilLayer(top=0, bottom=2, soil=Soil(phi_k=28, c_k=0, gamma=18, E=10_000, nu=0.3)),
            SoilLayer(top=2, bottom=20, soil=Soil(phi_k=35, c_k=0, gamma=19, E=80_000, nu=0.3)),
        ]
    )
    uniform_soft = SoilProfile(
        layers=[
            SoilLayer(top=0, bottom=20, soil=Soil(phi_k=30, c_k=0, gamma=18, E=10_000, nu=0.3)),
        ]
    )
    footing = RectangularFooting(B=2.0, L=2.0, D=1.0)
    actions = DesignActions(V=600)

    f1 = ShallowFoundation(footing, profile=soft_then_stiff, actions=actions)
    f2 = ShallowFoundation(footing, profile=uniform_soft, actions=actions)
    s1 = f1.check_settlement()
    s2 = f2.check_settlement()
    assert s1.s_elastic < s2.s_elastic


def test_settlement_steinbrenner_vs_simplified():
    """Per profilo omogeneo, Steinbrenner deve essere ragionevolmente
    vicino a Bowles (stessa formula elastica, integrazione diversa)."""
    soil = Soil(phi_k=30, c_k=0, gamma=18, E=20_000, nu=0.3)
    profile = SoilProfile(layers=[SoilLayer(top=0, bottom=20, soil=soil)])
    footing = RectangularFooting(B=2.0, L=2.0, D=1.0)
    actions = DesignActions(V=600)

    # Bowles (monostrato)
    s_simple = ShallowFoundation(footing, soil, actions).check_settlement()
    # Steinbrenner con z_max = 5*B (profondità di influenza realistica)
    s_stein = ShallowFoundation(footing, profile=profile, actions=actions).check_settlement(
        z_max=footing.D + 5 * 2.0
    )
    # i due valori devono essere nello stesso ordine di grandezza (entro 50%)
    ratio = s_stein.s_elastic / s_simple.s_elastic
    assert 0.5 < ratio < 1.5


# ===========================================================================
# 7) Report integrato sismico + stratigrafia + falda
# ===========================================================================


def test_full_seismic_layered_report():
    profile = SoilProfile(
        layers=[
            SoilLayer(
                top=0,
                bottom=2.0,
                soil=Soil(
                    phi_k=28, c_k=0, gamma=18, gamma_sat=19.5, E=15_000, name="Sabbia limosa"
                ),
            ),
            SoilLayer(
                top=2.0,
                bottom=8.0,
                soil=Soil(phi_k=34, c_k=0, gamma=19, gamma_sat=20, E=30_000, name="Sabbia densa"),
            ),
            SoilLayer(
                top=8.0,
                bottom=30,
                soil=Soil(phi_k=36, c_k=0, gamma=20, gamma_sat=21, E=50_000, name="Ghiaia"),
            ),
        ],
        water_depth=3.0,
    )
    footing = RectangularFooting(B=2.5, L=3.5, D=1.5)
    actions = DesignActions(V=1500, H_x=300, M_y=200)
    seismic = SeismicAction(kh=0.15, kv=0.075)

    f = ShallowFoundation(
        footing, profile=profile, actions=actions, seismic=seismic, code=NTC2018_Seismic_Reduced()
    )
    report = f.verify_all(s_limit=0.025)
    assert report.bearing is not None
    assert report.settlement is not None
    # fattori sismici nel report
    assert report.bearing.factors.zq < 1.0
    s = str(report)
    assert "Sismic" in s
    assert "zq=" in s


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
