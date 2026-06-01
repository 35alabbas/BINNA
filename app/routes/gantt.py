"""
BINNA — Gantt Data API  (Phase 8)
Routes: /api/v1/projects/<project_id>/gantt
Stores the full task list as a JSON blob per project.

Hierarchy: Milestone(0) → Group(1) → SubGroup(2) → Task(3 or any)
           Standalone tasks can be at level 0.

Recalculation (mirrors frontend recalc() in binna-gantt.html):
  Pass 1 (reverse order):
    All containers (milestone, group, subgroup) derive start / end / pct
    from their direct children (level == container.level + 1).
    Processing in reverse ensures nested containers resolve before parents.
    Tasks (type='task') are leaf nodes — they are never recalculated here.
"""
import json
from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models import GanttData, Project, ProjectMember

gantt_bp = Blueprint('gantt', __name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _check_access(project_id, user_id):
    proj = Project.query.get(project_id)
    if not proj:
        return None
    mem = ProjectMember.query.filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    return proj if mem else None


def _parse_date(s):
    """Parse a YYYY-MM-DD string → datetime.  Returns None on failure."""
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], '%Y-%m-%d')
    except (ValueError, TypeError):
        return None


def _fmt_date(d):
    """Format datetime → YYYY-MM-DD string."""
    return d.strftime('%Y-%m-%d') if d else None


def _task_dur(t):
    """Duration in days (minimum 1)."""
    s = _parse_date(t.get('start'))
    e = _parse_date(t.get('end') or t.get('start'))
    if s and e:
        return max(1, (e - s).days + 1)
    return 1


def _recalc_tasks(tasks):
    """
    Server-side recalculation — mirrors JS recalc() in binna-gantt.html.

    Pass 1 (reverse): containers (group/subgroup/milestone) derive
      start/end/pct from direct children.

    Pass 2 (forward, iterated): every task with predecessors is snapped to
      start exactly at max(pred_end + 1 + lag).  Iterates until stable so
      chains A→B→C propagate fully.
    """
    if not tasks:
        return tasks

    task_map = {t['id']: t for t in tasks if t.get('id')}

    def _pass1():
        for gi in range(len(tasks) - 1, -1, -1):
            g = tasks[gi]
            if g.get('type') == 'task':
                continue
            gL = g.get('level') or 0
            children = []
            for ci in range(gi + 1, len(tasks)):
                cL = tasks[ci].get('level') or 0
                if cL <= gL:
                    break
                if cL == gL + 1:
                    children.append(tasks[ci])
            if not children:
                continue
            starts = [_parse_date(c.get('start')) for c in children]
            ends   = [_parse_date(c.get('end') or c.get('start')) for c in children]
            starts = [d for d in starts if d]
            ends   = [d for d in ends   if d]
            if starts:
                g['start'] = _fmt_date(min(starts))
            if ends:
                g['end']   = _fmt_date(max(ends))
            total_dur = sum(_task_dur(c) for c in children)
            done_dur  = sum(_task_dur(c) * (c.get('pct') or 0) / 100.0 for c in children)
            g['pct']  = round(done_dur / total_dur * 100) if total_dur > 0 else 0

    _pass1()

    # Pass 2: snap predecessor-driven tasks to exact scheduled start
    changed = True
    guard   = 0
    while changed and guard < 30:
        changed = False
        guard  += 1
        for t in tasks:
            preds = t.get('preds') or []
            if not preds:
                continue
            min_start = None
            for p in preds:
                src = task_map.get(p.get('id'))
                if not src:
                    continue
                src_end = _parse_date(src.get('end') or src.get('start'))
                if not src_end:
                    continue
                lag  = int(p.get('lag') or 0)
                cand = src_end + timedelta(days=1 + lag)
                if min_start is None or cand > min_start:
                    min_start = cand
            if min_start is None:
                continue
            iso_min = _fmt_date(min_start)
            cur_start = _parse_date(t.get('start'))
            if not cur_start or min_start > cur_start:
                old_end  = _parse_date(t.get('end') or t.get('start'))
                old_start = _parse_date(t.get('start'))
                duration = max(1, (old_end - old_start).days + 1) if old_end and old_start else 1
                t['start'] = iso_min
                t['end']   = _fmt_date(min_start + timedelta(days=duration - 1))
                changed = True
        if changed:
            _pass1()

    return tasks


# ── routes ────────────────────────────────────────────────────────────────────

@gantt_bp.route('', methods=['GET'])
@jwt_required()
def get_gantt(project_id):
    uid = int(get_jwt_identity())
    proj = _check_access(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    gd = GanttData.query.filter_by(project_id=project_id).first()
    if not gd or not gd.tasks:
        return jsonify({'tasks': []}), 200

    try:
        tasks = json.loads(gd.tasks)
    except (ValueError, TypeError):
        tasks = []

    return jsonify({'tasks': tasks}), 200


@gantt_bp.route('', methods=['PUT'])
@jwt_required()
def save_gantt(project_id):
    uid = int(get_jwt_identity())
    proj = _check_access(project_id, uid)
    if not proj:
        return jsonify({'error': 'Project not found or access denied'}), 404

    body = request.get_json(silent=True) or {}
    tasks = body.get('tasks', [])
    if not isinstance(tasks, list):
        tasks = []

    # Server-side recalculation: groups from children, milestones from preds
    tasks = _recalc_tasks(tasks)

    gd = GanttData.query.filter_by(project_id=project_id).first()
    if not gd:
        gd = GanttData(project_id=project_id, updated_by=uid)
        db.session.add(gd)

    gd.tasks      = json.dumps(tasks, ensure_ascii=False)
    gd.updated_by = uid
    gd.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True, 'count': len(tasks)}), 200
