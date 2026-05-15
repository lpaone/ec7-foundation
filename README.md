# ec7-foundation

[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue.svg)](https://www.python.org/)
[![Build](https://img.shields.io/badge/build-uv-purple.svg)](https://docs.astral.sh/uv/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Verifica di fondazioni superficiali secondo **Eurocodice 7 (EN 1997-1)** e
**NTC 2018**, statico e sismico, con supporto per stratigrafie e falda.

## Installazione

```bash
# Da PyPI (quando pubblicato)
pip install ec7-foundation

# Con uv
uv add ec7-foundation

# Con il CLI YAML
pip install "ec7-foundation[yaml]"
```

## Sviluppo locale

Il progetto usa [uv](https://docs.astral.sh/uv/) per la gestione di
ambiente virtuale, dipendenze e build.

```bash
# Clona il repo
git clone https://github.com/youruser/ec7-foundation.git
cd ec7-foundation

# Crea l'ambiente e installa tutte le dipendenze di sviluppo
uv sync

# Esegui i test
uv run pytest

# Linting / formatting
uv run ruff check .
uv run ruff format .

# Costruisci wheel + sdist in dist/
uv build

# Esegui il CLI sull'esempio
uv run ec7-verify examples/input.yaml
```

## CLI

Il pacchetto installa il comando `ec7-verify` che accetta un file YAML
o JSON di input:

```bash
ec7-verify examples/input.yaml          # report testuale
ec7-verify examples/input.yaml --json   # report JSON strutturato
```

## Verifiche implementate

- **GEO** — Capacità portante (formula EN 1997-1 Annex D, c'-φ' e cu)
- **Scorrimento** sulla base (drenato e non drenato)
- **EQU** — Ribaltamento
- **SLE** — Cedimento elastico (Bowles monostrato, **Steinbrenner multistrato**)
- **Sismica** — Fattori di Paolucci & Pecker su capacità portante; kv su
  scorrimento e peso di volume

## Approcci di progetto

| Codice                       | Descrizione                                | γR_v (cap. portante) |
|------------------------------|--------------------------------------------|----------------------|
| `EC7_DA1_C1`                 | EN 1997-1 DA1 Comb. 1 (A1+M1+R1)           | 1.0                  |
| `EC7_DA1_C2`                 | EN 1997-1 DA1 Comb. 2 (A2+M2+R1)           | 1.0                  |
| `EC7_DA2`                    | EN 1997-1 DA2 (A1+M1+R2)                   | 1.4                  |
| `EC7_DA3`                    | EN 1997-1 DA3 (A2+M2+R3)                   | 1.0                  |
| `NTC2018_A1`                 | NTC 2018 Approccio 1 Comb.1 (A1+M1+R1)     | 1.0                  |
| `NTC2018_A2`                 | NTC 2018 Approccio 2 (A1+M1+R3)            | 2.3                  |
| `NTC2018_Seismic`            | NTC 2018 sismica (A1+M1+R3)                | 2.3                  |
| `NTC2018_Seismic_Reduced`    | NTC 2018 sismica con effetti inerziali     | **1.8**              |
| `EC7_Seismic_DA2`            | EC7+EC8 sismica DA2                        | 1.4                  |

## Architettura

```
ShallowFoundation                        <- orchestra
   |
   |-- Footing (ABC)                     <- geometria
   |     |-- RectangularFooting
   |     |-- StripFooting
   |     +-- CircularFooting
   |
   |-- Soil           |
   |-- SoilProfile -- +-- SoilLayer      <- terreno (mono o stratigrafia)
   |
   |-- DesignActions                     <- V, H, M
   |-- SeismicAction                     <- kh, kv (opzionale)
   +-- DesignCode (ABC)                  <- strategia coefficienti parziali
         |-- EC7_DA1_C1/C2 / DA2 / DA3
         |-- NTC2018_A1 / A2
         +-- NTC2018_Seismic / _Reduced

Check (ABC)                              <- singole verifiche
   |-- BearingCheck                      <- formula Annex D + Paolucci-Pecker
   |-- SlidingCheck
   |-- OverturningCheck
   +-- SettlementCheck                   <- Bowles o Steinbrenner

VerificationReport                       <- raccoglie i risultati
```

## Esempio: fondazione su stratigrafia con falda, in zona sismica

```python
from ec7 import (
    RectangularFooting, Soil, SoilLayer, SoilProfile,
    DesignActions, SeismicAction, ShallowFoundation,
    NTC2018_Seismic_Reduced,
)

# Stratigrafia: 3 strati, falda a 3 m
profile = SoilProfile(
    layers=[
        SoilLayer(top=0, bottom=2.0,
                  soil=Soil(phi_k=28, c_k=0, gamma=18, gamma_sat=19.5,
                            E=15_000, name="Sabbia limosa")),
        SoilLayer(top=2.0, bottom=8.0,
                  soil=Soil(phi_k=34, c_k=0, gamma=19, gamma_sat=20,
                            E=30_000, name="Sabbia densa")),
        SoilLayer(top=8.0, bottom=30,
                  soil=Soil(phi_k=36, c_k=0, gamma=20, gamma_sat=21,
                            E=50_000, name="Ghiaia")),
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

## Note tecniche sulle estensioni v0.2

### Stratigrafia (`SoilProfile`)

- Profilo composto da `SoilLayer` contigui dall'alto verso il basso.
- Falda definita a una quota (`water_depth`) — gestita automaticamente
  nel calcolo di sigma totale e sigma' efficace, anche se attraversa più
  strati di pesi di volume diversi.
- **Soil equivalente nel volume di influenza**: per applicare la formula
  Annex D in stratigrafia, si costruisce un `Soil` equivalente mediando
  i parametri (phi, c, gamma, E) pesati sugli spessori intersecati dalla
  zona di influenza del cuneo di rottura, di estensione ~B sotto la base.
  Approccio semplice e diffuso; per stratigrafie molto contrastate si
  consiglia verifica con metodo a due strati (Meyerhof-Hanna) o FEM.
- Cedimento multistrato calcolato con **formula di Steinbrenner** integrata
  per strati, usando F1 e F2 al centro del rettangolo (Bowles 1996, §5-6).

### Sismica (`SeismicAction`)

Due effetti distinti, entrambi gestiti:

1. **Effetto inerziale sulla sovrastruttura**: H e M passati in
   `DesignActions` riducono la capacità portante attraverso i fattori
   di inclinazione ic, iq, igamma già presenti in Annex D.
2. **Effetto inerziale sul cuneo di rottura**: i fattori z di
   **Paolucci & Pecker (1997)** moltiplicano i tre termini della formula:

       z_q = z_gamma = (1 - kh / tan(phi))^0.35
       z_c           = 1 - 0.32 * kh        (caso non drenato)

- `kv` modifica il peso di volume nel termine N_gamma e riduce V nella
  verifica a scorrimento.
- Coerentemente con NTC 2018 §7.11.5.3.1, si offrono due opzioni:
  - `NTC2018_Seismic`: gamma_Rv = 2.3 (come statico)
  - `NTC2018_Seismic_Reduced`: gamma_Rv = **1.8**, ammesso solo se nel
    calcolo di R_k si tengono in conto esplicitamente gli effetti
    inerziali (cioè si passa una `SeismicAction` con kh > 0).

### Convenzioni

- Forze in **kN**, momenti in **kN·m**, lunghezze in **m**, pressioni in **kPa**.
- Asse **x** parallelo a B (lato corto), asse **y** parallelo a L.
- M_x produce eccentricità lungo L (e_L = M_x/V).
- M_y produce eccentricità lungo B (e_B = M_y/V).
- Le azioni vanno passate **caratteristiche**; in combinazione statica i
  coefficienti A vengono applicati dalla `DesignCode`; in combinazione
  sismica i coefficienti A sono unitari (NTC 2018 §7.11.1).

## Test

```bash
pytest tests/ -v
```

25 test che coprono: fattori N vs letteratura, formula Annex D drenata/non
drenata, eccentricità Meyerhof, severità relativa degli approcci
normativi, pressioni sigma e sigma' in stratigrafia con falda,
equivalent_soil pesato, fattori sismici Paolucci-Pecker, cedimenti
Steinbrenner monostrato e multistrato, report integrato sismico +
stratigrafia + falda.

## Limiti noti / sviluppi futuri

- **Capacità portante a due strati contrastati** (es. argilla soffice
  sopra sabbia densa): la media pesata può dare risultati ottimistici.
  Per casi critici occorre il metodo di Meyerhof-Hanna o punching shear.
- **Cedimento di consolidazione e secondario** non inclusi (solo elastico
  immediato).
- **Fattori sismici alternativi** (Maugeri, Richards, Cascone-Carrubba):
  estendibile da `SeismicAction.seismic_factors` cambiando `method`.
- **Approccio prestazionale sismico** (Pecker 2017, displacement-based):
  fuori scope.
- **Verifica EQU specifica con coefficienti dedicati** (gamma_G,dst=1.1,
  gamma_G,stb=0.9): attualmente si usano i coefficienti della DesignCode
  corrente con `favorable=True/False`.
