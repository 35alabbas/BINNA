"""
BINNA — SQLAlchemy models
Phase 1: Users, Projects, ProjectMembers
Phase 2: DCLetter
"""
from datetime import datetime, timezone

import bcrypt
from app import db


def _now():
    return datetime.now(timezone.utc)


# ── Company (tenant) ──────────────────────────────────────────────────────────
# Phase 1 multi-tenant root. One row per customer company. Every user and every
# data row belongs to exactly one company (via company_id). New table → built by
# db.create_all() (no _ensure_schema entry; that list is for new *columns*).

VALID_COMPANY_STATUSES = ('trial', 'active', 'grace', 'locked')


class Company(db.Model):
    __tablename__ = 'companies'

    id            = db.Column(db.Integer,     primary_key=True)
    name          = db.Column(db.String(200), nullable=False)
    slug          = db.Column(db.String(120), unique=True, nullable=False, index=True)
    plan          = db.Column(db.String(20),  nullable=False, default='trial')   # 'trial' until pricing tiers exist
    max_users     = db.Column(db.Integer,     nullable=False, default=999)        # 999 = effectively unlimited for now
    trial_ends_at = db.Column(db.DateTime)                                        # set to +14 days at signup (Phase 2)
    grace_ends_at = db.Column(db.DateTime)                                        # set to +7 days after trial (Phase 4)
    status        = db.Column(db.String(20),  nullable=False, default='trial')   # trial | active | grace | locked
    created_at    = db.Column(db.DateTime,    default=_now)

    def to_dict(self) -> dict:
        return {
            'id':            self.id,
            'name':          self.name,
            'slug':          self.slug,
            'plan':          self.plan,
            'max_users':     self.max_users,
            'trial_ends_at': self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            'grace_ends_at': self.grace_ends_at.isoformat() if self.grace_ends_at else None,
            'status':        self.status,
            'created_at':    self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Company {self.slug}>'


# ── User ──────────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20),  default='user')   # PLATFORM role: admin | user (admin = BINNA super-admin)
    is_active     = db.Column(db.Boolean,     default=True)
    created_at    = db.Column(db.DateTime,    default=_now)

    # ── Multi-tenant (Phase 1) ──────────────────────────────────────────────────
    # company_id: which tenant this user belongs to (nullable until Phase 2 wires
    # the signup→company flow). company_role: TENANT role, distinct from the
    # platform `role` above. email_verified/token: columns built now; the
    # verification *logic* is wired in Phase 2.
    company_id               = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    company_role             = db.Column(db.String(20), default='viewer')   # owner | admin | member | viewer
    email_verified           = db.Column(db.Boolean, nullable=False, default=False)
    email_verification_token = db.Column(db.String(255))

    company = db.relationship('Company', foreign_keys=[company_id])

    # back-ref from ProjectMember
    memberships   = db.relationship('ProjectMember', back_populates='user',
                                    lazy='dynamic')

    # ── Password ──────────────────────────────────────────────────────────────
    def set_password(self, password: str) -> None:
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        self.password_hash = hashed.decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(
            password.encode(),
            self.password_hash.encode()
        )

    # ── Serialise ─────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            'id':         self.id,
            'username':   self.username,
            'email':      self.email,
            'role':       self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<User {self.username}>'


# ── Project ───────────────────────────────────────────────────────────────────

class Project(db.Model):
    __tablename__ = 'projects'

    id          = db.Column(db.Integer,     primary_key=True)
    company_id  = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    code        = db.Column(db.String(20),  nullable=False)          # e.g. APS
    name        = db.Column(db.String(200), nullable=False)
    client      = db.Column(db.String(200))
    consultant  = db.Column(db.String(200))
    contractor  = db.Column(db.String(200))
    description = db.Column(db.Text)
    status      = db.Column(db.String(20),  default='active')        # active | on-hold | completed
    created_by  = db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=False)
    created_at  = db.Column(db.DateTime,    default=_now)
    updated_at  = db.Column(db.DateTime,    default=_now, onupdate=_now)

    # Relationships
    members     = db.relationship('ProjectMember', back_populates='project',
                                  cascade='all, delete-orphan', lazy='select')
    creator     = db.relationship('User', foreign_keys=[created_by])

    # ── Serialise ─────────────────────────────────────────────────────────────
    def to_dict(self, include_members: bool = False) -> dict:
        data = {
            'id':          self.id,
            'code':        self.code,
            'name':        self.name,
            'client':      self.client or '',
            'consultant':  self.consultant or '',
            'contractor':  self.contractor or '',
            'description': self.description or '',
            'status':      self.status,
            'created_by':  self.created_by,
            'created_at':  self.created_at.isoformat() if self.created_at  else None,
            'updated_at':  self.updated_at.isoformat() if self.updated_at  else None,
        }
        if include_members:
            data['members'] = [m.to_dict() for m in self.members]
        return data

    def __repr__(self):
        return f'<Project {self.code} — {self.name}>'


