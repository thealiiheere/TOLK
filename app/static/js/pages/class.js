// Public class page, teacher profile page, and the enroll (pay + upload receipt) sheet.
import {
  api, avatar, busy, empty, errorBox, fmtPrice, go, html, icon, loading, mount, on, openSheet, periodLabel,
  ratingBadge, state, subjectIcon, subjectInfo, toast, toastError,
} from '../core.js';
import { t } from '../i18n.js';
import { classGrid, ratingSummary, reviewList, seatsInfo } from './components.js';

let current = null; // group shown on the class page

function cta(g) {
  const u = state.user;
  if (!u) return html`<button class="btn btn-primary btn-lg btn-block" data-action="go-login" data-next="/class/${g.id}">${t('sign_in_to_enroll')}</button>`;
  if (u.role !== 'student') return html`<div class="notice notice-info small"><span class="ico">ℹ️</span><div>${t('only_students_enroll')}</div></div>`;
  if (g.my.enrolled) return html`<a class="btn btn-success btn-lg btn-block" href="#/my">${icon('check')} ${t('you_are_enrolled')}</a>`;
  if (g.my.pending_payment) return html`<button class="btn btn-outline btn-lg btn-block" disabled>⏳ ${t('payment_under_review')}</button>`;
  if (g.seats_left === 0) return html`<button class="btn btn-outline btn-lg btn-block" disabled>${t('class_full')}</button>`;
  return html`<button class="btn btn-accent btn-lg btn-block" data-action="enroll-open">${t('enroll_now')}</button>`;
}

export async function renderClass(view, params, _query, alive) {
  mount(view, html`<div class="container">${loading()}</div>`);
  let g;
  try {
    g = await api(`/api/catalog/groups/${params.id}`);
  } catch (err) {
    if (alive()) mount(view, html`<div class="container">${errorBox(err)}</div>`);
    return;
  }
  if (!alive()) return;
  current = g;
  const s = subjectInfo(g);
  const tutor = g.tutor;
  mount(view, html`
    <div class="container">
      <div class="detail">
        <div class="stack-lg">
          <div class="cover detail-cover" style="--h:${s.hue}">${subjectIcon(s, 'xl')}<span class="subject">${s.label}</span></div>
          <div>
            <div class="row-wrap" style="margin-bottom:8px">
              <span class="badge badge-primary">${g.category === 'language' ? t('cat_language') : t('cat_other')}</span>
              ${g.level ? html`<span class="badge">${icon('level')} ${g.level}</span>` : ''}
              ${!g.is_published ? html`<span class="badge badge-warning">${t('unpublished')}</span>` : ''}
            </div>
            <h1 style="font-size:clamp(24px,4vw,32px)">${g.title}</h1>
            ${tutor ? html`<div class="row mt">${avatar(tutor, 'avatar-sm')}<a href="#/teacher/${tutor.id}" class="bold">${tutor.full_name}</a>${ratingBadge(tutor)}</div>` : ''}
          </div>
          <div class="facts">
            <div class="fact"><div class="k">${t('schedule')}</div><div class="v">${g.schedule || '—'}</div></div>
            <div class="fact"><div class="k">${t('price')}</div><div class="v">${fmtPrice(g.price)} / ${periodLabel(g.price_period)}</div></div>
            <div class="fact"><div class="k">${t('group_size_label')}</div><div class="v">${t('group_size', { n: g.enrolled, max: g.max_students })}</div></div>
            <div class="fact"><div class="k">${t('format')}</div><div class="v">${t('format_online')}</div></div>
          </div>
          ${g.description ? html`<div class="card card-pad"><h3 style="margin-bottom:10px">${t('about_class')}</h3><p class="prose">${g.description}</p></div>` : ''}
          ${tutor ? html`<div class="card card-pad">
            <h3 style="margin-bottom:14px">${t('your_teacher')}</h3>
            <div class="row" style="align-items:flex-start">${avatar(tutor, 'avatar-lg')}
              <div class="grow"><a href="#/teacher/${tutor.id}" class="bold" style="font-size:17px">${tutor.full_name}</a>
                <div style="margin:4px 0">${ratingBadge(tutor)}</div>
                ${tutor.subjects ? html`<div class="small muted">${tutor.subjects}</div>` : ''}</div></div>
            ${tutor.bio ? html`<p class="prose small mt">${tutor.bio}</p>` : ''}
            <a class="btn btn-soft btn-sm mt" href="#/teacher/${tutor.id}">${t('view_profile')} ${icon('arrow')}</a>
          </div>` : ''}
          <div class="card card-pad">
            <h3 style="margin-bottom:14px">${t('student_reviews')}</h3>
            ${ratingSummary(tutor?.rating || 0, tutor?.ratings_count || 0, g.rating_breakdown)}
            <div class="divider"></div>
            ${reviewList(g.reviews)}
          </div>
        </div>
        <aside class="side">
          <div class="card card-pad stack">
            <div class="price" style="font-size:26px">${fmtPrice(g.price)} <small>/ ${periodLabel(g.price_period)}</small></div>
            <div>${seatsInfo(g)}</div>
            ${cta(g)}
            <div class="divider" style="margin:4px 0"></div>
            <h4>${t('how_enroll_works')}</h4>
            <ol class="steps"><li>${t('enroll_step_1')}</li><li>${t('enroll_step_2')}</li><li>${t('enroll_step_3')}</li></ol>
          </div>
        </aside>
      </div>
    </div>
    <div class="sticky-cta"><div class="between"><div class="price">${fmtPrice(g.price)} <small>/ ${periodLabel(g.price_period)}</small></div><div style="flex:0 0 55%">${cta(g)}</div></div></div>`);
}

