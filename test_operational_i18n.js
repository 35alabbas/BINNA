'use strict';
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const storage = new Map();
const events = [];
const context = {
  window: null,
  CustomEvent: function CustomEvent(type, init) { this.type = type; this.detail = init.detail; },
  localStorage: {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { storage.set(key, String(value)); },
  },
  document: {
    documentElement: { lang: 'en', dir: 'ltr' },
    addEventListener() {},
    querySelectorAll() { return []; },
  },
  addEventListener() {},
  dispatchEvent(event) { events.push(event); },
  Intl,
  Date,
  console,
};
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/management-i18n.js', 'utf8'), context);
vm.runInContext(fs.readFileSync('static/js/operational-i18n.js', 'utf8'), context);

const i18n = context.BINNA_I18N;
const operational = context.BINNA_OPERATIONAL_I18N;
assert.ok(i18n, 'BINNA_I18N should be available');
assert.ok(operational, 'shared operational localization should be available');
assert.strictEqual(operational.translatePhrase('New Field Inspection Request', true), 'طلب فحص موقعي جديد');
assert.strictEqual(operational.translatePhrase('Search by code, title or area...', true), 'البحث بالرمز أو العنوان أو المنطقة...');
assert.strictEqual(operational.translatePhrase('Approved with Notes', true), 'مصادق عليه مع ملاحظات');
assert.strictEqual(operational.translatePhrase('FIR', true), 'FIR');
assert.strictEqual(operational.translatePhrase('New Field Inspection Request', false), 'New Field Inspection Request');
assert.strictEqual(operational.translatePhrase('Contract & Payment', true), 'العقد والسلف');
assert.strictEqual(i18n.toArabicDigits('Project 123.45'), 'Project ١٢٣.٤٥');
assert.strictEqual(i18n.normalizeDigits('١٬٢٣٤٫٥٠'), '1,234.50');
assert.strictEqual(i18n.parseNumber('١٬٢٣٤٫٥٠'), 1234.5);
assert.strictEqual(i18n.parseNumber('1,234.50'), 1234.5);
assert.strictEqual(i18n.parseNumber('not a number'), null);

i18n.setLang('ar');
assert.strictEqual(storage.get('binna_language'), 'ar');
assert.strictEqual(context.document.documentElement.dir, 'rtl');
assert.match(i18n.formatNumber(1250.5), /[١٢٥٠]/);
assert.doesNotMatch(i18n.formatNumber(1250.5), /[0-9]/);
assert.match(i18n.formatDate('2026-08-22'), /[٢٠٢٦]/);
assert.match(i18n.formatMoney(1250.5, 'IQD'), /IQD/);
assert.doesNotMatch(i18n.formatMoney(1250.5, 'IQD'), /[0-9]/);
assert.match(i18n.formatPercent(42.5), /٤٢/);
assert.match(i18n.formatDuration(15), /١٥/);
assert.strictEqual(i18n.canonicalNumber('١٬٢٣٤٫٥٠'), '1234.5');

i18n.setLang('en');
assert.strictEqual(context.document.documentElement.dir, 'ltr');
assert.match(i18n.formatNumber(1250.5), /[0-9]/);
assert.doesNotMatch(i18n.formatNumber(1250.5), /[٠-٩]/);
assert.match(i18n.formatPercent(42.5), /42/);
assert.match(i18n.formatDuration(15), /15/);
assert.ok(events.some(event => event.type === 'binna:languagechange'),
          'language changes should notify the current page without reloading it');

console.log('Operational i18n: 13 passed, 0 failed');
