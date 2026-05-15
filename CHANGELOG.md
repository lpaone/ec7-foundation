# Changelog

All notable changes to this project are documented in this file. The
format is inspired by [Keep a Changelog](https://keepachangelog.com/)
and the project follows [SemVer](https://semver.org/).

## [0.2.1] - 2026-05-15

### Changed
- Translated all source docstrings and inline comments to English, in
  Google style (`Args:` / `Returns:` / `Raises:` / `Attributes:`).
- Translated README, CHANGELOG and PUBLISHING to English. User-facing
  report strings remain Italian.

## [0.2.0] - 2026-05-14

### Added
- `SoilProfile` with `SoilLayer` for multi-layer profiles.
- Explicit groundwater handling with total sigma and effective sigma'
  computation across layers of different unit weights.
- `SeismicAction` with Paolucci & Pecker (1997) factors on the three
  terms of the bearing-capacity formula.
- New `DesignCode`s: `NTC2018_Seismic`, `NTC2018_Seismic_Reduced` (γR=1.8,
  NTC 2018 §7.11.5.3.1), `EC7_Seismic_DA2`.
- Multilayer settlement via the Steinbrenner formula (Bowles 1996 §5-6).
- `ec7-verify` CLI with YAML/JSON input.
- 15 new tests for profile, water, seismic and Steinbrenner.

### Changed
- `ShallowFoundation` now accepts `profile` and `seismic` as optional
  arguments. **Backward compatible** with v0.1 usage.

## [0.1.0] - 2026-05-14

### Added
- Static checks for bearing capacity (EN 1997-1 Annex D, Vesic formula),
  sliding, overturning, single-layer elastic settlement.
- Support for rectangular, strip and circular footings.
- Two-axis eccentricity (Meyerhof method).
- Design approaches EC7 DA1-C1, DA1-C2, DA2, DA3; NTC 2018 A1 and A2.
- 10 validation tests.
