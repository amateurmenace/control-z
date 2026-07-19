/* The steward console: one page, no framework, no build step.
 *
 * Everything here is a thin, honest skin over record/steward.py. The thinking
 * about curation lives in memory/issues.py and the thinking about intake lives
 * in record/sources.py; if a screen in this file looks like it is only moving
 * JSON around, that is the intended shape. A console that re-implements the
 * rules is a console that will one day disagree with the thing that runs at
 * 3am, and the steward will believe the screen.
 *
 * Three decisions are worth stating.
 *
 * **The token lives in a variable and nowhere else.** Not localStorage, not a
 * cookie. A refresh signs you out and Google re-issues silently if it can.
 * The cost is a click; the benefit is that there is no persisted credential on
 * a steward's machine for anything to read, and no session state on ours.
 *
 * **Nothing is drawn with innerHTML from record data.** Municipal video titles
 * are arbitrary strings from the internet and they land in this page beside
 * buttons that spend money. `h()` builds nodes and text goes in as text, so
 * there is no path from a channel's title to executing markup — belt as well
 * as the CSP's braces.
 *
 * **Failures are printed, never swallowed.** Every call goes through `api()`,
 * which turns a non-2xx into an Error carrying the server's own sentence, and
 * every caller prints that sentence. A 503 means the console is unconfigured
 * and says which environment variable is missing; a 502 on preview means the
 * town's channel could not be reached and says so rather than showing three
 * empty lists, which would read as "this town posts nothing."
 */

'use strict';

// --------------------------------------------------------------------------
// the smallest possible DOM helper
// --------------------------------------------------------------------------

function h(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  const a = attrs || {};
  for (const k of Object.keys(a)) {
    const v = a[k];
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') n.className = v;
    else if (k === 'text') n.textContent = v;
    else if (k === 'value') n.value = v;
    else if (k === 'checked') n.checked = !!v;
    else if (k.slice(0, 2) === 'on') n.addEventListener(k.slice(2), v);
    else if (v === true) n.setAttribute(k, '');
    else n.setAttribute(k, String(v));
  }
  for (const kid of kids.flat(4)) {
    if (kid === null || kid === undefined || kid === false || kid === '') continue;
    n.appendChild(typeof kid === 'object' ? kid : document.createTextNode(String(kid)));
  }
  return n;
}

function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function $(id) { return document.getElementById(id); }

function when(ts) {
  if (!ts) return '';
  try { return new Date(ts * 1000).toLocaleString(); } catch (e) { return String(ts); }
}

function plural(n, one, many) { return n === 1 ? one : (many || one + 's'); }

// --------------------------------------------------------------------------
// state — small enough to hold in the head
// --------------------------------------------------------------------------

let TOKEN = '';        // the Google ID token. Memory only, deliberately.
let ME = null;         // {steward, name, verbs}
let TOWNS = [];        // the editable working copy of every town's intake rules
let DIRTY = {};        // slug -> true, for towns edited but not yet saved
let PREVIEWS = {};     // "slug/index" -> the last preview response
let MERGE_PICK = {};   // issue id -> true, the sources of a pending merge

// --------------------------------------------------------------------------
// talking to the record
// --------------------------------------------------------------------------

async function api(path, opts) {
  const o = opts || {};
  const headers = { 'Accept': 'application/json' };
  if (TOKEN) headers['Authorization'] = 'Bearer ' + TOKEN;
  if (o.body !== undefined) headers['Content-Type'] = 'application/json';
  let r;
  try {
    r = await fetch(path, {
      method: o.method || 'GET',
      headers: headers,
      body: o.body === undefined ? undefined : JSON.stringify(o.body),
    });
  } catch (e) {
    // The network, not the record. Say which.
    throw Object.assign(new Error(
      'the console could not reach publicrecord (' + e.message + ')'), { status: 0 });
  }
  let body = null;
  try { body = await r.json(); } catch (e) { body = null; }
  if (!r.ok) {
    const detail = (body && (body.error || body.detail)) ||
                   ('publicrecord answered ' + r.status + ' with nothing to say');
    throw Object.assign(new Error(detail), { status: r.status, body: body });
  }
  return body;
}

/* One place decides what a failure means for the whole page. A 401 or 403 has
 * emptied the session and the gate must come back; a 503 means the console
 * was never configured, and no amount of clicking will change that. */
function handle(err, where) {
  if (err.status === 503) { unconfigured(err.message); return; }
  if (err.status === 401 || err.status === 403) {
    TOKEN = ''; ME = null;
    $('console').hidden = true; $('gate').hidden = false;
    $('signout').hidden = true; $('who').textContent = '';
    $('gate-title').textContent = 'That sign-in will not do';
    clear($('gate-body'));
    $('gate-body').appendChild(h('p', { class: 'say bad', text: err.message }));
    return;
  }
  say(where ? where + ': ' + err.message : err.message, 'bad');
}

