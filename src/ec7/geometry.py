"""Shallow-foundation geometries.

Handles area, Meyerhof effective area under eccentric loading, and the
effective dimensions B' and L' used in the bearing-capacity formula.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EffectiveGeometry:
    """Result of the effective-area computation."""

    B_eff: float  # effective width [m]
    L_eff: float  # effective length [m]
    A_eff: float  # effective area [m^2]


class Footing(ABC):
    """Abstract base class for a shallow footing.

    Subclasses must expose:
        - ``D``: embedment depth [m]
        - ``area``: gross area [m^2]
        - ``perimeter``: gross perimeter [m]
        - ``effective_geometry(e_B, e_L)``: B', L', A' via Meyerhof's method
        - ``equivalent_BL``: ``(B, L)`` tuple used by shape factors to
          interpret "short" and "long" sides for non-rectangular footings.
    """

    def __init__(self, D: float, base_inclination: float = 0.0, ground_inclination: float = 0.0):
        if D < 0:
            raise ValueError("Embedment depth D must be >= 0.")
        self.D = D
        # angles in radians, usually 0
        self.alpha = math.radians(base_inclination)  # base inclination
        self.beta = math.radians(ground_inclination)  # ground-surface inclination

    @property
    @abstractmethod
    def area(self) -> float: ...

    @property
    @abstractmethod
    def perimeter(self) -> float: ...

    @property
    @abstractmethod
    def equivalent_BL(self) -> tuple[float, float]:
        """Return ``(B, L)`` with B <= L for shape-factor computations."""

    @abstractmethod
    def effective_geometry(self, e_B: float, e_L: float) -> EffectiveGeometry: ...

    @property
    def shape_name(self) -> str:
        return type(self).__name__


class RectangularFooting(Footing):
    """Rectangular footing of sides B (short) and L (long)."""

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
            raise ValueError("B and L must be positive.")
        # convention: B is the short side
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
        # Meyerhof's method: the footing is "reduced" to the rectangle
        # centered on the load resultant. EN 1997-1 §6.5.4.
        if abs(e_B) >= self.B / 2 or abs(e_L) >= self.L / 2:
            raise ValueError(
                f"Eccentricity outside the footing core: "
                f"e_B={e_B:.3f} (B/2={self.B / 2:.3f}), "
                f"e_L={e_L:.3f} (L/2={self.L / 2:.3f}). "
                "Resultant falls outside the base, verification not feasible."
            )
        B_eff = self.B - 2 * abs(e_B)
        L_eff = self.L - 2 * abs(e_L)
        return EffectiveGeometry(B_eff=B_eff, L_eff=L_eff, A_eff=B_eff * L_eff)


class StripFooting(RectangularFooting):
    """Strip footing: finite B, conventionally very large L.

    Yields sq = sgamma = sc = 1 in the shape factors.
    """

    def __init__(
        self,
        B: float,
        D: float,
        base_inclination: float = 0.0,
        ground_inclination: float = 0.0,
        L_ref: float = 1.0,
    ):
        # L_ref is a reference length per unit of strip; force results are
        # in kN per metre of strip.
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
    """Circular footing of radius R.

    Verification uses an equivalent rectangle whose area equals the
    residual sector under eccentricity (EN 1997-1 §6.5.4, Bowles):
    ``A_eff = 2 * (R^2 * arccos(e/R) - e * sqrt(R^2-e^2))``,
    so ``B' = L' = sqrt(A_eff)``.
    """

    def __init__(
        self, R: float, D: float, base_inclination: float = 0.0, ground_inclination: float = 0.0
    ):
        super().__init__(D, base_inclination, ground_inclination)
        if R <= 0:
            raise ValueError("R must be positive.")
        self.R = R

    @property
    def area(self) -> float:
        return math.pi * self.R**2

    @property
    def perimeter(self) -> float:
        return 2 * math.pi * self.R

    @property
    def equivalent_BL(self) -> tuple[float, float]:
        # diameter as B and L for shape factors (s ≈ square case)
        d = 2 * self.R
        return d, d

    def effective_geometry(self, e_B: float, e_L: float) -> EffectiveGeometry:
        # resultant eccentricity
        e = math.hypot(e_B, e_L)
        if e >= self.R:
            raise ValueError(
                f"Resultant eccentricity {e:.3f} >= R={self.R:.3f}: resultant outside the base."
            )
        R = self.R
        A_eff = 2 * (R**2 * math.acos(e / R) - e * math.sqrt(R**2 - e**2))
        # equivalent square rectangle
        side = math.sqrt(A_eff)
        return EffectiveGeometry(B_eff=side, L_eff=side, A_eff=A_eff)
