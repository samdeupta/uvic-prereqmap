from __future__ import annotations

import re
from bs4 import Tag

from shared.errors import ParseError
from .prereq_parser import (
    PrereqParser,
    SELECT_ANY_N,
    TYPE_COURSE,
    KEY_LOGIC,
    KEY_CHILDREN,
    KEY_N,
    KEY_TYPE,
    KEY_CODE,
    _extract_course_codes
)


# ----- Regexes --------------------
_COREQ_N_OF_RE = re.compile(r"concurrently\s+enrolled\s+in\s+<span>(\d+)</span>\s+of\s*:", re.IGNORECASE)


# ----- CoreqParser --------------------
class CoreqParser(PrereqParser):
    # ----- Private Methods --------------------
    def _parse_result_div(self, result_div: Tag) -> dict:
        """
        Level 4: Base Case
        ------------------

        Extends `PrereqParser._parse_result_div()` to handle coreq-specific result div patterns.
        Unrecognised patterns are delegated to the parent.

        Pattern to node type mapping:
        - "Completed or concurrently enrolled in `N` of: [`COURSES`]"    -> ANY [COURSES]
        - "Completed or concurrently enrolled in all of: [`COURSES`]"    -> ALL [COURSES]  (parsed by PrereqParser)
        - All other patterns                                             -> Delegated to parent

        Raises `ParseError` if the result div is empty or cannot be parsed.
        """

        raw = str(result_div)

        # CASE: ANY [COURSES]
        m = _COREQ_N_OF_RE.search(raw)

        if m:
            n     = int(m.group(1))
            codes = _extract_course_codes(result_div)

            if not codes:
                raise ParseError(f"(Level 4) Expected course codes for ANY node in: {result_div}")

            return {
                KEY_LOGIC    : SELECT_ANY_N,
                KEY_N        : n,
                KEY_CHILDREN : [{KEY_TYPE: TYPE_COURSE, KEY_CODE: c} for c in codes],
            }

        # DEFAULT: Delegate all remaining patterns to PrereqParser
        return super()._parse_result_div(result_div)