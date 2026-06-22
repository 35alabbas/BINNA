#!/usr/bin/env python3
"""
BINNA — timezone-safe datetime comparison (Phase 4 pre-work).

DB columns are plain DateTime, so trial_ends_at / grace_ends_at / created_at
round-trip NAIVE, while _now() is tz-aware. Comparing the two directly raises
TypeError (the bug class that already hit password-reset expiry). models.as_aware()
+ is_past() are the canonical fix. This test asserts:

  1. The raw naive-vs-aware comparison really does raise (documents the hazard).
  2. as_aware() makes that same comparison safe.
  3. is_past() never throws and treats NULL as "no deadline" (never locked).
  4. A real trial-active company (trial_ends_at = created_at + 14d, like prod
     companies 1 & 2 right now) round-tripped through the DB is correctly NOT
     locked — and the comparison doesn't throw or silently misbehave.

Exit 0 = all assertions hold.
"""
import os, sys, tempfile
from datetime import timedelta

_TMP = os.path.join(tempfile.gettempdir(), 'binna_tz_test.db')
if os.path.exists(_TMP):
    os.remove(_TMP)
os.environ['DATABASE_URL'] = 'sqlite:///' + _TMP
os.environ['FLASK_ENV']    = 'development'

from app import create_app, db                                   # noqa: E402
from app.models import Company, _now, as_aware, is_past          # noqa: E402

app = create_app('development')
import run                                                        # noqa: E402,F401
with app.app_context():
    db.create_all(); run._ensure_schema()

_PASS = _FAIL = 0
def check(name, cond):
    global _PASS, _FAIL
    _PASS += bool(cond); _FAIL += (not cond)
    print(('  ok   ' if cond else '  FAIL ') + name)


print('═' * 70)
print('  TIMEZONE-SAFE DATETIME COMPARISON (Phase 4 pre-work)')
print('═' * 70)

# ── 1. The hazard: raw naive vs aware comparison raises ───────────────────────
print('\n[1] raw naive-vs-aware comparison is the bug')
naive_future = (_now() + timedelta(days=14)).replace(tzinfo=None)
raised = False
try:
    _ = naive_future > _now()        # naive > aware → TypeError
except TypeError:
    raised = True
check('raw `naive > _now()` raises TypeError (the bug as_aware prevents)', raised)

# ── 2. as_aware makes it safe ─────────────────────────────────────────────────
print('\n[2] as_aware() normalises so the comparison is safe')
check('as_aware(naive_future) > _now() is True, no throw', as_aware(naive_future) > _now())
check('as_aware(None) is None (NULL stays NULL)', as_aware(None) is None)

# ── 3. is_past primitive: NULL-safe, no throw ─────────────────────────────────
print('\n[3] is_past() — the Phase 4 comparison primitive')
naive_past = (_now() - timedelta(days=1)).replace(tzinfo=None)
check('is_past(naive past deadline) is True (expired), no throw', is_past(naive_past) is True)
check('is_past(naive future deadline) is False (still active)',  is_past(naive_future) is False)
check('is_past(None) is False (NULL ⇒ never expired ⇒ never auto-lock)', is_past(None) is False)

# ── 4. A real trial-active company round-tripped through the DB ────────────────
print('\n[4] real trial-active company (trial_ends_at = created_at + 14d) is NOT locked')
with app.app_context():
    c = Company(name='Zaid Co', slug='zaid-co', plan='trial', status='trial',
                trial_ends_at=_now() + timedelta(days=14))
    db.session.add(c); db.session.commit()
    cid = c.id

with app.app_context():                       # fresh context → forces a DB read-back
    c = db.session.get(Company, cid)
    te = c.trial_ends_at
    print(f'      re-fetched trial_ends_at = {te!r}  (tzinfo={te.tzinfo})')
    # The comparison must not throw regardless of naive/aware storage:
    threw = False
    try:
        active = not is_past(te)
    except TypeError:
        threw = True; active = False
    check('comparison did NOT throw on the round-tripped value', not threw)
    check('trial-active company is correctly NOT locked (is_past False)', is_past(te) is False)
    check('its NULL grace_ends_at is NOT past (never auto-lock)', is_past(c.grace_ends_at) is False)

print('\n' + '═' * 70)
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(1 if _FAIL else 0)
