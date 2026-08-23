'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const listeners = {};
const context = {
  window: null,
  CustomEvent: function CustomEvent(type, init) { this.type = type; this.detail = init.detail; },
  localStorage: {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { storage.set(key, String(value)); },
  },
  document: {
    readyState: 'loading',
    documentElement: { lang: 'en', dir: 'ltr' },
    addEventListener(type, handler) { listeners[type] = handler; },
    querySelectorAll() { return []; },
  },
  Intl,
  Date,
  console,
};
const storage = new Map();
context.window = context;
context.addEventListener = () => {};
context.dispatchEvent = () => {};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/management-i18n.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('static/js/operational-shell.js', 'utf8'), context);

const shell = context.BINNA_APP_SHELL;
assert.ok(shell, 'shared application shell should be exported');
assert.strictEqual(typeof shell.isModalBackdropTarget, 'function');
assert.strictEqual(shell.isModalBackdropTarget({
  matches(selector) { return selector.includes('.overlay'); },
  querySelector() { return null; },
}), true, 'overlay backdrops must be protected from click dismissal');
assert.strictEqual(shell.isModalBackdropTarget({
  matches() { return false; },
  querySelector() { return null; },
}), false, 'modal content must retain its normal click behavior');
assert.match(shell.legacyAccountSelector, /\.btn-logout-sm/,
             'DC legacy logout must be normalized with the other duplicate controls');
assert.match(shell.legacyAccountSelector, /#user-chip/,
             'legacy username chips must be normalized by the shared shell');
assert.strictEqual(typeof shell.operationalToggleHtml, 'function');
const operationalToggle = shell.operationalToggleHtml();
assert.match(operationalToggle, /class="op-sidebar-footer"/);
assert.match(operationalToggle, /data-binna-sidebar-toggle/);
assert.match(operationalToggle, /data-sidebar-toggle-label/);
assert.match(operationalToggle, /data-i18n="collapse"/);
assert.strictEqual(shell.stateKey, 'binna-sidebar-collapsed');
assert.strictEqual(shell.readCollapsed(context.localStorage), false);
shell.writeCollapsed(true, context.localStorage);
assert.strictEqual(storage.get('binna-sidebar-collapsed'), '1');
assert.strictEqual(shell.readCollapsed(context.localStorage), true);
shell.writeCollapsed(false, context.localStorage);
assert.strictEqual(storage.get('binna-sidebar-collapsed'), '0');
assert.deepStrictEqual(
  Object.assign({}, shell.togglePresentation(false, false)),
  { labelKey: 'collapse', icon: '⇤' },
);
assert.deepStrictEqual(
  Object.assign({}, shell.togglePresentation(true, false)),
  { labelKey: 'expand', icon: '⇥' },
);
assert.deepStrictEqual(
  Object.assign({}, shell.togglePresentation(false, true)),
  { labelKey: 'collapse', icon: '⇥' },
);
assert.deepStrictEqual(
  Object.assign({}, shell.togglePresentation(true, true)),
  { labelKey: 'expand', icon: '⇤' },
);
assert.strictEqual(shell.hasProjectContext('/company', { id: 42 }), false);
assert.strictEqual(shell.hasProjectContext('/dashboard', { id: 42 }), false);
assert.strictEqual(shell.hasProjectContext('/project/42', { id: 42 }), true);
assert.strictEqual(shell.hasProjectContext('/legacy/financial', { id: 42 }), true);
assert.strictEqual(shell.hasProjectContext('/legacy/financial', null), false);

const companyOnly = shell.visibleNavigation(null, false);
assert.deepStrictEqual(
  Array.from(companyOnly, section => section.id),
  ['workspace'],
  'company pages should expose Workspace navigation only',
);

const full = shell.visibleNavigation(null, true);
assert.deepStrictEqual(Array.from(full, section => section.id), ['workspace', 'project', 'consultant']);
assert.deepStrictEqual(
  Array.from(full[1].items, item => item.id),
  ['dc', 'dr', 'contract', 'accounts', 'gantt', 'subcontracts'],
  'project navigation should use the approved ordering',
);
assert.deepStrictEqual(
  Array.from(full[2].items, item => item.id),
  ['dwg', 'fir', 'mir', 'ms', 'rfi', 'lbt'],
  'consultant navigation should use the approved ordering',
);
assert.ok(!full.flatMap(section => Array.from(section.items)).some(item =>
  item.id === 'income' || item.id === 'expense'),
  'Income and Expenses must not be primary navigation entries',
);