function say(sentence, tone) {
  const box = $('say');
  clear(box);
  box.appendChild(h('div', { class: 'say ' + (tone || ''), text: sentence }));
  box.scrollIntoView({ block: 'nearest' });
}

// --------------------------------------------------------------------------
// the gate
// --------------------------------------------------------------------------

/* The 503 case, given the whole page rather than a broken corner of one. The
 * server hands over its own sentence ("RECORD_GOOGLE_CLIENT_ID is not set"),
 * which is better than anything this file could guess, and the list below
 * names every switch so the reader of this screen can finish the job. */
function unconfigured(sentence) {
  $('console').hidden = true;
  $('gate').hidden = false;
  $('signout').hidden = true;
  $('who').textContent = '';
  $('gate-title').textContent = 'The steward console is not configured';
  const body = $('gate-body');
  clear(body);
  body.appendChild(h('p', { class: 'say bad', text: sentence }));
  body.appendChild(h('p', {
    text: 'This is not a broken page. Publicrecord runs without a console — ' +
          'search, freshness, submissions and the pressed edition are all up. ' +
          'What is missing is the sign-in, so nobody can curate until the ' +
          'service is given these:'
  }));
  body.appendChild(h('dl', {},
    h('dt', { text: 'RECORD_GOOGLE_CLIENT_ID' }),
    h('dd', { text: 'the OAuth web client id this page signs in against' }),
    h('dt', { text: 'RECORD_STEWARD_ALLOWLIST' }),
    h('dd', { text: 'the stewards, by email, space or comma separated — an ' +
                    'empty list means nobody is a steward yet' }),
    h('dt', { text: 'google-auth[requests]' }),
    h('dd', { text: 'the verifier itself; without it the service refuses ' +
                    'every token rather than trusting one' })));
  clear($('signin'));
}

function gateBlocked(sentence) {
  $('gate').hidden = false;
  $('gate-title').textContent = 'The console cannot sign anyone in';
  clear($('gate-body'));
  $('gate-body').appendChild(h('p', { class: 'say bad', text: sentence }));
  clear($('signin'));
}

async function boot() {
  wireTabs();
  let cfg;
  try {
    const r = await fetch('/steward/config.json', { headers: { 'Accept': 'application/json' } });
    cfg = await r.json();
  } catch (e) {
    gateBlocked('the console could not reach publicrecord to ask whether it ' +
                'is configured (' + e.message + ')');
    return;
  }
  if (!cfg.configured) { unconfigured(cfg.why || 'the reason was not given'); return; }

  $('gate-title').textContent = 'Sign in to curate the record';
  clear($('gate-body'));
  $('gate-body').appendChild(h('p', {
    text: 'Stewards sign in with Google. There is no account to create and no ' +
          'password here — the allowlist is server-side and small on purpose. ' +
          'Readers never sign in to anything.'
  }));
  await google_signin(cfg.client_id);
}

/* Google Identity Services is loaded async from the tag in the head. It may
 * never arrive — a blocked host, an offline laptop, a CSP that was tightened
 * without updating this page. Waiting forever and showing a blank box is the
 * failure this loop exists to avoid. */
async function google_signin(clientId) {
  const deadline = Date.now() + 8000;
  while (!(window.google && window.google.accounts && window.google.accounts.id)) {
    if (Date.now() > deadline) {
      gateBlocked("Google's sign-in script did not load, so there is no way " +
                  'to sign in from this page. The API is unaffected — a ' +
                  'steward with an ID token can still call it directly.');
      return;
    }
    await new Promise(function (r) { setTimeout(r, 100); });
  }
  window.google.accounts.id.initialize({
    client_id: clientId,
    callback: onCredential,
    auto_select: true,
    cancel_on_tap_outside: false,
  });
  window.google.accounts.id.renderButton($('signin'), {
    theme: 'outline', size: 'large', text: 'signin_with', shape: 'rectangular',
  });
}

async function onCredential(resp) {
  TOKEN = (resp && resp.credential) || '';
  if (!TOKEN) { say('Google returned no credential to sign in with', 'bad'); return; }
  try {
    ME = await api('/api/steward/me');
  } catch (err) { handle(err); return; }
  $('gate').hidden = true;
  $('console').hidden = false;
  $('signout').hidden = false;
  $('who').textContent = ME.name ? (ME.name + ' · ' + ME.steward) : ME.steward;
  loadIntake();
}

function signOut() {
  TOKEN = ''; ME = null;
  if (window.google && window.google.accounts) window.google.accounts.id.disableAutoSelect();
  location.reload();
}

