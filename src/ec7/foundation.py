"""Main class: orchestrates verifications on a shallow foundation."""

from __future__ import annotations

from collections.abc import Sequence

from .actions import DesignActions
from .checks import (
    BearingCheck,
    OverturningCheck,
    SettlementCheck,
    SlidingCheck,
)
from .code import NTC2018_A2, DesignCode
from .geometry import Footing
from .profile import SoilProfile
from .results import (
    BearingResult,
    OverturningResult,
    SettlementResult,
    SlidingResult,
    VerificationReport,
)
from .seismic import SeismicAction
from .soil import Soil


class ShallowFoundation:
    """Complete shallow foundation.

    Composition:
        - ``footing``: geometry
        - ``soil``: single-layer soil — OPTIONAL when a ``profile`` is provided
        - ``profile``: layered profile — alternative or complement to ``soil``
        - ``actions``: characteristic actions (V, H, M)
        - ``seismic``: seismic action (kh, kv) for seismic conditions
        - ``code``: code / design approach

    Single-layer usage (v0.1 compatibility):

        f = ShallowFoundation(footing, soil, actions, code=NTC2018_A2())

    Layered usage:

        f = ShallowFoundation(footing, profile=profile, actions=actions,
                              code=NTC2018_A2())

    Layered + seismic:

        seismic = SeismicAction(kh=0.15, kv=0.075)
        f = ShallowFoundation(footing, profile=profile, actions=actions,
                              seismic=seismic, code=NTC2018_Seismic_Reduced())
    """

    def __init__(
        self,
        footing: Footing,
        soil: Soil | None = None,
        actions: DesignActions | None = None,
        code: DesignCode | None = None,
        profile: SoilProfile | None = None,
        seismic: SeismicAction | None = None,
    ):
        if soil is None and profile is None:
            raise ValueError("At least one of `soil` and `profile` is required.")
        if actions is None:
            raise ValueError("`actions` is required.")
        self.footing = footing
        self.soil = soil
        self.profile = profile
        self.actions = actions
        self.seismic = seismic
        self.code = code if code is not None else NTC2018_A2()

    # ----- individual checks -----------------------------------------------

    def check_bearing(self, **kwargs) -> BearingResult:
        kwargs.setdefault("profile", self.profile)
        kwargs.setdefault("seismic", self.seismic)
        return BearingCheck(**kwargs).run(self.footing, self.soil, self.actions, self.code)

    def check_sliding(self, **kwargs) -> SlidingResult:
        kwargs.setdefault("profile", self.profile)
        kwargs.setdefault("seismic", self.seismic)
        return SlidingCheck(**kwargs).run(self.footing, self.soil, self.actions, self.code)

    def check_overturning(self, **kwargs) -> OverturningResult:
        return OverturningCheck(**kwargs).run(self.footing, self.soil, self.actions, self.code)

    def check_settlement(self, s_limit: float | None = None, **kwargs) -> SettlementResult:
        kwargs.setdefault("profile", self.profile)
        return SettlementCheck(s_limit=s_limit, **kwargs).run(
            self.footing, self.soil, self.actions, self.code
        )

    # ----- full verification -----------------------------------------------

    def verify_all(
        self,
        Q_fraction: float = 0.0,
        delta_over_phi: float = 1.0,
        overturning_axis: str = "y",
        h_arm: float | None = None,
        s_limit: float | None = None,
        skip: Sequence[str] = (),
    ) -> VerificationReport:
        """Run all verifications and return the aggregated report.

        Args:
            Q_fraction: Fraction of variable load on total actions.
            delta_over_phi: Ratio between base/soil friction angle and phi.
            overturning_axis: ``'x'`` or ``'y'`` for overturning.
            h_arm: Application lever arm for H (default = D).
            s_limit: Allowable settlement [m].
            skip: Names of checks to skip (subset of
                ``{'bearing', 'sliding', 'overturning', 'settlement'}``).

        Returns:
            Aggregated ``VerificationReport``.
        """
        skip = set(skip)
        report = VerificationReport(code_name=self.code.name)

        if "bearing" not in skip:
            report.bearing = self.check_bearing(Q_fraction=Q_fraction)
        if "sliding" not in skip:
            report.sliding = self.check_sliding(
                delta_over_phi=delta_over_phi, Q_fraction=Q_fraction
            )
        if "overturning" not in skip:
            report.overturning = self.check_overturning(
                axis=overturning_axis, h_arm=h_arm, Q_fraction=Q_fraction
            )
        # settlement: needs at least E in soil/profile; if E is missing in
        # some layer we silently skip the check
        if "settlement" not in skip:
            try:
                report.settlement = self.check_settlement(s_limit=s_limit)
            except ValueError:
                pass

        return report

    def __repr__(self):
        n_layers = len(self.profile.layers) if self.profile else 1
        return (
            f"ShallowFoundation({self.footing.shape_name}, "
            f"D={self.footing.D} m, n_layers={n_layers}, "
            f"code={self.code.name})"
        )
