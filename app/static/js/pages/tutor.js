// Teacher dashboard: schedule lessons (a NEW meeting link every lesson), complete lessons, students, ratings.
import {
  api, avatar, busy, confirmSheet, empty, errorBox, fmtDate, formData, go, html, icon, loading, mount,
  on, openLink, openSheet, state, stars, strikesDots, subjectIcon, subjectInfo, toLocalInput, toast, toastError,
} from '../core.js';
import { t } from '../i18n.js';
import { lessonRow, ratingSummary, reviewList } from './components.js';

let dash = null;
let sheetRef = null;

export async function render(view, _params, _query, alive) {
  mount(view, html`<div class="container">${loading()}</div>`);
  try {
    dash = await api('/api/tutor/dashboard');
  } catch (err) {
    if (alive()) mount(view, html`<div class="container">${errorBox(err)}</div>`);
    return;
  }
  if (!alive()) return;
  const d = dash;
  if (d.tutor_status !== 'approved') {
    const rejected = d.tutor_status === 'rejected';
    mount(view, html`<div class="container" style="max-width:640px"><div class="card">${empty(rejected ? '🙁' : '⏳',
      rejected ? t('application_rejected') : t('application_pending'),
      rejected ? t('application_rejected_text', { contact: state.config.support_contact || '' }) : t('application_pending_text'),
      html`<a class="btn btn-outline" href="#/profile">${t('edit_profile')}</a>`)}</div></div>`);
    return;
  }
  const toComplete = d.groups.reduce((n, g) => n + g.to_complete.length, 0);
  mount(view, html`
    <div class="container stack-lg">
      <div class="page-head">
        <div><h1>${t('teaching')}</h1><p>${t('teaching_subtitle')}</p></div>
        <div class="card card-pad row" style="padding:12px 16px">
          <span style="font-size:26px;font-weight:800">${d.ratings_count ? d.rating.toFixed(1) : '—'}</span>
          <div>${stars(d.rating || 0)}<div class="tiny muted">${t('ratings_count', { n: d.ratings_count })}</div></div>
        </div>
      </div>
      ${toComplete ? html`<div class="notice notice-warning"><span class="ico">📝</span><div>${t('lessons_to_complete', { n: toComplete })}</div></div>` : ''}
      <div class="notice notice-info small"><span class="ico">🔗</span><div>${t('new_link_rule')}</div></div>
      ${d.groups.length ? d.groups.map(groupCard) : html`<div class="card">${empty('📚', t('no_groups_assigned'), t('no_groups_assigned_text'))}</div>`}
      <div class="card card-pad">
        <h3 style="margin-bottom:14px">${t('student_reviews')}</h3>
        ${ratingSummary(d.rating || 0, d.ratings_count, d.rating_breakdown)}
        <div class="divider"></div>
        ${reviewList(d.reviews)}
      </div>
    </div>`);
}

function groupCard(g) {
  const s = subjectInfo(g);
  return html`
    <section class="card">
      <div class="card-head">
        <div class="row grow">${subjectIcon(s)}
          <div class="grow"><h3 class="truncate">${g.title}</h3><div class="tiny muted">${s.label}${g.schedule ? ` · ${g.schedule}` : ''}</div></div></div>
        <button class="btn btn-outline btn-sm" data-action="students-open" data-id="${g.id}">${icon('users')} ${g.enrolled}/${g.max_students}</button>
      </div>
      <div class="card-body stack">
        ${g.to_complete.map((l) => lessonRow(l, {
          sub: html`<div class="tiny" style="color:var(--warning);margin-top:4px">${t('needs_completion')}</div>`,
          actions: html`<button class="btn btn-accent btn-sm" data-action="journal-open" data-group="${g.id}" data-lesson="${l.id}">${icon('check')} ${t('complete_lesson')}</button>`,
        }))}
        ${g.upcoming_lessons.length ? g.upcoming_lessons.map((l) => lessonRow(l, {
          actions: html`
            <button class="btn btn-soft btn-sm" data-action="open-link" data-link="${l.meet_link}">${icon('video')} ${t('start')}</button>
            <button class="btn btn-ghost btn-sm btn-icon" data-action="lesson-edit" data-group="${g.id}" data-lesson="${l.id}" aria-label="${t('edit')}">${icon('edit')}</button>
            <button class="btn btn-ghost btn-sm btn-icon" data-action="lesson-cancel" data-lesson="${l.id}" aria-label="${t('cancel_lesson')}">${icon('trash')}</button>`,
        })) : html`<div class="notice notice-warning small"><span class="ico">📅</span><div><b>${t('no_next_lesson')}</b><br>${t('no_next_lesson_text')}</div></div>`}
        <div><button class="btn ${g.upcoming_lessons.length ? 'btn-outline' : 'btn-primary'}" data-action="lesson-new" data-group="${g.id}">${icon('plus')} ${t('schedule_lesson')}</button></div>
        ${g.completed_lessons.length ? html`<details><summary class="small muted" style="cursor:pointer">${t('recent_lessons')}</summary>
          <div class="list mt">${g.completed_lessons.map((l) => html`<div class="list-item small"><span class="grow">${fmtDate(l.starts_at)}${l.topic ? ` · ${l.topic}` : ''}</span>
            ${l.avg_rating ? html`<span class="rating">${stars(l.avg_rating)} ${l.avg_rating.toFixed(1)}</span>` : html`<span class="tiny faint">${t('no_ratings_yet')}</span>`}</div>`)}</div></details>` : ''}
      </div>
    </section>`;
}

