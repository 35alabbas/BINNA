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
  - `FinancialData.data` (Text) → JSON: `{contractDetails:{}, boq:[], vo:[], payments:[], income:[], expenses:[], incomeCategories:[], expenseCategories:[], usdRate:1300, contract_type:'government'|'private', currency:'IQD'|'USD'|'EUR'|'custom', currency_custom:'', privateSettings:{}, cashflowSummary:{totalCertified,totalReceived,payments}}`
    - `payments[]` items now carry (added 2026-06-06): government fields (`boqItems`, `extraDeductions`, `surplusCredits`, `deductionReversals`, `penaltyDays/penaltyWaived/_penaltyOpen`, `releaseInitial/releaseFinal`, `received[]`, `attachments[]`, `_netDue/_received`) **and** private fields (`payment_mode:'private'`, `summaryRows[]`, `milestoneName/milestonePct`, `invoiceNo/period`, `scheduleLabel/schedulePct`, `privTaxEnabled/privTaxRate`, `relRet1/relRet2`).
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

---

## Session Log — 2026-06-05 → 2026-06-06

> All work this session is in two root frontend files (`binna-gantt.html`, `binna-contract.html`) plus the earlier `app/routes/projects.py` `/stats` recompute and `templates/project.html` cashflow display. **Not yet committed/pushed** at time of writing — awaiting Mohammed's go-ahead.

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
- **No migrations:** new blob keys (`contract_type`, `currency`, `privateSettings`, etc.) need no DB change (they live inside the `FinancialData.data` JSON), but remember the project still has **no migrations folder**.
- **Uncommitted:** all of today's work is local — push to `main` is the live deploy.
