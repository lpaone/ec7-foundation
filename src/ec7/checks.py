"""Classi di verifica: capacità portante, scorrimento, ribaltamento, cedimento.

Ognuna è un oggetto callable che, dato (footing, soil, actions, code),
restituisce un Result.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .bearing import compute_bearing_capacity
from .results import (
    BearingResult,
    OverturningResult,
    SettlementResult,
    SlidingResult,
)

if TYPE_CHECKING:
    from .actions import DesignActions
    from .code import DesignCode
    from .geometry import Footing
    from .profile import SoilProfile
    from .seismic import SeismicAction
    from .soil import Soil


def _design_profile(profile: SoilProfile, code) -> SoilProfile:
    """Crea una copia del profilo con parametri di progetto in ogni strato."""
    from .profile import SoilLayer, SoilProfile

    new_layers = []
    for layer in profile.layers:
        new_layers.append(
            SoilLayer(
                top=layer.top,
                bottom=layer.bottom,
                soil=code.design_soil(layer.soil),
            )
        )
    return SoilProfile(layers=new_layers, water_depth=profile.water_depth)


class Check(ABC):
    @abstractmethod
    def run(self, footing: Footing, soil: Soil, actions: DesignActions, code: DesignCode): ...


class BearingCheck(Check):
    """Verifica di capacità portante (SLU/GEO).

    1. trasforma terreno e azioni in valori di progetto secondo `code`;
    2. se è fornito un `profile` stratigrafico, ricava un `Soil` equivalente
       nel volume di influenza e usa il `profile` per il calcolo di q' al
       piano di posa (gestendo correttamente la falda multistrato);
    3. se è fornita un `seismic`, applica i fattori di Paolucci & Pecker
       e l'eventuale effetto di kv sul peso di volume;
    4. calcola R_k con la formula di Annex D;
    5. R_d = R_k / gamma_Rv;
    6. confronta con V_d.
    """

    def __init__(
        self,
        Q_fraction: float = 0.0,
        profile: SoilProfile | None = None,
        seismic: SeismicAction | None = None,
        depth_of_influence: float | None = None,
    ):
        self.Q_fraction = Q_fraction
        self.profile = profile
        self.seismic = seismic
        self.depth_of_influence = depth_of_influence

    def run(self, footing, soil, actions, code) -> BearingResult:
        # se viene fornito un profilo, ricavo il Soil equivalente da esso
        if self.profile is not None:
            B_ref = footing.equivalent_BL[0]  # lato corto
            zoi = self.depth_of_influence if self.depth_of_influence else B_ref
            soil_eq = self.profile.equivalent_soil(footing.D, B_ref, zoi)
            soil_d = code.design_soil(soil_eq)
            profile_d = _design_profile(self.profile, code)
        else:
            soil_d = code.design_soil(soil)
            profile_d = None

        actions_d = code.design_actions(actions, self.Q_fraction)

        comp = compute_bearing_capacity(
            footing, soil_d, actions_d, profile=profile_d, seismic=self.seismic
        )
        R_d = code.design_bearing_resistance(comp.R_k)
        e_B, e_L = actions_d.eccentricities()

        return BearingResult(
            E_d=actions_d.V,
            R_d=R_d,
            R_k=comp.R_k,
            q_ult=comp.q_ult,
            A_eff=comp.A_eff,
            B_eff=comp.B_eff,
            L_eff=comp.L_eff,
            factors=comp.factors,
            e_B=e_B,
            e_L=e_L,
        )


class SlidingCheck(Check):
    """Verifica a scorrimento sulla base (SLU).

    Drenata    : R_h_k = V * tan(delta) + c_a * A'
    Non drenata: R_h_k = A' * cu

    `delta` è l'angolo di attrito base-terreno; per default delta=phi
    (calcestruzzo gettato in opera) come da EN 1997-1 §6.5.3(10).
    Per cls prefabbricato o lisciato si può ridurre a delta = 2/3 phi.

    Se viene passato `profile`, i parametri usati sono quelli dello strato
    a contatto con la base. Se è passata `seismic`, V viene ridotto da kv
    verticale ascendente.
    """

    def __init__(
        self,
        delta_over_phi: float = 1.0,
        c_adhesion: float = 0.0,
        Q_fraction: float = 0.0,
        include_passive: bool = False,
        profile: SoilProfile | None = None,
        seismic: SeismicAction | None = None,
    ):
        if not 0 < delta_over_phi <= 1:
            raise ValueError("delta_over_phi deve essere in (0,1].")
        self.delta_over_phi = delta_over_phi
        self.c_adhesion = c_adhesion
        self.Q_fraction = Q_fraction
        self.include_passive = include_passive
        self.profile = profile
        self.seismic = seismic

    def run(self, footing, soil, actions, code) -> SlidingResult:
        # parametri di contatto: prendo lo strato a z = D (sotto la base)
        if self.profile is not None:
            contact_soil = self.profile.layer_at(footing.D).soil
            soil_d = code.design_soil(contact_soil)
        else:
            soil_d = code.design_soil(soil)
        actions_d = code.design_actions(actions, self.Q_fraction)

        e_B, e_L = actions_d.eccentricities()
        eff = footing.effective_geometry(e_B, e_L)
        A_eff = eff.A_eff

        H_d = actions_d.H_resultant
        V_d = actions_d.V

        # effetto kv verticale (riduzione conservativa di V)
        if self.seismic is not None and self.seismic.kv != 0:
            V_d = V_d * (1.0 - abs(self.seismic.kv))

        if soil_d.drained:
            delta = math.radians(self.delta_over_phi * soil_d.phi_k)
            R_h_k = V_d * math.tan(delta) + self.c_adhesion * A_eff
            delta_deg = math.degrees(delta)
        else:
            R_h_k = soil_d.cu_k * A_eff
            delta_deg = 0.0

        R_h_d = code.design_sliding_resistance(R_h_k)

        return SlidingResult(
            E_d=H_d,
            R_d=R_h_d,
            delta=delta_deg,
        )


class OverturningCheck(Check):
    """Verifica a ribaltamento (EQU) attorno allo spigolo della fondazione.

    Si considera il momento stabilizzante (peso verticale * braccio) contro
    il momento ribaltante (azione orizzontale * altezza + momento applicato).

    Asse di calcolo:
      - 'y' : ribaltamento attorno al lato lungo, dovuto a H_x e/o M_y
      - 'x' : ribaltamento attorno al lato corto, dovuto a H_y e/o M_x

    Si usa Approccio EQU: gamma_G,dst=1.1, gamma_G,stb=0.9 (EN 1997-1 Annex A,
    Tab. A.1). Per semplificazione, qui useremo direttamente i coefficienti
    della DesignCode con favorable/unfavorable, lasciando la scelta a chi
    chiama. È noto che EQU andrebbe trattato a parte.
    """

    def __init__(self, axis: str = "y", h_arm: float | None = None, Q_fraction: float = 0.0):
        if axis not in ("x", "y"):
            raise ValueError("axis deve essere 'x' o 'y'.")
        self.axis = axis
        self.h_arm = h_arm  # braccio di applicazione di H (default = D)
        self.Q_fraction = Q_fraction

    def run(self, footing, soil, actions, code) -> OverturningResult:
        # per EQU il verticale è favorevole, l'orizzontale è sfavorevole;
        # gestiamo le azioni come sono state passate (caratteristiche) e
        # applichiamo manualmente i coefficienti EQU se richiesti.
        # Versione semplificata: usiamo le azioni "di progetto" del codice
        # corrente (consigliato passare actions con favorable=True per V se
        # si vuole l'effetto stabilizzante).
        actions_d = code.design_actions(actions, self.Q_fraction)

        B, L = footing.equivalent_BL
        if self.axis == "y":
            # ribaltamento attorno asse parallelo a L -> braccio = B/2
            arm = B / 2
            H_dst = abs(actions_d.H_x)
            M_dst = abs(actions_d.M_y)
        else:
            arm = L / 2
            H_dst = abs(actions_d.H_y)
            M_dst = abs(actions_d.M_x)

        h = self.h_arm if self.h_arm is not None else footing.D
        M_destab = H_dst * h + M_dst
        M_stab = actions_d.V * arm

        M_stab_d = code.design_overturning_resistance(M_stab)

        return OverturningResult(
            E_d=M_destab,
            R_d=M_stab_d,
            axis=self.axis,
        )


class SettlementCheck(Check):
    """Cedimento elastico immediato (SLE) sotto carichi caratteristici.

    Due modalità:
      a) **monostrato** (default): soluzione di Schleicher con coefficiente
         di influenza tabellato da Bowles:
             s = q * B * (1 - nu^2) * I_s / E

      b) **multistrato (Steinbrenner)**: se viene passato un `SoilProfile`,
         si suddivide il sottosuolo in strati e si somma il contributo di
         ogni strato come differenza dei cedimenti calcolati al letto e al
         tetto (formula di Steinbrenner 1934):

             s = sum_i q * B' * (1 - nu_i^2) / E_i * (F1_i^bot - F1_i^top)

         dove F1 è la funzione di influenza di Steinbrenner per fondazione
         rigida rettangolare. Implementiamo F1 come integrale numerico
         della soluzione di Boussinesq, valido per fondazione flessibile
         (al centro). Per fondazione rigida si applica un fattore 0.93.

    NB: cedimento di consolidazione e secondario NON inclusi.
    """

    def __init__(
        self,
        s_limit: float | None = None,
        influence_factor: float | None = None,
        profile: SoilProfile | None = None,
        z_max: float | None = None,
        rigid_correction: float = 1.0,
        n_sublayers: int = 1,
    ):
        """
        Parametri
        ----------
        s_limit : float
            Cedimento ammissibile [m].
        influence_factor : float
            Override del coefficiente I_s (solo modalità monostrato).
        profile : SoilProfile
            Se fornito, attiva la modalità Steinbrenner multistrato.
        z_max : float
            Profondità massima di integrazione [m] dal piano campagna.
            Default: D + 2*B (zona di influenza pratica).
        rigid_correction : float
            Fattore di correzione per fondazione rigida (0.93 tipico) o
            flessibile (1.0). Default 1.0.
        n_sublayers : int
            Numero di sotto-strati in cui dividere ciascuno strato fisico
            per migliorare la precisione di Steinbrenner (default 1).
        """
        self.s_limit = s_limit
        self.I_s_override = influence_factor
        self.profile = profile
        self.z_max = z_max
        self.rigid_correction = rigid_correction
        self.n_sublayers = max(1, int(n_sublayers))

    # ------------------------------------------------------------------
    # monostrato (Bowles)
    # ------------------------------------------------------------------
    @staticmethod
    def _influence_factor(B: float, L: float) -> float:
        ratio = L / B
        if ratio <= 1.0:
            return 1.12
        elif ratio >= 10:
            return 2.10
        else:
            table = [(1, 1.12), (1.5, 1.36), (2, 1.53), (3, 1.78), (5, 2.10), (10, 2.10)]
            for (r1, v1), (r2, v2) in zip(table[:-1], table[1:], strict=False):
                if r1 <= ratio <= r2:
                    return v1 + (v2 - v1) * (ratio - r1) / (r2 - r1)
            return 2.10

    # ------------------------------------------------------------------
    # multistrato (Steinbrenner) - F1, F2 al centro di rettangolo flessibile
    # Riferimento: Bowles (1996), Foundation Analysis and Design, §5-6
    # ------------------------------------------------------------------
    @staticmethod
    def _steinbrenner_F1F2(B: float, L: float, H: float) -> tuple[float, float]:
        """Fattori F1, F2 di Steinbrenner per l'angolo di un rettangolo
        (B x L) caricato uniformemente su uno strato di spessore H.

        Definizioni (Bowles 1996):
            m' = L/B,  n' = H/B
            A0 = m' * ln( ((1+sqrt(m'^2+1))*sqrt(m'^2+n'^2)) /
                            (m'*(1+sqrt(m'^2+n'^2+1))) )
            A1 = ln( ((m'+sqrt(m'^2+1))*sqrt(1+n'^2)) /
                       (m'+sqrt(m'^2+n'^2+1)) )
            A2 = m' / (n'*sqrt(m'^2+n'^2+1))
            F1 = (1/pi) * (A0 + A1)
            F2 = (n'/(2*pi)) * atan(A2)

        Per il *centro* del rettangolo (B x L), si applica con B'=B/2,
        L'=L/2, e poi si moltiplica per 4 (sovrapposizione di 4 quarti).
        """
        if H <= 0 or B <= 0:
            return 0.0, 0.0
        # convenzione: m' = L/B
        if L < B:
            B, L = L, B
        mp = L / B
        np = H / B
        # protezione numerica
        eps = 1e-12
        s1 = math.sqrt(mp * mp + 1)
        s2 = math.sqrt(mp * mp + np * np + 1)
        s3 = math.sqrt(1 + np * np)
        s4 = math.sqrt(mp * mp + np * np)

        try:
            num0 = (1 + s1) * s4
            den0 = mp * (1 + s2)
            A0 = mp * math.log(max(num0 / max(den0, eps), eps))

            num1 = (mp + s1) * s3
            den1 = mp + s2
            A1 = math.log(max(num1 / max(den1, eps), eps))

            A2 = mp / max(np * s2, eps)
        except (ValueError, ZeroDivisionError):
            return 0.0, 0.0

        F1 = (A0 + A1) / math.pi
        F2 = (np / (2 * math.pi)) * math.atan(A2)
        return F1, F2

    @classmethod
    def _Is(cls, B: float, L: float, H: float, nu: float) -> float:
        """Fattore di forma Is = F1 + (1-2ν)/(1-ν) * F2 al centro.

        Si calcola F1, F2 per il quarto B/2 x L/2 di altezza H.
        """
        F1, F2 = cls._steinbrenner_F1F2(B / 2, L / 2, H)
        if abs(1 - nu) < 1e-9:
            return F1
        return F1 + (1 - 2 * nu) / (1 - nu) * F2

    @classmethod
    def _settlement_layer(
        cls, B: float, L: float, H_top: float, H_bot: float, q: float, E: float, nu: float
    ) -> float:
        """Cedimento di uno strato compreso tra H_top e H_bot (profondità
        misurate dalla base della fondazione), formula di Bowles:

            s = q * (B/2) * (1-ν²) / E * (4) * (Is(H_bot) - Is(H_top))

        Il fattore 4 corrisponde alla sovrapposizione dei 4 quarti per
        ottenere il cedimento al *centro* della fondazione.
        """
        if H_bot <= H_top:
            return 0.0
        Is_bot = cls._Is(B, L, H_bot, nu)
        Is_top = cls._Is(B, L, H_top, nu) if H_top > 0 else 0.0
        delta_Is = max(0.0, Is_bot - Is_top)
        return q * (B / 2) * (1 - nu * nu) / E * 4.0 * delta_Is

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------
    def run(self, footing, soil, actions, code) -> SettlementResult:
        # SLE: carichi e parametri caratteristici
        e_B, e_L = actions.eccentricities()
        eff = footing.effective_geometry(e_B, e_L)
        B_eff, L_eff, A_eff = eff.B_eff, eff.L_eff, eff.A_eff
        q = actions.V / A_eff

        from .geometry import CircularFooting

        if self.profile is None:
            # ---- modalità monostrato ----
            if soil.E is None:
                raise ValueError("Serve E nel Soil per il cedimento monostrato.")
            if isinstance(footing, CircularFooting):
                I_s = 0.88
                B_ref = 2 * footing.R
            else:
                I_s = self.I_s_override or self._influence_factor(B_eff, L_eff)
                B_ref = B_eff
            s = q * B_ref * (1 - soil.nu**2) * I_s / soil.E
            s *= self.rigid_correction
            return SettlementResult(s_elastic=s, s_limit=self.s_limit)

        # ---- modalità Steinbrenner multistrato ----
        D = footing.D
        z_max = self.z_max if self.z_max is not None else D + 2 * B_eff
        layers_under = self.profile.layers_under(D, z_max=z_max)
        if not layers_under:
            raise ValueError("Nessuno strato sotto il piano di posa per il calcolo cedimenti.")

        s_total = 0.0
        # iteriamo sugli strati sotto la base, splittando ciascuno in n_sublayers
        # per migliorare la precisione (utile se strato spesso o variabile)
        for z_top_abs, z_bot_abs, layer in layers_under:
            if layer.soil.E is None:
                raise ValueError(
                    f"Strato '{layer.soil.name}' senza modulo E: cedimento non calcolabile."
                )
            E = layer.soil.E
            nu = layer.soil.nu
            # profondità rispetto al piano di posa
            H_top = z_top_abs - D
            H_bot = z_bot_abs - D
            zs = [
                H_top + (H_bot - H_top) * i / self.n_sublayers for i in range(self.n_sublayers + 1)
            ]
            for h1, h2 in zip(zs[:-1], zs[1:], strict=False):
                s_total += self._settlement_layer(B_eff, L_eff, h1, h2, q, E, nu)

        s_total *= self.rigid_correction
        return SettlementResult(s_elastic=s_total, s_limit=self.s_limit)
