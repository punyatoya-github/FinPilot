from __future__ import annotations

import re

from finpilot.core.errors import InvalidTickerError

_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def normalize_ticker(raw: str) -> str:
    """Uppercase/strip a ticker and validate it. Guards against injection into URLs/prompts."""
    symbol = raw.strip().upper()
    if not _TICKER_RE.fullmatch(symbol):
        raise InvalidTickerError(raw)
    return symbol
