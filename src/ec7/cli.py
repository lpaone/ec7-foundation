"""CLI per il pacchetto ec7-foundation.

Permette di eseguire una verifica leggendo un file di input YAML o JSON
che descrive geometria, terreno, azioni, normativa e (opzionalmente)
sisma. Stampa il report a video.

Uso:
    ec7-verify input.yaml
    ec7-verify input.json --json    # output strutturato JSON

Esempio di input minimo (YAML):

    code: NTC2018_A2
    footing:
      type: rectangular
      B: 2.5
      L: 3.5
      D: 1.5
    soil:                 # in alternativa a `profile`
      phi_k: 32
      c_k: 5
      gamma: 19
      gamma_sat: 20
      E: 25000
    actions:
      V: 1200
      H_x: 150
      M_y: 100
    settlement_limit: 0.025
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from . import (
    EC7_DA1_C1,
    EC7_DA1_C2,
    EC7_DA2,
    EC7_DA3,
    NTC2018_A1,
    NTC2018_A2,
    CircularFooting,
    DesignActions,
    EC7_Seismic_DA2,
    NTC2018_Seismic,
    NTC2018_Seismic_Reduced,
    RectangularFooting,
    SeismicAction,
    ShallowFoundation,
    Soil,
    SoilLayer,
    SoilProfile,
    StripFooting,
)

_CODES = {
    "EC7_DA1_C1": EC7_DA1_C1,
    "EC7_DA1_C2": EC7_DA1_C2,
    "EC7_DA2": EC7_DA2,
    "EC7_DA3": EC7_DA3,
    "NTC2018_A1": NTC2018_A1,
    "NTC2018_A2": NTC2018_A2,
    "NTC2018_Seismic": NTC2018_Seismic,
    "NTC2018_Seismic_Reduced": NTC2018_Seismic_Reduced,
    "EC7_Seismic_DA2": EC7_Seismic_DA2,
}


def _load_input(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise SystemExit(
                "PyYAML non installato. Installa con: pip install 'ec7-foundation[yaml]'"
            ) from exc
        return yaml.safe_load(text)
    if path.suffix.lower() == ".json":
        return json.loads(text)
    raise SystemExit(f"Formato file non supportato: {path.suffix}")


def _build_footing(spec: dict[str, Any]):
    t = spec.get("type", "rectangular").lower()
    if t == "rectangular":
        return RectangularFooting(
            B=spec["B"],
            L=spec["L"],
            D=spec["D"],
            base_inclination=spec.get("base_inclination", 0.0),
            ground_inclination=spec.get("ground_inclination", 0.0),
        )
    if t == "strip":
        return StripFooting(
            B=spec["B"],
            D=spec["D"],
            base_inclination=spec.get("base_inclination", 0.0),
            ground_inclination=spec.get("ground_inclination", 0.0),
        )
    if t == "circular":
        return CircularFooting(
            R=spec["R"],
            D=spec["D"],
            base_inclination=spec.get("base_inclination", 0.0),
            ground_inclination=spec.get("ground_inclination", 0.0),
        )
    raise SystemExit(f"Tipo fondazione sconosciuto: {t}")


def _build_soil(spec: dict[str, Any]) -> Soil:
    return Soil(
        phi_k=spec.get("phi_k", 0.0),
        c_k=spec.get("c_k", 0.0),
        cu_k=spec.get("cu_k"),
        gamma=spec.get("gamma", 19.0),
        gamma_sat=spec.get("gamma_sat", 20.0),
        water_depth=spec.get("water_depth"),
        drained=spec.get("drained", True),
        E=spec.get("E"),
        nu=spec.get("nu", 0.3),
        name=spec.get("name", "Soil"),
    )


def _build_profile(spec: dict[str, Any]) -> SoilProfile:
    layers = [
        SoilLayer(top=layer["top"], bottom=layer["bottom"], soil=_build_soil(layer["soil"]))
        for layer in spec["layers"]
    ]
    return SoilProfile(layers=layers, water_depth=spec.get("water_depth"))


def _build_actions(spec: dict[str, Any]) -> DesignActions:
    return DesignActions(
        V=spec["V"],
        H_x=spec.get("H_x", 0.0),
        H_y=spec.get("H_y", 0.0),
        M_x=spec.get("M_x", 0.0),
        M_y=spec.get("M_y", 0.0),
        favorable=spec.get("favorable", False),
        already_factored=spec.get("already_factored", False),
    )


def _build_seismic(spec: dict[str, Any] | None) -> SeismicAction | None:
    if not spec:
        return None
    return SeismicAction(
        kh=spec["kh"], kv=spec.get("kv", 0.0), method=spec.get("method", "paolucci_pecker")
    )


def _build_code(name: str):
    if name not in _CODES:
        raise SystemExit(f"Codice sconosciuto: {name}. Disponibili: {', '.join(_CODES)}")
    return _CODES[name]()


def _report_to_dict(report) -> dict[str, Any]:
    """Serializza il report in un dict (per output JSON)."""
    out: dict[str, Any] = {"code": report.code_name, "all_passed": report.all_passed}
    if report.bearing:
        d = asdict(report.bearing)
        d.pop("factors", None)
        d["utilization"] = report.bearing.utilization
        d["passed"] = report.bearing.passed
        out["bearing"] = d
    if report.sliding:
        d = asdict(report.sliding)
        d["utilization"] = report.sliding.utilization
        d["passed"] = report.sliding.passed
        out["sliding"] = d
    if report.overturning:
        d = asdict(report.overturning)
        d["utilization"] = report.overturning.utilization
        d["passed"] = report.overturning.passed
        out["overturning"] = d
    if report.settlement:
        d = asdict(report.settlement)
        d["passed"] = report.settlement.passed
        out["settlement"] = d
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ec7-verify",
        description="Verifica di fondazioni superficiali secondo EC7 / NTC 2018.",
    )
    parser.add_argument("input", type=Path, help="File di input YAML o JSON.")
    parser.add_argument(
        "--json", action="store_true", help="Stampa il report in formato JSON anziché testo."
    )
    parser.add_argument("--version", action="version", version=_version_string())
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"File non trovato: {args.input}", file=sys.stderr)
        return 2

    data = _load_input(args.input)

    footing = _build_footing(data["footing"])
    if "profile" in data:
        profile = _build_profile(data["profile"])
        soil = None
    else:
        profile = None
        soil = _build_soil(data["soil"])
    actions = _build_actions(data["actions"])
    seismic = _build_seismic(data.get("seismic"))
    code = _build_code(data.get("code", "NTC2018_A2"))

    f = ShallowFoundation(
        footing, soil=soil, profile=profile, actions=actions, seismic=seismic, code=code
    )
    report = f.verify_all(
        Q_fraction=data.get("Q_fraction", 0.0),
        delta_over_phi=data.get("delta_over_phi", 1.0),
        overturning_axis=data.get("overturning_axis", "y"),
        h_arm=data.get("h_arm"),
        s_limit=data.get("settlement_limit"),
        skip=data.get("skip", ()),
    )

    if args.json:
        print(json.dumps(_report_to_dict(report), indent=2, ensure_ascii=False))
    else:
        print(report)

    return 0 if report.all_passed else 1


def _version_string() -> str:
    from . import __version__

    return f"ec7-verify {__version__}"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
