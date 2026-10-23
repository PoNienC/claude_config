#!/usr/bin/env node
// dd_status.mjs - the /dual_dev bookkeeping script: edits the status rows of a
// request's record files in place, so the coordinator never hand-edits a
// table (23 October 2026 test: hand-written edits cost about a minute per
// request and caused small slips). Also logs timing events, so every request
// reports its own working, waiting and Codex time.
//
// Usage (all commands take the request folder TD first; --dry-run prints
// the changed lines and writes nothing):
//   node dd_status.mjs task     <TD> <T01> <status> [--commit <hash>] [--fix <hash>]
//   node dd_status.mjs running  <TD> add <step> <file> | remove <step>
//   node dd_status.mjs handoff  <TD> <commit>
//   node dd_status.mjs closeout <TD> automatic|ask
//   node dd_status.mjs tokens   <TD> <n>                       (Codex tokens so far)
//   node dd_status.mjs audit    <TD> <scope> <status> [--findings B/H/M/L/N] [--fix <hash>]   (REVIEW.md table)
//   node dd_status.mjs mark     <TD> <event words...>          (appends "HH:MM:SS event" to ## Timing)
//
// Before TASKS.md exists (Phases 0-2), `mark` and `running` write to
// TD/TIMING.md instead; Phase 3 copies its lines into TASKS.md. Status
// changes must follow the documented order (same state again is a no-op);
// Blocked remembers the state it came from and resumes only there; an
// unknown current status is refused; `running add` keeps an existing job's
// start time; `mark` skips an event already logged. What the script does not cover (findings, prose, the
// REVIEW.md close-out line) is edited by hand.
//
// Exit codes: 0 ok, 2 bad arguments, unknown status or refused transition, 3 row or file not found.
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const TASK_STATUSES = ['Pending', 'In progress', 'Done, audit pending', 'In audit', 'Awaiting your review', 'Corrections', 'Complete', 'Blocked'];
// Allowed next states. A task can be blocked from any state and resume
// anywhere; corrections go back to audit (the re-check); nothing skips the audit.
const TASK_NEXT = {
  'Pending': ['In progress', 'Blocked'],
  'In progress': ['Done, audit pending', 'Blocked'],
  'Done, audit pending': ['In audit', 'Blocked'],
  'In audit': ['Awaiting your review', 'Corrections', 'Complete', 'Blocked'],
  'Awaiting your review': ['Corrections', 'Complete', 'Blocked'],
  'Corrections': ['In audit', 'Complete', 'Blocked'],
  'Complete': [],
};
const TASK_FIRST = ['Pending', 'In progress'];
const AUDIT_STATUSES = ['running', 'awaiting your review', 'fixing', 're-check running', 'complete'];
const AUDIT_NEXT = {
  'running': ['awaiting your review', 'fixing', 'complete'],
  'awaiting your review': ['fixing', 'complete'],
  'fixing': ['re-check running', 'complete'],
  're-check running': ['awaiting your review', 'fixing', 'complete'],
  'complete': [],
};
const AUDIT_FIRST = ['running'];

const argv = process.argv.slice(2);
const dry = argv.includes('--dry-run');
const args = argv.filter((a) => a !== '--dry-run');
const [cmd, td, ...rest] = args;
if (!cmd || !td) usage();

