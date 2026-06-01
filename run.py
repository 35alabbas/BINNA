#!/usr/bin/env python3
"""
BINNA — Construction PM
Usage:  python run.py
"""
import os
import sys

# Ensure UTF-8 I/O on Windows (no-op on other platforms)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

from app import create_app, db

app = create_app(os.environ.get('FLASK_ENV', 'development'))

# Create tables on startup — runs for both gunicorn and direct python run.py
with app.app_context():
    db.create_all()


@app.cli.command('init-db')
def init_db():
    """Create all database tables."""
    db.create_all()
    print('[OK] Database tables created.')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print('-' * 50)
    print('  BINNA Construction PM')
    print(f'  http://localhost:{port}')
    print('-' * 50)
    app.run(debug=True, host='0.0.0.0', port=port)