// --------------------------------------------------------------------------
// tabs
// --------------------------------------------------------------------------

const LOADERS = {
  'pane-intake': loadIntake, 'pane-queue': loadQueue,
  'pane-issues': loadIssues, 'pane-ledgers': loadLedgers,
};

function wireTabs() {
  for (const tab of document.querySelectorAll('.tab')) {
    tab.addEventListener('click', function () {
      for (const t of document.querySelectorAll('.tab')) {
        const on = t === tab;
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        $(t.dataset.pane).hidden = !on;
      }
      clear($('say'));
      const load = LOADERS[tab.dataset.pane];
      if (load) load();
    });
  }
  $('signout').addEventListener('click', signOut);
  $('intake-reload').addEventListener('click', loadIntake);
  $('queue-reload').addEventListener('click', loadQueue);
  $('queue-status').addEventListener('change', loadQueue);
  $('issues-reload').addEventListener('click', loadIssues);
  $('issues-status').addEventListener('change', loadIssues);
  $('issues-town').addEventListener('change', loadIssues);
  $('mint-go').addEventListener('click', mint);
  $('rebuild-go').addEventListener('click', rebuild);
}

// ==========================================================================
// 1. INTAKE — per town, per source, the rules and what they would do
// ==========================================================================

async function loadIntake() {
  const box = $('towns');
  clear(box);
  box.appendChild(h('p', { class: 'muted', text: 'reading the intake rules…' }));
  let j;
  try { j = await api('/api/steward/towns'); }
  catch (err) { clear(box); handle(err, 'the towns'); return; }
  TOWNS = j.towns || [];
  DIRTY = {};
  fillTownPicker();
  drawIntake();
}

function fillTownPicker() {
  const sel = $('issues-town');
  const keep = sel.value;
  clear(sel);
  sel.appendChild(h('option', { value: '', text: 'every town' }));
  for (const t of TOWNS) sel.appendChild(h('option', { value: t.slug, text: t.name || t.slug }));
  sel.value = keep;
}

function drawIntake() {
  const box = $('towns');
  clear(box);
  if (!TOWNS.length) {
    box.appendChild(h('div', { class: 'card' },
      h('p', { class: 'empty', text: 'No town has been onboarded yet, so there ' +
        'is nothing to poll. A town arrives as a row in `towns`; its rules are ' +
        'written here.' })));
    return;
  }
  for (const town of TOWNS) box.appendChild(drawTown(town));
}

function drawTown(town) {
  const card = h('div', { class: 'card' });
  card.appendChild(h('h2', {},
    (town.name || town.slug),
    h('span', { class: 'muted' }, '  ' + [town.slug, town.state, town.status]
      .filter(Boolean).join(' · ')),
    DIRTY[town.slug] ? h('span', { class: 'dirty', text: '   unsaved' }) : ''));

  // Bad regexes as the record itself sees them, before anything is edited.
  if ((town.problems || []).length) card.appendChild(problemsBox(town.problems));

  const srcs = town.sources || [];
  if (!srcs.length) {
    card.appendChild(h('p', { class: 'empty', text: 'This town has no sources. ' +
      'Nothing will ever be filed for it.' }));
  }
  srcs.forEach(function (src, i) { card.appendChild(drawSource(town, src, i)); });

  card.appendChild(h('div', { class: 'row-actions' },
    h('button', {
      class: 'btn primary', onclick: function () { saveSources(town); },
      text: 'Save these rules',
    }),
    h('button', {
      class: 'btn grave', onclick: function () { pollTown(town, this); },
      text: 'Poll now — this spends money',
    }),
    h('span', { class: 'muted', text: 'Saving replaces the town\'s whole ' +
      'intake config and refuses any pattern that will not compile.' })));
  return card;
}

function problemsBox(problems, title) {
  return h('div', { class: 'problems' },
    h('h4', { text: title || 'These patterns will not compile' }),
    h('ul', {}, problems.map(function (p) { return h('li', { text: p }); })));
}

