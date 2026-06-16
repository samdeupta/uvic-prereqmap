from __future__ import annotations

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from shared.http_client import HTTPClient
from shared.endpoints import (
    CALENDAR_URL,
    subject_codes_url,
    all_courses_url,
    course_detail_url
)
from shared.errors import InformationFetchError


# ----- Regexes --------------------
_HEX24_VALIDATION_RE    = re.compile(r'^[0-9a-f]{24}$', re.IGNORECASE)
_HEX24_SEARCH_RE        = re.compile(r'[0-9a-f]{24}', re.IGNORECASE)
_EXTRACT_CATALOG_ID_RE  = re.compile(r'''window\.catalogId\s*=\s*['"]([0-9a-f]{24})['"]''',
                                     re.IGNORECASE)


# ----- Constants --------------------
FETCH_WORKER_COUNT = 20


# ----- Data Classes --------------------
@dataclass
class Subject:
    code        : str
    name        : str


    def __str__(self):
        return f"({self.code}, {self.name})"


@dataclass
class Course:
    code                : str
    name                : str
    credits             : float
    prereq_html         : str | None
    coreq_html          : str | None
    conflict_html       : str | None


    def __str__(self):
        return f"({self.code}, {self.name}, {self.credits}, has_prereq={self.prereq_html is not None}, has_coreq={self.coreq_html is not None}, has_conflict={self.conflict_html is not None})"


