# UVic PrereqMap

UVic PrereqMap is a course prerequisite mapping tool for visualizing how University of Victoria courses connect through prerequisite relationships.

The goal is to make course planning easier by turning nested prerequisite requirements into a clearer graph-based structure.

---

## Current Status

This project is currently in early development.

The repository currently contains backend work including:

- Course information API structure
- Database connection and schema files
- Course information scraping modules
- Environment configuration examples

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
│   ├── db/
│   ├── scrapers/
│   ├── .env.example
│   └── .gitignore
├── frontend/
├── infra/
└── README.md
```

---

## Tech Stack

- Python
- PostgreSQL

Additional technologies will be added as development continues.