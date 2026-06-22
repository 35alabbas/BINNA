#!/usr/bin/env python3
"""
BINNA — Phase 4 admin panel + manual billing.

Covers the three new pieces of the lifecycle and admin surface:
  • billing.record_payment + paid_until auto-downgrade (active→grace→locked)
  • locked-sticky semantics (manual suspend holds)
  • /api/v1/admin/* routes, gated to the platform super-admin (role='admin')
  • mark-paid lifts an existing read-only lock end-to-end
  • /api/v1/company/storage usage indicator

Offline, throwaway SQLite. Exit 0 = all assertions hold.
"""
import io, os, sys, tempfile
from datetime import timedelta

_TMP = os.path.join(tempfile.gettempdir(), 'binna_admin_test.db')
if os.path.exists(_TMP):
    os.remove(_TMP)
os.environ['DATABASE_URL'] = 'sqlite:///' + _TMP
os.environ['FLASK_ENV']    = 'development'
os.environ.pop('RESEND_API_KEY', None)
os.environ.pop('R2_ACCESS_KEY_ID', None)          # force local-disk storage fallback
os.environ['APP_BASE_URL'] = 'http://localhost:5000'

from app import create_app, db, billing                            # noqa: E402
from app.models import Company, User, Payment, _now, add_months     # noqa: E402

app = create_app('development')
import run                                                          # noqa: E402,F401
with app.app_context():
    db.create_all(); run._ensure_schema()
client = app.test_client()

_PASS = _FAIL = 0
def check(name, cond):
    global _PASS, _FAIL
    _PASS += bool(cond); _FAIL += (not cond)
    print(('  ok   ' if cond else '  FAIL ') + name)

_n = [0]
def make_company(status='trial', trial_off=None, grace_off=None, paid_off=None):
    _n[0] += 1
    with app.app_context():
        c = Company(
            name=f'C{_n[0]}', slug=f'c{_n[0]}', plan='trial', status=status,
            trial_ends_at=(_now() + timedelta(days=trial_off)) if trial_off is not None else None,
            grace_ends_at=(_now() + timedelta(days=grace_off)) if grace_off is not None else None,
            paid_until=(_now() + timedelta(days=paid_off)) if paid_off is not None else None,
        )
        db.session.add(c); db.session.commit()
        return c.id


print('═' * 70)
print('  PHASE 4 — ADMIN PANEL + MANUAL BILLING')
print('═' * 70)

# ── 1. add_months helper (dependency-free, day-clamping) ──────────────────────
print('\n[1] add_months()')
from datetime import datetime, timezone
check('Jan 15 + 1mo = Feb 15', add_months(datetime(2026, 1, 15), 1) == datetime(2026, 2, 15))
check('Jan 31 + 1mo clamps to Feb 28 (2026)', add_months(datetime(2026, 1, 31), 1) == datetime(2026, 2, 28))
check('Dec 10 + 2mo rolls year', add_months(datetime(2026, 12, 10), 2) == datetime(2027, 2, 10))
check('preserves tzinfo', add_months(datetime(2026, 1, 1, tzinfo=timezone.utc), 1).tzinfo is timezone.utc)

# ── 2. record_payment + paid_until auto-downgrade ─────────────────────────────
print('\n[2] record_payment + active→grace→locked auto-downgrade')
cid = make_company('locked', trial_off=-40, grace_off=-10)        # fully lapsed company
with app.app_context():
    c = db.session.get(Company, cid)
    p = billing.record_payment(c, amount_iqd=250000, method='zain_cash', months=1, recorded_by=None)
    check('record_payment -> status active', c.status == 'active')
    check('paid_until ≈ now + 1 month', abs((c.paid_until.replace(tzinfo=None) - add_months(_now().replace(tzinfo=None), 1)).total_seconds()) < 5)
    check('grace_ends_at reset to NULL on payment', c.grace_ends_at is None)
    check('Payment row persisted (amount + method)', p.amount_iqd == 250000 and p.method == 'zain_cash')
    check('compute: active while inside paid window', billing.compute_status(c) == 'active')

