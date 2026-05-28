#!/bin/bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head

# Set RELOAD=true for development to auto-reload on code changes.
# Leave unset (default) in production.
if [ "$RELOAD" = "true" ]; then
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
  uvicorn app.main:app --host 0.0.0.0 --port 8000
fi