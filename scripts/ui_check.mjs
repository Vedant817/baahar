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
import { existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
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
  { name: '01-ask', url: BASE, ready: 'screen-ask', wait: 1500 },
  { name: '02-brief', url: `${BASE}?auto=1&model=template`, ready: 'brief-body', wait: 30000 },
  { name: '03-pocket', url: `${BASE}?model=template#pocket`, ready: 'screen-pocket', wait: 30000 },
  {
    // Cycle the shuffle button to the end of the cue pool. This is the only way a
    // seasonal cue is ever seen, so it is the only way the credit line is ever
    // seen -- and the check that it appears *only* then.
    name: '03b-pocket-seasonal',
    url: `${BASE}?model=template#pocket`,
    ready: 'screen-pocket',
    wait: 30000,
    afterReady: async (send) => {
      await send('Runtime.evaluate', {
        expression: `(() => {
          const btn = document.getElementById('next-cue');
          for (let i = 0; i < 8 && btn && btn.style.display !== 'none'; i++) {
            btn.click();
          }
        })()`,
      });
      await sleep(300);
    },
  },
  {
    // `walk=0` is not allowed by the API, so the shortest walk is used and the
    // timer is expired programmatically. Verifying the journal must not require
    // waiting out a real walk.
    name: '04-journal',
    url: `${BASE}?model=template&journal=1`,
    ready: 'journal',
    wait: 40000,
    afterReady: async (send) => {
      await send('Runtime.evaluate', {
        expression: `(() => {
          const el = document.getElementById('j-count');
          el.textContent = '2';
          document.getElementById('j-note').value =
            'kept reaching for the phone around minute six';
          document.querySelector('.jbtn[data-outcome="went"]').click();
        })()`,
      });
      await sleep(300);
    },
  },
  {
    // Reach a seasonal cue, then open the journal. The species question only
    // appears if one was actually shown, so this is the only path where it can
    // be screenshotted -- or asserted.
    name: '05-journal-species',
    url: `${BASE}?model=template&journal=1`,
    ready: 'screen-pocket',
    wait: 30000,
    afterReady: async (send) => {
      await send('Runtime.evaluate', {
        expression: `(() => {
          const btn = document.getElementById('next-cue');
          for (let i = 0; i < 8 && btn && btn.style.display !== 'none'; i++) btn.click();
          // openJournal() already ran for ?journal=1, before any cue was shown,
          // so the species block is still hidden. Reveal it the way a real walk
          // would, then answer it.
          if (typeof syncSpeciesQuestion === 'function') syncSpeciesQuestion();
          document.getElementById('j-count').textContent = '1';
          document.querySelector('.jbtn[data-saw="yes"]').click();
          document.querySelector('.jbtn[data-outcome="went"]').click();
        })()`,
      });
      await sleep(400);
    },
  },
];

/* Poll for a screen to actually render instead of sleeping a fixed amount.
 * A fixed delay is a race: it passed on a quiet machine and failed while an
 * eval was running in parallel, which is exactly the kind of flake that makes a
 * CI check worthless. */
