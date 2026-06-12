/**
 * BINNA API Client  —  shared across all module pages
 * Include with:  <script src="/static/js/binna-api.js"></script>
 */
'use strict';

const API_BASE = '/api/v1';

const BINNA = {

  // ── Session storage ────────────────────────────────────────────────────────
  getToken()  { return localStorage.getItem('binna_token'); },
  setToken(t) { localStorage.setItem('binna_token', t); },

  getUser() {
    try { return JSON.parse(localStorage.getItem('binna_user') || 'null'); }
    catch { return null; }
  },
  setUser(u) { localStorage.setItem('binna_user', JSON.stringify(u)); },

  /** The full project object that is currently "active". */
  getProject() {
    try { return JSON.parse(localStorage.getItem('binna_current_project') || 'null'); }
    catch { return null; }
  },
  setProject(p) { localStorage.setItem('binna_current_project', JSON.stringify(p)); },
  getProjectId() { const p = this.getProject(); return p ? p.id : null; },

  // ── Auth helpers ───────────────────────────────────────────────────────────
  logout() {
    localStorage.removeItem('binna_token');
    localStorage.removeItem('binna_user');
    localStorage.removeItem('binna_current_project');
    window.location.href = '/login';
  },

  requireAuth() {
    if (!this.getToken()) {
      window.location.href = '/login?next=' + encodeURIComponent(window.location.pathname);
      return false;
    }
    return true;
  },

  requireProject() {
    if (!this.requireAuth()) return false;
    if (!this.getProjectId()) {
      window.location.href = '/dashboard';
      return false;
    }
    return true;
  },

  // ── HTTP core ──────────────────────────────────────────────────────────────
  async request(method, path, body = null, isFormData = false) {
    const url = path.startsWith('http') ? path : API_BASE + path;

    const headers = { 'Authorization': 'Bearer ' + (this.getToken() || '') };
    if (!isFormData) headers['Content-Type'] = 'application/json';

    const opts = { method, headers };
    if (body !== null) opts.body = isFormData ? body : JSON.stringify(body);

    let res;
    try {
      res = await fetch(url, opts);
    } catch (e) {
      throw { error: 'Network error — is the BINNA server running?' };
    }

    if (res.status === 401) {
      this.logout();
      throw { error: 'Session expired — please log in again.' };
    }

    let data;
    try { data = await res.json(); }
    catch { data = {}; }

    if (!res.ok) {
      const err = (typeof data === 'object' && data !== null) ? data : { error: String(data) };
      throw { status: res.status, ...err };
    }

    return data;
  },

  // ── Convenience methods ────────────────────────────────────────────────────
  get(path)          { return this.request('GET',    path); },
  post(path, body)   { return this.request('POST',   path, body); },
  put(path, body)    { return this.request('PUT',    path, body); },
  patch(path, body)  { return this.request('PATCH',  path, body); },
  del(path)          { return this.request('DELETE', path); },
  upload(path, fd)   { return this.request('POST',   path, fd, true); },

  // ── Auth API calls ─────────────────────────────────────────────────────────
  async login(loginId, password) {
    const data = await this.post('/auth/login', { email: loginId, password });
    this.setToken(data.access_token);
    this.setUser(data.user);
    return data;
  },

  async register(username, email, password) {
    const data = await this.post('/auth/register', { username, email, password });
    this.setToken(data.access_token);
    this.setUser(data.user);
    return data;
  },

  async fetchMe() {
    const data = await this.get('/auth/me');
    this.setUser(data.user);
    return data.user;
  },

  // ── Project API calls ──────────────────────────────────────────────────────
  async fetchProjects()         { return this.get('/projects'); },
  async createProject(d)        { return this.post('/projects', d); },
  async updateProject(id, d)    { return this.put(`/projects/${id}`, d); },
  async deleteProject(id)       { return this.del(`/projects/${id}`); },
  async fetchProject(id)        { return this.get(`/projects/${id}`); },
  async fetchMembers(pid)       { return this.get(`/projects/${pid}/members`); },
  async addMember(pid, d)       { return this.post(`/projects/${pid}/members`, d); },
  async removeMember(pid, mid)  { return this.del(`/projects/${pid}/members/${mid}`); },
  async updateMemberRole(pid, mid, role) {
    return this.put(`/projects/${pid}/members/${mid}`, { role });
  },

  // ── Document Control API ──────────────────────────────────────────────────
  async fetchLetters(pid, params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/projects/${pid}/dc${qs ? '?' + qs : ''}`);
  },
  async createLetter(pid, d)        { return this.post(`/projects/${pid}/dc`, d); },
  async updateLetter(pid, lid, d)   { return this.put(`/projects/${pid}/dc/${lid}`, d); },
  async deleteLetter(pid, lid)      { return this.del(`/projects/${pid}/dc/${lid}`); },
  async getLetter(pid, lid)         { return this.get(`/projects/${pid}/dc/${lid}`); },
  async dcNextCode(pid, direction)  { return this.get(`/projects/${pid}/dc/next-code?direction=${direction}`); },
  async dcStats(pid)                { return this.get(`/projects/${pid}/dc/stats`); },

  // ── Submittals API (DWG / FIR / MIR / MS / RFI) ───────────────────────────
  async fetchSubmittals(pid, type, params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/projects/${pid}/submittals/${type}${qs ? '?' + qs : ''}`);
  },
  async createSubmittal(pid, type, d)       { return this.post(`/projects/${pid}/submittals/${type}`, d); },
  async updateSubmittal(pid, type, id, d)   { return this.put(`/projects/${pid}/submittals/${type}/${id}`, d); },
  async deleteSubmittal(pid, type, id)      { return this.del(`/projects/${pid}/submittals/${type}/${id}`); },
  async getSubmittal(pid, type, id)         { return this.get(`/projects/${pid}/submittals/${type}/${id}`); },
  async submittalsNextCode(pid, type, rev)  { return this.get(`/projects/${pid}/submittals/${type}/next-code?revision=${rev||'A'}`); },
  async submittalsStats(pid, type)          { return this.get(`/projects/${pid}/submittals/${type}/stats`); },

  // ── Daily Reports API ─────────────────────────────────────────────────────
  async fetchDRs(pid, params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/projects/${pid}/dr${qs ? '?' + qs : ''}`);
  },
  async createDR(pid, d)       { return this.post(`/projects/${pid}/dr`, d); },
  async updateDR(pid, id, d)   { return this.put(`/projects/${pid}/dr/${id}`, d); },
  async deleteDR(pid, id)      { return this.del(`/projects/${pid}/dr/${id}`); },
  async getDR(pid, id)         { return this.get(`/projects/${pid}/dr/${id}`); },
  async drNextCode(pid)        { return this.get(`/projects/${pid}/dr/next-code`); },
  async drStats(pid)           { return this.get(`/projects/${pid}/dr/stats`); },

  // ── Lab Tests API ─────────────────────────────────────────────────────────
  async fetchLBTs(pid, params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/projects/${pid}/lbt${qs ? '?' + qs : ''}`);
  },
  async createLBT(pid, d)           { return this.post(`/projects/${pid}/lbt`, d); },
  async updateLBT(pid, id, d)       { return this.put(`/projects/${pid}/lbt/${id}`, d); },
  async deleteLBT(pid, id)          { return this.del(`/projects/${pid}/lbt/${id}`); },
  async getLBT(pid, id)             { return this.get(`/projects/${pid}/lbt/${id}`); },
  async lbtNextCode(pid, direction) { return this.get(`/projects/${pid}/lbt/next-code?direction=${direction}`); },
  async lbtStats(pid)               { return this.get(`/projects/${pid}/lbt/stats`); },

  // ── Financial API ─────────────────────────────────────────────────────────
  async fetchFinancial(pid)   { return this.get(`/projects/${pid}/financial`); },
  async saveFinancial(pid, d) { return this.put(`/projects/${pid}/financial`, { data: d }); },
  async saveIncomeExpenses(pid, income, expenses, incomeCategories, expenseCategories, usdRate) {
    return this.put(`/projects/${pid}/financial/income`, {
      income, expenses, incomeCategories, expenseCategories, usdRate
    });
  },

  // ── Gantt API ─────────────────────────────────────────────────────────────
  async fetchGantt(pid)       { return this.get(`/projects/${pid}/gantt`); },
  async saveGantt(pid, tasks, stoppages) { return this.put(`/projects/${pid}/gantt`, stoppages === undefined ? { tasks } : { tasks, stoppages }); },

  // ── Subcontractor Module API (Phase 1) ────────────────────────────────────
  async fetchParties(pid)            { return this.get(`/projects/${pid}/parties`); },
  async createParty(pid, d)          { return this.post(`/projects/${pid}/parties`, d); },
  async updateParty(pid, id, d)      { return this.put(`/projects/${pid}/parties/${id}`, d); },
  async deleteParty(pid, id)         { return this.del(`/projects/${pid}/parties/${id}`); },
  async fetchSubcontracts(pid)       { return this.get(`/projects/${pid}/subcontracts`); },
  async createSubcontract(pid, d)    { return this.post(`/projects/${pid}/subcontracts`, d); },
  async getSubcontract(pid, id)      { return this.get(`/projects/${pid}/subcontracts/${id}`); },
  async updateSubcontract(pid, id, d){ return this.put(`/projects/${pid}/subcontracts/${id}`, d); },
  async deleteSubcontract(pid, id)   { return this.del(`/projects/${pid}/subcontracts/${id}`); },
  async subcontractsSummary(pid)     { return this.get(`/projects/${pid}/subcontracts/summary`); },

  // ── Global Parties Registry API ───────────────────────────────────────────
  async fetchGlobalParties(pid)        { return this.get(`/projects/${pid}/global-parties`); },
  async createGlobalParty(pid, d)      { return this.post(`/projects/${pid}/global-parties`, d); },
  async updateGlobalParty(pid, id, d)  { return this.put(`/projects/${pid}/global-parties/${id}`, d); },
  async deleteGlobalParty(pid, id)     { return this.del(`/projects/${pid}/global-parties/${id}`); },

  // ── Uploads API ───────────────────────────────────────────────────────────
  async uploadFile(pid, formData) { return this.upload(`/projects/${pid}/uploads`, formData); },

  // ── UI helpers ─────────────────────────────────────────────────────────────
  /** Inject the project badge text into elements with [data-proj-code] / [data-proj-name]. */
  injectProjectBadge() {
    const p = this.getProject();
    if (!p) return;
    document.querySelectorAll('[data-proj-code]').forEach(el => el.textContent = p.code);
    document.querySelectorAll('[data-proj-name]').forEach(el => el.textContent = p.name);
  },

  /** Format ISO date string → DD/MM/YYYY */
  fmtDate(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso.includes('T') ? iso : iso + 'T00:00:00');
      return String(d.getDate()).padStart(2, '0') + '/'
           + String(d.getMonth() + 1).padStart(2, '0') + '/'
           + d.getFullYear();
    } catch { return iso; }
  },

  /** Escape HTML special chars */
  esc(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  },

  /** Show a transient toast message */
  toast(msg, type = 'info', duration = 3000) {
    let container = document.getElementById('binna-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'binna-toast-container';
      container.style.cssText =
        'position:fixed;bottom:24px;right:24px;z-index:9999;display:flex;flex-direction:column;gap:8px';
      document.body.appendChild(container);
    }

    const colours = {
      success: { bg: '#ecfdf3', border: '#6ce9a6', text: '#027a48' },
      error:   { bg: '#fff1f0', border: '#fecdca', text: '#b42318' },
      info:    { bg: '#eff4ff', border: '#c7d7fd', text: '#1a56db' },
    };
    const c = colours[type] || colours.info;

    const toast = document.createElement('div');
    toast.style.cssText =
      `background:${c.bg};border:1px solid ${c.border};color:${c.text};`
      + 'padding:10px 16px;border-radius:8px;font-size:13px;font-family:Inter,sans-serif;'
      + 'box-shadow:0 4px 12px rgba(0,0,0,.1);max-width:320px;'
      + 'animation:binna-slide-in .2s ease';
    toast.textContent = msg;
    container.appendChild(toast);

    // Inject keyframe once
    if (!document.getElementById('binna-toast-style')) {
      const s = document.createElement('style');
      s.id = 'binna-toast-style';
      s.textContent = '@keyframes binna-slide-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}';
      document.head.appendChild(s);
    }

    setTimeout(() => toast.remove(), duration);
  },
};

