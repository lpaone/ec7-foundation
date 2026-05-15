"""Strategia di normativa: applica i coefficienti parziali a azioni,
parametri geotecnici e resistenze secondo l'approccio scelto.

Implementati:
  - EC7 (EN 1997-1) Design Approach 1, Combinazione 1   -> EC7_DA1_C1
  - EC7 Design Approach 1, Combinazione 2               -> EC7_DA1_C2
  - EC7 Design Approach 2                               -> EC7_DA2
  - EC7 Design Approach 3                               -> EC7_DA3
  - NTC 2018 Approccio 1, Combinazione 1 (A1+M1+R1)     -> NTC2018_A1   (capacità portante)
  - NTC 2018 Approccio 2 (A1+M1+R3)                     -> NTC2018_A2   (capacità portante)

Riferimenti coefficienti:
  EC7   : Annex A
  NTC 18: Tabb. 6.2.I (A), 6.2.II (M), 6.4.I (R per fondazioni superficiali)
"""

from __future__ import annotations

import math
from abc import ABC
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .actions import DesignActions
    from .soil import Soil


# ---------------------------------------------------------------------------
# Set di coefficienti parziali
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PartialFactorsActions:
    """Set A: coefficienti sulle azioni (favorevoli/sfavorevoli)."""

    gamma_G_unfav: float = 1.35
    gamma_G_fav: float = 1.00
    gamma_Q_unfav: float = 1.50
    gamma_Q_fav: float = 0.00


@dataclass(frozen=True)
class PartialFactorsMaterials:
    """Set M: coefficienti sui parametri geotecnici."""

    gamma_phi: float = 1.00  # su tan(phi')
    gamma_c: float = 1.00  # su c'
    gamma_cu: float = 1.00  # su cu
    gamma_gamma: float = 1.00  # sul peso di volume (per NTC è sempre 1)


@dataclass(frozen=True)
class PartialFactorsResistance:
    """Set R: coefficienti sulle resistenze (capacità portante, scorrimento, ribaltamento)."""

    gamma_Rv: float = 1.00  # capacità portante verticale
    gamma_Rh: float = 1.00  # scorrimento
    gamma_Re: float = 1.00  # ribaltamento (resistenza)


# ---------------------------------------------------------------------------
# Classe base strategia
# ---------------------------------------------------------------------------


class DesignCode(ABC):
    """Strategia di calcolo: contiene i tre set di coefficienti e i metodi
    per applicarli.

    Le sottoclassi sono semplici dataclass con valori dei coefficienti
    secondo l'approccio scelto. La logica di applicazione è la stessa.
    """

    name: str = "DesignCode"
    A: PartialFactorsActions
    M: PartialFactorsMaterials
    R: PartialFactorsResistance

    # ---- applicazione ai parametri del terreno -----------------------------

    def design_soil(self, soil: Soil) -> Soil:
        """Restituisce una copia del terreno con parametri di progetto."""
        phi_d_rad = math.atan(math.tan(soil.phi_k_rad) / self.M.gamma_phi)
        phi_d_deg = math.degrees(phi_d_rad)
        c_d = soil.c_k / self.M.gamma_c
        cu_d = soil.cu_k / self.M.gamma_cu if soil.cu_k is not None else None
        # peso di volume: gamma_M=1 in tutti i casi pratici, ma teniamolo
        return replace(
            soil,
            phi_k=phi_d_deg,
            c_k=c_d,
            cu_k=cu_d,
            gamma=soil.gamma / self.M.gamma_gamma,
            gamma_sat=soil.gamma_sat / self.M.gamma_gamma,
        )

    # ---- applicazione alle azioni ------------------------------------------

    def design_actions(self, actions: DesignActions, Q_fraction: float = 0.0) -> DesignActions:
        """Applica i coefficienti del set A alle azioni.

        Parametri
        ----------
        Q_fraction : float
            Frazione (0-1) dell'azione totale dovuta a carichi variabili.
            Se 0 si assume tutta permanente; se 1 tutta variabile.
            Per i carichi orizzontali e i momenti si applica lo stesso
            coefficiente medio di V (semplificazione frequente).
        """
        if actions.already_factored:
            return actions

        if not 0.0 <= Q_fraction <= 1.0:
            raise ValueError("Q_fraction deve essere in [0,1].")

        if actions.favorable:
            g = self.A.gamma_G_fav
            q = self.A.gamma_Q_fav
        else:
            g = self.A.gamma_G_unfav
            q = self.A.gamma_Q_unfav

        # coefficiente "medio" pesato sulla frazione di carico variabile
        gamma_eff = g * (1 - Q_fraction) + q * Q_fraction

        from .actions import DesignActions as _DA

        return _DA(
            V=actions.V * gamma_eff,
            H_x=actions.H_x * gamma_eff,
            H_y=actions.H_y * gamma_eff,
            M_x=actions.M_x * gamma_eff,
            M_y=actions.M_y * gamma_eff,
            favorable=actions.favorable,
            already_factored=True,
        )

    # ---- applicazione alle resistenze --------------------------------------

    def design_bearing_resistance(self, R_k: float) -> float:
        return R_k / self.R.gamma_Rv

    def design_sliding_resistance(self, R_h_k: float) -> float:
        return R_h_k / self.R.gamma_Rh

    def design_overturning_resistance(self, M_stab_k: float) -> float:
        return M_stab_k / self.R.gamma_Re

    def __repr__(self):
        return f"<{self.name}>"


# ---------------------------------------------------------------------------
# EC7 - EN 1997-1 (Annex A, set raccomandati dalla norma)
# ---------------------------------------------------------------------------


