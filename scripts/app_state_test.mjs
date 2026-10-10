/* Unit tests for src/baahar/static/app.js, without a browser.
 *
 * Why this file exists: `scripts/ui_check.mjs` is the only other JS harness, and
 * it drives real Chrome against a live server. That is the right tool for
 * "does this screen overflow at 430px" and the wrong tool for "does leaving
 * Pocket Mode re-arm the countdown that just yanked you" -- the second question
 * is about a 45-second timer, and a screenshot audit cannot answer it without
 * waiting 45 seconds per assertion.
 *
 * So app.js is evaluated inside a minimal DOM stub with a controllable clock.
 * No npm install, no jsdom, no browser, no server, no network. The stub is
 * deliberately dumb: a test that needs a new capability has to name that
 * capability here, so this file cannot silently grow into a second browser.
 *
 * Run:
 *   node scripts/app_state_test.mjs
 *
 * Exits non-zero on failure, like every other check in this repo.
 */

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const APP_JS = join(ROOT, 'src', 'baahar', 'static', 'app.js');

/* ── a DOM small enough to read ──────────────────────────────────────────────
 *
 * Every property app.js touches on an element, and nothing else. */

class StubElement {
  constructor(id = '') {
    this.id = id;
    this.hidden = false;
    this.disabled = false;
    this.textContent = '';
    this.value = '';
    this.innerHTML = '';
    this.className = '';
    this.tagName = 'DIV';
    this.dataset = {};
    this.style = {};
    this.children = [];
    this.options = [];
    this.listeners = {};
  }