function usage(msg) {
  if (msg) console.error(`dd_status: ${msg}`);
  console.error('usage: dd_status.mjs task|running|handoff|closeout|tokens|audit|mark <TD> ... [--dry-run]');
  process.exit(2);
}
function opt(name) {
  const i = rest.indexOf(name);
  return i >= 0 && rest[i + 1] !== undefined ? rest[i + 1] : undefined;
}
function positional() {
  const out = [];
  for (let i = 0; i < rest.length; i++) {
    if (rest[i].startsWith('--')) { i++; continue; }
    out.push(rest[i]);
  }
  return out;
}
function load(name, { createWith } = {}) {
  const p = join(td, name);
  if (!existsSync(p)) {
    if (createWith === undefined) { console.error(`dd_status: ${p} not found`); process.exit(3); }
    return { p, eol: '\n', lines: createWith.split('\n'), created: true };
  }
  const raw = readFileSync(p, 'utf8');
  const eol = raw.includes('\r\n') ? '\r\n' : '\n';
  return { p, eol, lines: raw.split(/\r?\n/) };
}
function save(file, changed) {
  if (!changed.length) { console.log('dd_status: nothing changed'); return; }
  for (const [i, before, after] of changed) console.log(`${dry ? 'DRY ' : ''}${file.p}:${i + 1}\n  - ${before}\n  + ${after}`);
  if (!dry) writeFileSync(file.p, file.lines.join(file.eol), 'utf8');
}
function stamp() { return new Date().toTimeString().slice(0, 8); }
function today() {
  const d = new Date();
  return `${d.getDate()} ${d.toLocaleString('en-GB', { month: 'long' })} ${d.getFullYear()}`;
}
// The record for `mark` and `running`: TASKS.md once it exists, else TD/TIMING.md.
function timingFile() {
  if (existsSync(join(td, 'TASKS.md'))) return load('TASKS.md');
  return load('TIMING.md', { createWith: '# Timing and running jobs (before TASKS.md exists)\n\n- Running now: none\n\n## Timing\n' });
}
function findRow(file, key) {
  for (let i = 0; i < file.lines.length; i++) {
    const line = file.lines[i];
    if (!line.startsWith('|')) continue;
    const cells = line.split('|').map((c) => c.trim());
    if (cells[1] === key) return { i, cells };
  }
  console.error(`dd_status: no row for ${key} in ${file.p}`);
  process.exit(3);
}
// A blocked task remembers where it was ("Blocked (from In progress)") and may
// only resume there, so blocking never skips the work or the audit. An empty
// or placeholder cell may only start; an unknown status is refused.
function checkTransition(kind, from, to, next, first) {
  if (from === to) return 'same';
  const blockedFrom = /^Blocked \(from (.+)\)$/.exec(from);
  let allowed;
  if (blockedFrom) allowed = [blockedFrom[1]];
  else if (from === '' || from === '—' || from === '-' || /^\{\{.*\}\}$/.test(from)) allowed = first;
  else allowed = next[from];
  if (allowed === undefined) {
    console.error(`dd_status: ${kind} has an unknown current status "${from}"; fix the cell by hand first; nothing changed`);
    process.exit(2);
  }
  if (allowed.includes(to)) return 'ok';
  console.error(`dd_status: ${kind} cannot move from "${from}" to "${to}" (allowed next: ${allowed.join(' · ') || 'none'}); nothing changed`);
  process.exit(2);
}
function setCells(file, row, updates) {
  const before = file.lines[row.i];
  const cells = row.cells.slice();
  for (const [col, value] of Object.entries(updates)) cells[Number(col) + 1] = value;
  file.lines[row.i] = `| ${cells.slice(1, -1).join(' | ')} |`;
  return file.lines[row.i] !== before ? [[row.i, before, file.lines[row.i]]] : [];
}
function setHeaderLine(file, prefix, value) {
  const i = file.lines.findIndex((l) => l.startsWith(prefix));
  if (i < 0) { console.error(`dd_status: no line starting "${prefix}" in ${file.p}`); process.exit(3); }
  const before = file.lines[i];
  const comment = before.includes('<!--') ? ' ' + before.slice(before.indexOf('<!--')) : '';
  file.lines[i] = `${prefix} ${value}${comment}`;
  return file.lines[i] !== before ? [[i, before, file.lines[i]]] : [];
}

