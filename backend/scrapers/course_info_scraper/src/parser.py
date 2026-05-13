from __future__ import annotations

import re
from bs4 import BeautifulSoup, Tag

from scrapers.shared.errors import ParseError


# ----- Regexes --------------------
# To search against raw HTML
_COMPLETE_ALL_OF_RE  = re.compile(r"Complete\s+all\s+of\s*:",                  re.IGNORECASE)
_COMPLETE_N_OF_RE    = re.compile(r"Complete\s+<span>\d+</span>\s+of\s*:",     re.IGNORECASE)
_COMPLETE_N_UNITS_RE = re.compile(r"Complete\s+<span>[\d.]+</span>\s+units",   re.IGNORECASE)
_CONCURRENTLY_RE     = re.compile(r"concurrently\s+enrolled",                  re.IGNORECASE)

# To search agains compressed <span> text with whitespace and comment artifacts removed
_WRAPPER_N_RE        = re.compile(r"Complete(\d+)of",                           re.IGNORECASE)

# Course code pattern
_COURSE_CODE_RE      = re.compile(r"^[A-Z]{2,4}-?[A-Z]?\d{3}[A-Z]?$")


# ----- Schema Keys --------------------
# Logic node keys
SELECT_ALL   = "ALL"
SELECT_ANY_N = "ANY"

# Base node type values
TYPE_COURSE     = "course"
TYPE_UNITS_FROM = "units_from"
TYPE_TEXT       = "text"

# Output dict keys
KEY_LOGIC    = "logic"
KEY_CHILDREN = "children"
KEY_N        = "n"
KEY_TYPE     = "type"
KEY_CODE     = "code"
KEY_UNITS    = "units"
KEY_COURSES  = "courses"
KEY_TEXT     = "text"


# ----- Helper Methods --------------------
def _get_span_int(tag: Tag) -> int | None:
    """Extracts integer from inside first `<span>` tag."""

    span = tag.find("span")

    if not span:
        return None
    
    try:
        return int(span.get_text(strip=True))
    except ValueError:
        return None


def _get_span_float(tag: Tag) -> float | None:
    """Extracts float from inside first `<span>` tag."""

    span = tag.find("span")

    if not span:
        return None
    
    try:
        return float(span.get_text(strip=True))
    except ValueError:
        return None


def _extract_course_codes(tag: Tag) -> list[str]:
    """Extracts all valid course codes from `<a>` tags inside the given tag."""

    codes = []

    for a in tag.find_all("a"):
        code = a.get_text(strip=True).upper()

        if _COURSE_CODE_RE.match(code):
            codes.append(code)
    
    return codes


def _compress_span_text(span: Tag) -> str:
    """
    Strips whitespace and React comment artifacts from span text.
    E.g. `"Complete<!-- -->1<!-- -->of the following"` -> `"Complete1ofthefollowing"`
    """

    return re.sub(r"\s+", "", span.get_text(strip=True))


def _span_to_logic(span: Tag) -> tuple[str, int]:
    """
    Extracts ANY/ALL logic and `n` value from a wrapper `<li>` span.
    Returns `(SELECT_ALL, 1)` or `(SELECT_ANY_N, n)`.
    """

    span_text = _compress_span_text(span)
    m         = _WRAPPER_N_RE.search(span_text)

    if m:
        return (SELECT_ANY_N, int(m.group(1)))

    return (SELECT_ALL, 1)


