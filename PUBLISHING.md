# Publishing ec7-foundation

Guida rapida per pubblicare il pacchetto su PyPI con `uv`.

## 1. Prerequisiti

- Account su [PyPI](https://pypi.org) e [TestPyPI](https://test.pypi.org).
- Un **API token** per ciascuno dei due (gestione → "Account settings"
  → "API tokens"). Imposta lo scope inizialmente al solo progetto se
  esiste, o "entire account" per la prima pubblicazione.
- `uv` installato (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

## 2. Aggiornare la versione

Modifica la stringa `version = "x.y.z"` in `pyproject.toml` e
aggiorna il `CHANGELOG.md`. Esegui i test:

```bash
uv sync
uv run pytest
uv run ruff check .
```

## 3. Costruire i pacchetti

```bash
rm -rf dist/
uv build
```

Produce due artefatti in `dist/`:

- `ec7_foundation-x.y.z-py3-none-any.whl`  (wheel binario)
- `ec7_foundation-x.y.z.tar.gz`             (source distribution)

## 4. Test su TestPyPI (consigliato la prima volta)

```bash
uv publish --publish-url https://test.pypi.org/legacy/ \
    --token "pypi-XXXXXXXXXXXX..."
```

Verifica installando da TestPyPI in una venv pulita:

```bash
uv venv /tmp/test-install
/tmp/test-install/bin/pip install \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    ec7-foundation
/tmp/test-install/bin/ec7-verify --version
```

## 5. Pubblicazione su PyPI

```bash
uv publish --token "pypi-XXXXXXXXXXXX..."
```

In alternativa, puoi salvare il token in `~/.pypirc` e usare semplicemente
`uv publish`.

## 6. Tag git e release

```bash
git tag -a vx.y.z -m "Release x.y.z"
git push origin vx.y.z
```

Crea una release su GitHub allegando il contenuto della sezione del
`CHANGELOG.md`.

## Note

- Il nome `ec7-foundation` deve essere disponibile su PyPI. Se non lo è,
  cambia `name` in `pyproject.toml` (es. `ec7-foundation-yourname`).
- Per CI/CD (GitHub Actions) puoi usare l'azione ufficiale
  [`pypa/gh-action-pypi-publish`](https://github.com/pypa/gh-action-pypi-publish)
  con OIDC/Trusted Publishing (no token).
