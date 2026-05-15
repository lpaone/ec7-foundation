"""Layered soil profile.

Handles:
    - multiple soil layers with top/bottom elevations
    - groundwater at a given depth
    - total and effective overburden pressure at any depth
    - weighted equivalent parameters over the failure-wedge influence
      volume (~B below the footing base) so that Annex D applies to
      layered profiles.

Convention: depth z increases downward, z=0 at ground surface.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .soil import Soil

GAMMA_W = 9.81  # kN/m^3


@dataclass
class SoilLayer:
    """Single layer of the soil profile.

    Attributes:
        top: Elevation of the layer top [m] (z=0 ground surface, positive
            downward).
        bottom: Bottom elevation [m]. The last layer may use float('inf').
        soil: Soil parameters (characteristic).
    """

    top: float
    bottom: float
    soil: Soil

    def __post_init__(self):
        if self.bottom <= self.top:
            raise ValueError(
                f"Layer '{self.soil.name}': bottom ({self.bottom}) must be > top ({self.top})."
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
    """Layered soil profile with optional groundwater.

    Attributes:
        layers: Layers listed top-down. Must be contiguous.
        water_depth: Groundwater depth from ground surface [m]. None means
            no groundwater.
    """

    layers: list[SoilLayer]
    water_depth: float | None = None

    def __post_init__(self):
        if not self.layers:
            raise ValueError("SoilProfile requires at least one layer.")
        # contiguity check
        for prev, curr in zip(self.layers[:-1], self.layers[1:], strict=False):
            if not math.isclose(prev.bottom, curr.top, abs_tol=1e-6):
                raise ValueError(f"Non-contiguous layers: bottom={prev.bottom} != top={curr.top}")
        if self.layers[0].top != 0.0:
            raise ValueError(f"First layer must start at z=0, found {self.layers[0].top}.")

    # ------------------------------------------------------------------
    # accessors
    # ------------------------------------------------------------------

    def layer_at(self, z: float) -> SoilLayer:
        """Return the layer containing depth z.

        For z below the last layer, returns the last layer (assumed
        infinite).

        Args:
            z: Depth [m].

        Returns:
            The layer that contains z.
        """
        for layer in self.layers:
            if layer.contains(z):
                return layer
        return self.layers[-1]

    def is_below_water(self, z: float) -> bool:
        return self.water_depth is not None and z > self.water_depth

    def unit_weight_at(self, z: float) -> float:
        """Return the *total* unit weight at depth z [kN/m^3]."""
        layer = self.layer_at(z)
        return layer.soil.gamma_sat if self.is_below_water(z) else layer.soil.gamma

    def effective_unit_weight_at(self, z: float) -> float:
        """Return the *effective* unit weight at depth z.

        Uses gamma above the water table and gamma_sat - gamma_w below it.
        """
        layer = self.layer_at(z)
        if self.is_below_water(z):
            return layer.soil.gamma_sat - GAMMA_W
        return layer.soil.gamma

    # ------------------------------------------------------------------
    # overburden stresses
    # ------------------------------------------------------------------

    def total_overburden_at(self, z: float) -> float:
        """Return total vertical pressure (sigma_v) at depth z [kPa]."""
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
        """Return effective vertical pressure (sigma'_v) at depth z [kPa]."""
        sigma_v = self.total_overburden_at(z)
        u = max(0.0, (z - self.water_depth) * GAMMA_W) if self.water_depth is not None else 0.0
        return sigma_v - u

    def _weighted_total(self, z1: float, z2: float, layer: SoilLayer) -> float:
        """Integral of total unit weight between z1 and z2 within the layer.

        Splits the interval when the water table crosses it.
        """
        g = layer.soil.gamma
        gs = layer.soil.gamma_sat
        wd = self.water_depth
        if wd is None or z2 <= wd:
            return g * (z2 - z1)
        if z1 >= wd:
            return gs * (z2 - z1)
        # water table inside the interval
        return g * (wd - z1) + gs * (z2 - wd)

    # ------------------------------------------------------------------
    # equivalent parameters for the Annex D formula
    # ------------------------------------------------------------------

    def equivalent_soil(self, D: float, B: float, depth_of_influence: float | None = None) -> Soil:
        """Build an equivalent ``Soil`` for the Annex D formula on layered profiles.

        Averages parameters over the failure-wedge influence depth below the
        footing base. Default influence depth is B (horizontal extent ~2B,
        vertical interest ~B).

        Averaging strategy (simple and robust):
            - phi, c, cu: thickness-weighted average over the intersected layers
            - gamma, gamma_sat: thickness-weighted average (used for unit
              weights below the base)
            - E, nu: thickness-weighted average (for elastic settlement)

        Non-averageable attributes (``drained``, ...) are inherited from the
        layer containing the midpoint of the influence zone.

        Args:
            D: Footing embedment depth [m].
            B: Footing short-side width [m].
            depth_of_influence: Depth below the base to average over [m].
                Defaults to B.

        Returns:
            A new ``Soil`` whose parameters are averages over the influence zone.

        Raises:
            ValueError: If the influence zone does not intersect any layer.
        """
        if depth_of_influence is None:
            depth_of_influence = B
        z_top = D
        z_bot = D + depth_of_influence

        # collect weighted contributions
        total_w = 0.0
        acc = {"phi": 0.0, "c": 0.0, "cu": 0.0, "gamma": 0.0, "gamma_sat": 0.0, "E": 0.0, "nu": 0.0}
        cu_weight = 0.0
        E_weight = 0.0
        ref_layer = None  # for non-averageable attributes (drained, ...)

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
            # layer that contains the midpoint of the influence zone
            if layer.contains((z_top + z_bot) / 2):
                ref_layer = layer

        if total_w == 0:
            raise ValueError(
                f"Influence zone ({z_top:.2f}-{z_bot:.2f} m) does not intersect any layer."
            )

        if ref_layer is None:
            ref_layer = self.layer_at(z_top)

        return Soil(
            phi_k=acc["phi"] / total_w,
            c_k=acc["c"] / total_w,
            cu_k=(acc["cu"] / cu_weight) if cu_weight > 0 else None,
            gamma=acc["gamma"] / total_w,
            gamma_sat=acc["gamma_sat"] / total_w,
            water_depth=None,  # handled separately by SoilProfile
            drained=ref_layer.soil.drained,
            E=(acc["E"] / E_weight) if E_weight > 0 else None,
            nu=acc["nu"] / total_w,
            name=f"equivalent({z_top:.2f}-{z_bot:.2f})",
        )

    # ------------------------------------------------------------------
    # interface to the multilayer Steinbrenner settlement computation
    # ------------------------------------------------------------------

    def layers_under(
        self, D: float, z_max: float | None = None
    ) -> list[tuple[float, float, SoilLayer]]:
        """Return the layers below the footing base up to z_max.

        Args:
            D: Footing embedment depth [m].
            z_max: Maximum integration depth [m]. Defaults to the last layer.

        Returns:
            List of ``(z_top, z_bottom, layer)`` triples covering the
            depth range under the base.
        """
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
