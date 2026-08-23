const assert = require('assert');
const calendar = require('./static/js/schedule-calendar.js');

let passed = 0;
function test(name, fn) {
  try { fn(); passed += 1; console.log('ok  ' + name); }
  catch (error) { console.error('FAIL ' + name); throw error; }
}

const stop = (start, end) => ({ start, end });

test('contract convention counts execution days after the contract date', () => {
  assert.equal(calendar.contractCompletionDate('2026-01-01', 100, 0, []), '2026-04-11');
});

test('stoppage-only skips interrupted dates without increasing contract duration', () => {
  assert.equal(calendar.contractExecutionDays(100, 0), 100);
  assert.equal(calendar.contractCompletionDate('2026-01-01', 100, 0, [stop('2026-02-01', '2026-02-10')]), '2026-04-21');
});

test('extension-only increases contractual execution duration', () => {
  assert.equal(calendar.contractExecutionDays(100, 15), 115);
  assert.equal(calendar.contractCompletionDate('2026-01-01', 100, 15, []), '2026-04-26');
});

test('combined stoppage and extension apply independently', () => {
  assert.equal(calendar.contractExecutionDays(100, 15), 115);
  assert.equal(calendar.contractCompletionDate('2026-01-01', 100, 15, [stop('2026-02-01', '2026-02-10')]), '2026-05-06');
});

test('overlapping and adjacent stoppages merge without double counting', () => {
  const merged = calendar.mergeStoppages([
    stop('2026-02-01', '2026-02-05'),
    stop('2026-02-04', '2026-02-10'),
    stop('2026-02-11', '2026-02-12'),
  ]);
  assert.deepEqual(merged, [{ start: '2026-02-01', end: '2026-02-12' }]);
  assert.equal(calendar.contractCompletionDate('2026-01-01', 100, 0, merged), '2026-04-23');
});

test('stoppages outside the execution timeline do not affect completion', () => {
  assert.equal(calendar.contractCompletionDate('2026-01-01', 10, 0, [
    stop('2025-12-01', '2025-12-31'), stop('2026-02-01', '2026-02-10'),
  ]), '2026-01-11');
});

test('activity interrupted midway resumes with unchanged inclusive duration', () => {
  assert.deepEqual(
    calendar.scheduleActivity('2026-01-01', 10, [stop('2026-01-05', '2026-01-07')]),
    { start: '2026-01-01', end: '2026-01-13' },
  );
});

test('effective predecessor finishes propagate through chains and preserve lag', () => {
  const tasks = [
    { id: 'a', start: '2026-01-01', end: '2026-01-05', baselineStart: '2025-12-30', baselineEnd: '2026-01-03', actualCompletion: '2026-01-20', preds: [] },
    { id: 'b', start: '2026-01-06', end: '2026-01-08', preds: [{ id: 'a', lag: 0 }] },
    { id: 'c', start: '2026-01-09', end: '2026-01-10', preds: [{ id: 'b', lag: 2 }] },
  ];
  const effective = calendar.scheduleTaskChain(tasks, [stop('2026-01-03', '2026-01-04')]);
  assert.deepEqual(effective.a, { start: '2026-01-01', end: '2026-01-07' });
  assert.deepEqual(effective.b, { start: '2026-01-08', end: '2026-01-10' });
  assert.deepEqual(effective.c, { start: '2026-01-13', end: '2026-01-14' });
  assert.deepEqual(tasks.map(t => [t.start, t.end]), [
    ['2026-01-01', '2026-01-05'], ['2026-01-06', '2026-01-08'], ['2026-01-09', '2026-01-10'],
  ]);
  assert.deepEqual([tasks[0].baselineStart, tasks[0].baselineEnd, tasks[0].actualCompletion], ['2025-12-30', '2026-01-03', '2026-01-20']);
});

test('container predecessors propagate from their latest executable descendant', () => {
  const tasks = [
    {id:'summary', type:'group', level:0, start:'2026-01-01', end:'2026-01-04', preds:[]},
    {id:'a', type:'task', level:1, start:'2026-01-01', end:'2026-01-02', preds:[]},
    {id:'b', type:'task', level:1, start:'2026-01-03', end:'2026-01-04', preds:[]},
    {id:'c', type:'task', level:0, start:'2026-01-05', end:'2026-01-05', preds:[{id:'summary',lag:1}]},
    {id:'d', type:'task', level:0, start:'2026-01-06', end:'2026-01-06', preds:[{id:'c',lag:0}]},
  ];
  const result = calendar.scheduleLeafTaskChain(tasks, [stop('2026-01-04', '2026-01-04')]);
  assert.equal(result.c.start, '2026-01-07');
  assert.equal(result.d.start, '2026-01-08');
});

test('contract and Gantt produce the same adjusted finish for the same execution timeline', () => {
  const stoppages = [stop('2026-02-01', '2026-02-10')];
  const contractEnd = calendar.contractCompletionDate('2026-01-01', 100, 0, stoppages);
  const ganttEnd = calendar.scheduleActivity('2026-01-02', 100, stoppages).end;
  assert.equal(contractEnd, ganttEnd);
});

console.log(`Schedule calendar: ${passed} passed, 0 failed`);
