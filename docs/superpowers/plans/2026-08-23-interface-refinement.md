# BINNA Interface Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver one account control, complete bilingual presentation, and non-dismissible modal backdrops across BINNA management and operational pages.

**Architecture:** Extend the existing shared application shell and localization controller instead of adding page-specific controllers. Keep canonical values in existing inputs and API payloads; localize only presentation nodes and attributes. Enforce modal behavior in the capture phase so legacy backdrop handlers cannot discard unsaved work.

**Tech Stack:** Flask templates, standalone HTML modules, browser JavaScript, CSS, Node assertion tests, isolated SQLite response tests, real-browser verification.

**Spec:** Approved four-stage design in the 2026-08-23 conversation.

## Global Constraints

- Preserve the existing `binna-sidebar-collapsed` controller and uncommitted sidebar changes.
- Do not change permissions, tenant isolation, calculations, Gantt behavior, BOQ import, or payment synchronization.
- Do not write to the real database, run migrations, commit, or push.
- Preserve user-entered content, abbreviations, reference codes, document numbers, and unsaved form values.

---

### Task 1: Shared account and modal policy

**Files:**
- Modify: `static/js/operational-shell.js`
- Modify: `static/css/app-shell.css`
- Test: `test_application_navigation.js`

**Interfaces:**
- Consumes: existing `BINNA_APP_SHELL.init()` and `.binna-user-menu`.
- Produces: `normalizeAccountControls()`, `protectModalBackdrops()`, and exactly one shared account dropdown.

- [ ] Add failing account-uniqueness and backdrop-policy tests.
- [ ] Run `node test_application_navigation.js` and confirm the new assertions fail.
- [ ] Implement shared legacy-account removal and capture-phase backdrop protection.
- [ ] Run the focused JS test and confirm it passes.
- [ ] Verify dashboard, project, DC, Financial, Gantt, and FIR in the safe browser preview.

### Task 2: Shared localization primitives and management pages

**Files:**
- Modify: `static/js/management-i18n.js`
- Modify: `templates/dashboard.html`
- Modify: `templates/project.html`
- Test: `test_operational_i18n.js`
- Test: `test_application_navigation.py`

**Interfaces:**
- Consumes: `BINNA_I18N.t`, `formatNumber`, `formatDate`, and `binna:languagechange`.
- Produces: locale-safe `formatMoney`, `formatPercent`, `formatDuration`, and presentation-only localization.

- [ ] Add failing numeric/date/preservation and management-copy tests.
- [ ] Run focused tests and confirm the expected failures.
- [ ] Add shared formatters and localize dashboard/project dynamic strings and modal labels.
- [ ] Remove management backdrop-close hooks while retaining explicit close and Cancel actions.
- [ ] Run JS and isolated Flask tests.

### Task 3: Operational module localization and modal hardening

**Files:**
- Modify: `static/js/operational-i18n.js`
- Modify: `static/js/contract-i18n.js`
- Modify only where shared translation cannot cover behavior: `binna-*.html`
- Test: `test_operational_i18n.js`
- Test: `test_application_navigation.py`

**Interfaces:**
- Consumes: shared `BINNA_I18N` formatters and original-node preservation maps.
- Produces: reversible text/attribute/option localization without input-value mutation.

- [ ] Add failing translation, option, dynamic-message, and canonical-value tests.
- [ ] Confirm failures against current behavior.
- [ ] Complete the shared phrase catalog and dynamic formatting rules.
- [ ] Replace hard-coded English number/date presentation in commercial and Gantt modules.
- [ ] Remove module backdrop-dismiss handlers where the shared policy is not sufficient.
- [ ] Run focused JS and isolated response tests.

### Task 4: Cross-module acceptance

**Files:**
- Modify tests only if browser findings expose an uncovered regression.

**Interfaces:**
- Consumes: all shared shell and localization behavior from Tasks 1-3.
- Produces: browser evidence for account uniqueness, direction, digits, state preservation, and modal safety.

- [ ] Run all focused Node tests and `git diff --check`.
- [ ] Run Flask navigation tests against a new SQLite file outside `instance` and compare real-database hashes before/after.
- [ ] In a real browser, verify representative management, document, commercial, consultant, and Gantt pages in English and Arabic.
- [ ] Confirm backdrop clicks retain modal visibility and unsaved field values; confirm explicit ×/Cancel dismisses.
- [ ] Report the preview URL, changed files, verification evidence, and any remaining untranslated content.
