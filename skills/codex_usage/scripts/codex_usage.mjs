#!/usr/bin/env node
// Codex usage report (Windows and macOS), written 8 October 2026.
//
// Plan limits: asked live from the local Codex app-server
//   (method account/rateLimits/read) - read-only, uses none of the quota.
// Token totals: summed from Codex's own session files
//   ($CODEX_HOME/sessions/**/*.jsonl, default ~/.codex), grouped by project
//   folder. Each file holds a session_meta line (cwd, originator) and
//   token_count events with cumulative totals; the last one is used.
//
// Usage:
//   node codex_usage.mjs            full report (plain text)
//   node codex_usage.mjs --brief    one line, used by the run_codex launchers
//   node codex_usage.mjs --json     machine-readable
// Always exits 0, so a launcher never fails because of this report.

import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";

const MODE = process.argv.includes("--json") ? "json" : process.argv.includes("--brief") ? "brief" : "full";
const CODEX_HOME = process.env.CODEX_HOME || path.join(os.homedir(), ".codex");
const DASHBOARD = "https://chatgpt.com/codex/settings/usage";
const TIMEOUT_MS = 20000;

const fmtTime = new Intl.DateTimeFormat("en-GB", {
  weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit"
});

function windowLabel(mins) {
  if (mins === 300) return "5-hour";
  if (mins === 10080) return "weekly";
  if (mins % 1440 === 0) return `${mins / 1440}-day`;
  return `${mins}-minute`;
}

function describeWindow(w) {
  if (!w) return null;
  const resets = w.resetsAt ? fmtTime.format(new Date(w.resetsAt * 1000)) : "unknown";
  return { label: windowLabel(w.windowDurationMins), usedPercent: w.usedPercent, resets };
}

// --- Plan limits from the local app-server -------------------------------
function readLimits() {
  return new Promise((resolve) => {
    const win = process.platform === "win32";
    // On Windows the npm shim needs a shell; pass one command string so Node
    // does not warn about concatenated arguments.
    const proc = win
      ? spawn("codex app-server", { shell: true, stdio: ["pipe", "pipe", "pipe"], windowsHide: true })
      : spawn("codex", ["app-server"], { stdio: ["pipe", "pipe", "pipe"] });
    const pending = new Map();
    let nextId = 1;
    let done = false;

    const finish = (value) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { proc.stdin.end(); } catch { /* already closed */ }
      // Make sure no app-server is left running (the shell may not pass on a kill).
      setTimeout(() => {
        if (proc.exitCode === null) {
          if (win) spawnSync("taskkill", ["/pid", String(proc.pid), "/T", "/F"], { windowsHide: true });
          else proc.kill();
        }
        resolve(value);
      }, 300);
    };
    const timer = setTimeout(() => finish({ error: "Codex did not answer within 20 s" }), TIMEOUT_MS);

    proc.on("error", (err) => finish({ error: `cannot start codex: ${err.message}` }));
    proc.on("exit", (code) => { if (!done) finish({ error: `codex app-server exited (${code})` }); });
    readline.createInterface({ input: proc.stdout }).on("line", (line) => {
      let msg;
      try { msg = JSON.parse(line); } catch { return; }
      if (msg.id !== undefined && pending.has(msg.id)) {
        pending.get(msg.id)(msg);
        pending.delete(msg.id);
      }
    });
    const request = (method, params) => new Promise((res) => {
      const id = nextId++;
      pending.set(id, res);
      proc.stdin.write(JSON.stringify({ id, method, params }) + "\n");
    });

    (async () => {
      const init = await request("initialize", {
        clientInfo: { title: "codex usage report", name: "codex_usage", version: "1.0.0" },
        capabilities: { experimentalApi: false }
      });
      if (init.error) return finish({ error: `initialize failed: ${init.error.message ?? "unknown"}` });
      proc.stdin.write(JSON.stringify({ method: "initialized", params: {} }) + "\n");
      const res = await request("account/rateLimits/read", {});
      if (res.error) return finish({ error: res.error.message ?? "rate limits not available" });
      const r = res.result ?? {};
      const rl = r.rateLimits ?? {};
      finish({
        plan: rl.planType ?? "unknown",
        primary: describeWindow(rl.primary),
        secondary: describeWindow(rl.secondary),
        resetCredits: r.rateLimitResetCredits?.availableCount ?? 0,
        limitReached: rl.rateLimitReachedType ?? null
      });
    })().catch((err) => finish({ error: err.message }));
  });
}

// --- Token totals from session files ---------------------------------------
function listSessionFiles(root, since) {
  const out = [];
  const walk = (dir) => {
    let entries;
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
    for (const e of entries) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.name.endsWith(".jsonl")) {
        try { if (fs.statSync(p).mtimeMs >= since) out.push(p); } catch { /* vanished */ }
      }
    }
  };
  walk(root);
  return out;
}

