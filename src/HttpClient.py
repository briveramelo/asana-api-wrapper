import logging
import time
from typing import Optional, Callable

import requests

logger = logging.getLogger(__name__)


_ASANA_BASE_URL = "https://app.asana.com/api/1.0"
_USER_AGENT = "asana-json-provisioner/0.1.0"

class HttpClient:
    def __init__(self, access_token: str, default_timeout: float = 30.0) -> None:
        self.base = _ASANA_BASE_URL.rstrip("/")
        self.timeout = default_timeout
        self.sess = requests.Session()
        self.sess.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        })

    def request(self, method: str, path: str, *, params: Optional[dict] = None, json: Optional[dict] = None) -> dict:
        url = f"{self.base}/{path.lstrip('/')}"
        resp = self.sess.request(method, url, params=params, json=json, timeout=self.timeout)
        # Raise to trigger with_backoff logic on 4xx/5xx (including 429)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            # Attach response for the backoff helper to inspect
            e.response = resp
            raise
        payload = resp.json() if resp.content else {}
        # Asana wraps everything in {'data': ...}
        return payload.get("data", payload)

    # --- Add inside _HttpClient ---

    def _request_raw(self, method: str, path: str, *, params: Optional[dict] = None, json: Optional[dict] = None) -> dict:
        """Return the full JSON payload from Asana (including 'data' and 'next_page')."""
        url = f"{self.base}/{path.lstrip('/')}"
        resp = self.sess.request(method, url, params=params, json=json, timeout=self.timeout)
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            e.response = resp
            raise
        return resp.json() if resp.content else {}

    def request_paginated(self, method: str, path: str, *, params: Optional[dict] = None) -> list[dict]:
        """Accumulate all pages of results and return a flat list of items from 'data'."""
        items: list[dict] = []
        _params = dict(params or {})
        while True:
            # use the same backoff wrapper the rest of the client uses
            payload = with_backoff(self._request_raw, method, path, params=_params)
            page_items = payload.get("data", []) or []
            items.extend(page_items)
            next_page = payload.get("next_page") or {}
            offset = next_page.get("offset")
            if not offset:
                break
            _params["offset"] = offset
        return items


def with_backoff(fn: Callable[..., any], *args, **kwargs) -> any:
    """Run an HTTP call with simple 429 (rate-limit) backoff using Retry-After if present."""
    max_attempts = 5
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # keep broad to avoid coupling to 'requests' types elsewhere
            resp = getattr(e, "response", None)
            headers = getattr(resp, "headers", {}) or {}
            status = (
                    getattr(resp, "status", None)
                    or getattr(resp, "status_code", None)
                    or getattr(e, "status", None)
            )
            retry_after = headers.get("Retry-After")
            if str(status) == "429" or retry_after:
                # Respect server-provided Retry-After seconds when available
                sleep_for = float(retry_after) if retry_after else delay
                logger.warning("Rate limit hit (attempt %s/%s). Sleeping for %.2fs...", attempt, max_attempts, sleep_for)
                time.sleep(sleep_for)
                delay = min(delay * 2, 8.0)
                continue
            # Surface other HTTP errors
            logger.error("Asana API error: %s", e)
            raise
    raise RuntimeError("Exceeded max retry attempts for Asana API call")
