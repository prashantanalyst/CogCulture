import anthropic
import pytest
from factcheck.llm import call_with_retry, friendly_error
from .helpers import api_error


def test_retries_then_succeeds():
    n = {"i": 0}; slept = []
    def fn():
        n["i"] += 1
        if n["i"] < 3:
            raise api_error(anthropic.RateLimitError, 429)
        return "ok"
    assert call_with_retry(fn, sleep=slept.append) == "ok" and len(slept) == 2


def test_gives_up_after_tries():
    slept = []
    with pytest.raises(anthropic.RateLimitError):
        call_with_retry(lambda: (_ for _ in ()).throw(api_error(anthropic.RateLimitError, 429)), tries=3, sleep=slept.append)
    assert len(slept) == 2


def test_non_retryable_raises_immediately():
    slept = []
    with pytest.raises(anthropic.AuthenticationError):
        call_with_retry(lambda: (_ for _ in ()).throw(api_error(anthropic.AuthenticationError, 401)), sleep=slept.append)
    assert slept == []


def test_retries_overloaded_529_and_connection():
    n = {"i": 0}
    def fn():
        n["i"] += 1
        if n["i"] == 1:
            raise api_error(anthropic.APIStatusError, 529)
        if n["i"] == 2:
            raise api_error(anthropic.APIConnectionError)
        return 1
    assert call_with_retry(fn, sleep=lambda s: None) == 1


def test_friendly_errors():
    assert "key" in friendly_error(api_error(anthropic.AuthenticationError, 401)).lower()
    assert "limit" in friendly_error(api_error(anthropic.RateLimitError, 429)).lower()
    assert "Network" in friendly_error(api_error(anthropic.APIConnectionError))
