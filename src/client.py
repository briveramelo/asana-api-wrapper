from __future__ import annotations
import time
import logging
from typing import Callable, Any
import asana
from .config import get_settings

logger = logging.getLogger(__name__)


def get_client() -> asana.Client:
    settings = get_settings()
    client = asana.Client.access_token(settings.access_token)
    client.options["headers"] = {
        **client.options.get("headers", {}),
        "User-Agent": "asana-json-provisioner/0.1.0",
    }
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    return client


def _with_backoff(fn: Callable[..., Any], *args, **kwargs) -> Any:
    """Run an Asana SDK call with simple 429 backoff."""
    max_attempts = 5
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # Broad to avoid tight coupling to SDK exceptions
            # Try to detect 429 and Retry-After
            retry_after = None
            status = getattr(getattr(e, "response", None), "status", None) or getattr(e, "status", None)
            headers = getattr(getattr(e, "response", None), "headers", None) or getattr(e, "headers", {})
            if isinstance(headers, dict):
                retry_after = headers.get("Retry-After")

            if str(status) == "429" or retry_after:
                sleep_for = float(retry_after) if retry_after else delay
                logger.warning("Rate limit hit (attempt %s/%s). Sleeping for %.2fs...", attempt, max_attempts, sleep_for)
                time.sleep(sleep_for)
                delay = min(delay * 2, 8)
                continue
            logger.error("Asana API error: %s", e)
            raise
    raise RuntimeError("Exceeded max retry attempts for Asana API call")