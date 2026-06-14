# PrereqParser Test Plan

## Methodology

The tests are all black-box: written by observing inputs and outputs only, with no reference to the parser's internal implementation. All HTML fixtures used in sections 2 and 3 are taken verbatim from `prereq_html_samples.txt`, a file of 2,253 real prerequisite HTML snippets from the UVic Kuali API, with their line numbers documented. Expected outputs were produced by running `PrereqParser.parse()` on those fixtures and manually verified.

---

## Section 1 — `TestPrereqParserInvalidInput`

Verifies that `ParseError` is raised for every category of invalid input. The parser must never return silently on bad input.

The 3 subcategories are tested:

- **Empty and blank strings:** `""`, `" "`, `"     "`, `"\t"`, `"\n"`, and mixed whitespace. These are distinct cases because whitespace-only strings may pass initial emptiness checks depending on implementation.

- **`None`:** Passing `None` where a `str` is expected must raise a `ParseError` rather than propagate an unexpected `AttributeError` or `TypeError` from inside the parser.

- **Malformed HTML:** Four structurally invalid inputs: 
    - A `<div>` with no `<ul>`
    - Plain text with no tags
    - A `<ul>` with no `<li>` children with a `"data-test"` attribute or wrapper `<li>`
    - A `<li>` with a `"data-test"` attribute whose inner result `<div>` is absent.
    
    These verify that the parser validates the expected HTML structure at each parsing stage before attempting to extract content.

---

## Section 2 — `TestPrereqParserLeafNodes`

Verifies that each distinct input pattern produces the correct output. Each test uses a verbatim HTML fixture from `prereq_html_samples.txt` (or an isolated result div constructed from inner content found there) and asserts an exact expected dict. The exception is `test_any_2_of_3_courses`, which uses a partial assert on `logic`, `n`, and `len(children)`, as the property under test is that `n` is extracted correctly, not the identity of the courses.

| Test | Input pattern | Source line |
|---|---|---|
| `test_all_of_single_course` | `Complete all of: [1 course]` | 5 |
| `test_all_of_multiple_courses` | `Complete all of: [3 courses]` | 160 |
| `test_any_1_of_2_courses` | `Complete 1 of: [2 courses]` | 1 |
| `test_any_2_of_3_courses` | `Complete 2 of: [3 courses]` | 238 |
| `test_plain_text_node` | Result div containing plain text only | 3 |
| `test_concurrently_enrolled_in_all_of_treated_as_all` | `Completed or concurrently enrolled in all of: [course]` | 991 |
| `test_concurrently_enrolled_in_n_of_treated_as_any` | `Completed or concurrently enrolled in 1 of: [2 courses]` | 214 (isolated) |
| `test_ufc` | `Complete N units from: [courses]` | 2239 (isolated) |
| `test_ufs_minimum_no_subject` | `Completed a minimum of N units` | 34 (isolated) |
| `test_ufs_bare_subject_and_level` | `N units of X-level SUBJECT courses` | 140 |
| `test_ufs_minimum_with_subject_and_level` | `Minimum N units of X-level SUBJECT_1 or SUBJECT_2 courses` | 8 (isolated) |
| `test_ufs_span_range_single_subject` | `Complete N units from SUBJECT LO - HI` | 1203 |
| `test_ufs_span_range_multi_subject` | `Complete N units from SUBJECT_1 or SUBJECT_2 LO - HI` | 2064 (isolated) |
| `test_ufs_structured_div_subject_only` | `Complete N units of: <div>SUBJECT courses</div>` | 1746 (isolated) |
| `test_ufs_structured_div_no_hyphen_level` | `Complete N units of: <div>X level SUBJECT</div>` | 824 (isolated) |
| `test_ufs_composite_course_and_units` | `COURSE and N units of SUBJECT courses` | 1748 (isolated) |
| `test_ufs_range_level` | `N units of X- or Y-level SUBJECT_1 or SUBJECT_2 courses` | 1144 (isolated) |
| `test_ufs_comma_separated_subjects` | `N units of X- or Y-level SUBJECT_1, SUBJECT_2, or SUBJECT_3 courses` | 1552 (isolated) |
| `test_ufs_no_subject_codes_falls_through_to_text` | `N units of X-level LONGNAME courses` -- `LONGNAME` refers to the full name of the subject referenced by a subject code | 150 (isolated) |
| `test_ufs_bare_minimum_no_subject_no_level` | `completed a minimum of N units` | 34 (isolated) |

