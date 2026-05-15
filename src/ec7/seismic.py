"""Seismic effects on bearing capacity.

Two distinct effects must be combined:

1) INERTIAL EFFECT ON THE SUPERSTRUCTURE: produces additional H and M on
   the footing. It is captured by the inclination factors i_c, i_q,
   i_gamma already present in the Annex D formula, computed with
   H_d = H_grav + H_sis. Handled upstream by passing the seismic
   contributions as components of ``DesignActions``.

2) INERTIAL EFFECT ON THE FAILURE WEDGE (soil "kinematic" effect): the
   inertial accelerations on the soil mass below the footing reduce the
   bearing capacity. Modelled via correction factors z_c, z_q, z_gamma
   that multiply the three terms of the formula.

Implementation follows Paolucci & Pecker (1997), the most common
formulation in Italian practice and cited in the NTC 2018 circular:

    z_q     = (1 - kh / tan(phi)) ^ 0.35
    z_gamma = (1 - kh / tan(phi)) ^ 0.35    (Pecker; some authors use 0.45)
    z_c     = 1 - 0.32 * kh                 (simplified formulation)

where kh is the horizontal seismic coefficient (= beta * a_max/g per
NTC 2018).

kv (vertical) is applied as a modification of the unit weight:
    gamma' -> gamma' * (1 ± kv)

References:
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
    """Seismic coefficients for the bearing-capacity check.

    Attributes:
        kh: Horizontal seismic coefficient, dimensionless.
            Per NTC 2018: kh = beta_m * a_max / g, where a_max = S * ag
            and beta_m is the reduction coefficient (Tab. 7.11.II).
        kv: Vertical seismic coefficient. Conventionally kv = ±0.5 * kh;
            the sign yielding the most unfavourable effect is used.
            Default 0 (neglected; conservative on the resistance side
            when kv points upward, safe-side for stabilising load).
        method: Method used to compute the correction factors. Only
            ``'paolucci_pecker'`` is implemented; extensible for
            Maugeri/Richards.
    """

    kh: float
    kv: float = 0.0
    method: str = "paolucci_pecker"

    def __post_init__(self):
        if self.kh < 0 or self.kh > 0.5:
            raise ValueError(f"kh={self.kh} outside plausible range [0, 0.5].")
        if abs(self.kv) > 0.5:
            raise ValueError(f"kv={self.kv} outside plausible range [-0.5, 0.5].")
        if self.method not in ("paolucci_pecker",):
            raise ValueError(f"Unknown seismic method: {self.method}")

    @property
    def is_seismic(self) -> bool:
        return self.kh > 0 or self.kv != 0

    # ------------------------------------------------------------------
    # correction factors z (inertial effect on the wedge)
    # ------------------------------------------------------------------

    def seismic_factors(self, phi_rad: float, drained: bool = True) -> tuple[float, float, float]:
        """Return ``(z_c, z_q, z_gamma)`` per Paolucci & Pecker.

        For undrained analysis the dedicated formulation for z_c is used.

        Args:
            phi_rad: Friction angle [rad]; ignored when ``drained=False``.
            drained: True for drained analysis, False for undrained.

        Returns:
            Tuple ``(z_c, z_q, z_gamma)``.
        """
        if self.kh == 0:
            return 1.0, 1.0, 1.0

        if not drained:
            # undrained conditions (Paolucci 1997, cohesive soils)
            # z_c = 1 - 0.32 * kh (clipped at >= 0)
            z_c = max(0.0, 1.0 - 0.32 * self.kh)
            return z_c, 1.0, 1.0

        # drained conditions
        tan_phi = math.tan(phi_rad)
        if tan_phi < 1e-6:
            return 1.0, 1.0, 1.0
        arg = 1 - self.kh / tan_phi
        if arg <= 0:
            # zero capacity: the soil slides
            return 0.0, 0.0, 0.0
        z_q = arg**0.35
        z_gamma = arg**0.35
        # z_c proposed in Paolucci-Pecker for c'>0 (per NTC it's customary
        # to assume z_c = z_q)
        z_c = z_q
        return z_c, z_q, z_gamma

    def gamma_modifier(self, sign: str = "down") -> float:
        """Return the unit-weight modifier accounting for kv.

        Args:
            sign: ``'down'`` applies ``(1 + kv)``, ``'up'`` applies ``(1 - kv)``.
                Pick the most unfavourable case.

        Returns:
            Multiplicative factor on the unit weight.

        Raises:
            ValueError: If ``sign`` is not ``'down'`` or ``'up'``.
        """
        if sign == "down":
            return 1.0 + self.kv
        if sign == "up":
            return 1.0 - self.kv
        raise ValueError(f"sign must be 'down' or 'up', got: {sign}")
