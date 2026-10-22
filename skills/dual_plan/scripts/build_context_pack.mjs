#!/usr/bin/env node
// build_context_pack.mjs - write one Markdown file holding everything a planner
// needs about a repository, so Codex (and Claude) plan from pasted text instead
// of exploring the repo one file at a time (7-14 minutes per plan on Windows,
// measured 7-21 October 2026). Part of the dual_plan skill.
//
// Usage:
//   node build_context_pack.mjs --repo <root> --out <file> [--include <path>]... [--max-chars 160000]
//
// The pack holds, in order: the repo tree (git ls-files, grouped by top folder),
// the key docs (AGENTS.md, .ai/PROJECT.md, .ai/STATE.md, .ai/DECISIONS.md,
// README.md - each capped), then every --include file in full (capped per
// file and in total). Paths are relative to the repo root. Read-only.
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const args = process.argv.slice(2);
const opt = { include: [], maxChars: 160000 };
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === '--repo') opt.repo = args[++i];
  else if (a === '--out') opt.out = args[++i];
  else if (a === '--include') opt.include.push(args[++i]);
  else if (a === '--max-chars') opt.maxChars = Number(args[++i]);
  else { console.error(`Unknown argument: ${a}`); process.exit(64); }
}
if (!opt.repo || !opt.out) { console.error('usage: --repo <root> --out <file> [--include <path>]... [--max-chars N]'); process.exit(64); }

const repo = resolve(opt.repo);
const git = (...a) => execFileSync('git', ['-C', repo, '-c', 'core.quotepath=off', ...a], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
const DOC_CAP = 12000;      // characters per key doc
const FILE_CAP = 40000;     // characters per included file
const TREE_LINES = 400;     // lines of the file tree

const cap = (text, n, label) => text.length <= n ? text : text.slice(0, n) + `\n… [${label}: truncated at ${n} characters of ${text.length}]`;
const read = (rel) => { const p = resolve(repo, rel); return existsSync(p) ? readFileSync(p, 'utf8') : null; };
const fence = (text) => { const t = text.replace(/\r\n/g, '\n'); const ticks = t.includes('~~~~') ? '~~~~~' : '~~~~'; return `${ticks}\n${t}\n${ticks}`; };

const parts = [];
const stats = { files: 0, chars: 0, skipped: [] };
let head = '';
try { head = git('log', '-1', '--format=%h %ad %s', '--date=short').trim(); } catch { head = '(no commits)'; }
let branch = '';
try { branch = git('branch', '--show-current').trim(); } catch { /* detached or none */ }
parts.push(`# Context pack — ${repo}\n\nBranch: \`${branch || 'none'}\` · last commit: ${head} · built ${new Date().toISOString().slice(0, 16).replace('T', ' ')}\n\nEverything a planner needs is pasted below. Paths are relative to the repo root.`);

// 1. Tree
let files = [];
try { files = git('ls-files').split('\n').filter(Boolean); } catch { files = []; }
const byTop = new Map();
for (const f of files) { const top = f.includes('/') ? f.split('/')[0] + '/' : '(root)'; byTop.set(top, (byTop.get(top) || 0) + 1); }
const summary = [...byTop.entries()].sort((a, b) => b[1] - a[1]).map(([k, v]) => `${v.toString().padStart(5)}  ${k}`).join('\n');
const treeShown = files.length > TREE_LINES ? files.slice(0, TREE_LINES).join('\n') + `\n… ${files.length - TREE_LINES} more files (run git ls-files for the rest)` : files.join('\n');
parts.push(`## Repository tree (${files.length} tracked files)\n\nFiles per top-level folder:\n${fence(summary)}\n\nAll paths:\n${fence(treeShown)}`);

// 2. Key docs
const keyDocs = ['AGENTS.md', '.ai/PROJECT.md', '.ai/STATE.md', '.ai/DECISIONS.md', 'README.md', 'CLAUDE.md'];
const docParts = [];
for (const d of keyDocs) { const t = read(d); if (t !== null) docParts.push(`### ${d}\n\n${fence(cap(t, DOC_CAP, d))}`); }
parts.push(`## Key documents\n\n${docParts.length ? docParts.join('\n\n') : '(none of AGENTS.md, .ai/*.md, README.md, CLAUDE.md found)'}`);

// 3. Included files
const incParts = [];
let budget = opt.maxChars - parts.join('\n\n').length;
for (const rel of opt.include) {
  const t = read(rel);
  if (t === null) { stats.skipped.push(`${rel} (not found)`); continue; }
  if (/\0/.test(t.slice(0, 4000))) { stats.skipped.push(`${rel} (binary)`); continue; }
  const body = cap(t, Math.min(FILE_CAP, Math.max(0, budget)), rel);
  if (budget <= 2000) { stats.skipped.push(`${rel} (pack full)`); continue; }
  incParts.push(`### ${rel} (${t.split('\n').length} lines)\n\n${fence(body)}`);
  budget -= body.length + rel.length + 40;
  stats.files++; stats.chars += body.length;
}
parts.push(`## Relevant files in full (${stats.files})\n\n${incParts.length ? incParts.join('\n\n') : '(none included)'}${stats.skipped.length ? `\n\nNot included: ${stats.skipped.join('; ')}` : ''}`);

const out = resolve(opt.out);
mkdirSync(dirname(out), { recursive: true });
const text = parts.join('\n\n') + '\n';
writeFileSync(out, text, 'utf8');
console.log(`CONTEXT PACK: ${out} — ${text.length} characters, ${files.length} tracked files listed, ${docParts.length} key docs, ${stats.files} files in full${stats.skipped.length ? `, skipped ${stats.skipped.length}` : ''}`);
