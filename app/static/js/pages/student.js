// Student dashboard: upcoming lessons (join links), lessons to rate, my classes, homework, payments.
import {
  api, avatar, busy, empty, errorBox, fmtDate, fmtPrice, formData, go, html, icon, loading, mount, on, openLink,
  openSheet, state, stars, strikesDots, subjectIcon, subjectInfo, toast, toastError,
} from '../core.js';
import { t } from '../i18n.js';
import { lessonRow, paymentStatus } from './components.js';

const JOIN_EARLY_MIN = 15; // the join button turns green this many minutes before the start

export async function render(view, _params, _query, alive) {
  mount(view, html`<div class="container">${loading()}</div>`);
  let d;
  try {
    d = await api('/api/student/dashboard');
  } catch (err) {
    if (alive()) mount(view, html`<div class="container">${errorBox(err)}</div>`);
    return;
  }
  if (!alive()) return;
  const first = state.user.full_name.split(' ')[0];
  const nothing = !d.classes.length && !d.payments.length;

  mount(view, html`
    <div class="container stack-lg">
      <div class="page-head">
        <div><h1>${t('hi_name', { name: first })}</h1><p>${t('my_learning_subtitle')}</p></div>
        <a class="btn btn-soft" href="#/">${icon('compass')} ${t('find_classes')}</a>
      </div>
      ${nothing ? html`<div class="card">${empty('🎒', t('no_classes_yet'), t('no_classes_yet_text'),
        html`<a class="btn btn-primary" href="#/">${t('explore_classes')}</a>`)}</div>` : ''}
      ${d.to_rate.length ? html`<section><div class="section-title"><h2>⭐ ${t('rate_lessons')}</h2></div>
        <div class="grid grid-2">${d.to_rate.map(rateCard)}</div></section>` : ''}
      ${d.classes.length ? html`<section><div class="section-title"><h2>${t('upcoming_lessons')}</h2></div>
        ${d.upcoming_lessons.length ? html`<div class="stack">${d.upcoming_lessons.map(upcomingRow)}</div>`
          : html`<div class="card">${empty('📅', t('no_upcoming'), t('no_upcoming_text'))}</div>`}</section>` : ''}
      ${d.classes.length ? html`<section><div class="section-title"><h2>${t('my_classes')}</h2></div>
        <div class="grid grid-2">${d.classes.map(classCard)}</div></section>` : ''}
      ${d.payments.length ? html`<section><div class="section-title"><h2>${t('payments')}</h2></div>
        <div class="card card-pad list">${d.payments.map((p) => html`
          <div class="list-item"><div class="grow"><div class="bold truncate">${p.group_title || '—'}</div>
            <div class="tiny muted">${fmtDate(p.created_at)} · ${fmtPrice(p.amount)}</div>
            ${p.status === 'rejected' && p.admin_comment ? html`<div class="tiny" style="color:var(--danger)">${p.admin_comment}</div>` : ''}
            ${p.status === 'pending' ? html`<div class="tiny muted">${t('payment_pending_hint')}</div>` : ''}</div>
            ${paymentStatus(p.status)}</div>`)}</div></section>` : ''}
      ${d.history.length ? html`<section><div class="section-title"><h2>${t('past_lessons')}</h2></div>
        <div class="card card-pad list">${d.history.map((l) => html`
          <div class="list-item"><div class="grow"><div class="bold truncate">${l.group_title}</div>
            <div class="tiny muted">${fmtDate(l.starts_at)}${l.topic ? ` · ${l.topic}` : ''}</div></div>
            ${l.my_rating ? stars(l.my_rating) : html`<span class="tiny faint">${t('absent')}</span>`}</div>`)}</div></section>` : ''}
      ${d.homework.length ? html`<section><div class="section-title"><h2>${t('homework')}</h2></div>
        <div class="card card-pad list">${d.homework.slice(0, 8).map((h) => html`
          <div class="list-item"><div class="grow"><a class="bold truncate" style="display:block" href="${h.link}" target="_blank" rel="noopener">${h.link}</a>
            <div class="tiny muted">${h.group_title || ''} · ${fmtDate(h.submitted_at)}${h.comment ? ` · ${h.comment}` : ''}</div></div></div>`)}</div></section>` : ''}
    </div>`);
}

function upcomingRow(l) {
  const startsIn = (new Date(l.starts_at) - Date.now()) / 60000;
  const ready = l.is_live || startsIn <= JOIN_EARLY_MIN;
  const action = l.meet_link
    ? html`<button class="btn ${ready ? 'btn-success' : 'btn-primary'}" data-action="join" data-link="${l.meet_link}">${icon('video')} ${t('join_lesson')}</button>`
    : html`<span class="badge badge-danger">${t('access_closed')}</span>`;
  return lessonRow(l, { title: l.group_title, actions: action });
}

