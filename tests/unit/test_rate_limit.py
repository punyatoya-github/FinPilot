import pytest

from finpilot.core.rate_limit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_allows_up_to_limit_then_blocks_with_retry_after() -> None:
    clock = Clock()
    limiter = RateLimiter(2, 60, clock)
    assert limiter.check("a") == 0.0
    clock.t += 10
    assert limiter.check("a") == 0.0
    wait = limiter.check("a")
    assert wait == pytest.approx(50.0)  # oldest hit (t=1000) frees at t=1060


def test_window_slides() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    assert limiter.check("a") == 0.0
    assert limiter.check("a") > 0
    clock.t += 60.1
    assert limiter.check("a") == 0.0


def test_blocked_hits_do_not_extend_the_block() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    limiter.check("a")
    for _ in range(5):
        clock.t += 5
        assert limiter.check("a") > 0
    clock.t = 1060.5
    assert limiter.check("a") == 0.0


def test_keys_are_independent() -> None:
    limiter = RateLimiter(1, 60, Clock())
    assert limiter.check("a") == 0.0
    assert limiter.check("b") == 0.0
    assert limiter.check("a") > 0


@pytest.mark.parametrize("limit", [0, -1])
def test_non_positive_limit_disables(limit: int) -> None:
    limiter = RateLimiter(limit, 60, Clock())
    assert not limiter.enabled
    assert all(limiter.check("a") == 0.0 for _ in range(100))