function drawSource(town, src, si) {
  const key = town.slug + '/' + si;
  const wrap = h('div', { class: 'source' + (src.enabled === false ? ' off' : '') });

  wrap.appendChild(h('div', { class: 'srchead' },
    h('h3', { text: src.label || src.url || ('source ' + (si + 1)) }),
    h('span', { class: 'mono dim', text: (src.kind || 'youtube') + ' · ' + (src.url || '') })));

  wrap.appendChild(h('div', { class: 'field' },
    h('label', { class: 'inline' },
      h('input', {
        type: 'checkbox', checked: src.enabled !== false,
        onchange: function () { src.enabled = this.checked; touch(town); },
      }), ' enabled'),
    h('label', { class: 'inline' }, 'cap per poll ',
      h('input', {
        type: 'number', min: '1', max: '200', value: String(src.max_per_poll || 12),
        onchange: function () { src.max_per_poll = parseInt(this.value, 10) || 12; touch(town); },
      })),
    h('label', { class: 'inline' }, 'nothing older than ',
      h('input', {
        type: 'text', value: src.since || '', placeholder: 'YYYY-MM-DD',
        onchange: function () { src.since = this.value.trim(); touch(town); },
      }))));

  // -- body rules: ordered, first match wins --------------------------------
  wrap.appendChild(h('h4', { text: 'body rules — ordered, first match wins' }));
  if (!(src.bodies || []).length) {
    wrap.appendChild(h('p', { class: 'empty', text: 'No body rules. Default-deny ' +
      'means this source would file nothing at all.' }));
  }
  (src.bodies || []).forEach(function (rule, ri) {
    wrap.appendChild(h('div', { class: 'rule-row' },
      h('span', { class: 'ord', text: String(ri + 1) + '.' }),
      h('input', {
        type: 'text', class: 'grow', value: rule.body || '', placeholder: 'body name',
        onchange: function () { rule.body = this.value; touch(town); },
      }),
      h('input', {
        type: 'text', class: 'grow', value: rule.match || '',
        placeholder: 'match pattern (regex, case-insensitive)',
        onchange: function () { rule.match = this.value; touch(town); },
      }),
      h('button', {
        class: 'btn tiny', title: 'move up', text: 'up',
        disabled: ri === 0,
        onclick: function () { move(src.bodies, ri, -1); touch(town); drawIntake(); },
      }),
      h('button', {
        class: 'btn tiny', title: 'move down', text: 'down',
        disabled: ri === src.bodies.length - 1,
        onclick: function () { move(src.bodies, ri, 1); touch(town); drawIntake(); },
      }),
      h('button', {
        class: 'btn tiny grave', text: 'remove',
        onclick: function () { src.bodies.splice(ri, 1); touch(town); drawIntake(); },
      })));
  });
  wrap.appendChild(h('button', {
    class: 'btn', text: 'Add a body rule',
    onclick: function () {
      if (!src.bodies) src.bodies = [];
      src.bodies.push({ body: '', match: '' });
      touch(town); drawIntake();
    },
  }));

  // -- exclusions -----------------------------------------------------------
  wrap.appendChild(h('h4', { text: 'exclusions — checked first, so a specific ' +
                                   '“not a meeting” beats a loose body rule' }));
  (src.exclude || []).forEach(function (pat, xi) {
    wrap.appendChild(h('div', { class: 'rule-row' },
      h('span', { class: 'ord', text: '×' }),
      h('input', {
        type: 'text', class: 'grow', value: pat, placeholder: 'exclude pattern',
        onchange: function () { src.exclude[xi] = this.value; touch(town); },
      }),
      h('button', {
        class: 'btn tiny grave', text: 'remove',
        onclick: function () { src.exclude.splice(xi, 1); touch(town); drawIntake(); },
      })));
  });
  wrap.appendChild(h('button', {
    class: 'btn', text: 'Add an exclusion',
    onclick: function () {
      if (!src.exclude) src.exclude = [];
      src.exclude.push('');
      touch(town); drawIntake();
    },
  }));

  // -- preview --------------------------------------------------------------
  wrap.appendChild(h('div', { class: 'row-actions' },
    h('button', {
      class: 'btn primary', text: 'Preview what a poll would file',
      onclick: function () { preview(town, src, si, this); },
    }),
    h('span', { class: 'muted', text: 'Reads the live feed and writes nothing.' })));

  const pv = h('div', { id: 'pv-' + si + '-' + town.slug });
  if (PREVIEWS[key]) drawPreview(pv, PREVIEWS[key], town, src);
  wrap.appendChild(pv);
  return wrap;
}

function move(arr, i, d) {
  const j = i + d;
  if (j < 0 || j >= arr.length) return;
  const tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
}

function touch(town) { DIRTY[town.slug] = true; }

async function preview(town, src, si, btn) {
  const key = town.slug + '/' + si;
  const pane = $('pv-' + si + '-' + town.slug);
  btn.disabled = true;
  clear(pane);
  pane.appendChild(h('p', { class: 'muted', text: 'polling the feed, filing nothing…' }));
  let p;
  try {
    p = await api('/api/steward/preview', { method: 'POST', body: { source: src, limit: 25 } });
  } catch (err) {
    btn.disabled = false;
    clear(pane);
    // 422 carries the list of patterns that will not compile; 502 means the
    // channel itself could not be read. Three empty lists would read as
    // "this town posts nothing", which is a lie in both cases.
    if (err.body && err.body.problems) pane.appendChild(problemsBox(err.body.problems));
    else pane.appendChild(h('p', { class: 'say bad', text: err.message }));
    return;
  }
  btn.disabled = false;
  PREVIEWS[key] = p;
  clear(pane);
  drawPreview(pane, p, town, src);
}