  addEventListener(type, fn) {
    (this.listeners[type] ||= []).push(fn);
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  querySelector() {
    return new StubElement();
  }

  querySelectorAll() {
    return [];
  }

  /* Fire a handler the way a tap would, so a test goes through the same path a
   * user does rather than calling the handler directly. */
  click() {
    (this.listeners.click || []).forEach((fn) => fn({}));
  }
}

/* A fake clock, because `scheduleAutoPocket` reads `Date.now()` and the whole
 * point of D3 is what happens across that span of time. Real timers would make
 * each test take 45 seconds and still not be deterministic.
 *
 * `Date` is subclassed rather than replaced so `new Date(iso)` in `fmtTime`
 * keeps working -- app.js needs both. */
function makeClock() {
  const base = Date.now();
  let elapsed = 0;
  const intervals = new Map();
  let nextId = 1;

  const clock = {
    advance(ms) {
      elapsed += ms;
    },
    setInterval(fn) {
      const id = nextId++;
      intervals.set(id, fn);
      return id;
    },
    clearInterval(id) {
      intervals.delete(id);
    },
    pending() {
      return intervals.size;
    },
    /* Run every live interval callback once, as if its period had elapsed. */
    tick() {
      for (const fn of [...intervals.values()]) fn();
    },
  };

  class FakeDate extends Date {
    static now() {
      return base + elapsed;
    }
  }

  clock.Date = FakeDate;
  return clock;
}

/* Build a fresh app.js over a stub DOM, a stub clock and a stub `/api/brief`.
 *
 * The script is re-evaluated per test so no state leaks between cases -- the
 * same reason the screenshot audit uses a fresh Chrome profile. */
function bootApp(briefPayload, location = { search: '', hash: '' }) {
  const clock = makeClock();
  const elements = new Map();
  const get = (id) => {
    if (!elements.has(id)) elements.set(id, new StubElement(id));
    return elements.get(id);
  };

  // The three screens must exist before app.js's body runs: it reads them at
  // load time to build `screens`.
  get('screen-ask');
  get('screen-brief');
  get('screen-pocket');

  const document = {
    getElementById: get,
    createElement: () => new StubElement(),
    querySelector: () => new StubElement(),
    querySelectorAll: () => [],
    addEventListener: () => {},
    body: new StubElement('body'),
    visibilityState: 'visible',
  };

  const storage = new Map();
  const requests = [];
  const sandbox = {
    document,
    window: {
      scrollTo: () => {},
      location,
      addEventListener: () => {},
    },
    localStorage: {
      getItem: (k) => (storage.has(k) ? storage.get(k) : null),
      setItem: (k, v) => storage.set(k, v),
    },
    performance: { now: () => clock.Date.now() },
    Intl,
    URLSearchParams,
    /* Only `/api/brief` is stubbed. `populateParks()` also fetches, but it
     * swallows its own failure, so an unknown URL returning a 404 exercises
     * that real code path rather than papering over it. */
    fetch: async (url) => {
      requests.push(url);
      if (!url.startsWith('/api/brief')) {
        return { ok: false, status: 404, json: async () => ({}) };
      }
      return { ok: true, status: 200, json: async () => briefPayload };
    },
    setTimeout: (fn) => clock.setInterval(fn),
    clearTimeout: (id) => clock.clearInterval(id),
    setInterval: (fn) => clock.setInterval(fn),
    clearInterval: (id) => clock.clearInterval(id),
    Date: clock.Date,
    console: { log: () => {}, warn: () => {}, error: () => {} },
  };
  sandbox.globalThis = sandbox;

  const context = vm.createContext(sandbox);
  const source = readFileSync(APP_JS, 'utf8');
  vm.runInContext(source, context, { filename: APP_JS });

  const names = [
    'state',
    'renderPlan',
    'load',
    'enterPocket',
    'exitPocket',
    'scheduleAutoPocket',
    'cancelAutoPocket',
    'applyPocketAvailability',
    'show',
    'AUTO_POCKET_MS',
    'boot',
  ];
  const app = {};
  for (const n of names) {
    try {
      app[n] = vm.runInContext(n, context);
    } catch {
      app[n] = undefined;
    }
  }
  if (typeof app.boot === 'function') {
    app.boot();
  }

  return { app, clock, get, requests };
}

/* The pocket gate in `enterPocket` only lowers the screen inside the fresh
 * current hour, exactly as it does for a real `/api/brief` payload. So the
 * fixture below has to carry the two timestamps the real endpoint returns.
 * Without them every GO case was quietly testing a stale plan the gate refuses
 * -- the entry assertions were green for the wrong reason until the gate landed.
 *
 * The clock is the harness's fake, so the hour is built from `Date.now()` at
 * payload time, which is within milliseconds of the fake clock's base. */
function freshHour(active) {
  const now = new Date().toISOString();
  return {
    generated_at: now,
    current_decision: active ? 'GO' : 'SKIP',
    current_slot: { time: now, decision: active ? 'GO' : 'SKIP' },
  };
}

/* Minimal payload shaped like `/api/brief`. Only the fields the code under test
 * reads are present, so a failure here means a real coupling broke. */
function payload({ active }) {
  return {
    plan: {
      overall: active ? 'GO' : 'SKIP',
      city: 'Bengaluru',
      headline: active ? 'Go at 06:30.' : 'Skip it. NAQI 320 is Severe or worse.',
      best_time: '2026-10-07T06:30:00+05:30',
      best_slot: null,
      slots: [],
      degraded: [],
      scorer: 'heuristic',
      park: null,
      ...freshHour(active),
    },
    briefing: { text: 'A brief.', writer: 'template', note: '' },
    pocket: {
      active,
      headline: active ? 'Phone in pocket.' : 'Stay in.',
      subline: active ? 'Look up. Walk Cubbon Park' : 'Baahar is not sending you out today.',
      walk_minutes: 20,
      notice_this: 'Listen for the first two birds.',
      park_name: 'Cubbon Park',
      safety_note: active ? 'Nothing unusual. Go enjoy it.' : 'Air is Severe today (NAQI 320)',
      seasonal_note: '',
    },
    meta: {},
    disclaimer: 'Informational only.',
  };
}

/* ── D2: the UI must honour `pocket.active` ─────────────────────────────── */

async function testSkipDisablesTheButton() {
  const { app, get } = bootApp(payload({ active: false }));
  await app.load();

  assert.equal(get('pocket').disabled, true, 'pocket button must be disabled on a SKIP');
}

async function testBlockedReasonIsVisibleAndUsesPayloadCopy() {
  const { app, get } = bootApp(payload({ active: false }));
  await app.load();

  const why = get('pocket-blocked');
  assert.equal(why.hidden, false, 'the reason must be visible, not a dead control');
  // The wording is the payload's, so it cannot drift from the verdict. app.js
  // writes no safety language of its own.
  assert.ok(
    why.textContent.includes('Stay in.'),
    `reason should carry the headline, got "${why.textContent}"`,
  );
  assert.ok(
    why.textContent.includes('Air is Severe today (NAQI 320)'),
    `reason should carry the safety note, got "${why.textContent}"`,
  );
}

async function testGoLeavesTheButtonUsable() {
  const { app, get } = bootApp(payload({ active: true }));
  await app.load();

  assert.equal(get('pocket').disabled, false, 'pocket button must stay enabled on a GO');
  assert.equal(get('pocket-blocked').hidden, true, 'no reason should show when it is available');
}

async function testSkipDoesNotArmTheAutoPocketCountdown() {
  const { app, get, clock } = bootApp(payload({ active: false }));
  await app.load();

  assert.equal(app.state.pocketActive, false, 'a SKIP must not mark pocket mode active');
  assert.equal(get('auto-hint').hidden, true, 'no countdown hint on a SKIP');
  // No walk or countdown timer may run on a SKIP.
  assert.equal(clock.pending(), 0, 'a SKIP must not leave any timer armed');

  // And prove the countdown really would have fired, so the assertion above is
  // not passing for the wrong reason.
  clock.advance(60_000);
  clock.tick();
  assert.equal(get('screen-pocket').hidden, true, 'nothing may enter Pocket Mode on a SKIP');
}

async function testGoStillArmsTheAutoPocketCountdown() {
  const { app, get, clock } = bootApp(payload({ active: true }));
  await app.load();

  assert.equal(get('auto-hint').hidden, false, 'the countdown hint should show on a GO');
  assert.equal(clock.pending(), 1, 'a GO should have exactly the auto-pocket tick armed');

  clock.advance(46_000);
  clock.tick();
  assert.equal(get('screen-pocket').hidden, false, 'the countdown should enter Pocket Mode');
}

async function testMissingActiveFlagIsNotPermission() {
  // A payload without `active` must not be able to enter a walk the backend
  // never agreed to, and must not throw on the way to rendering the brief.
  const incomplete = payload({ active: true });
  delete incomplete.pocket.active;
  const { app, get } = bootApp(incomplete);

  await app.load();
  assert.equal(app.state.pocketActive, false, 'an absent flag must read as not available');
  assert.equal(get('pocket').disabled, true);
  assert.equal(get('brief-body').hidden, false, 'the brief screen must still render');
}

async function testClickHandlerRefusesOnSkip() {
  const { app, get } = bootApp(payload({ active: false }));
  await app.load();

  const screen = get('screen-pocket');
  screen.hidden = true;
  get('pocket').click(); // a disabled button fires nothing in a browser

  assert.equal(screen.hidden, true, 'a click must not enter Pocket Mode on a SKIP');
}

async function testClickStillEntersOnGo() {
  const { app, get } = bootApp(payload({ active: true }));
  await app.load();

  const screen = get('screen-pocket');
  screen.hidden = true;
  get('pocket').click();

  assert.equal(screen.hidden, false, 'a click must still enter Pocket Mode on a GO');
}

/* ── D3: leaving Pocket Mode must not re-enter it ────────────────────────── */

async function testExitDoesNotRearmTheCountdown() {
  const { app, get, clock } = bootApp(payload({ active: true }));
  await app.load();
  assert.equal(clock.pending(), 1, 'precondition: the countdown is armed');

  app.enterPocket(false); // the countdown fires
  get('pocket-exit').click(); // the user backs out through the real handler

  assert.equal(clock.pending(), 0, 'exitPocket must cancel the countdown, not restart it');
}

async function testBriefScreenCountdownStillWorks() {
  const { app, get, clock } = bootApp(payload({ active: true }));
  await app.load();

  const screen = get('screen-pocket');
  screen.hidden = true;
  const hint = get('auto-hint');
  assert.equal(hint.hidden, false, 'the countdown hint should be visible on the brief screen');

  clock.advance(app.AUTO_POCKET_MS + 1_000);
  clock.tick();

  assert.equal(screen.hidden, false, 'the brief-screen countdown must still enter Pocket Mode');
  assert.match(hint.textContent, /Pocket Mode in \d+s/, `unexpected hint text "${hint.textContent}"`);
}

async function testExitThenAdvanceDoesNotReenter() {
  const { app, get, clock } = bootApp(payload({ active: true }));
  await app.load();

  app.enterPocket(false);
  get('pocket-exit').click();

  const screen = get('screen-pocket');
  assert.equal(screen.hidden, true, 'exit should show the brief screen');
  assert.equal(get('auto-hint').hidden, true, 'the auto-pocket hint should be gone');

  // Well past the re-arm the old code scheduled.
  clock.advance(120_000);
  clock.tick();
  assert.equal(screen.hidden, true, 'nothing may pull the user back in after they left');
}

async function testSkipRefusesDirectEntry() {
  const { app, get, clock } = bootApp(payload({ active: false }));
  await app.load();
  app.enterPocket(false);
  assert.equal(get('screen-pocket').hidden, true);
  assert.equal(get('screen-brief').hidden, false);
  assert.equal(clock.pending(), 0);
}

async function testSkipRefusesDirectCountdown() {
  const { app, get, clock } = bootApp(payload({ active: false }));
  await app.load();
  app.scheduleAutoPocket();
  assert.equal(get('auto-hint').hidden, true);
  assert.equal(clock.pending(), 0);
}

async function testSkipDeepLinksStayOnBrief() {
  for (const location of [
    { search: '', hash: '#pocket' },
    { search: '?journal=1', hash: '' },
  ]) {
    const { get, clock } = bootApp(payload({ active: false }), location);
    // Drain the mocked fetch/json promises and boot's load().then callback.
    for (let i = 0; i < 20; i++) await Promise.resolve();
    assert.equal(get('brief-body').hidden, false);
    assert.equal(get('screen-brief').hidden, false);
    assert.equal(get('screen-pocket').hidden, true);
    assert.equal(clock.pending(), 0);
  }
}

/* ── runner ──────────────────────────────────────────────────────────────── */

const tests = [
  ['D2 SKIP refuses direct Pocket Mode entry', testSkipRefusesDirectEntry],
  ['D2 SKIP refuses direct countdown scheduling', testSkipRefusesDirectCountdown],
  ['D2 SKIP deep links stay on the brief screen', testSkipDeepLinksStayOnBrief],
  ['D2 SKIP disables the pocket button', testSkipDisablesTheButton],
  ["D2 SKIP shows the payload's own reason", testBlockedReasonIsVisibleAndUsesPayloadCopy],
  ['D2 GO leaves the pocket button usable', testGoLeavesTheButtonUsable],
  ['D2 SKIP does not arm the auto-pocket countdown', testSkipDoesNotArmTheAutoPocketCountdown],
  ['D2 GO still arms the auto-pocket countdown', testGoStillArmsTheAutoPocketCountdown],
  ['D2 an absent active flag is not permission', testMissingActiveFlagIsNotPermission],
  ['D2 a click on SKIP does not enter', testClickHandlerRefusesOnSkip],
  ['D2 a click on GO still enters', testClickStillEntersOnGo],
  ['D3 exit does not re-arm the countdown', testExitDoesNotRearmTheCountdown],
  ['D3 the brief-screen countdown still fires', testBriefScreenCountdownStillWorks],
  ['D3 nothing re-enters after the user leaves', testExitThenAdvanceDoesNotReenter],
];

let failed = 0;
for (const [name, fn] of tests) {
  try {
    await fn();
    console.log(`  ok  ${name}`);
  } catch (err) {
    failed += 1;
    console.log(`  FAIL ${name}\n       ${String(err.message).split('\n')[0]}`);
  }
}

console.log('');
if (failed) {
  console.log(`RESULT: FAIL (${failed} of ${tests.length})`);
  process.exitCode = 1;
} else {
  console.log(`RESULT: PASS (${tests.length} app.js behaviour checks)`);
}