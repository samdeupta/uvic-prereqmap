import asyncio

from course_info_scraper.src.main import CourseInfoScraper


async def main():
    await CourseInfoScraper.run()


if __name__ == "__main__":
    asyncio.run(main())