function rateCard(l) {
  return html`
    <form class="card card-pad stack" data-submit="rate-submit" data-id="${l.id}">
      <div><div class="bold">${l.group_title}</div><div class="tiny muted">${fmtDate(l.starts_at, { weekday: 'long', day: 'numeric', month: 'long' })}${l.topic ? ` · ${l.topic}` : ''}</div></div>
      <div class="small">${t('how_was_lesson')}</div>
      <div class="star-pick" role="radiogroup" aria-label="${t('rating')}">
        ${[1, 2, 3, 4, 5].map((n) => html`<button type="button" data-action="rate-pick" data-n="${n}" aria-label="${n}">★</button>`)}
      </div>
      <input type="hidden" name="stars" value="">
      <div data-more hidden class="stack">
        <textarea class="textarea" name="comment" maxlength="500" placeholder="${t('rating_comment_placeholder')}" style="min-height:70px"></textarea>
        <button class="btn btn-primary" type="submit">${t('send_rating')}</button>
      </div>
    </form>`;
}

function classCard(c) {
  const s = subjectInfo(c);
  return html`
    <div class="card card-pad stack">
      <div class="row">${subjectIcon(s)}
        <div class="grow"><a class="bold" href="#/class/${c.id}">${c.title}</a><div class="tiny muted">${s.label}${c.level ? ` · ${c.level}` : ''}</div></div></div>
      ${c.tutor ? html`<div class="row small">${avatar(c.tutor, 'avatar-sm')}<span class="grow truncate">${c.tutor.full_name}</span>
        ${c.tutor.telegram_username ? html`<a class="btn btn-ghost btn-sm" href="https://t.me/${c.tutor.telegram_username.replace('@', '')}" target="_blank" rel="noopener">${t('message')}</a>` : ''}</div>` : ''}
      ${c.schedule ? html`<div class="row small muted">${icon('calendar')}<span>${c.schedule}</span></div>` : ''}
      <div class="between small"><span class="muted">${t('homework_strikes')}</span>${strikesDots(c.strikes)}</div>
      ${c.access_revoked ? html`<div class="notice notice-danger small"><span class="ico">⛔</span><div>${t('access_revoked_text', { contact: state.config.support_contact || '' })}</div></div>`
        : c.strikes > 0 ? html`<div class="notice notice-warning small"><span class="ico">⚠️</span><div>${t('strikes_warning', { n: c.strikes })}</div></div>` : ''}
      <div class="row-wrap">
        <button class="btn btn-soft btn-sm" data-action="hw-open" data-id="${c.id}" data-title="${c.title}" ${c.access_revoked ? 'disabled' : ''}>${icon('book')} ${t('submit_homework')}</button>
        <a class="btn btn-ghost btn-sm" href="#/class/${c.id}">${t('class_page')}</a>
      </div>
    </div>`;
}

on('join', (el) => openLink(el.dataset.link));
on('rate-pick', (el) => {
  const form = el.closest('form');
  const n = Number(el.dataset.n);
  form.stars.value = n;
  form.querySelectorAll('[data-action="rate-pick"]').forEach((b) => b.classList.toggle('on', Number(b.dataset.n) <= n));
  form.querySelector('[data-more]').hidden = false;
});
on('rate-submit', async (form) => {
  const stars = Number(form.stars.value);
  if (!stars) return toast(t('pick_stars'), 'warning');
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      await api(`/api/student/lessons/${form.dataset.id}/rate`, { method: 'POST', body: { stars, comment: form.comment.value } });
      toast(t('thanks_for_rating'), 'success');
      go('/my');
    } catch (err) { toastError(err); }
  });
});

let hwSheet = null;
on('hw-open', (el) => {
  hwSheet = openSheet({
    title: t('submit_homework'),
    body: html`<form class="stack" data-submit="hw-submit" data-group="${el.dataset.id}">
      <div class="bold">${el.dataset.title}</div>
      <label class="field"><span>${t('homework_link')}</span><input class="input" name="link" type="url" required placeholder="https://drive.google.com/..."></label>
      <label class="field"><span>${t('comment')} <span class="faint">(${t('optional')})</span></span><input class="input" name="comment" maxlength="500"></label>
      <button class="btn btn-primary btn-block" type="submit">${t('send')}</button></form>`,
  });
});
on('hw-submit', async (form) => {
  const data = formData(form);
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      await api('/api/student/homework', { method: 'POST', body: { group_id: Number(form.dataset.group), ...data } });
      hwSheet?.close();
      toast(t('homework_sent'), 'success');
      go('/my');
    } catch (err) { toastError(err); }
  });
});
