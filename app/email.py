"""
BINNA — Transactional email (Resend)

Phase 2 account flows (verification / invite / password-reset) send mail through
Resend's HTTP API. We POST with the stdlib (urllib) to avoid pulling in a new
dependency — the payload is a tiny JSON body.

Behaviour when RESEND_API_KEY is unset (local dev / automated tests):
the message + any tokenised link is logged to stderr and the call reports
success. That keeps every account flow exercisable offline — the verification
token is visible in the logs (and the DB), so tests never need a live mailbox.
"""
import json
import sys
import urllib.error
import urllib.request

from flask import current_app

_RESEND_ENDPOINT = 'https://api.resend.com/emails'


def send_email(to: str, subject: str, html: str) -> bool:
    """Send one email. Returns True on success (or on dev-mode log fallback)."""
    api_key   = current_app.config.get('RESEND_API_KEY', '')
    mail_from = current_app.config.get('MAIL_FROM', 'BINNA <onboarding@resend.dev>')

    # ── Dev / test fallback ─────────────────────────────────────────────────────
    if not api_key:
        print(
            '\n' + '─' * 70 +
            f'\n[EMAIL — dev fallback, RESEND_API_KEY unset]'
            f'\n  To:      {to}'
            f'\n  Subject: {subject}'
            f'\n  Body:\n{html}\n' + '─' * 70,
            file=sys.stderr, flush=True,
        )
        return True

    payload = json.dumps({
        'from':    mail_from,
        'to':      [to],
        'subject': subject,
        'html':    html,
    }).encode('utf-8')

    req = urllib.request.Request(
        _RESEND_ENDPOINT,
        data=payload,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type':  'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return 200 <= resp.status < 300
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace') if e.fp else ''
        print(f'[EMAIL] Resend HTTPError {e.code}: {body}', file=sys.stderr, flush=True)
        return False
    except (urllib.error.URLError, OSError) as e:
        print(f'[EMAIL] Resend send failed: {e}', file=sys.stderr, flush=True)
        return False


# ── Templated helpers ───────────────────────────────────────────────────────────

def _wrap(title: str, body_html: str, button_label: str, button_url: str) -> str:
    return (
        f'<div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;'
        f'padding:24px;color:#1a1a1a">'
        f'<h2 style="margin:0 0 16px">{title}</h2>'
        f'{body_html}'
        f'<p style="margin:24px 0">'
        f'<a href="{button_url}" style="background:#1a1a1a;color:#fff;'
        f'text-decoration:none;padding:12px 22px;border-radius:6px;'
        f'display:inline-block">{button_label}</a></p>'
        f'<p style="font-size:12px;color:#666">Or paste this link into your browser:<br>'
        f'<a href="{button_url}">{button_url}</a></p>'
        f'</div>'
    )


def send_verification_email(to: str, link: str) -> bool:
    html = _wrap(
        'Confirm your BINNA account',
        '<p>Welcome to BINNA. Confirm your email to activate your workspace and '
        'start your 14-day trial.</p>',
        'Verify email', link,
    )
    return send_email(to, 'Verify your BINNA account', html)


def send_invite_email(to: str, company_name: str, inviter: str, link: str) -> bool:
    html = _wrap(
        f'You have been invited to {company_name}',
        f'<p>{inviter} invited you to join <b>{company_name}</b> on BINNA. '
        f'Set a password to accept the invitation — this link also verifies your '
        f'email.</p>',
        'Accept invitation', link,
    )
    return send_email(to, f'Join {company_name} on BINNA', html)


def send_password_reset_email(to: str, link: str) -> bool:
    html = _wrap(
        'Reset your BINNA password',
        '<p>We received a request to reset your password. This link is valid for '
        '1 hour. If you did not request this, you can safely ignore this email.</p>',
        'Reset password', link,
    )
    return send_email(to, 'Reset your BINNA password', html)
