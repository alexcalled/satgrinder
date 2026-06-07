# SAT Grinder

SAT Grinder is a Django web app for SAT practice, skill tracking, domain ELO,
and grind-mode question sessions.

The live project is hosted at [satgrinder.com](satgrinder.com).

## Why SAT Grinder

SAT Grinder helps students focus their limited study time on the skills that
need the most work. It turns individual question results into clear skill,
domain, and overall progress instead of treating every practice session alike.

## Features

- Adaptive Reading, Writing, and Math practice sessions.
- Skill competence tracking and domain-based ELO ratings.
- Immediate answer feedback with explanations and score-change summaries.
- Profile statistics, domain breakdowns, and a live top-eight leaderboard.
- Question importing, admin tools, and an in-session SAT reference panel.

## Learning Techniques

- **Targeted practice:** Weaker skills are more likely to appear in a session.
- **Instant feedback:** Answers are reviewed before the student moves on.
- **Error correction:** Incorrect responses show the correct answer and explanation.
- **Progress visibility:** Skill competence and ELO changes make improvement measurable.
- **Repeated retrieval:** Grinding reinforces knowledge through active question solving.

## Requirements

- Python 3.13
- Docker and Docker Compose
- Git


# Installation

## 1. Clone the Project

```bash
git clone <repo-url>
cd satgrinder
```

## 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

## 3. Create the Environment File

Create a `.env` file in the project root:

```bash
touch .env
```

Add this local development configuration:

```env
DEBUG=True
SECRET_KEY=dev-only-secret-key
DATABASE_URL=postgres://satgrinder:satgrinder@localhost:5432/satgrinder
```

## 4. Start the Database

The project includes a Postgres service in `docker-compose.yml`.

```bash
docker compose up -d db
```

To check that it is running:

```bash
docker compose ps
```

## 5. Run Migrations

```bash
python manage.py migrate
```

## 6. Run the App

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Admin site:

```text
http://127.0.0.1:8000/admin
```


# Additional

## Create Admin Account

```bash
python manage.py createsuperuser
```

Admin site:

```text
http://127.0.0.1:8000/admin
```

## Import Questions

Questions can be imported from JSON with:

```bash
python manage.py import_questions path/to/questions.json
```

Validate a file without importing:

```bash
python manage.py import_questions path/to/questions.json --dry-run
```

Update an existing question with the same skill and prompt:

```bash
python manage.py import_questions path/to/questions.json --update-existing
```

### Question Import Format

```json
{
  "questions": [
    {
      "skill": "linear-equations-in-one-variable",
      "prompt": "Solve 2x + 4 = 10.",
      "explanation": "Subtract 4 from both sides, then divide by 2.",
      "difficulty": "medium",
      "choices": [
        { "text": "2", "is_correct": false },
        { "text": "3", "is_correct": true },
        { "text": "4", "is_correct": false },
        { "text": "5", "is_correct": false }
      ]
    }
  ]
}
```

Difficulty can be:

- `easy`
- `medium`
- `hard`

Each question must have exactly one correct answer choice.

## 9. Run Tests

Use SQLite for a quick local test run:

```bash
DATABASE_URL=sqlite:///db.sqlite3 python manage.py test core grinder
```

Run Django's system checks:

```bash
python manage.py check
```

## Useful Development Commands

Start Postgres:

```bash
docker compose up -d db
```

Stop Postgres:

```bash
docker compose down
```

Stop Postgres and delete its stored data:

```bash
docker compose down -v
```

Make migrations after model changes:

```bash
python manage.py makemigrations
python manage.py migrate
```

## Common Issues

### `DATABASE_URL` is missing

Make sure `.env` exists and includes:

```env
DATABASE_URL=postgres://satgrinder:satgrinder@localhost:5432/satgrinder
```

### Postgres connection refused

Start the database:

```bash
docker compose up -d db
```

Then retry:

```bash
python manage.py migrate
```

### Port 5432 is already in use

Another Postgres server may already be running. Either stop that server or change
the host port in `docker-compose.yml`.

### Port 8000 is already in use

Run Django on another port:

```bash
python manage.py runserver 127.0.0.1:8001
```

### Static files look stale

Restart the development server and refresh the browser.