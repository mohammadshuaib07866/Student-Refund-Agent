# Student Refund Support Agent

A conversational student support agent built with Google ADK, LiteLLM, OpenAI,
and SQLAlchemy. It looks up student enrollments, explains refund eligibility,
and records refund requests for review.

## Features

- Counts student records without exposing student details.
- Looks up students by their registered email and lists their enrollments.
- Checks the refund policy: purchase within 7 days and course completion at or
  below 20% (the limits are inclusive).
- Requests explicit confirmation before saving a refund request.
- Records requests as pending; it does not issue or transfer money.
- Reads refund request status from the database.

Refund amounts use the course price in the database. The current schema does
not store a separate amount paid for each enrollment.

## Project structure

```text
.
├── .gitignore                  # Ignore local environments, secrets, and caches
├── .python-version             # Project Python version
├── README.md                   # Project guide
├── pyproject.toml              # Project metadata and dependencies
├── uv.lock                     # Locked dependency versions
├── database/
│   └── students.db             # SQLite student, course, and refund data
└── refund_agent/
    ├── __init__.py
    ├── agent.py                # ADK agent and LiteLLM/OpenAI model config
    ├── .env                    # Local API key; do not commit
    ├── database/
    │   ├── connection.py       # SQLAlchemy engine and session factory
    │   └── models.py           # Student, course, enrollment, refund models
    └── tools/
        └── tools.py            # Database-backed agent tools
```

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)
- An OpenAI API key

## Setup

Install the project dependencies into the local environment:

```sh
uv sync
```

Set the OpenAI key in `refund_agent/.env`:

```dotenv
OPENAI_API_KEY=your_openai_api_key
```

The agent uses LiteLLM's `openai/gpt-4.1-mini` model route. Keep API keys
private; `.env` files are ignored by Git.

## Run

Start an interactive terminal session:

```sh
uv run adk run refund_agent
```

Start the ADK web interface:

```sh
uv run adk web
```

## Database

The application connects to `database/students.db`. SQLAlchemy sessions and
SQLite foreign-key enforcement are configured in
`refund_agent/database/connection.py`. The existing database contains the
tables described by the ORM models; refund requests are saved in
`refund_requests` with an initial `PENDING` status.
