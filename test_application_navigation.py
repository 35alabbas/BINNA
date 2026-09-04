#!/usr/bin/env python3
"""Shared application-navigation response contract on isolated SQLite."""
import os
import re
import sys
from pathlib import Path


def _verified_database() -> Path:
    url = os.environ.get('DATABASE_URL', '')
    if os.environ.get('BINNA_ISOLATED_TEST_DB') != '1' or not url.startswith('sqlite:///'):
        raise RuntimeError('Refusing to run without an explicitly isolated SQLite database')
    path = Path(url[len('sqlite:///'):]).resolve()
    protected = (Path(__file__).resolve().parent / 'instance').resolve()
    try:
        path.relative_to(protected)
    except ValueError:
        pass
    else:
        raise RuntimeError('Refusing to use a database inside C:\\BINNA\\instance')
    if not path.is_file() or path.stat().st_size != 0:
        raise RuntimeError('Test database must be a newly created empty file')
    return path


TEST_DB = _verified_database()

from app import create_app  # noqa: E402


app = create_app('development')
client = app.test_client()
passed = failed = 0


def check(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print('  ok   ' + name)
    else:
        failed += 1
        print('  FAIL ' + name)


print(f'ISOLATED_DATABASE={TEST_DB}')
print('Shared application navigation')

for route in ('/dashboard', '/project/1', '/company'):
    response = client.get(route)
    html = response.get_data(as_text=True)
    check(f'{route} loads the shared application shell',
          response.status_code == 200 and '/static/js/operational-shell.js' in html)
    check(f'{route} exposes the canonical sidebar toggle',
          'data-binna-sidebar-toggle' in html)

project_html = client.get('/project/1').get_data(as_text=True)
check('project cards consume the shared navigation model',
      'BINNA_APP_SHELL.visibleNavigation' in project_html)
check('project cards request only the active project navigation section',
      "dashboardModules('project')" in project_html and
      "dashboardModules('consultant')" not in project_html)
check('project dashboard does not render a consultant module section',
      'modules-grid-consultant' not in project_html and
      'consultant-title' not in project_html)

dashboard_html = client.get('/dashboard').get_data(as_text=True)
modules_match = re.search(r'const modules = \[(.*?)\];', dashboard_html, re.S)
dashboard_modules = re.findall(r"\['([^']+)'\s*,\s*'[^']+'\]",
                               modules_match.group(1) if modules_match else '')
check('company dashboard pills use the exact active module order',
      dashboard_modules == ['dc', 'dr', 'contract', 'financial', 'gantt', 'sub', 'lbt'])
check('company dashboard includes the active subcontractor URL',
      'sub' in dashboard_modules and '/legacy/${key}' in dashboard_html)
check('company dashboard excludes consultant workflow pills',
      not {'dwg', 'fir', 'mir', 'ms', 'rfi'}.intersection(dashboard_modules))

for module in ('contract', 'dc', 'dr', 'financial', 'gantt', 'sub',
               'dwg', 'fir', 'mir', 'ms', 'rfi', 'lbt', 'income', 'expense'):
    response = client.get('/legacy/' + module)
    check(f'{module} remains reachable through its existing URL',
          response.status_code == 200)
    check(f'{module} loads the shared application shell',
          '/static/js/operational-shell.js' in response.get_data(as_text=True))

for module in ('mir', 'ms', 'rfi'):
    html = client.get('/legacy/' + module).get_data(as_text=True)
    check(f'{module} exposes exactly one canonical operational sidebar',
          len(re.findall(r'id=["\']sidebar["\']', html)) == 1 and
          len(re.findall(r'class=["\'](?:[^"\']+\s)?sidebar(?:\s[^"\']*)?["\']', html)) == 1)
    check(f'{module} removes its conflicting inline sidebar toggle',
          'onclick="toggleSidebar()"' not in html and
          'function toggleSidebar()' not in html)
    check(f'{module} removes legacy permanent branding',
          'Construction PM' not in html and 'Government' not in html)

admin_html = client.get('/admin').get_data(as_text=True)
check('platform administration remains outside the company/project shell',
      '/static/js/operational-shell.js' not in admin_html)

print(f'RESULT: {passed} passed, {failed} failed')
sys.exit(1 if failed else 0)
