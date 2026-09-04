# BINNA Contract & Payments Audit

**Status:** APPROVED BUSINESS DECISIONS — IMPLEMENTATION SLICE NOT YET APPROVED  
**Audit date:** 2026-09-04  
**Business-decision approval:** Approved by Mohammed on 2026-09-04  
**Audited branch:** `feature/binna-foundation`  
**Audited checkpoint:** `069533866be20daddbe8fbf9b3199f883a2d72f0` â€” `docs: record MVP navigation verification`  
**Scope:** Read-only source audit. No code, test, schema, migration, database, commit, push, or merge was performed.

---

## 1. Executive verdict

BINNA does not need a new Contract & Payments backend or a destructive data migration to begin the approved simplification. The existing backend already stores one project-scoped financial document in `FinancialData.data`, and the same workspace already contains Contract Details, BOQ, Variation Orders, and Payments.

The main mismatch is in the standalone UI. `binna-contract.html` is a 4,588-line page containing two separate payment renderers: a government cumulative workflow and a private workflow with lump-sum, monthly, milestone, and custom templates. The page chooses between them using its own saved `data.contract_type` flag and does not use the project's `project_regime`, `investment_subtype`, `work_nature`, or `contract_structure` metadata.

The safest direction is therefore evolutionary:

1. Preserve the existing financial JSON, routes, permissions, and historical payment records.
2. Introduce a compatibility layer that interprets the old government/private fields as neutral payment-entry methods.
3. Characterize the existing behavior with focused tests before changing the large inline script.
4. Gradually converge the visible UI into one neutral payment workspace with optional rules and calculation aids.
5. Do not connect project classification to mandatory payment workflows; use it only for context and warnings.

---

## 2. Current user workflow

1. The user opens `/legacy/contract`, which loads `binna-contract.html` through the legacy page route.
2. `BINNA.requireProject()` requires an active project context, and `BINNA.getProject()` supplies the project identifier, code, and name.
3. The page calls `GET /api/v1/projects/<project_id>/financial` through `BINNA.fetchFinancial()`.
4. The returned JSON becomes the page's complete `data` object.
5. The user works through three visible tabs:
   - Contract Details
   - Bill of Quantities and Variation Orders
   - Payments
6. The Payment System selector chooses one of:
   - Cumulative
   - Lump Sum
   - Monthly Invoice
   - Milestone
   - Other
7. Internally, Cumulative is stored and rendered as `government`; the other four choices are stored and rendered as `private` plus `privateSettings.template`.
8. Once meaningful payment data exists, the payment-system choice and decimal precision are locked.
9. Input and change events schedule a complete financial-document autosave after 800 ms.
10. Saving calls `PUT /api/v1/projects/<project_id>/financial` with the entire JSON document.
11. Stoppages are loaded and saved separately through the Gantt stoppage endpoints. Approved extensions remain inside `contractDetails.extensions` in the financial JSON.

---

## 3. Architecture map

| Area | UI/source | Client API | Backend/storage | Existing verification |
|---|---|---|---|---|
| Workspace route | `app/pages.py`, `binna-contract.html` | Project context from `static/js/binna-api.js` | Legacy page delivery | `test_application_navigation.py` |
| Full financial document | `binna-contract.html` `loadAll()`, `collectAll()`, `saveAll()` | `fetchFinancial()`, `saveFinancial()` | `GET/PUT /api/v1/projects/<id>/financial`; `FinancialData.data` JSON | `test_module_access.py`, `test_isolation.py` |
| Contract details | `binna-contract.html` Contract Details tab | Full-document save | `data.contractDetails` | Indirect overview assertions in `test_phase_1b_ui_contract.py` |
| BOQ | `addBoqRow()`, `collectBoq()`, `recalcBoq()` | Full-document save | `data.boq` | Import coverage in `test_operational_foundation.py` |
| BOQ import | Import modal in `binna-contract.html` | `previewBoqImport()` | `POST /financial/boq-import/preview` | `test_operational_foundation.py` |
| Variation Orders | `addVoRow()`, `collectVO()`, `recalcVo()` | Full-document save | `data.vo` | No focused calculation suite found |
| Government/cumulative payments | `renderPayRows()` | Full-document save | `data.payments`, `data.contract_type` | Permission/isolation tests; no focused browser/JS calculation suite found |
| Private/template payments | `renderPrivatePayRows()` | Full-document save | Same `data.payments`; `privateSettings` | No focused browser/JS calculation suite found |
| Amounts received from owner | Both payment renderers | Full-document save | `payment.received[]`; summarized into `cashflowSummary` | Overview checks in `test_phase_1b_ui_contract.py` |
| Project cashbox | Separate Financial page and `/financial/income` partial save | `saveIncomeExpenses()` | Same JSON, but partial route preserves contract/BOQ/VO/payments | `test_payment_expense_sync.py` |
| Stoppages | Contract modal and Gantt UI | `fetchStoppages()`, `saveStoppages()` | Gantt stoppage endpoints and `GanttData` | `test_operational_foundation.py` |
| Extensions | Contract Details | Full-document save | `contractDetails.extensions[]` | No focused extension UI suite found |
| Payment attachments | Payment card | Embedded client-side | Base64 data URLs inside financial JSON | No focused size/storage suite found |
| Localization | Inline text plus `static/js/contract-i18n.js` | DOM translation/MutationObserver | No backend impact | General i18n tests, but no full contract-page coverage found |

