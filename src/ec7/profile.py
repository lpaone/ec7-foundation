"""Profilo stratigrafico del terreno.

Gestisce:
  - più strati di terreno con quote top/bottom
  - falda a quota definita
  - calcolo di pressione di sovraccarico (totale ed efficace) a qualsiasi profondità
  - parametri equivalenti pesati nel volume di influenza del cuneo di rottura
    (≈ B sotto il piano di posa) per applicare la formula di Annex D a stratigrafie.

Convenzione: profondità z crescenti verso il basso, z=0 al piano campagna.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .soil import Soil

GAMMA_W = 9.81  # kN/m^3


@dataclass
class SoilLayer:
    """Singolo strato del profilo.

    Parametri
    ---------
    top : float
        Quota della superficie superiore dello strato [m] (z=0 piano campagna,
        positivo verso il basso).
    bottom : float
        Quota inferiore [m]. Per l'ultimo strato si può usare float('inf').
    soil : Soil
        Parametri del terreno (caratteristici).
    """

    top: float
    bottom: float
    soil: Soil

    def __post_init__(self):
        if self.bottom <= self.top:
            raise ValueError(
                f"Strato '{self.soil.name}': bottom ({self.bottom}) deve essere > top ({self.top})."
            )

    @property
    def thickness(self) -> float:
        if math.isinf(self.bottom):
            return float("inf")
        return self.bottom - self.top

    def contains(self, z: float) -> bool:
        return self.top <= z < self.bottom


@dataclass
class SoilProfile:
    """Profilo stratigrafico con eventuale falda.

    Parametri
    ---------
    layers : list[SoilLayer]
        Strati elencati dall'alto verso il basso. Devono essere contigui.
    water_depth : float, opzionale
        Profondità della falda dal piano campagna [m]. None = falda assente.
    """

    layers: list[SoilLayer]
    water_depth: float | None = None

    def __post_init__(self):
        if not self.layers:
            raise ValueError("SoilProfile richiede almeno uno strato.")
        # verifica contiguità
        for prev, curr in zip(self.layers[:-1], self.layers[1:], strict=False):
            if not math.isclose(prev.bottom, curr.top, abs_tol=1e-6):
                raise ValueError(f"Strati non contigui: bottom={prev.bottom} != top={curr.top}")
        if self.layers[0].top != 0.0:
            raise ValueError(f"Il primo strato deve iniziare a z=0, trovato {self.layers[0].top}.")

    # ------------------------------------------------------------------
    # accessi
    # ------------------------------------------------------------------

    def layer_at(self, z: float) -> SoilLayer:
        """Strato che contiene la profondità z. Per z oltre l'ultimo strato
        restituisce l'ultimo (assunto infinito)."""
        for layer in self.layers:
            if layer.contains(z):
                return layer
        return self.layers[-1]

    def is_below_water(self, z: float) -> bool:
        return self.water_depth is not None and z > self.water_depth

    def unit_weight_at(self, z: float) -> float:
        """Peso di volume *totale* alla quota z."""
        layer = self.layer_at(z)
        return layer.soil.gamma_sat if self.is_below_water(z) else layer.soil.gamma

    def effective_unit_weight_at(self, z: float) -> float:
        """Peso di volume *efficace*: gamma sopra falda, gamma_sat - gamma_w sotto."""
        layer = self.layer_at(z)
        if self.is_below_water(z):
            return layer.soil.gamma_sat - GAMMA_W
        return layer.soil.gamma

    # ------------------------------------------------------------------
    # tensioni di sovraccarico
    # ------------------------------------------------------------------

    def total_overburden_at(self, z: float) -> float:
        """Pressione totale verticale (sigma_v) alla quota z [kPa]."""
        if z <= 0:
            return 0.0
        sigma = 0.0
        for layer in self.layers:
            if z <= layer.top:
                break
            z_top = layer.top
            z_bot = min(z, layer.bottom)
            sigma += self._weighted_total(z_top, z_bot, layer)
            if z_bot >= z:
                break
        return sigma

    def effective_overburden_at(self, z: float) -> float:
        """Pressione efficace verticale (sigma'_v) alla quota z [kPa]."""
        sigma_v = self.total_overburden_at(z)
        u = max(0.0, (z - self.water_depth) * GAMMA_W) if self.water_depth is not None else 0.0
        return sigma_v - u

    def _weighted_total(self, z1: float, z2: float, layer: SoilLayer) -> float:
        """Integrale di gamma_totale tra z1 e z2 nel layer dato.
        Spezza l'intervallo se la falda lo attraversa."""
        g = layer.soil.gamma
        gs = layer.soil.gamma_sat
        wd = self.water_depth
        if wd is None or z2 <= wd:
            return g * (z2 - z1)
        if z1 >= wd:
            return gs * (z2 - z1)
        # falda interna all'intervallo
        return g * (wd - z1) + gs * (z2 - wd)

    # ------------------------------------------------------------------
    # parametri equivalenti per la formula di Annex D
    # ------------------------------------------------------------------

    def equivalent_soil(self, D: float, B: float, depth_of_influence: float | None = None) -> Soil:
        """Costruisce un Soil "equivalente" per la formula Annex D in stratigrafia.

        Si media nei vari termini sulla profondità di influenza del cuneo di
        rottura sotto la base della fondazione. Il valore di default è B
        (estensione orizzontale ≈ 2B, profondità di interesse ≈ B).

        Strategia di media (semplice e robusta):
          - phi, c, cu : media pesata sugli spessori interessati;
          - gamma, gamma_sat : media pesata sugli spessori interessati
            (usata per i pesi di volume sotto la base);
          - E, nu      : media pesata sugli spessori (per cedimento elastico).

        I parametri "drained" e "water_depth" sono ereditati dal layer più
        rappresentativo (quello che contiene metà della zona di influenza).
        """
        if depth_of_influence is None:
            depth_of_influence = B
        z_top = D
        z_bot = D + depth_of_influence

        # raccolta dei contributi pesati
        total_w = 0.0
        acc = {"phi": 0.0, "c": 0.0, "cu": 0.0, "gamma": 0.0, "gamma_sat": 0.0, "E": 0.0, "nu": 0.0}
        cu_weight = 0.0
        E_weight = 0.0
        ref_layer = None  # per gli attributi non mediabili (drained, ecc.)

        for layer in self.layers:
            if layer.bottom <= z_top or layer.top >= z_bot:
                continue
            z1 = max(layer.top, z_top)
            z2 = min(layer.bottom, z_bot)
            w = z2 - z1
            if w <= 0:
                continue
            s = layer.soil
            total_w += w
            acc["phi"] += s.phi_k * w
            acc["c"] += s.c_k * w
            acc["gamma"] += s.gamma * w
            acc["gamma_sat"] += s.gamma_sat * w
            acc["nu"] += s.nu * w
            if s.cu_k is not None:
                acc["cu"] += s.cu_k * w
                cu_weight += w
            if s.E is not None:
                acc["E"] += s.E * w
                E_weight += w
            # strato che contiene il centro della zona di influenza
            if layer.contains((z_top + z_bot) / 2):
                ref_layer = layer

        if total_w == 0:
            raise ValueError(
                f"La zona di influenza ({z_top:.2f}-{z_bot:.2f} m) non interseca alcuno strato."
            )

        if ref_layer is None:
            ref_layer = self.layer_at(z_top)

        return Soil(
            phi_k=acc["phi"] / total_w,
            c_k=acc["c"] / total_w,
            cu_k=(acc["cu"] / cu_weight) if cu_weight > 0 else None,
            gamma=acc["gamma"] / total_w,
            gamma_sat=acc["gamma_sat"] / total_w,
            water_depth=None,  # gestita a parte dal SoilProfile
            drained=ref_layer.soil.drained,
            E=(acc["E"] / E_weight) if E_weight > 0 else None,
            nu=acc["nu"] / total_w,
            name=f"equivalent({z_top:.2f}-{z_bot:.2f})",
        )

    # ------------------------------------------------------------------
    # interfaccia con il calcolo del cedimento (multistrato Steinbrenner)
    # ------------------------------------------------------------------

    def layers_under(
        self, D: float, z_max: float | None = None
    ) -> list[tuple[float, float, SoilLayer]]:
        """Restituisce gli strati sotto il piano di posa fino a z_max (o ultimo strato)."""
        out = []
        for layer in self.layers:
            if layer.bottom <= D:
                continue
            z_top = max(layer.top, D)
            z_bot = layer.bottom if z_max is None else min(layer.bottom, z_max)
            if z_bot <= z_top:
                continue
            out.append((z_top, z_bot, layer))
            if z_max is not None and z_bot >= z_max:
                break
        return out
