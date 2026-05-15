"""Design-code strategy: applies partial factors to actions, geotechnical
parameters and resistances according to the selected approach.

Implemented:
    - EC7 (EN 1997-1) Design Approach 1, Combination 1 -> EC7_DA1_C1
    - EC7 Design Approach 1, Combination 2             -> EC7_DA1_C2
    - EC7 Design Approach 2                            -> EC7_DA2
    - EC7 Design Approach 3                            -> EC7_DA3
    - NTC 2018 Approach 1, Combination 1 (A1+M1+R1)    -> NTC2018_A1 (bearing capacity)
    - NTC 2018 Approach 2 (A1+M1+R3)                   -> NTC2018_A2 (bearing capacity)

Factor references:
    EC7   : Annex A
    NTC 18: Tab. 6.2.I (A), 6.2.II (M), 6.4.I (R for shallow foundations)
"""

from __future__ import annotations

import math
from abc import ABC
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .actions import DesignActions
    from .soil import Soil


# ---------------------------------------------------------------------------
# Partial-factor sets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PartialFactorsActions:
    """Set A: factors on actions (favourable/unfavourable)."""

    gamma_G_unfav: float = 1.35
    gamma_G_fav: float = 1.00
    gamma_Q_unfav: float = 1.50
    gamma_Q_fav: float = 0.00


@dataclass(frozen=True)
class PartialFactorsMaterials:
    """Set M: factors on geotechnical parameters."""

    gamma_phi: float = 1.00  # on tan(phi')
    gamma_c: float = 1.00  # on c'
    gamma_cu: float = 1.00  # on cu
    gamma_gamma: float = 1.00  # on unit weight (always 1 in NTC)


@dataclass(frozen=True)
class PartialFactorsResistance:
    """Set R: factors on resistances (bearing capacity, sliding, overturning)."""

    gamma_Rv: float = 1.00  # vertical bearing capacity
    gamma_Rh: float = 1.00  # sliding
    gamma_Re: float = 1.00  # overturning (resistance)


# ---------------------------------------------------------------------------
# Strategy base class
# ---------------------------------------------------------------------------


class DesignCode(ABC):
    """Calculation strategy: holds the three sets of partial factors and the
    methods to apply them.

    Subclasses are simple dataclasses with the factor values for the chosen
    approach. The application logic is the same.
    """

    name: str = "DesignCode"
    A: PartialFactorsActions
    M: PartialFactorsMaterials
    R: PartialFactorsResistance

    # ---- application to soil parameters ------------------------------------

    def design_soil(self, soil: Soil) -> Soil:
        """Return a copy of the soil with design parameters.

        Args:
            soil: Characteristic soil.

        Returns:
            A new ``Soil`` with phi, c, cu and unit weights reduced by the
            partial factors of the M set.
        """
        phi_d_rad = math.atan(math.tan(soil.phi_k_rad) / self.M.gamma_phi)
        phi_d_deg = math.degrees(phi_d_rad)
        c_d = soil.c_k / self.M.gamma_c
        cu_d = soil.cu_k / self.M.gamma_cu if soil.cu_k is not None else None
        # unit weight: gamma_M = 1 in all practical cases, kept for completeness
        return replace(
            soil,
            phi_k=phi_d_deg,
            c_k=c_d,
            cu_k=cu_d,
            gamma=soil.gamma / self.M.gamma_gamma,
            gamma_sat=soil.gamma_sat / self.M.gamma_gamma,
        )

    # ---- application to actions --------------------------------------------

    def design_actions(self, actions: DesignActions, Q_fraction: float = 0.0) -> DesignActions:
        """Apply the A-set factors to the actions.

        Args:
            actions: Characteristic actions.
            Q_fraction: Fraction (0-1) of the total action due to variable
                loads. 0 assumes fully permanent; 1 assumes fully variable.
                For horizontal loads and moments the same averaged
                coefficient of V is applied (common simplification).

        Returns:
            New ``DesignActions`` with factored components and
            ``already_factored=True``.

        Raises:
            ValueError: If ``Q_fraction`` is outside ``[0, 1]``.
        """
        if actions.already_factored:
            return actions

        if not 0.0 <= Q_fraction <= 1.0:
            raise ValueError("Q_fraction must be in [0, 1].")

        if actions.favorable:
            g = self.A.gamma_G_fav
            q = self.A.gamma_Q_fav
        else:
            g = self.A.gamma_G_unfav
            q = self.A.gamma_Q_unfav

        # weighted "average" coefficient based on the variable-load fraction
        gamma_eff = g * (1 - Q_fraction) + q * Q_fraction

        from .actions import DesignActions as _DA

        return _DA(
            V=actions.V * gamma_eff,
            H_x=actions.H_x * gamma_eff,
            H_y=actions.H_y * gamma_eff,
            M_x=actions.M_x * gamma_eff,
            M_y=actions.M_y * gamma_eff,
            favorable=actions.favorable,
            already_factored=True,
        )

    # ---- application to resistances ----------------------------------------

    def design_bearing_resistance(self, R_k: float) -> float:
        return R_k / self.R.gamma_Rv

    def design_sliding_resistance(self, R_h_k: float) -> float:
        return R_h_k / self.R.gamma_Rh

    def design_overturning_resistance(self, M_stab_k: float) -> float:
        return M_stab_k / self.R.gamma_Re

    def __repr__(self):
        return f"<{self.name}>"


# ---------------------------------------------------------------------------
# EC7 - EN 1997-1 (Annex A, recommended sets)
# ---------------------------------------------------------------------------


