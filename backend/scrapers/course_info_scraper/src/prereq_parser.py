from __future__ import annotations

import re
from bs4 import BeautifulSoup, Tag

from shared.errors import ParseError


# ----- Regexes --------------------
# To search against raw HTML
_COMPLETE_ALL_OF_RE  = re.compile(r"Complete\s+all\s+of\s*:",                  re.IGNORECASE)
_COMPLETE_N_OF_RE    = re.compile(r"Complete\s+<span>\d+</span>\s+of\s*:",     re.IGNORECASE)
_COMPLETE_N_UNITS_RE = re.compile(r"Complete\s+<span>[\d.]+</span>\s+units",   re.IGNORECASE)
_CONCURRENTLY_RE     = re.compile(r"concurrently\s+enrolled",                  re.IGNORECASE)

# To search against compressed <span> text with whitespace and comment artifacts removed
_WRAPPER_ALL_RE      = re.compile(r"Completeallof",                            re.IGNORECASE)
_WRAPPER_N_RE        = re.compile(r"Complete(\d+)of",                          re.IGNORECASE)

# Course/subject code patterns
_COURSE_CODE_RE      = re.compile(r"^[A-Z]{2,4}-?[A-Z]?\d{3}[A-Z]?$")
_SUBJECT_CODE_RE     = re.compile(r"\b[A-Z]{2,4}(?:-[A-Z])?\b")

# Extracts the units for UFS type
_UFS_UNITS_RE        = re.compile(r"([\d.]+)\s+units",                         re.IGNORECASE)

# Level range info patterns 
_UFS_LVL_RANGE_RE    = re.compile(r"(\d{3})-\s*or\s+(\d{3})-level",            re.IGNORECASE)  # "X- or Y-level"
_UFS_LVL_ONLY_RE     = re.compile(r"(\d{3})-level",                            re.IGNORECASE)  # "X-level"
_UFS_LVL_NOHYPH_RE   = re.compile(r"(\d{3})\s+level",                          re.IGNORECASE)  # "X level"
_UFS_LVL_OPEN_RE     = re.compile(r"(\d{3})-\s+\w",                            re.IGNORECASE)  # "X-"

# Composite UFS pattern
_UFS_COMPOSITE_RE    = re.compile(
    r"^([A-Z]{2,4}\s+\d{3}[A-Z]?)\s+and\s+([\d.]+\s+units\s+of\s+.+)$",        re.IGNORECASE)  # "COURSE_CODE and N units of [SUBJECTS] courses"

# English words that match subject code regex but are not subject codes
_SUBJ_STOPWORDS = frozenset({
    "OR", "AND", "THE", "ANY", "WITH", "OF", "IN", "AT", "TO", "A", "GPA", "AWR"})

# Patterns explicitly excluded from UFS type
_UFS_EXCLUSION_RE = re.compile(
    r"gpa|grade|numbered|excluding|units\s+of\s+(?:\d{3}-?\s*(?:or\s+\d{3}-)?level\s+)?courses\s+with",
    re.IGNORECASE)


# ----- Schema Keys --------------------
# Logic node keys
SELECT_ALL   = "ALL"
SELECT_ANY_N = "ANY"

# Base node type values
TYPE_COURSE              = "course"
TYPE_UNITS_FROM_COURSE   = "units_from_course"      # UFC
TYPE_UNITS_FROM_SUBJECT  = "units_from_subject"     # UFS
TYPE_TEXT                = "text"

# Output dict keys
KEY_LOGIC     = "logic"
KEY_CHILDREN  = "children"
KEY_N         = "n"
KEY_TYPE      = "type"
KEY_CODE      = "code"
KEY_UNITS     = "units"
KEY_COURSES   = "courses"
KEY_SUBJECTS  = "subjects"
KEY_LVL_RANGE = "lvl_range"
KEY_TEXT      = "text"


# ----- Helper Methods --------------------
def _get_span_int(tag: Tag) -> int:
    """
    Extracts integer from inside first `<span>` tag.
    Raises `ParseError` if `<span>` tag is not found or if its text cannot be parsed as an integer.
    """

    span = tag.find("span")

    if not span:
        raise ParseError(f"Expected <span> tag in: {tag}")
    
    try:
        return int(span.get_text(strip=True))
    except ValueError:
        raise ParseError(f"Expected integer inside first <span> tag of: {tag}")


