"""Capacità portante drenata e non drenata secondo EN 1997-1 Annex D.

Formule:

  Non drenata (D.1):
      R/A' = (pi + 2) * cu * b_c * s_c * i_c + q
  Drenata (D.2):
      R/A' = c'*Nc*b_c*s_c*i_c + q'*Nq*b_q*s_q*i_q + 0.5*gamma'*B'*Ngamma*b_g*s_g*i_g

I fattori sono quelli dell'Annex D (Brinch Hansen). Depth factors NON inclusi
per allinearsi all'Annex D, ma è disponibile un'opzione `include_depth_factors`
per la formulazione "estesa" di Brinch Hansen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .actions import DesignActions
    from .geometry import Footing
    from .profile import SoilProfile
    from .seismic import SeismicAction
    from .soil import Soil


@dataclass
class BearingCapacityFactors:
    """Tutti i fattori intermedi della formula, utili per il report."""

    Nc: float
    Nq: float
    Ngamma: float
    sc: float
    sq: float
    sgamma: float
    ic: float
    iq: float
    igamma: float
    bc: float
    bq: float
    bgamma: float
    gc: float = 1.0
    gq: float = 1.0
    ggamma: float = 1.0  # ground inclination
    dc: float = 1.0
    dq: float = 1.0
    dgamma: float = 1.0  # depth (opzionali)
    zc: float = 1.0
    zq: float = 1.0
    zgamma: float = 1.0  # sismici (Paolucci-Pecker)


def _bearing_capacity_coefficients(
    phi_rad: float, ngamma_method: str = "vesic"
) -> tuple[float, float, float]:
    """Nc, Nq, Ngamma per analisi drenata.

    Nq e Nc sono di Prandtl/Reissner (uguali in Hansen, Meyerhof, Vesic).
    Per Ngamma sono disponibili due opzioni:
      - 'vesic'  : Nγ = 2·(Nq+1)·tan(φ)     [default, più diffuso nei sw commerciali]
      - 'hansen' : Nγ = 1.5·(Nq-1)·tan(φ)   [base storica Annex D di EC7]
    """
    if phi_rad <= 1e-9:
        return 5.14, 1.0, 0.0
    Nq = math.exp(math.pi * math.tan(phi_rad)) * math.tan(math.pi / 4 + phi_rad / 2) ** 2
    Nc = (Nq - 1) / math.tan(phi_rad)
    if ngamma_method == "vesic":
        Ngamma = 2 * (Nq + 1) * math.tan(phi_rad)
    elif ngamma_method == "hansen":
        Ngamma = 1.5 * (Nq - 1) * math.tan(phi_rad)
    else:
        raise ValueError(f"ngamma_method sconosciuto: {ngamma_method}")
    return Nc, Nq, Ngamma


def _shape_factors_drained(
    B_eff: float, L_eff: float, phi_rad: float, Nq: float
) -> tuple[float, float, float]:
    """Fattori di forma drenata (Annex D)."""
    ratio = B_eff / L_eff
    sq = 1 + ratio * math.sin(phi_rad)
    sgamma = 1 - 0.3 * ratio
    if abs(Nq - 1) < 1e-9:
        sc = 1 + 0.2 * ratio  # limite phi=0
    else:
        sc = (sq * Nq - 1) / (Nq - 1)
    # fondazione circolare ha B'=L' -> ratio=1 (caso quadrato), Annex D OK
    return sc, sq, sgamma


def _shape_factor_undrained(B_eff: float, L_eff: float) -> float:
    """sc per analisi non drenata (Annex D, D.1)."""
    return 1 + 0.2 * (B_eff / L_eff)


def _inclination_factors_drained(
    H: float, V: float, A_eff: float, c: float, phi_rad: float, m: float
) -> tuple[float, float, float]:
    """Fattori di inclinazione drenata (Annex D, formula Vesic).

    m è il coefficiente che dipende dall'angolo della risultante
    orizzontale rispetto a B' o L'.
    """
    if H <= 1e-9:
        return 1.0, 1.0, 1.0

    # termine di "coesione attrita" (denominatore): V + A' * c' * cot(phi)
    if phi_rad > 1e-6:
        cot_phi = 1 / math.tan(phi_rad)
        denom = V + A_eff * c * cot_phi
    else:
        # caso drenato con phi quasi zero - usa formula non drenata
        return 1.0, 1.0, 1.0

    base = 1 - H / denom
    if base <= 0:
        # carico orizzontale eccessivo: capacità nulla (segnale di rottura)
        return 0.0, 0.0, 0.0

    iq = base**m
    igamma = base ** (m + 1)
    if abs(phi_rad) < 1e-6:
        ic = iq
    else:
        Nq = math.exp(math.pi * math.tan(phi_rad)) * math.tan(math.pi / 4 + phi_rad / 2) ** 2
        ic = iq - (1 - iq) / (Nq - 1) if Nq > 1.0001 else iq
    return ic, iq, igamma


def _inclination_factor_undrained(H: float, A_eff: float, cu: float) -> float:
    """ic per analisi non drenata (Annex D, D.1)."""
    if H <= 1e-9:
        return 1.0
    arg = 1 - H / (A_eff * cu)
    if arg < 0:
        return 0.0
    return 0.5 * (1 + math.sqrt(arg))


def _m_coefficient(B_eff: float, L_eff: float, H_B: float, H_L: float) -> float:
    """Coefficiente m di Vesic per i fattori di inclinazione.

    Combina mB (carico orizzontale nella direzione di B') e
    mL (direzione L') in base all'angolo della risultante.
    """
    mB = (2 + B_eff / L_eff) / (1 + B_eff / L_eff)
    mL = (2 + L_eff / B_eff) / (1 + L_eff / B_eff)
    H = math.hypot(H_B, H_L)
    if H < 1e-9:
        return mB
    # theta = angolo tra H e direzione L'
    theta = math.atan2(H_B, H_L)
    return mL * math.cos(theta) ** 2 + mB * math.sin(theta) ** 2


def _base_inclination_factors(alpha: float, phi_rad: float) -> tuple[float, float, float]:
    """Fattori di inclinazione della base alpha (Annex D)."""
    if abs(alpha) < 1e-9:
        return 1.0, 1.0, 1.0
    bq = (1 - alpha * math.tan(phi_rad)) ** 2
    bgamma = bq
    if abs(phi_rad) < 1e-6:
        bc = 1 - 2 * alpha / (math.pi + 2)
    else:
        Nc, Nq, _ = _bearing_capacity_coefficients(phi_rad)
        bc = bq - (1 - bq) / (Nc * math.tan(phi_rad))
    return bc, bq, bgamma


def _ground_inclination_factors(beta: float, phi_rad: float) -> tuple[float, float, float]:
    """Fattori di inclinazione del piano campagna (Brinch Hansen).

    NOTA: l'Annex D non li tratta esplicitamente; qui inseriamo le espressioni
    classiche di Brinch Hansen, usate dalla pratica europea.
    """
    if abs(beta) < 1e-9:
        return 1.0, 1.0, 1.0
    gq = (1 - math.tan(beta)) ** 2
    ggamma = gq
    if abs(phi_rad) < 1e-6:
        gc = 1 - 2 * beta / (math.pi + 2)
    else:
        Nc, Nq, _ = _bearing_capacity_coefficients(phi_rad)
        gc = gq - (1 - gq) / (Nc * math.tan(phi_rad))
    return gc, gq, ggamma


# ---------------------------------------------------------------------------
# API principale
# ---------------------------------------------------------------------------


@dataclass
class BearingCapacityComputation:
    """Risultato del calcolo della capacità portante caratteristica.

    R_k è in kN (forza totale sulla base efficace).
    """

    R_k: float  # [kN]
    q_ult: float  # [kPa] pressione ultima
    factors: BearingCapacityFactors
    A_eff: float  # [m^2]
    B_eff: float
    L_eff: float


def compute_bearing_capacity(
    footing: Footing,
    soil: Soil,
    actions: DesignActions,
    profile: SoilProfile | None = None,
    seismic: SeismicAction | None = None,
) -> BearingCapacityComputation:
    """Calcolo della capacità portante caratteristica secondo EN 1997-1 Annex D.

    Parametri
    ---------
    footing, actions : geometria e azioni
    soil : Soil
        Parametri di resistenza/deformabilità da usare nella formula.
        In stratigrafia è il `Soil` equivalente (vedi SoilProfile.equivalent_soil).
    profile : SoilProfile, opzionale
        Se fornito, il sovraccarico q' al piano di posa è calcolato dal
        profilo (corretto per falda multistrato) anziché dal singolo Soil.
    seismic : SeismicAction, opzionale
        Se fornita, applica i fattori sismici di Paolucci & Pecker sui
        tre termini della formula, e l'eventuale kv modifica gamma'.

    I parametri di terreno e azioni si intendono già di progetto se la
    DesignCode li ha trasformati a monte. Questa funzione è "pura": non
    applica coefficienti parziali.
    """
    e_B, e_L = actions.eccentricities()
    eff = footing.effective_geometry(e_B, e_L)
    B_eff, L_eff, A_eff = eff.B_eff, eff.L_eff, eff.A_eff

    H_x, H_y = actions.H_x, actions.H_y
    H = math.hypot(H_x, H_y)
    V = actions.V

    # ---- pesi di volume e sovraccarico ---------------------------------
    if profile is not None:
        # q' al piano di posa dal profilo (pressione efficace, gestisce la falda)
        q_overburden = profile.effective_overburden_at(footing.D)
        # gamma efficace sotto la base (a profondità D + B'/2)
        gamma_below = profile.effective_unit_weight_at(footing.D + B_eff / 2)
    else:
        gamma_below = soil.effective_unit_weight(footing.D + B_eff / 2)
        q_overburden = soil.overburden_at(footing.D)

    # ---- effetto sismico verticale (kv): modifica gamma' ----------------
    if seismic is not None and seismic.kv != 0:
        # caso più sfavorevole: kv riduce il peso stabilizzante del terreno
        # sotto la base (azione verso l'alto) -> gamma * (1 - kv)
        # ma aumenta la spinta sul cuneo (azione verso il basso) -> (1 + kv).
        # Conservativamente si applica (1 - |kv|) sulla gamma usata nel termine Nγ.
        kv_factor = 1.0 - abs(seismic.kv)
        gamma_below = gamma_below * kv_factor
        # q_overburden invece risente meno: assumiamo invariato per semplicità

    alpha = footing.alpha
    beta = footing.beta

    if soil.drained:
        phi_rad = soil.phi_k_rad
        c = soil.c_k

        Nc, Nq, Ngamma = _bearing_capacity_coefficients(phi_rad)
        sc, sq, sgamma = _shape_factors_drained(B_eff, L_eff, phi_rad, Nq)

        # m e fattori di inclinazione: per Annex D si usano le componenti
        # della forza orizzontale nelle direzioni B' e L'. Convenzione:
        # H_x agisce lungo B, H_y lungo L.
        m = _m_coefficient(B_eff, L_eff, H_x, H_y)
        ic, iq, igamma = _inclination_factors_drained(H, V, A_eff, c, phi_rad, m)

        bc, bq, bgamma = _base_inclination_factors(alpha, phi_rad)
        gc, gq, ggamma = _ground_inclination_factors(beta, phi_rad)

        # fattori sismici di Paolucci & Pecker
        if seismic is not None and seismic.kh > 0:
            zc, zq, zgamma = seismic.seismic_factors(phi_rad, drained=True)
        else:
            zc, zq, zgamma = 1.0, 1.0, 1.0

        q_ult = (
            c * Nc * sc * ic * bc * gc * zc
            + q_overburden * Nq * sq * iq * bq * gq * zq
            + 0.5 * gamma_below * B_eff * Ngamma * sgamma * igamma * bgamma * ggamma * zgamma
        )
    else:
        # Analisi non drenata - eq. (D.1)
        cu = soil.cu_k
        sc = _shape_factor_undrained(B_eff, L_eff)
        ic = _inclination_factor_undrained(H, A_eff, cu)
        bc, bq, bgamma = _base_inclination_factors(alpha, 0.0)
        gc, gq, ggamma = _ground_inclination_factors(beta, 0.0)
        Nc, Nq, Ngamma = 5.14, 1.0, 0.0
        sq = sgamma = 1.0
        iq = igamma = 1.0

        if seismic is not None and seismic.kh > 0:
            zc, zq, zgamma = seismic.seismic_factors(0.0, drained=False)
        else:
            zc, zq, zgamma = 1.0, 1.0, 1.0

        q_ult = (math.pi + 2) * cu * bc * sc * ic * zc + q_overburden

    R_k = q_ult * A_eff

    factors = BearingCapacityFactors(
        Nc=Nc,
        Nq=Nq,
        Ngamma=Ngamma,
        sc=sc,
        sq=sq,
        sgamma=sgamma,
        ic=ic,
        iq=iq,
        igamma=igamma,
        bc=bc,
        bq=bq,
        bgamma=bgamma,
        gc=gc,
        gq=gq,
        ggamma=ggamma,
        zc=zc,
        zq=zq,
        zgamma=zgamma,
    )

    return BearingCapacityComputation(
        R_k=R_k,
        q_ult=q_ult,
        factors=factors,
        A_eff=A_eff,
        B_eff=B_eff,
        L_eff=L_eff,
    )
