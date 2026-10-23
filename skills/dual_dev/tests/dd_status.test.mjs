// Tests for scripts/dd_status.mjs — run with:  node --test skills/dual_dev/tests/dd_status.test.mjs
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const script = join(here, '..', 'scripts', 'dd_status.mjs');

const TASKS = `# Tasks — T001_x: test

- Branch: \`dual_dev/T001_x\` · push policy: none
- Hand-off: pending <!-- pending | commit, date — see REVIEW.md -->
- Running now: none <!-- every background job -->
- Codex tokens so far: 0

| Task | Title | Executor | Reviewer | Block | Depends on | Risk | Status | Commit | Audit fix |
|---|---|---|---|---|---|---|---|---|---|
| T01 | First | Claude | Codex | B1 | — | low | Pending | — | — |
| T02 | Second | Claude | Codex | B2 | T01 | low | Pending | — | — |

Status values: Pending · In progress · Complete
`;
const REVIEW = `# Hand-off review — T001_x

## Audits

| Scope | Tasks | Reviewer (model, effort) | Status | Findings B/H/M/L/N | Fix commit |
|---|---|---|---|---|---|
| B1 | T01 | Codex (x, medium) | running | | |
`;

function setup({ tasks = true } = {}) {
  const td = mkdtempSync(join(tmpdir(), 'dd_status_'));
  if (tasks) writeFileSync(join(td, 'TASKS.md'), TASKS.replace(/\n/g, '\r\n'));
  writeFileSync(join(td, 'REVIEW.md'), REVIEW);
  return td;
}
function run(...args) {
  try { return { code: 0, out: execFileSync('node', [script, ...args], { encoding: 'utf8' }) }; }
  catch (e) { return { code: e.status, out: (e.stdout || '') + (e.stderr || '') }; }
}
const read = (td, f) => readFileSync(join(td, f), 'utf8');

test('task: status and commit land in the right cells, prose and CRLF untouched', () => {
  const td = setup();
  assert.equal(run('task', td, 'T01', 'In progress').code, 0);
  assert.equal(run('task', td, 'T01', 'Done, audit pending', '--commit', 'abc1234').code, 0);
  const t = read(td, 'TASKS.md');
  assert.match(t, /\| T01 \| First \| Claude \| Codex \| B1 \| — \| low \| Done, audit pending \| `abc1234` \| — \|/);
  assert.match(t, /\| T02 \| Second .* Pending \| — \| — \|/);
  assert.match(t, /Status values: Pending · In progress · Complete/);
  assert.ok(t.includes('\r\n') && !/[^\r]\n/.test(t), 'CRLF kept throughout');
});

test('task: unknown status and refused transition leave the file byte-for-byte unchanged', () => {
  const td = setup();
  const before = read(td, 'TASKS.md');
  assert.equal(run('task', td, 'T01', 'Finished').code, 2);
  assert.equal(run('task', td, 'T01', 'Complete').code, 2, 'Pending → Complete skips the audit');
  assert.equal(run('task', td, 'T01', 'In audit').code, 2, 'Pending → In audit skips the work');
  assert.equal(read(td, 'TASKS.md'), before);
  run('task', td, 'T01', 'In progress');
  const after = read(td, 'TASKS.md');
  assert.equal(run('task', td, 'T01', 'Complete').code, 2, 'In progress → Complete skips the audit');
  assert.equal(read(td, 'TASKS.md'), after);
});

test('task: same state again is a no-op; Blocked resumes only where it was; Corrections moves are allowed', () => {
  const td = setup();
  run('task', td, 'T01', 'In progress');
  assert.match(run('task', td, 'T01', 'In progress').out, /nothing changed/);
  assert.equal(run('task', td, 'T01', 'Blocked').code, 0);
  assert.match(read(td, 'TASKS.md'), /\| Blocked \(from In progress\) \|/);
  const blocked = read(td, 'TASKS.md');
  assert.equal(run('task', td, 'T01', 'Complete').code, 2, 'Blocked cannot jump to Complete');
  assert.equal(run('task', td, 'T01', 'In audit').code, 2, 'Blocked cannot jump into the audit');
  assert.equal(read(td, 'TASKS.md'), blocked);
  assert.equal(run('task', td, 'T01', 'In progress').code, 0, 'resume where it was');
  run('task', td, 'T01', 'Done, audit pending'); run('task', td, 'T01', 'In audit'); run('task', td, 'T01', 'Corrections');
  assert.equal(run('task', td, 'T01', 'In audit').code, 0, 'corrections go back to audit for the re-check');
  assert.equal(run('task', td, 'T01', 'Complete', '--fix', '7777777').code, 0);
  assert.match(read(td, 'TASKS.md'), /\| Complete \| — \| `7777777` \|/);
});