function drawPreview(pane, p, town, src) {
  const filed = p.file || [], excluded = p.excluded || [];
  const unmatched = p.unmatched || [], suggestions = p.suggestions || [];

  // The one number a steward is deciding on, before anything runs.
  pane.appendChild(h('div', { class: 'cost' },
    h('span', { class: 'n', text: String(p.would_cost) }),
    h('span', { class: 'what' },
      plural(p.would_cost, 'meeting', 'meetings') + ' would be filed, and each ' +
      'one costs money to ingest — embeddings always, ASR when there are no captions')));

  const notes = ['polled ' + p.polled + ' ' + plural(p.polled, 'item'),
                 'cap ' + p.cap];
  if (p.capped) notes.push(p.capped + ' over the cap would wait for the next poll');
  if ((p.too_old || []).length) notes.push((p.too_old || []).length + ' older than the cutoff');
  pane.appendChild(h('p', { class: 'muted', text: notes.join(' · ') }));

  const three = h('div', { class: 'three' });

  // would file
  const a = h('div', { class: 'pane' },
    h('h4', { text: 'would file — ' + filed.length }));
  if (!filed.length) a.appendChild(h('p', { class: 'empty', text: 'nothing' }));
  for (const it of filed) {
    a.appendChild(h('div', { class: 'r' },
      h('div', { class: 'title', text: it.title || '(untitled)' }),
      h('div', { class: 'why' }, 'body: ', h('b', { text: it.body || '?' }),
        '  ·  matched ', h('span', { class: 'pat', text: it.rule || '' })),
      it.published ? h('div', { class: 'why dim', text: it.published }) : ''));
  }
  three.appendChild(a);

  // excluded
  const b = h('div', { class: 'pane' },
    h('h4', { text: 'excluded — ' + excluded.length }));
  if (!excluded.length) b.appendChild(h('p', { class: 'empty', text: 'nothing' }));
  for (const it of excluded) {
    b.appendChild(h('div', { class: 'r' },
      h('div', { class: 'title', text: it.title || '(untitled)' }),
      h('div', { class: 'why', text: it.reason || '' })));
  }
  three.appendChild(b);

  // unmatched — the interesting list, and the only one with a button on it
  const c = h('div', { class: 'pane' },
    h('h4', { text: 'unmatched — ' + unmatched.length }));
  if (!unmatched.length) {
    c.appendChild(h('p', { class: 'empty', text: 'nothing — every title this ' +
      'feed carries is either a named body or deliberately excluded' }));
  } else {
    c.appendChild(h('p', { class: 'muted', text: 'Not errors: these are rules ' +
      'that do not exist yet. Adding one edits the list above; save to keep it.' }));
  }
  for (const it of unmatched) {
    const s = suggestionFor(it, suggestions);
    c.appendChild(h('div', { class: 'r' },
      h('div', { class: 'title', text: it.title || '(untitled)' }),
      s ? h('div', { class: 'suggest' },
            h('span', { class: 'why' }, 'suggested: '),
            h('b', { text: s.body }),
            h('span', { class: 'pat', text: s.match }),
            h('span', { class: 'why dim', text: 'seen ' + s.seen + '×' }),
            h('button', {
              class: 'btn tiny', text: 'add this rule',
              onclick: function () { addRule(town, src, s); },
            }))
        : h('div', { class: 'why dim', text: 'seen once — no rule suggested; ' +
            'add one by hand above if this is a public body' })));
  }
  three.appendChild(c);

  pane.appendChild(three);
}

/* Which suggestion, if any, belongs beside this unmatched title. The server
 * groups by the head of the string and hands back examples, so the exact
 * match is cheapest; the regex is the fallback for a title past the third
 * example. Both are the server's own rule, never a second guess at it. */
function suggestionFor(item, suggestions) {
  const title = item.title || '';
  for (const s of suggestions) {
    if ((s.examples || []).indexOf(title) >= 0) return s;
  }
  for (const s of suggestions) {
    try { if (new RegExp(s.match, 'i').test(title)) return s; } catch (e) { /* the
      server compiled it; if this browser will not, fall through quietly */ }
  }
  return null;
}

