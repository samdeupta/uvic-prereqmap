from __future__ import annotations

import pytest
from pathlib import Path

from src.prereq_parser import (
    PrereqParser, 
    SELECT_ALL, 
    SELECT_ANY_N, 
    TYPE_COURSE, 
    TYPE_TEXT, 
    TYPE_UNITS_FROM_COURSE,
    TYPE_UNITS_FROM_SUBJECT
)
from shared.errors import ParseError


# ----- Constants --------------------
SAMPLE_FILENAME = "prereq_html_samples.txt"


# ----- 1. Invalid Input Handling Tests --------------------
class TestPrereqParserInvalidInput:
    """Parser must raise `ParseError` (never return silently) for any invalid input."""

    # ----- Input: Empty/blank strings --------------------
    def test_empty_string(self):
        with pytest.raises(ParseError):
            PrereqParser().parse("")


    def test_single_space(self):
        with pytest.raises(ParseError):
            PrereqParser().parse(" ")


    def test_multiple_spaces(self):
        with pytest.raises(ParseError):
            PrereqParser().parse("     ")


    def test_tab_only(self):
        with pytest.raises(ParseError):
            PrereqParser().parse("\t")


    def test_newline_only(self):
        with pytest.raises(ParseError):
            PrereqParser().parse("\n")


    def test_mixed_whitespace(self):
        with pytest.raises(ParseError):
            PrereqParser().parse("  \t\n  \r\n  ")


    # ----- Input: None --------------------
    def test_none_raises(self):
        with pytest.raises(ParseError):
            PrereqParser().parse(None)


    # ----- Input: Invalid/malformed HTML (including those violating schema) --------------------
    def test_plain_div_no_ul(self):
        with pytest.raises(ParseError):
            PrereqParser().parse("<div><p>No list here</p></div>")


    def test_plain_text_no_tags(self):
        with pytest.raises(ParseError):
            PrereqParser().parse("Complete all of: CSC110")


    def test_ul_but_no_ruleview_children(self):
        """A `<ul>` with no wrapper children or inner `<li>` with a "data-test" attr raises `ParseError`."""

        with pytest.raises(ParseError):
            PrereqParser().parse("<div><div><div><ul></ul></div></div></div>")


    def test_result_div_missing(self):
        """A `<li>` with `"data-test"` attr whose inner result div is absent raises `ParseError`."""

        with pytest.raises(ParseError):
            PrereqParser().parse(
                '<div><div><div><ul>'
                '<li data-test="ruleView-A"></li>'
                '</ul></div></div></div>'
            )


