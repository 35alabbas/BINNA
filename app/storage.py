"""
BINNA — file storage backend (Phase 3).

Cloudflare R2 (S3-compatible) in production; local-disk fallback when the R2_*
config is unset (local dev / offline tests) — mirrors the email module's dev
fallback. Single chokepoint so every write path (the uploads endpoint + the DC
archive upload) and the serve route stay consistent: flip R2 on/off in one place.

R2 key layout: "<company_id>/<project_id>/<stored_name>" — tenant isolation in the
path, per BINNA_SAAS_PLAN Phase 3. The Upload row already carries company_id,
project_id and stored_name, so the key is reconstructable at serve time without a
schema change. Bytes live in R2; Postgres stores only the ownership record.
"""
import os
from flask import current_app, redirect, send_from_directory, abort

# Lazily-built boto3 client (one per process). Tests may inject a stub here.
_client = None

PRESIGN_TTL = 300  # seconds — short-lived presigned download URLs


def r2_enabled():
    """True only when all four R2 credentials/targets are configured."""
    cfg = current_app.config
    return bool(cfg.get('R2_ACCESS_KEY_ID') and cfg.get('R2_SECRET_ACCESS_KEY')
                and cfg.get('R2_BUCKET') and cfg.get('R2_ENDPOINT'))


def _client_or_build():
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config
        cfg = current_app.config
        _client = boto3.client(
            's3',
            endpoint_url=cfg['R2_ENDPOINT'],
            aws_access_key_id=cfg['R2_ACCESS_KEY_ID'],
            aws_secret_access_key=cfg['R2_SECRET_ACCESS_KEY'],
            region_name='auto',
            config=Config(signature_version='s3v4'),
        )
    return _client


def key_for(company_id, project_id, stored_name):
    return f"{company_id}/{project_id}/{stored_name}"


def save_file(f, company_id, project_id, stored_name):
    """Persist an uploaded Werkzeug FileStorage. R2 when enabled, else local disk."""
    if r2_enabled():
        _client_or_build().put_object(
            Bucket=current_app.config['R2_BUCKET'],
            Key=key_for(company_id, project_id, stored_name),
            Body=f.read(),
            ContentType=(f.mimetype or 'application/octet-stream'),
        )
        return
    folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    f.save(os.path.join(folder, stored_name))


def download_response(upload):
    """Deliver a stored file to an ALREADY-authorized caller (the route runs the
    tenancy gate first). R2: 302 redirect to a short-lived presigned GET URL.
    Disk: stream from UPLOAD_FOLDER."""
    if r2_enabled():
        url = _client_or_build().generate_presigned_url(
            'get_object',
            Params={'Bucket': current_app.config['R2_BUCKET'],
                    'Key': key_for(upload.company_id, upload.project_id, upload.stored_name)},
            ExpiresIn=PRESIGN_TTL,
        )
        return redirect(url)
    folder = current_app.config['UPLOAD_FOLDER']
    if not os.path.isfile(os.path.join(folder, upload.stored_name)):
        abort(404)
    return send_from_directory(folder, upload.stored_name, as_attachment=False)
