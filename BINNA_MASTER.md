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
- Flask-Migrate is **installed but there is NO migrations folder** — the schema is created via `db.create_all()` at startup, **not** `flask db upgrade`. `create_all()` only adds missing *tables*, never new *columns* on existing tables.
- **⚠️ NEVER drop/recreate the DB to pick up a new column — that destroys all production data.** Instead, new columns are added in place by the idempotent `_ensure_schema()` auto-migration in `run.py` (`ALTER TABLE … ADD COLUMN`), which runs after `create_all()` on every boot and self-heals on deploy. **When a model gains a column, append it to the `additions` list in `_ensure_schema()`.** (See the 2026-06-06 incident in the Session Log.)
- **DB:** SQLite locally (`binna.db`, git-ignored). A Render PostgreSQL instance **`binna-db` now exists** (provisioned 2026-06-16, free tier — **expires ~30 days, must upgrade before launch**) and is **empty**. `config.py` line 12 falls back to `sqlite:///binna.db` whenever `DATABASE_URL` is unset; the web service is currently **suspended** and its `DATABASE_URL` wiring to `binna-db` was **deliberately deferred** this session (see the credential incident in the 2026-06-16 Phase 0 log). ⚠️ **When the service is resumed, wire its `DATABASE_URL` to `binna-db`'s Internal URL** — otherwise it falls back to ephemeral container SQLite (wiped on every deploy/restart). `config.py` rewrites `postgres://` → `postgresql+psycopg://` automatically. **See the OPEN SECURITY TODO (password rotation) in the 2026-06-16 Phase 0 log before any real data enters the DB.**
- **Deploy:** push to `main` = live production deploy

### API surface — base `/api/v1`
Registered blueprints (`app/__init__.py`):
- `auth_bp` → `/api/v1/auth`
- `projects_bp` → `/api/v1/projects`
- Module blueprints are **nested under a project**: `/api/v1/projects/<int:project_id>/<module>`
  - `dc`, `submittals`, `dr`, `lbt`, `financial`, `gantt`, `parties`, `subcontracts`, `supply-agreements`, `global-parties` (+ `global-parties/seed` backfill, see Session Log 2026-06-13). `parties`, `subcontracts` **and** `supply-agreements` are all served by the single `subcontracts_bp`.
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
`Company`, `User`, `Project`, `ProjectMember`, `DCLetter`, `Archive`, `Submittal`, `DailyReport`, `LabTest`, `FinancialData`, `GanttData`, `Party`, `Subcontract`, `SupplyAgreement`, `GlobalParty`.

- **Multi-tenant (Phase 1, 2026-06-16):** `Company` (`companies` table) is the tenant root: `id, name, slug (unique), plan, max_users, trial_ends_at, grace_ends_at, status, created_at` (`plan`/`status` default `'trial'`, `max_users` 999, `status` ∈ `trial`/`active`/`grace`/`locked` = `VALID_COMPANY_STATUSES`). **Every tenant table carries `company_id`** (FK `companies.id`, nullable+indexed): `users, projects, project_members, dc_letters, archives, submittals, daily_reports, lab_tests, financial_data, gantt_data, parties, subcontracts, global_parties, supply_agreements`. ⚠️ **Two distinct role columns on `users`:** the pre-existing **`role`** is the PLATFORM role (`admin`|`user`; first-ever signup → `admin` = BINNA super-admin, set in `app/auth.py`) — **left untouched**; the NEW **`company_role`** is the TENANT role (`owner`|`admin`|`member`|`viewer`, default `viewer`). Also new on `users`: `email_verified` (bool, default false) + `email_verification_token` — **columns only; verification logic is Phase 2.** `company_id` is nullable because the signup→company wiring is Phase 2; nothing is backfilled (DB was emptied in Phase 0).

- **`GlobalParty`** (`global_parties` table) — flat per-project directory of every party (client/consultant/contractor/subcontractor/supplier/**laboratory**/other). Fields: `name_en`, `name_ar`, `role`, `logo_filename`, `notes`, `is_seeded` (true for the Client/Consultant/Contractor rows auto-seeded from the `Project` record — these can be edited but never deleted). Shared constants: `SEED_GLOBAL_PARTY_ROLES` (Project field → GlobalParty role, used by `create_project()` and the `/global-parties/seed` backfill) and `CREATABLE_GLOBAL_PARTY_ROLES` (roles a user can pick when adding a party manually — now includes `laboratory`).
  - **Auto-wiring (Session Log 2026-06-13/14):** adding a `subcontractor` GlobalParty auto-creates a `Subcontract`; adding a `supplier` auto-creates a `SupplyAgreement`. ⚠️ `Subcontract.party_id` FKs `parties.id` (the `Party` directory), **not** `global_parties.id` — auto-wiring mirrors the GlobalParty into a `Party` row first. `SupplyAgreement.global_party_id` FKs `global_parties` directly.

- **Subcontractor / Supplier module** (`app/routes/subcontracts.py`, payable direction):
  - **`Party`** (`parties`) — subcontract-module company directory; **`Subcontract`** (`subcontracts`) — agreement + payment blob in `data` JSON; the card template is driven by `data.payment_mode` (`cumulative`|`lump_sum`|`monthly`|`milestone`|`other`, default `cumulative`), **not** by the `kind` column.
  - **`SupplyAgreement`** (`supply_agreements`) — supplier PO: `global_party_id`, `ref` (`{CODE}-PO-NNN`), `description`, `po_value`, `currency`, `date_issued`, `status` (`open`|`partially_paid`|`closed`, derived server-side), `data` JSON `{payments:[], notes}`. Deliberately simple — no retention / cumulative / certificates. New table → built by `db.create_all()`.
  - **`LabTest.lab_party_id`** (FK `global_parties`, nullable) — links a lab test to a `laboratory` GlobalParty (the "Testing Lab" picker); added via `_ensure_schema()` `('lab_tests','lab_party_id','INTEGER')`.

- **Relational, countable per project:** `DCLetter`, `Archive`, `Submittal` (has `module_type` ∈ {dwg, fir, mir, ms, rfi}), `DailyReport`, `LabTest`.
- **JSON blobs (NOT relational), one row per project (`unique=True`):**
  - `FinancialData.data` (Text) → JSON: `{contractDetails:{}, boq:[], vo:[], payments:[], income:[], expenses:[], incomeCategories:[], expenseCategories:[], usdRate:1300, contract_type:'government'|'private', currency:'IQD'|'USD'|'EUR'|'custom', currency_custom:'', decimalPlaces:0, privateSettings:{}, cashflowSummary:{totalCertified,totalReceived,payments}}`
    - `payments[]` items now carry (added 2026-06-06): government fields (`boqItems`, `extraDeductions`, `surplusCredits`, `deductionReversals`, `penaltyDays/penaltyWaived/_penaltyOpen`, `releaseInitial/releaseFinal`, `received[]`, `attachments[]`, `_netDue/_received`) **and** private fields (`payment_mode:'private'`, `summaryRows[]`, `milestoneName/milestonePct`, `invoiceNo/period`, `scheduleLabel/schedulePct`, `privTaxEnabled/privTaxRate`, `relRet1/relRet2`).
  - `GanttData.tasks` (Text) → JSON array of tasks. Task items may carry a display-only `assignee:{type:'member'|'party', id, name}` (Session Log 2026-06-13/14) — no schema change.
  - `Subcontract.data` (Text) → JSON payment blob; carries `payment_mode` (drives the card template) plus the payable payment rows.
  - `GanttData.stoppages` (Text, default `'[]'`) → JSON array of **project-level** stoppage periods `{id,name,start,end,type:'holiday'|'weather'|'decision'|'other'}`. New column (added 2026-06-06) — needs a Render DB recreate to materialize; GET has a `getattr` fallback → `[]` and PUT rolls back to tasks-only if the column is missing.
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
- **Base template (Session Log 2026-06-15):** `templates/base.html` is the shared parent for the `templates/` SPA pages. **`dashboard.html`, `project.html`, `login.html`, `register.html` all `{% extends 'base.html' %}`.** base.html owns: `<head>` (meta, theme.js, theme.css, `{% block title %}`, Syne+DM Sans fonts, `{% block extra_css %}`), the shared Obsidian top-nav inside `{% block topbar %}` (guarded by `{% if not hide_nav %}`), `{% block content %}`, `{% block footer %}`, `binna-api.js`, and `{% block extra_js %}`. **login/register set `{% set hide_nav = true %}`** (nav-less). **project.html overrides `{% block topbar %}`** with its own back-button/project-context bar (keeps `#top-code`/`#top-name` JS hooks); dashboard uses the default nav. `extra_css` is injected **after** the base nav `<style>` so a page can override it. ⚠️ The legacy root `binna-*.html` module pages are **standalone** (NOT on base.html) — `index.html` and `404.html` too.
- **Theming (Session Log 2026-06-14, repalette 2026-06-15):** `static/css/theme.css` is the single source of truth. Each page's local `:root` vars are **aliased by name** to the canonical tokens (`--bg-base/--bg-surface/--brand-primary/...`), so **remapping the canonical tokens in theme.css recolors every page at once** — this is how the **Obsidian Crown** dark palette is applied site-wide (deep `#060608`, purple `#8B5CF6`/`#A78BFA`, gold `#C5A85A`). `:root` and `[data-theme="dark"]` now both carry Obsidian values + named tokens (`--bg-deep/--purple/--gold/--text-bright/--border-gold/...`); `body` is locked dark via `[data-theme] body{background:var(--bg-deep)!important}`. **`@media print` overrides the lock back to white paper** (sets `--bg-deep/--text-bright` + `body{background:#fff!important}`) so certificates never print dark. Self-contained pastel status pills kept as literal hex. theme.js (pre-paint) + theme.css linked into all ~22 pages.