---

## 4. Current data model and APIs

### Project classification

`Project` stores:

- `project_regime`
- `investment_subtype`
- `work_nature`
- `contract_structure`
- `optional_field_states`

These fields are correctly modeled as project metadata and have separate classification and warning endpoints. The contract page currently does not consume them.

### Financial document

`FinancialData` contains one unique record per project:

- `company_id`
- `project_id`
- `data` â€” complete JSON document
- `updated_by`
- `updated_at`

Observed JSON areas include:

- `contractDetails`
- `boq`
- `vo`
- `payments`
- `contract_type`
- `privateSettings`
- `currency`
- `currency_custom`
- `decimalPlaces`
- `cashflowSummary`
- `income`
- `expenses`
- `incomeCategories`
- `expenseCategories`
- `usdRate`

The full financial PUT accepts the document as an arbitrary JSON payload and rewrites the complete blob. It specially preserves system-linked project expenses and required expense categories.

### BOQ import

The import preview accepts `.xlsx` and `.csv`, up to 5 MB and 5,000 rows. It can map item number, description, unit, quantity, unit price, and optional source total. Description, quantity, and unit price are required for valid imported rows.

No BOQ or financial-table Excel export endpoint or visible export control was found in the audited checkpoint.

### Payment data

Both renderers reuse `data.payments`. Common/observed fields include:

- identity, description, date, status
- BOQ-linked quantities
- manual work and manual items
- extra deductions, reversals, and surplus credits
- received installments
- attachments
- custom summary labels/rows
- government calculation state
- private/template calculation state

This shared array is a strong compatibility foundation, but the meanings of some fields depend on which renderer is active.

---

## 5. Unified versus project-type-specific behavior

### Already unified

- One Contract & Payments page.
- One project-scoped financial record.
- One set of financial GET/PUT routes.
- One Contract Details tab.
- One BOQ and Variation Order area.
- One `payments` array.
- Shared currency, decimal precision, received-installment, deduction, reversal, attachment, and summary concepts.
- Shared project permissions and tenant-isolation gates.

### Still split or conflated

- `data.contract_type` switches between government and private renderers.
- `privateSettings.template` chooses lump-sum, monthly, milestone, or custom behavior.
- Project classification is not used by the contract page.
- Investment projects have no independent payment renderer. Unless manually changed, any non-private saved flag resolves to government behavior.
- The UI currently conflates â€œproject regimeâ€ with â€œpayment-entry/calculation method.â€ These are different business concepts.

The approved direction should not make government, private, or investment classification select a mandatory form. A project may be government-funded but still require a custom payment record, or a private project may use cumulative BOQ measurement.

---

## 6. KEEP / SIMPLIFY / DEFER / PRESERVE