# ----- 2. Leaf Node Structure Verification Tests --------------------
class TestPrereqParserLeafNodes:
    """
    Each test targets one specific input pattern using a real HTML snippet from `prereq_html_samples.txt`. 
    The expected output was produced by running `PrereqParser().parse()` and manually verified.
    """

    # ----- Type: ALL [COURSES] --------------------
    def test_all_of_single_course(self):
        """
        `"Complete all of: [COURSE]"` with one course -> ALL node with one course child.
        Source: Line 5.
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">Complete all of: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/5f29c3f836d0ae0026b17a96" target="_blank">AE322</a>'
            ' <!-- -->-<!-- --> <!-- -->Digital Arts<!-- --> <span style="margin-left:5px">(1.5)</span>'
            '</span></li>'
            '</ul></div>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "logic": SELECT_ALL,
            "children": [{"type": TYPE_COURSE, "code": "AE322"}]
        }


    def test_all_of_multiple_courses(self):
        """
        `"Complete all of: [A, B, C]"` -> ALL node with three course children in order.
        Source: Line 160.
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">Complete all of: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/66d2281c74171541059724aa" target="_blank">ASTR250</a>'
            ' <!-- -->-<!-- --> <!-- -->Introduction to Astrophysics<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/672e74702494ee5aaeb60ea6" target="_blank">PHYS215</a>'
            ' <!-- -->-<!-- --> <!-- -->Introductory Quantum Physics<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/672e72ab5d32637db2de8479" target="_blank">PHYS216</a>'
            ' <!-- -->-<!-- --> <!-- -->Introductory Electricity and Magnetism<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '</ul></div>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "logic": SELECT_ALL,
            "children": [
                {"type": TYPE_COURSE, "code": "ASTR250"},
                {"type": TYPE_COURSE, "code": "PHYS215"},
                {"type": TYPE_COURSE, "code": "PHYS216"}
            ]
        }


    # ----- Type: ANY [COURSES] --------------------
    def test_any_1_of_2_courses(self):
        """
        `"Complete 1 of: [A, B]"` -> ANY (`n=1`) node with two course children.
        Source: Line 1.
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">Complete <span>1</span> of: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/67ffff2c84f6076d6372d72a" target="_blank">ADMN311</a>'
            ' <!-- -->-<!-- --> <!-- -->Introduction to Public Administration<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/5f4d698c9c7aab0026994900" target="_blank">POLI350</a>'
            ' <!-- -->-<!-- --> <!-- -->Introduction to Public Administration<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '</ul></div>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "logic": SELECT_ANY_N,
            "n": 1,
            "children": [
                {"type": TYPE_COURSE, "code": "ADMN311"},
                {"type": TYPE_COURSE, "code": "POLI350"}
            ]
        }


    def test_any_2_of_3_courses(self):
        """
        `"Complete 2 of: [A, B, C]"` -> ANY (`n=2`) node with `n` correctly set to `2`.
        Source: Line 238.
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">Complete <span>2</span> of: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/5d1f6ea3d2bc1524008cb091" target="_blank">BIOL215</a>'
            ' <!-- -->-<!-- --> <!-- -->Principles of Ecology<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/5d1f70c9fb68f3240022d32c" target="_blank">BIOL225</a>'
            ' <!-- -->-<!-- --> <!-- -->Principles of Cell Biology<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/5d1f6f68fb68f3240022d231" target="_blank">BIOL230</a>'
            ' <!-- -->-<!-- --> <!-- -->Principles of Genetics<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '</ul></div>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        result = PrereqParser().parse(html)

        assert result["logic"] == SELECT_ANY_N
        assert result["n"] == 2
        assert len(result["children"]) == 3


    # ----- Type: BASE_TEXT --------------------
    def test_plain_text_node(self):
        """
        Result div containing only plain text -> BASE text node.
        Source: Line 3.
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result"><div>Permission of the school.</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type": TYPE_TEXT,
            "text": "Permission of the school."
        }


    # ----- Type: Concurrently enrolled --------------------
    def test_concurrently_enrolled_in_all_of_treated_as_all(self):
        """
        `"Completed or concurrently enrolled in all of: [COURSE]"` -> ALL node with one course child.
        Source: Line 991.
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">'
            'Completed or concurrently enrolled in all of: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/66ccaa9cd876d2824c20f5a0" target="_blank">FRAN305</a>'
            ' <!-- -->-<!-- --> <!-- -->Intermediate French Linguistics<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '</ul></div>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "logic": SELECT_ALL,
            "children": [{"type": TYPE_COURSE, "code": "FRAN305"}]
        }


    def test_concurrently_enrolled_in_n_of_treated_as_any(self):
        """
        `"Completed or concurrently enrolled in 1 of: [A, B]"` -> ANY (`n=1`) node with two course 
        children.
        Source: Line 214 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-B.2">'
            '<div data-test="ruleView-B.2-result">'
            'Completed or concurrently enrolled in <span>1</span> of: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/5d1f6e32d2bc1524008cb046" target="_blank">BIOC300A</a>'
            ' <!-- -->-<!-- --> <!-- -->General Biochemistry I<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/5d1f7523d2bc1524008cb555" target="_blank">BIOC300B</a>'
            ' <!-- -->-<!-- --> <!-- -->General Biochemistry II<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '</ul></div>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "logic"    : SELECT_ANY_N,
            "n"        : 1,
            "children" : [
                {"type": TYPE_COURSE, "code": "BIOC300A"},
                {"type": TYPE_COURSE, "code": "BIOC300B"},
            ]
        }


    # ----- Type: BASE_UFC --------------------
    def test_ufc(self):
        """
        `"Complete N units from: [COURSES]"` -> BASE_UFC node with float units and list of course 
        codes.
        Source: Line 2239 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-C">'
            '<div data-test="ruleView-C-result">Complete <span>3</span> units from: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/5d1f71bd94e82e2400a236e5" target="_blank">WRIT303</a>'
            ' <!-- -->-<!-- --> <!-- -->Poetry Workshop<!-- --> <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/5d1f69d7d2bc1524008cace0" target="_blank">WRIT304</a>'
            ' <!-- -->-<!-- --> <!-- -->Fiction Workshop<!-- --> <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/5d1f682e89944f24002acd8e" target="_blank">WRIT305</a>'
            ' <!-- -->-<!-- --> <!-- -->Playwriting Workshop<!-- --> <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/5d1f682794e82e2400a22fe2" target="_blank">WRIT316</a>'
            ' <!-- -->-<!-- --> <!-- -->Creative Nonfiction Workshop<!-- --> <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/63bf073f802d123791235b08" target="_blank">WRIT318</a>'
            ' <!-- -->-<!-- --> <!-- -->Screenwriting Workshop<!-- --> <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/5dd58afd125f762400db8da1" target="_blank">WRIT320</a>'
            ' <!-- -->-<!-- --> <!-- -->Writing and Film Production Workshop<!-- --> <span style="margin-left:5px">(1.5)</span></span></li>'
            '</ul></div>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"    : TYPE_UNITS_FROM_COURSE,
            "units"   : 3.0,
            "courses" : ["WRIT303", "WRIT304", "WRIT305", "WRIT316", "WRIT318", "WRIT320"],
        }


    # ----- Type: BASE_UFS --------------------
    def test_ufs_minimum_no_subject(self):
        """
        `"Completed a minimum of N units"` -> BASE_UFS with `subjects=None`.
        Source: Line 34 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result"><div>completed a minimum of 12 units</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 12.0,
            "subjects"  : None,
            "lvl_range" : {"min": -1, "max": -1},
        }


    def test_ufs_bare_subject_and_level(self):
        """
        `"N units of X-level SUBJECT courses."` -> BASE_UFS with subject and level.
        Source: Line 140.
        """
 
        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result"><div>9 units of 200-level ART courses.</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )
 
        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 9.0,
            "subjects"  : ["ART"],
            "lvl_range" : {"min": 200, "max": 299},
        }


    def test_ufs_minimum_with_subject_and_level(self):
        """
        `"Minimum N units of X-level SUBJECT_1 or SUBJECT_2 courses"` -> BASE_UFS.
        Source: Line 8 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result"><div>Minimum 3 units of 300-level AHVS or HA courses</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 3.0,
            "subjects"  : ["AHVS", "HA"],
            "lvl_range" : {"min": 300, "max": 399},
        }


    def test_ufs_span_range_single_subject(self):
        """
        `"Complete N units from [SUBJECTS] LO - HI"` -> BASE_UFS with subject and numeric lvl_range.
        Source: Line 1203.
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">'
            'Complete <span>1.5</span> units from <span>HSTR</span> <span>100</span> - <span>299</span>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 1.5,
            "subjects"  : ["HSTR"],
            "lvl_range" : {"min": 100, "max": 299},
        }


    def test_ufs_span_range_multi_subject(self):
        """
        `"Complete N units from [SUBJECTS] LO - HI"` -> BASE_UFS with multiple subjects.
        Source: Line 2064 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">'
            'Complete <span>1.5</span> units from <span>MATH</span> <span>or STAT</span> <span>100</span> - <span>499</span>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 1.5,
            "subjects"  : ["MATH", "STAT"],
            "lvl_range" : {"min": 100, "max": 499},
        }


    def test_ufs_structured_div_subject_only(self):
        """
        `"Complete N units of: [SUBJECTS] courses"` -> BASE_UFS, no level constraint.
        Source: Line 1746 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">'
            'Complete <span>4.5</span> units of: <div>PHIL courses</div>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 4.5,
            "subjects"  : ["PHIL"],
            "lvl_range" : {"min": -1, "max": -1},
        }


    def test_ufs_structured_div_no_hyphen_level(self):
        """
        `"Complete N units of: X level [SUBJECTS]"` -> BASE_UFS with no-hyphen level.
        Source: Line 824 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">'
            'Complete <span>1.5</span> units of: <div>100 level PHYS</div>'
            '</div></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 1.5,
            "subjects"  : ["PHYS"],
            "lvl_range" : {"min": 100, "max": 199},
        }


    def test_ufs_composite_course_and_units(self):
        """
        `"COURSE and N units of SUBJECT courses"` -> ALL [COURSE, BASE_UFS].
        Source: Line 1748 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result"><div>PHIL 203 and 3 units of PHIL courses</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "logic"    : SELECT_ALL,
            "children" : [
                {"type": TYPE_COURSE, "code": "PHIL203"},
                {
                    "type"      : TYPE_UNITS_FROM_SUBJECT,
                    "units"     : 3.0,
                    "subjects"  : ["PHIL"],
                    "lvl_range" : {"min": -1, "max": -1},
                },
            ],
        }


    def test_ufs_range_level(self):
        """
        `"N units of X- or Y-level [SUBJECTS] courses"` -> BASE_UFS with range lvl_range.
        Source: Line 1144 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result"><div>4.5 units of 300- or 400-level GNDR or WS courses</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 4.5,
            "subjects"  : ["GNDR", "WS"],
            "lvl_range" : {"min": 300, "max": 499},
        }


    def test_ufs_comma_separated_subjects(self):
        """
        `"N units of X- or Y-level [SUBJECTS] courses"` -> BASE_UFS with comma subjects.
        Source: Line 1552 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result"><div>6.0 units of 300- or 400-level BIOL, EPHE, or MEDS courses</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 6.0,
            "subjects"  : ["BIOL", "EPHE", "MEDS"],
            "lvl_range" : {"min": 300, "max": 499},
        }


    def test_ufs_no_subject_codes_falls_through_to_text(self):
        """
        `"N units of X-level LONGNAME courses"` where `LONGNAME` is the full name of a subject -> BASE_TEXT 
        (cannot identify qualifying courses without a subject code).
        Source: Line 150 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result"><div>9 units of 300-level Visual Arts courses</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type" : TYPE_TEXT,
            "text" : "9 units of 300-level Visual Arts courses",
        }


    def test_ufs_bare_minimum_no_subject_no_level(self):
        """
        `"completed a minimum of N units"` with no subject and no level -> BASE_UFS,
        `subjects=None`.
        Source: Line 34 (isolated).
        """

        html = (
            '<div><div><div><ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result"><div>completed a minimum of 12 units</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "type"      : TYPE_UNITS_FROM_SUBJECT,
            "units"     : 12.0,
            "subjects"  : None,
            "lvl_range" : {"min": -1, "max": -1},
        }


