"""
ec7 - Verifica di fondazioni superficiali secondo Eurocodice 7 (EN 1997-1)
        e Norme Tecniche per le Costruzioni 2018 (NTC 2018).

Supporta:
  - geometria rettangolare, nastriforme, circolare
  - eccentricità su due assi (Meyerhof)
  - terreno monostrato o stratigrafia (SoilProfile) con falda multistrato
  - verifiche statiche e sismiche (Paolucci & Pecker 1997)
  - cedimenti elastici monostrato (Bowles) e multistrato (Steinbrenner)
"""

from .actions import DesignActions
from .code import (
    EC7_DA1_C1,
    EC7_DA1_C2,
    EC7_DA2,
    EC7_DA3,
    NTC2018_A1,
    NTC2018_A2,
    DesignCode,
    EC7_Seismic_DA2,
    NTC2018_Seismic,
    NTC2018_Seismic_Reduced,
)
from .foundation import ShallowFoundation
from .geometry import CircularFooting, Footing, RectangularFooting, StripFooting
from .profile import SoilLayer, SoilProfile
from .results import (
    BearingResult,
    OverturningResult,
    SettlementResult,
    SlidingResult,
    VerificationReport,
)
from .seismic import SeismicAction
from .soil import Soil

__all__ = [
    "Footing",
    "RectangularFooting",
    "StripFooting",
    "CircularFooting",
    "Soil",
    "SoilLayer",
    "SoilProfile",
    "DesignActions",
    "SeismicAction",
    "DesignCode",
    "EC7_DA1_C1",
    "EC7_DA1_C2",
    "EC7_DA2",
    "EC7_DA3",
    "NTC2018_A1",
    "NTC2018_A2",
    "NTC2018_Seismic",
    "NTC2018_Seismic_Reduced",
    "EC7_Seismic_DA2",
    "ShallowFoundation",
    "BearingResult",
    "SlidingResult",
    "OverturningResult",
    "SettlementResult",
    "VerificationReport",
]

try:
    from importlib.metadata import version as _v

    __version__ = _v("ec7-foundation")
except Exception:  # pragma: no cover
    __version__ = "0.0.0+unknown"
