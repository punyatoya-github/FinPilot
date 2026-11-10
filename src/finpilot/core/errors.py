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


class LLMError(FinPilotError):
    """The report generator failed (API error, or no valid output after retries)."""


class ReportValidationError(FinPilotError):
    """LLM output parsed but violated content guardrails."""


class ReportNotFoundError(FinPilotError):
    def __init__(self, report_id: str) -> None:
        super().__init__(f"No report found with id {report_id!r}")
        self.report_id = report_id


class RateLimitedError(FinPilotError):
    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Rate limit exceeded. Try again in {max(1, round(retry_after))} seconds.")
        self.retry_after = retry_after
