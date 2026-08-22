"""Phase 1B-2 optional-before-migration, mandatory-after-migration auditing."""
import json

from app import db
from app.models import AuditLog
from app.tenancy import phase_1b_2_schema_status


def record_audit(*, company_id, actor_user_id, action_type, project_id=None,
                 previous_values=None, new_values=None):
    """Stage an audit row in the caller's transaction when the schema exists."""
    if not phase_1b_2_schema_status()['ready']:
        return None
    row = AuditLog(
        company_id=company_id,
        project_id=project_id,
        actor_user_id=actor_user_id,
        action_type=action_type,
        previous_values=(json.dumps(previous_values, ensure_ascii=False, sort_keys=True)
                         if previous_values is not None else None),
        new_values=(json.dumps(new_values, ensure_ascii=False, sort_keys=True)
                    if new_values is not None else None),
    )
    db.session.add(row)
    return row
