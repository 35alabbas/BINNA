#!/usr/bin/env python3
"""
BINNA — Phase 3 R2 connectivity check (READ-ONLY).

Confirms the Cloudflare R2 credentials actually work end-to-end before any upload
code is written. Does TWO read-only calls: head_bucket (auth + bucket exists) and
list_objects_v2 (MaxKeys=5). Writes nothing.

Reads R2_* straight from the environment (not app.config) so it can run anywhere
the env vars are set — notably the Render web service shell:

    pip install boto3 -q && python test_r2_connectivity.py

Exit 0 = credentials valid and bucket reachable.
"""
import os
import sys

REQUIRED = ('R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_BUCKET', 'R2_ENDPOINT')
missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    print('R2 env vars not set in this environment:', ', '.join(missing))
    print('-> Run this in the Render web service shell (where R2_* are configured), '
          'not locally. Nothing tested.')
    sys.exit(2)

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    print("boto3 not installed here. In the Render shell run: pip install boto3 -q")
    sys.exit(2)

endpoint = os.environ['R2_ENDPOINT']
bucket   = os.environ['R2_BUCKET']
# Don't print secrets; show only non-sensitive context.
print(f'endpoint: {endpoint}')
print(f'bucket:   {bucket}')
print(f'account:  {os.environ.get("R2_ACCOUNT_ID", "(unset)")}')

client = boto3.client(
    's3',
    endpoint_url=endpoint,
    aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
    region_name='auto',
    config=Config(signature_version='s3v4'),
)

try:
    client.head_bucket(Bucket=bucket)
    print('head_bucket: OK (credentials valid, bucket reachable)')

    resp = client.list_objects_v2(Bucket=bucket, MaxKeys=5)
    keys = [o['Key'] for o in resp.get('Contents', [])]
    print(f'list_objects_v2: OK - {resp.get("KeyCount", 0)} object(s) (showing up to 5): {keys}')

    print('\nRESULT: R2 connectivity CONFIRMED. Safe to wire the upload path.')
    sys.exit(0)
except (ClientError, BotoCoreError) as e:
    print(f'\nRESULT: R2 connectivity FAILED - {type(e).__name__}: {e}')
    sys.exit(1)