function findLesson(lessonId) {
  for (const g of dash.groups) {
    const l = [...g.upcoming_lessons, ...g.to_complete].find((x) => x.id === lessonId);
    if (l) return { group: g, lesson: l };
  }
  return {};
}

// ---------- schedule / edit lesson ----------
function lessonSheet(group, lesson = null, intro = '') {
  const defaultStart = new Date(Date.now() + 24 * 3600e3);
  defaultStart.setMinutes(0, 0, 0);
  const prevLink = [...group.upcoming_lessons].pop()?.meet_link;
  sheetRef = openSheet({
    title: lesson ? t('edit_lesson') : t('schedule_lesson'),
    body: html`<form class="stack" data-submit="lesson-save" data-group="${group.id}" data-lesson="${lesson?.id || ''}">
      ${intro ? html`<div class="notice notice-success small"><span class="ico">✅</span><div>${intro}</div></div>` : ''}
      <div class="bold">${group.title}</div>
      <div class="form-grid">
        <label class="field"><span>${t('date_time')}</span><input class="input" type="datetime-local" name="starts_at" required
          value="${toLocalInput(lesson ? lesson.starts_at : defaultStart)}"></label>
        <label class="field"><span>${t('duration')}</span><select class="select" name="duration_min">
          ${[45, 60, 90, 120].map((m) => html`<option value="${m}" ${(lesson?.duration_min || 60) === m ? 'selected' : ''}>${t('minutes', { n: m })}</option>`)}</select></label>
        <label class="field full"><span>${t('topic')} <span class="faint">(${t('optional')})</span></span>
          <input class="input" name="topic" maxlength="200" value="${lesson?.topic || ''}" placeholder="${t('topic_placeholder')}"></label>
        <label class="field full"><span>${t('meeting_link')}</span>
          <input class="input" name="meet_link" type="url" required value="${lesson?.meet_link || ''}" placeholder="https://meet.google.com/abc-defg-hij">
          <span class="hint">${t('meeting_link_hint')}</span></label>
      </div>
      ${!lesson && prevLink ? html`<div class="tiny faint">${t('previous_link')}: ${prevLink}</div>` : ''}
      <div class="row-wrap tiny muted"><span>${t('create_meeting_in')}</span>
        <a href="https://meet.google.com/new" target="_blank" rel="noopener">Google Meet ↗</a>
        <a href="https://zoom.us/meeting/schedule" target="_blank" rel="noopener">Zoom ↗</a></div>
      <button class="btn btn-primary btn-lg btn-block" type="submit">${lesson ? t('save') : t('schedule_and_notify')}</button>
    </form>`,
  });
}

on('lesson-new', (el) => {
  const group = dash.groups.find((g) => g.id === Number(el.dataset.group));
  if (group) lessonSheet(group);
});
on('lesson-edit', (el) => {
  const { group, lesson } = findLesson(Number(el.dataset.lesson));
  if (lesson) lessonSheet(group, lesson);
});
on('lesson-save', async (form) => {
  const data = formData(form);
  const body = {
    starts_at: new Date(data.starts_at).toISOString(),
    duration_min: Number(data.duration_min),
    topic: data.topic,
    meet_link: data.meet_link.trim(),
  };
  const lessonId = form.dataset.lesson;
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      if (lessonId) await api(`/api/tutor/lessons/${lessonId}`, { method: 'PATCH', body });
      else await api('/api/tutor/lessons', { method: 'POST', body: { ...body, group_id: Number(form.dataset.group) } });
      sheetRef?.close();
      toast(lessonId ? t('lesson_updated') : t('lesson_scheduled'), 'success');
      go('/teach');
    } catch (err) { toastError(err); }
  });
});
on('lesson-cancel', async (el) => {
  if (!(await confirmSheet(t('cancel_lesson_confirm'), { okText: t('cancel_lesson'), danger: true }))) return;
  try {
    await api(`/api/tutor/lessons/${el.dataset.lesson}/cancel`, { method: 'POST' });
    toast(t('lesson_cancelled'), 'success');
    go('/teach');
  } catch (err) { toastError(err); }
});
on('open-link', (el) => openLink(el.dataset.link));

