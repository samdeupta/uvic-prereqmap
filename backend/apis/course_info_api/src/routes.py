from __future__ import annotations

import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.connection import db
from db.schema import Course


# ----- Constants --------------------
VALID_FIELDS = frozenset({"code", "subject", "lvl", "name", "credits", "prereqs", "coreqs"})
_LVL_RANGE_RE = re.compile(r"^(\d{3})-(\d{3})$")


# ----- Helper Methods --------------------
def _parse_fields(fields: str | None) -> list[str] | None:
    """
    Parses and validates the comma-separated fields param.
    Returns `None` if fields param was not provided (return all columns).
    Raises `400` if any field name is invalid.
    """

    if fields is None:
        return None

    requested = [f.strip() for f in fields.split(",") if f.strip()]

    invalid = set(requested) - VALID_FIELDS

    if invalid:
        raise HTTPException(
            status_code = 400,
            detail      = f"Invalid field(s): {', '.join(sorted(invalid))}. Valid fields are: {', '.join(sorted(VALID_FIELDS))}."
        )

    return requested


def _parse_lvl(lvl: str | None) -> tuple[int, int] | None:
    """
    Parses the `lvl` query parameter into an inclusive `(min, max)` integer range.

    Accepted formats:
    - Type 1 (single value): `"<VAL>"`      -> `(<VAL>, <VAL>)`
    - Type 2 (range):        `"<LO>-<HI>"`  -> `(<LO>, <HI>)`

    Returns `None` if `lvl` is `None`.
    Raises `400` if the value is not a valid integer, not a valid `min-max` range string,
    or if `min > max`.
    """

    if lvl is None:
        return None

    lvl = lvl.strip()

    # CASE: Type 2
    m = _LVL_RANGE_RE.match(lvl)

    if m:
        lo, hi = int(m.group(1)), int(m.group(2))

        if lo > hi:
            raise HTTPException(
                status_code = 400,
                detail      = f"Invalid lvl range '{lvl}': min ({lo}) must not be greater than max ({hi})."
            )

        return (lo, hi)

    # CASE: Type 1
    if re.match(r"^\d{3}$", lvl):
        return (int(lvl), int(lvl))

    raise HTTPException(
        status_code = 400,
        detail      = f"Invalid lvl value '{lvl}': expected a 3-digit integer (e.g. '300') or an inclusive 3-digit range (e.g. '200-399')."
    )


def _filter_fields(course: Course, fields: list[str] | None) -> dict:
    """
    Returns a dict of course attributes filtered to requested fields.
    Returns all fields if fields is `None`.
    """

    if fields is None:
        return {f: getattr(course, f) for f in VALID_FIELDS}

    return {f: getattr(course, f) for f in fields}


# ----- Router --------------------
router = APIRouter(prefix="/courses", tags=["courses"])


# ----- Routes --------------------
@router.get("/", response_model=list[dict])
async def get_courses(
    fields  : str | None = Query(default=None, description="Comma-separated list of fields to return. e.g. code,name,credits"),
    lvl     : str | None = Query(default=None, description="Filter by course level. Accepts a single value (e.g. 300) or an inclusive range (e.g. 200-399)."),
    subject : str | None = Query(default=None, description="Filter by subject code. e.g. CSC"),
    session : AsyncSession = Depends(db.get_session)) -> list[dict]:
    """
    Fetch all courses with optional field selection and filtering.

    :param fields: Comma-separated list of fields to return                                     (default: all)
    :param lvl: Filter by course level. Single value (e.g. `300`) or range (e.g. `200-399`).    (default: all)
    :param subject: Filter by subject code. E.g.: `"CSC"`                                       (default: all)
    """

    parsed_fields = _parse_fields(fields)
    lvl_range     = _parse_lvl(lvl)

    query = select(Course)

    if lvl_range is not None:
        lo, hi = lvl_range
        
        if lo == hi:
            query = query.where(Course.lvl == lo)
        else:
            query = query.where(Course.lvl >= lo, Course.lvl <= hi)

    if subject is not None:
        query = query.where(Course.subject == subject.upper())

    result  = await session.execute(query)
    courses = result.scalars().all()

    return [_filter_fields(c, parsed_fields) for c in courses]


@router.get("/{code}", response_model=dict)
async def get_course(
    code    : str,
    fields  : str | None = Query(default=None, description="Comma-separated list of fields to return. e.g. code,name,prereqs"),
    session : AsyncSession = Depends(db.get_session)) -> dict:
    """
    Fetch a single course by course code.

    :param code: Course code. E.g.: `"CSC225"`
    :param fields: Comma-separated list of fields to return (default: all)
    """

    parsed_fields = _parse_fields(fields)

    result = await session.execute(
        select(Course).where(Course.code == code.upper())
    )
    course = result.scalar_one_or_none()

    if course is None:
        raise HTTPException(status_code=404, detail=f"Course '{code}' not found.")

    return _filter_fields(course, parsed_fields)