# ----- 3. Complex/Composite Tree Structure Verification Tests --------------------
class TestPrereqParserCompositeNodes:
    """
    Tests for the 2 structural patterns that combine multiple base nodes:
    - Wrapper `<li>` with `"Complete all/N of the following"` span
    - `<div>` with `<span class="rules_groupHeader_37">`
    Both patterns can contain further nested nodes, producing a tree.
    """

    # ----- Wrapper <li>: Complete all of the following --------------------
    def test_wrapper_li_all_of_following(self):
        """
        `"Complete all of the following"` wrapper containing an ANY (`n=1`) course rule and a plain 
        text rule -> ALL node with two children: ANY node and BASE text node.
        Source: Line 83.
        """

        html = (
            '<div><div><div><ul>'
            '<li><span>Complete <!-- -->all<!-- --> of the following</span>'
            '<ul>'
            '<li data-test="ruleView-A">'
            '<div data-test="ruleView-A-result">Complete <span>1</span> of: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/6839d39dfab5d1d1354ed2fb" target="_blank">ANTH250</a>'
            ' <!-- -->-<!-- --> <!-- -->Biological Anthropology<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '<li><span><a href="#/courses/view/64c6ab1a9c2bcc8d794c5046" target="_blank">ANTH251</a>'
            ' <!-- -->-<!-- --> <!-- -->Human Evolutionary Biology<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '</ul></div>'
            '</div></li>'
            '<li data-test="ruleView-B">'
            '<div data-test="ruleView-B-result"><div>Minimum third-year standing</div></div>'
            '</li>'
            '</ul></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "logic": SELECT_ALL,
            "children": [
                {
                    "logic": SELECT_ANY_N,
                    "n": 1,
                    "children": [
                        {"type": TYPE_COURSE, "code": "ANTH250"},
                        {"type": TYPE_COURSE, "code": "ANTH251"}
                    ]
                },
                {"type": TYPE_TEXT, "text": "Minimum third-year standing"}
            ]
        }


    # ----- Wrapper <li>: Complete N of the following --------------------
    def test_wrapper_li_any_1_of_following(self):
        """
        `"Complete 1 of the following"` wrapper containing an ALL course rule and a text rule -> 
        ANY (`n=1`) node with two children: ALL node and BASE text node.
        Source: Line 107.
        """

        html = (
            '<div><div><div><ul>'
            '<li><span>Complete <!-- -->1<!-- --> of the following</span>'
            '<ul>'
            '<li data-test="ruleView-C">'
            '<div data-test="ruleView-C-result">Complete all of: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/647e6d6f40cd47aa7e166dae" target="_blank">ANTH350</a>'
            ' <!-- -->-<!-- --> <!-- -->Primate Behaviour and Conservation<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '</ul></div>'
            '</div></li>'
            '<li data-test="ruleView-B">'
            '<div data-test="ruleView-B-result"><div>Permission of the program</div></div>'
            '</li>'
            '</ul></li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "logic": SELECT_ANY_N,
            "n": 1,
            "children": [
                {
                    "logic": SELECT_ALL,
                    "children": [{"type": TYPE_COURSE, "code": "ANTH350"}]
                },
                {"type": TYPE_TEXT, "text": "Permission of the program"}
            ]
        }


    # ----- <div> with <span class="rules_groupHeader_37"> --------------------
    def test_group_header_div(self):
        """
        A `<div>` containing an empty `<span class="rules_groupHeader_37">` and a wrapper `<li>` forces
        ANY (`n=1`) logic. The wrapper `<li>`'s children are themselves nested under another ANY (`n=1`).
        Source: Line 1738.
        """

        html = (
            '<div><div><div><ul>'
            '<div>'
            '<span class="rules_groupHeader_37"></span>'
            '<li><span>Complete <!-- -->1<!-- --> of the following</span>'
            '<ul>'
            '<li data-test="ruleView-D.1">'
            '<div data-test="ruleView-D.1-result">Complete all of: '
            '<div><ul style="margin-top:5px;margin-bottom:5px">'
            '<li><span><a href="#/courses/view/5d1f75bf94e82e2400a239c2" target="_blank">PHIL207A</a>'
            ' <!-- -->-<!-- --> <!-- -->Introduction to Ancient Philosophy<!-- -->'
            ' <span style="margin-left:5px">(1.5)</span></span></li>'
            '</ul></div>'
            '</div></li>'
            '<li data-test="ruleView-D.2">'
            '<div data-test="ruleView-D.2-result"><div>4.5 units of PHIL courses</div></div>'
            '</li>'
            '</ul></li>'
            '</div>'
            '<li data-test="ruleView-B">'
            '<div data-test="ruleView-B-result"><div>or permission of the department.</div></div>'
            '</li>'
            '</ul></div></div></div>'
        )

        assert PrereqParser().parse(html) == {
            "logic": SELECT_ANY_N,
            "n": 1,
            "children": [
                {
                    "logic": SELECT_ANY_N,
                    "n": 1,
                    "children": [
                        {
                            "logic": SELECT_ALL,
                            "children": [{"type": TYPE_COURSE, "code": "PHIL207A"}]
                        },
                        {
                            "type": TYPE_UNITS_FROM_SUBJECT,
                            "units": 4.5,
                            "subjects": ["PHIL"],
                            "lvl_range": {"min": -1, "max": -1}
                        }
                    ]
                },
                {"type": TYPE_TEXT, "text": "or permission of the department."}
            ]
        }


