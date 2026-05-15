"""Azioni di progetto sulla fondazione.

Convenzione assi:
  - x: parallelo a B (lato corto)
  - y: parallelo a L (lato lungo)
  - z: verticale verso l'alto

V       : forza verticale [kN] (positiva di compressione)
H_x,H_y : forze orizzontali [kN]
M_x,M_y : momenti [kN m] attorno agli assi x e y rispettivamente.
          Il momento M_x produce eccentricità lungo y -> e_L = M_x / V.
          Il momento M_y produce eccentricità lungo x -> e_B = M_y / V.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class DesignActions:
    """Sollecitazioni applicate alla base della fondazione.

    I valori passati sono già caratteristici per default; i fattori parziali
    sul lato delle azioni (set A) li applica la DesignCode quando richiesto.
    Se l'utente passa direttamente valori di progetto, può impostare
    `already_factored=True`.
    """

    V: float  # [kN]
    H_x: float = 0.0  # [kN]
    H_y: float = 0.0  # [kN]
    M_x: float = 0.0  # [kN m]  (intorno all'asse x -> eccentricità in y)
    M_y: float = 0.0  # [kN m]  (intorno all'asse y -> eccentricità in x)
    favorable: bool = False  # True se l'azione verticale è favorevole alla stabilità
    already_factored: bool = False

    def __post_init__(self):
        if self.V <= 0:
            raise ValueError("V deve essere positivo (compressione sulla fondazione).")

    @property
    def H_resultant(self) -> float:
        """Modulo della forza orizzontale risultante."""
        return math.hypot(self.H_x, self.H_y)

    def eccentricities(self) -> tuple[float, float]:
        """Eccentricità (e_B, e_L) della risultante rispetto al centro
        della fondazione. e_B è l'eccentricità lungo la direzione B (lato corto)."""
        if self.V == 0:
            return 0.0, 0.0
        e_B = self.M_y / self.V
        e_L = self.M_x / self.V
        return e_B, e_L

    def horizontal_angle_to_B(self) -> float:
        """Angolo (radianti) della risultante orizzontale rispetto all'asse B."""
        return math.atan2(self.H_y, self.H_x)
