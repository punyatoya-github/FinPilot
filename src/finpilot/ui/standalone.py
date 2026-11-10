"""Run the dashboard against a remote FinPilot API: finpilot-ui --api-url http://host:8000"""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from finpilot.ui.backends import HttpBackend
from finpilot.ui.dashboard import build_dashboard


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="finpilot-ui", description=__doc__)
    parser.add_argument(
        "--api-url", default=os.environ.get("FINPILOT_API_URL", "http://127.0.0.1:8000")
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args(argv)
    build_dashboard(HttpBackend(args.api_url)).launch(server_name=args.host, server_port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
