#!/usr/bin/env python3
"""Add the paid-payment expense identity bridge; dry-run is the default."""
import argparse
import os

from sqlalchemy import inspect, text

from app import create_app, db


TABLE = 'payment_expense_links'
INDEXES = (
    ('ix_payment_expense_links_company_id', 'company_id'),
    ('ix_payment_expense_links_project_id', 'project_id'),
)


def dry_run():
    present = TABLE in inspect(db.engine).get_table_names()
    print(('PRESENT: table ' if present else 'WOULD CREATE: table ') + TABLE)
    print(f'DRY RUN: {0 if present else 1} additive change(s) pending; nothing written.')


def apply_migration():
    from app.models import PaymentExpenseLink
    present = TABLE in inspect(db.engine).get_table_names()
    PaymentExpenseLink.__table__.create(bind=db.engine, checkfirst=True)
    with db.engine.begin() as connection:
        for name, column in INDEXES:
            connection.execute(text(f'CREATE INDEX IF NOT EXISTS {name} ON {TABLE} ({column})'))
    print(('PRESENT: table ' if present else 'CREATED: table ') + TABLE)
    print('APPLY COMPLETE: additive schema only; no existing rows rewritten.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--confirm-payment-expense-links', action='store_true')
    args = parser.parse_args()
    if args.apply and not args.confirm_payment_expense_links:
        parser.error('--apply requires --confirm-payment-expense-links')
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        apply_migration() if args.apply else dry_run()


if __name__ == '__main__':
    main()