# ── ProjectMember ─────────────────────────────────────────────────────────────

_ROLE_ORDER = {'viewer': 0, 'member': 1, 'admin': 2, 'owner': 3}


class ProjectMember(db.Model):
    __tablename__ = 'project_members'

    id         = db.Column(db.Integer,  primary_key=True)
    company_id = db.Column(db.Integer,  db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id = db.Column(db.Integer,  db.ForeignKey('projects.id'), nullable=False)
    user_id    = db.Column(db.Integer,  db.ForeignKey('users.id'),    nullable=False)
    role       = db.Column(db.String(20), default='member')           # owner | admin | member | viewer
    joined_at  = db.Column(db.DateTime,  default=_now)

    # Relationships
    project    = db.relationship('Project',     back_populates='members')
    user       = db.relationship('User',        back_populates='memberships')

    __table_args__ = (
        db.UniqueConstraint('project_id', 'user_id', name='uq_project_member'),
    )

    @property
    def role_level(self) -> int:
        return _ROLE_ORDER.get(self.role, 0)

    def to_dict(self) -> dict:
        return {
            'id':         self.id,
            'project_id': self.project_id,
            'user_id':    self.user_id,
            'username':   self.user.username if self.user else None,
            'email':      self.user.email    if self.user else None,
            'role':       self.role,
            'joined_at':  self.joined_at.isoformat() if self.joined_at else None,
        }

    def __repr__(self):
        return f'<ProjectMember user={self.user_id} project={self.project_id} role={self.role}>'


# ── DCLetter ──────────────────────────────────────────────────────────────────

class DCLetter(db.Model):
    __tablename__ = 'dc_letters'

    id            = db.Column(db.Integer,     primary_key=True)
    company_id    = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id    = db.Column(db.Integer,     db.ForeignKey('projects.id'), nullable=False)
    code          = db.Column(db.String(60),  nullable=False)          # APS-LetterIN-001
    direction     = db.Column(db.String(10),  nullable=False)          # incoming | outgoing
    subject       = db.Column(db.String(500), nullable=False)
    from_party    = db.Column(db.String(200), nullable=False)          # "from" is reserved
    to_party      = db.Column(db.String(200), nullable=False)
    cc            = db.Column(db.String(500))                          # outgoing only
    letter_date   = db.Column(db.Date,        nullable=False)
    received_date = db.Column(db.Date)                                 # incoming only
    orig_no       = db.Column(db.String(100))                          # original letter ref
    status        = db.Column(db.String(30),  default='pending')
    # status options: pending | received | replied | for-reference | sent
    notes         = db.Column(db.Text)
    file_name     = db.Column(db.String(500))                          # attachment name (Phase 8 for actual upload)
    created_by    = db.Column(db.Integer,     db.ForeignKey('users.id'))
    created_at    = db.Column(db.DateTime,    default=_now)
    updated_at    = db.Column(db.DateTime,    default=_now, onupdate=_now)

    project = db.relationship('Project', backref=db.backref('dc_letters', lazy='dynamic',
                                                             cascade='all, delete-orphan'))
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            'id':            self.id,
            'project_id':    self.project_id,
            'code':          self.code,
            'direction':     self.direction,
            'subject':       self.subject,
            'from_party':    self.from_party,
            'to_party':      self.to_party,
            'cc':            self.cc or '',
            'letter_date':   self.letter_date.isoformat()   if self.letter_date   else None,
            'received_date': self.received_date.isoformat() if self.received_date else None,
            'orig_no':       self.orig_no  or '',
            'status':        self.status,
            'notes':         self.notes    or '',
            'file_name':     self.file_name or '',
            'created_by':    self.created_by,
            'created_at':    self.created_at.isoformat() if self.created_at else None,
            'updated_at':    self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<DCLetter {self.code}>'


# ── Archive ───────────────────────────────────────────────────────────────────

class Archive(db.Model):
    __tablename__ = 'archives'

    id              = db.Column(db.Integer,     primary_key=True)
    company_id      = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id      = db.Column(db.Integer,     db.ForeignKey('projects.id'), nullable=False)
    archive_number  = db.Column(db.String(60),  nullable=False)          # APS-ARC-001
    name            = db.Column(db.String(500), nullable=False)          # user-supplied
    date            = db.Column(db.Date,        nullable=False)          # auto-set to today
    file_attachment = db.Column(db.String(500))                          # UUID-prefixed stored filename
    created_by      = db.Column(db.Integer,     db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime,    default=_now)
    updated_at      = db.Column(db.DateTime,    default=_now, onupdate=_now)

    project = db.relationship('Project',
                              backref=db.backref('archives', lazy='dynamic',
                                                 cascade='all, delete-orphan'))
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            'id':              self.id,
            'project_id':      self.project_id,
            'archive_number':  self.archive_number,
            'name':            self.name,
            'date':            self.date.isoformat() if self.date else None,
            'file_attachment': self.file_attachment or '',
            'created_by':      self.created_by,
            'created_at':      self.created_at.isoformat() if self.created_at else None,
            'updated_at':      self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Archive {self.archive_number}>'


# ── Submittal ─────────────────────────────────────────────────────────────────

VALID_SUBMITTAL_TYPES   = frozenset({'dwg', 'fir', 'mir', 'ms', 'rfi'})
VALID_SUBMITTAL_STATUSES = ('pending', 'approved', 'notes', 'rejected', 'corrections')


class Submittal(db.Model):
    __tablename__ = 'submittals'

    id             = db.Column(db.Integer,     primary_key=True)
    company_id     = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id     = db.Column(db.Integer,     db.ForeignKey('projects.id'), nullable=False)
    module_type    = db.Column(db.String(10),  nullable=False)          # dwg | fir | mir | ms | rfi
    code           = db.Column(db.String(60),  nullable=False)          # TST-DWG-001-A
    doc_number     = db.Column(db.Integer,     nullable=False)          # numeric part of code
    revision       = db.Column(db.String(5),   default='A')             # A, B, C…
    title          = db.Column(db.String(500), nullable=False)
    description    = db.Column(db.Text)
    submittal_date = db.Column(db.Date,        nullable=False)
    location       = db.Column(db.String(200))
    engineer       = db.Column(db.String(200))
    related_refs   = db.Column(db.String(500))                          # related drawings / docs
    submitted_to   = db.Column(db.String(200))
    cc_party       = db.Column(db.String(200))
    notes          = db.Column(db.Text)
    status         = db.Column(db.String(30),  default='pending')
    # status: pending | approved | notes | rejected | corrections
    file_name      = db.Column(db.String(500))                          # submitted file (Phase 8 upload)
    # ── Response fields ───────────────────────────────────────────────────────
    response_status   = db.Column(db.String(30))
    response_date     = db.Column(db.Date)
    response_by       = db.Column(db.String(200))
    response_location = db.Column(db.String(200))
    response_notes    = db.Column(db.Text)
    response_file     = db.Column(db.String(500))
    # ─────────────────────────────────────────────────────────────────────────
    created_by     = db.Column(db.Integer,     db.ForeignKey('users.id'))
    created_at     = db.Column(db.DateTime,    default=_now)
    updated_at     = db.Column(db.DateTime,    default=_now, onupdate=_now)

    project = db.relationship('Project',
                              backref=db.backref('submittals', lazy='dynamic',
                                                 cascade='all, delete-orphan'))
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            'id':               self.id,
            'project_id':       self.project_id,
            'module_type':      self.module_type,
            'code':             self.code,
            'doc_number':       self.doc_number,
            'revision':         self.revision or 'A',
            'title':            self.title,
            'description':      self.description or '',
            'submittal_date':   self.submittal_date.isoformat()   if self.submittal_date else None,
            'location':         self.location    or '',
            'engineer':         self.engineer    or '',
            'related_refs':     self.related_refs or '',
            'submitted_to':     self.submitted_to or '',
            'cc_party':         self.cc_party    or '',
            'notes':            self.notes       or '',
            'status':           self.status,
            'file_name':        self.file_name   or '',
            'response_status':  self.response_status  or '',
            'response_date':    self.response_date.isoformat() if self.response_date else None,
            'response_by':      self.response_by      or '',
            'response_location':self.response_location or '',
            'response_notes':   self.response_notes   or '',
            'response_file':    self.response_file    or '',
            'created_by':       self.created_by,
            'created_at':       self.created_at.isoformat() if self.created_at else None,
            'updated_at':       self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Submittal {self.code}>'


# ── DailyReport ───────────────────────────────────────────────────────────────

class DailyReport(db.Model):
    __tablename__ = 'daily_reports'

    id            = db.Column(db.Integer,     primary_key=True)
    company_id    = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id    = db.Column(db.Integer,     db.ForeignKey('projects.id'), nullable=False)
    code          = db.Column(db.String(60),  nullable=False)          # APS-DR-001
    doc_number    = db.Column(db.Integer,     nullable=False)
    date          = db.Column(db.Date,        nullable=False)
    weather       = db.Column(db.String(50),  default='sunny')
    weather_notes = db.Column(db.String(500))
    engineers     = db.Column(db.Integer,     default=0)
    laborers      = db.Column(db.Integer,     default=0)
    technicians   = db.Column(db.Integer,     default=0)
    other_workers = db.Column(db.Integer,     default=0)
    works         = db.Column(db.Text)                                 # JSON array of strings
    visitors      = db.Column(db.Text)                                 # JSON array of {name, org}
    next_plan     = db.Column(db.Text)
    notes         = db.Column(db.Text)
    prepared_by   = db.Column(db.String(200))
    reviewed_by   = db.Column(db.String(200))
    created_by    = db.Column(db.Integer,     db.ForeignKey('users.id'))
    created_at    = db.Column(db.DateTime,    default=_now)
    updated_at    = db.Column(db.DateTime,    default=_now, onupdate=_now)

    project = db.relationship('Project',
                              backref=db.backref('daily_reports', lazy='dynamic',
                                                 cascade='all, delete-orphan'))
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self) -> dict:
        import json
        return {
            'id':            self.id,
            'project_id':    self.project_id,
            'code':          self.code,
            'doc_number':    self.doc_number,
            'date':          self.date.isoformat()    if self.date       else None,
            'weather':       self.weather   or 'sunny',
            'weather_notes': self.weather_notes or '',
            'engineers':     self.engineers     or 0,
            'laborers':      self.laborers      or 0,
            'technicians':   self.technicians   or 0,
            'other_workers': self.other_workers or 0,
            'works':         json.loads(self.works)    if self.works    else [],
            'visitors':      json.loads(self.visitors) if self.visitors else [],
            'next_plan':     self.next_plan  or '',
            'notes':         self.notes      or '',
            'prepared_by':   self.prepared_by or '',
            'reviewed_by':   self.reviewed_by or '',
            'created_by':    self.created_by,
            'created_at':    self.created_at.isoformat() if self.created_at else None,
            'updated_at':    self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<DailyReport {self.code}>'


# ── LabTest ───────────────────────────────────────────────────────────────────

VALID_LBT_RESULTS = ('pending', 'pass', 'fail')


class LabTest(db.Model):
    __tablename__ = 'lab_tests'

    id             = db.Column(db.Integer,     primary_key=True)
    company_id     = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id     = db.Column(db.Integer,     db.ForeignKey('projects.id'), nullable=False)
    code           = db.Column(db.String(60),  nullable=False)          # APS-LBTOUT-001
    doc_number     = db.Column(db.Integer,     nullable=False)
    direction      = db.Column(db.String(5),   nullable=False)          # out | in
    date           = db.Column(db.Date,        nullable=False)
    # LBTOUT (sent-sample) fields
    material       = db.Column(db.String(500))
    test_type      = db.Column(db.String(500))
    lab            = db.Column(db.String(200))                          # lab name (free text / mirrored from lab_party)
    lab_party_id   = db.Column(db.Integer,     db.ForeignKey('global_parties.id'), nullable=True)  # → GlobalParty(role='laboratory')
    location       = db.Column(db.String(200))
    sample_ref     = db.Column(db.String(100))
    qty            = db.Column(db.String(100))
    notes          = db.Column(db.Text)
    file_name      = db.Column(db.String(500))
    # LBTIN (result) fields
    related_out_id = db.Column(db.Integer,     db.ForeignKey('lab_tests.id'), nullable=True)
    result         = db.Column(db.String(20),  default='pending')       # pending | pass | fail
    req_val        = db.Column(db.String(100))
    act_val        = db.Column(db.String(100))
    unit           = db.Column(db.String(50))
    result_notes   = db.Column(db.Text)
    result_file    = db.Column(db.String(500))
    # Meta
    created_by     = db.Column(db.Integer,     db.ForeignKey('users.id'))
    created_at     = db.Column(db.DateTime,    default=_now)
    updated_at     = db.Column(db.DateTime,    default=_now, onupdate=_now)

    project = db.relationship('Project',
                              backref=db.backref('lab_tests', lazy='dynamic',
                                                 cascade='all, delete-orphan'))
    creator = db.relationship('User', foreign_keys=[created_by])

    def to_dict(self) -> dict:
        return {
            'id':             self.id,
            'project_id':     self.project_id,
            'code':           self.code,
            'doc_number':     self.doc_number,
            'direction':      self.direction,
            'date':           self.date.isoformat() if self.date else None,
            'material':       self.material    or '',
            'test_type':      self.test_type   or '',
            'lab':            self.lab         or '',
            'lab_party_id':   self.lab_party_id,
            'location':       self.location    or '',
            'sample_ref':     self.sample_ref  or '',
            'qty':            self.qty         or '',
            'notes':          self.notes       or '',
            'file_name':      self.file_name   or '',
            'related_out_id': self.related_out_id,
            'result':         self.result      or 'pending',
            'req_val':        self.req_val     or '',
            'act_val':        self.act_val     or '',
            'unit':           self.unit        or '',
            'result_notes':   self.result_notes or '',
            'result_file':    self.result_file  or '',
            'created_by':     self.created_by,
            'created_at':     self.created_at.isoformat() if self.created_at else None,
            'updated_at':     self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<LabTest {self.code}>'


# ── FinancialData ─────────────────────────────────────────────────────────────

class FinancialData(db.Model):
    __tablename__ = 'financial_data'

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, unique=True)
    data       = db.Column(db.Text)                                    # JSON blob
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    project = db.relationship('Project',
                              backref=db.backref('financial_data', uselist=False,
                                                 cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<FinancialData project={self.project_id}>'


# ── GanttData ─────────────────────────────────────────────────────────────────

class GanttData(db.Model):
    __tablename__ = 'gantt_data'

    id         = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, unique=True)
    tasks      = db.Column(db.Text)                                    # JSON array
    stoppages  = db.Column(db.Text, default='[]')                      # JSON array of project-level stoppage periods
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now)

    project = db.relationship('Project',
                              backref=db.backref('gantt_data', uselist=False,
                                                 cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<GanttData project={self.project_id}>'


# ── Subcontractor Module (Phase 1) ────────────────────────────────────────────
# Two NEW tables only — created by db.create_all() on deploy (no _ensure_schema
# entry needed; that list is for new columns on EXISTING tables). Money direction
# here is PAYABLE (money the user owes subcontractors/suppliers).

VALID_PARTY_ROLES = ('main_contractor', 'consultant', 'client', 'subcontractor', 'supplier')
VALID_SUBCONTRACT_KINDS = ('lump_sum', 'milestone', 'monthly', 'custom', 'open_supply')


class Party(db.Model):
    """Company / entity directory — one row per company per project."""
    __tablename__ = 'parties'

    id           = db.Column(db.Integer,     primary_key=True)
    company_id   = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id   = db.Column(db.Integer,     db.ForeignKey('projects.id'), nullable=False, index=True)
    name         = db.Column(db.String(200), nullable=False)
    name_ar      = db.Column(db.String(200))
    role         = db.Column(db.String(30),  nullable=False, default='subcontractor')
    contact_name = db.Column(db.String(200))
    phone        = db.Column(db.String(120))
    email        = db.Column(db.String(200))
    notes        = db.Column(db.Text)
    is_default   = db.Column(db.Boolean,     default=False)   # True for the 3 seeded parties
    documents    = db.Column(db.Text,        default='[]')    # JSON: [{file, original, label, date}]
    created_at   = db.Column(db.DateTime,    default=_now)

    project      = db.relationship('Project',
                                   backref=db.backref('parties', lazy='dynamic',
                                                      cascade='all, delete-orphan'))
    subcontracts = db.relationship('Subcontract', back_populates='party',
                                   lazy='dynamic')

    def to_dict(self) -> dict:
        import json
        try:
            docs = json.loads(self.documents) if self.documents else []
        except (ValueError, TypeError):
            docs = []
        return {
            'id':           self.id,
            'project_id':   self.project_id,
            'name':         self.name,
            'name_ar':      self.name_ar or '',
            'role':         self.role,
            'contact_name': self.contact_name or '',
            'phone':        self.phone or '',
            'email':        self.email or '',
            'notes':        self.notes or '',
            'is_default':   bool(self.is_default),
            'documents':    docs,
            'created_at':   self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<Party {self.name} ({self.role})>'


class Subcontract(db.Model):
    """The agreement — many per party. Payment blob lives in `data` (JSON)."""
    __tablename__ = 'subcontracts'

    id          = db.Column(db.Integer,     primary_key=True)
    company_id  = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id  = db.Column(db.Integer,     db.ForeignKey('projects.id'), nullable=False, index=True)
    party_id    = db.Column(db.Integer,     db.ForeignKey('parties.id'),  nullable=False)
    ref         = db.Column(db.String(50))                  # {PROJECT_CODE}-SUB-001
    title       = db.Column(db.String(300))                 # scope description
    kind        = db.Column(db.String(20),  default='custom')
    status      = db.Column(db.String(20),  default='active')   # active | closed
    data        = db.Column(db.Text,        default='{}')   # JSON payment blob
    documents   = db.Column(db.Text,        default='[]')   # contract-level docs
    created_at  = db.Column(db.DateTime,    default=_now)

    project     = db.relationship('Project',
                                  backref=db.backref('subcontracts', lazy='dynamic',
                                                     cascade='all, delete-orphan'))
    party       = db.relationship('Party', back_populates='subcontracts')

    def to_meta_dict(self) -> dict:
        """Lightweight listing shape — no parsed blob."""
        return {
            'id':         self.id,
            'ref':        self.ref or '',
            'title':      self.title or '',
            'kind':       self.kind,
            'status':     self.status,
            'party':      {
                'id':   self.party.id   if self.party else self.party_id,
                'name': self.party.name if self.party else '',
                'role': self.party.role if self.party else '',
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def to_dict(self) -> dict:
        import json
        try:
            blob = json.loads(self.data) if self.data else {}
        except (ValueError, TypeError):
            blob = {}
        try:
            docs = json.loads(self.documents) if self.documents else []
        except (ValueError, TypeError):
            docs = []
        d = self.to_meta_dict()
        d['data'] = blob
        d['documents'] = docs
        return d

    def __repr__(self):
        return f'<Subcontract {self.ref}>'


# ── Global Parties Registry ───────────────────────────────────────────────────
# Flat per-project directory of every party involved in the project (client,
# consultant, contractor, subcontractor, supplier, other). Independent of the
# Subcontractor module's `Party` model (company directory for subcontract
# agreements, mounted at /parties) — different shape and its own API surface
# at /global-parties to avoid colliding with the existing /parties routes.

VALID_GLOBAL_PARTY_ROLES = ('client', 'consultant', 'contractor', 'subcontractor', 'supplier', 'laboratory', 'other')

# Roles a user can assign when creating a party via the registry UI/API.
# client/consultant/contractor are seeded once from the project record and
# are not user-creatable afterwards. 'laboratory' parties surface in the Lab
# Tests module's "Testing Lab" picker (never auto-seeded).
CREATABLE_GLOBAL_PARTY_ROLES = ('subcontractor', 'supplier', 'laboratory', 'other')

# Project fields that auto-seed a GlobalParty record (Global Parties Registry)
# when filled — (Project field name, GlobalParty.role). Used both at project
# creation and by the /global-parties/seed backfill endpoint.
SEED_GLOBAL_PARTY_ROLES = (
    ('client',     'client'),
    ('consultant', 'consultant'),
    ('contractor', 'contractor'),
)


class GlobalParty(db.Model):
    __tablename__ = 'global_parties'

    id            = db.Column(db.Integer,     primary_key=True)
    company_id    = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id    = db.Column(db.Integer,     db.ForeignKey('projects.id'), nullable=False, index=True)
    name_en       = db.Column(db.String(200), nullable=False)
    name_ar       = db.Column(db.String(200))
    role          = db.Column(db.String(20),  nullable=False, default='other')
    logo_filename = db.Column(db.String(500))              # stored filename (uploads API)
    notes         = db.Column(db.Text)
    is_seeded     = db.Column(db.Boolean,     nullable=False, default=False)  # Client/Consultant/Contractor — never deletable
    created_at    = db.Column(db.DateTime,    default=_now)

    project = db.relationship('Project',
                              backref=db.backref('global_parties', lazy='dynamic',
                                                 cascade='all, delete-orphan'))

    def to_dict(self) -> dict:
        return {
            'id':            self.id,
            'project_id':    self.project_id,
            'name_en':       self.name_en,
            'name_ar':       self.name_ar or '',
            'role':          self.role,
            'logo_filename': self.logo_filename or '',
            'logo_url':      f'/api/v1/uploads/{self.logo_filename}' if self.logo_filename else '',
            'notes':         self.notes or '',
            'is_seeded':     bool(self.is_seeded),
            'created_at':    self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<GlobalParty {self.name_en} ({self.role})>'


# ── Supply Agreement (Purchase Order) ─────────────────────────────────────────
# Supplier counterpart to Subcontract — deliberately far simpler. A PO header
# plus a flat payment log inside `data` (JSON). No retention, no cumulative
# درعة, no progress certificates: PO value → log payments → see balance.

class SupplyAgreement(db.Model):
    __tablename__ = 'supply_agreements'

    id              = db.Column(db.Integer,     primary_key=True)
    company_id      = db.Column(db.Integer,     db.ForeignKey('companies.id'), nullable=True, index=True)
    project_id      = db.Column(db.Integer,     db.ForeignKey('projects.id'), nullable=False, index=True)
    global_party_id = db.Column(db.Integer,     db.ForeignKey('global_parties.id'), nullable=True)
    ref             = db.Column(db.String(50))                 # {PROJECT_CODE}-PO-NNN
    description     = db.Column(db.String(255))
    po_value        = db.Column(db.Float,        default=0)
    currency        = db.Column(db.String(10),   default='IQD')
    date_issued     = db.Column(db.String(20))
    status          = db.Column(db.String(20),   default='open')   # open | partially_paid | closed
    data            = db.Column(db.Text,         default='{}')      # JSON: { payments: [], notes: '' }
    created_at      = db.Column(db.DateTime,     default=_now)

    project = db.relationship('Project',
                              backref=db.backref('supply_agreements', lazy='dynamic',
                                                 cascade='all, delete-orphan'))

    def to_dict(self) -> dict:
        import json
        try:
            blob = json.loads(self.data) if self.data else {}
        except (ValueError, TypeError):
            blob = {}
        if not isinstance(blob, dict):
            blob = {}
        return {
            'id':              self.id,
            'project_id':      self.project_id,
            'global_party_id': self.global_party_id,
            'ref':             self.ref or '',
            'description':     self.description or '',
            'po_value':        self.po_value or 0,
            'currency':        self.currency or 'IQD',
            'date_issued':     self.date_issued or '',
            'status':          self.status or 'open',
            'data':            blob,
            'created_at':      self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<SupplyAgreement {self.ref}>'
