# UVic PrereqMap

UVic PrereqMap is a course prerequisite mapping tool for visualizing how University of Victoria courses connect through prerequisite relationships.

The goal is to make course planning easier by turning nested prerequisite requirements into a clearer graph-based structure.

---

## Current Status

The backend is feature-complete for data acquisition and serving. A frontend has not yet been started.

The repository currently contains:

- **Course Info Scraper** — a full scraping pipeline that fetches all UVic course data from the Kuali API, parses prerequisite HTML into a structured tree, and writes everything to a PostgreSQL database in a single atomic transaction
- **Prerequisite Parser** — a recursive HTML parser handling 10 distinct prerequisite input patterns from the Kuali API, with a comprehensive unit and regression test suite (2,253 real samples)
- **Course Info API** — a read-only FastAPI service exposing course and prerequisite data with filtering by subject and level
- **Database layer** — PostgreSQL schema and async SQLAlchemy connection management
- **Docker / Compose setup** — separate Dockerfiles and a Compose file for the API service and scraper

---

## Project Motivation

University course prerequisites can become difficult to track because one course may depend on several others, each with their own prerequisite requirements.

UVic PrereqMap aims to simplify this process by representing prerequisite chains visually instead of requiring students to manually navigate course calendar pages.

---

## Planned Features

- Search for a UVic course
- Display prerequisite relationships as an interactive graph
- Support prerequisite groups such as:
  - `"Complete any 1 of:"`
  - `"Complete all of:"`
- Provide a clearer view of possible prerequisite paths

---

## Repository Structure

```txt
uvic-prereqmap/
├── backend/
│   ├── apis/
│   │   └── course_info_api/
│   ├── db/
│   ├── scrapers/
│   │   └── course_info_scraper/
│   └── .gitignore
├── infra/
│   └── docker/
├── .env.example
├── .gitignore
└── README.md
```

---

## Tech Stack

- **Python** — scraper, parser, and API
- **FastAPI** — Course Info API
- **PostgreSQL** — course and prerequisite storage
- **SQLAlchemy (async)** — database access layer
- **BeautifulSoup4** — prerequisite HTML parsing
- **Docker / Docker Compose** — containerised deployment

---

## Running Locally

Copy `.env.example` to `.env` and fill in your database credentials, then:

```bash
# Start the API server
docker compose -f infra/compose.yml up apis

# Run the scraper (one-shot)
docker compose -f infra/compose.yml run scrapers
```

The API will be available at `http://localhost:8000`. See `backend/apis/course_info_api/README.md` for full endpoint documentation.