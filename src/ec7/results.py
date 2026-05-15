"""Strutture dati per i risultati delle verifiche."""

from __future__ import annotations

from dataclasses import dataclass

from .bearing import BearingCapacityFactors


@dataclass
class BaseResult:
    """Risultato comune: domanda E_d, resistenza R_d, fattore di sicurezza."""

    E_d: float  # azione di progetto
    R_d: float  # resistenza di progetto
    name: str = "Check"
    units_E: str = "kN"
    units_R: str = "kN"

    @property
    def utilization(self) -> float:
        if self.R_d <= 0:
            return float("inf")
        return self.E_d / self.R_d

    @property
    def passed(self) -> bool:
        return self.E_d <= self.R_d

    @property
    def safety_factor(self) -> float:
        if self.E_d <= 0:
            return float("inf")
        return self.R_d / self.E_d

    def __str__(self) -> str:
        status = "OK" if self.passed else "NON VERIFICATO"
        return (
            f"[{self.name}] E_d = {self.E_d:.2f} {self.units_E}  "
            f"R_d = {self.R_d:.2f} {self.units_R}  "
            f"U = {self.utilization:.2%}  -> {status}"
        )


@dataclass
class BearingResult(BaseResult):
    name: str = "Capacità portante (GEO)"
    R_k: float = 0.0
    q_ult: float = 0.0
    A_eff: float = 0.0
    B_eff: float = 0.0
    L_eff: float = 0.0
    factors: BearingCapacityFactors | None = None
    e_B: float = 0.0
    e_L: float = 0.0


@dataclass
class SlidingResult(BaseResult):
    name: str = "Scorrimento"
    delta: float = 0.0  # angolo di attrito base-terreno [gradi]
    R_pk: float = 0.0  # resistenza passiva caratteristica (se inclusa)


@dataclass
class OverturningResult(BaseResult):
    name: str = "Ribaltamento (EQU)"
    units_E: str = "kN m"
    units_R: str = "kN m"
    axis: str = "y"  # asse di ribaltamento


@dataclass
class SettlementResult:
    """Cedimento elastico (SLE). Non c'è un confronto E/R: si calcola
    il cedimento e si confronta con un limite ammissibile fornito dall'utente."""

    s_elastic: float  # [m]
    s_limit: float | None = None  # [m] limite SLE
    name: str = "Cedimento elastico (SLE)"

    @property
    def passed(self) -> bool:
        if self.s_limit is None:
            return True
        return self.s_elastic <= self.s_limit

    @property
    def utilization(self) -> float:
        if self.s_limit is None or self.s_limit <= 0:
            return 0.0
        return self.s_elastic / self.s_limit

    def __str__(self) -> str:
        msg = f"[{self.name}] s = {self.s_elastic * 1000:.2f} mm"
        if self.s_limit is not None:
            status = "OK" if self.passed else "NON VERIFICATO"
            msg += (
                f"  s_lim = {self.s_limit * 1000:.2f} mm  U = {self.utilization:.2%}  -> {status}"
            )
        else:
            msg += "  (nessun limite specificato)"
        return msg


@dataclass
class VerificationReport:
    """Raccolta dei risultati di tutte le verifiche."""

    code_name: str
    bearing: BearingResult | None = None
    sliding: SlidingResult | None = None
    overturning: OverturningResult | None = None
    settlement: SettlementResult | None = None

    @property
    def all_passed(self) -> bool:
        results = [self.bearing, self.sliding, self.overturning, self.settlement]
        return all(r is None or r.passed for r in results)

    def __str__(self) -> str:
        lines = [
            "=" * 70,
            f"  REPORT DI VERIFICA - {self.code_name}",
            "=" * 70,
        ]
        if self.bearing:
            f = self.bearing.factors
            lines += [
                str(self.bearing),
                f"   q_ult = {self.bearing.q_ult:.1f} kPa, R_k = {self.bearing.R_k:.1f} kN",
                f"   A_eff = {self.bearing.A_eff:.3f} m^2 "
                f"(B'={self.bearing.B_eff:.3f}, L'={self.bearing.L_eff:.3f})",
                f"   e_B = {self.bearing.e_B:.3f} m, e_L = {self.bearing.e_L:.3f} m",
            ]
            if f is not None:
                lines += [
                    f"   Fattori capacità : Nc={f.Nc:.2f}  Nq={f.Nq:.2f}  Nγ={f.Ngamma:.2f}",
                    f"   Fattori forma    : sc={f.sc:.3f}  sq={f.sq:.3f}  sγ={f.sgamma:.3f}",
                    f"   Fattori inclin.  : ic={f.ic:.3f}  iq={f.iq:.3f}  iγ={f.igamma:.3f}",
                    f"   Fattori base     : bc={f.bc:.3f}  bq={f.bq:.3f}  bγ={f.bgamma:.3f}",
                ]
                if any(abs(x - 1.0) > 1e-6 for x in (f.zc, f.zq, f.zgamma)):
                    lines.append(
                        f"   Fattori sismici  : zc={f.zc:.3f}  zq={f.zq:.3f}  zγ={f.zgamma:.3f}"
                    )
        if self.sliding:
            lines.append(str(self.sliding))
        if self.overturning:
            lines.append(str(self.overturning))
        if self.settlement:
            lines.append(str(self.settlement))
        lines += [
            "-" * 70,
            f"  ESITO COMPLESSIVO: {'TUTTE VERIFICATE' if self.all_passed else 'ALMENO UNA NON VERIFICATA'}",
            "=" * 70,
        ]
        return "\n".join(lines)
