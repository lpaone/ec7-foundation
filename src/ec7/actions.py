"""Design actions on the footing.

Axis convention:
    - x: parallel to B (short side)
    - y: parallel to L (long side)
    - z: vertical, upward

V       : vertical force [kN] (positive in compression)
H_x,H_y : horizontal forces [kN]
M_x,M_y : moments [kN m] about the x and y axes respectively.
          M_x produces eccentricity along y -> e_L = M_x / V.
          M_y produces eccentricity along x -> e_B = M_y / V.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class DesignActions:
    """Loads applied at the base of the footing.

    Inputs are characteristic values by default; partial factors on the
    actions side (A set) are applied by the ``DesignCode`` when requested.
    If the user passes design values directly, set ``already_factored=True``.

    Attributes:
        V: Vertical force [kN].
        H_x: Horizontal force along x [kN].
        H_y: Horizontal force along y [kN].
        M_x: Moment about x [kN m] (produces eccentricity along y).
        M_y: Moment about y [kN m] (produces eccentricity along x).
        favorable: True if the vertical action is stabilising.
        already_factored: True if values are already design values.
    """

    V: float  # [kN]
    H_x: float = 0.0  # [kN]
    H_y: float = 0.0  # [kN]
    M_x: float = 0.0  # [kN m] (about x -> eccentricity along y)
    M_y: float = 0.0  # [kN m] (about y -> eccentricity along x)
    favorable: bool = False
    already_factored: bool = False

    def __post_init__(self):
        if self.V <= 0:
            raise ValueError("V must be positive (compression on the footing).")

    @property
    def H_resultant(self) -> float:
        """Magnitude of the resultant horizontal force [kN]."""
        return math.hypot(self.H_x, self.H_y)

    def eccentricities(self) -> tuple[float, float]:
        """Return ``(e_B, e_L)`` of the resultant relative to the footing centre.

        ``e_B`` is the eccentricity along direction B (short side).

        Returns:
            Tuple ``(e_B, e_L)`` in metres.
        """
        if self.V == 0:
            return 0.0, 0.0
        e_B = self.M_y / self.V
        e_L = self.M_x / self.V
        return e_B, e_L

    def horizontal_angle_to_B(self) -> float:
        """Return the angle (rad) of the horizontal resultant w.r.t. the B axis."""
        return math.atan2(self.H_y, self.H_x)
