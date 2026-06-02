# BINNA — Master Context File

> Shared memory for the dual-AI workflow.
> **Gemini** = Architect (designs logic, schema, UI). **Claude Code** = Builder (reads the real codebase, implements, tests).
> Keep this file in sync after every major feature.

---

## Project Overview

**BINNA** is a Construction Project Management (PM) system built for the **Iraqi construction market** (e.g. cumulative payment rules, bilingual EN/AR content, BOQ/VO contract workflows).

- **Production:** https://binnapm.com (Render.com, auto-deploys on push to `main`)
- **Repo:** https://github.com/malabasi35/BINNA (private)
- **Entry point:** `run.py` · production server `gunicorn run:app` · `Procfile: web: gunicorn run:app`

---

## Codebase Reality Sheet

> Verified against live files. Gemini should design against these constraints.

### Stack
- Flask app-factory: `create_app` in `app/__init__.py`
- Flask-SQLAlchemy, Flask-JWT-Extended, Flask-CORS
- Flask-Migrate is **installed but there is NO migrations folder** — the schema is created via `db.create_all()` at startup, **not** `flask db upgrade`. New models/columns appear after a DB recreate, not a migration.
- **DB:** SQLite locally (`binna.db`, git-ignored) · PostgreSQL on Render (`config.py` rewrites `postgres://` → `postgresql+psycopg://`)
- **Deploy:** push to `main` = live production deploy

### API surface — base `/api/v1`
Registered blueprints (`app/__init__.py`):
- `auth_bp` → `/api/v1/auth`
- `projects_bp` → `/api/v1/projects`
- Module blueprints are **nested under a project**: `/api/v1/projects/<int:project_id>/<module>`
  - `dc`, `submittals`, `dr`, `lbt`, `financial`, `gantt`
- `uploads_bp` → its own full URL paths (JWT-protected `/api/v1/uploads/<filename>`)
- `pages_bp` → serves HTML pages

### Auth pattern (every protected route)
```python
@jwt_required()
def handler(...):
    uid = int(get_jwt_identity())   # identity is a STRING → cast to int
```
Access control helpers in `projects.py`:
- `_get_membership(project_id, user_id) -> (Project, ProjectMember) | (None, None)`
- `_requires_role(project_id, user_id, min_role) -> (Project, ProjectMember) | (None, None)`
- Role order: `viewer(0) < member(1) < admin(2) < owner(3)`

### Models (`app/models.py`)
`User`, `Project`, `ProjectMember`, `DCLetter`, `Archive`, `Submittal`, `DailyReport`, `LabTest`, `FinancialData`, `GanttData`.

- **Relational, countable per project:** `DCLetter`, `Archive`, `Submittal` (has `module_type` ∈ {dwg, fir, mir, ms, rfi}), `DailyReport`, `LabTest`.
- **JSON blobs (NOT relational), one row per project (`unique=True`):**
  - `FinancialData.data` (Text) → JSON: `{contractDetails:{}, boq:[], vo:[], payments:[], income:[], expenses:[], incomeCategories:[], expenseCategories:[], usdRate:1300}`
  - `GanttData.tasks` (Text) → JSON array of tasks
  - ⚠️ Any aggregation over financial/gantt data must `json.loads()` and compute in Python — there are no payment/task columns to `SUM`/`JOIN`.

### Conventions
- Auto-generated refs: `{PROJECT_CODE}-DR-001`, `{PROJECT_CODE}-ARC-001`, etc. — max existing number + 1, zero-padded to 3 digits.
- File uploads stored as `{uuid4().hex}_{secure_filename}`; downloaded via JWT-protected endpoint → frontend fetches with token → blob download.
- New project seeds a blank `FinancialData` record (`projects.py` create route).

### Frontend
- Vanilla JS, no framework.
- API client `static/js/binna-api.js` → `BINNA.get/post/put/del/upload` + `fetchFinancial`.
- Token in `localStorage['binna_token']`, sent as `Bearer`.
- Auth pages in `templates/` (`login.html`, `register.html`); legacy module pages `binna-<module>.html` at repo root, served via `pages_bp`.

---

## Endpoint Spec Checklist (for Gemini)
When specifying an endpoint, provide: method + full path (respect `/projects/<project_id>/...` nesting), target blueprint file, required role, request body shape, response JSON shape.

---

## Feature Log
| Date | Feature | Builder notes |
|------|---------|---------------|
| 2026-06-02 | Dashboard Stats endpoint `GET /api/v1/projects/<id>/stats` | Aggregates relational counts + JSON-blob lengths. See `app/routes/projects.py`. |
| 2026-06-02 | Dashboard Stats frontend wiring (`templates/project.html`) | Cards carry `id="stat-<key>"` via per-module `statKey`; `loadStats()` fills counters from the API. **Deviation:** the `financial` stat (payments/BOQ count) shows on the **Contract & Payment** card per Gemini's mapping; the income/expense **Financial** card and **Subcontractor** card have no counter (no matching stat). Cards are JS-generated, so IDs are assigned in `moduleCardHtml`, not static HTML. |