def _get_span_float(tag: Tag) -> float:
    """
    Extracts float from inside first `<span>` tag.
    Raises `ParseError` if `<span>` tag is not found or if its text cannot be parsed as a float.
    """

    span = tag.find("span")

    if not span:
        raise ParseError(f"Expected <span> tag in: {tag}")
    
    try:
        return float(span.get_text(strip=True))
    except ValueError:
        raise ParseError(f"Expected float inside first <span> tag of: {tag}")


def _extract_course_codes(tag: Tag) -> list[str]:
    """
    Extracts all valid course codes from `<a>` tags inside the given tag.
    Raises `ParseError` if any course code does not match expected pattern.
    """

    codes = []

    for a in tag.find_all("a"):
        code = a.get_text(strip=True).upper()

        if not _COURSE_CODE_RE.match(code):
            raise ParseError(f"""Unexpected course code format "{code}" in: {a}""")
            
        codes.append(code)
    
    return codes


def _compress_span_text(span: Tag) -> str:
    """
    Strips whitespace and React comment artifacts from span text.
    
    Examples:
    - `"Complete<!-- -->1<!-- -->of the following"` -> `"Complete1ofthefollowing"`
    - `"Complete<!-- -->all<!-- -->of the following"` -> `"Completeallofthefollowing"`
    """

    return re.sub(r"\s+", "", span.get_text(strip=True))


def _span_to_logic(span: Tag) -> tuple[str, int]:
    """
    Extracts ANY/ALL logic and `n` value from a wrapper `<li>` span.
    Returns `(SELECT_ALL, 1)` or `(SELECT_ANY_N, n)`.

    Raises `ParseError` if span text does not match expected ANY/ALL patterns.
    """

    span_text = _compress_span_text(span)
    m         = _WRAPPER_N_RE.search(span_text)

    if m:
        return (SELECT_ANY_N, int(m.group(1)))
    elif _WRAPPER_ALL_RE.search(span_text):
        return (SELECT_ALL, 1)

    raise ParseError(f"Expected <span> text to match ANY/ALL pattern in: {span}")


