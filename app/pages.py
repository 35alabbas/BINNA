"""
BINNA — Page routes (HTML views)
All authentication / authorisation is handled client-side (JWT in localStorage).
Flask simply serves the HTML; the JS on each page calls the API.
"""
import os
from flask import Blueprint, render_template, redirect, send_from_directory, abort, request

pages_bp = Blueprint('pages', __name__)

# Absolute path of the project root
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── SPA pages ─────────────────────────────────────────────────────────────────

@pages_bp.route('/')
def index():
    # Marketing landing page — the canonical file lives at the repo root
    # (with the split-screen auth modal), served directly like the legacy
    # module pages rather than via render_template (templates/ holds a stale copy).
    return send_from_directory(_ROOT, 'index.html')


@pages_bp.route('/login')
def login_page():
    # Retired as a standalone page (Phase 2 consolidation). The sign-in UI is now
    # the landing-page modal, auto-opened by '?signin=1'. Redirect there, carrying
    # over any query params (verified=1 / verified=already / reset=1) so the modal
    # can surface the right confirmation message.
    qs = request.query_string.decode()
    return redirect('/?signin=1' + ('&' + qs if qs else ''))


@pages_bp.route('/register')
def register_page():
    return render_template('register.html')


@pages_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')


@pages_bp.route('/project/<int:project_id>')
def project_home(project_id):
    return render_template('project.html')


# ── Phase 2 account-flow pages (self-contained, no template dependency) ─────────
# These are the landing pages for the tokenised links inside verification /
# invite / reset emails. Kept minimal and inline so the flows work end-to-end
# without waiting on the full SPA; they POST to the JSON API.

def _account_form_page(title, intro, fields_html, endpoint, success_redirect):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — BINNA</title>
<style>
 body{{font-family:Arial,Helvetica,sans-serif;background:#0f0f12;color:#eee;
   display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
 .card{{background:#1a1a20;padding:32px;border-radius:12px;width:340px;
   box-shadow:0 10px 40px rgba(0,0,0,.5)}}
 h1{{font-size:20px;margin:0 0 8px}} p.intro{{color:#aaa;font-size:14px;margin:0 0 20px}}
 input{{width:100%;box-sizing:border-box;padding:11px;margin:6px 0;border-radius:7px;
   border:1px solid #333;background:#0f0f12;color:#eee}}
 button{{width:100%;padding:12px;margin-top:12px;border:0;border-radius:7px;
   background:#c8a44d;color:#1a1a20;font-weight:bold;cursor:pointer}}
 .msg{{font-size:13px;margin-top:12px;min-height:18px}} .err{{color:#ff6b6b}} .ok{{color:#6bdc8a}}
</style></head><body><div class="card">
<h1>{title}</h1><p class="intro">{intro}</p>
<form id="f">{fields_html}<button type="submit">{title}</button></form>
<div class="msg" id="m"></div></div>
<script>
const p=new URLSearchParams(location.search);
document.getElementById('f').addEventListener('submit',async e=>{{
 e.preventDefault();const m=document.getElementById('m');m.className='msg';m.textContent='…';
 const body={{token:p.get('token')}};
 document.querySelectorAll('#f input').forEach(i=>{{if(i.name)body[i.name]=i.value;}});
 try{{
  const r=await fetch('{endpoint}',{{method:'POST',headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify(body)}});
  const d=await r.json();
  if(r.ok){{m.className='msg ok';m.textContent=d.message||'Success. Redirecting…';
    setTimeout(()=>location.href='{success_redirect}',1200);}}
  else{{m.className='msg err';m.textContent=d.error||'Something went wrong';}}
 }}catch(_){{m.className='msg err';m.textContent='Network error';}}
}});
</script></body></html>"""


@pages_bp.route('/reset-password')
def reset_password_page():
    return _account_form_page(
        'Reset password',
        'Choose a new password for your BINNA account.',
        '<input type="password" name="new_password" placeholder="New password" minlength="6" required>',
        '/api/v1/auth/reset-password', '/?signin=1&reset=1',
    )


@pages_bp.route('/accept-invite')
def accept_invite_page():
    return _account_form_page(
        'Accept invitation',
        'Set a password to join your team on BINNA.',
        '<input type="text" name="username" placeholder="Choose a username (optional)">'
        '<input type="password" name="password" placeholder="Password" minlength="6" required>',
        '/api/v1/company/accept-invite', '/dashboard',
    )


# ── Legacy module pages (original HTML files, still use localStorage) ─────────
# These will be replaced one-by-one in Phase 2+

_LEGACY_MODULES = frozenset({
    'contract', 'dc', 'dr', 'dwg', 'expense', 'financial', 'fir', 'gantt', 'income', 'lbt', 'mir', 'ms', 'rfi', 'sub'
})


# Some module keys map to a differently-named root HTML file. The Subcontractor
# card (key 'sub') now opens the Phase-1 module page binna-subcontract.html;
# existing sidebar links to /legacy/sub keep working unchanged.
_LEGACY_FILE_OVERRIDE = {'sub': 'subcontract'}


@pages_bp.route('/legacy/<module_name>')
def legacy_module(module_name):
    """Serve the original standalone HTML files directly from the project root."""
    if module_name not in _LEGACY_MODULES:
        abort(404)
    fname = _LEGACY_FILE_OVERRIDE.get(module_name, module_name)
    return send_from_directory(_ROOT, f'binna-{fname}.html')


# ── 404 handler ───────────────────────────────────────────────────────────────

@pages_bp.app_errorhandler(404)
def not_found(e):
    # Return JSON for API routes, HTML for everything else
    from flask import request, jsonify
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found'}), 404
    return render_template('404.html'), 404