class EC7_DA1_C1(DesignCode):
    """Design Approach 1, Combination 1 : A1 + M1 + R1."""

    name = "EC7 DA1-C1 (A1+M1+R1)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.35, gamma_G_fav=1.00, gamma_Q_unfav=1.50, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()  # tutti 1.0
    R = PartialFactorsResistance(gamma_Rv=1.0, gamma_Rh=1.0, gamma_Re=1.0)


class EC7_DA1_C2(DesignCode):
    """Design Approach 1, Combination 2 : A2 + M2 + R1."""

    name = "EC7 DA1-C2 (A2+M2+R1)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.30, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials(gamma_phi=1.25, gamma_c=1.25, gamma_cu=1.40)
    R = PartialFactorsResistance(gamma_Rv=1.0, gamma_Rh=1.0, gamma_Re=1.0)


class EC7_DA2(DesignCode):
    """Design Approach 2 : A1 + M1 + R2 (raccomandato da EN per fondazioni superficiali)."""

    name = "EC7 DA2 (A1+M1+R2)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.35, gamma_G_fav=1.00, gamma_Q_unfav=1.50, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=1.4, gamma_Rh=1.1, gamma_Re=1.4)


class EC7_DA3(DesignCode):
    """Design Approach 3 : (A1*/A2) + M2 + R3.

    Qui si assume azioni geotecniche A2 (lato strutturale userebbe A1).
    Per una fondazione superficiale "pura" si va con A2.
    """

    name = "EC7 DA3 (A2+M2+R3)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.30, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials(gamma_phi=1.25, gamma_c=1.25, gamma_cu=1.40)
    R = PartialFactorsResistance(gamma_Rv=1.0, gamma_Rh=1.0, gamma_Re=1.0)


# ---------------------------------------------------------------------------
# NTC 2018 - Tabb. 6.2.I, 6.2.II, 6.4.I
# ---------------------------------------------------------------------------


class NTC2018_A1(DesignCode):
    """NTC 2018 Approccio 1, Comb. 1 : (A1+M1+R1).

    Per le fondazioni superficiali NTC indica Approccio 2 come riferimento;
    A1 si usa per dimensionamento strutturale della fondazione stessa.
    """

    name = "NTC 2018 Approccio 1 Comb.1 (A1+M1+R1)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.30, gamma_G_fav=1.00, gamma_Q_unfav=1.50, gamma_Q_fav=0.0
    )
    # nota: gamma_G1=1.30 (perm. strutturali) per geotecnica - vedi 6.2.I
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=1.0, gamma_Rh=1.0, gamma_Re=1.0)


class NTC2018_A2(DesignCode):
    """NTC 2018 Approccio 2 : (A1+M1+R3).

    Approccio di riferimento per fondazioni superficiali secondo NTC 2018
    (Tab. 6.4.I): gamma_R = 2.3 per capacità portante, 1.1 per scorrimento.
    """

    name = "NTC 2018 Approccio 2 (A1+M1+R3)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.30, gamma_G_fav=1.00, gamma_Q_unfav=1.50, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=2.3, gamma_Rh=1.1, gamma_Re=1.0)


# ---------------------------------------------------------------------------
# COMBINAZIONI SISMICHE
# ---------------------------------------------------------------------------
# In condizioni sismiche, NTC 2018 §7.11 prevede:
#   - coefficienti parziali sulle azioni unitari (l'azione sismica è già
#     "caratteristica" basata sulla pericolosità; G e Q permanenti entrano
#     nella combinazione con i loro coefficienti psi)
#   - coefficienti parziali sui parametri geotecnici unitari (M1)
#   - coefficienti sulle resistenze ridotti rispetto allo statico:
#     gamma_R = 2.3 normalmente, riducibile a 1.8 se si tengono in conto
#     esplicitamente gli effetti inerziali sul cuneo di rottura
#     (cioè se si usa SeismicAction con kh > 0 nel calcolo).


class NTC2018_Seismic(DesignCode):
    """NTC 2018 - Combinazione sismica, capacità portante con γR=2.3.

    Da usare con `SeismicAction` se si desidera computare anche gli effetti
    inerziali sul cuneo (formule di Paolucci & Pecker), ma mantenendo il
    coefficiente parziale "standard" 2.3. Se si vuole il bonus a 1.8 usa
    `NTC2018_Seismic_Reduced`.
    """

    name = "NTC 2018 Sismica (gamma_R = 2.3)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.00, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=2.3, gamma_Rh=1.1, gamma_Re=1.0)


class NTC2018_Seismic_Reduced(DesignCode):
    """NTC 2018 - Combinazione sismica con γR ridotto a 1.8.

    Applicabile *solo* se nel calcolo del carico limite si considerano
    esplicitamente gli effetti inerziali sul volume di terreno significativo
    (i.e. è stato passato un `SeismicAction` con kh > 0 e si usano i fattori
    z di Paolucci & Pecker). Riferimento: NTC 2018 §7.11.5.3.1.
    """

    name = "NTC 2018 Sismica con effetti inerziali (gamma_R = 1.8)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.00, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=1.8, gamma_Rh=1.1, gamma_Re=1.0)


class EC7_Seismic_DA2(DesignCode):
    """EN 1997-1 / EN 1998-5 - Combinazione sismica con approccio DA2.

    Coefficienti raccomandati: A=1.0 (azioni sismiche), M=1.0, R simile a DA2.
    Le National Annexes possono variare; questa è la formulazione base.
    """

    name = "EC7+EC8 Sismica DA2 (gamma_R = 1.4)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.00, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=1.4, gamma_Rh=1.1, gamma_Re=1.0)
