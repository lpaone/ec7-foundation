"""Classe principale: orchestra le verifiche su una fondazione superficiale."""

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
    """Fondazione superficiale completa.

    Composizione:
      - footing  : geometria
      - soil     : terreno (monostrato) - OPZIONALE se è fornito un profile
      - profile  : profilo stratigrafico - alternativa o complemento a soil
      - actions  : azioni caratteristiche (V, H, M)
      - seismic  : azione sismica (kh, kv) per condizioni sismiche
      - code     : normativa / approccio di progetto

    Per uso monostrato (compatibilità con la prima versione):
        f = ShallowFoundation(footing, soil, actions, code=NTC2018_A2())

    Per stratigrafia:
        f = ShallowFoundation(footing, profile=profile, actions=actions,
                              code=NTC2018_A2())

    Per stratigrafia + sismica:
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
            raise ValueError("Serve almeno uno tra `soil` e `profile`.")
        if actions is None:
            raise ValueError("Le azioni `actions` sono obbligatorie.")
        self.footing = footing
        self.soil = soil
        self.profile = profile
        self.actions = actions
        self.seismic = seismic
        self.code = code if code is not None else NTC2018_A2()

    # ----- verifiche individuali -------------------------------------------

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

    # ----- verifica completa -----------------------------------------------

    def verify_all(
        self,
        Q_fraction: float = 0.0,
        delta_over_phi: float = 1.0,
        overturning_axis: str = "y",
        h_arm: float | None = None,
        s_limit: float | None = None,
        skip: Sequence[str] = (),
    ) -> VerificationReport:
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
        # cedimento: serve almeno E nel soil/profile; se manca E in qualche
        # strato lo skippiamo silenziosamente
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