| Feature | Classification | Reason |
|---|---|---|
| Single financial record per project | KEEP | Already supports a unified workspace and compatibility |
| Existing financial GET/PUT routes | KEEP | Permission-gated, tenant-scoped, and widely reused |
| Contract Details | KEEP + SIMPLIFY | Useful common fields; avoid regime-specific required forms |
| Manual overrides for contract/VO/final values | KEEP | Matches flexible user-entered direction |
| BOQ rows, sections, sub-items, ordering, units | KEEP | Good Excel-like foundation |
| BOQ import preview and validation | KEEP | Useful and safely permission-gated |
| BOQ fixed columns only | SIMPLIFY/EXTEND LATER | Flexible rows exist, but custom columns and row notes are limited |
| BOQ/financial Excel export | ADD LATER | Required by product direction but not found |
| Variation Order table | KEEP + SIMPLIFY | Common contract concept; current fields are useful |
| One payments array | KEEP | Best compatibility bridge for a unified UI |
| Separate government/private visible workspaces | SIMPLIFY | Replace gradually with one neutral payment workspace |
| `contract_type` and `privateSettings` stored keys | PRESERVE | Existing records depend on them; use through an adapter |
| Project regime metadata | KEEP AS CONTEXT | Show context/warnings only; do not force a renderer |
| Cumulative BOQ measurement | KEEP AS OPTIONAL METHOD | Valuable for measured contracts, regardless of regime |
| Manual/custom payment rows | KEEP + FIX | Central to the approved flexible direction |
| Hard-coded government calculations | CONVERT TO OPTIONAL RULES | Do not impose them automatically on every government project |
| Private templates | KEEP AS STARTING TEMPLATES | Templates should prefill/edit, not create a separate subsystem |
| Received installments and cashflow summary | KEEP | Correctly separate owner receipts from project cashbox income |
| Shared Gantt stoppages | KEEP | Correct single source of truth |
| Approved extensions | KEEP; HARDEN LATER | Useful, but should gain stronger references/auditability |
| Base64 payment attachments in financial JSON | REPLACE LATER; PRESERVE OLD DATA | Risks blob growth and bypasses the normal upload ownership records |
| Advanced framework-agreement expansion | DEFER | Explicitly outside active MVP |

---

## 7. Gaps against the approved product direction

### 7.1 Project regime and payment method are conflated

The page's `getContractType()` returns only government or private based on the financial JSON. The project classification fields are not read. This creates parallel payment systems that do not accurately represent the project model.

### 7.2 Several calculations are embedded as assumptions

The cumulative renderer includes assumptions such as:

- performance guarantee required = 5% of contract total
- withholding 10% of current work before 50% completion, capped at the required 5%
- two 50% guarantee releases
- default tax rate of 3%
- optional final-payment retention of 10%
- special â€œwithin/over 20%â€ quantity and new-price handling

The private renderer has optional toggles, but its initial defaults include 20% advance recovery and 5% retention.

These may be useful presets for some Iraqi contracts, but they must become editable optional rules or templates, not consequences of project regime.

### 7.3 Flexible rows are inconsistent

- Private `summaryRows` contribute to gross/subtotal/net calculations.
- Government `customSummaryRows` are displayed, but the audited `netFinal` calculation does not include their signed values.

Therefore the government custom-row UI can visually show a value without affecting the calculated net. This must be characterized by a RED test before repair.

### 7.4 BOQ is flexible by row, not yet by table design

The BOQ supports editable rows, sections, sub-items, custom units, drag/order controls, and import. However, the columns remain fixed to item number, description, unit, quantity, price, and amount. There is no dedicated row-notes field or confirmed Excel export.

### 7.5 The page is an untested monolith

`binna-contract.html` contains UI, state management, rendering, calculations, attachment handling, localization hooks, and persistence orchestration in one large inline script. Existing tests strongly cover backend permissions/isolation and BOQ import, but no focused JavaScript calculation suite for this workspace was found.

### 7.6 Mobile and RTL need focused verification

The page uses the shared shell and a translation layer, but no dedicated screen-width responsive breakpoint was found inside `binna-contract.html`; most detected media rules are print rules. The workspace contains dense grids and wide tables. This does not prove failure, but it requires targeted 390 px English and Arabic/RTL checks during implementation.

---

## 8. Compatibility and security risks

### Strengths to preserve

- Financial routes use `authorize_project_access()`.
- View and edit permissions are separated by module.
- Foreign-tenant financial access is denied.
- Closed projects block writes through the shared authorization path.
- Stoppages use the Gantt source of truth and preserve Gantt tasks.
- Project-owner receipts remain separate from project cashbox income.
- Linked subcontractor/supplier payment expenses are protected against manual removal.

### Risks to address incrementally

1. **Historical-data risk:** Renaming/removing `contract_type`, `privateSettings`, or payment fields would break saved records. Use an adapter; do not migrate first.
2. **Lost-update risk:** The entire JSON document is autosaved and replaced, with no document revision/ETag check. Two editors can overwrite each other.
3. **Audit gap:** Financial saves update `updated_by` and `updated_at`, but the audited financial routes do not record immutable `AuditLog` entries for contract/BOQ/payment changes.
4. **Schema/data-quality risk:** The full PUT accepts an arbitrary payload without a versioned server-side shape validation.
5. **Attachment risk:** Each payment attachment is converted to a base64 data URL and embedded in the financial JSON. There is a 5 MB per-file client check but no clear aggregate document limit. This can produce very large autosave requests and bypass the normal upload ownership model.
6. **Calculation risk:** Important rules live in browser JavaScript and lack a focused calculation test suite.
7. **Custom-row correctness risk:** Government custom summary values appear disconnected from final net calculations.
8. **Localization risk:** Much of the dynamic interface is translated by scanning generated DOM text. New dynamic labels can remain English unless explicitly covered.

