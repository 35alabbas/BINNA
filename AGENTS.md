# BINNA Project Instructions

## Product and interface

- BINNA is a bilingual Arabic/English project-management platform for contractor companies operating in Iraq.
- The active product target is contractor companies, not consultant-side users or government-authority workflows.
- Arabic interfaces use RTL; English interfaces use LTR.
- Keep the UI light, professional, and sidebar-based.

## Active MVP scope (authoritative as of 2026-09-04)

- Company and project dashboards.
- Contract and Payments.
- BOQ.
- Accounts.
- Gantt and progress.
- Document Control.
- Daily Reports.
- Lab Tests.
- Subcontractors and Suppliers.
- Roles, permissions, monitoring comments, and audit logs.
- MIR, FIR, MS, RFI, and DWG are outside the active MVP and must not appear in the active MVP navigation or project module cards. Preserve their existing code, database records, and historical data temporarily; do not delete or migrate them without a later, separately approved cleanup.

## Project and contract model

- A normal project is itself the main contract.
- A framework agreement is a parent project containing multiple child contracts. It is not a supplier agreement.
- A framework agreement has a master BOQ. Child contracts select items from that BOQ.
- Master BOQ items may have fixed or variable prices. Additional items may be added when necessary.
- Call-off is an optional contractual setting for a framework agreement.
- Support contract-specific variations, guarantees, delays, penalties, preliminary and final handover, and notifications.
- Maintain a simple immutable audit log for important actions and changes.
- Use one unified contract workspace for government, private, and investment projects.
- Treat project classification as metadata for context and warnings only. Do not create separate complex forms or hard-coded workflows for every contract type.
- Prefer flexible, Excel-like tables with user-entered values, editable rows, notes, and Excel import/export. Avoid hard-coding every possible calculation or contractual workflow.
- Advanced framework-agreement expansion is deferred beyond the active MVP.

## Roles, employees, and permissions

- Company managers and projects managers may create, close, and manage projects; assign or replace project managers; manage employees; monitor projects; and add comments.
- Company managers and projects managers must not directly edit operational project records unless separately authorized.
- Each project has one designated project manager with full operational control. The same person may manage multiple projects.
- Project managers grant employees per-module view/edit permissions but do not create or close projects.
- Employees may belong to multiple projects and may have different permissions in each project.
- Consultant-side workflow development is deferred beyond the active MVP.

## Gantt and progress

- Preserve the existing Gantt chart, original baseline, predecessor relationships, stoppages, approved extensions, and all current working features.
- Gantt activity durations are entered manually.
- Contract completion dates change only after approved extensions.
- Activity weight equals the activity duration divided by the total duration of all executable leaf activities.
- Physical progress is the weighted sum of actual activity completion.
- Summary rows must never be counted twice.
- Financial progress is independent from schedule progress.
- The company project list displays the project name, financial progress percentage, schedule progress percentage, commencement date, and completion date when available.

## Finance and payments

- Project cashbox income means funding received from the company only.
- Payments received from the project owner belong to the main-contract payment records and must never automatically appear as project cashbox income.
- Subcontractor and supplier payments appear as project expenses and affect the project cashbox only when actually paid.
- HR and payroll are deferred beyond the active MVP.
- A framework agreement has one overall cashbox and separate financial tracking for each child contract.
- Internal allocations must not be double-counted as expenses.

## Engineering constraints

- Preserve existing code, documentation, working behavior, and tests unless a task explicitly authorizes a scoped change.
- Do not rely on Cloudflare, old domains, or discontinued hosting services.
- Support Excel import and export for BOQs and financial tables.
- Support Word export for correspondence and official documents.
- Support government, private, and investment projects through the unified contract workspace.
- Defer ITP integration, prequalification workflows, HR and payroll, advanced framework-agreement expansion, and consultant-side workflow development.
- Preserve existing code and data, tenant isolation, permissions, auditability, existing financial separation, and Gantt behavior.