# simulate the paid month lapsing
with app.app_context():
    c = db.session.get(Company, cid)
    c.paid_until = _now() - timedelta(days=1); c.grace_ends_at = None; db.session.commit()
    check('compute: lapsed-paid (grace unstamped) -> grace', billing.compute_status(c) == 'grace')
    eff = billing.refresh_status(c)
    check('refresh stamps grace from paid_until, status -> grace', eff == 'grace' and c.grace_ends_at is not None)
    delta = c.grace_ends_at.replace(tzinfo=None) - (c.paid_until.replace(tzinfo=None) + timedelta(days=billing.GRACE_DAYS))
    check('grace_ends_at = paid_until + 7d', abs(delta.total_seconds()) < 2)

with app.app_context():
    c = db.session.get(Company, cid)
    c.paid_until = _now() - timedelta(days=30); c.grace_ends_at = _now() - timedelta(days=1); db.session.commit()
    check('compute: paid + grace both lapsed -> locked', billing.compute_status(c) == 'locked')

# ── 3. locked-sticky + manual-active-sticky ───────────────────────────────────
print('\n[3] sticky states')
cid_lk = make_company('locked', trial_off=5, grace_off=None)      # locked but trial in the FUTURE
with app.app_context():
    check('stored locked is sticky even with a future trial', billing.compute_status(db.session.get(Company, cid_lk)) == 'locked')
cid_ma = make_company('active', trial_off=-100, paid_off=None)    # manual active, no paid window
with app.app_context():
    check('manual active (paid_until NULL) stays active', billing.compute_status(db.session.get(Company, cid_ma)) == 'active')

# early-renewal stacking
cid_rn = make_company('active', paid_off=10)
with app.app_context():
    c = db.session.get(Company, cid_rn); before = c.paid_until.replace(tzinfo=None)
    billing.record_payment(c, amount_iqd=250000, method='qi_card', months=1, recorded_by=None)
    check('early renewal stacks months onto existing paid_until',
          abs((c.paid_until.replace(tzinfo=None) - add_months(before, 1)).total_seconds()) < 5)

# ── 4. admin API: auth gate + companies list ──────────────────────────────────
print('\n[4] admin API — gate + companies list')

def signup(username, email, company):
    r = client.post('/api/v1/auth/register', json={
        'username': username, 'email': email, 'password': 'password1', 'company_name': company})
    assert r.status_code == 201, r.get_json()
    with app.app_context():
        tok = User.query.filter_by(email=email).first().email_verification_token
    client.get(f'/api/v1/auth/verify/{tok}')
    rl = client.post('/api/v1/auth/login', json={'email': email, 'password': 'password1'})
    j = rl.get_json()
    return {'Authorization': 'Bearer ' + j['access_token']}, j['user']

hdr_admin, u_admin = signup('boss', 'boss@acme.test', 'Acme')     # FIRST signup → platform super-admin
hdr_user,  u_user  = signup('staff', 'staff@beta.test', 'Beta')   # platform role 'user'

check('[4a] first signup is platform admin (role=admin)', u_admin['role'] == 'admin')
check('[4b] second signup is platform user (role=user)', u_user['role'] == 'user')
check('[4c] non-admin BLOCKED from /admin/companies (403)', client.get('/api/v1/admin/companies', headers=hdr_user).status_code == 403)
check('[4d] unauthenticated BLOCKED from /admin/companies (401)', client.get('/api/v1/admin/companies').status_code == 401)

r = client.get('/api/v1/admin/companies', headers=hdr_admin)
check('[4e] admin lists companies (200)', r.status_code == 200)
companies = r.get_json()['companies']
names = {c['name'] for c in companies}
check('[4f] Acme + Beta both visible to admin', {'Acme', 'Beta'} <= names)
beta = next((c for c in companies if c['name'] == 'Beta'), None)
check('[4g] row carries owner_email + member_count', beta and beta['owner_email'] == 'staff@beta.test' and beta['member_count'] == 1)
beta_id = beta['id']

# ── 5. mark-paid: validation + effect + revenue ───────────────────────────────
print('\n[5] mark-paid + revenue tracker')
check('[5a] bad method rejected (400)',
      client.post(f'/api/v1/admin/companies/{beta_id}/mark-paid',
                  json={'amount_iqd': 250000, 'method': 'paypal'}, headers=hdr_admin).status_code == 400)