class EC7_DA1_C1(DesignCode):
    """Design Approach 1, Combination 1: A1 + M1 + R1."""

    name = "EC7 DA1-C1 (A1+M1+R1)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.35, gamma_G_fav=1.00, gamma_Q_unfav=1.50, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()  # all 1.0
    R = PartialFactorsResistance(gamma_Rv=1.0, gamma_Rh=1.0, gamma_Re=1.0)


class EC7_DA1_C2(DesignCode):
    """Design Approach 1, Combination 2: A2 + M2 + R1."""

    name = "EC7 DA1-C2 (A2+M2+R1)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.30, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials(gamma_phi=1.25, gamma_c=1.25, gamma_cu=1.40)
    R = PartialFactorsResistance(gamma_Rv=1.0, gamma_Rh=1.0, gamma_Re=1.0)


class EC7_DA2(DesignCode):
    """Design Approach 2: A1 + M1 + R2 (recommended by EN for shallow foundations)."""

    name = "EC7 DA2 (A1+M1+R2)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.35, gamma_G_fav=1.00, gamma_Q_unfav=1.50, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=1.4, gamma_Rh=1.1, gamma_Re=1.4)


class EC7_DA3(DesignCode):
    """Design Approach 3: (A1*/A2) + M2 + R3.

    Geotechnical actions A2 are assumed here (the structural side would use
    A1). For a "pure" shallow foundation use A2.
    """

    name = "EC7 DA3 (A2+M2+R3)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.30, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials(gamma_phi=1.25, gamma_c=1.25, gamma_cu=1.40)
    R = PartialFactorsResistance(gamma_Rv=1.0, gamma_Rh=1.0, gamma_Re=1.0)


# ---------------------------------------------------------------------------
# NTC 2018 - Tab. 6.2.I, 6.2.II, 6.4.I
# ---------------------------------------------------------------------------


class NTC2018_A1(DesignCode):
    """NTC 2018 Approach 1, Comb. 1: (A1+M1+R1).

    For shallow foundations NTC recommends Approach 2; A1 is used for the
    structural design of the footing itself.
    """

    name = "NTC 2018 Approccio 1 Comb.1 (A1+M1+R1)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.30, gamma_G_fav=1.00, gamma_Q_unfav=1.50, gamma_Q_fav=0.0
    )
    # note: gamma_G1 = 1.30 (structural perm.) for geotechnics - see 6.2.I
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=1.0, gamma_Rh=1.0, gamma_Re=1.0)


class NTC2018_A2(DesignCode):
    """NTC 2018 Approach 2: (A1+M1+R3).

    Reference approach for shallow foundations per NTC 2018 (Tab. 6.4.I):
    gamma_R = 2.3 for bearing capacity, 1.1 for sliding.
    """

    name = "NTC 2018 Approccio 2 (A1+M1+R3)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.30, gamma_G_fav=1.00, gamma_Q_unfav=1.50, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=2.3, gamma_Rh=1.1, gamma_Re=1.0)


# ---------------------------------------------------------------------------
# SEISMIC COMBINATIONS
# ---------------------------------------------------------------------------
# In seismic conditions, NTC 2018 §7.11 prescribes:
#   - unit partial factors on actions (the seismic action is already
#     "characteristic" based on hazard; permanent G and Q enter the
#     combination with their psi coefficients)
#   - unit partial factors on geotechnical parameters (M1)
#   - reduced resistance factors compared to static:
#     gamma_R = 2.3 nominally, reducible to 1.8 if the inertial effects on
#     the failure wedge are explicitly accounted for (i.e. SeismicAction
#     with kh > 0 is used in the computation).


class NTC2018_Seismic(DesignCode):
    """NTC 2018 - Seismic combination, bearing capacity with γR = 2.3.

    Use with ``SeismicAction`` to also account for inertial effects on the
    wedge (Paolucci & Pecker), while keeping the "standard" partial factor
    2.3. For the 1.8 bonus use ``NTC2018_Seismic_Reduced``.
    """

    name = "NTC 2018 Sismica (gamma_R = 2.3)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.00, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=2.3, gamma_Rh=1.1, gamma_Re=1.0)


class NTC2018_Seismic_Reduced(DesignCode):
    """NTC 2018 - Seismic combination with γR reduced to 1.8.

    Applicable *only* if the ultimate-load computation explicitly accounts
    for the inertial effects on the significant soil volume (i.e. a
    ``SeismicAction`` with kh > 0 has been passed and the Paolucci & Pecker
    z-factors are used). Reference: NTC 2018 §7.11.5.3.1.
    """

    name = "NTC 2018 Sismica con effetti inerziali (gamma_R = 1.8)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.00, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=1.8, gamma_Rh=1.1, gamma_Re=1.0)


class EC7_Seismic_DA2(DesignCode):
    """EN 1997-1 / EN 1998-5 - Seismic combination with the DA2 approach.

    Recommended factors: A = 1.0 (seismic actions), M = 1.0, R similar to
    DA2. National Annexes may differ; this is the base formulation.
    """

    name = "EC7+EC8 Sismica DA2 (gamma_R = 1.4)"
    A = PartialFactorsActions(
        gamma_G_unfav=1.00, gamma_G_fav=1.00, gamma_Q_unfav=1.00, gamma_Q_fav=0.0
    )
    M = PartialFactorsMaterials()
    R = PartialFactorsResistance(gamma_Rv=1.4, gamma_Rh=1.1, gamma_Re=1.0)