// ---------- complete lesson (journal) ----------
on('journal-open', async (el) => {
  const groupId = Number(el.dataset.group);
  const lessonId = Number(el.dataset.lesson);
  const { lesson } = findLesson(lessonId);
  let data;
  try { data = await api(`/api/tutor/groups/${groupId}/students`); } catch (err) { return toastError(err); }
  sheetRef = openSheet({
    title: t('complete_lesson'),
    wide: true,
    body: html`<form data-submit="journal-save" data-group="${groupId}" data-lesson="${lessonId}">
      <div class="small muted">${data.title} · ${fmtDate(lesson?.starts_at, { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })}</div>
      ${data.students.length ? data.students.map((s) => html`
        <div class="journal-row" data-student="${s.id}">
          <div class="row">${avatar(s, 'avatar-sm')}<div class="grow"><div class="bold small truncate">${s.full_name}</div>
            <div class="row tiny muted">${strikesDots(s.strikes)}${s.latest_homework ? html`<a href="${s.latest_homework.link}" target="_blank" rel="noopener">${t('latest_homework')}</a>` : ''}</div></div></div>
          <div class="seg" data-field="attended">
            <button type="button" class="active" data-action="seg" data-v="1">${t('present')}</button>
            <button type="button" data-action="seg" data-v="0">${t('absent')}</button></div>
          <div class="seg" data-field="hw_status">
            <button type="button" data-action="seg" data-v="done">👍 ${t('hw_done')}</button>
            <button type="button" class="active" data-action="seg" data-v="none">—</button>
            <button type="button" data-action="seg" data-v="strike">❌ ${t('hw_strike')}</button></div>
        </div>`) : html`<p class="muted mt">${t('no_students_yet')}</p>`}
      <p class="tiny faint mt">${t('journal_hint')}</p>
      <button class="btn btn-primary btn-lg btn-block mt" type="submit">${t('save_and_complete')}</button>
    </form>`,
  });
});
on('seg', (el) => {
  el.parentElement.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b === el));
});
on('journal-save', async (form) => {
  const records = [...form.querySelectorAll('[data-student]')].map((row) => ({
    student_id: Number(row.dataset.student),
    attended: row.querySelector('[data-field="attended"] .active').dataset.v === '1',
    hw_status: row.querySelector('[data-field="hw_status"] .active').dataset.v,
  }));
  const groupId = Number(form.dataset.group);
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      await api(`/api/tutor/lessons/${form.dataset.lesson}/complete`, { method: 'POST', body: { records } });
      sheetRef?.close();
      const group = dash.groups.find((g) => g.id === groupId);
      // Ask for the next lesson (with a new link) right away if nothing is scheduled.
      if (group && !group.upcoming_lessons.length) lessonSheet(group, null, t('lesson_completed_next'));
      else toast(t('lesson_completed'), 'success');
      const view = document.getElementById('view');
      render(view, {}, {}, () => true);
    } catch (err) { toastError(err); }
  });
});

// ---------- students ----------
on('students-open', async (el) => {
  const groupId = Number(el.dataset.id);
  let data;
  try { data = await api(`/api/tutor/groups/${groupId}/students`); } catch (err) { return toastError(err); }
  sheetRef = openSheet({
    title: data.title,
    wide: true,
    body: data.students.length ? html`<div class="list">${data.students.map((s) => html`
      <div class="list-item">${avatar(s)}
        <div class="grow"><div class="bold">${s.full_name}</div>
          <div class="row-wrap tiny muted">${s.telegram_username ? html`<a href="https://t.me/${s.telegram_username.replace('@', '')}" target="_blank" rel="noopener">${s.telegram_username}</a>` : ''}
            ${s.latest_homework ? html`<a href="${s.latest_homework.link}" target="_blank" rel="noopener">📎 ${t('latest_homework')} (${fmtDate(s.latest_homework.submitted_at)})</a>` : html`<span>${t('no_homework_yet')}</span>`}</div></div>
        <div class="row" style="gap:4px">${strikesDots(s.strikes)}
          <button class="btn btn-ghost btn-sm btn-icon" data-action="strike" data-group="${groupId}" data-student="${s.id}" data-op="remove" aria-label="−1">−</button>
          <button class="btn btn-ghost btn-sm btn-icon" data-action="strike" data-group="${groupId}" data-student="${s.id}" data-op="add" aria-label="+1">+</button></div>
      </div>`)}</div>` : empty('👥', t('no_students_yet')),
  });
});
on('strike', async (el) => {
  try {
    const res = await api('/api/tutor/strikes', { method: 'POST', body: {
      group_id: Number(el.dataset.group), student_id: Number(el.dataset.student), action: el.dataset.op,
    } });
    const dots = el.parentElement.querySelector('.strikes');
    dots.outerHTML = String(strikesDots(res.strikes));
  } catch (err) { toastError(err); }
});