function readSession(file) {
  let text;
  try { text = fs.readFileSync(file, "utf8"); } catch { return null; }
  const firstLine = text.slice(0, text.indexOf("\n") === -1 ? undefined : text.indexOf("\n"));
  let cwd = "unknown", origin = "unknown";
  try {
    const meta = JSON.parse(firstLine);
    if (meta.type === "session_meta") {
      cwd = meta.payload?.cwd ?? cwd;
      origin = meta.payload?.originator ?? meta.payload?.source ?? origin;
    }
  } catch { /* not a session file */ }
  const at = text.lastIndexOf('"type":"token_count"');
  if (at === -1) return { cwd, origin, total: 0, cached: 0 };
  const start = text.lastIndexOf("\n", at) + 1;
  const end = text.indexOf("\n", at);
  try {
    const ev = JSON.parse(text.slice(start, end === -1 ? undefined : end));
    const u = ev.payload?.info?.total_token_usage ?? {};
    return { cwd, origin, total: u.total_tokens ?? 0, cached: u.cached_input_tokens ?? 0 };
  } catch {
    return { cwd, origin, total: 0, cached: 0 };
  }
}

function sessionTotals() {
  const now = Date.now();
  const startOfToday = new Date(); startOfToday.setHours(0, 0, 0, 0);
  const weekAgo = now - 7 * 24 * 3600 * 1000;
  const files = listSessionFiles(path.join(CODEX_HOME, "sessions"), weekAgo);
  const sum = { today: { total: 0, cached: 0, sessions: 0 }, week: { total: 0, cached: 0, sessions: 0 } };
  const byProject = new Map();
  for (const f of files) {
    const s = readSession(f);
    if (!s) continue;
    const isToday = fs.statSync(f).mtimeMs >= startOfToday.getTime();
    for (const [key, on] of [["week", true], ["today", isToday]]) {
      if (!on) continue;
      sum[key].total += s.total; sum[key].cached += s.cached; sum[key].sessions += 1;
    }
    const p = byProject.get(s.cwd) ?? { total: 0, sessions: 0, origins: new Map() };
    p.total += s.total; p.sessions += 1;
    p.origins.set(s.origin, (p.origins.get(s.origin) ?? 0) + 1);
    byProject.set(s.cwd, p);
  }
  const projects = [...byProject.entries()]
    .sort((a, b) => b[1].total - a[1].total)
    .map(([cwd, p]) => ({ cwd, total: p.total, sessions: p.sessions, origins: Object.fromEntries(p.origins) }));
  return { ...sum, projects };
}

const human = (n) => n >= 1e6 ? `${(n / 1e6).toFixed(1)} M` : n >= 1e3 ? `${Math.round(n / 1e3)} k` : String(n);

// --- Output ---------------------------------------------------------------
const limits = await readLimits();

if (MODE === "brief") {
  if (limits.error) {
    console.log(`plan limits unavailable (${limits.error})`);
  } else {
    const parts = [limits.primary, limits.secondary].filter(Boolean)
      .map((w) => `${w.label} limit ${w.usedPercent}% used, resets ${w.resets}`);
    console.log(parts.length ? parts.join("; ") : `no limit window reported (plan ${limits.plan})`);
  }
  process.exit(0);
}

const totals = sessionTotals();

if (MODE === "json") {
  console.log(JSON.stringify({ limits, totals, dashboard: DASHBOARD }, null, 2));
  process.exit(0);
}

const lines = [];
if (limits.error) {
  lines.push(`Plan limits: unavailable - ${limits.error}. Check "codex login status".`);
} else {
  lines.push(`Plan: ${limits.plan}`);
  for (const w of [limits.primary, limits.secondary].filter(Boolean)) {
    lines.push(`${w.label[0].toUpperCase()}${w.label.slice(1)} limit: ${w.usedPercent}% used, resets ${w.resets}`);
  }
  if (!limits.secondary && limits.primary?.label !== "5-hour") lines.push("5-hour limit: none on this plan");
  lines.push(`Limit-reset credits available: ${limits.resetCredits}`);
  if (limits.limitReached) lines.push(`LIMIT REACHED: ${limits.limitReached}`);
}
lines.push(`Tokens today: ${human(totals.today.total)} (${human(totals.today.cached)} cached input) in ${totals.today.sessions} sessions`);
lines.push(`Tokens last 7 days: ${human(totals.week.total)} (${human(totals.week.cached)} cached input) in ${totals.week.sessions} sessions`);
for (const p of totals.projects.slice(0, 5)) {
  const origins = Object.entries(p.origins).map(([o, n]) => `${o} ${n}`).join(", ");
  lines.push(`  ${human(p.total)} - ${p.cwd} (${p.sessions} sessions: ${origins})`);
}
lines.push(`Dashboard: ${DASHBOARD}`);
console.log(lines.join("\n"));
process.exit(0);
