# ===== UVic Course Info Scraper ====================
_UVIC_BASE  = "https://www.uvic.ca"
_KUALI_BASE = "https://uvic.kuali.co/api/v1/catalog"

CALENDAR_URL = f"{_UVIC_BASE}/calendar/future/undergrad/index.php"

def subject_codes_url(catalog_id: str) -> str:
    return f"{_UVIC_BASE}/BAN1P/pkg_kuali_api.pr_get_catalog?p_catalog={catalog_id}"

def all_courses_url(catalog_id: str) -> str:
    return f"{_KUALI_BASE}/courses/{catalog_id}?q="

def course_detail_url(catalog_id: str, course_pid: str) -> str:
    return f"{_KUALI_BASE}/course/{catalog_id}/{course_pid}"

def course_page_url(course_pid: str) -> str:
    return f"{_UVIC_BASE}/calendar/future/undergrad/index.php#/courses/{course_pid}"
# ===================================================