const restricted = shell.visibleNavigation({
  dc: { view: true },
  financial: { view: false },
  gantt: { view: true },
  subcontracts: { view: false },
  submittals: { view: false },
  lbt: { view: true },
}, true);
assert.deepStrictEqual(
  Array.from(restricted[1].items, item => item.id),
  ['dc', 'dr', 'gantt'],
  'project modules should respect existing effective view permissions',
);
assert.deepStrictEqual(
  Array.from(restricted[2].items, item => item.id),
  ['lbt'],
  'consultant modules should respect existing effective view permissions',
);

const project = { id: 42, name: 'Project Alpha' };
const contextual = shell.visibleNavigation(null, true, project);
assert.strictEqual(contextual[0].items[2].href, '/project/42');
assert.strictEqual(typeof shell.projectBadgeSelectors, 'object');
assert.ok(shell.projectBadgeSelectors.code.includes('#proj-code'));
assert.ok(shell.projectBadgeSelectors.name.includes('#proj-name'));
assert.ok(shell.projectBadgeSelectors.code.includes('#proj-code-display'));
assert.ok(shell.projectBadgeSelectors.name.includes('#proj-name-display'));

const i18n = context.BINNA_I18N;
assert.strictEqual(i18n.messages.en.accounts, 'Accounts');
assert.strictEqual(i18n.messages.en.contractPayments, 'Contract & Payments');
assert.strictEqual(i18n.messages.en.drawingApprovals, 'Drawing Approvals (DWG)');
assert.strictEqual(i18n.messages.ar.accounts, 'الحسابات');
assert.strictEqual(i18n.messages.ar.contractPayments, 'العقد والسلف');
assert.strictEqual(i18n.messages.ar.drawingApprovals, 'مصادقة المخططات (DWG)');
assert.strictEqual(i18n.messages.ar.fieldInspectionRequest, 'طلب فحص موقعي (FIR)');
assert.strictEqual(i18n.messages.ar.materialInspectionRequest, 'طلب فحص مواد (MIR)');
assert.strictEqual(i18n.messages.ar.methodStatement, 'بيان تنفيذ العمل (MS)');
assert.strictEqual(i18n.messages.ar.laboratoryTests, 'الفحوصات المختبرية (LBT)');

i18n.setLang('ar');
assert.strictEqual(storage.get('binna_language'), 'ar');
assert.strictEqual(context.document.documentElement.dir, 'rtl');
i18n.setLang('en');
assert.strictEqual(context.document.documentElement.dir, 'ltr');

const menu = shell.userMenuHtml({ username: 'mohammed', email: 'me@example.test' });
assert.match(menu, /mohammed/);
assert.match(menu, /me@example\.test/);
assert.match(menu, /data-lang="ar"/);
assert.match(menu, /data-lang="en"/);
assert.match(menu, /binna-user-logout/);

const appShellCss = fs.readFileSync('static/css/app-shell.css', 'utf8');
const operationalShellCss = fs.readFileSync('static/css/operational-shell.css', 'utf8');
assert.match(appShellCss, /--app-sidebar:280px/);
assert.match(appShellCss, /--app-sidebar-compact:72px/);
assert.match(appShellCss, /\.app-nav\{[^}]*overflow-x:hidden/);
assert.match(appShellCss, /@media\(max-width:820px\)/);
assert.match(operationalShellCss, /\.sidebar\{[^}]*width:280px[^}]*overflow:hidden/);
assert.match(operationalShellCss, /sidebar-collapsed \.sidebar\{width:72px/);
assert.match(operationalShellCss, /\.op-nav-body\{[^}]*overflow-x:hidden[^}]*overflow-y:auto/);
assert.match(operationalShellCss, /@media\(max-width:820px\)/);

console.log('Application navigation: 55 passed, 0 failed');
