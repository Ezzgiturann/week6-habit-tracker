#!/usr/bin/env bash
# Guardrails: run every deterministic check. Exits non-zero on the first failure,
# so the same script works locally and in CI.
set -euo pipefail
cd "$(dirname "$0")"

echo "==> ruff check (lint)"
ruff check .

echo "==> black --check (format)"
black --check .

echo "==> pytest (tests)"
pytest

echo "All checks passed."
