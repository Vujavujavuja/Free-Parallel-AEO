# Free-Parallel-AEO

An open-source, self-hostable AI brand-visibility scanner. You enter a company
profile, an orchestrator model generates a set of realistic buyer questions, the
backend sends those questions to many models in parallel through OpenRouter, and
the answers are analyzed into a report: which models mention the brand, in which
questions, with what sources, how competitors compare, and whether visibility is
organic or search-driven.

It does what a number of paid AEO/brand-visibility tools do. The underlying
architecture is straightforward, so this exists to run the same analysis locally
for the cost of the model calls alone.

## What it produces

Each run generates:

- An **XLSX workbook** (8 sheets: overview, question aggregate, mention heatmap,
  sources by model and question, domain frequency, competitor share-of-voice,
  search queries, insights and quotes).
- A **CSV** (one row per model answer).
- A **JSON** file (the full structured run).

Runs are also viewable in the web UI and stored on disk so they persist between
restarts.

## Requirements

- **Python 3.11 or newer.** This is the only hard requirement to start.
- **An OpenRouter API key**, for runs against real models. Create one at
  <https://openrouter.ai/keys>. A run across a panel of frontier models typically
  costs about $0.50–$5 depending on the models and options chosen. You can enter
  the key in the web UI or place it in a `.env` file.
- **No Node.js required.** The web UI ships pre-built. Node is only needed if you
  intend to modify the frontend.

There is also a built-in offline **stub provider** that runs the entire pipeline
without an API key and at zero cost. It is intended for trying the tool and for
tests, not for real analysis.

## Setup and running

Clone the repository and run the single entry point:

```bash
git clone https://github.com/Vujavujavuja/Free-Parallel-AEO.git
cd Free-Parallel-AEO
python run.py
```

`run.py` is self-contained. On first run it creates a virtual environment
(using `uv` if available, otherwise `venv` + `pip`), installs dependencies,
prepares the local data directory, starts the server, and opens the browser.
Subsequent runs skip the steps already completed. The default address is
<http://127.0.0.1:8000>.

### Providing the API key

Either:

- In the web UI, open **Run options → OpenRouter API key**, paste the key, and
  save. It is validated against OpenRouter and written to `.env`.
- Or create a `.env` file before starting:

  ```
  OPENROUTER_API_KEY=sk-or-...
  ```

The key is stored only in the local `.env` file (which is git-ignored) and is
never logged or sent anywhere except OpenRouter.

### Running a scan from the UI

1. Fill in the company profile (name, website, competitors, and so on).
2. Optionally upload supporting documents (`.docx`, `.pdf`, `.md`, `.txt`); their
   text is passed to the orchestrator as context.
3. Optionally add exact questions of your own (they run verbatim; the orchestrator
   fills the remainder up to the requested count).
4. Select the models. With a key set, the OpenRouter catalogue loads and can be
   searched and filtered.
5. Run the scan, watch progress, then review the dashboard and download the
   report files.

## Command line

The same functionality is available headlessly, which is useful for automation.

```bash
# Diagnostics: Python version, key presence, storage location.
python -m aeo doctor

# List the available OpenRouter models.
python -m aeo models

# Run a scan from a profile file and write reports to a directory.
python -m aeo scan --company examples/acme.yaml --out ./reports

# Run the same scan offline with the stub provider (no key, no cost).
python -m aeo scan --company examples/acme.yaml --stub --out ./reports

# List and inspect past runs.
python -m aeo runs list
python -m aeo runs show <run-id>

# Serve the UI without the full bootstrap, on a specific port.
python -m aeo serve --port 8080
```

An example profile is provided at `examples/acme.yaml`.

## Configuration

Non-secret defaults are in `config/default.toml` and can be overridden by
environment variables (or entries in `.env`). The main options:

| Variable              | Default                       | Purpose                                        |
| --------------------- | ----------------------------- | ---------------------------------------------- |
| `OPENROUTER_API_KEY`  | (none)                        | Required for real runs.                        |
| `ORCHESTRATOR_MODEL`  | `anthropic/claude-opus-4.8`   | Model used to generate the question set.       |
| `ENABLE_WEB_SEARCH`   | `false`                       | Allow OpenRouter web search during answers.    |
| `PROMPT_MODE`         | `single_shot`                 | `single_shot` or `per_question`.               |
| `MAX_TOKENS`          | `8000`                        | Per-response token cap.                         |
| `CONCURRENCY`         | `6`                           | Maximum simultaneous model calls.              |
| `COST_CAP_USD`        | `5.00`                        | Abort the run if spend exceeds this.           |
| `DATA_DIR`            | `./data`                      | Where runs are stored.                          |
| `HOST` / `PORT`       | `127.0.0.1` / `8000`          | Server bind address.                            |
| `API_TOKEN`           | (unset)                       | Optional bearer token to protect the API.      |

## Data and privacy

All data stays on the machine that runs the tool. Company profiles, uploaded
document text, model answers, and generated reports are written to `./data/runs/`
(one folder per run) and `./reports/`. Both directories, along with `.env`, are
git-ignored and are never committed or transmitted. To remove a run, delete its
folder under `./data/runs/`.

## Development

For working on the code:

```bash
make dev        # install package and dev dependencies (editable)
make lint       # ruff
make typecheck  # mypy --strict
make test       # pytest
make build      # rebuild the frontend into src/aeo/web/dist
```

The backend is FastAPI (Python); the frontend is React with Vite and is served
as static files by the backend. Analysis is deterministic and covered by tests.

## License

MIT. See [LICENSE](LICENSE).
