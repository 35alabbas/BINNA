# BINNA — Multi-Tenant SaaS Plan

> Unified plan merging: the 4-phase implementation plan, the infrastructure note, and the business decisions made with the architect.
> **Architect:** Mohammed (product owner) + Claude chat (spec layer). **Builder:** Claude Code (touches the repo, deploys). **Actor for code/deploy = Claude Code, never the chat.**
> Mission: turn the single-tenant BINNA (already live at binnapm.com) into a multi-company SaaS that other Iraqi construction firms can sign up for, pay for, and use.

---

## AIM

- **Actor:** Claude Code for the Build Track; Mohammed for the Launch Track. Claude chat = architect/spec only.
- **Input:** current live codebase (Flask + PostgreSQL on Render), the decisions locked below.
- **Mission:** rebuild BINNA (currently single-tenant with only dummy test data) into a multi-company SaaS, then launch to paying companies. No real data exists yet, so we start from a clean slate.

---

## Locked decisions

| Decision | Locked value |
|---|---|
| Backend + DB | Render — Flask + PostgreSQL, auto-deploy on push to `main` |
| File storage | Cloudflare R2 (Phase 3 only — not before) |
| Auth | **Keep existing Flask-JWT login** + **email verification** (no Supabase, no SMS). Email verification runs on plain Flask + a transactional email service. |
| Migration method | `_ensure_schema()` `ALTER TABLE … ADD COLUMN` in `run.py`. **NEVER drop/recreate the DB.** |
| Invites | CEO adds a member by email + assigns a role (owner / admin / member / viewer) |
| User limits | Do **not** enforce yet (pricing undecided). Build the empty columns anyway. |
| Trial / grace | 14-day trial → 7-day grace → lock **(confirmed)** |
| Payments | All manual: Zain Cash / Asia Hawala / Qi Card / NBI. You mark "paid" in admin panel. No payment API. |
| DNS | Namecheap now → migrate to Hostinger ~Aug 1, before launch. **Not a database task.** |

## Open / assumed — override if wrong

- **Verification:** **email verification = YES**, SMS = NO. Done on plain Flask + a transactional email provider — no Supabase. Provider chosen at Phase 2.
- **Trial = 14 days, grace = 7 days:** my defaults. Change the numbers if you want.
- **Notes.docx:** deferred — Mohammed will fold in later.
- **Pricing tiers:** still undecided. The schema is built so this is a later number-change, not a rebuild.

---

# BUILD TRACK

> Claude Code executes one phase, you verify, then the next phase starts. Do not skip ahead.

## Phase 0 — Clean slate (DO THIS FIRST)

The current database holds **only dummy/test data** made while building — nothing worth keeping. So instead of an elaborate migration, we clear it and build the multi-tenant structure on an empty database.

**Tasks (Claude Code):**
- Confirm with Mohammed there is no data to preserve (confirmed: dummy only).
- Clear the existing dummy data so Phase 1 builds on a clean database. **There are TWO databases — both must be cleared:** (1) local `binna.db` (SQLite, on the dev machine), and (2) **Render production PostgreSQL** (reached via `DATABASE_URL`, provided as an env var, never pasted in plaintext). Clearing production is an outward-facing action — only with Mohammed's explicit go-ahead. Best done *now*, while production is guaranteed 100% dummy.
- Note the methods differ: SQLite uses `DELETE` + `sqlite_sequence` reset + `VACUUM`; PostgreSQL uses `TRUNCATE … RESTART IDENTITY CASCADE` (or equivalent). Neither drops/recreates the schema.
- **Keep the production-safe pattern from day one:** even though this data is disposable, do *not* form the habit of dropping/recreating the DB to pick up changes. Add new columns via `_ensure_schema()` `ALTER TABLE`. This is the exact discipline that protects real customer data later — practice it now.

**Verify:** **both** databases empty/clean (local + Render production); app boots against both; `_ensure_schema()` is the mechanism used to add columns (not drop-and-recreate).

**Dependency:** none. This is the starting point.

---

## Phase 1 — Multi-tenant database structure

**Database changes (Claude Code):**
- Create `companies` table: `id`, `name`, `slug`, `plan`, `max_users`, `trial_ends_at`, `grace_ends_at`, `status`, `created_at`.
  - `plan` default `"trial"`. `max_users` default `999` (= unlimited for now). `status` ∈ `trial` / `active` / `grace` / `locked`.
- Add `company_id` foreign key to `users`.
- Add `company_id` to **every** project/data table (projects, and all module tables).
- Add `role` column to `users`: `owner` / `admin` / `member` / `viewer`.
- Add all new columns via the `additions` list in `_ensure_schema()` (`ALTER TABLE … ADD COLUMN`). **Do not** use `flask db upgrade` (there is no migrations folder).

**No backfill needed.** The database is empty (Phase 0), so there's no existing data to assign to a company. The first real company gets created the normal way — when someone signs up through the registration flow (Phase 2). There is **no pre-seeded "first company,"** and Al-Hajrass has nothing to do with BINNA's data.

**Verify:** app boots; `companies` table exists; `users` and all data tables have `company_id` + the `role` column; a fresh sign-up can create a company and become its `owner`.

**Dependency:** Phase 0 (clean database).

---

## Phase 2 — Accounts & access (replaces the old "Supabase" phase)

Auth stays as the existing Flask-JWT login. We add company + roles + **email verification** on top of it.

