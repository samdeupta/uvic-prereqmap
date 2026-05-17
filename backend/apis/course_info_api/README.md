# Course Info API

## Overview

A read-only FastAPI service that exposes UVic course and prerequisite data from the database. All endpoints are prefixed with `/course-info-api/courses`.

---

## Fields

All endpoints support field selection via the `fields` query parameter. The valid fields are:

| Field | Type | Description |
|---|---|---|
| `code` | `string` | Full course code, e.g. `"CSC110"` |
| `subject` | `string` | Subject prefix extracted from code, e.g. `"CSC"` |
| `lvl` | `integer` | Course level rounded to the nearest hundred, e.g. `100` |
| `name` | `string` | Course title |
| `credits` | `float` | Minimum credit value |
| `prereqs` | `JSON` or `null` | Parsed prerequisite tree. See the course info scraper README for the full output schema |

---

## Endpoints

### `GET /course-info-api/courses/`

Returns all courses. Supports optional field selection and filtering.

**Query Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `fields` | `string` | No | Comma-separated list of fields to return. Returns all fields if omitted |
| `lvl` | `integer` | No | Filter by course level. e.g. `300` returns all 300-level courses |
| `subject` | `string` | No | Filter by subject code. Case-insensitive. e.g. `CSC` or `csc` |

`lvl` and `subject` can be combined to filter by both simultaneously.

**Responses:**

`200 OK` — returns a list of course objects. Returns an empty list if no courses match the filters.

```json
[
    {
        "code": "CSC225",
        "subject": "CSC",
        "lvl": 200,
        "name": "Algorithms and Data Structures I",
        "credits": 1.5,
        "prereqs": {
            "logic": "ALL",
            "children": [
                {"type": "course", "code": "CSC115"}
            ]
        }
    },
    ...
]
```

`400 Bad Request` — returned when one or more field names in the `fields` parameter are invalid.

```json
{
    "detail": "Invalid field(s): foo. Valid fields are: code, credits, lvl, name, prereqs, subject."
}
```

---

### `GET /course-info-api/courses/{code}`

Returns a single course by its course code.

**Path Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `code` | `string` | Yes | Course code. Case-insensitive. e.g. `CSC225` or `csc225` |

**Query Parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `fields` | `string` | No | Comma-separated list of fields to return. Returns all fields if omitted |

**Responses:**

`200 OK` — returns a single course object.

```json
{
    "code": "CSC225",
    "subject": "CSC",
    "lvl": 200,
    "name": "Algorithms and Data Structures I",
    "credits": 1.5,
    "prereqs": {
        "logic": "ALL",
        "children": [
            {"type": "course", "code": "CSC115"}
        ]
    }
}
```

`400 Bad Request` — returned when one or more field names in the `fields` parameter are invalid.

```json
{
    "detail": "Invalid field(s): foo. Valid fields are: code, credits, lvl, name, prereqs, subject."
}
```

`404 Not Found` — returned when no course with the given code exists in the database.

```json
{
    "detail": "Course 'CSC999' not found."
}
```