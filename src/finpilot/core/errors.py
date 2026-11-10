"""Domain exceptions. The API layer maps these to HTTP status codes in Sprint 2."""


class FinPilotError(Exception):
    """Base class for all FinPilot errors."""


class InvalidTickerError(FinPilotError):
    def __init__(self, ticker: str) -> None:
        super().__init__(f"Invalid ticker: {ticker!r}")
        self.ticker = ticker


class TickerNotFoundError(FinPilotError):
    def __init__(self, ticker: str) -> None:
        super().__init__(f"No data found for ticker {ticker!r}")
        self.ticker = ticker


class DataProviderError(FinPilotError):
    """The upstream market data provider failed."""


class InsufficientDataError(FinPilotError):
    """Not enough fundamentals available to produce a score."""