check('[5b] non-positive amount rejected (400)',
      client.post(f'/api/v1/admin/companies/{beta_id}/mark-paid',
                  json={'amount_iqd': 0, 'method': 'nbi'}, headers=hdr_admin).status_code == 400)
check('[5c] non-admin cannot mark-paid (403)',
      client.post(f'/api/v1/admin/companies/{beta_id}/mark-paid',
                  json={'amount_iqd': 250000, 'method': 'nbi'}, headers=hdr_user).status_code == 403)

# baseline first — section [2]/[3] unit calls already wrote Payment rows to this shared DB
rev0 = client.get('/api/v1/admin/revenue', headers=hdr_admin).get_json()
base_total = rev0['total_iqd']; base_count = rev0['count']; base_ah = rev0['by_method']['asia_hawala']

r = client.post(f'/api/v1/admin/companies/{beta_id}/mark-paid',
                json={'amount_iqd': 300000, 'method': 'asia_hawala', 'months': 3, 'note': 'Q3'}, headers=hdr_admin)
check('[5d] mark-paid succeeds (201)', r.status_code == 201)
jd = r.get_json()
check('[5e] company now active + paid_until set', jd['company']['status'] == 'active' and jd['company']['paid_until'])

rev = client.get('/api/v1/admin/revenue', headers=hdr_admin).get_json()
check('[5f] revenue total increases by the payment', rev['total_iqd'] - base_total == 300000)
check('[5g] by_method asia_hawala increases by 300000', rev['by_method']['asia_hawala'] - base_ah == 300000)
check('[5h] revenue log grows by exactly 1 row', rev['count'] - base_count == 1)

# ── 6. activate / suspend + end-to-end lock lift ──────────────────────────────
print('\n[6] activate / suspend + lock lift end-to-end')

def newproj(hdr, code):
    return client.post('/api/v1/projects', json={'code': code, 'name': code,
                       'client': 'C', 'consultant': 'K', 'contractor': 'T'}, headers=hdr)

# suspend Beta → read-only; its writes 403 with account_locked
client.post(f'/api/v1/admin/companies/{beta_id}/suspend', headers=hdr_admin)
blocked = newproj(hdr_user, 'PB1')
check('[6a] suspended company write BLOCKED (403)', blocked.status_code == 403)
check("[6b] block carries code='account_locked'", blocked.get_json().get('code') == 'account_locked')

# mark-paid lifts the lock
client.post(f'/api/v1/admin/companies/{beta_id}/mark-paid',
            json={'amount_iqd': 250000, 'method': 'zain_cash'}, headers=hdr_admin)
check('[6c] after mark-paid, previously-locked tenant CAN write (201)', newproj(hdr_user, 'PB2').status_code == 201)

# suspend again, then manual activate (sticky, no payment)
client.post(f'/api/v1/admin/companies/{beta_id}/suspend', headers=hdr_admin)
client.post(f'/api/v1/admin/companies/{beta_id}/activate', headers=hdr_admin)
check('[6d] manual activate lifts lock too (201)', newproj(hdr_user, 'PB3').status_code == 201)

# ── 7. storage usage indicator ────────────────────────────────────────────────
print('\n[7] /company/storage usage indicator')
proj = newproj(hdr_user, 'PST').get_json()
pid = proj.get('project', proj).get('id') if isinstance(proj, dict) else None
if pid is None:
    pid = proj['id'] if isinstance(proj, dict) and 'id' in proj else proj.get('project', {}).get('id')
blob = b'%PDF-1.4 hello binna storage test'
up = client.post(f'/api/v1/projects/{pid}/uploads',
                 data={'file': (io.BytesIO(blob), 'doc.pdf')},
                 content_type='multipart/form-data', headers=hdr_user)
check('[7a] file upload succeeds (201)', up.status_code == 201)
st = client.get('/api/v1/company/storage', headers=hdr_user).get_json()
check('[7b] used_bytes equals the uploaded byte count', st['used_bytes'] == len(blob))
check('[7c] file_count = 1', st['file_count'] == 1)
check('[7d] percent_used computed against quota', isinstance(st['percent_used'], (int, float)))

print('\n' + '═' * 70)
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(1 if _FAIL else 0)
