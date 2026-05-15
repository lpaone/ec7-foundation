# Changelog

Tutti i cambiamenti rilevanti a questo progetto sono documentati in questo
file. Il formato si ispira a [Keep a Changelog](https://keepachangelog.com/)
e il progetto segue [SemVer](https://semver.org/).

## [0.2.0] - 2026-05-14

### Aggiunto
- `SoilProfile` con `SoilLayer` per stratigrafie a più strati.
- Gestione esplicita della falda con calcolo di sigma totale e sigma'
  efficace anche su strati di pesi di volume diversi.
- `SeismicAction` con fattori di Paolucci & Pecker (1997) sui tre termini
  della formula di capacità portante.
- Nuove `DesignCode`: `NTC2018_Seismic`, `NTC2018_Seismic_Reduced` (γR=1.8,
  NTC 2018 §7.11.5.3.1), `EC7_Seismic_DA2`.
- Cedimento multistrato con formula di Steinbrenner (Bowles 1996 §5-6).
- CLI `ec7-verify` con input YAML/JSON.
- 15 nuovi test per profilo, falda, sismica e Steinbrenner.

### Modificato
- `ShallowFoundation` ora accetta `profile` e `seismic` come argomenti
  opzionali. **Backward compatible** con l'uso v0.1.

## [0.1.0] - 2026-05-14

### Aggiunto
- Verifiche statiche di capacità portante (Annex D EN 1997-1, formula di
  Vesic), scorrimento, ribaltamento, cedimento elastico monostrato.
- Supporto per fondazioni rettangolari, nastriformi e circolari.
- Eccentricità su due assi (metodo di Meyerhof).
- Approcci di progetto EC7 DA1-C1, DA1-C2, DA2, DA3; NTC 2018 A1 e A2.
- 10 test di validazione.
