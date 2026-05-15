# Publishing ec7-foundation

Quick guide to publishing the package to PyPI with `uv`.

## 1. Prerequisites

- Accounts on [PyPI](https://pypi.org) and [TestPyPI](https://test.pypi.org).
- An **API token** for each (manage → "Account settings" → "API tokens").
  Initially scope it to the project alone if it already exists, or
  "entire account" for the first publication.
- `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`).

## 2. Bump the version

Edit the `version = "x.y.z"` string in `pyproject.toml` and update
`CHANGELOG.md`. Run the tests:

```bash
uv sync
uv run pytest
uv run ruff check .
```

## 3. Build the packages

```bash
rm -rf dist/
uv build
```

Produces two artefacts in `dist/`:

- `ec7_foundation-x.y.z-py3-none-any.whl`  (binary wheel)
- `ec7_foundation-x.y.z.tar.gz`             (source distribution)

## 4. Test on TestPyPI (recommended the first time)

```bash
uv publish --publish-url https://test.pypi.org/legacy/ \
    --token "pypi-XXXXXXXXXXXX..."
```

Verify by installing from TestPyPI in a clean venv:

```bash
uv venv /tmp/test-install
/tmp/test-install/bin/pip install \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    ec7-foundation
/tmp/test-install/bin/ec7-verify --version
```

## 5. Publish to PyPI

```bash
uv publish --token "pypi-XXXXXXXXXXXX..."
```

Alternatively, you can save the token in `~/.pypirc` and simply run
`uv publish`.

## 6. Git tag and release

```bash
git tag -a vx.y.z -m "Release x.y.z"
git push origin vx.y.z
```

Create a release on GitHub attaching the contents of the relevant
`CHANGELOG.md` section.

## Notes

- The name `ec7-foundation` must be available on PyPI. If it is not,
  change `name` in `pyproject.toml` (e.g. `ec7-foundation-yourname`).
- For CI/CD (GitHub Actions) you can use the official
  [`pypa/gh-action-pypi-publish`](https://github.com/pypa/gh-action-pypi-publish)
  action with OIDC/Trusted Publishing (no token).
