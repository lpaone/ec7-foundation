"""Verification classes: bearing capacity, sliding, overturning, settlement.

Each check is a callable object that, given
``(footing, soil, actions, code)``, returns a ``Result``.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from .bearing import compute_bearing_capacity
from .results import (
    BearingResult,
    OverturningResult,
    SettlementResult,
    SlidingResult,
)

if TYPE_CHECKING:
    from .actions import DesignActions
    from .code import DesignCode
    from .geometry import Footing
    from .profile import SoilProfile
    from .seismic import SeismicAction
    from .soil import Soil


def _design_profile(profile: SoilProfile, code) -> SoilProfile:
    """Return a copy of the profile with design parameters in every layer."""
    from .profile import SoilLayer, SoilProfile

    new_layers = []
    for layer in profile.layers:
        new_layers.append(
            SoilLayer(
                top=layer.top,
                bottom=layer.bottom,
                soil=code.design_soil(layer.soil),
            )
        )
    return SoilProfile(layers=new_layers, water_depth=profile.water_depth)


class Check(ABC):
    @abstractmethod
    def run(self, footing: Footing, soil: Soil, actions: DesignActions, code: DesignCode): ...


class BearingCheck(Check):
    """Bearing-capacity verification (SLU/GEO).

    Steps:
        1. Transform soil and actions into design values via ``code``.
        2. If a layered ``profile`` is provided, derive an equivalent
           ``Soil`` over the influence volume and use ``profile`` for the
           q' computation at the footing base (handling multilayer water
           correctly).
        3. If ``seismic`` is provided, apply Paolucci & Pecker factors and
           the kv effect on unit weight.
        4. Compute R_k via Annex D.
        5. R_d = R_k / gamma_Rv.
        6. Compare to V_d.
    """

    def __init__(
        self,
        Q_fraction: float = 0.0,
        profile: SoilProfile | None = None,
        seismic: SeismicAction | None = None,
        depth_of_influence: float | None = None,
    ):
        self.Q_fraction = Q_fraction
        self.profile = profile
        self.seismic = seismic
        self.depth_of_influence = depth_of_influence

    def run(self, footing, soil, actions, code) -> BearingResult:
        # if a profile is provided, derive the equivalent Soil from it
        if self.profile is not None:
            B_ref = footing.equivalent_BL[0]  # short side
            zoi = self.depth_of_influence if self.depth_of_influence else B_ref
            soil_eq = self.profile.equivalent_soil(footing.D, B_ref, zoi)
            soil_d = code.design_soil(soil_eq)
            profile_d = _design_profile(self.profile, code)
        else:
            soil_d = code.design_soil(soil)
            profile_d = None

        actions_d = code.design_actions(actions, self.Q_fraction)

        comp = compute_bearing_capacity(
            footing, soil_d, actions_d, profile=profile_d, seismic=self.seismic
        )
        R_d = code.design_bearing_resistance(comp.R_k)
        e_B, e_L = actions_d.eccentricities()

        return BearingResult(
            E_d=actions_d.V,
            R_d=R_d,
            R_k=comp.R_k,
            q_ult=comp.q_ult,
            A_eff=comp.A_eff,
            B_eff=comp.B_eff,
            L_eff=comp.L_eff,
            factors=comp.factors,
            e_B=e_B,
            e_L=e_L,
        )


class SlidingCheck(Check):
    """Sliding check on the base (SLU).

    Drained:    R_h_k = V * tan(delta) + c_a * A'
    Undrained:  R_h_k = A' * cu

    ``delta`` is the base/soil friction angle; default ``delta = phi``
    (cast-in-place concrete) per EN 1997-1 §6.5.3(10). For precast or
    smoothed concrete it can be reduced to ``delta = 2/3 phi``.

    If ``profile`` is provided, parameters come from the layer in contact
    with the base. If ``seismic`` is provided, V is reduced by upward kv.
    """

    def __init__(
        self,
        delta_over_phi: float = 1.0,
        c_adhesion: float = 0.0,
        Q_fraction: float = 0.0,
        include_passive: bool = False,
        profile: SoilProfile | None = None,
        seismic: SeismicAction | None = None,
    ):
        if not 0 < delta_over_phi <= 1:
            raise ValueError("delta_over_phi must be in (0, 1].")
        self.delta_over_phi = delta_over_phi
        self.c_adhesion = c_adhesion
        self.Q_fraction = Q_fraction
        self.include_passive = include_passive
        self.profile = profile
        self.seismic = seismic

    def run(self, footing, soil, actions, code) -> SlidingResult:
        # contact parameters: pick the layer at z = D (below the base)
        if self.profile is not None:
            contact_soil = self.profile.layer_at(footing.D).soil
            soil_d = code.design_soil(contact_soil)
        else:
            soil_d = code.design_soil(soil)
        actions_d = code.design_actions(actions, self.Q_fraction)

        e_B, e_L = actions_d.eccentricities()
        eff = footing.effective_geometry(e_B, e_L)
        A_eff = eff.A_eff

        H_d = actions_d.H_resultant
        V_d = actions_d.V

        # vertical kv effect (conservative reduction of V)
        if self.seismic is not None and self.seismic.kv != 0:
            V_d = V_d * (1.0 - abs(self.seismic.kv))

        if soil_d.drained:
            delta = math.radians(self.delta_over_phi * soil_d.phi_k)
            R_h_k = V_d * math.tan(delta) + self.c_adhesion * A_eff
            delta_deg = math.degrees(delta)
        else:
            R_h_k = soil_d.cu_k * A_eff
            delta_deg = 0.0

        R_h_d = code.design_sliding_resistance(R_h_k)

        return SlidingResult(
            E_d=H_d,
            R_d=R_h_d,
            delta=delta_deg,
        )


class OverturningCheck(Check):
    """Overturning check (EQU) about a footing edge.

    Compares the stabilising moment (vertical weight times lever arm)
    against the overturning moment (horizontal action times height plus
    applied moment).

    Axes:
        - ``'y'``: overturning about the long side, due to H_x and/or M_y
        - ``'x'``: overturning about the short side, due to H_y and/or M_x

    EQU approach: gamma_G,dst = 1.1, gamma_G,stb = 0.9 (EN 1997-1 Annex A,
    Tab. A.1). For simplicity this implementation uses the current
    ``DesignCode`` coefficients with favourable/unfavourable flags, leaving
    the choice to the caller. Strictly EQU should be handled separately.
    """

    def __init__(self, axis: str = "y", h_arm: float | None = None, Q_fraction: float = 0.0):
        if axis not in ("x", "y"):
            raise ValueError("axis must be 'x' or 'y'.")
        self.axis = axis
        self.h_arm = h_arm  # H application lever arm (default = D)
        self.Q_fraction = Q_fraction

    def run(self, footing, soil, actions, code) -> OverturningResult:
        # For EQU, the vertical is favourable and horizontal is unfavourable;
        # we accept the actions as passed (characteristic) and manually apply
        # the EQU factors if needed. Simplified version: use the design
        # actions of the current code (it is recommended to pass actions
        # with favorable=True on V if the stabilising effect is desired).
        actions_d = code.design_actions(actions, self.Q_fraction)

        B, L = footing.equivalent_BL
        if self.axis == "y":
            # overturning about an axis parallel to L -> arm = B/2
            arm = B / 2
            H_dst = abs(actions_d.H_x)
            M_dst = abs(actions_d.M_y)
        else:
            arm = L / 2
            H_dst = abs(actions_d.H_y)
            M_dst = abs(actions_d.M_x)

        h = self.h_arm if self.h_arm is not None else footing.D
        M_destab = H_dst * h + M_dst
        M_stab = actions_d.V * arm

        M_stab_d = code.design_overturning_resistance(M_stab)

        return OverturningResult(
            E_d=M_destab,
            R_d=M_stab_d,
            axis=self.axis,
        )


class SettlementCheck(Check):
    """Immediate elastic settlement (SLE) under characteristic loads.

    Two modes:
        a) **Single layer** (default): Schleicher's solution with the
           influence coefficient tabulated by Bowles:

               s = q * B * (1 - nu^2) * I_s / E

        b) **Multilayer (Steinbrenner)**: if a ``SoilProfile`` is provided,
           the subsoil is split into layers and each contribution is the
           difference between settlements computed at the layer bottom and
           top (Steinbrenner 1934):

               s = sum_i q * B' * (1 - nu_i^2) / E_i
                       * (F1_i^bot - F1_i^top)

           where F1 is Steinbrenner's influence function for a rigid
           rectangular footing. F1 is implemented as the numerical
           integral of Boussinesq's solution, valid for a flexible
           footing (at the centre). For a rigid footing apply a 0.93
           correction factor.

    Note: consolidation and secondary settlement are NOT included.
    """

    def __init__(
        self,
        s_limit: float | None = None,
        influence_factor: float | None = None,
        profile: SoilProfile | None = None,
        z_max: float | None = None,
        rigid_correction: float = 1.0,
        n_sublayers: int = 1,
    ):
        """Initialise the check.

        Args:
            s_limit: Allowable settlement [m].
            influence_factor: Override of I_s (single-layer mode only).
            profile: If provided, enables multilayer Steinbrenner mode.
            z_max: Maximum integration depth [m] from ground surface.
                Default: D + 2*B (practical influence zone).
            rigid_correction: Correction factor for a rigid (0.93 typical)
                or flexible (1.0) footing. Default 1.0.
            n_sublayers: Number of sublayers each physical layer is split
                into for Steinbrenner accuracy (default 1).
        """
        self.s_limit = s_limit
        self.I_s_override = influence_factor
        self.profile = profile
        self.z_max = z_max
        self.rigid_correction = rigid_correction
        self.n_sublayers = max(1, int(n_sublayers))

    # ------------------------------------------------------------------
    # single layer (Bowles)
    # ------------------------------------------------------------------
    @staticmethod
    def _influence_factor(B: float, L: float) -> float:
        ratio = L / B
        if ratio <= 1.0:
            return 1.12
        elif ratio >= 10:
            return 2.10
        else:
            table = [(1, 1.12), (1.5, 1.36), (2, 1.53), (3, 1.78), (5, 2.10), (10, 2.10)]
            for (r1, v1), (r2, v2) in zip(table[:-1], table[1:], strict=False):
                if r1 <= ratio <= r2:
                    return v1 + (v2 - v1) * (ratio - r1) / (r2 - r1)
            return 2.10

    # ------------------------------------------------------------------
    # multilayer (Steinbrenner) - F1, F2 at the centre of a flexible
    # rectangle. Reference: Bowles (1996), Foundation Analysis and
    # Design, §5-6.
    # ------------------------------------------------------------------
    @staticmethod
    def _steinbrenner_F1F2(B: float, L: float, H: float) -> tuple[float, float]:
        """Return Steinbrenner F1, F2 for a rectangle corner.

        Rectangle ``B x L`` uniformly loaded on a layer of thickness H.

        Definitions (Bowles 1996):
            m' = L/B,  n' = H/B
            A0 = m' * ln( ((1+sqrt(m'^2+1))*sqrt(m'^2+n'^2)) /
                            (m'*(1+sqrt(m'^2+n'^2+1))) )
            A1 = ln( ((m'+sqrt(m'^2+1))*sqrt(1+n'^2)) /
                       (m'+sqrt(m'^2+n'^2+1)) )
            A2 = m' / (n'*sqrt(m'^2+n'^2+1))
            F1 = (1/pi) * (A0 + A1)
            F2 = (n'/(2*pi)) * atan(A2)

        For the *centre* of a rectangle ``B x L``, apply this with
        ``B' = B/2``, ``L' = L/2`` and multiply by 4 (superposition of
        the four quarter-rectangles).
        """
        if H <= 0 or B <= 0:
            return 0.0, 0.0
        # convention: m' = L/B
        if L < B:
            B, L = L, B
        mp = L / B
        np = H / B
        # numerical protection
        eps = 1e-12
        s1 = math.sqrt(mp * mp + 1)
        s2 = math.sqrt(mp * mp + np * np + 1)
        s3 = math.sqrt(1 + np * np)
        s4 = math.sqrt(mp * mp + np * np)

        try:
            num0 = (1 + s1) * s4
            den0 = mp * (1 + s2)
            A0 = mp * math.log(max(num0 / max(den0, eps), eps))

            num1 = (mp + s1) * s3
            den1 = mp + s2
            A1 = math.log(max(num1 / max(den1, eps), eps))

            A2 = mp / max(np * s2, eps)
        except (ValueError, ZeroDivisionError):
            return 0.0, 0.0

        F1 = (A0 + A1) / math.pi
        F2 = (np / (2 * math.pi)) * math.atan(A2)
        return F1, F2

    @classmethod
    def _Is(cls, B: float, L: float, H: float, nu: float) -> float:
        """Shape factor Is = F1 + (1 - 2ν)/(1 - ν) * F2 at the centre.

        Computes F1, F2 for the B/2 x L/2 quarter of height H.
        """
        F1, F2 = cls._steinbrenner_F1F2(B / 2, L / 2, H)
        if abs(1 - nu) < 1e-9:
            return F1
        return F1 + (1 - 2 * nu) / (1 - nu) * F2

    @classmethod
    def _settlement_layer(
        cls, B: float, L: float, H_top: float, H_bot: float, q: float, E: float, nu: float
    ) -> float:
        """Settlement of one layer between H_top and H_bot.

        Depths are measured from the footing base, Bowles' formula:

            s = q * (B/2) * (1 - ν²) / E * 4 * (Is(H_bot) - Is(H_top))

        The factor 4 accounts for the superposition of the four
        quarter-rectangles to obtain the centre settlement.
        """
        if H_bot <= H_top:
            return 0.0
        Is_bot = cls._Is(B, L, H_bot, nu)
        Is_top = cls._Is(B, L, H_top, nu) if H_top > 0 else 0.0
        delta_Is = max(0.0, Is_bot - Is_top)
        return q * (B / 2) * (1 - nu * nu) / E * 4.0 * delta_Is

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------
    def run(self, footing, soil, actions, code) -> SettlementResult:
        # SLE: characteristic loads and parameters
        e_B, e_L = actions.eccentricities()
        eff = footing.effective_geometry(e_B, e_L)
        B_eff, L_eff, A_eff = eff.B_eff, eff.L_eff, eff.A_eff
        q = actions.V / A_eff

        from .geometry import CircularFooting

        if self.profile is None:
            # ---- single-layer mode ----
            if soil.E is None:
                raise ValueError("Soil.E is required for single-layer settlement.")
            if isinstance(footing, CircularFooting):
                I_s = 0.88
                B_ref = 2 * footing.R
            else:
                I_s = self.I_s_override or self._influence_factor(B_eff, L_eff)
                B_ref = B_eff
            s = q * B_ref * (1 - soil.nu**2) * I_s / soil.E
            s *= self.rigid_correction
            return SettlementResult(s_elastic=s, s_limit=self.s_limit)

        # ---- multilayer Steinbrenner mode ----
        D = footing.D
        z_max = self.z_max if self.z_max is not None else D + 2 * B_eff
        layers_under = self.profile.layers_under(D, z_max=z_max)
        if not layers_under:
            raise ValueError("No layers below the footing base for settlement computation.")

        s_total = 0.0
        # iterate over layers below the base, splitting each into
        # n_sublayers to improve accuracy (useful for thick or variable
        # layers)
        for z_top_abs, z_bot_abs, layer in layers_under:
            if layer.soil.E is None:
                raise ValueError(
                    f"Layer '{layer.soil.name}' has no E modulus: settlement not computable."
                )
            E = layer.soil.E
            nu = layer.soil.nu
            # depth relative to the footing base
            H_top = z_top_abs - D
            H_bot = z_bot_abs - D
            zs = [
                H_top + (H_bot - H_top) * i / self.n_sublayers for i in range(self.n_sublayers + 1)
            ]
            for h1, h2 in zip(zs[:-1], zs[1:], strict=False):
                s_total += self._settlement_layer(B_eff, L_eff, h1, h2, q, E, nu)

        s_total *= self.rigid_correction
        return SettlementResult(s_elastic=s_total, s_limit=self.s_limit)