async function waitForRender(send, id, budgetMs) {
  const deadline = Date.now() + budgetMs;
  let last = null;
  while (Date.now() < deadline) {
    const probe = await send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(() => {
        const el = document.getElementById(${JSON.stringify(id)});
        if (!el) return 'absent';
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') return 'not-rendered';
        return el.getBoundingClientRect().height > 0 ? 'VISIBLE' : 'zero-height';
      })()`,
    });
    last = probe.result.value;
    if (last === 'VISIBLE') return { ok: true, waited: true, state: last };
    await sleep(250);
  }
  return { ok: false, waited: true, state: last };
}

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

  // A fresh profile per run. A reused one lets Chrome serve a cached index.html
  // or app.js from a previous run, which means the audit can quietly verify
  // stale markup and pass while the live page is broken. That is the worst kind
  // of green.
  const profile = join(
    process.env.TEMP || '.',
    `baahar-cdp-profile-${process.pid}`,
  );
  rmSync(profile, { recursive: true, force: true });

  const bin = findChrome();
  const child = spawn(bin, [
    '--headless=new',
    `--remote-debugging-port=${PORT}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--hide-scrollbars',
    '--user-data-dir=' + profile,
    'about:blank',
  ], { stdio: 'ignore' });

  // Wait for the debugger endpoint.
  //
  // 120s, not 15s. On a cold GitHub runner, first-launch Chrome with a brand-new
  // profile takes noticeably longer than on a warm dev machine, and the previous
  // 15s budget failed the whole UI job with "Chrome debugger never came up" --
  // which says nothing about the thing the job exists to check. A generous
  // ceiling costs nothing when Chrome starts in two seconds.
  const DEBUGGER_BUDGET_MS = 120000;
  let wsUrl = null;
  const started = Date.now();
  let lastError = '';
  while (Date.now() - started < DEBUGGER_BUDGET_MS && !wsUrl) {
    await sleep(250);
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const tabs = await res.json();
      const page = tabs.find((t) => t.type === 'page');
      if (page) wsUrl = page.webSocketDebuggerUrl;
    } catch (e) {
      lastError = e.message || String(e);
    }
  }
  if (!wsUrl) {
    child.kill();
    throw new Error(
      `Chrome debugger never came up after ${DEBUGGER_BUDGET_MS}ms. ` +
      `Binary: ${bin}. Last probe error: ${lastError || 'none'}. ` +
      'On CI, check that Chrome is installed and that the runner is not ' +
      'memory-starved -- headless Chrome with a fresh profile is the first ' +
      'thing to get OOM-killed.',
    );
  }

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
    const ready = await waitForRender(send, shot.ready, shot.wait);
    if (shot.afterReady) await shot.afterReady(send);
    await sleep(400); // let layout settle before capture

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
              journal: rendered('journal'),
              journalDone: rendered('j-done'),
              speciesQ: rendered('j-species'),
            },
            // The data-source credit line must appear only while a seasonal cue
            // is actually on screen. Shown under a hand-written cue it would
            // claim a provenance the cue does not have.
            seasonalNote: rendered('p-seasonal'),
            cue: (document.getElementById('p-cue') || {}).textContent || '',
            evidence: (document.getElementById('p-seasonal') || {}).textContent || '',
            markdown: (document.getElementById('j-md') || {}).textContent || '',
            decision: (document.getElementById('decision') || {}).textContent || null,
          };
      })()`,
    });

    const png = await send('Page.captureScreenshot', {
      format: 'png', captureBeyondViewport: false,
    });
    const path = `${OUT}/${shot.name}.png`;
    writeFileSync(path, Buffer.from(png.data, 'base64'));

    results.push({
      shot: shot.name,
      ...audit.result.value,
      waitedFor: shot.ready,
      readyState: ready.state,
      file: path,
    });
    console.log(`\n▸ ${shot.name}`);
    console.log(`  file            ${path}`);
    console.log(`  waited for      ${shot.ready} -> ${ready.state}`);
    console.log(`  scrollWidth     ${audit.result.value.scrollWidth} (viewport ${audit.result.value.clientWidth})`);
    console.log(`  overflow        ${audit.result.value.overflow}px`);
    if (audit.result.value.offenders.length) {
      console.log(`  offenders       ${audit.result.value.offenders.join(' | ')}`);
    }
    console.log(`  screens         ${JSON.stringify(audit.result.value.screens)}`);
    console.log(`  credit line     ${audit.result.value.seasonalNote}`);
    console.log(`  cue             ${audit.result.value.cue}`);
    if (audit.result.value.evidence) {
      console.log(`  evidence        ${audit.result.value.evidence}`);
    }
    if (audit.result.value.markdown) {
      const first = audit.result.value.markdown.split('\n').find((l) => l.includes('Species cue'));
      if (first) console.log(`  journal         ${first.trim()}`);
    }
    console.log(`  decision        ${audit.result.value.decision}`);
  }

  ws.close();
  child.kill();
  // Best effort. Chrome has not necessarily released the profile directory by
  // the time `kill` returns, and a locked profile on Windows would otherwise
  // fail the whole audit after every check has already passed.
  await sleep(300);
  try {
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  } catch { /* a stale temp profile is harmless */ }

  console.log('\n── console errors ──');
  console.log(consoleErrors.length ? consoleErrors.join('\n') : '(none)');

  const overflowed = results.filter((r) => r.overflow > 1 || r.offenders.length);
  const stuck = results.filter(
    (r) => Object.values(r.screens).includes('VISIBLE') && r.shot === '03-pocket'
      ? false
      : false,
  );
  // Screen-specific expectations. Indexed by name rather than position, so
  // inserting a shot cannot silently shift every assertion down one.
  const shot = Object.fromEntries(results.map((r) => [r.shot, r]));

  // Pocket Mode only renders when the brief authorises a walk *now*, and
  // recorded fixtures can never do that: `walk.eligibility` refuses recorded
  // data as permission (see commit a9bdfbd). So the four shots that start on
  // the pocket screen are auditable only on a live GO hour.
  //
  // When the verdict is not GO, report those screens as SKIPPED with the
  // reason. A red build over the weather is as useless as an audit that
  // quietly stops covering three screens, so the failure and the skip are
  // both made explicit rather than either being silent.
  const pocketReachable = shot['03-pocket'].screens.pocket === 'VISIBLE';
  const notAudited = [];
  if (!pocketReachable) {
    const verdict = shot['02-brief'].decision || 'unknown verdict';
    for (const name of ['03-pocket', '03b-pocket-seasonal', '04-journal', '05-journal-species']) {
      notAudited.push(`${name}: not audited, brief said ${verdict} and Pocket Mode was not authorised`);
    }
  }

  const problems = [];
  if (shot['02-brief'].screens.loading === 'VISIBLE') {
    problems.push('02-brief: loading spinner still painted');
  }
  if (shot['02-brief'].screens.briefBody !== 'VISIBLE') {
    problems.push('02-brief: brief body not rendered');
  }
  if (pocketReachable) {
    for (const name of ['03-pocket', '03b-pocket-seasonal']) {
      if (shot[name].screens.pocket !== 'VISIBLE') problems.push(`${name}: pocket screen not rendered`);
    }
  }

  // The credit line follows the cue: hidden on a hand-written cue, visible on a
  // seasonal one. Both halves matter -- a missing line under a data-backed claim
  // hides where it came from, and a visible line under a hand-written cue invents
  // a source for it.
  const firstPocket = shot['03-pocket'];
  const seasonalShot = shot['03b-pocket-seasonal'];
  if (pocketReachable && firstPocket.seasonalNote === 'VISIBLE') {
    problems.push('03-pocket: data-source credit shown under a hand-written cue');
  }
  if (pocketReachable) {
    if (seasonalShot.seasonalNote !== 'VISIBLE') {
      problems.push('03b-pocket-seasonal: no data-source credit on the seasonal cue');
    }
    if (!/^Look for an? [A-Z]/.test(seasonalShot.cue)) {
      problems.push(`03b-pocket-seasonal: shuffle did not reach a seasonal cue (showed "${seasonalShot.cue}")`);
    }
    if (!/research grade/i.test(seasonalShot.evidence)) {
      problems.push(`03b-pocket-seasonal: credit line does not name the data source (showed "${seasonalShot.evidence}")`);
    }
    if (!/not that you will see/i.test(seasonalShot.evidence)) {
      problems.push('03b-pocket-seasonal: credit line is missing the "a record is not a promise" caveat');
    }
  }

  if (pocketReachable) {
    if (shot['04-journal'].screens.journal !== 'VISIBLE') {
      problems.push('04-journal: after-walk journal not rendered');
    }
    if (shot['04-journal'].screens.journalDone !== 'VISIBLE') {
      problems.push('04-journal: journal markdown did not appear after tapping an outcome');
    }
    // The species question must stay hidden unless a seasonal cue was actually
    // shown during the walk. This journal screen is reached without walking, so
    // asking would collect an answer about a suggestion nobody was given.
    if (shot['04-journal'].screens.speciesQ === 'VISIBLE') {
      problems.push('04-journal: species question shown without a seasonal cue');
    }

    // And the converse: after a seasonal cue was reached, the question must appear.
    const speciesShot = shot['05-journal-species'];
    if (speciesShot.screens.speciesQ !== 'VISIBLE') {
      problems.push('05-journal-species: species question missing after a seasonal cue');
    }
    if (!/Chocolate Pansy|Gecko|mulberry|Brahminy|Toad|Squirrel|Spider/.test(speciesShot.markdown || '')) {
      problems.push(
        `05-journal-species: journal markdown does not name the suggested species (showed "${(speciesShot.markdown || '').slice(0, 80)}")`,
      );
    }
  }

  console.log('');
  if (notAudited.length) {
    console.log('── not audited (recorded data cannot authorise a walk) ──');
    notAudited.forEach((s) => console.log(`  SKIPPED ${s}`));
  }
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