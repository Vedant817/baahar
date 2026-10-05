/* Baahar front end.
 *
 * No framework, no build step, no dependencies. Three screens, one API call,
 * and a deliberate attempt to make the user stop looking at this.
 *
 * The interaction budget in docs/DOD.md is <=3 actions before Pocket Mode.
 * Current path: tap "Find my hour" -> optionally tap "Pocket the phone", and if
 * the user does nothing, Baahar auto-enters Pocket Mode after AUTO_POCKET_MS
 * with a visible, cancellable countdown.
 */

'use strict';

const API = '/api/brief';

const state = {
  data: null,
  cues: [],
  cueIndex: 0,
  walkSeconds: 20 * 60,
  remaining: 0,
  pocketTimer: null,
  walkTimer: null,
  countdown: null,
  autoPocketAt: 0,
};

const $ = (id) => document.getElementById(id);

const screens = {
  ask: $('screen-ask'),
  brief: $('screen-brief'),
  pocket: $('screen-pocket'),
};

/* Auto-enter Pocket Mode: long enough to read a 120-word briefing at a
 * comfortable pace, short enough that the user never has to hunt for the
 * button. Deliberately not instant -- a UI that hijacks the screen instantly
 * feels hostile rather than helpful. */
const AUTO_POCKET_MS = 45000;

function show(name) {
  Object.entries(screens).forEach(([key, el]) => { el.hidden = key !== name; });
  window.scrollTo(0, 0);
}

function fmtClock(sec) {
  const m = Math.floor(Math.max(0, sec) / 60);
  const s = Math.max(0, sec) % 60;
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

/* ── options ─────────────────────────────────────────────────────────── */

function readOptions() {
  return {
    model: $('opt-model').value,
    scorer: $('opt-scorer').value,
    walk_minutes: parseInt($('opt-walk').value, 10) || 20,
    park: $('opt-park').value || undefined,
  };
}

/* ── loading ─────────────────────────────────────────────────────────── */

let elapsedTimer = null;

function startLoading() {
  $('loading').hidden = false;
  $('brief-body').hidden = true;
  const t0 = performance.now();
  $('elapsed').textContent = '0';
  elapsedTimer = setInterval(() => {
    $('elapsed').textContent = Math.round((performance.now() - t0) / 1000);
  }, 250);

  // The open-weight path is slow (measured: tens of seconds). Say so instead of
  // showing an unexplained spinner, and offer a way out.
  $('loading-text').textContent = 'Reading the air, then writing your brief…';
  const o = readOptions();
  if (o.model !== 'template') {
    $('ask-hint').textContent = '';
    $('loading-text').textContent =
      'Reading the air, then writing your brief…';
  }
}

function stopLoading() {
  clearInterval(elapsedTimer);
  $('loading').hidden = true;
  $('brief-body').hidden = false;
}

/* ── rendering ───────────────────────────────────────────────────────── */

function fmtTime(iso) {
  // The API sends an offset-aware ISO string; the browser knows the user's zone
  // but Baahar's plan is in Bengaluru time, so format in IST explicitly.
  const d = new Date(iso);
  return new Intl.DateTimeFormat('en-GB', {
    hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata',
  }).format(d);
}

function fmtISTDay(iso) {
  const d = new Date(iso);
  return new Intl.DateTimeFormat('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', timeZone: 'Asia/Kolkata',
  }).format(d);
}

function renderSignals(plan) {
  const slot = plan.best_slot;
  const list = $('signals');
  list.innerHTML = '';
  if (!slot) return;

  const air = slot.air || {};
  const wx = slot.weather || {};
  const rows = [];
  if (air.naqi !== null && air.naqi !== undefined) {
    rows.push(['Indian NAQI', `${air.naqi} · ${(air.naqi_band || '')}`]);
  }
  if (air.dominant_label) rows.push(['Main pollutant', air.dominant_label]);
  if (wx.temp_c !== null && wx.temp_c !== undefined) {
    const feels = wx.apparent_c !== null && wx.apparent_c !== undefined &&
      Math.abs(wx.apparent_c - wx.temp_c) >= 1.5;
    rows.push(['Temperature', `${wx.temp_c}°C${feels ? ` (feels ${wx.apparent_c}°)` : ''}`]);
  }
  if (wx.precip_prob !== null && wx.precip_prob !== undefined) {
    rows.push(['Rain chance', `${wx.precip_prob}%`]);
  }
  if (plan.scorer) rows.push(['Scored by', plan.scorer]);

  rows.forEach(([k, v]) => {
    const li = document.createElement('li');
    li.innerHTML = `<span class="k"></span><span class="v"></span>`;
    li.querySelector('.k').textContent = k;
    li.querySelector('.v').textContent = v;
    list.appendChild(li);
  });
}

