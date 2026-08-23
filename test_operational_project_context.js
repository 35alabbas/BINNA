const fs = require('fs');

let passed = 0;
let failed = 0;
function check(condition, message) {
  if (condition) passed += 1;
  else { failed += 1; console.error(`FAIL: ${message}`); }
}

const modules = [
  'binna-dc.html', 'binna-dr.html', 'binna-contract.html',
  'binna-financial.html', 'binna-income.html', 'binna-expense.html',
  'binna-gantt.html', 'binna-subcontract.html', 'binna-dwg.html',
  'binna-fir.html', 'binna-mir.html', 'binna-ms.html',
  'binna-rfi.html', 'binna-lbt.html'
];

for (const file of modules) {
  const html = fs.readFileSync(file, 'utf8');
  check(html.includes('/static/js/operational-shell.js'), `${file} loads the shared operational shell`);
  check(!html.includes('Auxiliary Pump Station'), `${file} has no stale sample project name`);
  check(!html.includes('<b id="proj-code">APS</b>'), `${file} has no stale sample project code`);
}

const dc = fs.readFileSync('binna-dc.html', 'utf8');
check(!dc.includes('id="proj-name-display">Loading…'), 'Document Control header does not ship as permanently loading');

const contract = fs.readFileSync('binna-contract.html', 'utf8');
check(!contract.includes('id="contract-type-tag"'), 'contract top bar omits the government/private badge');

console.log(`Operational project context: ${passed} passed, ${failed} failed`);
process.exitCode = failed ? 1 : 0;