def _parse_lvl_range(text: str) -> dict:
    """
    Extracts level range from input string.
    Returns `{"min": <MIN_VALUE>, "max": <MAX_VALUE>}`.

    Pattern to output mapping:
    - Type 1: No level          -> {"min": -1, "max": -1}
    - Type 2: "X-level"         -> {"min": X, "max": X+99}
    - Type 3: "X level"         -> {"min": X, "max": X+99}
    - Type 4: "X- or Y-level"   -> {"min": X, "max": Y+99}
    - Type 5: "X-"              -> {"min": X, "max": -1}
    """

    # CASE: Type 4
    m = _UFS_LVL_RANGE_RE.search(text)

    if m:
        return {"min": (int(m.group(1)) // 100) * 100, "max": (int(m.group(2)) // 100) * 100 + 99}

    # CASE: Type 2
    m = _UFS_LVL_ONLY_RE.search(text)

    if m:
        lo = (int(m.group(1)) // 100) * 100
        return {"min": lo, "max": lo + 99}

    # CASE: Type 3
    m = _UFS_LVL_NOHYPH_RE.search(text)

    if m:
        lo = (int(m.group(1)) // 100) * 100
        return {"min": lo, "max": lo + 99}

    # CASE: Type 5
    m = _UFS_LVL_OPEN_RE.search(text)
    
    if m:
        return {"min": (int(m.group(1)) // 100) * 100, "max": -1}

    # DEFAULT CASE: Type 1
    return {"min": -1, "max": -1}


def _extract_subject_codes(text: str) -> list[str] | None:
    """
    Extracts subject codes from input string, filtering out stopwords.
    Returns `None` if no subject codes are found.
    """

    codes = [c for c in _SUBJECT_CODE_RE.findall(text) if c not in _SUBJ_STOPWORDS]
    return codes if codes else None


def _build_ufs_node(units: float, text: str) -> dict:
    """Builds a UFS node from a units count and constraints text."""

    return {
        KEY_TYPE      : TYPE_UNITS_FROM_SUBJECT,
        KEY_UNITS     : units,
        KEY_SUBJECTS  : _extract_subject_codes(text),
        KEY_LVL_RANGE : _parse_lvl_range(text),
    }


def _is_ufs(result_div: Tag) -> bool:
    """
    Returns True if `result_div` should be parsed as a BASE_UFS node.

    Patterns considered:
    - Type 1: "Complete `N` units from `[SUBJECTS]` `LO` - `HI`"
    - Type 2: "Complete `N` units of: `X` level `SUBJECT`"
    - Type 3: "`COURSE` and `N` units of `SUBJECT` courses"
    - Type 4: 
        - "`N` units of `X`-level [`SUBJECTS`] courses"
        - "`N` units of `X`- or `Y`-level [`SUBJECTS`] courses"
        - "`N` units of `X` level [`SUBJECTS`] courses"
        - "Minimum `N` units of [`SUBJECTS`] courses"
        - "complete a minimum `N` units"
    """

    raw       = str(result_div)
    text      = result_div.get_text(separator=" ", strip=True)
    inner_div = result_div.find("div")

    # CASE: Type 1, Type 2
    if _COMPLETE_N_UNITS_RE.search(raw):
        # CASE: Type 1
        if not inner_div:
            return True
        
        # CASE: Type 2
        inner_text = inner_div.get_text(strip=True)
        return bool(_extract_subject_codes(inner_text) 
                    or _parse_lvl_range(inner_text) != {"min": -1, "max": -1})

    # CASE: Exclusion from BASE_UFS
    if _UFS_EXCLUSION_RE.search(text):
        return False

    # CASE: Type 3
    if _UFS_COMPOSITE_RE.match(text.strip()):
        return True

    # DEFAULT CASE: Type 4
    if not re.search(
        r"(?:complete|minimum(?:\s+of)?|completed\s+a\s+minimum(?:\s+of)?)\s+[\d.]+\s+units"
        r"|[\d.]+\s+units\s+of",
        text, re.IGNORECASE
    ):
        return False

    # Without subject codes, we can't identify qualifying courses, so fall through to text.
    if _extract_subject_codes(text):
        return True

    # Allow bare "minimum N units" with no subject or level constraint
    return bool(re.search(
        r"(?:complete|minimum(?:\s+of)?|completed\s+a\s+minimum(?:\s+of)?)\s+[\d.]+\s+units\s*$",
        text, re.IGNORECASE
    ))


def _parse_ufs(result_div: Tag) -> dict:
    """
    Parses a BASE_UFS node from a result div.
    Raises `ParseError` if the tag cannot be parsed.

    Patterns handled:
    - Type 1: "Complete `N` units from `[SUBJECTS]` `LO` - `HI`"
    - Type 2: "Complete `N` units of: `X` level [`SUBJECTS`]"
    - Type 3: "`COURSE` and `N` units of `SUBJECT` courses"
    - Type 4: 
        - "`N` units of `X`-level [`SUBJECTS`] courses"
        - "`N` units of `X`- or `Y`-level [`SUBJECTS`] courses"
        - "`N` units of `X` level [`SUBJECTS`] courses"
        - "Minimum `N` units of [`SUBJECTS`] courses"
        - "complete a minimum `N` units"
    """

    inner_div = result_div.find("div")
    text      = result_div.get_text(separator=" ", strip=True)

    # CASE: Type 1
    if not inner_div and _COMPLETE_N_UNITS_RE.search(str(result_div)):
        spans = [s.get_text(strip=True) for s in result_div.find_all("span")]

        if len(spans) < 3:
            raise ParseError(f"(Level 4) Expected at least 3 spans in units-from-range node: {result_div}")

        try:
            units = float(spans[0])
        except ValueError:
            raise ParseError(f"(Level 4) Expected float in first span of units-from-range node: {result_div}")

        try:
            lo = int(spans[-2])
            hi = int(spans[-1])
        except ValueError:
            raise ParseError(f"(Level 4) Expected integers for LO and HI in: {result_div}")

        return {
            KEY_TYPE      : TYPE_UNITS_FROM_SUBJECT,
            KEY_UNITS     : units,
            KEY_SUBJECTS  : _extract_subject_codes(" ".join(spans[1:-2])),
            KEY_LVL_RANGE : {"min": lo, "max": hi},
        }

    # CASE: Type 2
    if inner_div and _COMPLETE_N_UNITS_RE.search(str(result_div)):
        inner_text = inner_div.get_text(strip=True)
        return _build_ufs_node(_get_span_float(result_div), inner_text)

    # CASE: Type 3
    m = _UFS_COMPOSITE_RE.match(text.strip())

    if m:
        raw_code = re.sub(r"\s+", "", m.group(1)).upper()
        ufs_text = m.group(2)
        units_m  = _UFS_UNITS_RE.search(ufs_text)

        if not units_m:
            raise ParseError(f"(Level 4) Expected unit count in composite UFS text: {text!r}")
        
        return {
            KEY_LOGIC: SELECT_ALL, 
            KEY_CHILDREN: [{KEY_TYPE: TYPE_COURSE, KEY_CODE: raw_code}, 
                           _build_ufs_node(float(units_m.group(1)), ufs_text)]
        }

    # DEFAULT CASE: Type 4
    m = _UFS_UNITS_RE.search(text)

    if not m:
        raise ParseError(f"(Level 4) Expected unit count in UFS text: {text!r}")

    return _build_ufs_node(float(m.group(1)), text)


# ----- PrereqParser --------------------
class PrereqParser:
    # ----- Private Methods --------------------
    @staticmethod
    def _parse_result_div(result_div: Tag) -> dict | None:
        """
        Level 4: Base Case
        ------------------
        
        Inspects a div with attr `"data-test"="ruleView-X-result"` and returns the appropriate leaf 
        node.

        Pattern to node type mapping:
        - "Complete all of: [`COURSES`]"                          -> ALL [COURSES]
        - "Concurrently enrolled in: [`COURSES`]"                 -> ALL [COURSES]
        - "Complete `N` of: [`COURSES`]"                          -> ANY [COURSES]
        - "Complete `N` units from: [`COURSES`]"                  -> BASE_UFC
        - "Complete `N` units from [`SUBJECTS`] `LO` - `HI`"      -> BASE_UFS
        - "Complete `N` units of: `PLAIN_TEXT`"                   -> BASE_UFS or BASE_TEXT
        - "`N` units of [`SUBJECTS`] courses"                     -> BASE_UFS
        - "`N` units of `X`-level [`SUBJECTS`] courses"           -> BASE_UFS
        - "`N` units of `X`- or `Y`-level [`SUBJECTS`] courses"   -> BASE_UFS
        - "`N` units of `X` level [`SUBJECTS`] courses"           -> BASE_UFS
        - "`COURSE` and `N` units of `SUBJECT` courses"           -> ALL [COURSE, BASE_UFS]
        - Min grade / GPA / plain text                            -> BASE_TEXT

        Raises `ParseError` if `result_div` content does not match any of the defined patterns.
        """

        raw   = str(result_div)
        text  = result_div.get_text(separator=" ", strip=True)

        # CASE: ALL [COURSES]
        if _COMPLETE_ALL_OF_RE.search(raw) or _CONCURRENTLY_RE.search(raw):
            codes = _extract_course_codes(result_div)

            if not codes:
                return None     # Empty course list: Degenerate Kuali node, skip silently
            
            return {
                KEY_LOGIC    : SELECT_ALL,
                KEY_CHILDREN : [{KEY_TYPE: TYPE_COURSE, KEY_CODE: c} for c in codes],
            }

        # CASE: ANY [COURSES]
        if _COMPLETE_N_OF_RE.search(raw):
            n = _get_span_int(result_div)
            codes = _extract_course_codes(result_div)

            if not codes:
                raise ParseError(f"(Level 4) Expected course codes for ANY node in: {result_div}")
            
            return {
                KEY_LOGIC    : SELECT_ANY_N,
                KEY_N        : n,
                KEY_CHILDREN : [{KEY_TYPE: TYPE_COURSE, KEY_CODE: c} for c in codes],
            }

        # CASE: BASE_UFC
        course_codes = _extract_course_codes(result_div)

        if _COMPLETE_N_UNITS_RE.search(raw) and course_codes:
            units = _get_span_float(result_div)
            
            return {
                KEY_TYPE    : TYPE_UNITS_FROM_COURSE,
                KEY_UNITS   : units,
                KEY_COURSES : course_codes,
            }
        
        # CASE: BASE_UFS
        if _is_ufs(result_div):
            return _parse_ufs(result_div)

        # DEFAULT CASE: BASE_TEXT
        if not text:
            raise ParseError(f"(Level 4) Expected text for BASE text node in: {result_div}")

        return {KEY_TYPE: TYPE_TEXT, KEY_TEXT: text}


    @staticmethod
    def _parse_ruleview_li(li: Tag) -> dict | None:
        """
        Level 3
        -------
        
        Finds the result div inside a `<li>` with the `"data-test"` attr and delegates its parsing 
        to `_parse_result_div()`.

        Returns `None` if the result div contains a degenerate node (e.g. empty course list).
        Raises `ParseError` if the expected result div is not found.
        """

        result_div = li.find("div", {"data-test": re.compile(r"-result$")})

        if not result_div:
            raise ParseError(f"""(Level 3) Expected result div with "data-test" attr in <li>: {li}""")

        return PrereqParser._parse_result_div(result_div)


    @staticmethod
    def _find_inner_ul(div: Tag) -> tuple[Tag, Tag | None]:
        """
        Finds the `<ul>` tag inside a `<div>` containing a `<span class="rules_groupHeader_37">`.

        Returns `(inner_ul, wrapper_li)` where `wrapper_li` is the `<li>` containing the `<ul>` if 
        present, or `None` if the `<ul>` is a direct child.

        Raises `ParseError` if expected `<ul>` is not found.
        """

        for child in div.children:
            # Skip non-tag elements (e.g. NavigableString newlines between tags)
            if not isinstance(child, Tag):
                continue

            # CASE: If nested div, recurse into it
            if child.name == "div":
                try:
                    return PrereqParser._find_inner_ul(child)
                except ParseError:
                    continue
            
            # CASE: If wrapper <li> exists
            if child.name == "li" and not child.get("data-test"):
                ul = child.find("ul", recursive=False)
                
                if ul:
                    return (ul, child)
            
            # CASE: If direct <ul> child exists
            if child.name == "ul":
                return (child, None)

        raise ParseError(f"Expected inner <ul> in <div>: {div}")


    @staticmethod
    def _parse_child(child: Tag) -> tuple[dict | None, str, int]:
        """
        Level 2
        -------
        
        Handles a direct child of a `<ul>` based on its type.

        Returns `(node, logic, n)` where `logic` and `n` signal ANY/ALL context to the parent 
        `_parse_ul()` when the child is a group wrapper.

        Child types handled:
        - Type 1: `<li>` with no `"data-test"` attr
        - Type 2: `<div>` containing a `<span class="rules_groupHeader_37">`
        - Type 3: `<li>` with `"data-test"` attr
        
        Type to logic mapping:
        - Type 1: Extracts logic from `<span>` and recurses into inner `<ul>` via `_parse_ul()`
        - Type 2: Grouping logic always ANY with `n=1`, finds and parses nested `<ul>` tag via 
                  `_find_inner_ul()` and `via _parse_ul()`.
            - If `<span>` body has text, adds it as a BASE text node child.
            - If `<div>` contains an `<li>` with a `"data-test"` attr, delegates its parsing to 
              `_parse_ruleview_li()` and adds it as a child.
        - Type 3: Delegates parsing to `_parse_ruleview_li()`

        Raises `ParseError` if child tag does not match the expected types.
        """

        # CASE: Type 1
        if child.name == "li" and not child.get("data-test"):
            span = child.find("span", recursive=False)

            if not span:
                raise ParseError(f"(Level 2) Expected <span> in <div>: {child}")

            logic, n = _span_to_logic(span)
            inner_ul = child.find("ul", recursive=False)

            if not inner_ul:
                raise ParseError(f"(Level 2) Expected inner <ul> in wrapper <li>: {child}")

            node = PrereqParser._parse_ul(inner_ul, logic_override=logic, n_override=n)

            return (node, logic, n)

        # CASE: Type 2
        if child.name == "div":
            header_span = child.find("span", class_="rules_groupHeader_37")

            if not header_span:
                raise ParseError(f"(Level 2) Expected <span> in <div>: {child}")

            logic, n = SELECT_ANY_N, 1
            children: list[dict] = []

            # Non-empty header span text -> prepend as BASE text node
            header_text = header_span.get_text(strip=True)

            if header_text:
                children.append({KEY_TYPE: TYPE_TEXT, KEY_TEXT: header_text})

            # Delegate each child div back through _parse_child()
            for div_child in child.children:
                # Skip non-tag elements (e.g. NavigableString newlines between tags)
                if not isinstance(div_child, Tag):
                    continue

                # Skip the header span itself (already processed above)
                if div_child.name == "span" and "rules_groupHeader_37" in div_child.get("class", []):
                    continue

                node, _, _ = PrereqParser._parse_child(div_child)

                if node is not None:
                    children.append(node)

            return (PrereqParser._wrap(children, logic, n), logic, n)

        # CASE: Type 3
        if child.name == "li" and child.get("data-test"):
            if "ruleView" not in child.get("data-test", ""):
                raise ParseError(f"""(Level 2) Unexpected "data-test" value in <li>: {child.get("data-test")}""")

            node = PrereqParser._parse_ruleview_li(child)

            return (node, SELECT_ALL, 1)

        raise ParseError(f"(Level 2) Unexpected tag type: {child}")


    @staticmethod
    def _wrap(children: list[dict], logic: str, n: int) -> dict:
        """
        Wraps a list of children into an ANY/ALL node.
        Returns the single child directly if there is only one.
        """

        if not children:
            raise ParseError(f"Expected at least one child to wrap in: {children}")

        if len(children) == 1:
            return children[0]

        if logic == SELECT_ANY_N:
            return {KEY_LOGIC: SELECT_ANY_N, KEY_N: n, KEY_CHILDREN: children}

        return {KEY_LOGIC: SELECT_ALL, KEY_CHILDREN: children}


    @staticmethod
    def _parse_ul(ul: Tag, logic_override: str = SELECT_ALL, n_override: int = 1) -> dict:
        """
        Level 1
        -------
        
        Iterates direct children of a `<ul>`, delegates each to `_parse_child()`, then wraps 
        collected nodes into a single ANY/ALL node.

        `logic_override` and `n_override` are set by the parent wrapper span when this is called 
        recursively.

        If any child div has a `<span class="rules_groupHeader_37">`, it overrides grouping logic for 
        the entire `<ul>` to ANY.
        """

        children : list[dict] = []
        logic    : str        = logic_override
        n        : int        = n_override

        for child in ul.children:
            # Skip non-tag elements (e.g. NavigableString newlines between tags)
            if not isinstance(child, Tag):
                continue

            # Delegate parsing of child tags down the pipeline
            node, child_logic, child_n = PrereqParser._parse_child(child)

            if node is not None:
                children.append(node)

            # CASE: Grouping logic override
            if child.name == "div" and child_logic == SELECT_ANY_N:
                logic = SELECT_ANY_N
                n     = child_n

        return PrereqParser._wrap(children, logic, n)


    # ----- Public Method --------------------
    @staticmethod
    def parse(html: str) -> dict:
        """
        Parses raw prereq HTML into a nested prereq tree dict.

        Pipeline:
        ---------
        ```
        parse()
        └── _parse_ul()                         Level 1: Parses each <ul>
            └── _parse_child()                  Level 2: Delegates parsing by child type
                ├── _parse_ul()                          Recurses for nested <ul>s
                └── _parse_ruleview_li()        Level 3: Finds result div
                    └── _parse_result_div()     Level 4 (Base Case): Returns leaf node
        ```

        Output node shapes:
        - {`KEY_LOGIC`: `SELECT_ALL`, `KEY_CHILDREN`: [...]}
        - {`KEY_LOGIC`: `SELECT_ANY_N`, `KEY_N`: N, `KEY_CHILDREN`: [...]}
        - {`KEY_TYPE`: `TYPE_COURSE`, `KEY_CODE`: `<COURSE_CODE>`}
        - {`KEY_TYPE`: `TYPE_UNITS_FROM_COURSE`, `KEY_UNITS`: `<UNITS>`, `KEY_COURSES`: [...]}
        - {`KEY_TYPE`: `TYPE_UNITS_FROM_SUBJECT`, `KEY_UNITS`: `<UNITS>`, `KEY_SUBJECTS`: [...] | None, `KEY_LVL_RANGE`: {...}}
        - {`KEY_TYPE`: `TYPE_TEXT`, `KEY_TEXT`: `<TEXT>`}

        Raises `ParseError` if the HTML structure fails to be parsed according to expected schema.
        """

        if not html or not html.strip():
            raise ParseError(f"Expected HTML")

        soup     = BeautifulSoup(html, "html.parser")
        outer_ul = soup.find("ul")

        if not outer_ul:
            raise ParseError(f"Expected outer <ul> tag")

        try:
            return PrereqParser._parse_ul(outer_ul)
        except Exception as e:
            raise ParseError(f"{e}; for HTML: {html}") from e