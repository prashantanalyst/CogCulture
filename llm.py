from __future__ import annotations
import random
import time
import anthropic
from . import config

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}


def make_client(api_key: str):
    return anthropic.Anthropic(api_key=api_key, max_retries=0, timeout=120.0)


def _retryable(e: Exception) -> bool:
    if isinstance(e, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    return isinstance(e, anthropic.APIStatusError) and e.status_code in RETRY_STATUS


def call_with_retry(fn, *, tries: int = config.MAX_RETRIES, sleep=time.sleep):
    """Run fn(); retry transient API failures with jittered exponential backoff."""
    for attempt in range(tries):
        try:
            return fn()
        except Exception as e:
            if not _retryable(e) or attempt == tries - 1:
                raise
            sleep(min(30, 2 ** attempt) + random.random())


def friendly_error(e: Exception) -> str:
    if isinstance(e, anthropic.AuthenticationError):
        return "The API key was rejected. Check ANTHROPIC_API_KEY."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "The API key does not have permission for this request."
    if isinstance(e, anthropic.RateLimitError):
        return "Rate limit or credit limit reached. Wait a minute or check API credits."
    if isinstance(e, anthropic.BadRequestError) and "credit" in str(e).lower():
        return "API credits appear to be exhausted."
    if isinstance(e, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return "Network problem reaching the API."
    return f"{type(e).__name__}: {str(e)[:200]}"
