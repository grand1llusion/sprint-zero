(function () {
  'use strict';
  var COLOURS = { you: '#2563eb', sam: '#0f766e', priya: '#7c3aed', marcus: '#ea580c', sofia: '#db2777', kenji: '#0891b2',
                  dana: '#475569', leah: '#ca8a04', jordan: '#16a34a', rosa: '#9333ea', pruitt: '#b45309' };
  var LEVEL = { strong: 'STRONG', partial: 'PARTIAL', weak: 'WEAK', off_topic: 'OFF TOPIC' };
  var view = null, busy = false, picked = [];

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
  function renderTeam() {
    var t = document.getElementById('team'); t.textContent = '';
    [view.team.scrum_master].concat(view.team.developers).forEach(function (p) {
      var m = el('div', 'member'); m.id = 'm-' + p.id; m.appendChild(avatar(p));
      var d = el('div'); d.appendChild(el('b', null, p.name)); d.appendChild(el('small', null, p.role)); m.appendChild(d); t.appendChild(m);
    });
    var s = document.getElementById('stakeholders'); s.textContent = '';
    view.pack.stakeholders.forEach(function (p) {
      var m = el('div', 'member'); m.id = 'm-' + p.id; m.appendChild(avatar(p));
      var d = el('div'); d.appendChild(el('b', null, p.name)); d.appendChild(el('small', null, p.role)); m.appendChild(d); s.appendChild(m);
    });
    document.getElementById('packTitle').textContent = view.pack.title + ': ' + view.pack.tagline;
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
    if (item.type === 'quiz') return el('div', 'system', item.title + ': ' + item.correct + ' of ' + item.of + ' correct');
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
      var ta = el('textarea'); ta.placeholder = 'Type what you would say…'; ta.maxLength = 1500; ta.setAttribute('aria-label', s.prompt);
      var row = el('div', 'row'), hint = el('small', null, 'Ctrl+Enter to send'), send = el('button', 'btn', 'Send');
      send.addEventListener('click', function () { if (ta.value.trim()) submit(ta.value.trim()); });
      ta.addEventListener('keydown', function (e) { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) send.click(); });
      row.appendChild(hint); row.appendChild(send); c.appendChild(ta); c.appendChild(row); ta.focus();
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
      var qrow = el('div', 'row'), qbtn = el('button', 'btn', 'Submit answers');
      qbtn.addEventListener('click', function () {
        var answers = s.questions.map(function (q, i) { var r = form.querySelector('input[name=q' + i + ']:checked'); return r ? +r.value : null; });
        if (answers.indexOf(null) >= 0) { qrow.firstChild.textContent = 'Answer every question first.'; return; }
        submit(answers);
      });
      qrow.appendChild(el('small', null, s.title)); qrow.appendChild(qbtn); c.appendChild(form); c.appendChild(qrow);
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
      c.appendChild(el('p', null, s.prompt)); c.appendChild(list); c.appendChild(prow); update();
    } else {
      var again = el('button', 'btn ghost', 'Play again');
      again.addEventListener('click', function () { store('sz-session', ''); start(); });
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
    r.flags.forEach(function (f) { d.appendChild(el('small', null, f)); });
    return d;
  }

  // ---------------------------------------------------------------- flow
  function render(previousFeedLength) {
    renderTimeline(); renderBoard(); renderFeed(previousFeedLength); renderComposer();
    var last = view.feed.slice(previousFeedLength || 0).filter(function (i) { return i.type === 'reaction' || i.type === 'prompt'; });
    highlightSpeakers(last.map(function (i) { return i.type === 'prompt' ? i.speaker.id : i.id; }));
  }
  function submit(answer) {
    if (busy) return; busy = true;
    var c = document.getElementById('composer'); c.querySelectorAll('button,textarea,input').forEach(function (x) { x.disabled = true; });
    var typing = el('div', 'typing', 'The team is responding'); ['.', '.', '.'].forEach(function (d) { typing.appendChild(el('span', null, d)); });
    var feed = document.getElementById('feed'); feed.appendChild(typing); feed.scrollTop = feed.scrollHeight;
    var before = view.feed.length;
    api('POST', '/api/sessions/' + view.id + '/answer', { step: view.step.number, answer: answer })
      .then(function (v) { view = v; typing.remove(); render(before); })
      .catch(function (e) { typing.textContent = 'Something went wrong: ' + e.message; renderComposer(); })
      .then(function () { busy = false; });
  }
  function load(v) { view = v; store('sz-session', v.id); renderTeam(); render(0); }
  function start() { api('POST', '/api/sessions', { pack: 'flood-alert' }).then(load); }

  var saved = store('sz-session');
  if (saved) api('GET', '/api/sessions/' + saved).then(load).catch(start); else start();
})();
