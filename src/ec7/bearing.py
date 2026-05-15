"""Drained and undrained bearing capacity per EN 1997-1 Annex D.

Formulas:

  Undrained (D.1):
      R/A' = (pi + 2) * cu * b_c * s_c * i_c + q
  Drained (D.2):
      R/A' = c'*Nc*b_c*s_c*i_c + q'*Nq*b_q*s_q*i_q
             + 0.5*gamma'*B'*Ngamma*b_g*s_g*i_g

The factors are those of Annex D (Brinch Hansen). Depth factors are NOT
included to stay aligned with Annex D, but an ``include_depth_factors``
option is available for the extended Brinch Hansen formulation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .actions import DesignActions
    from .geometry import Footing
    from .profile import SoilProfile
    from .seismic import SeismicAction
    from .soil import Soil


@dataclass
class BearingCapacityFactors:
    """All intermediate factors of the formula, useful for reporting."""

    Nc: float
    Nq: float
    Ngamma: float
    sc: float
    sq: float
    sgamma: float
    ic: float
    iq: float
    igamma: float
    bc: float
    bq: float
    bgamma: float
    gc: float = 1.0
    gq: float = 1.0
    ggamma: float = 1.0  # ground inclination
    dc: float = 1.0
    dq: float = 1.0
    dgamma: float = 1.0  # depth (optional)
    zc: float = 1.0
    zq: float = 1.0
    zgamma: float = 1.0  # seismic (Paolucci-Pecker)


def _bearing_capacity_coefficients(
    phi_rad: float, ngamma_method: str = "vesic"
) -> tuple[float, float, float]:
    """Return Nc, Nq, Ngamma for drained analysis.

    Nq and Nc follow Prandtl/Reissner (same in Hansen, Meyerhof, Vesic).
    Two options are available for Ngamma:
        - ``'vesic'``: Nγ = 2·(Nq+1)·tan(φ)   [default, common in
          commercial software]
        - ``'hansen'``: Nγ = 1.5·(Nq-1)·tan(φ)  [historical base of
          Annex D in EC7]
    """
    if phi_rad <= 1e-9:
        return 5.14, 1.0, 0.0
    Nq = math.exp(math.pi * math.tan(phi_rad)) * math.tan(math.pi / 4 + phi_rad / 2) ** 2
    Nc = (Nq - 1) / math.tan(phi_rad)
    if ngamma_method == "vesic":
        Ngamma = 2 * (Nq + 1) * math.tan(phi_rad)
    elif ngamma_method == "hansen":
        Ngamma = 1.5 * (Nq - 1) * math.tan(phi_rad)
    else:
        raise ValueError(f"Unknown ngamma_method: {ngamma_method}")
    return Nc, Nq, Ngamma


def _shape_factors_drained(
    B_eff: float, L_eff: float, phi_rad: float, Nq: float
) -> tuple[float, float, float]:
    """Drained shape factors (Annex D)."""
    ratio = B_eff / L_eff
    sq = 1 + ratio * math.sin(phi_rad)
    sgamma = 1 - 0.3 * ratio
    if abs(Nq - 1) < 1e-9:
        sc = 1 + 0.2 * ratio  # phi=0 limit
    else:
        sc = (sq * Nq - 1) / (Nq - 1)
    # circular footing has B'=L' -> ratio=1 (square case), Annex D OK
    return sc, sq, sgamma


def _shape_factor_undrained(B_eff: float, L_eff: float) -> float:
    """sc for undrained analysis (Annex D, D.1)."""
    return 1 + 0.2 * (B_eff / L_eff)


def _inclination_factors_drained(
    H: float, V: float, A_eff: float, c: float, phi_rad: float, m: float
) -> tuple[float, float, float]:
    """Drained inclination factors (Annex D, Vesic formulation).

    ``m`` depends on the angle of the horizontal resultant relative to B' or L'.
    """
    if H <= 1e-9:
        return 1.0, 1.0, 1.0

    # "cohesion-friction" term (denominator): V + A' * c' * cot(phi)
    if phi_rad > 1e-6:
        cot_phi = 1 / math.tan(phi_rad)
        denom = V + A_eff * c * cot_phi
    else:
        # drained with phi ~ 0 - fall back to undrained formula
        return 1.0, 1.0, 1.0

    base = 1 - H / denom
    if base <= 0:
        # excessive horizontal load: zero capacity (failure signal)
        return 0.0, 0.0, 0.0

    iq = base**m
    igamma = base ** (m + 1)
    if abs(phi_rad) < 1e-6:
        ic = iq
    else:
        Nq = math.exp(math.pi * math.tan(phi_rad)) * math.tan(math.pi / 4 + phi_rad / 2) ** 2
        ic = iq - (1 - iq) / (Nq - 1) if Nq > 1.0001 else iq
    return ic, iq, igamma


def _inclination_factor_undrained(H: float, A_eff: float, cu: float) -> float:
    """ic for undrained analysis (Annex D, D.1)."""
    if H <= 1e-9:
        return 1.0
    arg = 1 - H / (A_eff * cu)
    if arg < 0:
        return 0.0
    return 0.5 * (1 + math.sqrt(arg))


def _m_coefficient(B_eff: float, L_eff: float, H_B: float, H_L: float) -> float:
    """Vesic ``m`` coefficient for the inclination factors.

    Combines mB (horizontal load along B') and mL (along L') based on the
    angle of the resultant.
    """
    mB = (2 + B_eff / L_eff) / (1 + B_eff / L_eff)
    mL = (2 + L_eff / B_eff) / (1 + L_eff / B_eff)
    H = math.hypot(H_B, H_L)
    if H < 1e-9:
        return mB
    # theta = angle between H and the L' direction
    theta = math.atan2(H_B, H_L)
    return mL * math.cos(theta) ** 2 + mB * math.sin(theta) ** 2


def _base_inclination_factors(alpha: float, phi_rad: float) -> tuple[float, float, float]:
    """Base-inclination factors for tilt alpha (Annex D)."""
    if abs(alpha) < 1e-9:
        return 1.0, 1.0, 1.0
    bq = (1 - alpha * math.tan(phi_rad)) ** 2
    bgamma = bq
    if abs(phi_rad) < 1e-6:
        bc = 1 - 2 * alpha / (math.pi + 2)
    else:
        Nc, Nq, _ = _bearing_capacity_coefficients(phi_rad)
        bc = bq - (1 - bq) / (Nc * math.tan(phi_rad))
    return bc, bq, bgamma


def _ground_inclination_factors(beta: float, phi_rad: float) -> tuple[float, float, float]:
    """Ground-surface inclination factors (Brinch Hansen).

    Note: Annex D does not address them explicitly; the classic Brinch
    Hansen expressions used in European practice are inserted here.
    """
    if abs(beta) < 1e-9:
        return 1.0, 1.0, 1.0
    gq = (1 - math.tan(beta)) ** 2
    ggamma = gq
    if abs(phi_rad) < 1e-6:
        gc = 1 - 2 * beta / (math.pi + 2)
    else:
        Nc, Nq, _ = _bearing_capacity_coefficients(phi_rad)
        gc = gq - (1 - gq) / (Nc * math.tan(phi_rad))
    return gc, gq, ggamma


# ---------------------------------------------------------------------------
# Main API
# ---------------------------------------------------------------------------


@dataclass
class BearingCapacityComputation:
    """Result of the characteristic bearing-capacity computation.

    Attributes:
        R_k: Total force on the effective base [kN].
        q_ult: Ultimate pressure [kPa].
        factors: Intermediate factors of the formula.
        A_eff: Effective area [m^2].
        B_eff: Effective short side [m].
        L_eff: Effective long side [m].
    """

    R_k: float  # [kN]
    q_ult: float  # [kPa]
    factors: BearingCapacityFactors
    A_eff: float  # [m^2]
    B_eff: float
    L_eff: float


def compute_bearing_capacity(
    footing: Footing,
    soil: Soil,
    actions: DesignActions,
    profile: SoilProfile | None = None,
    seismic: SeismicAction | None = None,
) -> BearingCapacityComputation:
    """Compute the characteristic bearing capacity per EN 1997-1 Annex D.

    Soil and action parameters are assumed already at design level if the
    ``DesignCode`` has transformed them upstream. This function is "pure":
    it does not apply partial factors.

    Args:
        footing: Footing geometry.
        soil: Strength/stiffness parameters used in the formula. For a
            layered profile this is the equivalent ``Soil`` (see
            ``SoilProfile.equivalent_soil``).
        actions: Design actions.
        profile: If provided, the surcharge q' at the base is computed
            from the profile (handling multilayer water table correctly)
            instead of from the single ``Soil``.
        seismic: If provided, applies Paolucci & Pecker seismic factors on
            the three terms of the formula; any kv modifies gamma'.

    Returns:
        A ``BearingCapacityComputation`` containing R_k, q_ult and the
        intermediate factors.
    """
    e_B, e_L = actions.eccentricities()
    eff = footing.effective_geometry(e_B, e_L)
    B_eff, L_eff, A_eff = eff.B_eff, eff.L_eff, eff.A_eff

    H_x, H_y = actions.H_x, actions.H_y
    H = math.hypot(H_x, H_y)
    V = actions.V

    # ---- unit weights and surcharge ------------------------------------
    if profile is not None:
        # q' at the base from the profile (effective pressure, handles water)
        q_overburden = profile.effective_overburden_at(footing.D)
        # effective gamma below the base (at depth D + B'/2)
        gamma_below = profile.effective_unit_weight_at(footing.D + B_eff / 2)
    else:
        gamma_below = soil.effective_unit_weight(footing.D + B_eff / 2)
        q_overburden = soil.overburden_at(footing.D)

    # ---- vertical seismic effect (kv): modifies gamma' ------------------
    if seismic is not None and seismic.kv != 0:
        # Worst case: kv reduces the stabilising weight of the soil below
        # the base (upward action) -> gamma * (1 - kv), but it increases
        # the thrust on the wedge (downward) -> (1 + kv). Conservatively
        # apply (1 - |kv|) on the gamma used in the Nγ term.
        kv_factor = 1.0 - abs(seismic.kv)
        gamma_below = gamma_below * kv_factor
        # q_overburden is less affected: assumed unchanged for simplicity

    alpha = footing.alpha
    beta = footing.beta

    if soil.drained:
        phi_rad = soil.phi_k_rad
        c = soil.c_k

        Nc, Nq, Ngamma = _bearing_capacity_coefficients(phi_rad)
        sc, sq, sgamma = _shape_factors_drained(B_eff, L_eff, phi_rad, Nq)

        # m and inclination factors: Annex D uses the horizontal force
        # components along B' and L'. Convention: H_x acts along B,
        # H_y along L.
        m = _m_coefficient(B_eff, L_eff, H_x, H_y)
        ic, iq, igamma = _inclination_factors_drained(H, V, A_eff, c, phi_rad, m)

        bc, bq, bgamma = _base_inclination_factors(alpha, phi_rad)
        gc, gq, ggamma = _ground_inclination_factors(beta, phi_rad)

        # Paolucci & Pecker seismic factors
        if seismic is not None and seismic.kh > 0:
            zc, zq, zgamma = seismic.seismic_factors(phi_rad, drained=True)
        else:
            zc, zq, zgamma = 1.0, 1.0, 1.0

        q_ult = (
            c * Nc * sc * ic * bc * gc * zc
            + q_overburden * Nq * sq * iq * bq * gq * zq
            + 0.5 * gamma_below * B_eff * Ngamma * sgamma * igamma * bgamma * ggamma * zgamma
        )
    else:
        # Undrained analysis - eq. (D.1)
        cu = soil.cu_k
        sc = _shape_factor_undrained(B_eff, L_eff)
        ic = _inclination_factor_undrained(H, A_eff, cu)
        bc, bq, bgamma = _base_inclination_factors(alpha, 0.0)
        gc, gq, ggamma = _ground_inclination_factors(beta, 0.0)
        Nc, Nq, Ngamma = 5.14, 1.0, 0.0
        sq = sgamma = 1.0
        iq = igamma = 1.0

        if seismic is not None and seismic.kh > 0:
            zc, zq, zgamma = seismic.seismic_factors(0.0, drained=False)
        else:
            zc, zq, zgamma = 1.0, 1.0, 1.0

        q_ult = (math.pi + 2) * cu * bc * sc * ic * zc + q_overburden

    R_k = q_ult * A_eff

    factors = BearingCapacityFactors(
        Nc=Nc,
        Nq=Nq,
        Ngamma=Ngamma,
        sc=sc,
        sq=sq,
        sgamma=sgamma,
        ic=ic,
        iq=iq,
        igamma=igamma,
        bc=bc,
        bq=bq,
        bgamma=bgamma,
        gc=gc,
        gq=gq,
        ggamma=ggamma,
        zc=zc,
        zq=zq,
        zgamma=zgamma,
    )

    return BearingCapacityComputation(
        R_k=R_k,
        q_ult=q_ult,
        factors=factors,
        A_eff=A_eff,
        B_eff=B_eff,
        L_eff=L_eff,
    )
