/* Minimal Chrome DevTools Protocol driver.
 *
 * Node 22+ ships a built-in WebSocket client, so verifying the UI needs no npm
 * install at all. Used to:
 *   - screenshot each screen at a phone viewport for the README/DEV post
 *   - fail loudly on console errors and unhandled rejections
 *   - report the exact element causing horizontal overflow
 *
 * Usage:
 *   node scripts/ui_check.mjs [--port 9222] [--width 430] [--height 932]
 *                             [--out DIR] [--url URL]
 */

import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';

const CHROME_CANDIDATES = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  '/usr/bin/google-chrome',
  '/usr/bin/chromium',
  '/usr/bin/chromium-browser',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
];

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const PORT = parseInt(arg('port', '9333'), 10);
const WIDTH = parseInt(arg('width', '430'), 10);
const HEIGHT = parseInt(arg('height', '932'), 10);
const OUT = arg('out', 'docs/media');
const BASE = arg('url', 'http://127.0.0.1:8000/');

const SHOTS = [
  { name: '01-ask', url: BASE, settle: 1200 },
  { name: '02-brief', url: `${BASE}?auto=1&model=template`, settle: 9000 },
  { name: '03-pocket', url: `${BASE}?model=template#pocket`, settle: 9000 },
];

function findChrome() {
  const override = arg('chrome', '');
  const candidates = override ? [override, ...CHROME_CANDIDATES] : CHROME_CANDIDATES;
  for (const p of candidates) {
    if (existsSync(p)) return p;
  }
  throw new Error(
    'No Chrome/Edge binary found. Pass one explicitly:\n' +
    '  node scripts/ui_check.mjs --chrome "/path/to/chrome"\n' +
    'Looked in:\n  ' + candidates.join('\n  '),
  );
}

async function main() {
  mkdirSync(OUT, { recursive: true });

  const bin = findChrome();
  const child = spawn(bin, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--hide-scrollbars',
    '--user-data-dir=' + (process.env.TEMP || '.') + '/baahar-cdp-profile',
    'about:blank',
  ], { stdio: 'ignore' });

  // Wait for the debugger endpoint.
  let wsUrl = null;
  for (let i = 0; i < 60 && !wsUrl; i++) {
    await sleep(250);
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const tabs = await res.json();
      const page = tabs.find((t) => t.type === 'page');
      if (page) wsUrl = page.webSocketDebuggerUrl;
    } catch { /* not up yet */ }
  }
  if (!wsUrl) { child.kill(); throw new Error('Chrome debugger never came up'); }

  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let id = 0;
  const pending = new Map();
  const consoleErrors = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      return;
    }
    if (msg.method === 'Runtime.exceptionThrown') {
      consoleErrors.push('EXCEPTION ' + JSON.stringify(msg.params.exceptionDetails.text));
    }
    if (msg.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(msg.params.type)) {
      consoleErrors.push(msg.params.type.toUpperCase() + ' ' +
        msg.params.args.map((a) => a.value ?? a.description ?? '').join(' '));
    }
  };
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const mid = ++id;
      pending.set(mid, { resolve, reject });
      ws.send(JSON.stringify({ id: mid, method, params }));
    });

  await send('Runtime.enable');
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', {
    width: WIDTH, height: HEIGHT, deviceScaleFactor: 2, mobile: true,
  });

  const results = [];

  for (const shot of SHOTS) {
    await send('Page.navigate', { url: shot.url });
    await sleep(shot.settle);

    // Layout audit: overflow, hidden-attribute violations, missing text.
    const audit = await send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(() => {
        const de = document.documentElement;
        const overflow = de.scrollWidth - de.clientWidth;
        const scrollRoots = [...document.querySelectorAll('*')].filter((el) => {
          const s = getComputedStyle(el);
          return s.overflowX === 'auto' || s.overflowX === 'scroll';
        });
        const insideScroller = (el) => scrollRoots.some((r) => r.contains(el));
        const wide = [];
        for (const el of document.querySelectorAll('body *')) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && r.right > de.clientWidth + 1 && !insideScroller(el)) {
            wide.push((el.id || el.className || el.tagName) + ' right=' + Math.round(r.right));
          }
        }
        // "hidden" is only a hint; an author display: rule can override it, so
        // measure what is actually painted.
        const rendered = (id) => {
          const el = document.getElementById(id);
          if (!el) return 'absent';
          const cs = getComputedStyle(el);
          if (cs.display === 'none' || cs.visibility === 'hidden') return 'not-rendered';
          return el.getBoundingClientRect().height > 0 ? 'VISIBLE' : 'zero-height';
        };
        return {
          scrollWidth: de.scrollWidth,
          clientWidth: de.clientWidth,
          overflow,
          offenders: wide.slice(0, 6),
          screens: {
            loading: rendered('loading'),
            briefBody: rendered('brief-body'),
            pocket: rendered('screen-pocket'),
            failsafe: rendered('failsafe'),
          },
          decision: (document.getElementById('decision') || {}).textContent || null,
        };
      })()`,
    });

    const png = await send('Page.captureScreenshot', {
      format: 'png', captureBeyondViewport: false,
    });
    const path = `${OUT}/${shot.name}.png`;
    writeFileSync(path, Buffer.from(png.data, 'base64'));

    results.push({ shot: shot.name, ...audit.result.value, file: path });
    console.log(`\n▸ ${shot.name}`);
    console.log(`  file            ${path}`);
    console.log(`  scrollWidth     ${audit.result.value.scrollWidth} (viewport ${audit.result.value.clientWidth})`);
    console.log(`  overflow        ${audit.result.value.overflow}px`);
    if (audit.result.value.offenders.length) {
      console.log(`  offenders       ${audit.result.value.offenders.join(' | ')}`);
    }
    console.log(`  screens         ${JSON.stringify(audit.result.value.screens)}`);
    console.log(`  decision        ${audit.result.value.decision}`);
  }

  ws.close();
  child.kill();

  console.log('\n── console errors ──');
  console.log(consoleErrors.length ? consoleErrors.join('\n') : '(none)');

  const overflowed = results.filter((r) => r.overflow > 1 || r.offenders.length);
  const stuck = results.filter(
    (r) => Object.values(r.screens).includes('VISIBLE') && r.shot === '03-pocket'
      ? false
      : false,
  );
  // Screen-specific expectations.
  const problems = [];
  if (results[1].screens.loading === 'VISIBLE') problems.push('02-brief: loading spinner still painted');
  if (results[1].screens.briefBody !== 'VISIBLE') problems.push('02-brief: brief body not rendered');
  if (results[2].screens.pocket !== 'VISIBLE') problems.push('03-pocket: pocket screen not rendered');
  if (results[2].screens.failsafe === 'VISIBLE') problems.push('03-pocket: failsafe showing early');

  console.log('');
  if (overflowed.length || problems.length || consoleErrors.length) {
    if (overflowed.length) problems.push(`overflow on ${overflowed.map((r) => r.shot).join(', ')}`);
    if (consoleErrors.length) problems.push(`${consoleErrors.length} console error(s)`);
    console.log('RESULT: FAIL');
    problems.forEach((p) => console.log(`  - ${p}`));
    process.exitCode = 1;
  } else {
    console.log('RESULT: PASS');
  }
  void stuck;
}

main().catch((e) => { console.error('ui_check failed:', e.message); process.exit(2); });