# ----- 4. Regression Tests on Real Sample Data --------------------
class TestPrereqParserRealSamples:
    """
    Regression suite against all lines in `prereq_html_samples.txt`.

    Each line is a real prereq HTML snippet from the UVic Kuali API.
    These tests check that the parser returns valid-looking output and does not crash. It does not check 
    the exact parsed result for every sample.

    The fixture skips gracefully when the sample file is not present.
    """

    @pytest.fixture(scope="class")
    def sample_lines(self) -> list[str]:
        """Returns a list of HTML samples."""

        path = Path(__file__).parent / SAMPLE_FILENAME

        if not path.exists():
            pytest.skip("prereq_html_samples.txt not found")

        with open(path, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]


    @pytest.fixture(scope="class")
    def parsed_samples(self, sample_lines: list[str]) -> list[dict | None]:
        """
        Pre-parses all samples once. Stores `None` for any line that raises an exception, so structural 
        tests can skip those lines without re-raising.
        """

        results = []

        for html in sample_lines:
            try:
                results.append(PrereqParser().parse(html))
            except Exception:
                results.append(None)

        return results


    def test_no_parse_errors(self, sample_lines: list[str], parsed_samples: list[dict | None]):
        """
        Every sample must parse without raising any exception.
        Only re-parses lines where `parsed_samples` recorded `None` (i.e. samples which caused 
        `PrereqParser` to raise an exception), so the error is captured and reported cleanly.
        """

        errors = []

        for i, result in enumerate(parsed_samples):
            if result is not None:
                continue

            try:
                PrereqParser().parse(sample_lines[i])
            except Exception as e:
                errors.append(f"Line {i + 1}: {type(e).__name__}: {e}")

        assert not errors, (
            f"{len(errors)} of {len(sample_lines)} samples raised errors:\n"
            + "\n".join(errors[:10])
        )


    def test_all_results_are_dicts(self, parsed_samples: list[dict | None]):
        """Every parsed result must be a dict."""

        for i, result in enumerate(parsed_samples):
            if result is None:
                continue

            assert isinstance(result, dict), f"Line {i + 1}: got {type(result).__name__}"


    def test_all_results_have_logic_or_type(self, parsed_samples: list[dict | None]):
        """Top-level result must have either 'logic' (composite) or 'type' (leaf) key."""

        for i, result in enumerate(parsed_samples):
            if result is None:
                continue

            assert "logic" in result or "type" in result, (
                f"Line {i + 1}: result has neither 'logic' nor 'type': {result}"
            )


    def test_logic_nodes_have_non_empty_children(self, parsed_samples: list[dict | None]):
        """Any node with 'logic' must have a non-empty 'children' list (checked recursively)."""

        def check(node: dict, line_num: int):
            if "logic" in node:
                assert isinstance(node.get("children"), list) and len(node["children"]) > 0, (
                    f"Line {line_num}: logic node has empty or missing children: {node}"
                )

                for child in node["children"]:
                    check(child, line_num)

        for i, result in enumerate(parsed_samples):
            if result is not None:
                check(result, i + 1)


    def test_any_nodes_have_positive_int_n(self, parsed_samples: list[dict | None]):
        """Every ANY node must have an integer `n>=1` (checked recursively)."""

        def check(node: dict, line_num: int):
            if node.get("logic") == SELECT_ANY_N:
                n = node.get("n")

                assert isinstance(n, int) and n >= 1, (
                    f"Line {line_num}: ANY node has invalid n={n!r}"
                )
            
            for child in node.get("children", []):
                check(child, line_num)

        for i, result in enumerate(parsed_samples):
            if result is not None:
                check(result, i + 1)


    def test_course_nodes_have_non_empty_string_code(self, parsed_samples: list[dict | None]):
        """Every course leaf node must have a non-empty string `"code"` (checked recursively)."""

        def check(node: dict, line_num: int):
            if node.get("type") == TYPE_COURSE:
                code = node.get("code")
                assert isinstance(code, str) and code.strip(), (
                    f"Line {line_num}: course node has invalid code={code!r}"
                )

            for child in node.get("children", []):
                check(child, line_num)

        for i, result in enumerate(parsed_samples):
            if result is not None:
                check(result, i + 1)


    def test_text_nodes_have_non_empty_string_text(self, parsed_samples: list[dict | None]):
        """Every BASE_TEXT node must have a non-empty string `"text"` (checked recursively)."""

        def check(node: dict, line_num: int):
            if node.get("type") == TYPE_TEXT:
                text = node.get("text")
                assert isinstance(text, str) and text.strip(), (
                    f"Line {line_num}: text node has invalid text={text!r}"
                )

            for child in node.get("children", []):
                check(child, line_num)

        for i, result in enumerate(parsed_samples):
            if result is not None:
                check(result, i + 1)


    def test_ufc_nodes_have_required_keys(self, parsed_samples: list[dict | None]):
        """
        Every BASE_UFC node must have `units` (non-negative float) and `courses` (non-empty list of 
        strings) (checked recursively).
        """

        def check(node: dict, line_num: int):
            if node.get("type") == TYPE_UNITS_FROM_COURSE:
                units = node.get("units")
                assert isinstance(units, float) and units >= 0, (
                    f"Line {line_num}: UFC node has invalid units={units!r}"
                )

                courses = node.get("courses")
                assert (
                    isinstance(courses, list)
                    and len(courses) > 0
                    and all(isinstance(c, str) and c.strip() for c in courses)
                ), (
                    f"Line {line_num}: UFC node has invalid courses={courses!r}"
                )

            for child in node.get("children", []):
                check(child, line_num)

        for i, result in enumerate(parsed_samples):
            if result is not None:
                check(result, i + 1)


    def test_ufs_nodes_have_required_keys(self, parsed_samples: list[dict | None]):
        """
        Every BASE_UFS node must have `units` (non-negative float), `subjects` (list|None), 
        and `lvl_range` (dict with int `min` and `max`) (checked recursively).
        """

        def check(node: dict, line_num: int):
            if node.get("type") == TYPE_UNITS_FROM_SUBJECT:
                units = node.get("units")
                assert isinstance(units, float) and units >= 0, (
                    f"Line {line_num}: UFS node has invalid units={units!r}"
                )

                subjects = node.get("subjects")
                assert subjects is None or (isinstance(subjects, list) 
                                            and all(isinstance(s, str) for s in subjects)), (
                    f"Line {line_num}: UFS node has invalid subjects={subjects!r}"
                )

                lvl = node.get("lvl_range")
                assert (
                    isinstance(lvl, dict)
                    and isinstance(lvl.get("min"), int)
                    and isinstance(lvl.get("max"), int)
                ), (
                    f"Line {line_num}: UFS node has invalid lvl_range={lvl!r}"
                )

            for child in node.get("children", []):
                check(child, line_num)

        for i, result in enumerate(parsed_samples):
            if result is not None:
                check(result, i + 1)