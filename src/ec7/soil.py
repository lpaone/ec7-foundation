"""Modello di terreno per il calcolo della capacità portante.

I parametri si intendono caratteristici (suffisso _k). I valori di progetto
vengono calcolati al volo dalla classe DesignCode applicando i coefficienti
parziali del set M (M1 o M2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Soil:
    """Parametri caratteristici del terreno sotto la fondazione.

    Parametri
    ----------
    phi_k : float
        Angolo di resistenza al taglio efficace, in gradi.
    c_k : float
        Coesione efficace [kPa]. Per analisi drenata.
    cu_k : float, opzionale
        Resistenza al taglio non drenata [kPa]. Necessaria se drained=False.
    gamma : float
        Peso di volume sopra falda [kN/m^3].
    gamma_sat : float
        Peso di volume saturo [kN/m^3].
    water_depth : float, opzionale
        Profondità della falda rispetto al piano campagna [m].
        None = falda assente o molto profonda.
    drained : bool
        True per analisi drenata (c', phi'), False per non drenata (cu).
    E : float, opzionale
        Modulo elastico [kPa] per il calcolo dei cedimenti.
    nu : float
        Coefficiente di Poisson, default 0.3.
    """

    phi_k: float
    c_k: float
    gamma: float
    gamma_sat: float = 20.0
    cu_k: float | None = None
    water_depth: float | None = None
    drained: bool = True
    E: float | None = None
    nu: float = 0.3
    name: str = "Soil"

    def __post_init__(self):
        if self.phi_k < 0 or self.phi_k >= 50:
            raise ValueError(f"phi_k={self.phi_k}° fuori range plausibile (0-50).")
        if self.c_k < 0:
            raise ValueError("c_k deve essere >= 0.")
        if self.gamma <= 0 or self.gamma_sat <= 0:
            raise ValueError("I pesi di volume devono essere positivi.")
        if not self.drained and self.cu_k is None:
            raise ValueError("Analisi non drenata richiede cu_k.")
        if self.nu <= 0 or self.nu >= 0.5:
            raise ValueError("Coefficiente di Poisson deve essere in (0, 0.5).")

    @property
    def phi_k_rad(self) -> float:
        return math.radians(self.phi_k)

    def effective_unit_weight(self, depth: float) -> float:
        """Peso di volume efficace alla profondità data (sopra falda = gamma,
        sotto falda = gamma_sat - gamma_w)."""
        gamma_w = 9.81
        if self.water_depth is None or depth <= self.water_depth:
            return self.gamma
        return self.gamma_sat - gamma_w

    def overburden_at(self, depth: float) -> float:
        """Pressione efficace di sovraccarico al piano di posa [kPa].

        Calcolata in modo semplificato (terreno omogeneo) integrando il peso
        di volume efficace; se la falda è sopra il piano di posa, si tiene
        conto del peso saturo immerso.
        """
        if self.water_depth is None or depth <= self.water_depth:
            return self.gamma * depth
        # parte sopra falda + parte sotto falda immersa
        gamma_w = 9.81
        return self.gamma * self.water_depth + (self.gamma_sat - gamma_w) * (
            depth - self.water_depth
        )
