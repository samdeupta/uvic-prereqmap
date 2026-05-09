from __future__ import annotations

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scrapers.shared.config import (
    REQUEST_TIMEOUT_SECS,
    REQUEST_DELAY_SECS,
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    RETRY_STATUS_CODES,
    DEFAULT_USER_AGENT,
)


class HTTPClient:
    def __init__(self,
                 pool_connections: int = 1,
                 pool_maxsize: int = 1):
        """
        HTTP client with retry logic and polite rate limiting.

        Wraps `requests.Session` to add:
        - Exponential backoff retries for transient errors.
        - Shared session with connection pooling.
        - Minimum delay between requests to avoid hammering servers.

        Intended for use as a context manager:

            with HTTPClient() as client:
                response = client.get(url)
        """

        self._session: requests.Session | None = None
        self._last_request_ts: float = 0.0

        self._pool_connections = pool_connections
        self._pool_maxsize     = pool_maxsize


    # ----- Private Methods --------------------
    def _build_retry(self) -> Retry:
        """
        Configures a `Retry` policy for GET requests.

        Policy:
        - Retries up to `MAX_RETRIES` times.
        - Waits with exponential backoff (factor = `RETRY_BACKOFF_FACTOR`).
        - Only retries on HTTP status codes listed in `RETRY_STATUS_CODES`.
        - Respects Retry-After headers from the server.
        """

        return Retry(
            total                      = MAX_RETRIES,
            backoff_factor             = RETRY_BACKOFF_FACTOR,
            status_forcelist           = RETRY_STATUS_CODES,
            allowed_methods            = {"GET"},
            raise_on_status            = False,
            respect_retry_after_header = True,
        )


    def _build_session(self) -> requests.Session:
        """
        Creates and configures a new `requests.Session` with retry logic
        mounted for both HTTP and HTTPS.
        """

        session = requests.Session()
        session.headers.update({
            "User-Agent":      DEFAULT_USER_AGENT,
            "Accept":          "application/json, text/html;q=0.9, */*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection":      "keep-alive",
        })

        adapter = HTTPAdapter(
            max_retries      = self._build_retry(),
            pool_connections = self._pool_connections,
            pool_maxsize     = self._pool_maxsize,
        )

        session.mount("http://",  adapter)
        session.mount("https://", adapter)

        return session


    def _polite_delay(self):
        """
        Enforces a minimum delay between requests.
        Sleeps only if less than `REQUEST_DELAY_SECS` has elapsed since the
        last request completed.
        """

        elapsed = time.time() - self._last_request_ts

        if elapsed < REQUEST_DELAY_SECS:
            time.sleep(REQUEST_DELAY_SECS - elapsed)

    
    # ----- Public Methods --------------------
    def get(self, url: str, **kwargs) -> requests.Response:
        """
        Performs a GET request with polite delay, retry, and timeout.
        Raises `requests.HTTPError` on 4xx/5xx responses.

        :param url:     URL to fetch.
        :param kwargs:  Additional keyword arguments passed to `session.get()`.
        """

        self._polite_delay()

        if self._session is None:
            self._session = self._build_session()

        response = self._session.get(url, timeout=REQUEST_TIMEOUT_SECS, **kwargs)
        response.raise_for_status()

        self._last_request_ts = time.time()  # Updated after request completes

        return response


    def close(self):
        """
        Closes the underlying session and resets client state.
        """

        if self._session is not None:
            self._session.close()
            self._session         = None
            self._last_request_ts = 0.0

    
    # ----- Context Manager --------------------
    def __enter__(self) -> HTTPClient:
        return self

    def __exit__(self, *args):
        self.close()