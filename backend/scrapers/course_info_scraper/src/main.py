from __future__ import annotations

import re

from sqlalchemy import delete

from db.connection import db
from db.schema import Course
from shared.http_client import HTTPClient
from src.fetcher import CourseInfoFetcher
from src.prereq_parser import PrereqParser


# ----- Helper Methods --------------------
def _parse_subject(code: str) -> str:
    """
    Extracts subject code from course code. 
    E.g. `"CSC225"` -> `"CSC"`
    """

    return re.match(r"^(.*?)\d{3}", code).group(1)


def _parse_lvl(code: str) -> int:
    """
    Extracts course level from course code. 
    E.g. `"CSC225"` -> `200`
    """

    return (int(re.search(r"\d{3}", code).group()) // 100) * 100


# ----- Course Info Scraper Run --------------------
class CourseInfoScraper:
    @staticmethod
    async def run():
        """
        Full Course Info scraper run pipeline:
        - Fetches all UVic course data from the Kuali API
        - Parses prereq HTML
        - Writes everything to the DB in one transaction.

        On any failure the entire transaction is rolled back (no partial data writes).
        """

        with HTTPClient("UVic Course Info Scraper") as client:
            fetcher  = CourseInfoFetcher(client)
            courses  = fetcher.fetch_all_courses()

        print(f"Fetched {len(courses)} courses.")

        await db.create_tables()

        async with db.async_session() as session:
            async with session.begin():
                # Clear old data from tables
                await session.execute(delete(Course))

                print("Truncated existing data.")

                # Insert new course data
                for course in courses:
                    prereqs = None

                    if course.prereq_html:
                        prereqs = PrereqParser.parse(course.prereq_html)

                    session.add(Course(
                        code    = course.code,
                        subject = _parse_subject(course.code),
                        lvl     = _parse_lvl(course.code),
                        name    = course.name,
                        credits = course.credits,
                        prereqs = prereqs,
                    ))

                print(f"Inserted {len(courses)} courses.")

        print("Scraper run complete.")