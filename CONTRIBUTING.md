# Contributing to Parallel-AEO

Thanks for your interest in improving Parallel-AEO. This is a small, focused
project — contributions that keep it that way are very welcome.

## Getting set up

You need Python 3.11+. Node is only needed if you change the frontend.

```bash
git clone https://github.com/Vujavujavuja/Parallel-AEO.git
cd Parallel-AEO
make dev          # install the package + dev dependencies (editable)
```

`make dev` uses `uv` if it's installed, otherwise `pip`. To run the app while
developing:

```bash
python run.py           # bootstrap + serve the UI at http://127.0.0.1:8000
# or, without the full bootstrap:
python -m aeo serve
```

## Before you open a pull request

Run the same checks CI runs — all must pass:

```bash
make lint         # ruff
make typecheck    # mypy --strict
make test         # pytest
```

If you touch the frontend:

```bash
make build        # rebuild the SPA into src/aeo/web/dist (commit the dist)
cd frontend && npm run test
```

The prebuilt SPA under `src/aeo/web/dist` is committed so end users don't need
Node — please rebuild and commit it when you change the frontend.

## Conventions

- **Typed and linted.** `mypy --strict` and `ruff` must be clean. Public
  functions are typed; imports stay layered (`api → services → core/analysis/
  reports → providers/storage`), no upward deps.
- **`src/` layout.** The package lives in `src/aeo/`.
- **Deterministic analysis.** Everything in `aeo/analysis/` is pure and
  reproducible — no network calls, no randomness. Test analyzers against
  fixtures, not live model output.
- **Providers, analyzers, and report formats sit behind interfaces** so they're
  easy to add. New OpenRouter behaviour goes in `providers/`, new report formats
  in `reports/`.

## What gets merged

Happy to take:

- Bug fixes (ideally with a regression test).
- New report formats, analyzers, or providers behind the existing interfaces.
- Documentation and DX improvements.
- New buyer-question categories / prompt refinements — with a note on why.

Please **open an issue first** for larger changes (new dependencies, schema
changes, big features) so we can agree on the approach before you build it.

Every code change should keep the test suite green and add tests for new
behaviour. Analysis changes should include a golden/fixture test.

## Reporting bugs

Use the bug report template — it asks for your Python version, OS, and the
output of `python -m aeo doctor`, which resolves most environment issues quickly.
