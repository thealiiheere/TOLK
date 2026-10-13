# TOLK — developer guide

Education marketplace (startup MVP) connecting students and teachers: small online groups for languages and
"other" subjects. Runs as a Telegram Mini App + normal browser. UI languages: **uz (default), ru, en**.
Roles: `student`, `tutor` (shown as "teacher" in the UI), `admin`. Production: AWS EC2 with systemd + nginx
(see "Production" below).

## Stack

- Backend: FastAPI + SQLAlchemy 2 (typed `Mapped[]` models) + Alembic. PostgreSQL in prod, SQLite in dev/tests.
- Frontend: **no build step**. Plain ES modules + one CSS file served from `app/static/`. No frameworks, no CDN
  except `telegram.org` scripts. Hash routing (`#/path?query`).
- Auth: Telegram only (Mini App `initData` or Login Widget, HMAC-verified) → opaque bearer token
  (`sessions` table stores SHA-256 of it). Demo one-click login only when `DEMO_MODE=true` and only for `is_demo` users.
- Payments: manual. Student transfers to a card, uploads receipt → admin approves → student auto-enrolled.
- Video: no API. Teacher pastes a Zoom/Meet/Teams link **per lesson**; reuse of a link within a class is rejected.

## Commands (Windows dev box: use `.venv/Scripts/python.exe`)

```bash
python run.py                         # migrate + (demo seed if DEMO_MODE) + uvicorn --reload on :8000
python -m pytest                      # tests/ (signed initData, temp SQLite; ~19 tests, ~6 s)
python -m app.seed [--reset]          # demo data; --reset drops all tables (refused in production)
alembic revision --autogenerate -m "msg"   # after changing app/models.py, then review the file
alembic upgrade head
```

`.claude/launch.json` → `tolk-dev`: runs with SQLite `data/dev.db`, DEMO_MODE on (overrides `.env`).
Bash heredocs containing Uzbek apostrophes + Cyrillic sometimes fail to parse here: put one-off patch scripts in a
file (scratchpad) and run them with Python instead.

## File map

```
app/
  config.py      Settings (pydantic-settings, reads .env). All env vars live here. config_warnings() logged at startup.
  database.py    engine, SessionLocal, Base, get_db (SQLite pragmas: FK on, WAL)
  models.py      ORM: User, TutorDocument, Session, Group, Enrollment(table group_students), Payment, Lesson,
                 LessonRecord, LessonRating, HomeworkSubmission
  schemas.py     Pydantic request bodies + validators (meeting-link host allow-list, http URLs, language code,
                 course code format COURSE_CODE_RE)
  services.py    shared queries (tutor_ratings, enrolled_counts, notification recipients), course codes
                 (course_code_prefix, generate_course_code, ensure_course_code_free), add_tutor_documents,
                 + dict serializers (user_me, group_card, tutor_card, lesson_dict, review_dict, document_dict).
                 API response shapes live HERE.
  auth.py        Telegram signature checks, upsert_telegram_user, sessions, guards:
                 get_current_user → require_onboarded → require_admin / require_tutor / require_approved_tutor / require_student
  i18n.py        backend strings (API errors, Telegram notifications, bot welcome) in uz/ru/en; ApiError("key", status, **params)
  notify.py      best-effort Telegram messages via BackgroundTasks (never raises)
  uploads.py     private file storage (upload_dir/receipts, upload_dir/certificates): magic-byte type check, size limit,
                 random names, read_upload() validates before write_upload(); admin-only download endpoints
  seed.py        demo data (+ generated receipt and certificate images, auto course codes)
  main.py        app, error handlers (translate ApiError/validation via X-Lang), security headers + CSP,
                 /api/config, /health, static mount, index
  routers/
    auth.py      /api/auth: telegram, telegram-widget, demo-users, demo-login, me (GET/PATCH), logout,
                 onboarding (MULTIPART form: role, full_name, phone, bio, subjects, certificates[])
    catalog.py   /api/catalog (public): filters, groups (filters + sort + q search), groups/{id}, tutors/{id}
    student.py   /api/student: dashboard, enroll (multipart receipt), lessons/{id}/rate, homework
    tutor.py     /api/tutor: dashboard, documents (GET/POST multipart), groups/{id}/students, lessons (POST/PATCH),
                 lessons/{id}/cancel|complete, strikes
    admin.py     /api/admin: stats, payments (+receipt, review), groups CRUD (+students add/remove),
                 tutors (+decision with comment, +documents/{doc_id} file), users (+block), violations, strikes
  static/
    index.html   shell only (appbar, #view, tabbar, #toasts)
    css/app.css  design tokens on :root, dark theme via [data-theme=dark] (synced with Telegram colorScheme)
    js/core.js   state, html`` templating (auto-escapes), api(), router, on() event delegation, sheets, toasts,
                 formatting (price/date), avatar/stars/subjectInfo/subjectIcon/codeBadge, icons, session helpers
    js/i18n.js   UI dictionary: key → [uz, ru, en]; t(key, {params}); language names for class subjects
    js/app.js    boot (Telegram init, theme, session restore), routes table, top bar + bottom tab bar
    js/pages/    explore.js (catalog+filters), class.js (class page, teacher page, enroll sheet),
                 account.js (login, onboarding, profile), student.js, tutor.js, admin.js,
                 components.js (class cards, reviews, lesson rows, certificatesField/certificatesError/documentList)
alembic/versions/   0001_initial_schema, 0002_tutor_documents, 0003_course_code (data migration: backfills codes)
tests/              conftest.py (env, signed initData helper, Api client wrapper), test_api.py
telegram_bot.py     long-polling bot: /start → welcome + Mini App button, sets menu button. Separate process.
docker-compose.yml  alternative Docker deployment (caddy + web + bot + db) — NOT what production uses
```