function addRule(town, src, s) {
  if (!src.bodies) src.bodies = [];
  const already = src.bodies.some(function (r) {
    return (r.match || '') === s.match || (r.body || '') === s.body;
  });
  if (already) { say('a rule for “' + s.body + '” is already in this source', ''); return; }
  // Specific before general: a new named body goes above the catch-alls that
  // were already there, or "City Council" swallows "Committee on Planning".
  src.bodies.unshift({ body: s.body, match: s.match });
  touch(town);
  drawIntake();
  say('added “' + s.body + '” to ' + (src.label || src.url) + '. It is not saved ' +
      'yet — press “Save these rules”, then preview again to see it take.', 'good');
}

async function saveSources(town) {
  try {
    await api('/api/steward/towns/' + encodeURIComponent(town.slug) + '/sources',
              { method: 'PUT', body: { sources: town.sources || [] } });
  } catch (err) {
    if (err.body && err.body.problems) {
      say(err.message + ' — nothing was saved.', 'bad');
      const box = $('say');
      box.appendChild(problemsBox(err.body.problems));
      return;
    }
    handle(err, 'saving ' + town.slug); return;
  }
  DIRTY[town.slug] = false;
  say('saved ' + town.slug + '’s intake rules', 'good');
  loadIntake();
}

async function pollTown(town, btn) {
  if (DIRTY[town.slug]) {
    say('save ' + town.slug + '’s rules first — a poll runs what the record ' +
        'has stored, not what is on this screen', 'bad');
    return;
  }
  if (!confirm('Run the intake for ' + town.slug + ' for real?\n\n' +
               'This files matching videos into the review queue. It does not ' +
               'add anything to the record — approval is still a separate act — ' +
               'but ingesting what it files costs money.')) return;
  btn.disabled = true;
  try {
    const r = await api('/api/steward/towns/' + encodeURIComponent(town.slug) + '/poll',
                        { method: 'POST', body: { limit: 25 } });
    say('polled ' + town.slug + ': filed ' + (r.filed === undefined ? '?' : r.filed) +
        ' into the review queue', 'good');
  } catch (err) { handle(err, 'polling ' + town.slug); }
  btn.disabled = false;
}

// ==========================================================================
// 2. THE REVIEW QUEUE
// ==========================================================================

async function loadQueue() {
  const box = $('queue');
  clear(box);
  box.appendChild(h('p', { class: 'muted', text: 'reading the queue…' }));
  let j;
  try { j = await api('/api/steward/submissions?status=' +
                      encodeURIComponent($('queue-status').value) + '&limit=200'); }
  catch (err) { clear(box); handle(err, 'the queue'); return; }
  clear(box);
  const subs = j.submissions || [];
  if (!subs.length) {
    box.appendChild(h('div', { class: 'card' },
      h('p', { class: 'empty', text: 'Nothing is ' + j.status + '.' })));
    return;
  }
  for (const s of subs) box.appendChild(drawSubmission(s));
}

function drawSubmission(s) {
  const card = h('div', { class: 'card' });
  card.appendChild(h('h3', { text: s.title || s.url || s.id }));
  card.appendChild(h('p', { class: 'mono dim' },
    [s.town, s.body, s.date].filter(Boolean).join(' · ') || 'no town, body or date given'));
  if (s.url) {
    card.appendChild(h('p', {},
      h('a', { href: s.url, rel: 'noopener noreferrer nofollow', target: '_blank',
               text: s.url })));
  }
  if (s.note) card.appendChild(h('p', { class: 'muted', text: '“' + s.note + '”' }));
  card.appendChild(h('p', { class: 'mono dim', text: 'submitted ' + when(s.added_at) }));
  if (s.reason) card.appendChild(h('p', { class: 'mono', text: 'reason: ' + s.reason }));

  if (s.status === 'submitted') {
    const reason = h('input', { type: 'text', class: 'grow',
                                placeholder: 'why this is not for the record' });
    card.appendChild(h('div', { class: 'row-actions' },
      h('button', {
        class: 'btn primary', text: 'Approve',
        onclick: function () { decide(s, 'approve', {}, this); },
      }),
      reason,
      h('button', {
        class: 'btn grave', text: 'Reject',
        onclick: function () {
          const why = reason.value.trim();
          if (!why) { say('a rejection needs a reason — it is the part that ' +
                          'outlives the row', 'bad'); reason.focus(); return; }
          decide(s, 'reject', { reason: why }, this);
        },
      })));
  }
  return card;
}

async function decide(s, verb, body, btn) {
  btn.disabled = true;
  try {
    await api('/api/steward/submissions/' + encodeURIComponent(s.id) + '/' + verb,
              { method: 'POST', body: body });
    say(verb === 'approve'
        ? 'approved — the pipeline job picks it up; nothing transcribes while you wait'
        : 'rejected, with the reason recorded', 'good');
    loadQueue();
  } catch (err) { btn.disabled = false; handle(err, verb); }
}

// ==========================================================================
// 3. THE EIGHT VERBS
// ==========================================================================

