#!/usr/bin/env python3
"""Focused Stage 1 UI contract checks (no database access)."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
dashboard = (ROOT / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
project = (ROOT / 'templates' / 'project.html').read_text(encoding='utf-8')
api = (ROOT / 'static' / 'js' / 'binna-api.js').read_text(encoding='utf-8')

checks = {
    'project code is visibly optional and may be auto-generated':
        'id="f-code"' in dashboard and 'auto-generated' in dashboard.lower(),
    'creation exposes independent classification controls': all(token in dashboard for token in (
        'id="f-project-regime"', 'id="f-investment-subtype"',
        'id="f-work-nature"', 'id="f-contract-structure"',
    )),
    'investment subtype is contextually controlled':
        'updateInvestmentSubtypeVisibility' in dashboard,
    'small-project creation still requires only a name':
        "if (!name)" in dashboard and 'if (!code || !name)' not in dashboard,
    'project page includes warnings and classification settings':
        'id="project-warnings"' in project and 'id="classification-section"' in project,
    'project page handles migration-required classification safely':
        'project_classification_migration_required' in project,
    'shared API exposes classification and warning operations': all(token in api for token in (
        'fetchProjectWarnings', 'updateProjectClassification', 'dismissProjectWarning',
    )),
}

failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(('  ok   ' if passed else '  FAIL ') + name)
print(f'RESULT: {len(checks) - len(failed)} passed, {len(failed)} failed')
sys.exit(1 if failed else 0)
