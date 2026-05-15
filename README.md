# ec7-foundation

[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![Build](https://img.shields.io/badge/build-uv-purple.svg)](https://docs.astral.sh/uv/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Shallow-foundation verification per **Eurocode 7 (EN 1997-1)** and the
Italian **NTC 2018**, static and seismic, with support for layered
profiles and groundwater.

## Installation

```bash
# From PyPI (once published)
pip install ec7-foundation

# With uv
uv add ec7-foundation

# With the YAML CLI extras
pip install "ec7-foundation[yaml]"
```

## Local development

The project uses [uv](https://docs.astral.sh/uv/) for virtual
environments, dependency management and builds.

```bash
# Clone the repo
git clone https://github.com/youruser/ec7-foundation.git
cd ec7-foundation

# Create the environment and install all dev dependencies
uv sync

# Run the tests
uv run pytest

# Linting / formatting
uv run ruff check .
uv run ruff format .

# Build wheel + sdist into dist/
uv build

# Run the CLI on the example
uv run ec7-verify examples/input.yaml
```

## CLI

The package installs the `ec7-verify` command, which accepts a YAML or
JSON input file:

```bash
ec7-verify examples/input.yaml          # text report
ec7-verify examples/input.yaml --json   # structured JSON report
```

## Implemented checks

- **GEO** — Bearing capacity (EN 1997-1 Annex D formula, c'-φ' and cu)
- **Sliding** on the base (drained and undrained)
- **EQU** — Overturning
- **SLE** — Elastic settlement (Bowles single-layer, **multilayer Steinbrenner**)
- **Seismic** — Paolucci & Pecker factors on bearing capacity; kv on
  sliding and unit weight

## Design approaches

| Code                         | Description                                   | γR_v (bearing) |
|------------------------------|-----------------------------------------------|----------------|
| `EC7_DA1_C1`                 | EN 1997-1 DA1 Comb. 1 (A1+M1+R1)              | 1.0            |
| `EC7_DA1_C2`                 | EN 1997-1 DA1 Comb. 2 (A2+M2+R1)              | 1.0            |
| `EC7_DA2`                    | EN 1997-1 DA2 (A1+M1+R2)                      | 1.4            |
| `EC7_DA3`                    | EN 1997-1 DA3 (A2+M2+R3)                      | 1.0            |
| `NTC2018_A1`                 | NTC 2018 Approach 1 Comb. 1 (A1+M1+R1)        | 1.0            |
| `NTC2018_A2`                 | NTC 2018 Approach 2 (A1+M1+R3)                | 2.3            |
| `NTC2018_Seismic`            | NTC 2018 seismic (A1+M1+R3)                   | 2.3            |
| `NTC2018_Seismic_Reduced`    | NTC 2018 seismic with inertial effects        | **1.8**        |
| `EC7_Seismic_DA2`            | EC7+EC8 seismic DA2                           | 1.4            |

## Architecture

```
ShallowFoundation                        <- orchestrator
   |
   |-- Footing (ABC)                     <- geometry
   |     |-- RectangularFooting
   |     |-- StripFooting
   |     +-- CircularFooting
   |
   |-- Soil           |
   |-- SoilProfile -- +-- SoilLayer      <- soil (single or layered)
   |
   |-- DesignActions                     <- V, H, M
   |-- SeismicAction                     <- kh, kv (optional)
   +-- DesignCode (ABC)                  <- partial-factor strategy
         |-- EC7_DA1_C1/C2 / DA2 / DA3
         |-- NTC2018_A1 / A2
         +-- NTC2018_Seismic / _Reduced

Check (ABC)                              <- individual verifications
   |-- BearingCheck                      <- Annex D formula + Paolucci-Pecker
   |-- SlidingCheck
   |-- OverturningCheck
   +-- SettlementCheck                   <- Bowles or Steinbrenner

VerificationReport                       <- aggregates the results
```

## Example: layered footing with groundwater, in a seismic zone

```python
from ec7 import (
    RectangularFooting, Soil, SoilLayer, SoilProfile,
    DesignActions, SeismicAction, ShallowFoundation,
    NTC2018_Seismic_Reduced,
)

# Profile: 3 layers, water table at 3 m
profile = SoilProfile(
    layers=[
        SoilLayer(top=0, bottom=2.0,
                  soil=Soil(phi_k=28, c_k=0, gamma=18, gamma_sat=19.5,
                            E=15_000, name="Silty sand")),
        SoilLayer(top=2.0, bottom=8.0,
                  soil=Soil(phi_k=34, c_k=0, gamma=19, gamma_sat=20,
                            E=30_000, name="Dense sand")),
        SoilLayer(top=8.0, bottom=30,
                  soil=Soil(phi_k=36, c_k=0, gamma=20, gamma_sat=21,
                            E=50_000, name="Gravel")),
    ],
    water_depth=3.0,
)

footing = RectangularFooting(B=2.5, L=3.5, D=1.5)
actions = DesignActions(V=1500, H_x=300, M_y=200)
seismic = SeismicAction(kh=0.06, kv=0.03)

f = ShallowFoundation(
    footing, profile=profile, actions=actions, seismic=seismic,
    code=NTC2018_Seismic_Reduced(),
)
print(f.verify_all(s_limit=0.025))
```

## Technical notes on the v0.2 extensions

### Layered profile (`SoilProfile`)

- Profile made of contiguous `SoilLayer`s from top to bottom.
- Water table defined at one elevation (`water_depth`) — handled
  automatically in the computation of total sigma and effective sigma',
  even when it crosses several layers of different unit weights.
- **Equivalent Soil in the influence volume**: to apply the Annex D
  formula to a layered profile, an equivalent `Soil` is built by
  thickness-weighted averaging of the parameters (phi, c, gamma, E) over
  the layers intersected by the failure-wedge influence zone, of extent
  ~B below the base. Simple and widely used approach; for strongly
  contrasted profiles a two-layer method (Meyerhof-Hanna) or FEM is
  recommended.
- Multilayer settlement computed with the **Steinbrenner formula**
  integrated layer-by-layer, using F1 and F2 at the centre of the
  rectangle (Bowles 1996, §5-6).

### Seismic action (`SeismicAction`)

Two distinct effects, both handled:

1. **Inertial effect on the superstructure**: the H and M passed in
   `DesignActions` reduce the bearing capacity through the inclination
   factors ic, iq, igamma already present in Annex D.
2. **Inertial effect on the failure wedge**: the z factors of
   **Paolucci & Pecker (1997)** multiply the three terms of the formula:

       z_q = z_gamma = (1 - kh / tan(phi))^0.35
       z_c           = 1 - 0.32 * kh        (undrained case)

- `kv` modifies the unit weight in the N_gamma term and reduces V in
  the sliding check.
- Consistently with NTC 2018 §7.11.5.3.1, two options are offered:
  - `NTC2018_Seismic`: gamma_Rv = 2.3 (same as static)
  - `NTC2018_Seismic_Reduced`: gamma_Rv = **1.8**, allowed only when the
    R_k computation explicitly accounts for inertial effects (i.e. a
    `SeismicAction` with kh > 0 is passed).

### Conventions

- Forces in **kN**, moments in **kN·m**, lengths in **m**, pressures in **kPa**.
- Axis **x** parallel to B (short side), axis **y** parallel to L.
- M_x produces eccentricity along L (e_L = M_x/V).
- M_y produces eccentricity along B (e_B = M_y/V).
- Actions are passed **characteristic**; in static combinations the
  A-set coefficients are applied by the `DesignCode`; in seismic
  combinations the A coefficients are unity (NTC 2018 §7.11.1).

## Tests

```bash
pytest tests/ -v
```

25 tests covering: N factors vs the literature, drained/undrained
Annex D formula, Meyerhof eccentricity, relative severity of the design
approaches, sigma and sigma' in a layered profile with water,
thickness-weighted `equivalent_soil`, Paolucci-Pecker seismic factors,
single-layer and multilayer Steinbrenner settlements, integrated
seismic + layered + water report.

## Known limitations / future work

- **Two-contrast-layer bearing capacity** (e.g. soft clay over dense
  sand): the weighted average may yield optimistic results. For critical
  cases the Meyerhof-Hanna method or punching shear is needed.
- **Consolidation and secondary settlement** not included (only
  immediate elastic).
- **Alternative seismic factors** (Maugeri, Richards, Cascone-Carrubba):
  extensible by changing `method` in `SeismicAction.seismic_factors`.
- **Performance-based seismic approach** (Pecker 2017,
  displacement-based): out of scope.
- **EQU check with dedicated coefficients** (gamma_G,dst=1.1,
  gamma_G,stb=0.9): currently the coefficients of the active DesignCode
  are used with `favorable=True/False`.