## Domain rules (where they are enforced)

- **Catalog visibility**: group `is_published` AND has a tutor with `tutor_status="approved"` and not blocked
  (`catalog._public_groups`).
- **Catalog search** (`q`): case-insensitive substring over course code, title, subject, description, teacher name.
  Filters: category, subjects (comma list), price_min/max, min_rating (tutor average), has_seats; sort
  rating / price_asc / price_desc / newest.
- **Group**: `category` = `language` (subject = ISO code like `en`, validated/lowercased in `GroupIn`) or `other`
  (free-text subject). Price in UZS (int), `price_period` month/course/lesson, `max_students` (default 5).
- **Course code** (`Group.code`, NOT NULL, unique index): uppercase `[A-Z0-9][A-Z0-9-]{1,19}` (`invalid_course_code`).
  Admin may type one (stored uppercased) or leave it empty → `generate_course_code` gives `PREFIX-101`, `-102`, …
  (prefix = language code, or first 3 Latin letters of the subject, else `CRS`). On edit, empty = keep current code.
  Duplicates → 409 `course_code_taken`. Migration 0003 duplicates the prefix logic (migrations never import app code).
- **Enrollment**: student uploads receipt → `Payment(pending, group_id)`. Admin approve → `Enrollment` created
  (capacity checked; `group_full` if no seat). One pending payment per student+group.
- **Lessons**: tutor creates with `starts_at` (UTC, ≥ now-1h, ≤ +180d), `duration_min`, required `meet_link`
  (https + host in `MEETING_LINK_HOSTS`), link must not repeat within the class (`meeting_link_reused`).
  Statuses: scheduled → completed | cancelled. Complete only after start; records attendance + hw_status (done/none/strike).
  After completing a class with no upcoming lesson, the UI immediately opens "schedule next lesson".
