# TOLK

An education platform that helps students and teachers find each other: online classes in small groups,
for languages and other subjects. Runs as a **Telegram Mini App** (and in a normal browser), in **Uzbek, Russian and English**.

- **Students** browse the catalog (filters: languages / other subjects, price range, teacher rating, free seats),
  enroll by paying to a card and uploading the receipt, join each lesson via its Zoom / Google Meet link,
  and rate every lesson with 1–5 stars.
- **Teachers** sign up themselves (admin approves), schedule lessons with a **new meeting link for every lesson**,
  mark attendance and homework (3-strike rule) and see their ratings.
- **Admins** create classes (price, seats, schedule, teacher), approve payments (which enrolls the student),
  approve teachers, manage users and discipline.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements-dev.txt
copy .env.example .env            # then set ENVIRONMENT=development and DEMO_MODE=true
python run.py                     # http://127.0.0.1:8000
```

With `DEMO_MODE=true` the sign-in page lists demo accounts (admin, teachers, students) for one-click login.
Without a `DATABASE_URL`, data is stored in SQLite at `data/tolk.db`.

```bash
python -m pytest                  # tests
python -m app.seed --reset        # wipe the dev database and re-create demo data
```

## Deploy

See [DEPLOY.md](DEPLOY.md) (AWS EC2 + Docker Compose + automatic HTTPS).

## Developer guide

See [CLAUDE.md](CLAUDE.md) for the architecture, conventions and how to make common changes.