**Email-sending setup (do this first in Phase 2 — powers both verification and invites):**
- Pick a transactional email provider (free tier is enough at this stage) and wire it into Flask (API key in Render env vars).
- One sending capability serves **both** the verification emails and the invite emails below.

**Backend logic (Claude Code):**
- **Scope every DB query to the logged-in user's `company_id`.** No query returns another company's data. This is the heart of multi-tenancy — test it hard.
- **Add `email_verified` (boolean, default false) + a verification token to the `users` model** (via `_ensure_schema()`).
- **Company registration flow (self-signup):** user signs up → account created **unverified**, no access yet → verification email sent with a tokenised link → user clicks link → `email_verified = true` → `companies` row created, user becomes its `owner`, `trial_ends_at` set to +14 days.
- **Invite system:** owner/admin adds a member by email + assigns a role (admin / member / viewer). The member receives an invite email; **clicking the invite link proves email ownership, so invited members skip the separate verification step** (the link *is* the verification). Reuse the existing role order `viewer(0) < member(1) < admin(2) < owner(3)`.
- **Password reset** (uses the same email plumbing — easy to add here).
- **Role-based access middleware:** enforce role on every protected route (extend the existing `_requires_role` helper to also check `company_id` match). Unverified self-signups cannot access the app until verified.

**Verify:** create two test companies. A self-signup is blocked until the emailed link is clicked. Confirm company A literally cannot see company B's data via any endpoint. Invited member lands verified via the invite link. A `viewer` cannot edit; an `owner` can manage members.

**Dependency:** Phase 1 (users must have `company_id` + `role` before access is wired).

---

## Phase 3 — Cloudflare R2 file storage

**Setup (Claude Code, with your account):**
- Create Cloudflare account + R2 bucket; create an API token (read + write).
- Add R2 credentials to Render env vars; configure CORS for binnapm.com.

**BINNA integration:**
- File-upload endpoint (Flask → R2). Files stored as `company_id/project_id/filename` (tenant isolation in the path).
- Store the file **URL** in PostgreSQL, not the file bytes.
- Presigned URLs for secure downloads. 50 MB/file limit. Allowed types: PDF, PNG, JPG, DWG, XLSX.

**Verify:** company A's files live under its `company_id` prefix and are not reachable by company B. Upload + download round-trip works via presigned URL.

**Dependency:** Phase 1 (paths need `company_id`).

---

## Phase 4 — Dashboards & manual billing

**CEO workspace (the customer's view):**
- Company settings page.
- Invite users by email + assign role; remove/deactivate users.
- Storage-usage indicator (how much R2 used).

**Your admin panel (your view):**
- List all companies + plan + status.
- Activate / suspend accounts manually.
- **Mark invoice as paid → set company `status = active`, extend the period.**
- Revenue tracker: who paid, when, how much.

**Trial / grace / lock logic:**
- On login (or a daily check): if `now > trial_ends_at` and unpaid → `status = grace`. If `now > grace_ends_at` and unpaid → `status = locked`.
- `locked` = read-only or blocked (your call — recommend read-only so they don't lose access to their data, just can't edit until they pay).

**Verify:** marking an invoice paid flips the company to `active`. A locked company cannot edit. The revenue tracker totals correctly.

**Dependency:** Phases 1–3.

---

# LAUNCH TRACK

> Your job, not code. Runs in parallel with the Build Track. Only the DNS step is time-boxed.

- [ ] **Decide pricing** — single tier or Starter/Pro/Enterprise. Until decided, every company is `plan = trial`, `max_users = 999`. This is a later number-change, not a rebuild.
- [ ] **Write a payment-instructions page** — how a company pays you (Zain Cash / Asia Hawala / Qi Card / NBI account details) and how they tell you they've paid.
- [ ] **DNS migration to Hostinger (~Aug 1)** — move nameservers, repoint binnapm.com → Render. Do this *near launch*, not during Phase 0–1. Touching DNS early only adds risk and helps nothing.
- [ ] **Email deliverability records (after the Hostinger migration)** — add SPF + DKIM (and optionally DMARC) DNS records for the chosen email provider (recommended: **Resend**) so verification / invite / invoice emails reach the inbox instead of spam. Do this *on Hostinger after Aug 1* — setting them up on Namecheap now means redoing them after the move. The verification logic works before this; this is purely about deliverability.
- [ ] **Go-live checklist** — Phases 0–4 verified, DNS live on Hostinger, payment page published, first real company onboarded.

---

## Status: ready for Phase 0

All decisions are locked. Nothing is blocking the build.

- **Trial / grace:** 14 days → 7 days → lock. ✅ confirmed.
- **Verification:** email verification YES, SMS NO. ✅ decided.
- **Auth:** keep Flask-JWT, add native email verification, no Supabase. ✅ decided.
- **Al-Hajrass:** unrelated to BINNA — not a tenant, no data row. ✅ decided.
- **Notes.docx:** Mohammed will fold in later. ⏳ deferred by choice (non-blocking).
- **Pricing:** undecided — doesn't block; schema handles it as a later number-change.

**Next action:** hand **Phase 0 only** to Claude Code. Verify it, then release Phase 1.

> **Mohammed's role inside BINNA:** you are the **platform super-admin** (the admin panel — see all companies, mark invoices paid, activate/lock). You are *not* a "company" in the data. If you want to test the product as a user, register a test company through the normal sign-up flow like any customer would. Al-Hajrass is your employer, unrelated to BINNA.
