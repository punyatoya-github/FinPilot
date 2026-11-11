"""ASGI entry point: `uvicorn finpilot.asgi:app`.

Importing this module builds the real app (database, providers, dashboard), so only
uvicorn and `python -m finpilot` should import it. Tests use `finpilot.main.create_app`.
"""

from finpilot.main import create_app

app = create_app()
