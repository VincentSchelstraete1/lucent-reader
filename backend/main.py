"""Compatibility entrypoint for local commands that still import ``main:app``.

The authoritative application lives in :mod:`app.main`. Keeping this module as
an alias prevents an outdated launch command from exposing legacy, unguarded
provider routes.
"""

from app.main import app

__all__ = ["app"]