switch (cmd) {
  case 'task': {
    const [id, status] = positional();
    if (!id || !status) usage('task needs <T01> <status>');
    if (!TASK_STATUSES.includes(status)) usage(`unknown task status "${status}"; use one of: ${TASK_STATUSES.join(' · ')}`);
    const file = load('TASKS.md');
    const row = findRow(file, id);
    const current = row.cells[8];
    const move = checkTransition('task', current, status, TASK_NEXT, TASK_FIRST);
    const written = status === 'Blocked' ? `Blocked (from ${current})` : status;
    const updates = move === 'same' ? {} : { 7: written };
    if (opt('--commit')) updates[8] = `\`${opt('--commit')}\``;
    if (opt('--fix')) updates[9] = `\`${opt('--fix')}\``;
    save(file, setCells(file, row, updates));
    break;
  }
  case 'running': {
    const [action, step, out] = positional();
    const file = timingFile();
    const i = file.lines.findIndex((l) => l.startsWith('- Running now:'));
    if (i < 0) { console.error(`dd_status: no "- Running now:" line in ${file.p}`); process.exit(3); }
    const before = file.lines[i];
    const comment = before.includes('<!--') ? before.slice(before.indexOf('<!--')) : '';
    const body = before.replace(/^- Running now:\s*/, '').replace(/\s*<!--.*$/, '').trim();
    let items = body === 'none' || body === '' ? [] : body.split(' · ');
    if (action === 'add') {
      if (!step || !out) usage('running add needs <step> <file>');
      if (!items.some((x) => x.startsWith(step + ' '))) items.push(`${step} ${stamp()} → ${out}`);
    } else if (action === 'remove') {
      if (!step) usage('running remove needs <step>');
      items = items.filter((x) => !x.startsWith(step + ' '));
    } else usage('running needs add|remove');
    file.lines[i] = `- Running now: ${items.length ? items.join(' · ') : 'none'}${comment ? ' ' + comment : ''}`;
    save(file, file.lines[i] !== before || file.created ? [[i, before, file.lines[i]]] : []);
    break;
  }
  case 'handoff': {
    const [commit] = positional();
    if (!commit) usage('handoff needs <commit>');
    const file = load('TASKS.md');
    save(file, setHeaderLine(file, '- Hand-off:', `\`${commit}\`, ${today()} — see REVIEW.md`));
    break;
  }
  case 'closeout': {
    const [mode] = positional();
    if (!['automatic', 'ask'].includes(mode)) usage('closeout needs automatic|ask');
    const file = load('TASKS.md');
    const i = file.lines.findIndex((l) => l.startsWith('- Close-out:'));
    if (i < 0) {
      const j = file.lines.findIndex((l) => l.startsWith('- Hand-off:'));
      if (j < 0) { console.error('dd_status: no "- Hand-off:" line to insert after'); process.exit(3); }
      file.lines.splice(j + 1, 0, `- Close-out: ${mode}`);
      save(file, [[j + 1, '(new line)', file.lines[j + 1]]]);
    } else save(file, setHeaderLine(file, '- Close-out:', mode));
    break;
  }
  case 'tokens': {
    const [n] = positional();
    if (!n || !/^[\d,]+$/.test(n)) usage('tokens needs a number');
    const file = load('TASKS.md');
    save(file, setHeaderLine(file, '- Codex tokens so far:', n));
    break;
  }
  case 'audit': {
    const [scope, status] = positional();
    if (!scope || !status) usage('audit needs <scope> <status>');
    if (!AUDIT_STATUSES.includes(status)) usage(`unknown audit status "${status}"; use one of: ${AUDIT_STATUSES.join(' · ')}`);
    const file = load('REVIEW.md');
    const row = findRow(file, scope);
    const move = checkTransition('audit', row.cells[4], status, AUDIT_NEXT, AUDIT_FIRST);
    const updates = move === 'same' ? {} : { 3: status };
    if (opt('--findings')) updates[4] = opt('--findings');
    if (opt('--fix')) updates[5] = `\`${opt('--fix')}\``;
    save(file, setCells(file, row, updates));
    break;
  }
  case 'mark': {
    const words = positional().join(' ');
    if (!words) usage('mark needs an event description');
    const file = timingFile();
    let i = file.lines.findIndex((l) => l.trim() === '## Timing');
    if (i < 0) { file.lines.push('', '## Timing', ''); i = file.lines.length - 2; }
    let end = i + 1;
    while (end < file.lines.length && !file.lines[end].startsWith('## ')) end++;
    while (end > i + 1 && file.lines[end - 1].trim() === '') end--;
    const already = file.lines.slice(i + 1, end).some((l) => l.replace(/^\d\d:\d\d:\d\d /, '') === words);
    if (already) { console.log(`dd_status: "${words}" already logged - nothing changed`); break; }
    const line = `${stamp()} ${words}`;
    file.lines.splice(end, 0, line);
    save(file, [[end, '(new line)', line]]);
    break;
  }
  default:
    usage(`unknown command "${cmd}"`);
}
