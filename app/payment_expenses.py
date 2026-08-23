"""Transactional synchronization from payable operational records to cash expenses."""
import json
import uuid

from sqlalchemy import inspect

from app import db
from app.audit import record_audit
from app.models import FinancialData, PaymentExpenseLink


SUBCONTRACT_CATEGORY_ID = 'system-subcontractors'
SUPPLIER_CATEGORY_ID = 'system-suppliers'


def payment_expense_schema_ready():
    return 'payment_expense_links' in inspect(db.engine).get_table_names()


def _load_financial(project_id, company_id, actor_user_id):
    row = FinancialData.query.filter_by(project_id=project_id).first()
    if not row:
        row = FinancialData(company_id=company_id, project_id=project_id,
                            updated_by=actor_user_id, data='{}')
        db.session.add(row)
    try:
        payload = json.loads(row.data) if row.data else {}
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault('income', [])
    payload.setdefault('expenses', [])
    payload.setdefault('incomeCategories', [])
    payload.setdefault('expenseCategories', [])
    return row, payload


def ensure_system_category(payload, category_id, default_name):
    categories = payload.setdefault('expenseCategories', [])
    category = next((c for c in categories if isinstance(c, dict) and c.get('id') == category_id), None)
    if category is None:
        category = {'id': category_id, 'name': default_name,
                    'archived': False, 'system_required': True}
        categories.append(category)
    else:
        category.setdefault('name', default_name)
        category['archived'] = False
        category['system_required'] = True
    return category


def _payment_map(payments):
    return {str(p.get('id')): p for p in payments if isinstance(p, dict) and p.get('id')}


def _positive_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def normalize_payment_ids(payments):
    for payment in payments:
        if isinstance(payment, dict) and not payment.get('id'):
            payment['id'] = str(uuid.uuid4())
    return payments


