"""Soil model used by the bearing-capacity computation.

Parameters are characteristic values (suffix ``_k``). Design values are
computed on the fly by ``DesignCode`` applying the partial factors of
the M set (M1 or M2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Soil:
    """Characteristic soil parameters below the footing.

    Attributes:
        phi_k: Effective angle of shearing resistance [deg].
        c_k: Effective cohesion [kPa]. For drained analysis.
        cu_k: Undrained shear strength [kPa]. Required when ``drained=False``.
        gamma: Unit weight above the water table [kN/m^3].
        gamma_sat: Saturated unit weight [kN/m^3].
        water_depth: Water-table depth from ground surface [m]. None means
            no groundwater or very deep.
        drained: True for drained analysis (c', phi'), False for undrained (cu).
        E: Young's modulus [kPa] for settlement computation.
        nu: Poisson's ratio (default 0.3).
        name: Optional label.
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
            raise ValueError(f"phi_k={self.phi_k}° outside plausible range (0-50).")
        if self.c_k < 0:
            raise ValueError("c_k must be >= 0.")
        if self.gamma <= 0 or self.gamma_sat <= 0:
            raise ValueError("Unit weights must be positive.")
        if not self.drained and self.cu_k is None:
            raise ValueError("Undrained analysis requires cu_k.")
        if self.nu <= 0 or self.nu >= 0.5:
            raise ValueError("Poisson's ratio must be in (0, 0.5).")

    @property
    def phi_k_rad(self) -> float:
        return math.radians(self.phi_k)

    def effective_unit_weight(self, depth: float) -> float:
        """Return the effective unit weight at the given depth.

        Uses gamma above the water table and gamma_sat - gamma_w below it.

        Args:
            depth: Depth from ground surface [m].

        Returns:
            Effective unit weight [kN/m^3].
        """
        gamma_w = 9.81
        if self.water_depth is None or depth <= self.water_depth:
            return self.gamma
        return self.gamma_sat - gamma_w

    def overburden_at(self, depth: float) -> float:
        """Return the effective overburden pressure at the footing base [kPa].

        Computed assuming a homogeneous soil by integrating the effective
        unit weight; when the water table is above the base, the submerged
        weight is accounted for.

        Args:
            depth: Embedment depth from ground surface [m].

        Returns:
            Effective overburden pressure [kPa].
        """
        if self.water_depth is None or depth <= self.water_depth:
            return self.gamma * depth
        # portion above the water table + portion below (submerged)
        gamma_w = 9.81
        return self.gamma * self.water_depth + (self.gamma_sat - gamma_w) * (
            depth - self.water_depth
        )