// ── Team Members legend (localStorage per project) ────────────────────────────
BINNA.teamKey = function(pid) { return 'binna_team_' + pid; };
BINNA.getTeamMembers = function(pid) {
  try { return JSON.parse(localStorage.getItem(BINNA.teamKey(pid)) || '[]'); }
  catch { return []; }
};
BINNA.saveTeamMembers = function(pid, members) {
  localStorage.setItem(BINNA.teamKey(pid), JSON.stringify(members));
};

/** Render the compact team legend into #sidebar-team-legend / #sidebar-team-items. */
BINNA.renderSidebarTeam = function() {
  var wrapper  = document.getElementById('sidebar-team-legend');
  var container = document.getElementById('sidebar-team-items');
  if (!container) return;
  var pid = BINNA.getProjectId();
  if (!pid) { if (wrapper) wrapper.style.display = 'none'; return; }
  var members = BINNA.getTeamMembers(pid);
  if (!members.length) { if (wrapper) wrapper.style.display = 'none'; return; }
  if (wrapper) wrapper.style.display = 'block';
  container.innerHTML = members.map(function(m) {
    return '<div style="display:flex;align-items:center;gap:7px;margin-bottom:5px">'
      + '<span style="width:9px;height:9px;border-radius:2px;flex-shrink:0;display:inline-block;background:' + BINNA.esc(m.color) + ';box-shadow:0 0 0 1px rgba(0,0,0,.12)"></span>'
      + '<span style="font-size:11.5px;color:var(--text2,#344054);font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0">' + BINNA.esc(m.name) + '</span>'
      + '<span style="font-size:10px;color:var(--muted2,#98a2b3);flex-shrink:0;max-width:70px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + BINNA.esc(m.role) + '</span>'
      + '</div>';
  }).join('');
};

