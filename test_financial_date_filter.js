'use strict';

const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const context = { window: null, console };
context.window = context;
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/js/financial-date-filter.js', 'utf8'), context);

const dates = context.BINNA_FINANCIAL_DATES;
assert.ok(dates, 'shared financial date helper should be exported');
assert.strictEqual(dates.parseDate('15/08/2026'), '2026-08-15');
assert.strictEqual(dates.parseDate('١٥/٠٨/٢٠٢٦'), '2026-08-15');
assert.strictEqual(dates.parseDate('2026-08-15'), '2026-08-15');
assert.strictEqual(dates.parseDate('31/02/2026'), null);
assert.strictEqual(dates.parseDate('not-a-date'), null);

const rows = [
  { id: 1, date: '2026-08-14' },
  { id: 2, date: '2026-08-15' },
  { id: 3, date: '2026-08-16' },
  { id: 4, date: '2026-08-17' },
];
assert.deepStrictEqual(Array.from(dates.filterRows(rows, '15/08/2026', ''), row => row.id), [2]);
assert.deepStrictEqual(Array.from(dates.filterRows(rows, '', '١٦/٠٨/٢٠٢٦'), row => row.id), [3]);
assert.deepStrictEqual(Array.from(dates.filterRows(rows, '15/08/2026', '17/08/2026'), row => row.id), [2, 3, 4]);
assert.deepStrictEqual(Array.from(dates.filterRows(rows, '', ''), row => row.id), [1, 2, 3, 4]);
assert.deepStrictEqual(Array.from(dates.filterRows(rows, '17/08/2026', '15/08/2026'), row => row.id), []);
assert.deepStrictEqual(Array.from(dates.filterRows(rows, '31/02/2026', ''), row => row.id), []);
assert.strictEqual(dates.formatDisplay('2026-08-15', false), '15/08/2026');
assert.strictEqual(dates.formatDisplay('2026-08-15', true), '١٥/٠٨/٢٠٢٦');
const textInput = { value: '' };
assert.strictEqual(dates.syncPicker({ value: '2026-08-15' }, textInput, true), '2026-08-15');
assert.strictEqual(textInput.value, '١٥/٠٨/٢٠٢٦');

for (const file of ['binna-income.html', 'binna-expense.html']) {
  const html = fs.readFileSync(file, 'utf8');
  assert.ok(html.includes('onchange="updateRowDate('), `${file} routes edited dates through strict validation`);
  assert.ok(!html.includes('dispToISO(this.value)||this.value'), `${file} never persists invalid date text`);
}
const accountsHtml = fs.readFileSync('binna-financial.html', 'utf8');
assert.ok(accountsHtml.includes('onchange="upPDate('), 'Accounts routes preview dates through strict validation');
assert.ok(!accountsHtml.includes('dispToISO(this.value)||this.value'), 'Accounts never persists invalid date text');

console.log('Financial date filtering: 21 passed, 0 failed');
