(function () {
  'use strict';
  var COLOURS = { you: '#2563eb', sam: '#0f766e', priya: '#7c3aed', marcus: '#ea580c', sofia: '#db2777', kenji: '#0891b2',
                  dana: '#475569', leah: '#ca8a04', jordan: '#16a34a', rosa: '#9333ea', pruitt: '#b45309' };
  var LEVEL = { strong: 'STRONG', partial: 'PARTIAL', weak: 'WEAK', off_topic: 'OFF TOPIC' };
  var view = null, busy = false, picked = [], helpUsed = false;

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function initials(name) { return name.split(' ').filter(function (w) { return /^[A-Z]/.test(w); }).slice(-2).map(function (w) { return w[0]; }).join(''); }
  function avatar(p, small) {
    var a = el('span', 'avatar' + (small ? ' sm' : ''), p.id === 'you' ? 'You' : initials(p.name));
    a.style.setProperty('--c', COLOURS[p.id] || '#64748b'); a.setAttribute('aria-hidden', 'true'); return a;
  }
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch (e) {} return null; }
  function api(method, path, body) {
    return fetch(path, { method: method, headers: { 'content-type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.detail || r.statusText); return j; }); });
  }

  // ---------------------------------------------------------------- team, timeline, board
  function member(p, title) {
    var m = el('div', 'member'); m.id = 'm-' + p.id; m.appendChild(avatar(p));
    var d = el('div'); d.appendChild(el('b', null, p.name)); d.appendChild(el('small', null, title || p.role)); m.appendChild(d);
    return m;
  }
  function renderTeam() {
    var sm = document.getElementById('roleSM'); sm.textContent = '';
    sm.appendChild(member(view.team.scrum_master, 'Coaches you and the team; removes blockers'));
    var t = document.getElementById('team'); t.textContent = '';
    view.team.developers.forEach(function (p) { t.appendChild(member(p)); });
    document.getElementById('devCount').textContent = view.team.developers.length;
    var s = document.getElementById('stakeholders'); s.textContent = '';
    view.pack.stakeholders.forEach(function (p) { s.appendChild(member(p)); });
    var chip = document.getElementById('packTitle');
    chip.textContent = 'Scenario: ' + view.pack.title; chip.hidden = false;
    document.querySelector('.chat-head h2').textContent = '# ' + view.pack.product.name.toLowerCase().replace(/\s+/g, '-');
    var dod = document.getElementById('dod'); dod.textContent = '';
    view.pack.definition_of_done.forEach(function (d) { dod.appendChild(el('li', null, d)); });
  }

  function currentDay() {
    var s = view.step;
    if (s.kind === 'debrief') return view.pack.sprint_days + 1;
    if (s.step === 'quiz_post') return view.pack.sprint_days + 1;
    return s.day || 0;
  }

  function renderTimeline() {
    var t = document.getElementById('timeline'); t.textContent = '';
    var day = currentDay(), labels = ['Setup'];
    for (var d = 1; d <= view.pack.sprint_days; d++) labels.push('Day ' + d);
    labels.push('Debrief');
    labels.forEach(function (label, i) {
      var li = el('li', i < day ? 'done' : i === day ? 'now' : '', label);
      if (i === day) li.setAttribute('aria-current', 'step');
      t.appendChild(li);
    });
    document.getElementById('dayLabel').textContent = labels[Math.min(day, labels.length - 1)];
  }

  // Today's agenda (done ✓ / now ● / next ○), what comes next, and the whole Sprint on request.
  function dayName(d) { return d === 0 ? 'Setup' : d > view.pack.sprint_days ? 'Debrief' : 'Day ' + d; }
  function renderToday() {
    var box = document.getElementById('today'); box.textContent = '';
    if (!view.agenda) return;
    var day = currentDay(), todays = view.agenda.filter(function (a) { return a.day === day; });
    var strip = el('div', 'today-strip');
    strip.appendChild(el('span', 'today-label', day > view.pack.sprint_days ? 'Wrap-up' : dayName(day) + (day ? ' today' : '')));
    var list = el('ol', 'today-items');
    todays.forEach(function (a) {
      var li = el('li', a.status + (a.event ? ' event' : ''));
      li.appendChild(el('span', 'tick', a.status === 'done' ? '✓' : a.status === 'now' ? '●' : '○'));
      li.appendChild(el('span', null, a.title));
      if (a.status === 'now') li.setAttribute('aria-current', 'step');
      list.appendChild(li);
    });
    strip.appendChild(list);
    var later = view.agenda.filter(function (a) { return a.day > day; })[0];
    if (later) strip.appendChild(el('span', 'today-next', 'Up next: ' + dayName(later.day) + ' · ' + later.title));
    box.appendChild(strip);
    var all = el('details', 'whole-sprint'); all.appendChild(el('summary', null, 'See the whole Sprint'));
    var grid = el('div', 'sprint-days');
    var days = []; view.agenda.forEach(function (a) { if (days.indexOf(a.day) < 0) days.push(a.day); });
    days.forEach(function (d) {
      var col = el('div', 'sprint-day' + (d === day ? ' current' : '')); col.appendChild(el('b', null, dayName(d)));
      view.agenda.filter(function (a) { return a.day === d; }).forEach(function (a) {
        col.appendChild(el('span', 'ag ' + a.status + (a.event ? ' event' : ''), (a.status === 'done' ? '✓ ' : a.status === 'now' ? '● ' : '○ ') + a.title));
      });
      grid.appendChild(col);
    });
    all.appendChild(grid); box.appendChild(all);
  }

  function renderBoard() {
    setGoal('productGoal', view.product_goal); setGoal('sprintGoal', view.sprint_goal);
    var items = view.pack.backlog.filter(function (b) { return view.selected.indexOf(b.id) >= 0; });
    var days = view.pack.sprint_days, day = Math.max(0, currentDay() - 1);
    var done = Math.min(items.length, Math.floor(items.length * day / days)), doing = Math.min(items.length - done, 2);
    fill('colTodo', items.slice(done + doing)); fill('colDoing', items.slice(done, done + doing)); fill('colDone', items.slice(0, done));
  }
  function setGoal(id, text) { var p = document.getElementById(id); p.textContent = text || 'Not set yet'; p.className = text ? '' : 'muted'; }
  function fill(id, items) {
    var c = document.getElementById(id); c.textContent = '';
    if (!items.length) c.appendChild(el('p', 'empty', view.selected.length ? 'Nothing here' : 'Set in Sprint Planning'));
    items.forEach(function (b) {
      var card = el('div', 'card'); card.appendChild(el('span', null, b.id + ' ' + b.title));
      card.appendChild(el('span', 'pts', b.points == null ? '?' : b.points + ' pts')); c.appendChild(card);
    });
  }

  // ---------------------------------------------------------------- learn as you go (definitions, never answers)
  function renderLearn() {
    var box = document.getElementById('learn'), s = view.step; box.textContent = '';
    if (!s.terms || !s.terms.length) { box.hidden = true; return; }
    box.hidden = false;
    box.appendChild(el('h2', null, '📘 Learn as you go'));
    if (s.legend) {
      box.appendChild(el('p', 'learn-lead', 'How to read a backlog card:'));
      var card = el('div', 'anatomy');
      function part(n, node) { var g = el('span', 'a-part'); g.appendChild(mark(n)); g.appendChild(node); return g; }
      var main = el('span', 'a-main'); main.appendChild(part(1, el('b', null, 'B1')));
      main.appendChild(part(2, el('span', null, 'Residents sign up by texting RIVER…')));
      var meta = el('span', 'a-meta'); meta.appendChild(part(3, el('span', null, 'high value')));
      meta.appendChild(part(4, el('span', null, '5 pts')));
      card.appendChild(main); card.appendChild(meta); box.appendChild(card);
      var ol = el('ol', 'legend');
      s.legend.forEach(function (l) { var li = el('li'); li.appendChild(el('b', null, l.label + ': ')); li.appendChild(document.createTextNode(l.meaning)); ol.appendChild(li); });
      box.appendChild(ol);
      box.appendChild(el('p', 'learn-job', 'Your job: pick the items in priority order, most valuable first, that the team can finish ' +
        'within its capacity of about ' + s.capacity + ' points. Leave out anything that isn\'t ready.'));
    }
    var dl = el('dl', 'terms');
    s.terms.filter(function (t) { return !s.legend || ['Value', 'Story points'].indexOf(t.term) < 0; }).forEach(function (t) {
      dl.appendChild(el('dt', null, t.term)); dl.appendChild(el('dd', null, t.meaning));
    });
    box.appendChild(dl);
  }
  function mark(n) { var m = el('span', 'mark', String(n)); m.setAttribute('aria-hidden', 'true'); return m; }

  // ---------------------------------------------------------------- the feed
  function person(id) {
    var all = [view.team.scrum_master].concat(view.team.developers, view.pack.stakeholders);
    for (var i = 0; i < all.length; i++) if (all[i].id === id) return all[i];
    return { id: id, name: id, role: '' };
  }
  function bubble(p, text, mine) {
    var m = el('div', 'msg' + (mine ? ' you' : '')); m.appendChild(avatar(p, true));
    var b = el('div', 'body'), who = el('div', 'who', p.name); who.appendChild(el('small', null, p.role));
    b.appendChild(who); b.appendChild(el('div', null, text)); m.appendChild(b); return m;
  }
  function renderItem(item) {
    if (item.type === 'prompt') {
      var card = el('div', 'prompt-card');
      card.appendChild(el('span', 'tag', (item.day ? 'Day ' + item.day + ' · ' : '') + item.title));
      card.appendChild(bubble(item.speaker, item.text));
      card.appendChild(el('p', 'ask', 'Your call: ' + item.prompt)); return card;
    }
    if (item.type === 'system') return el('div', 'system', (item.day ? 'Day ' + item.day + ' · ' : '') + item.title);
    if (item.type === 'quiz') return el('div', 'system', item.skipped ? item.title + ': skipped'
      : item.title + ': ' + item.correct + ' of ' + item.of + ' correct');
    if (item.type === 'you') {
      var text = item.kind === 'planning'
        ? 'Sprint backlog: ' + view.selected.join(', ') + ' (' + item.answer.total_size + ' points)'
        : item.answer;
      return bubble({ id: 'you', name: 'You', role: 'Product Owner' }, text, true);
    }
    if (item.type === 'reaction') return bubble(person(item.id), item.text);
    if (item.type === 'coach') {
      var c = el('div', 'coach'), head = el('div', 'head');
      head.appendChild(avatar(person('sam'), true)); head.appendChild(el('b', null, 'Sam, coaching'));
      head.appendChild(el('span', 'chip ' + item.grade.level, LEVEL[item.grade.level]));
      head.appendChild(el('small', null, item.competency + (item.grade.low_confidence ? ' · low-confidence grade' : '')));
      c.appendChild(head); c.appendChild(el('div', null, item.text));
      if (item.grade.level !== 'strong' && item.ideal) {
        var d = el('details'); d.appendChild(el('summary', null, 'See one strong answer'));
        d.appendChild(el('p', null, item.ideal)); c.appendChild(d);
      }
      return c;
    }
    return el('div');
  }
  function renderFeed(fromIndex) {
    var f = document.getElementById('feed');
    if (!fromIndex) f.textContent = '';
    view.feed.slice(fromIndex || 0).forEach(function (item) { f.appendChild(renderItem(item)); });
    if (view.result) f.appendChild(renderDebrief(view.result));
    f.scrollTop = f.scrollHeight;
  }
  function highlightSpeakers(ids) {
    document.querySelectorAll('.member.speaking').forEach(function (m) { m.classList.remove('speaking'); });
    ids.forEach(function (id) { var m = document.getElementById('m-' + id); if (m) m.classList.add('speaking'); });
  }

  // ---------------------------------------------------------------- the composer
  function renderComposer() {
    var c = document.getElementById('composer'); c.textContent = ''; var s = view.step;
    if (s.kind === 'text') {
      helpUsed = false;
      var ta = el('textarea'); ta.maxLength = 1500; ta.setAttribute('aria-label', s.prompt);
      ta.placeholder = 'Type what you would say…' + (s.help ? '\nNeed an idea? Press HELP for an example you can edit.' : '');
      var row = el('div', 'row'), left = el('div', 'left'), send = el('button', 'btn', 'Send');
      if (s.help) {
        var help = el('button', 'btn help', 'HELP'); help.type = 'button';
        help.setAttribute('aria-label', 'Help: fill in an example answer you can edit');
        help.addEventListener('click', function () {
          ta.value = ta.value.trim() ? ta.value.trim() + '\n\n' + s.help : s.help;
          helpUsed = true; ta.focus();
          var start = ta.value.indexOf('[', ta.value.length - s.help.length), end = ta.value.indexOf(']', start);
          if (start >= 0 && end > start) ta.setSelectionRange(start, end + 1);   // select the first blank to fill in
        });
        left.appendChild(help);
      }
      left.appendChild(el('small', null, s.help ? 'Replace each [bracket] with your own words · Ctrl+Enter to send' : 'Ctrl+Enter to send'));
      send.addEventListener('click', function () { if (ta.value.trim()) submit(ta.value.trim()); });
      ta.addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send.click(); });
      row.appendChild(left); row.appendChild(send); c.appendChild(ta); c.appendChild(row); ta.focus();
    } else if (s.kind === 'quiz') {
      var form = el('div', 'quiz');
      s.questions.forEach(function (q, i) {
        var fs = el('fieldset'); fs.appendChild(el('legend', null, (i + 1) + '. ' + q.q));
        q.options.forEach(function (o, j) {
          var lab = el('label'), r = el('input'); r.type = 'radio'; r.name = 'q' + i; r.value = j;
          lab.appendChild(r); lab.appendChild(el('span', null, o)); fs.appendChild(lab);
        });
        form.appendChild(fs);
      });
      c.appendChild(el('p', 'quiz-note', s.note));
      var qrow = el('div', 'row'), qbtn = el('button', 'btn', 'Submit answers'), skip = el('button', 'btn ghost', 'Skip for now');
      skip.addEventListener('click', function () { submit('skip'); });
      qbtn.addEventListener('click', function () {
        var answers = s.questions.map(function (q, i) { var r = form.querySelector('input[name=q' + i + ']:checked'); return r ? +r.value : null; });
        if (answers.indexOf(null) >= 0) { qrow.firstChild.textContent = 'Answer every question first.'; return; }
        submit(answers);
      });
      var qbtns = el('div'); qbtns.appendChild(skip); qbtns.appendChild(document.createTextNode(' ')); qbtns.appendChild(qbtn);
      qrow.appendChild(el('small', null, s.title)); qrow.appendChild(qbtns); c.appendChild(form); c.appendChild(qrow);
    } else if (s.kind === 'planning') {
      picked = []; var list = el('div', 'pick'), meter = el('div', 'meter'), bar = el('div', 'bar'), fillBar = el('i');
      var label = el('small'); bar.appendChild(fillBar); meter.appendChild(label); meter.appendChild(bar);
      function update() {
        var total = picked.reduce(function (n, id) { var b = s.backlog.filter(function (x) { return x.id === id; })[0]; return n + (b.points || 0); }, 0);
        label.textContent = total + ' of ~' + s.capacity + ' points · order: ' + (picked.join(' → ') || 'pick items in priority order');
        fillBar.style.width = Math.min(100, 100 * total / s.capacity) + '%'; meter.className = 'meter' + (total > s.capacity ? ' over' : '');
        pbtn.disabled = !picked.length;
      }
      s.backlog.forEach(function (b) {
        var btn = el('button'); btn.type = 'button'; btn.setAttribute('aria-pressed', 'false');
        btn.appendChild(el('span', null, b.id + '  ' + b.title));
        btn.appendChild(el('span', 'meta', b.value + ' value · ' + (b.points == null ? '?? pts' : b.points + ' pts')));
        btn.addEventListener('click', function () {
          var i = picked.indexOf(b.id); if (i >= 0) picked.splice(i, 1); else picked.push(b.id);
          btn.setAttribute('aria-pressed', String(i < 0)); update();
        });
        list.appendChild(btn);
      });
      var prow = el('div', 'row'), pbtn = el('button', 'btn', 'Start the Sprint');
      pbtn.addEventListener('click', function () { submit(picked.slice()); });
      prow.appendChild(meter); prow.appendChild(pbtn);
      var head = el('div', 'pick-head'); head.setAttribute('aria-hidden', 'true');
      head.appendChild(el('span', null, 'ID · Backlog item (what users need)')); head.appendChild(el('span', null, 'Value · Size'));
      c.appendChild(el('p', null, s.prompt)); c.appendChild(head); c.appendChild(list); c.appendChild(prow); update();
    } else {
      var again = el('button', 'btn ghost', 'Play again');
      again.addEventListener('click', function () { store('sz-session', ''); start(chosenPack); });
      c.appendChild(again);
    }
  }

  function renderDebrief(r) {
    var d = el('div', 'debrief');
    d.appendChild(el('div', 'medal', (r.medal ? r.medal + ' · ' : '') + r.percent + '%'));
    d.appendChild(el('small', null, 'Score ' + r.score + ' of ' + r.max));
    var skills = el('div', 'skills');
    Object.keys(r.competencies).forEach(function (k) {
      var row = el('div', 'skill'); row.appendChild(el('span', null, r.competency_names[k]));
      row.appendChild(el('span', 'chip ' + r.competencies[k], LEVEL[r.competencies[k]])); skills.appendChild(row);
    });
    d.appendChild(skills);
    if (r.quiz.quiz_pre != null && r.quiz.quiz_post != null) {
      d.appendChild(el('p', 'quiz-delta', 'Quick check: ' + r.quiz.quiz_pre + ' before → ' + r.quiz.quiz_post + ' after'));
    }
    if (r.help_used) d.appendChild(el('p', null, 'You used HELP on ' + r.help_used + (r.help_used === 1 ? ' decision' : ' decisions') +
      '. Next time, try one without it.'));
    r.flags.forEach(function (f) { d.appendChild(el('small', null, f)); });
    return d;
  }

  // ---------------------------------------------------------------- flow
  function render(previousFeedLength) {
    renderTimeline(); renderToday(); renderLearn(); renderBoard(); renderFeed(previousFeedLength); renderComposer();
    var last = view.feed.slice(previousFeedLength || 0).filter(function (i) { return i.type === 'reaction' || i.type === 'prompt'; });
    highlightSpeakers(last.map(function (i) { return i.type === 'prompt' ? i.speaker.id : i.id; }));
  }
  // What the system is doing while the learner waits: real steps, named after the grader and people involved.
  function statusLines(step, answer) {
    if (step.kind === 'quiz') return [answer === 'skip' ? 'Skipping the warm-up…' : 'Saving your answers…'];
    var decider = /decider/i.test(view.grader || '');
    var grading = decider ? 'Strands Decider 2B is weighing your answer against the rubric…'
                          : 'Checking your answer against the rubric…';
    if (step.kind === 'planning') {
      return ['Allowing Strands to weigh your plan…', 'Checking the Sprint against the team\'s capacity…',
              'Priya and Marcus are reviewing the Sprint backlog…', 'Sam is preparing your coaching…'];
    }
    var names = step.reacting || [], who = names.length > 1 ? names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1] : names[0];
    return ['Allowing Strands to weigh the option…', grading,
            who ? who + (names.length > 1 ? ' are' : ' is') + ' reading your message…' : 'The team is reading your message…',
            'Sam is preparing your coaching…'];
  }
  function showStatus(lines) {
    var c = document.getElementById('composer'); c.textContent = '';
    var box = el('div', 'status'); box.setAttribute('role', 'status'); box.setAttribute('aria-live', 'polite');
    var spin = el('span', 'spinner'); spin.setAttribute('aria-hidden', 'true');
    var text = el('span', 'status-text', lines[0]), secs = el('small', 'status-time', '0s');
    box.appendChild(spin); box.appendChild(text); box.appendChild(secs); c.appendChild(box);
    var i = 0, started = Date.now();
    var timer = setInterval(function () {
      var elapsed = Math.round((Date.now() - started) / 1000); secs.textContent = elapsed + 's';
      var next = Math.min(lines.length - 1, Math.floor(elapsed / 3));
      if (next !== i) { i = next; text.textContent = lines[i]; }
    }, 500);
    return function () { clearInterval(timer); };
  }
  function submit(answer) {
    if (busy) return; busy = true;
    var stop = showStatus(statusLines(view.step, answer));
    var typing = el('div', 'typing', 'The team is responding'); ['.', '.', '.'].forEach(function (d) { typing.appendChild(el('span', null, d)); });
    var feed = document.getElementById('feed'); feed.appendChild(typing); feed.scrollTop = feed.scrollHeight;
    var before = view.feed.length;
    api('POST', '/api/sessions/' + view.id + '/answer', { step: view.step.number, answer: answer, help_used: helpUsed })
      .then(function (v) { stop(); view = v; typing.remove(); render(before); })
      .catch(function (e) { stop(); typing.textContent = 'Something went wrong: ' + e.message; renderComposer(); })
      .then(function () { busy = false; });
  }
  function load(v) { view = v; store('sz-session', v.id); renderTeam(); render(0); }
  function start(pack) { return api('POST', '/api/sessions', { pack: pack || 'flood-alert' }).then(load); }

  // ---------------------------------------------------------------- onboarding: walkthrough, then a spotlight tour
  var chosenPack = 'flood-alert', obIndex = 0;
  var OB = [
    function () {
      return '<h1 id="obTitle">Welcome to Sprint Zero</h1>' +
        '<p class="lead">On most teams, your first Scrum Sprint is also your first week on the job. Sprint Zero lets you ' +
        'practise first. You will play the <b>Product Owner</b> for one five-day Sprint, with an AI team that reacts the way ' +
        'real people do.</p><div class="facts">' +
        '<div class="fact"><b>About 20 minutes</b>Pause anytime; your progress is saved in this browser.</div>' +
        '<div class="fact"><b>No experience needed</b>The next screen covers the basics.</div>' +
        '<div class="fact"><b>Your own words</b>You type what you would say. There are no trick questions.</div>' +
        '<div class="fact"><b>A coach beside you</b>Sam, the Scrum Master, gives feedback after every decision.</div></div>';
    },
    function () {
      return '<h1 id="obTitle">Scrum in two minutes</h1>' +
        '<p class="lead">Scrum is a simple way for a small team to build something useful in short cycles called ' +
        '<b>Sprints</b>, checking and adjusting as they go. Every Scrum Team has three roles:</p><div class="roles3">' +
        '<div class="role-card" style="--c:#2563eb"><small>That\'s you</small><b>Product Owner</b>Decides <i>what</i> gets built and in what order, ' +
        'keeps the Product Backlog, and says no when needed to protect the goal.</div>' +
        '<div class="role-card" style="--c:#0f766e"><small>Sam</small><b>Scrum Master</b>Coaches the team and you, helps clear blockers, ' +
        'and keeps Scrum working. A guide, not a boss.</div>' +
        '<div class="role-card" style="--c:#7c3aed"><small>Seven people</small><b>Developers</b>Decide <i>how</i> to build it and who does ' +
        'which task. Each has their own skills, habits and opinions.</div></div><div class="mini">' +
        '<div><h3>Events</h3><ul><li><b>Sprint Planning:</b> choose the work and the Sprint Goal</li><li><b>Daily Scrum:</b> the Developers check progress</li>' +
        '<li><b>Sprint Review:</b> show stakeholders what is done</li><li><b>Retrospective:</b> improve how the team works</li></ul></div>' +
        '<div><h3>Artifacts and their goals</h3><ul><li><b>Product Backlog</b> → Product Goal</li><li><b>Sprint Backlog</b> → Sprint Goal</li>' +
        '<li><b>Increment</b> (the finished work) → Definition of Done</li></ul></div></div>';
    },
    function () {
      return '<h1 id="obTitle">How your Sprint will run</h1><p class="lead">One Sprint, five working days, compressed into about 20 minutes.</p>' +
        '<ol class="plan"><li class="opt"><span><b>Optional warm-up</b>: five quick questions you can skip</span><span class="t">1 min</span></li>' +
        '<li><span><b>The briefing</b>: meet your sponsor and set the Product Goal</span><span class="t">2 min</span></li>' +
        '<li><span><b>Sprint Planning</b>: choose the work that fits, then write the Sprint Goal</span><span class="t">4 min</span></li>' +
        '<li><span><b>Days 2 to 5</b>: real situations land in the team chat. Type what you would say; the team reacts and Sam coaches</span><span class="t">10 min</span></li>' +
        '<li><span><b>Debrief</b>: how you did on each Product Owner skill, and what to try next time</span><span class="t">2 min</span></li></ol>';
    },
    function () {
      return '<h1 id="obTitle">Choose your scenario</h1><p class="lead">Every scenario is a real product for people who need it. ' +
        'More are on the way.</p><div class="scenarios">' +
        '<button type="button" class="scenario" aria-pressed="true" data-pack="flood-alert"><b>🌊 RiverWatch Alerts</b>' +
        '<small>Text-message flood warnings for a rural county, in English and Spanish.</small></button>' +
        '<button type="button" class="scenario" disabled><b>🏥 Clinic Finder</b><small>A low-data phone guide to the nearest free clinic.</small><span class="soon">COMING SOON</span></button>' +
        '<button type="button" class="scenario" disabled><b>🍎 Food Bank Volunteers</b><small>Scheduling volunteers for a community food bank.</small><span class="soon">COMING SOON</span></button></div>';
    }
  ];
  function showOnboard(i, onFinish) {
    obIndex = i; var ob = document.getElementById('onboard'); ob.hidden = false;
    document.getElementById('obBody').innerHTML = OB[i]();
    var prog = document.getElementById('obProgress'); prog.textContent = '';
    OB.forEach(function (_, j) { prog.appendChild(el('i', j <= i ? 'on' : '')); });
    document.getElementById('obBack').disabled = i === 0;
    var next = document.getElementById('obNext');
    next.textContent = i === OB.length - 1 ? (onFinish ? 'Start my Sprint' : 'Back to my Sprint') : 'Next';
    next.onclick = function () {
      if (i < OB.length - 1) return showOnboard(i + 1, onFinish);
      ob.hidden = true; if (onFinish) onFinish();
    };
    document.getElementById('obBack').onclick = function () { showOnboard(Math.max(0, i - 1), onFinish); };
    next.focus();
  }

  var TOUR = [
    ['teamPanel', 'Your team', 'Three roles: you are the Product Owner, Sam is the Scrum Master, and seven Developers do the building. Whoever is speaking lights up.'],
    ['chatPanel', 'The team chat', 'Each day, something happens here. Look for the blue "Your call" card, then type what you would say.'],
    ['boardPanel', 'The Scrum board', 'Your goals and the Sprint\'s work. Cards move across the board as the days pass.'],
    ['timeline', 'Your progress', 'From setup to the debrief. Reopen "How it works" anytime.']
  ];
  function showTour(i) {
    var tour = document.getElementById('tour');
    if (i >= TOUR.length) { tour.hidden = true; store('sz-toured', '1'); return; }
    var target = document.getElementById(TOUR[i][0]);
    if (!target || !target.offsetParent) return showTour(i + 1);   // hidden on small screens
    tour.hidden = false; target.scrollIntoView({ block: 'nearest' });
    var r = target.getBoundingClientRect(), hole = document.getElementById('tourHole'), tip = document.getElementById('tourTip');
    hole.style.left = (r.left - 6) + 'px'; hole.style.top = (r.top - 6) + 'px';
    hole.style.width = (r.width + 12) + 'px'; hole.style.height = (r.height + 12) + 'px';
    tip.innerHTML = ''; tip.appendChild(el('b', null, TOUR[i][1])); tip.appendChild(el('div', null, TOUR[i][2]));
    var row = el('div', 'row'), btn = el('button', 'btn', i === TOUR.length - 1 ? 'Got it' : 'Next');
    row.appendChild(el('small', null, (i + 1) + ' of ' + TOUR.length)); row.appendChild(btn); tip.appendChild(row);
    btn.addEventListener('click', function () { showTour(i + 1); });
    var left = r.right + 16 + 320 < innerWidth ? r.right + 16 : Math.max(16, r.left - 336);
    if (left < 16 || r.width > innerWidth * .6) { left = Math.min(innerWidth - 336, Math.max(16, r.left + 16)); tip.style.top = Math.min(innerHeight - 200, r.bottom + 14) + 'px'; }
    else tip.style.top = Math.max(16, Math.min(innerHeight - 220, r.top + 24)) + 'px';
    tip.style.left = left + 'px'; btn.focus();
  }

  document.getElementById('howBtn').addEventListener('click', function () { showOnboard(0, null); });
  var saved = store('sz-session');
  function firstRun() { showOnboard(0, function () { start(chosenPack).then(function () { if (!store('sz-toured')) showTour(0); }); }); }
  if (saved) api('GET', '/api/sessions/' + saved).then(load).catch(firstRun); else firstRun();
})();