# ----- Course Info Data Fetcher --------------------
class CourseInfoFetcher:
    def __init__(self, client: HTTPClient):
        """
        Fetches raw course data from the UVic Kuali API.

        Responsibilities:
        - Scraping the latest catalog ID from the UVic calendar page.
        - Fetching the list of all subjects (subject codes and names).
        - Fetching the list of all courses.
        - Fetching the no. of credits and raw prereq/coreq/conflict HTML for each course.

        :param client: Shared HTTP client instance.
        """

        self._client        = client
        self._catalog_id    : str | None = None

        self._fetch_catalog_id()


    # ----- Private Methods--------------------
    def _is_valid_catalog_id(self, s: str) -> bool:
        """
        Returns True if the string is a valid 24-character hex catalog ID.

        :param s: String to validate.
        """

        return bool(_HEX24_VALIDATION_RE.match(s))
    

    def _fetch_course_details(self, pid: str) -> tuple[float, str | None, str | None, str | None]:
        """
        Fetches the credits and raw prereq, coreq, and credit conflict HTML for a specific course.

        Kuali API raw JSON return format:
            {
                "credits": {"credits": {"min":`MIN_CREDITS`, "max": `MAX_CREDITS`}},
                "preAndCorequisites": `PREREQ_RAW_HTML`,
                "preOrCorequisites":  `COREQ_RAW_HTML`,
                "supplementalNotes":  `CONFLICT_RAW_HTML`
            }
        
        The minimum credit value is used for the `credits` field.
        
        Return format:
            (`CREDITS`, `PREREQ_RAW_HTML`, `COREQ_RAW_HTML`, `CONFLICT_RAW_HTML`)

        :param pid: Kuali course PID.
        """

        url     = course_detail_url(self._catalog_id, pid)
        data    : dict = self._client.get_json(url)

        return (
            float(((data.get("credits") or {}).get("credits") or {}).get("min") or 0),
            data.get("preAndCorequisites") or None,
            data.get("preOrCorequisites")  or None,
            data.get("supplementalNotes")  or None,
        )
    

    def _fetch_catalog_id(self):
        """
        Scrapes the UVic calendar page to extract the latest catalog ID.
        Stores it internally for use in subsequent requests.

        Raises `InformationFetchError` if the catalog ID cannot be found.
        """

        html = self._client.get_text(CALENDAR_URL)

        # Primary: Look for explicit window.catalogId assignment in the page HTML
        m = _EXTRACT_CATALOG_ID_RE.search(html)
        if m and self._is_valid_catalog_id(m.group(1)):
            self._catalog_id = m.group(1)
            return

        # Fallback: Look for any 24-character hex string in the page
        m = _HEX24_SEARCH_RE.search(html)
        if m and self._is_valid_catalog_id(m.group(0)):
            self._catalog_id = m.group(0)
            return

        raise InformationFetchError("Could not find a valid 24-hex catalog ID in the UVic calendar page.")
    

    def _fetch_one(self, args: tuple[int, dict], courses: list[Course | None], counter: list[int], 
                   lock: threading.Lock, total: int):
        """
        Worker function for `fetch_all_courses`. Extracts course fields from a raw Kuali API entry, 
        fetches its details, and writes the result to its pre-assigned index in `courses`. 
        
        Raises `InformationFetchError` if required fields are missing.

        `counter` is a single-element list used as a mutable integer across threads. It is incremented 
        under `lock` to protect against race conditions.

        Kuali API raw JSON return format:
            [{ "__catalogCourseId": `CODE`, "pid": `PID`, "title": `NAME` }, ...]

        :param args:    `(idx, entry)` tuple where `idx` is the course's position in
                        the original API response and `entry` is the raw Kuali dict.
        :param courses: Shared pre-allocated output list.
        :param counter: Single-element list holding the completed course count.
        :param lock:    Lock protecting `counter`.
        :param total:   Total number of entries, used for progress display.
        """

        self._client.register_thread()

        idx, entry = args

        code = (entry.get("__catalogCourseId") or "").strip().upper()
        name = (entry.get("title")             or "").strip()
        pid  = (entry.get("pid")               or "").strip()

        if not (code and name and pid):
            raise InformationFetchError(f"Kuali API response does not contain required fields: {entry}")

        credits, prereq_html, coreq_html, conflict_html = self._fetch_course_details(pid)

        courses[idx] = Course(
            code          = code,
            name          = name,
            credits       = credits,
            prereq_html   = prereq_html,
            coreq_html    = coreq_html,
            conflict_html = conflict_html
        )

        with lock:
            counter[0] += 1

            if counter[0] % 10 == 0:
                print(f"Scraped {counter[0]}/{total} courses ({int(counter[0] / total * 100)}%)")


    # ----- Public Methods --------------------
    def fetch_subjects(self) -> list[Subject]:
        """
        Fetches all subject codes and names from the UVic catalog API.

        Kuali API raw JSON return format:
            [{"subject": `CODE`, "title": "`NAME` (`CODE`)" }, ...]
        """

        url     = subject_codes_url(self._catalog_id)
        data    : list[dict] = self._client.get_json(url)

        subjects = []

        for entry in data:
            code    = (entry.get("subject") or "").strip().upper()
            title   = (entry.get("title")   or "").strip()

            if not code:
                continue

            # Strips the " (CODE)" suffix Kuali appends to every title
            name = title[:-(len(code) + 2)].rstrip()

            subjects.append(Subject(code=code, name=name))

        return subjects


    def fetch_all_courses(self) -> list[Course]:
        """
        Fetches all courses and their details from the Kuali catalog API using a thread pool of size 
        `FETCH_WORKER_COUNT`.

        Course order in the returned list is guaranteed to match the order returned by the Kuali API 
        regardless of thread scheduling. Each course is assigned a fixed index before threading begins 
        and written to that index on completion.
        """

        # Single-threaded section: Fetching the list of courses
        url     = all_courses_url(self._catalog_id)
        data    : list[dict] = self._client.get_json(url)
        total   = len(data)

        # Multi-threaded section: Fetching course details
        courses : list[Course | None] = [None] * total
        counter = [0]
        lock    = threading.Lock()

        print("Fetching course data from Kuali API...")

        with ThreadPoolExecutor(max_workers=FETCH_WORKER_COUNT) as executor:
            for i, entry in enumerate(data):
                executor.submit(self._fetch_one, (i, entry), courses, counter, lock, total)

        courses = [c for c in courses if c is not None]

        print(f"\nFetched {len(courses)} courses.\n")

        return courses