# ----- PrereqParser --------------------
class PrereqParser:
    # ----- Private Methods --------------------
    def _parse_result_div(self, result_div: Tag) -> dict | None:
        """
        Level 4: Base Case
        ------------------
        
        Inspects a div with attr `"data-test"="ruleView-X-result"` and returns the appropriate leaf 
        node.

        Pattern to node type mapping:
        - "Complete all of: [`COURSES`]"            -> ALL node
        - "Concurrently enrolled in: [`COURSES`]"   -> ALL node
        - "Complete N of: [`COURSES`]"              -> ANY node
        - "Complete X units from: [`COURSES`]"      -> BASE units_from
        - "Min grade / GPA ... `COURSES`"           -> BASE text
        - Plain text                                -> BASE text
        - Empty course list on structured rule      -> None (skip)
        """

        raw   = str(result_div)
        text  = result_div.get_text(separator=" ", strip=True)
        codes = _extract_course_codes(result_div)

        # CASE: ALL node
        if _COMPLETE_ALL_OF_RE.search(raw) or _CONCURRENTLY_RE.search(raw):
            if not codes:
                return None
            
            return {
                KEY_LOGIC    : SELECT_ALL,
                KEY_CHILDREN : [{KEY_TYPE: TYPE_COURSE, KEY_CODE: c} for c in codes],
            }

        # CASE: ANY node
        if _COMPLETE_N_OF_RE.search(raw) and codes:
            n = _get_span_int(result_div)

            if n is None:
                return None
            
            return {
                KEY_LOGIC    : SELECT_ANY_N,
                KEY_N        : n,
                KEY_CHILDREN : [{KEY_TYPE: TYPE_COURSE, KEY_CODE: c} for c in codes],
            }

        # CASE: BASE units_from node
        if _COMPLETE_N_UNITS_RE.search(raw) and codes:
            units = _get_span_float(result_div)

            if units is None:
                return None
            
            return {
                KEY_TYPE    : TYPE_UNITS_FROM,
                KEY_UNITS   : units,
                KEY_COURSES : codes,
            }

        if not text:
            return None

        # DEFAULT CASE: BASE text node
        return {KEY_TYPE: TYPE_TEXT, KEY_TEXT: text}


    def _parse_ruleview_li(self, li: Tag) -> dict | None:
        """
        Level 3
        -------
        
        Finds the result div inside a `<li>` with the `"data-test"` attr and delegates its parsing 
        to `_parse_result_div()`.
        """

        result_div = li.find("div", {"data-test": re.compile(r"-result$")})

        if not result_div:
            return None

        return self._parse_result_div(result_div)


    def _find_inner_ul(self, div: Tag) -> tuple[Tag | None, Tag | None]:
        """
        Finds the `<ul>` tag inside a `<div>` containing a `<span class="rules_groupHeader_37">`.

        Returns `(inner_ul, wrapper_li)` where `wrapper_li` is the `<li>` containing the `<ul>` if 
        present, or `None` if the `<ul>` is a direct child.
        """

        for child in div.children:
            # Skip non-tag elements (e.g. NavigableString newlines between tags)
            if not isinstance(child, Tag):
                continue

            # CASE: If nested div, recurse into it
            if child.name == "div":
                result = self._find_inner_ul(child)

                if result[0]:
                    return result
            
            # CASE: If wrapper <li> exists
            if child.name == "li" and not child.get("data-test"):
                ul = child.find("ul", recursive=False)
                
                if ul:
                    return (ul, child)
            
            # CASE: If direct <ul> child exists
            if child.name == "ul":
                return (child, None)

        return (None, None)


    def _parse_child(self, child: Tag) -> tuple[dict | None, str, int]:
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
        - Default Type: anything else
        
        Type to logic mapping:
        - Type 1: Extracts logic from `<span>` and recurses into inner `<ul>` via `_parse_ul()`
        - Type 2: Grouping logic always ANY with `n=1`, finds and parses nested `<ul>` tag via 
                  `_find_inner_ul()` and `via _parse_ul()`.
            - If `<span>` body has text, adds it as a BASE text node child.
            - If `<div>` contains an `<li>` with a `"data-test"` attr, delegates its parsing to 
              `_parse_ruleview_li()` and adds it as a child.
        - Type 3: Delegates parsing to `_parse_ruleview_li()`
        """

        # CASE: Type 1
        if child.name == "li" and not child.get("data-test"):
            span = child.find("span", recursive=False)

            if not span:
                return (None, SELECT_ALL, 1)

            logic, n = _span_to_logic(span)
            inner_ul = child.find("ul", recursive=False)

            if not inner_ul:
                return (None, logic, n)

            node = self._parse_ul(inner_ul, logic_override=logic, n_override=n)

            return (node, logic, n)

        # CASE: Type 2
        if child.name == "div":
            header_span = child.find("span", class_="rules_groupHeader_37")

            if not header_span:
                return (None, SELECT_ALL, 1)

            logic, n = SELECT_ANY_N, 1
            children: list[dict] = []

            # CASE: Non-empty <span> body
            header_text = header_span.get_text(strip=True)

            if header_text:
                children.append({KEY_TYPE: TYPE_TEXT, KEY_TEXT: header_text})

            # Find and parse inner <ul>
            inner_ul, wrapper_li = self._find_inner_ul(child)

            if inner_ul:
                if wrapper_li is not None:
                    span                    = wrapper_li.find("span", recursive=False)
                    child_logic, child_n    = _span_to_logic(span) if span else (SELECT_ALL, 1)
                    node                    = self._parse_ul(inner_ul, 
                                                             logic_override=child_logic, 
                                                             n_override=child_n)
                else:
                    node = self._parse_ul(inner_ul)
                
                if node:
                    children.append(node)

            # CASE: <li> with "data-test" attr
            for li in child.find_all("li", recursive=False):
                if li.get("data-test") and "ruleView" in li.get("data-test", ""):
                    node = self._parse_ruleview_li(li)

                    if node:
                        children.append(node)

            return (self._wrap(children, logic, n), logic, n)

        # CASE: Type 3
        if child.name == "li" and child.get("data-test"):
            if "ruleView" not in child.get("data-test", ""):
                return (None, SELECT_ALL, 1)

            node = self._parse_ruleview_li(child)

            return (node, SELECT_ALL, 1)

        # CASE: Default Type
        return (None, SELECT_ALL, 1)


    def _wrap(self, children: list[dict], logic: str, n: int) -> dict | None:
        """
        Wraps a list of children into an ANY/ALL node.
        Returns the single child directly if there is only one.
        """

        if not children:
            return None

        if len(children) == 1:
            return children[0]

        if logic == SELECT_ANY_N:
            return {KEY_LOGIC: SELECT_ANY_N, KEY_N: n, KEY_CHILDREN: children}

        return {KEY_LOGIC: SELECT_ALL, KEY_CHILDREN: children}


    def _parse_ul(self, ul: Tag, logic_override: str = SELECT_ALL, n_override: int = 1) -> dict | None:
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
            node, child_logic, child_n = self._parse_child(child)

            if node:
                children.append(node)

            # CASE: Grouping logic override
            if child.name == "div" and child_logic == SELECT_ANY_N:
                logic = SELECT_ANY_N
                n     = child_n

        return self._wrap(children, logic, n)


    # ----- Public Method --------------------
    def parse(self, html: str | None) -> dict | None:
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
        - {`KEY_LOGIC`: `SELECT_ALL`,   `KEY_CHILDREN`: [...]}
        - {`KEY_LOGIC`: `SELECT_ANY_N`, `KEY_N`: N, `KEY_CHILDREN`: [...]}
        - {`KEY_TYPE`: `TYPE_COURSE`,        `KEY_CODE`: `<COURSE_CODE>`}
        - {`KEY_TYPE`: `TYPE_UNITS_FROM`,    `KEY_UNITS`: `<UNITS>`, `KEY_COURSES`: [...]}
        - {`KEY_TYPE`: `TYPE_TEXT`,          `KEY_TEXT`: `<TEXT>`}
        """

        if not html or not html.strip():
            return None

        soup     = BeautifulSoup(html, "html.parser")
        outer_ul = soup.find("ul")

        if not outer_ul:
            return None

        return self._parse_ul(outer_ul)