#!/usr/bin/env python3
"""
Real-API Resend send test — confirms the Cloudflare 1010 block is cleared.

Uses the SAME urllib request path as app/email.py (with the new User-Agent),
hitting the live Resend API. Not a mock. Never prints the API key.

Usage (on the Render shell, where RESEND_API_KEY is set):
    python test_resend_send.py you@example.com

If no recipient is given it falls back to TEST_EMAIL_TO, then to
'delivered@resend.dev' (Resend's always-accepts test inbox).
"""
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = 'https://api.resend.com/emails'

api_key = os.environ.get('RESEND_API_KEY', '')
if not api_key:
    sys.exit('ABORT: RESEND_API_KEY is not set in this environment.')

mail_from = os.environ.get('MAIL_FROM', 'BINNA <onboarding@resend.dev>')
to = (sys.argv[1] if len(sys.argv) > 1
      else os.environ.get('TEST_EMAIL_TO', 'delivered@resend.dev'))

payload = json.dumps({
    'from':    mail_from,
    'to':      [to],
    'subject': 'BINNA Resend connectivity test',
    'html':    '<p>If you can read this, the Cloudflare 1010 block is cleared.</p>',
}).encode('utf-8')

req = urllib.request.Request(
    ENDPOINT,
    data=payload,
    headers={
        'Authorization': f'Bearer {api_key}',
        'Content-Type':  'application/json',
        'User-Agent':    'BINNA/1.0',
        'Accept':        'application/json',
    },
    method='POST',
)

print(f'POST {ENDPOINT}  from={mail_from!r}  to={to!r}')
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode('utf-8', 'replace')
        print(f'HTTP {resp.status}')
        print('RESPONSE:', body)
        print('\nRESULT: PASS — Resend accepted the request (Cloudflare block cleared).')
except urllib.error.HTTPError as e:
    body = e.read().decode('utf-8', 'replace') if e.fp else ''
    print(f'HTTP {e.code}')
    print('RESPONSE:', body)
    if e.code == 403 and '1010' in body:
        print('\nRESULT: FAIL — still Cloudflare 1010. User-Agent fix did not clear it.')
    else:
        print('\nRESULT: FAIL — non-1010 error (check key, from-domain, or payload above).')
    sys.exit(1)
except (urllib.error.URLError, OSError) as e:
    print('RESULT: FAIL — network/transport error:', e)
    sys.exit(1)
