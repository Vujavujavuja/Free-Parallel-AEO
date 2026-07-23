# Security Policy

## Supported versions

Parallel-AEO is pre-1.0 and moves quickly. Security fixes land on the latest
release and `main`.

| Version | Supported |
| ------- | --------- |
| 0.1.x   | ✅        |
| < 0.1   | ❌        |

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for a
vulnerability.

1. Preferred: use GitHub's private vulnerability reporting on this repository —
   the **Security** tab → **Report a vulnerability**. This opens a private
   advisory visible only to the maintainers.
2. If that isn't available, open a minimal public issue that says only "security
   report — please enable private reporting" (no details), and the maintainers
   will follow up.

Please include, where possible: affected version/commit, steps to reproduce,
impact, and any suggested fix. We aim to acknowledge reports within a few days
and to coordinate a fix and disclosure timeline with you.

## Scope and good to know

Parallel-AEO is a local, self-hosted tool. A few things that shape its threat
model:

- **Your data leaves your machine when you run a scan.** Company profiles,
  questions, uploaded document text, and the resulting answers are sent to the
  OpenRouter API and the selected models. Everything else stays local.
- **The only secret is `OPENROUTER_API_KEY`.** It is read from the environment /
  a gitignored `.env`, is never written to run records or logs, and is sent only
  to OpenRouter over TLS.
- **Run data is stored unencrypted on disk** under `./data/runs/` (gitignored).
- **The optional `API_TOKEN`** gates the REST API when you expose it beyond
  localhost; there is no other authn/authz.
- Report cells are sanitized against CSV/formula injection from model output.

If you deploy this beyond your own machine, put it behind your own
authentication and TLS, and set `API_TOKEN`.