export async function renderTeacher(view, params, _query, alive) {
  mount(view, html`<div class="container">${loading()}</div>`);
  let tutor;
  try {
    tutor = await api(`/api/catalog/tutors/${params.id}`);
  } catch (err) {
    if (alive()) mount(view, html`<div class="container">${errorBox(err)}</div>`);
    return;
  }
  if (!alive()) return;
  mount(view, html`
    <div class="container stack-lg">
      <div class="card card-pad">
        <div class="row" style="align-items:flex-start;gap:16px">${avatar(tutor, 'avatar-lg')}
          <div class="grow">
            <h1 style="font-size:26px">${tutor.full_name}</h1>
            <div style="margin:6px 0">${ratingBadge(tutor)}</div>
            ${tutor.subjects ? html`<div class="chips mt">${tutor.subjects.split(',').map((x) => html`<span class="badge badge-primary">${x.trim()}</span>`)}</div>` : ''}
          </div>
        </div>
        ${tutor.bio ? html`<p class="prose mt-lg">${tutor.bio}</p>` : ''}
      </div>
      <div>
        <div class="section-title"><h2>${t('teacher_classes')}</h2></div>
        ${tutor.groups.length ? classGrid(tutor.groups) : empty('📚', t('no_open_classes'))}
      </div>
      <div class="card card-pad">
        <h3 style="margin-bottom:14px">${t('student_reviews')}</h3>
        ${ratingSummary(tutor.rating || 0, tutor.ratings_count, tutor.rating_breakdown)}
        <div class="divider"></div>
        ${reviewList(tutor.reviews)}
      </div>
    </div>`);
}

// ---------- enroll sheet ----------
function enrollSheet(g) {
  const cfg = state.config;
  const sheet = openSheet({
    title: t('enroll_title'),
    body: html`
      <form id="enroll-form" class="stack" data-submit="enroll-submit">
        <div class="between"><div><div class="bold">${g.title}</div><div class="small muted">${g.tutor?.full_name || ''}</div></div>
          <div class="price">${fmtPrice(g.price)}</div></div>
        <div class="notice notice-info small"><span class="ico">💳</span><div>${t('enroll_pay_text', { amount: fmtPrice(g.price) })}</div></div>
        ${cfg.payment_card_number ? html`
          <div class="copy-box"><div><div class="tiny muted">${t('card_number')}</div><div class="mono">${cfg.payment_card_number}</div>
            ${cfg.payment_card_holder ? html`<div class="tiny muted">${cfg.payment_card_holder}</div>` : ''}</div>
            <button type="button" class="btn btn-outline btn-sm" data-action="copy" data-text="${cfg.payment_card_number.replace(/\s/g, '')}">${icon('copy')} ${t('copy')}</button></div>`
          : html`<div class="notice notice-warning small"><span class="ico">⚠️</span><div>${t('card_not_configured', { contact: cfg.support_contact || '' })}</div></div>`}
        <label class="file-drop" id="receipt-drop">
          <input type="file" name="receipt" accept="image/jpeg,image/png,image/webp,application/pdf" data-change="receipt-picked">
          <span style="font-size:30px">🧾</span>
          <span class="bold">${t('upload_receipt')}</span>
          <span class="tiny">${t('upload_receipt_hint', { mb: cfg.max_upload_mb || 5 })}</span>
        </label>
        <button class="btn btn-accent btn-lg btn-block" type="submit">${t('send_for_review')}</button>
        <p class="tiny faint center">${t('enroll_after_text')}</p>
      </form>`,
  });
  return sheet;
}

let enrollRef = null;
on('enroll-open', () => {
  if (!current) return;
  enrollRef = enrollSheet(current);
});
on('receipt-picked', (input) => {
  const file = input.files?.[0];
  const drop = document.getElementById('receipt-drop');
  if (!file || !drop) return;
  drop.querySelectorAll('img,.picked').forEach((n) => n.remove());
  if (file.type.startsWith('image/')) {
    const img = document.createElement('img');
    img.src = URL.createObjectURL(file);
    img.alt = '';
    drop.prepend(img);
  }
  const name = document.createElement('span');
  name.className = 'picked small bold';
  name.textContent = `✓ ${file.name}`;
  drop.appendChild(name);
});
on('enroll-submit', async (form) => {
  const file = form.receipt.files?.[0];
  if (!file) return toast(t('upload_receipt'), 'warning');
  if (file.size > (state.config.max_upload_mb || 5) * 1024 * 1024) return toast(t('file_too_large', { mb: state.config.max_upload_mb || 5 }), 'error');
  const fd = new FormData();
  fd.append('group_id', current.id);
  fd.append('receipt', file);
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      await api('/api/student/enroll', { method: 'POST', form: fd });
      enrollRef?.close();
      toast(t('receipt_sent'), 'success');
      go(`/class/${current.id}`);
    } catch (err) { toastError(err); }
  });
});
on('copy', async (el) => {
  try { await navigator.clipboard.writeText(el.dataset.text); toast(t('copied'), 'success'); } catch { /* ignore */ }
});
on('go-login', (el) => go(`/login?next=${encodeURIComponent(el.dataset.next || '/')}`));
