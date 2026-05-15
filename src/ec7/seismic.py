"""Effetti sismici sulla capacità portante.

Effetti distinti che vanno combinati:

1) EFFETTO INERZIALE sulla sovrastruttura: produce H e M aggiuntivi sulla
   fondazione. Si traduce nei fattori di inclinazione i_c, i_q, i_gamma già
   presenti nella formula di Annex D, calcolati con H_d = H_grav + H_sis.
   Questo viene gestito a monte semplicemente passando le azioni sismiche
   come componenti di DesignActions.

2) EFFETTO INERZIALE sul cuneo di rottura (effetto "cinematico" del terreno):
   le accelerazioni inerziali sulla massa di terreno sotto la fondazione
   riducono la capacità portante. Si traduce in fattori correttivi
   z_c, z_q, z_gamma che moltiplicano i tre termini della formula.

Implementazione di Paolucci & Pecker (1997), che è la formulazione più
diffusa nella pratica italiana e citata dalla circolare NTC 2018:

    z_q     = (1 - kh / tan(phi)) ^ 0.35
    z_gamma = (1 - kh / tan(phi)) ^ 0.35    (Pecker; alcuni autori usano l'esponente 0.45)
    z_c     = 1 - 0.32 * kh                 (formulazione semplificata)

dove kh è il coefficiente sismico orizzontale (= beta * a_max/g per NTC 2018).

kv (verticale) viene applicato come modifica del peso di volume:
    gamma' -> gamma' * (1 ± kv)

Riferimenti:
  - Paolucci R., Pecker A. (1997), Soil inertia effects on the bearing
    capacity of rectangular foundations on cohesive soils, Engng Struct.
  - NTC 2018, §7.11.5.3.1
  - Circolare 2019, C.7.11.5.3.1
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class SeismicAction:
    """Coefficienti sismici per la verifica della capacità portante.

    Parametri
    ---------
    kh : float
        Coefficiente sismico orizzontale, adimensionale.
        Da NTC 2018: kh = beta_m * a_max / g, dove a_max = S * ag
        e beta_m è il coefficiente di riduzione (Tab. 7.11.II).
    kv : float, opzionale
        Coefficiente sismico verticale. Convenzionalmente kv = ±0.5 * kh;
        si usa il segno che dà l'effetto più sfavorevole.
        Default: 0 (trascurato, opzione conservativa lato resistenza
        se kv è diretto verso l'alto; lato sicurezza per il calcolo del
        carico stabilizzante).
    method : str
        Metodo per il calcolo dei fattori correttivi. Solo 'paolucci_pecker'
        è implementato; estendibile per Maugeri/Richards.
    """

    kh: float
    kv: float = 0.0
    method: str = "paolucci_pecker"

    def __post_init__(self):
        if self.kh < 0 or self.kh > 0.5:
            raise ValueError(f"kh={self.kh} fuori range plausibile [0, 0.5].")
        if abs(self.kv) > 0.5:
            raise ValueError(f"kv={self.kv} fuori range plausibile [-0.5, 0.5].")
        if self.method not in ("paolucci_pecker",):
            raise ValueError(f"Metodo sismico sconosciuto: {self.method}")

    @property
    def is_seismic(self) -> bool:
        return self.kh > 0 or self.kv != 0

    # ------------------------------------------------------------------
    # fattori correttivi z (effetto inerziale sul cuneo)
    # ------------------------------------------------------------------

    def seismic_factors(self, phi_rad: float, drained: bool = True) -> tuple[float, float, float]:
        """Restituisce (z_c, z_q, z_gamma) per Paolucci & Pecker.

        Per analisi non drenata si usa la formulazione apposita su z_c.
        """
        if self.kh == 0:
            return 1.0, 1.0, 1.0

        if not drained:
            # condizioni non drenate (Paolucci 1997, terreni coesivi)
            # z_c = 1 - 0.32 * kh (limitato a >=0)
            z_c = max(0.0, 1.0 - 0.32 * self.kh)
            return z_c, 1.0, 1.0

        # condizioni drenate
        tan_phi = math.tan(phi_rad)
        if tan_phi < 1e-6:
            return 1.0, 1.0, 1.0
        arg = 1 - self.kh / tan_phi
        if arg <= 0:
            # capacità nulla: il terreno scivola
            return 0.0, 0.0, 0.0
        z_q = arg**0.35
        z_gamma = arg**0.35
        # z_c proposto in Paolucci-Pecker per c'>0 (per NTC è usuale assumere z_c=z_q)
        z_c = z_q
        return z_c, z_q, z_gamma

    def gamma_modifier(self, sign: str = "down") -> float:
        """Modificatore del peso di volume per effetto di kv.
        sign='down' applica (1+kv), 'up' applica (1-kv).
        Convenzionalmente si sceglie il caso più sfavorevole."""
        if sign == "down":
            return 1.0 + self.kv
        if sign == "up":
            return 1.0 - self.kv
        raise ValueError(f"sign deve essere 'down' o 'up', ricevuto: {sign}")