---

## 9. Smallest recommended first implementation slice

### PROPOSED â€” NOT YET APPROVED

Implement a **payment-method compatibility foundation**, not the full unified redesign.

The first slice should:

1. Add focused characterization tests for current legacy financial JSON and payment-method selection.
2. Introduce a small pure normalization/compatibility layer that maps existing data to neutral methods:
   - legacy `government` -> `cumulative_boq`
   - legacy private `lumpsum` -> `lump_sum`
   - legacy private `monthly` -> `monthly`
   - legacy private `milestone` -> `milestone`
   - legacy private `custom` -> `flexible_manual`
3. Preserve `contract_type`, `privateSettings`, and every existing payment object unchanged when reading and saving historical records.
4. Change only the user-facing concept from â€œgovernment/private contract typeâ€ to â€œPayment Entry Method.â€
5. Do not use `project_regime` to choose the method. It may be displayed as informational project context only.
6. Add a RED test proving whether signed government custom rows affect the payment net. If they do not, document the failure and repair it only if included in the approved slice.
7. Add no schema or migration.

This slice provides a safe foundation for the later unified payment table without deleting working calculations or forcing a risky rewrite.

### Explicitly outside the first slice

- Full visual redesign of all payment cards
- Database normalization
- Attachment migration
- Concurrency/versioning implementation
- New framework-agreement behavior
- Removal of legacy keys or renderers
- Full BOQ custom-column system

---

## 10. Exact expected files and tests

### Likely modified files for the proposed first slice

- `binna-contract.html`
- `static/js/contract-i18n.js`
- A new focused pure-JavaScript helper, preferably `static/js/contract-workspace.js`
- `static/js/binna-api.js` only if project classification context must be refreshed from the API rather than existing project context

### Likely tests

- New `test_contract_workspace.js`
- New or extended `test_contract_workspace_ui.py`
- Existing `test_module_access.py`
- Existing `test_isolation.py`
- Existing `test_operational_foundation.py`
- Existing `test_payment_expense_sync.py`
- Existing `test_phase_1b_ui_contract.py`
- Existing application navigation and i18n suites

After implementation, run focused RED/GREEN tests first, then the complete isolated offline regression. Keep the two real external-service suites intentionally skipped unless separately authorized with safe credentials.

---

## 11. Approved business decisions

**Approved by Mohammed on 2026-09-04.** These approvals resolve the product decisions only. No implementation slice or production-code modification has been approved yet.

1. **Fully customizable payment entry methods:** Payment entry methods must be fully customizable. BINNA may provide reusable templates such as cumulative BOQ, lump sum, monthly, milestone, and flexible manual entry, but project classification or contract category must never force a payment method.

2. **Optional government templates:** Government percentages and rules must be optional, editable templates. They must not be automatically enforced solely because the project is classified as government, private, or investment.

3. **Small common financial core:** Every payment must have a small common financial core for Accounts, reports, and summaries:
   - identity/description
   - date
   - status
   - gross/work value
   - additions
   - deductions
   - net value
   - amount received
   - outstanding balance
   - notes
   - attachments

   Additional fields, calculation methods, and table layout must remain customizable.

4. **Work-value entry:** Each payment must support either BOQ-based cumulative measurement or direct manual work-value entry.

5. **Signed additions and deductions:** User-created additions and deductions must affect the calculated net using explicit positive or negative treatment and tested arithmetic.

6. **Attachment compatibility and deferred migration:** Existing embedded attachments must remain readable. New attachments should eventually use BINNA's protected upload service, but this migration is deferred from the first implementation slice.

7. **MVP BOQ priority:** For the active MVP, reliable BOQ import and export should be completed before building arbitrary custom columns or a spreadsheet formula engine.

---

## 12. Final repository-state confirmation

The audit used the remote GitHub checkpoint `0695338` in read-only mode. No repository file was changed remotely.

Mohammed's local check immediately before this report showed:

```text
?? .claude/
```

Therefore the local tracked worktree was clean, and the pre-existing `.claude/` directory remained untracked and untouched.

---

## Next Session Starting Point

1. Business decisions resolved and approved.
2. Review and approve the smallest implementation slice.
3. Define TDD characterization and RED tests before production-code changes.
4. Implement only the separately approved slice.
5. Run focused tests and complete isolated offline regression.
6. Perform Mohammed's visual verification.
7. Document, commit, and push only after approval.
8. Do not merge into `main` yet.