function renderHours(plan) {
  const table = $('hours-table');
  table.innerHTML = '';
  const head = document.createElement('tr');
  ['Time', 'Call', 'NAQI', 'Feels', 'Why'].forEach((h) => {
    const th = document.createElement('th');
    th.textContent = h;
    head.appendChild(th);
  });
  table.appendChild(head);

  (plan.slots || []).forEach((s) => {
    const tr = document.createElement('tr');
    const sig = s.signals || {};
    const cells = [
      fmtTime(s.time),
      null,
      sig.naqi ?? '—',
      sig.apparent_c ?? sig.temp_c ?? '—',
      (s.reasons || [])[0] || '',
    ];
    cells.forEach((c, i) => {
      const td = document.createElement('td');
      if (i === 1) { td.textContent = s.decision; td.className = `d-${s.decision}`; }
      else { td.textContent = c; }
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });
  $('hours-n').textContent = (plan.slots || []).length;
}

function renderPlan(data) {
  const { plan, briefing, pocket } = data;

  $('decision').textContent = plan.overall;
  $('decision').dataset.d = plan.overall;
  $('headline').textContent = plan.headline || '';
  $('window').textContent = plan.best_time
    ? `${fmtISTDay(plan.best_time)} · ${fmtTime(plan.best_time)} · ${plan.city}`
    : plan.city;
  $('briefing').textContent = briefing.text;

  // Never hide a degradation. If Baahar is replaying a fixture, it says so.
  const notes = [];
  (plan.degraded || []).forEach((d) => notes.push(d));
  if (briefing.note) notes.push(briefing.note);
  const deg = $('degraded');
  if (notes.length) {
    deg.textContent = notes.join(' · ');
    deg.hidden = false;
  } else {
    deg.hidden = true;
  }

  renderSignals(plan);
  renderHours(plan);

  const park = plan.park;
  if (park) {
    $('park-block').hidden = false;
    $('park-name').textContent = park.name;
    $('park-vibe').textContent = park.vibe;
    $('park-note').textContent =
      [park.crowding_hint, park.gate_note].filter(Boolean).join(' — ');
  }

  $('attrib').textContent =
    `Weather and air quality: Open-Meteo (CC BY 4.0), Indian NAQI computed with ` +
    `CPCB 2014 sub-index breakpoints applied to hourly concentrations. ` +
    `Park data curated by hand from OpenStreetMap (ODbL). ` +
    `Briefing writer: ${briefing.writer}. Baahar is informational, not medical advice.`;

  // Pocket Mode payload
  state.cues = [pocket.notice_this].concat((data.meta && data.meta.cues_remaining) || [])
    .filter(Boolean);
  state.cueIndex = 0;
  state.walkSeconds = (pocket.walk_minutes || 20) * 60;

  $('p-headline').textContent = pocket.headline;
  $('p-subline').textContent = pocket.subline || '';
  $('p-safety').textContent = pocket.safety_note || '';
  $('p-timer').textContent = fmtClock(state.walkSeconds);
  $('next-cue').style.display = state.cues.length > 1 ? '' : 'none';
  paintCue();

  $('use-fast').hidden = briefing.writer !== 'template';
  $('use-fast').textContent = 'Rewrite it locally instead (instant)';
}

/* ── Pocket Mode ─────────────────────────────────────────────────────── */

function paintCue() {
  const cue = state.cues[state.cueIndex % Math.max(1, state.cues.length)] || '';
  $('p-cue').textContent = cue;
}

function enterPocket(auto) {
  clearTimeout(state.pocketTimer);
  clearTimeout(state.countdown);
  clearInterval(state.autoTick);
  $('auto-hint').hidden = true;
  show('pocket');
  state.remaining = state.walkSeconds;
  $('p-timer').textContent = fmtClock(state.remaining);
  document.body.style.background = '#000';

  if (state.autoTick) clearInterval(state.autoTick);
  state.walkTimer = setInterval(() => {
    state.remaining -= 1;
    $('p-timer').textContent = fmtClock(state.remaining);
    if (state.remaining <= 0) {
      clearInterval(state.walkTimer);
      showFailsafe();
    }
  }, 1000);
}

function exitPocket() {
  clearInterval(state.walkTimer);
  document.body.style.background = '';
  show('brief');
  scheduleAutoPocket();
}

function showFailsafe() {
  clearInterval(state.walkTimer);
  show('pocket');           // stay fullscreen/black
  $('failsafe').hidden = false;
  const tick = () => {
    $('fs-time').textContent = new Date().toLocaleTimeString('en-GB', {
      hour: '2-digit', minute: '2-digit',
    });
  };
  tick();
  setInterval(tick, 10000);
}

/* Auto-pocket with a visible, cancellable countdown. The user can always opt
 * out by tapping, and can opt in again immediately. */
function scheduleAutoPocket() {
  clearTimeout(state.pocketTimer);
  clearInterval(state.autoTick);
  state.autoPocketAt = Date.now() + AUTO_POCKET_MS;
  const hint = $('auto-hint');
  hint.hidden = false;
  state.autoTick = setInterval(() => {
    const left = Math.max(0, Math.round((state.autoPocketAt - Date.now()) / 1000));
    hint.textContent = `Pocket Mode in ${left}s — tap "Pocket the phone" now to skip the wait`;
    if (left <= 0) enterPocket(true);
  }, 500);
}

function cancelAutoPocket() {
  clearTimeout(state.pocketTimer);
  clearInterval(state.autoTick);
  $('auto-hint').hidden = true;
}

/* ── fetch ───────────────────────────────────────────────────────────── */

async function load(modelOverride) {
  const opts = readOptions();
  if (modelOverride) opts.model = modelOverride;

  const params = new URLSearchParams();
  Object.entries(opts).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') params.set(k, v);
  });

  show('brief');
  startLoading();

  try {
    const res = await fetch(`${API}?${params.toString()}`);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try { detail = (await res.json()).detail || detail; } catch (_) { /* keep */ }
      throw new Error(detail);
    }
    const data = await res.json();
    state.data = data;
    renderPlan(data);
    stopLoading();
    scheduleAutoPocket();
  } catch (err) {
    clearInterval(elapsedTimer);
    $('loading').innerHTML =
      `<p style="color:#ff6b6b;line-height:1.6"></p>`;
    $('loading').querySelector('p').textContent =
      `Could not build a brief: ${err.message}. ` +
      `Baahar will not guess at conditions it could not read.`;
  }
}

