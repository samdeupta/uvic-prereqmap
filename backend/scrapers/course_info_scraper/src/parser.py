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

        Raises `ParseError` if `result_div` content does not match any of the defined patterns.
        """

        raw   = str(result_div)
        text  = result_div.get_text(separator=" ", strip=True)
        codes = _extract_course_codes(result_div)

        # CASE: ALL node
        if _COMPLETE_ALL_OF_RE.search(raw) or _CONCURRENTLY_RE.search(raw):
            if not codes:
                return None     # Empty course list: Degenerate Kuali node, skip silently
            
            return {
                KEY_LOGIC    : SELECT_ALL,
                KEY_CHILDREN : [{KEY_TYPE: TYPE_COURSE, KEY_CODE: c} for c in codes],
            }

        # CASE: ANY node
        if _COMPLETE_N_OF_RE.search(raw):
            n = _get_span_int(result_div)

            if not codes:
                raise ParseError(f"(Level 4) Expected course codes for ANY node in: {result_div}")
            
            return {
                KEY_LOGIC    : SELECT_ANY_N,
                KEY_N        : n,
                KEY_CHILDREN : [{KEY_TYPE: TYPE_COURSE, KEY_CODE: c} for c in codes],
            }

        # CASE: BASE units_from node
        if _COMPLETE_N_UNITS_RE.search(raw) and codes:
            units = _get_span_float(result_div)
            
            return {
                KEY_TYPE    : TYPE_UNITS_FROM,
                KEY_UNITS   : units,
                KEY_COURSES : codes,
            }

        if not text:
            raise ParseError(f"(Level 4) Expected text for BASE text node in: {result_div}")

        # DEFAULT CASE: BASE text node
        return {KEY_TYPE: TYPE_TEXT, KEY_TEXT: text}


    def _parse_ruleview_li(self, li: Tag) -> dict | None:
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

        return self._parse_result_div(result_div)


    def _find_inner_ul(self, div: Tag) -> tuple[Tag, Tag | None]:
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
                    return self._find_inner_ul(child)
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

            node = self._parse_ul(inner_ul, logic_override=logic, n_override=n)

            return (node, logic, n)

        # CASE: Type 2
        if child.name == "div":
            header_span = child.find("span", class_="rules_groupHeader_37")

            if not header_span:
                raise ParseError(f"(Level 2) Expected <span> in <div>: {child}")

            logic, n = SELECT_ANY_N, 1
            children: list[dict] = []

            # CASE: Non-empty <span> body
            header_text = header_span.get_text(strip=True)

            if header_text:
                children.append({KEY_TYPE: TYPE_TEXT, KEY_TEXT: header_text})

            # Iterate div children directly — handles all structural variants:
            # - direct ruleView <li> children (most common)
            # - wrapper <li> containing inner <ul>
            # - nested groupHeader <div> (double nesting)
            for div_child in child.children:
                # Skip non-tag elements (e.g. NavigableString newlines between tags)
                if not isinstance(div_child, Tag):
                    continue

                # Skip the header span itself
                if div_child.name == "span" and "rules_groupHeader_37" in div_child.get("class", []):
                    continue

                # Direct ruleView <li>
                if div_child.name == "li" and div_child.get("data-test"):
                    if "ruleView" in div_child.get("data-test", ""):
                        node = self._parse_ruleview_li(div_child)
                        if node is not None:
                            children.append(node)

                # Wrapper <li> with inner <ul>
                elif div_child.name == "li" and not div_child.get("data-test"):
                    span = div_child.find("span", recursive=False)

                    if not span:
                        raise ParseError(f"(Level 2) Expected <span> in wrapper <li>: {div_child}")
                    
                    child_logic, child_n    = _span_to_logic(span)
                    inner_ul                = div_child.find("ul", recursive=False)

                    if not inner_ul:
                        raise ParseError(f"(Level 2) Expected inner <ul> in wrapper <li>: {div_child}")
                    
                    children.append(self._parse_ul(inner_ul, logic_override=child_logic, n_override=child_n))

                # Nested groupHeader <div> — recurse via _parse_child
                elif div_child.name == "div":
                    node, _, _ = self._parse_child(div_child)
                    children.append(node)

            return (self._wrap(children, logic, n), logic, n)

        # CASE: Type 3
        if child.name == "li" and child.get("data-test"):
            if "ruleView" not in child.get("data-test", ""):
                raise ParseError(f"""(Level 2) Unexpected "data-test" value in <li>: {child.get("data-test")}""")

            node = self._parse_ruleview_li(child)

            return (node, SELECT_ALL, 1)

        raise ParseError(f"(Level 2) Unexpected tag type: {child}")


    def _wrap(self, children: list[dict], logic: str, n: int) -> dict:
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


    def _parse_ul(self, ul: Tag, logic_override: str = SELECT_ALL, n_override: int = 1) -> dict:
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

            if node is not None:
                children.append(node)

            # CASE: Grouping logic override
            if child.name == "div" and child_logic == SELECT_ANY_N:
                logic = SELECT_ANY_N
                n     = child_n

        return self._wrap(children, logic, n)


    # ----- Public Method --------------------
    def parse(self, html: str) -> dict:
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
        - {`KEY_TYPE`: `TYPE_UNITS_FROM`, `KEY_UNITS`: `<UNITS>`, `KEY_COURSES`: [...]}
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
            return self._parse_ul(outer_ul)
        except Exception as e:
            raise ParseError(f"{e}; for HTML: {html}") from e