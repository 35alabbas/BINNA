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
from datetime import datetime, timezone

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


def _build_pred_map(tasks):
    """Map task_id → list of its predecessor task ids."""
    pred_map = {}
    for t in tasks:
        tid = t.get('id')
        if tid is None:
            continue
        pred_map[tid] = [
            p.get('id') for p in (t.get('preds') or [])
            if p.get('id') is not None
        ]
    return pred_map


def has_cycle(task_id, new_predecessor_id, pred_map):
    """
    Return True if making `new_predecessor_id` a predecessor of `task_id`
    would create a circular dependency.

    A task may never depend (directly or transitively) on itself.  Starting
    from the proposed predecessor we DFS down the *existing* predecessor
    chain; if the traversal ever reaches `task_id`, the new edge would close
    a loop and must be rejected.
    """
    if task_id == new_predecessor_id:
        return True
    stack = [new_predecessor_id]
    seen = set()
    while stack:
        cur = stack.pop()
        if cur == task_id:
            return True
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(pred_map.get(cur, []))
    return False


def _detect_cycle(tasks):
    """
    Validate the entire predecessor graph of a submitted task list.

    Performs an iterative DFS with white/grey/black colouring.  A grey node
    re-encountered while still on the active path means a back-edge — i.e. a
    circular dependency.  Returns True if any task participates in a cycle.

    This guards `_recalc_tasks` Pass 2 (which walks `preds`) from looping
    forever on a malformed chain such as A→B→C→A.
    """
    pred_map = _build_pred_map(tasks)
    WHITE, GREY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in pred_map}

    for root in pred_map:
        if color[root] != WHITE:
            continue
        # (node, iterator over its predecessors) frames on an explicit stack
        stack = [(root, iter(pred_map.get(root, [])))]
        color[root] = GREY
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if nxt not in color:          # dangling ref — ignore
                    continue
                if color[nxt] == GREY:        # back-edge → cycle
                    return True
                if color[nxt] == WHITE:
                    color[nxt] = GREY
                    stack.append((nxt, iter(pred_map.get(nxt, []))))
                    advanced = True
                    break
            if not advanced:
                color[node] = BLACK
                stack.pop()
    return False


def _recalc_tasks(tasks):
    """
    Server-side recalculation — container rollup only.

    Pass 1 (reverse): containers (group/subgroup/milestone) derive
      start/end/pct from direct children.

    Task (leaf) start/end dates are NEVER modified server-side; predecessor
    scheduling is the frontend's responsibility.

    NOTE (demo-data cleanup): because the old server-side Pass 2 scheduler
    was removed, tasks written directly via the API (e.g. demo/seed data)
    that never passed through the frontend recalc() will NOT have their
    predecessor dates normalized here. Such payloads must arrive already
    scheduled, or be loaded through the UI which runs recalc() before save.
    """
    if not tasks:
        return tasks

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

    # Circular dependency guard — abort before touching the DB or recalc().
    # A cyclic predecessor chain (e.g. linking a task to its own descendant)
    # would otherwise drive _recalc_tasks Pass 2 into an unstable loop.
    if _detect_cycle(tasks):
        return jsonify({
            'error': 'Circular dependency detected: '
                     'This action would create an invalid task chain.'
        }), 400

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