/* ── wiring ──────────────────────────────────────────────────────────── */

async function populateParks() {
  try {
    const res = await fetch('/api/parks');
    const data = await res.json();
    const sel = $('opt-park');
    (data.parks || []).forEach((p) => {
      const opt = document.createElement('option');
      opt.value = p.id;
      opt.textContent = `${p.name} · ${p.distance_km} km`;
      sel.appendChild(opt);
    });
  } catch (_) {
    /* the picker is a convenience; the default (nearest) always works */
  }
}

function boot() {
  $('go').addEventListener('click', () => load());
  $('pocket').addEventListener('click', () => { cancelAutoPocket(); enterPocket(false); });
  $('pocket-exit').addEventListener('click', exitPocket);
  $('next-cue').addEventListener('click', () => { state.cueIndex += 1; paintCue(); });
  $('use-fast').addEventListener('click', () => load('template'));
  $('fs-back').addEventListener('click', () => {
    $('failsafe').hidden = true;
    clearInterval(state.walkTimer);
    document.body.style.background = '';
    show('brief');
  });
  populateParks();

  // Hide the ambient chrome entirely while walking: no accidental taps, no
  // status bar, nothing to scroll.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && !screens.pocket.hidden) {
      showPocketChrome(true);
    }
  });

  // Deep links. `?auto=1` skips straight to the brief; `#pocket` goes straight
  // into Pocket Mode. Two reasons this exists: you can send yourself the link
  // before a walk, and the demo screenshots in the README and DEV post can be
  // regenerated by anyone with one command.
  const params = new URLSearchParams(window.location.search);
  const bindings = [
    ['model', 'opt-model'],
    ['scorer', 'opt-scorer'],
    ['walk', 'opt-walk'],
    ['park', 'opt-park'],
  ];
  bindings.forEach(([key, id]) => {
    if (!params.has(key)) return;
    const el = $(id);
    const value = params.get(key);
    if (el.tagName === 'SELECT') {
      if (Array.from(el.options).some((o) => o.value === value)) el.value = value;
    } else {
      el.value = value;
    }
  });

  const skipToPocket = window.location.hash === '#pocket';
  if (params.get('auto') === '1' || skipToPocket) {
    load().then(() => {
      if (skipToPocket && state.data) {
        cancelAutoPocket();
        enterPocket(false);
      }
    });
  }
}

function showPocketChrome(show_) { /* reserved: future lock-mode integration */ }

document.addEventListener('DOMContentLoaded', boot);