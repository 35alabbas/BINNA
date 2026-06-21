#!/usr/bin/env python3
"""
BINNA — Phase 3 R2 upload-path test (offline, STUBBED S3 client).

Forces R2 "enabled" with dummy creds and injects an in-memory fake client, so the
upload -> store -> serve path is exercised without touching the network. Verifies:

  1. Upload puts the object under key  <company_id>/<project_id>/<stored_name>
     with the exact bytes (tenant isolation lives in the key path, per the plan).
  2. Serve returns a 302 redirect to a presigned GET URL for that same key.
  3. Tenant isolation carries over to R2: company B cannot fetch company A's file
     (404 before any presign); an unauthenticated caller gets 401.

Exit 0 = all assertions hold.
"""
import io, os, sys, tempfile

_TMP = os.path.join(tempfile.gettempdir(), 'binna_r2_upload_test.db')
if os.path.exists(_TMP):
    os.remove(_TMP)
os.environ['DATABASE_URL'] = 'sqlite:///' + _TMP
os.environ['FLASK_ENV']    = 'development'
os.environ.pop('RESEND_API_KEY', None)
os.environ['APP_BASE_URL'] = 'http://localhost:5000'
# Make sure no real R2 creds leak in from the environment.
for _k in ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET', 'R2_ENDPOINT'):
    os.environ.pop(_k, None)

from app import create_app, db, storage                # noqa: E402
from app.models import User                            # noqa: E402

app = create_app('development')
# Turn R2 ON for this test and inject a stub client (bypasses boto3 entirely).
app.config.update(
    R2_ACCESS_KEY_ID='test-key',
    R2_SECRET_ACCESS_KEY='test-secret',
    R2_BUCKET='binna-files-test',
    R2_ENDPOINT='https://fake.r2.example',
)


class FakeR2:
    """Minimal in-memory stand-in for the boto3 S3 client."""
    def __init__(self):
        self.objects = {}          # (Bucket, Key) -> bytes
        self.presigned = []        # record of presign calls

    def put_object(self, Bucket, Key, Body, ContentType=None):
        self.objects[(Bucket, Key)] = Body if isinstance(Body, (bytes, bytearray)) else Body.read()
        return {'ETag': '"stub"'}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        self.presigned.append((op, Params['Bucket'], Params['Key'], ExpiresIn))
        return f"https://fake.r2.example/{Params['Bucket']}/{Params['Key']}?sig=stub&exp={ExpiresIn}"


fake = FakeR2()
storage._client = fake          # _client_or_build() returns this, never builds boto3

import run                                              # noqa: E402,F401
with app.app_context():
    db.create_all(); run._ensure_schema()
client = app.test_client()

_PASS = _FAIL = 0
def check(name, cond):
    global _PASS, _FAIL
    _PASS += bool(cond); _FAIL += (not cond)
    print(('  ok   ' if cond else '  FAIL ') + name)


def signup(username, email, pw, company):
    r = client.post('/api/v1/auth/register', json={
        'username': username, 'email': email, 'password': pw, 'company_name': company})
    assert r.status_code == 201, r.get_json()
    with app.app_context():
        tok = User.query.filter_by(email=email).first().email_verification_token
    client.get(f'/api/v1/auth/verify/{tok}')
    rl = client.post('/api/v1/auth/login', json={'email': email, 'password': pw})
    return {'Authorization': 'Bearer ' + rl.get_json()['access_token']}, rl.get_json()['user']['id']


def create_project(hdr, code, name):
    r = client.post('/api/v1/projects', json={'code': code, 'name': name,
                    'client': 'C', 'consultant': 'K', 'contractor': 'T'}, headers=hdr)
    assert r.status_code == 201, r.get_json()
    return r.get_json()['project']['id']


print('═' * 70)
print('  PHASE 3 — R2 UPLOAD PATH (stubbed S3)')
print('═' * 70)
print('  r2_enabled:', end=' ')
with app.app_context():
    print(storage.r2_enabled())

hdr_a, uid_a = signup('owner_a', 'a@aco.test', 'passwordA', 'Alpha Co')
hdr_b, uid_b = signup('owner_b', 'b@bco.test', 'passwordB', 'Beta Co')
pid_a = create_project(hdr_a, 'APA', 'Alpha Project')
with app.app_context():
    cid_a = User.query.get(uid_a).company_id

CONTENT = b'ALPHA SECRET PDF BYTES'

# ── 1. Upload → object lands in R2 under the company/project/name key ──────────
print('\n[1] upload stores object at company/project/stored_name with right bytes')
up = client.post(f'/api/v1/projects/{pid_a}/uploads',
                 data={'file': (io.BytesIO(CONTENT), 'alpha.pdf')},
                 content_type='multipart/form-data', headers=hdr_a)
check(f'[{up.status_code}] upload accepted (201)', up.status_code == 201)
stored = up.get_json().get('file_name')
expected_key = f'{cid_a}/{pid_a}/{stored}'
check('object written to exactly one key', len(fake.objects) == 1)
check(f'key is company/project/stored_name ({expected_key})',
      ('binna-files-test', expected_key) in fake.objects)
check('stored bytes match the uploaded bytes',
      fake.objects.get(('binna-files-test', expected_key)) == CONTENT)

# ── 2. Serve → 302 presigned URL for that key ─────────────────────────────────
print('\n[2] serve returns a 302 presigned URL for the key')
sv = client.get(f'/api/v1/uploads/{stored}', headers=hdr_a)
loc = sv.headers.get('Location', '')
check(f'[{sv.status_code}] owner serve is a 302 redirect', sv.status_code == 302)
check('redirect points at the presigned URL for the right key', expected_key in loc)
check('a presign was generated with a finite TTL',
      bool(fake.presigned) and fake.presigned[-1][3] == storage.PRESIGN_TTL)

# ── 3. Tenant isolation carries over to R2 ────────────────────────────────────
print('\n[3] isolation: company B cannot fetch company A file; unauth blocked')
n_presigns_before = len(fake.presigned)
svb = client.get(f'/api/v1/uploads/{stored}', headers=hdr_b)
check(f'[{svb.status_code}] company B fetch BLOCKED (404)', svb.status_code == 404)
check('no presigned URL generated for the cross-tenant attempt',
      len(fake.presigned) == n_presigns_before)
sv_anon = client.get(f'/api/v1/uploads/{stored}')
check(f'[{sv_anon.status_code}] unauthenticated fetch rejected (401)', sv_anon.status_code == 401)

print('\n' + '═' * 70)
print(f'  RESULT: {_PASS} passed, {_FAIL} failed')
print('═' * 70)
sys.exit(1 if _FAIL else 0)