def sync_paid_payment_log(*, project, actor_user_id, source_type,
                          agreement_id, party_name, currency,
                          old_payments, new_payments, category_id, category_name):
    """Sync only new payment identities; unchanged historical rows are never backfilled."""
    if not payment_expense_schema_ready():
        return {'ready': False, 'created': 0, 'reversed': 0}

    old_by_id = _payment_map(old_payments)
    new_by_id = _payment_map(new_payments)
    financial_row, payload = _load_financial(project.id, project.company_id, actor_user_id)
    ensure_system_category(payload, category_id, category_name)
    expenses = payload['expenses']
    created = reversed_count = 0

    for payment_id, payment in new_by_id.items():
        amount = _positive_number(payment.get('amount'))
        if not amount:
            continue
        active = (PaymentExpenseLink.query.filter_by(
            project_id=project.id, source_type=source_type,
            source_agreement_id=agreement_id, source_payment_uuid=payment_id,
            status='active').order_by(PaymentExpenseLink.version.desc()).first())
        if active:
            rate = _exchange_rate(currency, payment)
            previous = {'amount': active.amount, 'currency': active.currency,
                        'exchange_rate': active.exchange_rate,
                        'payment_date': active.payment_date}
            entry = next((e for e in expenses if isinstance(e, dict) and
                          e.get('id') == active.expense_entry_id), None)
            if entry:
                entry.update(amount=amount, rate=rate, date=payment.get('date') or '', cur=currency)
            active.amount = amount
            active.exchange_rate = rate
            active.amount_iqd = amount * rate
            active.payment_date = payment.get('date') or ''
            current = {'amount': amount, 'currency': currency,
                       'exchange_rate': rate, 'payment_date': payment.get('date') or ''}
            if previous != current:
                record_audit(company_id=project.company_id, project_id=project.id,
                             actor_user_id=actor_user_id,
                             action_type='payment_expense_updated',
                             previous_values=previous, new_values=current)
            continue
        if payment_id in old_by_id:
            continue
        rate = _exchange_rate(currency, payment)
        previous_version = (PaymentExpenseLink.query.filter_by(
            project_id=project.id, source_type=source_type,
            source_agreement_id=agreement_id, source_payment_uuid=payment_id,
        ).order_by(PaymentExpenseLink.version.desc()).first())
        version = (previous_version.version + 1) if previous_version else 1
        expense_id = 'linked-expense-' + str(uuid.uuid4())
        link = PaymentExpenseLink(
            company_id=project.company_id, project_id=project.id,
            source_type=source_type, source_agreement_id=agreement_id,
            source_payment_uuid=payment_id, version=version,
            expense_entry_id=expense_id, status='active', amount=amount,
            currency=currency, exchange_rate=rate, amount_iqd=amount * rate,
            payment_date=payment.get('date') or '', created_by=actor_user_id,
        )
        db.session.add(link)
        expenses.append({
            'id': expense_id, 'desc': f'{party_name} payment', 'cat': category_id,
            'date': payment.get('date') or '', 'cur': currency,
            'amount': amount, 'rate': rate, 'system_generated': True,
            'source': {'type': source_type, 'agreement_id': agreement_id,
                       'payment_uuid': payment_id, 'version': version},
        })
        created += 1
        record_audit(company_id=project.company_id, project_id=project.id,
                     actor_user_id=actor_user_id, action_type='payment_expense_created',
                     new_values={'source_type': source_type, 'agreement_id': agreement_id,
                                 'payment_uuid': payment_id, 'amount': amount,
                                 'currency': currency, 'exchange_rate': rate})

    for payment_id in set(old_by_id) - set(new_by_id):
        active = (PaymentExpenseLink.query.filter_by(
            project_id=project.id, source_type=source_type,
            source_agreement_id=agreement_id, source_payment_uuid=payment_id,
            status='active').order_by(PaymentExpenseLink.version.desc()).first())
        if not active:
            continue
        reversal_id = 'linked-reversal-' + str(uuid.uuid4())
        expenses.append({
            'id': reversal_id, 'desc': f'Reversal: {party_name} payment',
            'cat': category_id, 'date': active.payment_date or '', 'cur': active.currency,
            'amount': -active.amount, 'rate': active.exchange_rate,
            'system_generated': True, 'reversal': True,
            'source': {'type': source_type, 'agreement_id': agreement_id,
                       'payment_uuid': payment_id, 'version': active.version,
                       'reverses': active.expense_entry_id},
        })
        active.status = 'reversed'
        active.reversal_entry_id = reversal_id
        reversed_count += 1
        record_audit(company_id=project.company_id, project_id=project.id,
                     actor_user_id=actor_user_id, action_type='payment_expense_reversed',
                     previous_values={'source_type': source_type, 'agreement_id': agreement_id,
                                      'payment_uuid': payment_id, 'amount': active.amount,
                                      'currency': active.currency})

    financial_row.data = json.dumps(payload, ensure_ascii=False)
    financial_row.updated_by = actor_user_id
    return {'ready': True, 'created': created, 'reversed': reversed_count}


def _exchange_rate(currency, payment):
    if (currency or 'IQD').upper() == 'IQD':
        return 1.0
    rate = _positive_number(payment.get('exchangeRate'))
    if not rate:
        raise ValueError('exchange_rate_required')
    return rate


def has_active_payment_links(project_id, source_type, agreement_id):
    if not payment_expense_schema_ready():
        return False
    return PaymentExpenseLink.query.filter_by(
        project_id=project_id, source_type=source_type,
        source_agreement_id=agreement_id, status='active').first() is not None


def preserve_linked_expenses(existing, incoming):
    canonical = [e for e in existing if isinstance(e, dict) and e.get('system_generated')]
    manual = [e for e in incoming if isinstance(e, dict) and not e.get('system_generated') and not e.get('source')]
    return manual + canonical


def preserve_required_expense_categories(existing, incoming):
    """Keep payment-integration categories canonical across generic JSON saves."""
    incoming_categories = [dict(c) for c in incoming if isinstance(c, dict)]
    required = {
        str(c.get('id')): dict(c) for c in existing
        if isinstance(c, dict) and c.get('id') and c.get('system_required')
    }
    if not required:
        return incoming_categories
    preserved_ids = set()
    result = []
    for category in incoming_categories:
        category_id = str(category.get('id'))
        canonical = required.get(category_id)
        if canonical is not None:
            canonical['archived'] = False
            canonical['system_required'] = True
            result.append(canonical)
            preserved_ids.add(category_id)
        else:
            result.append(category)
    result.extend(category for category_id, category in required.items()
                  if category_id not in preserved_ids)
    return result