async function loadIssues() {
  const box = $('issues');
  clear(box);
  box.appendChild(h('p', { class: 'muted', text: 'reading the issues…' }));
  const q = '?town=' + encodeURIComponent($('issues-town').value) +
            '&status=' + encodeURIComponent($('issues-status').value) + '&limit=300';
  let j;
  try { j = await api('/api/steward/issues' + q); }
  catch (err) { clear(box); handle(err, 'the issues'); return; }
  clear(box);
  const issues = j.issues || [];
  if (!issues.length) {
    box.appendChild(h('div', { class: 'card' },
      h('p', { class: 'empty', text: 'No issues match that filter.' })));
    return;
  }
  const picked = Object.keys(MERGE_PICK).filter(function (k) { return MERGE_PICK[k]; });
  box.appendChild(h('div', { class: 'card' },
    h('p', { class: 'muted', text: issues.length + ' ' + plural(issues.length, 'issue') +
      (picked.length ? ' · ' + picked.length + ' picked as merge sources' : '') })));
  for (const iss of issues) box.appendChild(drawIssue(iss));
}

function drawIssue(iss) {
  const card = h('div', { class: 'card' });
  card.appendChild(h('h3', {},
    h('label', { class: 'inline' },
      h('input', {
        type: 'checkbox', checked: !!MERGE_PICK[iss.id],
        title: 'pick as a merge source',
        onchange: function () { MERGE_PICK[iss.id] = this.checked; },
      })),
    ' ' + (iss.name || iss.id)));
  card.appendChild(h('p', { class: 'mono dim' },
    [iss.id, iss.town, iss.status, iss.origin,
     iss.n_meetings + ' ' + plural(iss.n_meetings, 'meeting'),
     iss.n_segments + ' ' + plural(iss.n_segments, 'segment'),
     iss.first_seen && iss.last_seen ? iss.first_seen + ' → ' + iss.last_seen : '',
     iss.following ? 'followed' : ''].filter(Boolean).join(' · ')));

  // rename
  const nameField = h('input', { type: 'text', class: 'grow', value: iss.name || '' });
  card.appendChild(h('div', { class: 'field' },
    nameField,
    h('button', {
      class: 'btn', text: 'Rename',
      onclick: function () { verb(this, issuePath(iss.id, 'rename'), 'POST',
                                  { name: nameField.value }, 'renamed'); },
    })));

  // split
  const meetField = h('input', { type: 'text', placeholder: 'meeting id to split off' });
  const splitName = h('input', { type: 'text', placeholder: 'name for the new issue (optional)' });
  card.appendChild(h('div', { class: 'field' },
    meetField, splitName,
    h('button', {
      class: 'btn', text: 'Split',
      onclick: function () {
        verb(this, issuePath(iss.id, 'split'), 'POST',
             { meeting_id: meetField.value.trim(), name: splitName.value.trim() },
             'split off');
      },
    })));

  const sources = Object.keys(MERGE_PICK).filter(function (k) {
    return MERGE_PICK[k] && k !== iss.id;
  });
  card.appendChild(h('div', { class: 'row-actions' },
    h('button', {
      class: 'btn', disabled: !sources.length,
      text: 'Merge ' + sources.length + ' picked into this',
      onclick: function () {
        verb(this, issuePath(iss.id, 'merge'), 'POST', { src_ids: sources },
             'merged — the sources keep a tombstone pointing here');
      },
    }),
    h('button', {
      class: 'btn', text: 'Promote',
      onclick: function () { verb(this, issuePath(iss.id, 'promote'), 'POST', {},
                                  'promoted — links unchanged until the next rebuild'); },
    }),
    h('button', {
      class: 'btn', text: iss.following ? 'Unfollow' : 'Follow',
      onclick: function () {
        verb(this, issuePath(iss.id, 'follow'),
             iss.following ? 'DELETE' : 'POST', undefined,
             iss.following ? 'unfollowed' : 'followed');
      },
    }),
    h('button', {
      class: 'btn grave', text: 'Forget',
      onclick: function () {
        if (!confirm('Forget “' + (iss.name || iss.id) + '”?\n\n' +
                     'This is the one destructive verb — merge leaves a ' +
                     'tombstone pointing home, forget does not. The audit row ' +
                     'is written before the issue is gone, so the log outlives ' +
                     'it, but the issue does not come back.')) return;
        verb(this, issuePath(iss.id, 'forget'), 'POST', {}, 'forgotten');
      },
    })));
  return card;
}

/* One issue, one verb. The id is the only part of the URL that did not come
 * from this file, so it is the only part that is encoded — and it is encoded
 * even though the route is declared `:path`, because an id is corpus data and
 * corpus data does not get to decide which route it hits. */
