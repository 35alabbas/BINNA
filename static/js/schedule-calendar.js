(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.BINNA_SCHEDULE_CALENDAR = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  var DAY_MS = 86400000;

  function parseISO(value) {
    var match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return null;
    var date = new Date(Date.UTC(+match[1], +match[2] - 1, +match[3]));
    return isNaN(date.getTime()) ? null : date;
  }

  function iso(date) {
    return date.toISOString().slice(0, 10);
  }

  function addCalendarDays(value, days) {
    var date = value instanceof Date ? new Date(value.getTime()) : parseISO(value);
    if (!date) return null;
    date.setUTCDate(date.getUTCDate() + Math.round(Number(days) || 0));
    return date;
  }

  function mergeStoppages(rows) {
    var ranges = (Array.isArray(rows) ? rows : []).map(function (row) {
      var start = parseISO(row && row.start), end = parseISO(row && (row.end || row.start));
      if (!start || !end) return null;
      if (end < start) { var swap = start; start = end; end = swap; }
      return { startDate: start, endDate: end };
    }).filter(Boolean).sort(function (a, b) { return a.startDate - b.startDate; });

    var merged = [];
    ranges.forEach(function (range) {
      var previous = merged[merged.length - 1];
      if (!previous || range.startDate > addCalendarDays(previous.endDate, 1)) {
        merged.push(range);
      } else if (range.endDate > previous.endDate) {
        previous.endDate = range.endDate;
      }
    });
    return merged.map(function (range) { return { start: iso(range.startDate), end: iso(range.endDate) }; });
  }

  function prepared(rows) {
    return mergeStoppages(rows).map(function (row) {
      return { start: parseISO(row.start), end: parseISO(row.end) };
    });
  }

  function stopContaining(date, ranges) {
    for (var index = 0; index < ranges.length; index += 1) {
      if (date >= ranges[index].start && date <= ranges[index].end) return ranges[index];
    }
    return null;
  }

  function pushOut(date, ranges) {
    var result = new Date(date.getTime()), stop = stopContaining(result, ranges);
    if (stop) result = addCalendarDays(stop.end, 1);
    return result;
  }

  function addWorkingDaysInclusive(start, executionDays, ranges) {
    var remaining = Math.max(1, Math.round(Number(executionDays) || 1));
    var date = pushOut(start, ranges), last = new Date(date.getTime());
    while (remaining > 0) {
      var stop = stopContaining(date, ranges);
      if (stop) {
        date = addCalendarDays(stop.end, 1);
        continue;
      }
      last = new Date(date.getTime());
      remaining -= 1;
      if (remaining > 0) date = addCalendarDays(date, 1);
    }
    return last;
  }

  function contractExecutionDays(originalDuration, extensionDays) {
    return Math.max(0, Math.round(Number(originalDuration) || 0))
      + Math.max(0, Math.round(Number(extensionDays) || 0));
  }

  function contractCompletionDate(startISO, originalDuration, extensionDays, stoppages) {
    var start = parseISO(startISO), remaining = contractExecutionDays(originalDuration, extensionDays);
    if (!start || remaining <= 0) return '';
    var ranges = prepared(stoppages), date = new Date(start.getTime());
    // Existing BINNA convention: the contract date is day zero, so execution
    // day one is the following calendar date. Stoppage ranges are inclusive.
    while (remaining > 0) {
      date = addCalendarDays(date, 1);
      var stop = stopContaining(date, ranges);
      if (stop) {
        date = new Date(stop.end.getTime());
        continue;
      }
      remaining -= 1;
    }
    return iso(date);
  }

  function inclusiveDuration(task) {
    var start = parseISO(task && task.start), end = parseISO(task && (task.end || task.start));
    return start && end ? Math.max(1, Math.round((end - start) / DAY_MS) + 1) : 1;
  }

  function scheduleActivity(startISO, duration, stoppages) {
    var start = parseISO(startISO);
    if (!start) return { start: startISO || '', end: startISO || '' };
    var ranges = prepared(stoppages), effectiveStart = pushOut(start, ranges);
    return { start: iso(effectiveStart), end: iso(addWorkingDaysInclusive(effectiveStart, duration, ranges)) };
  }

  function scheduleTaskChain(tasks, stoppages) {
    var source = Array.isArray(tasks) ? tasks : [], byId = {}, result = {}, pending = source.slice();
    source.forEach(function (task) { byId[String(task.id)] = task; });
    var guard = source.length + 1;
    while (pending.length && guard-- > 0) {
      var next = [], progressed = false;
      pending.forEach(function (task) {
        var predecessors = (task.preds || []).filter(function (pred) { return byId[String(pred.id)]; });
        if (predecessors.some(function (pred) { return !result[String(pred.id)]; })) { next.push(task); return; }
        var planned = parseISO(task.start);
        if (!planned) { result[String(task.id)] = { start: task.start || '', end: task.end || task.start || '' }; progressed = true; return; }
        var effectiveStart = planned;
        predecessors.forEach(function (pred) {
          var finish = parseISO(result[String(pred.id)].end);
          var earliest = addCalendarDays(finish, 1 + Math.round(Number(pred.lag) || 0));
          if (earliest > effectiveStart) effectiveStart = earliest;
        });
        result[String(task.id)] = scheduleActivity(iso(effectiveStart), inclusiveDuration(task), stoppages);
        progressed = true;
      });
      if (!progressed) break;
      pending = next;
    }
    pending.forEach(function (task) {
      result[String(task.id)] = scheduleActivity(task.start, inclusiveDuration(task), stoppages);
    });
    return result;
  }

  function scheduleLeafTaskChain(tasks, stoppages) {
    var source = Array.isArray(tasks) ? tasks : [], hasChildren = {}, byId = {};
    source.forEach(function (task, index) {
      byId[String(task.id)] = index;
      var level = Number(task.level) || 0;
      if (index + 1 < source.length && (Number(source[index + 1].level) || 0) === level + 1) hasChildren[String(task.id)] = true;
    });
    var leaves = source.filter(function (task) { return !hasChildren[String(task.id)]; });
    var leafIds = {};
    leaves.forEach(function (task) { leafIds[String(task.id)] = true; });
    var expanded = leaves.map(function (task) {
      var predecessors = [];
      (task.preds || []).forEach(function (pred) {
        var predId = String(pred.id), predIndex = byId[predId];
        if (predIndex === undefined || leafIds[predId]) { predecessors.push({id:pred.id,lag:pred.lag}); return; }
        var parentLevel = Number(source[predIndex].level) || 0;
        for (var i = predIndex + 1; i < source.length; i++) {
          var level = Number(source[i].level) || 0;
          if (level <= parentLevel) break;
          if (leafIds[String(source[i].id)]) predecessors.push({id:source[i].id,lag:pred.lag});
        }
      });
      var unique = {};
      predecessors.forEach(function (pred) {
        var key = String(pred.id), lag = Math.round(Number(pred.lag) || 0);
        if (key !== String(task.id) && (!unique[key] || lag > unique[key].lag)) unique[key] = {id:pred.id,lag:lag};
      });
      return Object.assign({}, task, {preds:Object.keys(unique).map(function (key) { return unique[key]; })});
    });
    return scheduleTaskChain(expanded, stoppages);
  }

  return {
    mergeStoppages: mergeStoppages,
    contractExecutionDays: contractExecutionDays,
    contractCompletionDate: contractCompletionDate,
    inclusiveDuration: inclusiveDuration,
    scheduleActivity: scheduleActivity,
    scheduleTaskChain: scheduleTaskChain,
    scheduleLeafTaskChain: scheduleLeafTaskChain,
  };
});
