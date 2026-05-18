import uvicorn

from course_info_api.src.main import CourseInfoAPI


def main():
    course_info_api = CourseInfoAPI.create()
    uvicorn.run(course_info_api, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()