- **Ratings**: 1–5 stars per student per lesson (unique). Allowed when the lesson has ended (by time, even if the
  tutor hasn't completed it), within 14 days, not cancelled, student not marked absent, and student enrolled
  (or has a record). Tutor rating = average of all their `LessonRating`s; drives catalog sort and `min_rating` filter.
- **3-strike rule**: `Enrollment.strikes` (max 3). At 3, the student no longer receives lesson links and can't submit homework.
- **Teacher sign-up / verification**: onboarding with role `tutor` requires subjects + bio ≥ 20 chars + **at least one
  certificate** (JPG/PNG/WEBP/PDF, ≤ 5 per upload, ≤ 10 total) → `tutor_status="pending"`. Documents are private
  (`TutorDocument`, `upload_dir/certificates`), only admins can open them. Admin **cannot approve without documents**
  (`tutor_no_documents`); rejection stores `User.tutor_review_note` (sent to the teacher). A rejected teacher who
  uploads new documents (`POST /api/tutor/documents`) goes back to `pending`. Teachers approved before this rule
  may have no documents; they stay approved.
- **Admins**: users in `ADMIN_TELEGRAM_IDS` are promoted at sign-in AND on their next authenticated request
  (`auth.get_current_user_optional`), so editing the env var + restarting is enough.
- **Blocking** a user deletes their sessions; blocked users get 403 `account_blocked`.

## Conventions

- **Never** build HTML with string concatenation of data: use `html```  (escapes everything) and `raw()` only for
  trusted markup. Strict CSP: no inline `<script>` and no `onclick=` attributes — use `data-action` / `data-submit` /
  `data-change` / `data-input` attributes with `on('name', handler)` from core.js.
- Every user-facing string goes through i18n in **all three languages**:
  frontend `t('key')` in `js/i18n.js`; backend errors `ApiError("key")` + entry in `app/i18n.py` MESSAGES.
  Pydantic validators raise `ValueError("<i18n key>")` and main.py maps it to the translated message.
- API errors are always `{"detail": "<translated>", "code": "<key>"}`. The frontend shows `detail`; tests assert `code`.
- Response dicts come from `services.py` serializers; datetimes are ISO strings in UTC (`iso()`), SQLite naive
  datetimes are treated as UTC (`aware()`).
- Schema change = edit `app/models.py` + new Alembic migration (autogenerate, then review; SQLite uses batch mode;
  replace `sa.text('(CURRENT_TIMESTAMP)')` with `sa.func.now()`). New NOT NULL column on a table with data →
  add nullable, backfill, then alter to NOT NULL (see 0003) or give it a `server_default`.
- Multipart endpoints: a pydantic `Form()` model can't be combined with `File()` params in FastAPI — declare
  `Form(...)` fields and build the model inside (see `routers/auth.py: onboarding`).
- ORM collections stay loaded after commit (`expire_on_commit=False`): append to relationships
  (`tutor.documents.append(doc)`) instead of `db.add(child)` when the parent's list is returned afterwards.
- Pages render into `#view` via `mount(view, html`...`)`; async page handlers receive `alive()` and must check it after awaits.
- Flags emoji don't render on Windows → language classes use a code tile (`subjectIcon`), not flags.
- Dates shown in the viewer's local time; `<input type=datetime-local>` values are converted with `new Date(v).toISOString()`.

## Recipes

- **New translated UI text**: add `key: [uz, ru, en]` to `D` in `js/i18n.js`, use `t('key', {param})`.
- **New API endpoint**: add to the relevant router with the right guard dependency; raise `ApiError`; add a test.
- **New field on Group**: models.py → migration → `GroupIn` (schemas.py) → `group_card` (services.py) →
  admin form `groupForm` + `group-save` body (pages/admin.js) → display in components.js / class.js.
  Searchable? add it to the `or_` in `catalog.list_groups`.
- **New page**: `route('/path', handler, {tab, role|auth, back})` in app.js; handler `(view, params, query, alive)`.
- **New notification**: add `n_*` key to `app/i18n.py`, call `background.add_task(notify, recipients, "n_key", **params)`.

## Production (AWS EC2, Ubuntu 26.04) — no Docker in use there

- URL: https://100-29-35-38.sslip.io (sslip.io hostname → Let's Encrypt cert via certbot, auto-renew timer).
  Bare IP and http redirect to it. Bot: @tolkplatformbot. API docs hidden (ENVIRONMENT=production), DEMO_MODE=false.
- Code `/srv/tolk` (git clone of `main`, owned by system user `tolk`), venv `/srv/tolk/.venv`,
  uploads `/srv/tolk/data/uploads`, settings `/srv/tolk/.env` (mode 600; secrets generated on the server — never print).
- systemd: `tolk-web` (uvicorn 127.0.0.1:8000, 2 workers, `alembic upgrade head` in ExecStartPre) and `tolk-bot`.
- nginx site `/etc/nginx/sites-available/tolk` (proxy + X-Forwarded-*, 12 MB body limit). PostgreSQL 18 local,
  role/db `tolk`. ufw allows OpenSSH + Nginx Full. 1 GB swap (instance has ~0.9 GB RAM, small disk).
- Deploy: `ssh ubuntu@100.29.35.38 "cd /srv/tolk && sudo -u tolk git pull --ff-only && sudo -u tolk .venv/bin/pip install -q -r requirements.txt && sudo systemctl restart tolk-web tolk-bot"`
- Before deploying a migration: `sudo -u postgres pg_dump tolk | gzip > /var/backups/tolk/before-<rev>-<date>.sql.gz`;
  for data migrations rehearse first on a copy (restore the dump into a scratch DB, run `alembic upgrade head`
  against it with DATABASE_URL overridden, then drop it).
- Logs: `sudo journalctl -u tolk-web -f` / `-u tolk-bot`; nginx in `/var/log/nginx/`.
- Change settings: edit `/srv/tolk/.env` with sudo, then `sudo systemctl restart tolk-web tolk-bot`.

## Gotchas

- Only one process may long-poll a bot token: stop any local `telegram_bot.py` when the server bot runs.
- `/static` is served with `Cache-Control: no-cache` (ETag revalidation) so deploys show up immediately.
- Receipts and certificates are never publicly served; the admin UI fetches them with the bearer token (blob URLs).
- `.env` in this repo points at a local Postgres and holds an old, revoked bot token; the dev launch config uses SQLite.
- Runtime data lives in `data/` (gitignored); old tracked artefacts (`app/tolk.db`, `app/uploads/`) were removed from git.