---

## Endpoint Spec Checklist (for Gemini)
When specifying an endpoint, provide: method + full path (respect `/projects/<project_id>/...` nesting), target blueprint file, required role, request body shape, response JSON shape.

---

## Feature Log
| Date | Feature | Builder notes |
|------|---------|---------------|
| 2026-06-02 | Dashboard Stats endpoint `GET /api/v1/projects/<id>/stats` | Aggregates relational counts + JSON-blob lengths. See `app/routes/projects.py`. |
| 2026-06-02 | Dashboard Stats frontend wiring (`templates/project.html`) | Cards carry `id="stat-<key>"` via per-module `statKey`; `loadStats()` fills counters from the API. The `financial` stat (payments/BOQ count = Dhar'a/cumulative bills) shows on the **Contract & Payment** card. Cards are JS-generated, so IDs are assigned in `moduleCardHtml`, not static HTML. |
| 2026-06-02 | Cashflow metric for Financial card | Endpoint adds `cashflow = len(income) + len(expenses)` from the FinancialData blob; **Financial** card mapped via `statKey:'cashflow'` (`stat-cashflow`). **Subcontractor** card remains unmapped — its backend model is not yet architected (future session). |
| 2026-06-05 | Gantt collapse/expand fix (`binna-gantt.html`) | `visible()` rewritten to a forward-descendant sweep using `_effLevel(t)=(level||0)+(textIndent||0)`; a collapsed group hides only its true descendants (stops at the first peer/ancestor), no longer swallowing sibling groups. Stats-strip Groups count stays correct. |
| 2026-06-05 | Gantt indent/outdent level fix | Root cause of recurring collapse bug: `indentTask/outdentTask` only mutated `textIndent`, never `level`. Replaced with `_shiftSubtree(delta)` that operates on `level`, moves the whole subtree, folds `textIndent`→0, saves to DB immediately. |
| 2026-06-05 | Gantt demo/sample ("Pass 2") data removal | Removed seeded demo/sample task data and the server-side date-shifting in gantt recalc; added a circular-dependency guard to the gantt engine (see recent commits `639e5a3`, `bfe928f`, `c02f5a8`). |
| 2026-06-05 | Gantt selection ribbon + delete cleanup | `#sel-toolbar` given a fixed **40px in-flow** height (`min-height;box-sizing:border-box;flex-shrink:0`) — NOT `position:absolute/fixed` — so selecting a row no longer shifts the task list. Removed the redundant standalone Delete button from the top toolbar. |
| 2026-06-05 | Three-button delete dialog (`binna-gantt.html`) | Custom BINNA-styled modal replacing native `confirm()`. Any row with children shows **Delete Options**: *Delete All* / *Delete Group Only* (promotes children up one level) / *Cancel*; body reads "[Group] contains [N] tasks". |
| 2026-06-05 | Contract fixes (`binna-contract.html`) | (1) Manual work entry = **cumulative work to date** (net = entered − Σ previous cumulatives). (2) Editable Payment Summary row labels (`pstLbl`): gray placeholder = default UI-only, black = custom; print shows custom-or-default in black. |
| 2026-06-05 | Amount Received section | Per-payment installments (date/amount/note), per-installment + total % of net, Total Received vs Net Due, Fully Paid ✓ / Remaining. Server `/stats` recomputes `certified`(Σ `_netDue`) and `received`(Σ `received[].amount`) fresh from the raw blob; `templates/project.html` shows Total Certified / Total Received (%) on the Contract & Payment card. |
| 2026-06-05 | Contract Type toggle (Stage 1 of 3) | Government/Private toggle at top of Contract Details, stored as `data.contract_type`. Locks after real payment data exists (`hasPaymentData()`), page tag, conditional Payments tab. |
| 2026-06-06 | Private Contract payments (Stage 2 of 3) | Full user-defined private payment system in `data.payments` (each row `payment_mode:'private'`, settings in `data.privateSettings`). Templates: **Milestone / Monthly Invoice / Lump Sum / Custom**; advance-payment recovery, retention + release, optional per-payment tax, fully custom summary rows; reuses the gov Amount Received + Attachments. Dispatch via a guard at the top of `renderPayRows()` → `renderPrivatePayRows()`. |
| 2026-06-06 | Extra Deductions / Surplus / reversals in private | Replicated the government deduction machinery for private cards (incl. % of net / fixed, inline reversals, and cross-payment "Reverse Previous Deduction" via `buildPrivDeductionsRegistry`). |
| 2026-06-06 | Currency selector (gov + private) | Field in the Contract Details table: **IQD/USD/EUR/Custom** (`data.currency`, `data.currency_custom`). `curSym()` resolves the symbol; applied across **all payment-card amounts** in both renderers (gov converted via a scoped `renderPayRows` pass). |
| 2026-06-06 | Deductions/Surplus/Insurance/Penalty moved into the Payment Summary table | Both card types: editable deduction/surplus/reversal rows render **inside** the `.pst` table with a footer control row (`+ Add Deduction / + Add Surplus / Reverse Previous`). Gov-only: Insurance Release checkboxes + Daily Penalty became conditional in-table rows (penalty has an inline delay-days/waiver editor + `+ Daily Penalty` opener). All controls preserved (user chose "keep everything, just relocate"). |
| 2026-06-06 | % allocation caps (private Milestone/Lump Sum) | "Total Allocated: X% / 100%" bar; `addPrivatePay()` and `generateLumpPayments()` block exceeding 100%; both **+ Add Payment** buttons disable at 100%. |
| 2026-06-06 | BOQ work-items popup modal (gov only) | The long inline BOQ table is replaced by a collapsed summary line ("📋 BOQ Items — X items \| Total: Y") + **View / Edit Items**. Full table opens in a 90vw×85vh overlay (`#boq-items-modal`) with fixed header/footer, Escape-to-close, no outside-click close, **Done** (keep) / **✕** (discard w/ confirm if dirty). Table HTML is stashed in `_boqTableHTML[idx]` each render; modal body refreshes from it. |
| 2026-06-06 | Private payment template order + Decimal Places (`binna-contract.html`) | (1) Template selector reordered to **Lump Sum / Monthly Invoice / Milestone / Other (Custom)** (display only; internal ids unchanged). (2) New **Decimal Places** row (0/1/2) in Contract Details next to Currency → `data.decimalPlaces` (default 0). `fmt()` now delegates to decimal-aware `fmtN()`, so all money (gov + private cards, BOQ/VO totals, income/expense, contract-page dashboard strip) honors it; `fmtQty()` switched to its own integer formatter so quantities stay clean. Selector locks once `hasPaymentData()`. The cross-page `project.html` dashboard cards are server-fed and still format independently (not yet wired). |
| 2026-06-06 | Gantt Stoppages (فترات التوقف) | New `GanttData.stoppages` column + GET/PUT wiring (resilient to a not-yet-recreated DB). Toolbar **⛔ Stoppages** opens `#stoppages-modal` (name/start/end/type CRUD). Engine: **non-destructive** derived effective dates (`computeEffMap`/`effMap`) — stored task dates stay planned; a render-time pass skips non-working stoppage days. Visuals: hatched pause segments inside spanning bars (`barHatch`) + red-tinted stoppage columns on header & chart (`unitStop`). Empty stoppages = zero behavior change. Left table shows planned dates; chart bars show stoppage-adjusted span. |
| 2026-06-06 | Gantt predecessor arrow routing fix | Rewrote only the path geometry in `renderDeps()` to orthogonal elbow connectors that exit the predecessor's right tip and arrive at the successor's left tip, routing through inter-row space. Normal case: stub → single vertical in the gap → horizontal approach. Tight/overlap case: drop a half-row into the inter-row gap → route left clear of bars → rise to tip. Kept in-content `#dep-svg` (scrolls with bars, zoom-accurate via `barPos`); did **not** adopt the spec's `getBoundingClientRect`/fixed-overlay/`data-task-id` approach (unnecessary here). |
| 2026-06-06 | Schema auto-heal (`run.py` `_ensure_schema()`) | **Incident fix.** Adding `GanttData.stoppages` to the model without the column existing on live Postgres made every `SELECT` on GanttData fail → all Gantt charts appeared empty (data was never deleted, only unreadable). Added an idempotent post-`create_all()` auto-migration that `ALTER TABLE … ADD COLUMN`s any missing columns in place (verified: existing rows preserved). Establishes the project's standard for column additions — **never drop/recreate the DB.** |
| 2026-06-13 | Global Parties Registry — Phase 1 (+ post-merge fixes) | `GlobalParty` model + `/global-parties` CRUD (commit `18359c9`), plus same-session fixes: legacy-column migration (see Session Log), `/global-parties/seed` backfill endpoint, and a `MY_ROLE` frontend bug that hid all role-gated buttons. |
| 2026-06-12 | Subcontractor Module — Phase 1 (Core) | **Two NEW tables** `Party` + `Subcontract` (`app/models.py`) created by `db.create_all()` on deploy — no `_ensure_schema()` entry needed (that list is for new *columns*). New blueprint `app/routes/subcontracts.py` nested under `/api/v1/projects/<id>` (registered in `app/__init__.py`): Parties CRUD with **lazy seeding** of 3 defaults (main_contractor/consultant/client) on first GET — gives live projects their defaults with no migration; party delete **409** when referenced. Subcontracts CRUD (auto-ref `{CODE}-SUB-NNN`, blank §3 blob seeded by kind; `kind` **immutable** once the blob holds a non-zero amount — server check mirrors `hasPaymentData`). `GET /subcontracts/summary` json.loads()-and-computes-in-Python (per-contract committed/certified/paid/retained/balance + per-currency + flat totals, try/except per contract). `/stats` extended with `subcontracts = {count, payable}`; `project.html` Subcontractor card wired (object-valued stat handled separately from the scalar loop). New root page **`binna-subcontract.html`** served at `/legacy/sub` (via `_LEGACY_FILE_OVERRIDE` in `pages.py`, so existing sidebar links keep working). **Money direction = PAYABLE** throughout ("Net Payable / Balance Payable"). Payable payment renderer **copy-adapted** (not shared) from the contract private renderer: advance recovery, retention + 50/50 release, in-table deductions/reversals/surplus, optional tax, % allocation caps (lump_sum/milestone). Per-payment **Their Request** row, **Certificate bar** (draft→certified→signed→paid; Certify/Print/Sign-Online/Upload-Signed/Mark-Paid enable in order), canvas **signature modal** (dataURL in blob), **open_supply** running account (Invoices In / Payments Out + balance), and a print certificate with amount-in-words + two signature blocks. Uploads use the existing JWT uploads flow (stored filename in the blob/documents). Verified by a 20-assertion test-client smoke test (lazy seed, ref numbering, summary math, kind 409, party 409, stats, malformed-blob resilience). `git diff` confirmed **no changes** to `binna-contract.html`, gantt, or DC. |

---

## Session Log — 2026-06-05 → 2026-06-06

> All work from the 06-05→06-06 session is in two root frontend files (`binna-gantt.html`, `binna-contract.html`) plus the earlier `app/routes/projects.py` `/stats` recompute and `templates/project.html` cashflow display. **Committed and pushed** (commit `3a3b803`, live on binnapm.com).

### Bugs fixed
- **Gantt collapse/expand** swallowing sibling groups → forward-descendant `visible()` using effective level (`level + textIndent`).
- **Gantt indent/outdent** only changing `textIndent` (never `level`) — the real root cause of the persistent collapse bug; replaced with `_shiftSubtree` that moves whole subtrees on `level` and saves immediately.
- **Gantt "Pass 2" / demo data** removed; server-side task date-shifting stopped; circular-dependency guard added to the engine.
- **Gantt selection ribbon** shifting the task list → reserved a permanent 40px in-flow height (no absolute/fixed positioning).
- **Redundant Gantt Delete button** removed from the top toolbar.

### Features added
- Three-button **Delete Options** dialog (Gantt).
- **Amount Received** section + dashboard cashflow reliability (server recomputes from raw blob).
- **Contract Type** toggle (Stage 1) and full **Private Contract** payment system (Stage 2).
- **Currency** selector (IQD/USD/EUR/Custom) across both renderers.
- **Deductions + Surplus inside the Payment Summary table** (both); **Insurance Release** + **Daily Penalty** in-table (gov).
- **% allocation caps** (private Milestone/Lump Sum).
- **BOQ work-items popup modal** (gov).

### Architectural decisions
- **One payments array, two renderers.** Government and private payments coexist in `data.payments`; private rows carry `payment_mode:'private'`. A guard at the top of `renderPayRows()` delegates to `renderPrivatePayRows()` when `contract_type==='private'`, so **every existing call site (load, recalc, onchange handlers, installments, attachments) routes correctly without changes.**
- **Dashboard cashflow is recomputed, never cached-read.** Each render writes `row._netDue` / `row._received` and `data.cashflowSummary`; the server `/stats` sums these from the raw blob (with `cashflowSummary` fallback) so the strip can never go stale.
- **Reuse over rewrite for deductions/reversals.** Private reuses the government deduction/reversal functions verbatim (they all call `renderPayRows()` → guard); only the cross-payment registry got a private variant (`buildPrivDeductionsRegistry`) that derives gross from the private net.
- **Currency is a display concern.** `data.currency`/`currency_custom` + `curSym()`; amounts append the symbol. Gov literals were converted by a scoped text pass over `renderPayRows` only (every ` IQD` there is a safe source literal — user data never appears as a source literal).
- **Lock = real data.** Contract type locks via `hasPaymentData()` (real entered values), not the always-present empty starter row.
- **BOQ table built-then-stashed.** Still built every render, but stored in `_boqTableHTML[idx]` and shown in a modal instead of inline.

### Known issues / open work
- **Private Contract is Stage 2 of 3.** Stage 3 (Gemini to spec) is future work.
- **Currency scope:** applied to payment cards only. BOQ, VO, Income/Expense and the project dashboard still hardcode `IQD` (intentional for now; extendable on request).
- **Gov surplus/cross-reversal math** keeps the pre-existing `max(0, deductions − credits)` netting (credits can only offset deductions), whereas private treats surplus/reversals as purely additive. Left as-is to avoid changing established gov certificate math.
- **Print:** the Payment Summary `.pst` table now contains editable inputs; footer control rows are hidden in print (`.pst-foot`), but deduction/penalty inputs still print as boxes rather than clean certificate text.
- **Subcontractor** backend model still not architected (carried over).
- **No migrations:** new blob keys (`contract_type`, `currency`, `privateSettings`, `decimalPlaces`, etc.) need no DB change (they live inside the `FinancialData.data` JSON). The project still has **no migrations folder** — column additions go through `_ensure_schema()` (see Stack).
- **`GanttData.stoppages` column:** added automatically by `_ensure_schema()` on deploy — **no manual action, and DO NOT drop/recreate the DB.** (PUT still has a tasks-only rollback as a belt-and-braces fallback.)
- **`project.html` dashboard currency/decimals:** cross-page cards are server-fed and still hardcode `IQD` / format independently — extendable on request.

## Session Log — 2026-06-06 (session 2)

> Files: `app/models.py`, `app/routes/gantt.py`, `static/js/binna-api.js`, `binna-contract.html`, `binna-gantt.html`, `run.py`. Committed + pushed (live deploy). Final commit `da5987c`.

- **Contract:** private template order (Lump Sum / Monthly Invoice / Milestone / Other) + **Decimal Places** setting (`data.decimalPlaces`, 0/1/2) via decimal-aware `fmt()`→`fmtN()`; locks after payment data.
- **Gantt Stoppages:** new `stoppages` column + API, modal CRUD, non-destructive derived effective dates, hatched bars + tinted timeline columns.
- **Gantt arrows:** orthogonal elbow routing in `renderDeps()` (right tip → left tip, inter-row only) — no bar-body crossings in normal/tight cases.

### ⚠️ Incident — "Gantt data gone" (resolved, no data lost)
- **Symptom:** after deploying the `stoppages` column, every Gantt chart loaded empty.
- **Cause:** `db.create_all()` doesn't add columns to existing tables, so live Postgres lacked `stoppages`; SQLAlchemy still put it in every `SELECT`, so reads 500'd. **Rows were never deleted — only unreadable.**
- **Wrong turn:** the original spec (and my first note) said "recreate the DB." That would have **permanently destroyed all data** — do not do this.
- **Fix:** `_ensure_schema()` in `run.py` adds missing columns in place on boot (commit `da5987c`); reload restored all tasks.
- **Standing rule:** non-destructive migrations only; never drop/recreate the DB. Saved as a permanent guardrail.

## Session Log — 2026-06-12 (Subcontractor Module, Phase 1)

> Files: `app/models.py`, `app/routes/subcontracts.py` (new), `app/__init__.py`, `app/routes/projects.py`, `app/pages.py`, `static/js/binna-api.js`, `templates/project.html`, `binna-subcontract.html` (new). Not yet committed/pushed at time of writing.

### What was built
- **Schema:** `Party` (company directory, one row per company per project; `documents` JSON, `is_default` for the 3 seeds) and `Subcontract` (agreement; `data` JSON payment blob, `documents`, `kind`, `status`). **New tables only → `db.create_all()`**; deliberately **no `_ensure_schema()` entry** (that list is for new columns on existing tables, per the 06-06 incident rule).
- **API** (`subcontracts.py`, nested `/api/v1/projects/<id>`): parties CRUD (+lazy seed, +409 on referenced delete), subcontracts CRUD (auto-ref, kind-lock, full-blob PUT like financial), `/subcontracts/summary` (Python rollup, resilient). Roles: read=viewer, create/edit=member, delete=admin.
- **Frontend** (`binna-subcontract.html`): dashboard (totals strip + table), parties directory (CRUD + per-party docs), contract page (header w/ currency/decimals lock-after-data, mini strip, payable payment cards, open_supply tables), certificate bar + canvas signature modal + print certificate with amount-in-words.

### Architectural decisions
- **PAYABLE, not receivable.** All labels are "Net Payable / Total Paid / Balance Payable". The contract page's receivable wording was never reused.
- **Copy-adapt, never share.** The payable payment renderer is a self-contained reimplementation of the contract private renderer's *behaviors* (advance recovery, retention/release, deductions/reversals/surplus, tax, % caps) — `binna-contract.html` was **not touched** (verified by `git diff`). ⚠️ **Duplication risk logged:** the two renderers now embody the same payment math in two places; a future change to one must be mirrored or they will drift.
- **Server summary mirrors persisted per-row fields.** Each payment card writes `_net` / `_retHeld` / `_retReleased` into the blob on every render (same pattern as the contract's `_netDue`); `/subcontracts/summary` and `/stats` sum those in Python (with a from-scratch fallback), so the dashboard can't go stale and there are no columns to SUM.
- **`/legacy/sub` repointed via `_LEGACY_FILE_OVERRIDE`** so existing sidebar links across all module pages keep working without editing the guarded files.
- **Mixed currencies are not converted** — totals show a flat sum plus per-currency breakdown.

### Out of scope (Phase 2, untouched by design)
- DC From/To combobox fed by parties · Gantt task `partyId` · Expense auto-link on Mark Paid (only `paid/paidDate` kept accurate) · any change to `binna-contract.html`/gantt/DC.

## Session Log — 2026-06-13 (Global Parties Registry — Phase 1 fixes)

> Context: commit `18359c9` ("Global Parties Registry + cross-module integration") landed the `GlobalParty` model, `/global-parties` API, Parties modal (`templates/project.html`), and cross-module wiring (Subcontractor party picker, DC From/To, Income/Expense dropdowns). This session fixed three issues found during live testing of that feature, plus a cleanup pass on `binna-subcontract.html`. **Not yet committed at end of session** — 6 files: `app/models.py`, `app/routes/global_parties.py`, `app/routes/projects.py`, `run.py`, `templates/project.html`, `binna-subcontract.html`.

### ⚠️ Incident — seeding silently failed on every new project (resolved, no data lost)
- **Symptom:** creating a project with Client/Consultant/Contractor filled in produced **zero** `GlobalParty` rows.
- **Cause:** the live `binna.db`'s `global_parties` table still had the pre-rename `type` column as `NOT NULL` (now `role`). The current model never sets `type`, so every insert raised `IntegrityError` and **rolled back the entire `create_project()` transaction** — project, member, and `FinancialData` included, not just the seed.
- **Fix:** `_ensure_schema()` (`run.py`) now folds `type`→`role`/`is_seeded` and `logo`→`logo_filename` into the new columns, then `ALTER TABLE … DROP COLUMN` (SQLite ≥3.35, bundled 3.50.4). Applied in place to live `binna.db` — same standing rule as the 06-06 stoppages incident: **non-destructive in-place migrations only, never drop/recreate the DB.**

### Backfill endpoint
- `POST /api/v1/projects/<id>/global-parties/seed` (member+, idempotent) — backfills Client/Consultant/Contractor `GlobalParty` rows for projects created before the registry existed, or whose Client/Consultant/Contractor were filled in later via Edit. Shares `SEED_GLOBAL_PARTY_ROLES` with `create_project()`.

### Bug — role-gated UI invisible to every user (Edit project, +Add Party, party edit/delete)
- **Symptom:** the "+ Add Party" button (Parties modal) and the "Edit" button (project header) never rendered — for **any** user, including the project owner.
- **Cause:** `GET /api/v1/projects/<id>` returns `{ project: { ...fields, my_role } }` — `my_role` is nested *inside* `project`. `loadProject()` in `templates/project.html` read `MY_ROLE = data.my_role` (a top-level path that doesn't exist) → always `undefined` → every `(ROLE_LEVEL[MY_ROLE] || 0) >= ROLE_LEVEL.x` check evaluated `false`.
- **Fix:** `MY_ROLE = data.project.my_role`. Also added `console.error(...)` in `loadGlobalParties()`'s catch block for future diagnosis.
- **Guardrail:** any per-request field merged onto `result` inside `get_project()` (e.g. `my_role`) lives under `data.project.*` in the frontend, never `data.*` directly.

### `binna-subcontract.html` cleanup
- Removed the redundant per-project "Parties Directory" tab/view — superseded by the Global Parties Registry's Parties modal on the project dashboard; "New Subcontract" now points the user there instead of a local party form.
- Fixed remaining `p.type` → `p.role` references left over from the Phase-1 `GlobalParty` rename.

### Status at end of session
- Live dev server (port 5000) running with all fixes applied; verified via E2E (register → create project with Client/Consultant/Contractor → 3 seeded `GlobalParty` rows → `my_role: 'owner'` confirmed at `data.project.my_role`).
- 6 files above remain **uncommitted** — review and commit next session. *(Committed at the start of the 06-13/14 session below, as `710461a`, together with that session's first feature.)*

## Session Log — 2026-06-13/14 (Subcontractors & Suppliers + Supply Agreements + cross-module auto-wiring)

> Five sequential tasks, each committed separately. Built directly on the Global Parties Registry. Commits: `710461a` (party picker + rename), `0bfde3e` (auto-wiring + laboratory + gantt assignee), `dcd354c` (payment-system dropdown), `51d8286` (Supply Agreements module), `18ca885` (dark mode — its own log below).

### Module rename — "Subcontractors & Suppliers"  (`710461a`)
- "Subcontractor Management" / "Subcontractor Mgmt" → **"Subcontractors & Suppliers"** everywhere it's a label: module page title + header tag, project card (`templates/project.html`), and the sidebar nav link across **all** served legacy `binna-*.html` pages.
- **`binna-sub.html` left untouched on purpose** — it's dead code, orphaned by `_LEGACY_FILE_OVERRIDE = {'sub': 'subcontract'}` in `app/pages.py` (so `/legacy/sub` serves `binna-subcontract.html`). `app/pages.py` has no module-title string to change.

### Subcontract party picker sourced from GlobalParty  (`710461a`)
- "New Subcontract" now picks from the **Global Parties Registry** filtered to `role ∈ {subcontractor, supplier}` (was the old `Party` model). Empty state opens a modal linking to `/project/<id>#parties`; `templates/project.html` boot honours that hash and auto-opens the Parties modal **after** `loadProject()` resolves (so `MY_ROLE` is set and the +Add Party button shows).
- Completed the Phase-1 `GlobalParty.type → role` rename: fixed stale `type=` refs in `app/routes/subcontracts.py` that were **crashing `GET`/`POST /parties`**. **Guardrail:** `GlobalParty` has `role`, never `type` (the column was dropped — see 06-13 incident).

### Cross-module auto-wiring  (`0bfde3e`, extended by `51d8286`)
- Removed the manual **"+ New Subcontract"** button — records are created automatically when a party is added in the Parties modal:
  - **subcontractor → `Subcontract`** (payment-certificate workflow), **supplier → `SupplyAgreement`** (PO) — in both the `POST` and `PUT` handlers of `app/routes/global_parties.py`. Idempotent.
- ⚠️ **Key deviation + guardrail (read before touching auto-wiring):** the prompt said "set `Subcontract.party_id = global_party.id`". `Subcontract.party_id` **FKs `parties.id`** (the subcontract-module `Party` directory), *not* `global_parties.id`, and the dashboard reads the party name through that relationship — so a literal global-party id would yield **nameless** contracts. Instead the auto-wiring **mirrors the GlobalParty into a `Party` row** and links the Subcontract to that (dedup by `name+role`). SupplyAgreement *does* carry `global_party_id` directly (dedup on it). **No schema change to the FK.**
- Auto-created subcontracts use `kind='subcontractor'`; the subcontract card template is driven by `data.payment_mode` (below), not by `kind`.

### Laboratory role + Lab Tests "Testing Lab" picker  (`0bfde3e`)
- Added `'laboratory'` to `CREATABLE_GLOBAL_PARTY_ROLES` (and `VALID_GLOBAL_PARTY_ROLES`, and the registry role dropdown in `templates/project.html`). **Never seeded.**
- `lab_tests.lab_party_id` (FK `global_parties`, nullable) — new column, added to `_ensure_schema()` as `('lab_tests','lab_party_id','INTEGER')`. The free-text "Lab Name" field is replaced by a **"Testing Lab" dropdown** sourced from `role=='laboratory'` GlobalParties; save stores `lab_party_id` **and** mirrors the name into the existing `lab` column (back-compat for display/search), and the table resolves the live name from `lab_party_id` first.
- DC From/To datalist confirmed **already** fed by `/global-parties` unfiltered — no change needed (laboratory now appears there automatically).

### Gantt "Assigned To"  (`0bfde3e`)
- Display-only field stored on the task blob as **`assignee:{type,id,name}`** (`type ∈ {member, party}`). Options: team members from `GET /projects/<id>` → `members[]` + subcontractor/supplier GlobalParties. Rendered as a small grey ellipsis-truncated label on the task bar. **No schema change** (lives in `GanttData.tasks` JSON, preserved through `sanitizeTask`).

### Subcontract "Payment System" dropdown  (`dcd354c`)
- Header dropdown mirroring `binna-contract.html`: **Cumulative / Lump Sum / Monthly Invoice / Milestone / Other**, stored as **`data.payment_mode`** (default `'cumulative'`, *derived from the server `kind` for pre-existing subs* so their template is preserved). Locks after real payment data (`hasRealData()`). The card template is now driven by `data.payment_mode` via `tmplKind()` instead of the server-side `kind`. **`binna-contract.html` not touched** (verified).

### Supply Agreements (Purchase Orders) module  (`51d8286`)
- New **`SupplyAgreement`** model (`supply_agreements` table) — PO header + flat payment log in `data` JSON (`{payments:[], notes}`). **No retention, no cumulative درعة, no certificates.** New table → `db.create_all()` handles it (no `_ensure_schema` entry). Uses `_now` (timezone-aware) for `created_at`, matching every other model (the prompt's `datetime.utcnow` was not adopted for consistency).
- Routes registered on the existing `subcontracts_bp`: `GET/POST /supply-agreements`, `GET/PUT/DELETE /supply-agreements/<id>`, `GET /supply-agreements/summary`. List/detail compute `total_paid` + `balance` and join `GlobalParty.name_en` as `party_name`.
- **Status is derived server-side** on every PUT (`open` / `partially_paid` / `closed` from `total_paid` vs `po_value`) — the client value is never trusted.
- Dashboard split into two tabs: **Subcontracts** (unchanged) + **Supply Agreements** (totals strip, table, status badges, no manual "New" button). Detail view: editable PO header that **locks once a real payment is logged**, inline payment log (`+ Log Payment` / edit / delete), live Total Paid / Balance footer.

### Verification
- Each task verified end-to-end against a **temp SQLite DB** via the Flask test client (auto-wiring routing, PO status transitions, summary math, `lab_party_id` round-trip, `payment_mode` persistence, `_ensure_schema` ALTER on a pre-existing table). Inline JS of every edited page re-checked with `node --check`. Backend `create_app` import-checked after each change.

## Landing Page
- Status: **LIVE** (`/` serves the marketing landing page with the split-screen auth modal)
- Color scheme: **"Obsidian Crown"** — deep near-black `#060608`/`#0b0b10`/`#0f0f16` backgrounds, **gold** `#C5A85A` as the primary brand accent (the **BINNA wordmark in nav AND footer is gold Syne 900**, plus eyebrow labels, `.st em`, accent lines, nav Sign-In, grid lines, active tab indicator, auth wordmark) and **purple** `#8B5CF6`/`#A78BFA` for buttons, icons, feature tags & `.cv.hi`. Applied via remapped `:root` legacy aliases + an "Obsidian Crown" override block at the end of the inline `<style>`. Page is locked dark regardless of the theme toggle (`[data-theme] body{background:#060608!important}`).
- Hero visual: **blueprint canvas animation** (`#wall-canvas`) — animated gold survey grid + center crosshair + corner ticks + dashed "PROJECT SCOPE" dimension line + purple survey nodes, settling into a slow pulsing static draw. **Replaced** the old isometric brick-wall animation. Hero is a **normal scrollable section** (the ScrollTrigger pin was removed); hero text shows immediately. The **scrolling module ticker was removed entirely** (HTML had no static element — it was JS-built into a missing `#tk`, which was actually throwing). Footer gained a gold `info@binnapm.com` link + an Arabic tagline.
- File: `C:/BINNA/index.html` (repo root — the canonical copy; `templates/index.html` is a **stale** older copy, not served)
- Served via `send_from_directory(_ROOT, 'index.html')` in `app/pages.py` `index()` — **not** `render_template`, because Flask's `template_folder` is `templates/` which holds the outdated copy. (Same pattern as the legacy `binna-*.html` pages.)
- Auth: in-page split-screen overlay modal (no redirect to `/login`). Three trigger points (nav, hero, CTA) open it; it talks to `/api/v1/auth/login` + `/register` and stores `binna_token`/`binna_user` in `localStorage`, then redirects to `/dashboard`.


## Session Log — 2026-06-14 (Dark Mode — CSS variable architecture)

> Goal: site-wide dark mode via CSS custom properties. The prompt assumed a single `static/css/main.css` + `templates/base.html`; **neither exists** — BINNA is ~22 standalone HTML pages, each with its own inline `<style>` and its own per-file `:root` palette (`--bg/--white/--surface/--text/--accent/...`), no shared shell. Implemented the shared-stylesheet approach instead.

### What landed
- **`static/css/theme.css`** — single source of truth: canonical `:root` light palette + `[data-theme="dark"]` overrides (backgrounds, text, borders, shadows, gantt). Brand colors (`--brand-*`) are mode-invariant. Plus `.binna-theme-toggle` styling and a **`@media print` block that forces the light "paper" palette** so certificates/reports never print dark regardless of theme.
- **`static/js/theme.js`** — pre-paint IIFE (reads `localStorage['binna-theme']`, else `prefers-color-scheme`) sets `data-theme` before CSS → no flash; `binnaThemeInit()` wires the toggle + live OS-change sync.
- **All 22 pages wired** (6 `templates/` + 16 root `binna-*`/`index`): `theme.js` then `theme.css` injected before inline CSS, `data-theme=""` on `<html>`, toggle button in `.topbar-right` (or fixed top-right on auth/landing/404 pages with no navbar).

### Aliasing strategy (Step 4)
- Each page's local `:root` color vars were **re-pointed to canonical vars by NAME** (e.g. `--bg:var(--bg-base)`, `--white:var(--bg-surface)`, `--surface:var(--bg-surface-2)`, `--text:var(--text-primary)`, `--accent:var(--brand-primary)`, `--success/danger/warning:var(--brand-*)`). Existing rules referencing the local names keep working and now flip automatically.
- **Self-contained pastel status pills** (`--*-bg`, `--*-br`, `--pending/approved/rejected/in/out/...`) were **left as literal hex** — they read fine on both light and dark and have no canonical equivalent.
- Hardcoded **light backgrounds** in CSS/inline styles → surface vars; **Gantt** got a dedicated pass (`--ms/g/sg-bg`, weekend/today cells, row tints → `--gantt-*`/`--bg-hover`). Fixed three forced-dark-text spots that would vanish in dark (`.cert-doc` kept as white paper, contract `.pst-lbl`, gantt `.csw.sel`).

### Notable consequences / deferred
- **Light-mode hue shift (intentional, centralized):** accent unified blue `#1a56db` → canonical indigo `#4f46e5`; success/danger/warning shifted to the brighter `--brand-*` set. All reversible from one place — edit `theme.css`.
- **Marketing landing pages** (`index.html`, `templates/index.html`, OFFLINE) are theme-wired with a toggle but keep their bespoke navy/`--off` hero palette — **not** fully darkened by design.
- Backend/routes/schema untouched (verified). Each page's inline JS syntax re-checked with `node --check`; `theme.css`/`theme.js` confirmed served 200 and present on rendered pages.

## Session Log — 2026-06-15 (Landing page LIVE + split-screen auth modal)

> Files: `index.html` (root), `app/pages.py`. **No** backend routes, models, or `binna-*.html` pages touched (by design).

### Landing page activated
- `app/pages.py` `index()`: `redirect('/login')` → **`send_from_directory(_ROOT, 'index.html')`**. ⚠️ Deliberately **not** `render_template('index.html')`: Flask's `template_folder` is `templates/`, which holds a **stale 1367-line copy**; the canonical landing page (1705 lines, with the modal) lives at the **repo root** and is served directly like the legacy `binna-*.html` pages. `redirect` import left in place (still harmless; `render_template` still used by other routes).

### Split-screen auth overlay modal (`index.html`)
- Self-contained overlay (`#auth-overlay`, z-index 10000 — above admin panel/theme toggle). **LEFT** = navy branding panel (`--blue`→`--blue2` gradient + a running-bond **brick pattern drawn on `<canvas id="auth-brick">`**), BINNA headline + 3 bullets. **RIGHT** = white panel with a **Sign In / Create Account** tab switcher.
- Forms: Sign In (email + password); Create Account (**Name + Email + Password only**). **Eye toggle** (show/hide) on both; **password-strength bar** on register (5-step Weak→Strong). Inline **red error box** + green **success message** (register shows "taking you to your dashboard…" before redirect). **ESC** + **click-outside** close; body scroll locked while open.
- Wiring: `POST /api/v1/auth/login {email,password}` and `POST /api/v1/auth/register {username,email,password}` — `username` is the "Name" field (server requires ≥3 chars, password ≥6). On success stores `binna_token` (+ `binna_refresh`, `binna_user`) in `localStorage` and redirects to `/dashboard`. All modal CSS/JS namespaced `auth-*` / `authX()` — no collision with the existing lang/admin globals.
- **Triggers (3):** nav "Sign In" (login tab), hero "Sign In to BINNA" (login) + "Get Started" (register, replaced the old "Explore ↓" — `ht-btn2` EN/AR translation defaults updated to match), CTA "Sign In" (login) + "Get Started" (register, added a second CTA button).

### Verification
- App boots; `GET /` → **200** with modal markup/JS present. Test-client **register → 201** and **login → 200** using the exact JSON keys the modal sends, both returning `access_token`. Reduced-motion + mobile (left panel hidden ≤720px) handled in CSS.

## Session Log — 2026-06-15 (Landing page redesign — "Obsidian Crown")

> Files: `index.html` only — **CSS + inline-style changes only**. No JS logic, HTML structure, Flask routes, or auth functionality changed.

### What changed
- Full visual recolor to the **Obsidian Crown** system (deep `#060608`, purple `#8B5CF6`/`#A78BFA`, gold `#C5A85A`). Implementation: (1) the page's local `:root` adds the new tokens and **remaps the legacy aliases** (`--blue/--white/--off/--accent/--accent2/--text/--muted/--ll`) onto the dark palette as a catch-all; (2) a single **"Obsidian Crown" override block** appended to the end of the main inline `<style>` sets explicit per-element values for nav, hero, ticker, sections, feature cards, Iraq bullets, cert card, CTA, footer, theme toggle, and the whole auth modal.
- Hero gained a **gold CSS grid** (`background-image` 44px) + a **radial purple glow** via `#hero::before`. Auth left panel gained a **gold grid** (40px) + a **2px gold left accent line** via `.auth-left::before`; the JS brick canvas is hidden with `.auth-brick{display:none}` (CSS-only — JS untouched, draws harmlessly to a hidden canvas). Auth tabs switched from purple pill to **gold underline** active indicator.
- Removed every literal light background from the source (`#fff`/`#F7F9FF`/`#EFF6FF`/`#F1F5F9` in `.nc/.bw/#ticker/.sec/.fc/.fb/.cc/.cr`) — replaced with dark/purple/gold equivalents. `@media print` left untouched. (The one remaining `#E2E8F0` is the admin-editor input **text** color, not a background — admin panel kept per spec; only `#admin-btn` background → `#8B5CF6`.)
- Page locked dark regardless of theme toggle: `[data-theme="dark"|"light"] body{background:#060608!important}`.

### ⚠️ Pre-existing bug fixed (one char)
- The Arabic `TRANSLATIONS` object had a **double comma** (`'بِنّا',,'fc1-desc'`) — a real **JS syntax error present in committed HEAD**, which silently broke the entire lang/ticker/admin `<script>` block (page fell back to static English HTML; ticker never rendered). Removed the stray comma so the block parses. This restores intended behavior; it does not change logic. Found via `node --check` on the extracted inline scripts.

### Verification
- `GET /` → **200**. All three inline `<script>` blocks pass `node --check` (after the comma fix). Grep confirms **zero** light backgrounds in the served HTML (outside `@media print`). New tokens (`#060608`, `#8B5CF6`, `#C5A85A`, hero glow, gold grids) confirmed present.

## Session Log — 2026-06-15 (Landing redesign v2 — blueprint hero, gold-forward, ticker removed)

> Files: `index.html` only — **CSS, inline styles, and the hero canvas animation**. No other JS logic, Flask routes, auth functionality, or other HTML files touched.

### Hero animation swapped: brick wall → blueprint
- **Removed** the entire isometric brick-wall canvas block (`project/initStates/drawBrick/render` + the `ScrollTrigger.create` **hero pin**) and replaced it with a self-contained **blueprint draw-on animation** on the same `#wall-canvas`: a gold survey grid sweeps in, then center crosshair → corner registration ticks → dashed "PROJECT SCOPE" dimension line → 6 purple survey nodes, finishing in a slow `Math.sin` pulse via `drawStatic()`. Guards with `if(!canvas) return`.
- Hero is now a **normal scrollable section** (no pin). Hero text (`#ht-eye/#ht-title/#ht-sub/#ht-ar/#ht-btns`) is revealed **immediately** via CSS `opacity:1!important;transform:none!important` (previously driven by the pin's `onUpdate`). The last-turn CSS hero grid + `#hero::before` purple glow were removed (`#hero::before{content:none}`) since the canvas now provides both.

### Ticker removed
- Deleted the base ticker CSS (`#ticker/.tk-t/.tk-i/.tk-d` + `@keyframes tk`), the override-block ticker rules, and the **orphaned JS builder** (`const tk=getElementById('tk'); …tk.appendChild`). There was never a static ticker element — the builder targeted a missing `#tk` and was **throwing a TypeError on every load**; removing it also clears that console error. (`gsap.registerPlugin` and the 6 remaining `ScrollTrigger.create` calls — shelf, `.rv`/`.fc`/`.ipt` reveals, cert counters — were preserved.)

### Color shift to gold-forward + content
- **BINNA wordmark is now GOLD** `#C5A85A` in nav (`.nb-m`) **and** footer (`.fb-brand`, Syne 900) and the auth left panel (`.auth-brand-mark`). `.st em` and the CTA `em` switched purple→gold. Nav bg → `rgba(6,6,8,0.97)`; `.nl` 0.42; `.nb-s` 0.6; `.bo` border 0.35; `.st` font-size → `clamp(42px,5vw,68px)`; `.v-ar` 0.4.
- Feature cards: `.fc:hover` bg `#0f0f16`; `.fc-img` → `#0d0818` + a 28px gold grid overlay.
- Auth left headline reworded with em spans: **"Iraqi"** gold + **"construction project"** purple (`.hl-g`/`.hl-p`).
- Footer HTML gained a gold `info@binnapm.com` mailto link + Arabic tagline `بِنّا · Construction Project Management · Iraq`.

### Verification
- `GET /` → **200**. All 3 inline `<script>` blocks pass `node --check`. Grep confirms: brick-wall refs **0**, ticker (`#tk`/`@keyframes tk`/`.tk-*`) **0**, `pin:true` **0**, light backgrounds **0** (outside `@media print`); blueprint (`PROJECT SCOPE`), footer email, `.hl-g` spans, `#0d0818`, and gold `.nb-m` all present.

## Session Log — 2026-06-15 (base.html + Obsidian Crown site-wide + landing canvases)

> Three parts. Files: `templates/base.html` (new), `templates/{dashboard,project,login,register}.html` (refactored), `static/css/theme.css`, `index.html`. No backend/routes/models touched.

### Part 1 — base.html + template inheritance
- Created **`templates/base.html`** (see Frontend reality sheet for block layout). Refactored the 4 SPA pages to extend it; `index.html`/`404.html` left standalone per instructions.
- **Key decision — two different navs:** dashboard and project had divergent topbars (project carries a back-button + `#top-code`/`#top-name` that its JS writes). A single shared nav would null-crash project's `renderHeader`. So base provides the dashboard-style nav as the default `{% block topbar %}`; **project overrides the whole block** with its own bar (all JS hooks preserved); login/register suppress it via `{% set hide_nav = true %}` (top-level child `set` propagates to the parent `{% if %}`). Pages keep their **Inter** font via `extra_css` (base loads Syne+DM Sans).
- ⚠️ Gotcha hit + fixed: a literal `{% block topbar %}` string sitting **inside a CSS comment** in base.html was parsed by Jinja as a real (unclosed) tag → 500 on every page. Don't put `{%`/`{{` inside template comments/CSS. Reworded the comment.

### Part 2 — Obsidian Crown site-wide via theme.css
- Rather than hand-edit 15 `binna-*.html` files (~17.5k lines, JS-risky), drove the recolor through **theme.css**: remapped the canonical tokens (`--bg-base→#060608`, `--bg-surface→#0b0b10`, `--bg-surface-2→#0f0f16`, `--brand-primary→#8B5CF6`, text/border tokens, gantt tokens) to Obsidian values in **both** `:root` and `[data-theme="dark"]`, added the named Obsidian tokens, and a `body` dark-lock. Because every page already aliases its local `:root` to these canonicals (2026-06-14 dark-mode architecture), all module + SPA pages flip at once. Verified `/legacy/{dc,gantt,contract,financial}` → 200 and still link theme.css. base.html nav styled with the new tokens (gold wordmark, gold-dim user pill/logout).
- **Print guard:** the new `body` `!important` lock would have forced dark printing, so `@media print` now also resets `--bg-deep`/`--bg-elevated`/`--text-bright` and forces `body{background:#fff!important}`.

### Part 3 — index.html landing canvases
- **Vision section:** removed the 3D isometric shelf canvas markup, replaced with `<canvas id="vision-canvas">` (transparent 500px wrapper) + a self-contained **floating project-hierarchy animation** (root→phase→task nodes, animated dependency links + travelling gold flow dots, per-task progress bars, summary chips, corner ticks). The old shelf JS IIFE is left in place but no-ops via its `if(!sc) return;` guard.
- **Hero blueprint:** the idle pulse loop now spawns **12 drifting gold particles** (halo + core, sine-pulsed alpha, edge-wrap), and `drawStatic` takes a time arg so the **grid alpha pulses** (`0.045+sin(t/900)*0.018`) and the **purple glow radius breathes** (`maxR*(0.82+sin(t/1100)*0.18)`).

### Verification
- `GET /`, `/dashboard`, `/project/1`, `/login`, `/register` all → **200** (no Jinja/500). Nav inheritance confirmed at markup level: login/register have no base nav button, dashboard renders it, project renders its own back-button bar (no base default). All 4 SPA pages load Syne+DM Sans from base. All 4 inline `<script>` blocks in index.html pass `node --check`. `/legacy/*` module pages 200 + theme.css-linked (Obsidian via aliases).

## Session Log — 2026-06-16 (Phase 0 — Clean slate for the multi-tenant SaaS rebuild)

> First step of the BINNA → multi-tenant SaaS plan (`BINNA_SAAS_PLAN.md` Phase 0). Goal: clear the dummy/test data so Phase 1 builds the multi-tenant structure (`companies`, `company_id`, roles) on an empty database — **without** forming the habit of dropping/recreating the DB. No real customer data exists yet. Phase 1 NOT started; awaiting go-ahead.

### Local `binna.db` — cleared (schema-preserving)
- **Before:** 14 tables holding dummy data — `users` 12, `project_members` 8, `projects` 7, `financial_data` 7, `global_parties` 7, `parties` 12, `subcontracts` 3, `daily_reports`/`dc_letters`/`gantt_data` 1 each; `archives`/`lab_tests`/`submittals`/`supply_agreements` 0.
- **Method:** `DELETE FROM` every table (FKs off for the sweep) + `DELETE FROM sqlite_sequence` to reset AUTOINCREMENT so fresh IDs start at 1, then `VACUUM`. **No table or column was dropped** — the schema built by `db.create_all()` + `_ensure_schema()` is fully intact. This deliberately practices the production-safe discipline even on disposable data.
- **After:** 14 tables, **0 rows total**.
- **Boot verified:** importing `run.py` (runs the exact prod startup path `create_app` → `db.create_all()` → `_ensure_schema()`) succeeds; test client `GET /` → 200, `GET /login` → 200, `POST /api/v1/auth/register` → 201 on the empty DB (smoke-test user then deleted, re-confirmed 0 rows). `_ensure_schema()`-managed columns all present post-clear: `gantt_data.stoppages`, `global_parties.role` + `is_seeded` (legacy `type` correctly absent), `lab_tests.lab_party_id`.

### Render production — evolved during the session (Postgres provisioned)
- **Start of session:** no Render PostgreSQL existed — the account had only the BINNA web service, and `config.py:12` fell back to ephemeral container SQLite (wiped on every deploy/restart, never durable). So there was **no persistent production data to clear**; the only real database to clean was local `binna.db` (done above).
- **During the session:** a free Render PostgreSQL instance **`binna-db` was provisioned** and starts **empty** (a fresh Postgres needs no clearing). The web service's `DATABASE_URL` was **not** wired to it before work paused (see credential incident below), and the service is **suspended**.
- `clear_render_db.py` (single `psycopg` connection, terminates other backends, `SET statement_timeout`, one `TRUNCATE … RESTART IDENTITY CASCADE`; reads `DATABASE_URL` from `os.environ`, never prints it) is **retained as the guardrailed re-clear utility** for when the DB is wired and ever needs resetting during testing. (First version self-deadlocked by holding a Flask app-context SELECT open against a second TRUNCATE connection — rewritten to one connection.)

### ⚠️ Credential incident — password rotation attempted, then DEFERRED by decision
- Render's "create a new default credential" (`binna_users`) did **not** create a separate, independently-rotatable Postgres login on this plan — it authenticates as the **same underlying role `binna_db_user`** (verified: connecting with the new password reports `current_user = binna_db_user`). PostgreSQL roles have exactly one password; the only thing that invalidates a leaked password is **changing that role's password** (`ALTER ROLE binna_db_user WITH PASSWORD …`), not adding a credential.
- **Verified the old setup password still authenticates (`AUTH OK`).** A full reset path was built and tested-ready (`reset_password.py` via `ALTER ROLE`, `rotate_db_url.py`, `check_credential.py` — all read secrets from env, never print them, verify against the **external** host since the **internal** host only resolves inside Render).
- **DECISION (Mohammed, 2026-06-16): SKIP rotation for now** — DB empty, app suspended, no customers, accepted low risk. Not rotated.

### ✅ RESOLVED (2026-06-18) — exposed DB password rotated; leaked credential dead
- **Original issue:** the `binna_db_user` PostgreSQL password was **exposed in plaintext during setup** (and also appeared in chat transcripts) and still authenticated (`AUTH OK` via `check_credential.py` on 2026-06-16).
- **Resolution (2026-06-18):** the database credential was **rotated via Render's credential-rotation feature**. The DB now uses a **new default credential, `users_database`**. **Both prior logins — `binna_users` and `binna_db_user` — have been deleted/revoked in Render**, so the exposed setup password no longer maps to any live role.
- **Resolved — AUTH FAILED independently verified (2026-06-18):** the old exposed password now returns **`AUTH FAILED`** against `binna_db_user` via `check_credential.py` (a real database-level auth attempt, not a dashboard label). This is the decisive proof the June 16 attempt lacked — unlike then (when the old password still returned `AUTH OK`), the leaked secret is now confirmed **dead**.
- **Web service:** `DATABASE_URL` updated to the new `users_database` credential (see Pre-launch item #1).
- **Note:** the rotation itself was performed by Mohammed directly in Render (not via `reset_password.py`); `check_credential.py` was then used to confirm the kill, run in Mohammed's own terminal so the live secret never entered the AI session. The tooling remains available for any future role-level rotation.

### Standing rule reaffirmed
- Column additions go through the `additions` list in `_ensure_schema()` (`run.py`) via `ALTER TABLE … ADD COLUMN`. **Never drop/recreate the DB** (see the 2026-06-06 stoppages and 2026-06-13 `global_parties` incidents). Phase 1's new `companies` table arrives via `db.create_all()`; new columns on existing tables (`users.company_id`, `users.role`, every data table's `company_id`) arrive via `_ensure_schema()`.

### ⚠️ Pre-launch items carried to the Launch Track (not Phase 0 tasks)
1. **Wire `DATABASE_URL`** on the BINNA web service to `binna-db`'s **Internal Database URL** when the service is resumed (otherwise it falls back to ephemeral SQLite). `config.py` auto-rewrites the scheme to `postgresql+psycopg://`.
2. ✅ **DONE (2026-06-18) — exposed `binna_db_user` password rotated.** Credential rotated via Render's rotation feature to new default `users_database`; old roles `binna_users` + `binna_db_user` deleted/revoked. See the ✅ RESOLVED note above.
3. **Upgrade the free Postgres** (`binna-db` free tier expires ~30 days from 2026-06-16) to a paid instance before launch, or the DB + data are deleted.

### Status — Phase 0 COMPLETE ✅
- **Local `binna.db`:** cleared, schema intact, app boots — verified.
- **Render production:** no durable data existed to clear; `binna-db` Postgres provisioned and empty. Password rotation was deferred at the time, then **completed 2026-06-18** — credential rotated to new default `users_database`, old `binna_users`/`binna_db_user` revoked (see ✅ RESOLVED note above).
- **Phase 1 NOT started.** Ready to begin Phase 1 (multi-tenant DB structure) on Mohammed's go-ahead.

## Session Log — 2026-06-16 (Phase 1 — Multi-tenant database structure)

> `BINNA_SAAS_PLAN.md` Phase 1. Schema only — **no API scoping, no auth-flow changes** (those are Phase 2, deliberately untouched). Files: `app/models.py`, `run.py`. Phase 2 NOT started.

### What changed
- **New `Company` model** (`companies` table) — tenant root: `id, name, slug (unique, indexed), plan ('trial'), max_users (999), trial_ends_at, grace_ends_at, status ('trial'; ∈ trial/active/grace/locked), created_at`. New table → built by `db.create_all()` (no `_ensure_schema` entry).
- **`company_id` added to all 14 tenant tables** (`users` + 13 data tables) — FK `companies.id`, **nullable + indexed**. Nullable because Phase 2 wires signup→company; no backfill (DB emptied in Phase 0).
- **`users` gained:** `company_role` (tenant role `owner/admin/member/viewer`, default `viewer`), `email_verified` (bool, default false), `email_verification_token`. The verification *columns* exist now; the *logic* is Phase 2.
- **All new columns registered in `_ensure_schema()`** (`run.py` `additions` list) via `ALTER TABLE … ADD COLUMN`. **Nothing dropped/recreated.** Boolean DDL uses `DEFAULT FALSE` (not `DEFAULT 0`) so it is valid on PostgreSQL as well as SQLite.

### ⚠️ Key deviation (read before touching user roles)
- The plan said "add a `role` column to `users` (owner/admin/member/viewer)". **`users.role` already existed** as the PLATFORM role (`admin`|`user`; first-ever signup → `admin`, the BINNA super-admin — `app/auth.py:52`). Overwriting it would conflate "is this the platform super-admin?" with "what's this user's role inside their company?". So the tenant role was added as a **separate `company_role`** column; `users.role` is **untouched**. Guardrail: **platform role = `users.role`; tenant role = `users.company_role`** — never merge them.
- `ProjectMember.role` (project-scoped owner/admin/member/viewer) is unchanged and still independent of both — it governs per-project membership, not company membership.

### Verification
- **Local SQLite (`binna.db`, predates Phase 1 → exercises the `_ensure_schema` ALTER path):** app boots (`create_all` + `_ensure_schema` clean); 15 tables incl. `companies` with all 9 columns; `company_id` present on all 14 tenant tables; `users` has `company_role`/`email_verified`/`email_verification_token` and still has platform `role`. ORM round-trip (Company → owner User → Project, all `company_id`-linked, `company_role='owner'`, defaults `trial/trial/999`, `email_verified=False`) succeeded, then **rolled back → 0 rows** (DB stays empty for Phase 2). `GET /`, `/login` → 200. `py_compile` clean on `models.py`/`run.py`.
- **PostgreSQL (`binna-db`):** ✅ **CONFIRMED** — Mohammed ran `verify_phase1.py` against binna-db's EXTERNAL url: `RESULT: PASS — Phase 1 schema present on postgresql`. App boots against production Postgres; `companies` table + `company_id` on all 14 data tables + `users.company_role`/`email_verified`/`email_verification_token` present; `users.role` preserved. (Running it also materialized the empty Phase-1 schema on binna-db — the production schema, no rows.) `_ensure_schema` DDL written Postgres-safe; `verify_phase1.py` writes no data.

### Status
- Phase 1 schema **COMPLETE and verified on BOTH SQLite and production PostgreSQL** (`binna-db`). **Phase 2 NOT started** — awaiting Mohammed's go-ahead.

## Session Log — 2026-06-18 (Per-member module permissions — storage + backfill)

> Foundation for an admin-controlled, per-member permission system. **Storage + one-time backfill only — no route files touched.** A future phase wires the route checks.

### What changed
- **New `ProjectMember.permissions` column** (`app/models.py`) — `TEXT`, JSON map `{module: {'view': bool, 'edit': bool}}` over the 10 modules (`financial, gantt, uploads, dc, dr, lbt, projects, submittals, global_parties, subcontracts`). Default `'{}'` = "not yet provisioned". **Both flags false for a module = no access at all** (member can't even open it read-only) — supported by the schema for future admin use, but no existing member is migrated into that state.
- **Single source of truth** (`app/models.py`): `_MODULE_EDIT_MIN_ROLE` (module → minimum project role that grants EDIT today) + `default_permissions_for_role(role)`. VIEW is granted for every module (nothing hides itself today); EDIT only where the role meets the module's current threshold. Derived from actual route logic: `dc/dr/lbt/submittals/global_parties/subcontracts` create/update gate on `member`; `financial/gantt/uploads` have **no** route gate today but are pinned to `member` so current viewers are **not** granted edit (role intent, not the open loophole); `projects` writes gate on `admin`.
- **Column registered in `_ensure_schema()`** (`run.py` `additions` list) per the standing rule — `ALTER TABLE project_members ADD COLUMN permissions TEXT DEFAULT '{}'`. Boot-safe on existing DBs; nothing dropped.
- **One-time migration `migrate_member_permissions.py`** (new, top-level alongside `check_db.py` etc.) — dry-run by default (reads only, writes/alters nothing), `--apply` adds the column + backfills. Idempotent: only rows where `permissions` is NULL/`''`/`'{}'`. Raw SQL so it runs even on a pre-migration DB. After `--apply` it asserts the invariant that **no member ended up hidden** (both flags false) from any module.

### Backfill policy (what each role gets)
- **viewer** → `view=true` everywhere, `edit=false` everywhere (read-only, incl. financial/gantt/uploads — no carry-over of the route loophole).
- **member** → `edit=true` on all modules **except `projects`** (project admin stays `edit=false`).
- **admin / owner** → `edit=true` on all 10 modules.
- Invariant: every member keeps `view=true` on every module → **nobody is migrated to a hidden state.**

### Verification
- Dry run on local dev DB: **0 `project_members` rows** (real members live in the Render production DB), so a local `--apply` is a no-op. Policy + exact per-role JSON generated straight from `default_permissions_for_role()` and sanity-checked (viewer all-view/no-edit; member edit-all-but-projects; admin edit-all). `py_compile` clean.
- **NOT yet applied to any DB.** Production backfill: run `migrate_member_permissions.py --apply` against `binna-db` (with `DATABASE_URL`/`FLASK_ENV=production`) once reviewed.

### Status
- Permission **storage + backfill tooling COMPLETE**; route enforcement **NOT started** (deliberately — next phase). Migration not yet run against production.
