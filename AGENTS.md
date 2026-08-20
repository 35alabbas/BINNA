# BINNA Project Instructions

## Product and interface

- BINNA is a bilingual Arabic/English project-management platform for contractor companies operating in Iraq.
- Arabic interfaces use RTL; English interfaces use LTR.
- Keep the UI light, professional, and sidebar-based.

## Project and contract model

- A normal project is itself the main contract.
- A framework agreement is a parent project containing multiple child contracts. It is not a supplier agreement.
- A framework agreement has a master BOQ. Child contracts select items from that BOQ.
- Master BOQ items may have fixed or variable prices. Additional items may be added when necessary.
- Call-off is an optional contractual setting for a framework agreement.
- Support contract-specific variations, guarantees, delays, penalties, preliminary and final handover, and notifications.
- Maintain a simple immutable audit log for important actions and changes.

## Roles, employees, and permissions

- Company managers and projects managers may create, close, and manage projects; assign or replace project managers; manage employees; monitor projects; and add comments.
- Company managers and projects managers must not directly edit operational project records unless separately authorized.
- Each project has one designated project manager with full operational control. The same person may manage multiple projects.
- Project managers grant employees per-module view/edit permissions but do not create or close projects.
- Employees may belong to multiple projects and may have different permissions in each project.
- Consultant modules MIR, FIR, MS, RFI, and DWG are optional and are enabled by the project manager.
- Framework agreements generally do not require consultant modules, but lab testing may still be enabled.

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
- HR and payroll must support payment from either the project cashbox or directly by the company.
- Payroll paid directly by the company counts as project cost but does not reduce the project cashbox balance.
- A framework agreement has one overall cashbox and separate financial tracking for each child contract.
- Internal allocations must not be double-counted as expenses.

## Engineering constraints

- Preserve existing code, documentation, working behavior, and tests unless a task explicitly authorizes a scoped change.
- Do not rely on Cloudflare, old domains, or discontinued hosting services.
- Support Excel import and export for BOQs and financial tables.
- Support Word export for correspondence and official documents.
- Support both government and private projects.
- Defer ITP integration and prequalification workflows.
- Prefer changes that maintain Arabic/English behavior, tenant isolation, project permissions, financial separation, and auditability.
