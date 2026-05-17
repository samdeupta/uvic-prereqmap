import asyncio

from course_info_api.src.main import CourseInfoAPI


async def main():
    await asyncio.gather(
        CourseInfoAPI.create()
    )


if __name__ == "__main__":
    asyncio.run(main())