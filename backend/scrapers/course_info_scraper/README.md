# Course Info Scraper

## Overview

Fetches all UVic course data from the Kuali API and writes it to the database in a single atomic transaction. On any failure the entire transaction is rolled back, ensuring no partial data is written.

---

## Pipeline

1. Scrape the UVic calendar page to extract the latest catalog ID
2. Fetch the list of all courses (code, name, PID)
3. For each course, fetch its credits, raw prerequisite HTML, and raw corequisite HTML via its PID
4. Parse each course's raw prerequisite and corequisite HTML into structured trees
5. Truncate existing data and insert all courses in one transaction

Steps 1-3 are handled by `CourseInfoFetcher`. Step 4 is handled by `PrereqParser` and `CoreqParser`. Step 5 is handled by `CourseInfoScraper`.

---

## Catalog ID Discovery

The catalog ID is a 24-character hex string that scopes all Kuali API requests to a specific academic term. It is scraped from the UVic calendar page on each run so the scraper always targets the latest catalog without manual configuration.

Two strategies are attempted in order:

1. Look for an explicit `window.catalogId = '...'` assignment in the page HTML.
2. Fall back to extracting any 24-character hex string found anywhere in the page.

`InformationFetchError` is raised if neither strategy succeeds.

---

## Prerequisite HTML

Each course's prerequisite data is returned by the Kuali API as raw React-rendered HTML. This HTML encodes prerequisite logic through its structure rather than its text content, requiring a recursive parser to extract meaning.

### Input Patterns

**10** distinct input patterns are present in the HTML. The first eight are single-node patterns (four of which are `BASE_UFS` sub-forms). The last two are structural patterns that combine multiple nodes into a tree.

- **`Complete all of: [COURSES]`:**
    
    The student must complete every listed course. Also produced by the `Completed or concurrently enrolled in all of:` variant, which is treated identically.

- **`Complete N of: [COURSES]`:**
    
    The student must complete at least `N` of the listed courses, where `N` is encoded in a `<span>` tag. Also produced by the `Completed or concurrently enrolled in N of:` variant, which is treated identically.

- **`Complete N units from: [COURSES]`:**
    
    The student must complete at least `N` units drawn from the listed courses, where `N` is a float encoded in a `<span>` tag.

- **`Complete N units from [SUBJECTS] LO - HI` (span range form):**
    
    The student must complete at least `N` units from courses in the given subjects within a numeric level range. The no. of units, subjects and hi-lo range bounds are each encoded in separate `<span>` tags (e.g. `Complete <span>3</span> units from <span>GEOG</span> <span>100</span> - <span>299</span>`).

- **`Complete N units of: TEXT` (structured div form):**
    
    The student must complete at least `N` units of courses described by plain text. The `N` is encoded in a `<span>` and the `TEXT` is encoded in a `<div>`. If the inner text contains recognisable subject codes or level information (e.g. `"100 level MATH"`, `"STAT courses"`), it is parsed as a `BASE_UFS` node. If the content is freeform (e.g. `"an AWR-designated course"`), it is parsed as a `BASE_TEXT` node.

- **Plain-text `UFS` forms:**

    Unit requirements expressed entirely as plain text with no structured HTML has **6** sub-forms:
    - `"N units of X level [SUBJECTS] courses"` / `"N units of X-level [SUBJECTS] courses"`
    - `"N units of X- or Y-level [SUBJECTS] courses"`
    - `"Complete N units of: X level [SUBJECTS]"`
    - `"Minimum N units of [SUBJECTS] courses"`
    - `"Minimum N units of [SUBJECTS] courses"`
    - `"complete a minimum N units"`

    If text is technically a `UFS` type but no recognisable subject codes can be extracted (e.g. `"9 units of 300-level Visual Arts courses"`), the node falls through to `BASE_TEXT` instead.

- **`COURSE and N units of SUBJECT courses` (composite form):**

    A plain-text result div combining a single course requirement with a subject unit requirement. Parsed as an `ALL` node with two children: a `COURSE` node and a `BASE_UFS` node (e.g. `"PHIL 203 and 3 units of PHIL courses"`).

- **Plain Text:**

    A freeform text condition with no associated course list, such as `"Permission of the department"` or `"Minimum third-year standing"`.

