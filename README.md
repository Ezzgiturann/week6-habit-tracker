# Starter — Habit Tracker

A tiny FastAPI + SQLite service for habits and daily check-ins. You'll add two features
on branches, open PRs, and run an AI reviewer.

## Setup
```bash
pip install -r requirements-dev.txt   # app deps + black + ruff
pytest                                # 3 tests should pass
uvicorn main:app --reload             # http://localhost:8000  (docs at /docs)
```

## Guardrails
Run all checks with one command. It stops at the first failure and exits non-zero:
```bash
./check.sh
```

| Step | Command | What it catches |
|---|---|---|
| Lint | `ruff check .` | Unused imports, undefined names, import order, likely bugs (bugbear), outdated syntax, lines over 88 chars |
| Format | `black --check .` | Any file not in Black's canonical format (fix with `black .`) |
| Tests | `pytest` | Behavior regressions; one failing test fails the whole build |

The same script runs in GitHub Actions (`.github/workflows/ci.yml`) on every push to
`main` and on every pull request, so a PR cannot look green while a check fails.
Config lives in `pyproject.toml`.

**Verified:**
- The unmodified starter failed both linters: `ruff` reported 2 × E501 (lines over 88
  chars) in `main.py`, and `black --check` would reformat `main.py`. Running `black .`
  fixed both.
- Adding a deliberately failing test (`assert 1 + 1 == 3`) made `./check.sh` exit with
  code 1 (`1 failed, 3 passed`). Removing it brought the exit code back to 0.

## Endpoints
- `POST /habits` `{ "name": ... }`
- `GET /habits`
- `POST /habits/{id}/checkin` `{ "day": "2026-09-22" }`
- `GET /habits/{id}/checkins`

## Files
- `main.py` — the app
- `test_main.py` — pytest suite
- `check.sh`, `pyproject.toml`, `requirements-dev.txt`, `.github/workflows/ci.yml` — guardrails
- `docs/TASKS.md` — the two features to implement
