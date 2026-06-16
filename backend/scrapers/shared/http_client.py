from __future__ import annotations

import threading
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ----- Constants --------------------
REQUEST_TIMEOUT_SECS = 10
MAX_RETRIES = 4
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
REQUEST_DELAY_SECS = 0.7
DEFAULT_USER_AGENT = "UVic PrereqMap Data Scraper"


# ---- HTTP Client --------------------
class HTTPClient:
    def __init__(self,
                 user_agent       : str  = DEFAULT_USER_AGENT,
                 pool_connections : int  = 1,
                 pool_maxsize     : int  = 1,
                 multithreaded    : bool = False):
        """
        HTTP client with retry logic and polite rate limiting.

        Wraps `requests.Session` to add:
        - Exponential backoff retries for transient errors.
        - Shared session with connection pooling.
        - Minimum delay between requests to avoid hammering servers.

        Two delay modes are supported:
        - Single-threaded (default): One shared `_last_request_ts` enforces a global minimum delay of 
          `REQUEST_DELAY_SECS` between all requests.
        - Multi-threaded (`multithreaded=True`): Each thread maintains its own delay tracker via 
          `threading.local()`. Threads must call `register_thread()` before making their first request. 
          The delay is enforced independently per thread, allowing concurrent requests across threads to 
          different endpoints without global serialization.

        `pool_maxsize` should be set to match the number of concurrent threads when using multi-threaded 
        mode.

        Intended for use as a context manager:

            with HTTPClient() as client:
                response = client.get(url)
        """

        self._session         : requests.Session | None = None
        self._last_request_ts : float                   = 0.0
        self._multithreaded   : bool                    = multithreaded
        self._local           : threading.local         = threading.local()

        self._pool_connections = pool_connections
        self._pool_maxsize     = pool_maxsize
        self._user_agent       = user_agent


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
            "User-Agent":      self._user_agent,
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
        Enforces a minimum delay of `REQUEST_DELAY_SECS` before each request.

        Modes:
        ------
        - Single-threaded: Reads and updates the shared `_last_request_ts`.
        - Multi-threaded: Reads and updates the calling thread's own `_local.last_request_ts`, so 
          each thread enforces its delay independently without blocking other threads.
        """

        if self._multithreaded:
            if not hasattr(self._local, "last_request_ts"):
                raise RuntimeError("Thread has not been registered. "
                                   "Call register_thread() before making requests in multi-threaded mode.")
            
            last_ts: float = self._local.last_request_ts
        else:
            last_ts = self._last_request_ts

        elapsed = time.time() - last_ts

        if elapsed < REQUEST_DELAY_SECS:
            time.sleep(REQUEST_DELAY_SECS - elapsed)

        now = time.time()

        if self._multithreaded:
            self._local.last_request_ts = now
        else:
            self._last_request_ts = now


    # ----- Public Methods --------------------
    def register_thread(self):
        """
        Initialises a per-thread delay tracker for the calling thread.

        Must be called once per worker thread before its first request when using multi-threaded mode. 
        Raises `RuntimeError` if called in single-threaded mode.
        """

        if self._multithreaded:
            self._local.last_request_ts = 0.0
        else:
            raise RuntimeError("HTTPClient instance is in single threaded mode. "
                               "register_thread() should only be called in multi-threaded mode.")


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

        return response


    def get_text(self, url: str) -> str:
        """
        Fetches a URL and returns the response body as plain text.
        """

        return self.get(url).text


    def get_json(self, url: str) -> dict | list[dict]:
        """
        Fetches a URL and returns the response body as parsed JSON.
        """

        return self.get(url).json()


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