test('task: unknown row exits 3; unknown current status and placeholder cells are guarded', () => {
  const td = setup();
  assert.equal(run('task', td, 'T09', 'In progress').code, 3);
  writeFileSync(join(td, 'TASKS.md'), TASKS.replace('| low | Pending | — | — |\n| T02', '| low | Finnished | — | — |\n| T02').replace('| T02 | Second | Claude | Codex | B2 | T01 | low | Pending |', '| T02 | Second | Claude | Codex | B2 | T01 | low | — |'));
  const before = read(td, 'TASKS.md');
  assert.equal(run('task', td, 'T01', 'Complete').code, 2, 'unknown current status is refused');
  assert.equal(run('task', td, 'T02', 'Complete').code, 2, 'placeholder cell cannot jump to Complete');
  assert.equal(read(td, 'TASKS.md'), before);
  assert.equal(run('task', td, 'T02', 'In progress').code, 0, 'placeholder cell may start');
});

test('running: add is idempotent (keeps the first start time), remove ends at none', () => {
  const td = setup();
  run('running', td, 'add', 'B1_audit_r1', 'codex/B1_audit_r1_out.md');
  const first = read(td, 'TASKS.md').match(/- Running now: (B1_audit_r1 \d\d:\d\d:\d\d → codex\/B1_audit_r1_out\.md)/)[1];
  assert.match(run('running', td, 'add', 'B1_audit_r1', 'codex/B1_audit_r1_out.md').out, /nothing changed/);
  assert.ok(read(td, 'TASKS.md').includes(first), 'start time unchanged on retry');
  run('running', td, 'add', 'T02_exec', 'codex/T02_exec_out.md');
  assert.match(read(td, 'TASKS.md'), /B1_audit_r1 .* · T02_exec .* <!-- every background job -->/);
  run('running', td, 'remove', 'B1_audit_r1'); run('running', td, 'remove', 'T02_exec');
  assert.match(read(td, 'TASKS.md'), /- Running now: none <!-- every background job -->/);
});

test('mark and running before TASKS.md exists go to TIMING.md', () => {
  const td = setup({ tasks: false });
  assert.equal(run('mark', td, 'request received').code, 0);
  assert.equal(run('running', td, 'add', 'plan', 'codex/plan_out.md').code, 0);
  assert.ok(existsSync(join(td, 'TIMING.md')) && !existsSync(join(td, 'TASKS.md')));
  const t = read(td, 'TIMING.md');
  assert.match(t, /- Running now: plan \d\d:\d\d:\d\d → codex\/plan_out\.md/);
  assert.match(t, /## Timing\r?\n\d\d:\d\d:\d\d request received/);
});

test('handoff, closeout, tokens: header lines updated, close-out inserted once', () => {
  const td = setup();
  run('handoff', td, 'def5678'); run('closeout', td, 'automatic'); run('closeout', td, 'ask'); run('tokens', td, '12,345');
  const t = read(td, 'TASKS.md');
  assert.match(t, /- Hand-off: `def5678`, \d+ \w+ \d{4} — see REVIEW\.md <!--/);
  assert.equal((t.match(/^- Close-out: /gm) || []).length, 1);
  assert.match(t, /- Close-out: ask/);
  assert.match(t, /- Codex tokens so far: 12,345/);
});

test('audit: REVIEW.md row updated; backwards move refused', () => {
  const td = setup();
  assert.equal(run('audit', td, 'B1', 'fixing', '--findings', '0/0/1/0/0').code, 0);
  assert.equal(run('audit', td, 'B1', 'running').code, 2);
  assert.equal(run('audit', td, 'B1', 'complete', '--fix', '9f9f9f9').code, 0);
  assert.match(read(td, 'REVIEW.md'), /\| B1 \| T01 \| Codex \(x, medium\) \| complete \| 0\/0\/1\/0\/0 \| `9f9f9f9` \|/);
});

test('mark: timing section created, appended in order, duplicate event skipped', () => {
  const td = setup();
  run('mark', td, 'request received'); run('mark', td, 'Codex plan launched');
  assert.match(run('mark', td, 'request received').out, /already logged/);
  const t = read(td, 'TASKS.md');
  const i = t.indexOf('## Timing');
  assert.ok(i > 0);
  const lines = t.slice(i).split(/\r?\n/).filter((l) => /^\d\d:\d\d:\d\d /.test(l));
  assert.deepEqual(lines.map((l) => l.slice(9)), ['request received', 'Codex plan launched']);
});

test('dry run writes nothing', () => {
  const td = setup();
  const before = read(td, 'TASKS.md');
  const r = run('task', td, 'T01', 'In progress', '--dry-run');
  assert.equal(r.code, 0);
  assert.match(r.out, /DRY /);
  assert.equal(read(td, 'TASKS.md'), before);
});