- **Wrapper `<li>` with `"Complete all/N of the following"` span:**

    A `<li>` element whose `<span>` reads `"Complete all of the following"` or `"Complete N of the following"` groups its child nodes under an `ALL` or `ANY (n=N)` node respectively. Each child is itself one of the four single-node patterns above, or another wrapper, making this pattern recursive.

- **`<div>` with `<span class="rules_groupHeader_37">`:**

    A `<div>` containing a `<span class="rules_groupHeader_37">` forces `ANY (n=1)` logic on its enclosing `<ul>`. If the span has non-empty text, that text is prepended as a plain text child node. The remaining children are parsed recursively.

---

## Prereq Output Schema

`PrereqParser.parse()` returns a single dict representing the root of the prerequisite tree. There are two categories of node: composite nodes and leaf nodes.

### Composite Nodes

Composite nodes have a `"logic"` key and a `"children"` list. Children are themselves nodes of any type.

```python
# ALL: student must satisfy every child
{"logic": "ALL", "children": [...]}

# ANY (n): student must satisfy at least n children
{"logic": "ANY", "n": 2, "children": [...]}
```

### Leaf Nodes

Leaf nodes have a `"type"` key and no children.

```python
# A single required course
{"type": "course", "code": "CSC110"}

# A freeform text condition
{"type": "text", "text": "Minimum third-year standing"}

# A unit requirement drawn from a specific set of linked courses
{"type": "units_from_course", "units": 3.0, "courses": ["WRIT303", "WRIT304", "WRIT305"]}

# A unit requirement from courses matching a subject/level description
{"type": "units_from_subject", "units": 3.0, "subjects": ["AHVS", "HA"], "lvl_range": {"min": 300, "max": 399}}
```

#### `UFS` Field Details

- **`subjects`:** A list of subject codes, or `None` if there are no subject constraint (e.g `"Completed a minimum of 12 units"`).

- **`lvl_range`:** A dict with integer `"min"` and `"max"` keys encoding the level constraint. A value of `-1` for a bound indicates that the corresponding side of the range is unbounded.

    | `lvl_range` | Meaning | Example source text |
    |---|---|---|
    | `{"min": -1, "max": -1}` | No level constraint | `"4.5 units of PHIL courses"` |
    | `{"min": 300, "max": 399}` | Strict single level (300-level only) | `"Minimum 3 units of 300-level AHVS courses"` |
    | `{"min": 300, "max": 499}` | Level range (300- or 400-level) | `"3 units of 300- or 400-level PHIL courses"` |
    | `{"min": 300, "max": -1}` | Open upper bound (300 and above) | `"Minimum 3 units of 300- courses"` |
    | `{"min": 100, "max": 299}` | Numeric range from span form | `"Complete 3 units from GEOG 100 - 299"` |

    The convention for strict single levels is `max = min + 99` (e.g. 300-level -> `{"min": 300, "max": 399}`). For ranges expressed as `"300- or 400-level"`, `max` is the upper level's base plus 99 (e.g. `{"min": 300, "max": 499}`). For the numeric span form (`Complete N units from SUBJ LO - HI`), `min` and `max` are taken directly from the span values.

### Notes

- Courses with no prerequisite data have `prereqs` set to `null` in the database. `PrereqParser` is only invoked when the Kuali API returns a non-empty prerequisite HTML string.

- Courses with no corequisite data have `coreqs` set to `null` in the database. `CoreqParser` is only invoked when the Kuali API returns a non-empty corequisite HTML string. `CoreqParser` is a subclass of `PrereqParser` and shares the same output schema.

A node with a single child is returned as that child directly, without wrapping it in an `ALL` or `ANY` node.

---

## Database Schema

Each course is stored as a single row with the following fields:

| Field | Type | Description |
|---|---|---|
| `code` | `str` | Full course code, e.g. `"CSC110"` |
| `subject` | `str` | Subject prefix extracted from code, e.g. `"CSC"` |
| `lvl` | `int` | Course level rounded to the nearest hundred, e.g. `100` |
| `name` | `str` | Course title |
| `credits` | `float` | Minimum credit value |
| `prereqs` | `JSONB` | Parsed prerequisite tree, or `null` if none |
| `coreqs` | `JSONB` | Parsed corequisite tree, or `null` if none |