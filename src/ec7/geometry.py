"""Geometrie di fondazione superficiale.

Gestisce il calcolo dell'area, dell'area efficace (Meyerhof) sotto carico
eccentrico, e delle dimensioni efficaci B' e L' usate nella formula di
capacità portante.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EffectiveGeometry:
    """Risultato del calcolo dell'area efficace."""

    B_eff: float  # larghezza efficace [m]
    L_eff: float  # lunghezza efficace [m]
    A_eff: float  # area efficace [m^2]


class Footing(ABC):
    """Classe astratta per una fondazione superficiale.

    Tutte le sottoclassi devono esporre:
      - `D`            : profondità del piano di posa [m]
      - `area`         : area lorda [m^2]
      - `perimeter`    : perimetro lordo [m]
      - `effective_geometry(e_B, e_L)` : restituisce B', L', A' con il
                                          metodo di Meyerhof.
      - `equivalent_BL`: tupla (B, L) equivalente, per fondazioni non
                         rettangolari serve a interpretare 'lato corto'
                         e 'lato lungo' nei fattori di forma.
    """

    def __init__(self, D: float, base_inclination: float = 0.0, ground_inclination: float = 0.0):
        if D < 0:
            raise ValueError("La profondità di posa D deve essere >= 0.")
        self.D = D
        # angoli in radianti, di solito 0
        self.alpha = math.radians(base_inclination)  # inclinazione della base
        self.beta = math.radians(ground_inclination)  # inclinazione del piano campagna

    @property
    @abstractmethod
    def area(self) -> float: ...

    @property
    @abstractmethod
    def perimeter(self) -> float: ...

    @property
    @abstractmethod
    def equivalent_BL(self) -> tuple[float, float]:
        """Restituisce (B, L) con B <= L per il calcolo dei fattori di forma."""

    @abstractmethod
    def effective_geometry(self, e_B: float, e_L: float) -> EffectiveGeometry: ...

    @property
    def shape_name(self) -> str:
        return type(self).__name__


class RectangularFooting(Footing):
    """Fondazione rettangolare di lati B (lato corto) e L (lato lungo)."""

    def __init__(
        self,
        B: float,
        L: float,
        D: float,
        base_inclination: float = 0.0,
        ground_inclination: float = 0.0,
    ):
        super().__init__(D, base_inclination, ground_inclination)
        if B <= 0 or L <= 0:
            raise ValueError("B e L devono essere positivi.")
        # convenzione: B è il lato corto
        if B > L:
            B, L = L, B
        self.B = B
        self.L = L

    @property
    def area(self) -> float:
        return self.B * self.L

    @property
    def perimeter(self) -> float:
        return 2 * (self.B + self.L)

    @property
    def equivalent_BL(self) -> tuple[float, float]:
        return self.B, self.L

    def effective_geometry(self, e_B: float, e_L: float) -> EffectiveGeometry:
        # Metodo di Meyerhof: si "riduce" la fondazione al rettangolo
        # centrato sulla risultante. EN 1997-1 §6.5.4.
        if abs(e_B) >= self.B / 2 or abs(e_L) >= self.L / 2:
            raise ValueError(
                f"Eccentricità fuori dal nocciolo della fondazione: "
                f"e_B={e_B:.3f} (B/2={self.B / 2:.3f}), "
                f"e_L={e_L:.3f} (L/2={self.L / 2:.3f}). "
                "La risultante esce dalla base, verifica geometricamente non eseguibile."
            )
        B_eff = self.B - 2 * abs(e_B)
        L_eff = self.L - 2 * abs(e_L)
        return EffectiveGeometry(B_eff=B_eff, L_eff=L_eff, A_eff=B_eff * L_eff)


class StripFooting(RectangularFooting):
    """Fondazione nastriforme: B finito, L convenzionalmente molto grande.

    Nei fattori di forma si avranno sq = sgamma = sc = 1.
    """

    def __init__(
        self,
        B: float,
        D: float,
        base_inclination: float = 0.0,
        ground_inclination: float = 0.0,
        L_ref: float = 1.0,
    ):
        # L_ref è una lunghezza di riferimento per unità di nastro;
        # i risultati di forza saranno in kN per metro di nastro.
        super().__init__(
            B=B,
            L=max(B * 1e3, 1e3),
            D=D,
            base_inclination=base_inclination,
            ground_inclination=ground_inclination,
        )
        self._L_ref = L_ref

    @property
    def is_strip(self) -> bool:
        return True


class CircularFooting(Footing):
    """Fondazione circolare di raggio R.

    Per la verifica si usa una rettangolare equivalente di area uguale
    al settore residuo sotto eccentricità (approccio EN 1997-1 §6.5.4
    e Bowles): area efficace = 2 * (R^2 * arccos(e/R) - e * sqrt(R^2-e^2)),
    quindi B' = L' = sqrt(A_eff).
    """

    def __init__(
        self, R: float, D: float, base_inclination: float = 0.0, ground_inclination: float = 0.0
    ):
        super().__init__(D, base_inclination, ground_inclination)
        if R <= 0:
            raise ValueError("R deve essere positivo.")
        self.R = R

    @property
    def area(self) -> float:
        return math.pi * self.R**2

    @property
    def perimeter(self) -> float:
        return 2 * math.pi * self.R

    @property
    def equivalent_BL(self) -> tuple[float, float]:
        # diametro come B e L per i fattori di forma (s ≈ caso quadrato)
        d = 2 * self.R
        return d, d

    def effective_geometry(self, e_B: float, e_L: float) -> EffectiveGeometry:
        # eccentricità risultante
        e = math.hypot(e_B, e_L)
        if e >= self.R:
            raise ValueError(
                f"Eccentricità risultante {e:.3f} >= R={self.R:.3f}: risultante fuori dalla base."
            )
        R = self.R
        A_eff = 2 * (R**2 * math.acos(e / R) - e * math.sqrt(R**2 - e**2))
        # rettangolo equivalente di lati uguali
        side = math.sqrt(A_eff)
        return EffectiveGeometry(B_eff=side, L_eff=side, A_eff=A_eff)
