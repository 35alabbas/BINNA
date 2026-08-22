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
  dispatchEvent(event) { events.push(event); },
  Intl,
  Date,
  console,
};
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/management-i18n.js', 'utf8'), context);

const i18n = context.BINNA_I18N;
assert.ok(i18n, 'BINNA_I18N should be available');
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

i18n.setLang('en');
assert.strictEqual(context.document.documentElement.dir, 'ltr');
assert.match(i18n.formatNumber(1250.5), /[0-9]/);
assert.doesNotMatch(i18n.formatNumber(1250.5), /[٠-٩]/);
assert.ok(events.some(event => event.type === 'binna:languagechange'),
          'language changes should notify the current page without reloading it');

console.log('Operational i18n: 13 passed, 0 failed');
