"""Uvicorn entry shim for tooling that expects a root-level main:app module
(e.g. `hermes verify` recipe detection). The canonical app lives in
apps.api.main.
"""

from apps.api.main import app

__all__ = ["app"]