// ── Undo stack (session-only, max 50) ────────────────────────────────────────
BINNA._undoStack = [];
BINNA.undo = {
  push: function(fn) {
    BINNA._undoStack.push(fn);
    if (BINNA._undoStack.length > 50) BINNA._undoStack.shift();
  },
  pop: function() {
    var fn = BINNA._undoStack.pop();
    if (fn) { try { fn(); } catch(e) { BINNA.toast('Undo error: ' + (e.message || e), 'error'); } }
    else BINNA.toast('Nothing to undo', 'info', 2000);
  },
  clear: function() { BINNA._undoStack = []; },
};
BINNA._deleteSelectedFn = null;
BINNA.registerDeleteSelected = function(fn) { BINNA._deleteSelectedFn = fn; };

// ── Global keyboard shortcuts ─────────────────────────────────────────────────
document.addEventListener('keydown', function(e) {
  var tag = document.activeElement ? document.activeElement.tagName : '';
  var editing = (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT');
  if (e.ctrlKey && !e.shiftKey && !e.altKey && (e.key === 'z' || e.key === 'Z') && !editing) {
    e.preventDefault();
    BINNA.undo.pop();
  }
  if ((e.key === 'Delete' || e.key === 'Backspace') && !editing && BINNA._deleteSelectedFn) {
    e.preventDefault();
    BINNA._deleteSelectedFn();
  }
});

window.BINNA = BINNA;