**Notes:**
- Tests marked *"isolated"* use inner HTML content from the given sample line wrapped in a minimal scaffold, since the UFS requirement in the original sample is nested inside a larger tree.
- `test_ufs_no_subject_codes_falls_through_to_text` verifies that plain-text unit requirements where no subject code can be extracted (e.g. `"9 units of 300-level Visual Arts courses"`) fall through to a `BASE_TEXT` node rather than producing a `BASE_UFS` node with `subjects=None`.
- `test_ufs_minimum_no_subject` and `test_ufs_bare_minimum_no_subject_no_level` both use the same source line (34) but target slightly different phrasings of the bare minimum form.

---

## Section 3 — `TestPrereqParserCompositeNodes`

Verifies the two structural patterns that produce composite trees by combining multiple child nodes. All 3 tests use full exact dict matches to catch any structural regression in the recursive output (the line number in parentheses refers to the line number the HTML sample was taken from in `prereq_html_samples.txt`).

- **`test_wrapper_li_all_of_following` (line 83):** A `<li>` whose span reads `"Complete all of the following"` groups its children under an `ALL` node. The fixture contains two children, an `ANY (n=1)` course rule and a plain text rule, verifying that the wrapper correctly produces an `ALL` node and that its children are themselves parsed recursively.

- **`test_wrapper_li_any_1_of_following` (line 107):** The same wrapper pattern but with an integer `N` in the span, producing an `ANY (n=N)` node. The fixture contains an `ALL` course rule and a plain text rule as children, verifying that `n` is extracted from the span and that child parsing is recursive.

- **`test_group_header_div` (line 1738):** A `<div>` containing a `<span class="rules_groupHeader_37">` forces `ANY (n=1)` logic on the enclosing `<ul>`. The fixture represents the deepest nesting in the sample data: the groupHeader div wraps a wrapper `<li>` which itself contains an `ALL` node and a `BASE_UFS` node, producing a two-level `ANY (n=1) -> ANY (n=1) -> [ALL [COURSE], BASE_UFS]` tree alongside a sibling text node at the outer level.

---

## Section 4 — `TestPrereqParserRealSamples`

Regression suite executed against all 2,253 samples in `prereq_html_samples.txt`. The purpose is breadth coverage across the full diversity of real-world inputs, not exact output verification. All **9** tests share a single class-scoped fixture that loads the file once. The fixture skips gracefully if `prereq_html_samples.txt` is not present.

| Test | Assertion |
|---|---|
| `test_no_parse_errors` | Every line parses without raising any exception |
| `test_all_results_are_dicts` | Every result is a `dict` |
| `test_all_results_have_logic_or_type` | Every top-level result has `"logic"` or `"type"` |
| `test_logic_nodes_have_non_empty_children` | Every node with `"logic"` has a non-empty `"children"` list, checked recursively |
| `test_any_nodes_have_positive_int_n` | Every `ANY` node has an integer `n >= 1`, checked recursively |
| `test_course_nodes_have_non_empty_string_code` | Every course node has a non-empty string `"code"`, checked recursively |
| `test_text_nodes_have_non_empty_string_text` | Every `BASE_TEXT` node has a non-empty string `"text"`, checked recursively |
| `test_ufc_nodes_have_required_keys` | Every `BASE_UFC` node has a non-negative float `"units"` and a non-empty list of strings `"courses"`, checked recursively |
| `test_ufs_nodes_have_required_keys` | Every `BASE_UFS` node has a non-negative float `"units"`, a `"subjects"` value that is `None` or a list of strings, and a `"lvl_range"` dict with integer `"min"` and `"max"`, checked recursively |

---

## Notes

- `prereq_html_samples.txt` must be in the same directory as the test file.
- If `prereq_html_samples.txt` is absent, sections 1–3 run in full but section 4 will be skipped.