function issuePath(id, tail) {
  return '/api/steward/issues/' + encodeURIComponent(id) + '/' + tail;
}

async function verb(btn, path, method, body, done) {
  btn.disabled = true;
  try {
    await api(path, { method: method, body: body });
    say(done, 'good');
    MERGE_PICK = {};
    loadIssues();
  } catch (err) { btn.disabled = false; handle(err, 'that verb'); }
}

async function mint() {
  const q = $('mint-q').value.trim();
  const town = $('issues-town').value;
  if (!q || !town) {
    say('mint needs a query and a town — pick a town above, since an issue ' +
        'belongs to one record', 'bad');
    return;
  }
  try {
    await api('/api/steward/mint', { method: 'POST', body: { q: q, town: town } });
    $('mint-q').value = '';
    say('minted an issue for “' + q + '” in ' + town, 'good');
    loadIssues();
  } catch (err) { handle(err, 'mint'); }
}

async function rebuild() {
  const town = $('issues-town').value;
  if (!town) { say('rebuild which town? pick one above', 'bad'); return; }
  if (!confirm('Rebuild ' + town + '’s issues?\n\n' +
               'This re-derives issue links from every segment in the town. It ' +
               'keeps minted, steward-touched and followed issues — a rebuild ' +
               'refreshes links, it never forgets a human’s work — but it is ' +
               'the heaviest verb and takes a while.')) return;
  say('rebuilding ' + town + '… this holds the connection open', '');
  try {
    const r = await api('/api/steward/rebuild', { method: 'POST', body: { town: town } });
    say('rebuilt ' + town + ' in ' + r.seconds + 's: ' + JSON.stringify(r.result), 'good');
    loadIssues();
  } catch (err) { handle(err, 'rebuild'); }
}

// ==========================================================================
// 4. THE LEDGERS
// ==========================================================================

async function loadLedgers() {
  let spend, audit;
  try {
    spend = await api('/api/steward/spend?limit=200');
    audit = await api('/api/steward/audit?limit=200');
  } catch (err) { handle(err, 'the ledgers'); return; }

  // Totals first and largest: the point of this ledger is that the number is
  // seen before the invoice is.
  const totals = $('spend-totals');
  clear(totals);
  const rows = spend.totals || [];
  const allUnits = rows.reduce(function (a, r) { return a + (r.units || 0); }, 0);
  const allCalls = rows.reduce(function (a, r) { return a + (r.calls || 0); }, 0);
  totals.appendChild(h('div', { class: 'total' },
    h('span', { class: 'n', text: allUnits.toLocaleString() }),
    h('span', { class: 'k', text: 'units, all models' })));
  totals.appendChild(h('div', { class: 'total' },
    h('span', { class: 'n', text: allCalls.toLocaleString() }),
    h('span', { class: 'k', text: 'calls' })));
  for (const t of rows) {
    totals.appendChild(h('div', { class: 'total' },
      h('span', { class: 'n', text: (t.units || 0).toLocaleString() }),
      h('span', { class: 'k', text: (t.model || '?') + ' · ' + (t.purpose || '?') +
        ' · ' + (t.calls || 0) + ' ' + plural(t.calls || 0, 'call') })));
  }
  if (!rows.length) {
    totals.appendChild(h('div', { class: 'total' },
      h('span', { class: 'n', text: '0' }),
      h('span', { class: 'k', text: 'nothing has been spent yet' })));
  }

  $('spend-rows').replaceChildren(table(
    ['when', 'model', 'purpose', 'town', 'target', 'units'],
    (spend.spend || []).map(function (s) {
      return [when(s.added_at), s.model, s.purpose, s.town, s.target,
              { num: (s.units || 0).toLocaleString() }];
    }), 'No spend rows yet.'));

  $('audit-rows').replaceChildren(table(
    ['when', 'steward', 'verb', 'target', 'town', 'what'],
    (audit.audit || []).map(function (a) {
      return [when(a.added_at), a.steward, a.verb, a.target, a.town,
              JSON.stringify(a.payload || {})];
    }), 'Nothing has been curated yet.'));
}

function table(headers, rows, empty) {
  if (!rows.length) return h('p', { class: 'empty', text: empty });
  return h('div', { class: 'scroller' },
    h('table', {},
      h('thead', {}, h('tr', {}, headers.map(function (t) { return h('th', { text: t }); }))),
      h('tbody', {}, rows.map(function (r) {
        return h('tr', {}, r.map(function (cell) {
          return (cell && cell.num !== undefined)
            ? h('td', { class: 'num', text: cell.num })
            : h('td', { text: cell === null || cell === undefined ? '' : String(cell) });
        }));
      }))));
}

// --------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', boot);
