// Admin panel: overview, payments (receipts), classes (create / edit / students), teachers, users, discipline.
import {
  api, avatar, busy, codeBadge, confirmSheet, empty, errorBox, fmtDate, fmtDateTime, fmtPrice, formData, go, html, icon, loading,
  mount, on, openSheet, periodLabel, ratingBadge, state, strikesDots, subjectIcon, subjectInfo, toast, toastError,
} from '../core.js';
import { LANGUAGE_CODES, subjectName, t } from '../i18n.js';
import { documentList, paymentStatus } from './components.js';

const TABS = ['overview', 'payments', 'classes', 'teachers', 'users', 'discipline'];
let stats = {};
let cache = {};
let sheetRef = null;
let receiptUrls = [];

export async function render(view, params, query, alive) {
  const tab = TABS.includes(params.tab) ? params.tab : 'overview';
  mount(view, html`<div class="container"><div class="page-head"><div><h1>${t('admin_panel')}</h1></div></div>
    <nav class="tabs" id="admin-tabs">${tabs(tab)}</nav><div id="admin-body">${loading()}</div></div>`);
  try {
    stats = await api('/api/admin/stats');
    if (!alive()) return;
    mount(document.getElementById('admin-tabs'), tabs(tab));
    const body = document.getElementById('admin-body');
    receiptUrls.forEach((u) => URL.revokeObjectURL(u));
    receiptUrls = [];
    await PAGES[tab](body, query, alive);
  } catch (err) {
    if (alive()) mount(document.getElementById('admin-body'), errorBox(err));
  }
}

function tabs(active) {
  const counts = { payments: stats.pending_payments, teachers: stats.pending_tutors, discipline: stats.violations };
  return TABS.map((tab) => html`<a href="#/admin/${tab}" class="${tab === active ? 'active' : ''}">${t(`admin_${tab}`)}
    ${counts[tab] ? html`<span class="count-dot">${counts[tab]}</span>` : ''}</a>`);
}

const reload = () => go(location.hash.slice(1));

// ---------- overview ----------
async function overview(body) {
  const s = stats;
  const tile = (v, k, href) => html`<a class="card stat" href="${href || '#/admin'}" style="color:inherit;text-decoration:none"><div class="v">${v}</div><div class="k">${k}</div></a>`;
  mount(body, html`
    <div class="stack-lg">
      <div class="grid grid-stats">
        ${tile(s.pending_payments, t('stat_pending_payments'), '#/admin/payments')}
        ${tile(s.students, t('stat_students'), '#/admin/users')}
        ${tile(s.tutors, t('stat_teachers'), '#/admin/teachers')}
        ${tile(s.groups, t('stat_classes'), '#/admin/classes')}
        ${tile(s.enrollments, t('stat_enrollments'), '#/admin/classes')}
        ${tile(s.upcoming_lessons, t('stat_upcoming_lessons'))}
        ${tile(fmtPrice(s.revenue_month), t('stat_revenue_month'), '#/admin/payments?status=approved')}
        ${tile(fmtPrice(s.revenue_total), t('stat_revenue_total'), '#/admin/payments?status=approved')}
        ${tile(s.avg_rating ? `${s.avg_rating.toFixed(2)} ★` : '—', t('stat_avg_rating'))}
        ${tile(s.violations, t('stat_violations'), '#/admin/discipline')}
      </div>
      <div class="row-wrap">
        <button class="btn btn-primary" data-action="group-new">${icon('plus')} ${t('create_class')}</button>
        <a class="btn btn-outline" href="#/admin/payments">${t('review_payments')}${s.pending_payments ? html` <span class="count-dot">${s.pending_payments}</span>` : ''}</a>
        <a class="btn btn-outline" href="#/admin/teachers">${t('teacher_applications')}${s.pending_tutors ? html` <span class="count-dot">${s.pending_tutors}</span>` : ''}</a>
      </div>
    </div>`);
}

// ---------- payments ----------
async function payments(body, query, alive) {
  const status = ['pending', 'approved', 'rejected', 'all'].includes(query.status) ? query.status : 'pending';
  const list = await api('/api/admin/payments', { query: { status } });
  if (!alive()) return;
  cache.payments = list;
  mount(body, html`
    <div class="seg" style="margin-bottom:16px">${['pending', 'approved', 'rejected', 'all'].map((s) =>
      html`<button class="${s === status ? 'active' : ''}" data-action="nav" data-to="/admin/payments?status=${s}">${t(s === 'all' ? 'all' : `payment_${s}`)}</button>`)}</div>
    ${list.length ? html`<div class="stack">${list.map((p) => html`
      <div class="card card-pad row" style="align-items:flex-start;flex-wrap:wrap">
        <button class="receipt-thumb" data-action="receipt-view" data-id="${p.id}" data-pdf="${p.receipt_type === 'application/pdf' ? '1' : ''}" aria-label="${t('view_receipt')}">
          ${p.receipt_type === 'application/pdf' ? '📄' : html`<img data-receipt="${p.id}" alt="">`}</button>
        <div class="grow" style="min-width:200px">
          <div class="between"><div class="bold">${p.student.full_name}</div>${paymentStatus(p.status)}</div>
          <div class="tiny muted">${[p.student.phone, p.student.telegram_username].filter(Boolean).join(' · ')}</div>
          <div class="small mt" style="margin-top:6px">${p.group ? html`${codeBadge(p.group.code)} <a href="#/class/${p.group.id}">${p.group.title}</a>` : html`<span class="faint">${t('class_deleted')}</span>`}
            ${p.group && p.status === 'pending' ? html` · <span class="${p.group.seats_left ? '' : 'bold'}" style="${p.group.seats_left ? '' : 'color:var(--danger)'}">${t('seats_left', { n: p.group.seats_left })}</span>` : ''}</div>
          <div class="row-wrap small" style="margin-top:4px"><b>${fmtPrice(p.amount)}</b>
            ${p.group && p.group.price !== p.amount ? html`<span class="badge badge-warning">${t('price_changed', { price: fmtPrice(p.group.price) })}</span>` : ''}
            <span class="tiny faint">${fmtDateTime(p.created_at)}</span></div>
          ${p.admin_comment ? html`<div class="tiny muted" style="margin-top:4px">💬 ${p.admin_comment}</div>` : ''}
          ${p.status === 'pending' ? html`<div class="row-wrap mt">
            <button class="btn btn-success btn-sm" data-action="pay-approve" data-id="${p.id}">${icon('check')} ${t('approve_enroll')}</button>
            <button class="btn btn-danger-soft btn-sm" data-action="pay-reject" data-id="${p.id}">${t('reject')}</button></div>` : ''}
        </div>
      </div>`)}</div>` : html`<div class="card">${empty('🧾', t('no_payments'))}</div>`}`);
  // Receipts are private: load them with the auth header and show as blob URLs.
  body.querySelectorAll('img[data-receipt]').forEach(async (img) => {
    try {
      const url = URL.createObjectURL(await api(`/api/admin/payments/${img.dataset.receipt}/receipt`, { blob: true }));
      receiptUrls.push(url);
      img.src = url;
    } catch { img.replaceWith('🧾'); }
  });
}

on('nav', (el) => go(el.dataset.to));
on('receipt-view', async (el) => {
  try {
    const blob = await api(`/api/admin/payments/${el.dataset.id}/receipt`, { blob: true });
    const url = URL.createObjectURL(blob);
    receiptUrls.push(url);
    if (el.dataset.pdf) { window.open(url, '_blank', 'noopener'); return; }
    openSheet({ title: t('receipt'), wide: true, body: html`<img src="${url}" alt="${t('receipt')}" style="margin:0 auto;max-height:75vh;border-radius:12px">` });
  } catch (err) { toastError(err); }
});
on('pay-approve', async (el) => {
  await busy(el, async () => {
    try {
      await api(`/api/admin/payments/${el.dataset.id}/review`, { method: 'POST', body: { status: 'approved' } });
      toast(t('payment_approved_toast'), 'success');
      reload();
    } catch (err) { toastError(err); }
  });
});
on('pay-reject', (el) => {
  sheetRef = openSheet({
    title: t('reject_payment'),
    body: html`<form class="stack" data-submit="pay-reject-save" data-id="${el.dataset.id}">
      <label class="field"><span>${t('reason_for_student')}</span><textarea class="textarea" name="comment" maxlength="500" placeholder="${t('reject_reason_placeholder')}"></textarea></label>
      <button class="btn btn-danger btn-block" type="submit">${t('reject')}</button></form>`,
  });
});
on('pay-reject-save', async (form) => {
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      await api(`/api/admin/payments/${form.dataset.id}/review`, { method: 'POST', body: { status: 'rejected', comment: form.comment.value } });
      sheetRef?.close();
      toast(t('payment_rejected_toast'), 'success');
      reload();
    } catch (err) { toastError(err); }
  });
});

// ---------- classes ----------
async function classes(body, _query, alive) {
  const [groups, tutors] = await Promise.all([api('/api/admin/groups'), api('/api/admin/tutors')]);
  if (!alive()) return;
  cache.groups = groups;
  cache.tutors = tutors.filter((x) => x.tutor_status === 'approved' && !x.is_blocked);
  mount(body, html`
    <div class="between" style="margin-bottom:16px"><span class="muted">${t('classes_total', { n: groups.length })}</span>
      <button class="btn btn-primary" data-action="group-new">${icon('plus')} ${t('create_class')}</button></div>
    ${groups.length ? html`<div class="grid grid-2">${groups.map((g) => {
      const s = subjectInfo(g);
      return html`<div class="card card-pad stack">
        <div class="row">${g.poster_url ? html`<img class="poster-thumb" src="${g.poster_url}" alt="">` : subjectIcon(s)}<div class="grow">${codeBadge(g.code)} <a class="bold" href="#/class/${g.id}">${g.title}</a>
          <div class="tiny muted">${s.label}${g.level ? ` · ${g.level}` : ''}</div></div>
          ${g.is_published ? html`<span class="badge badge-success">${t('published')}</span>` : html`<span class="badge">${t('hidden')}</span>`}</div>
        ${g.tutor ? html`<div class="row small">${avatar(g.tutor, 'avatar-sm')}<span class="grow truncate">${g.tutor.full_name}</span>${ratingBadge(g.tutor)}</div>`
          : html`<div class="notice notice-warning small"><span class="ico">⚠️</span><div>${t('no_teacher_assigned')}</div></div>`}
        <div class="row-wrap small muted"><b style="color:var(--text)">${fmtPrice(g.price)} / ${periodLabel(g.price_period)}</b>
          <span>· ${t('group_size', { n: g.enrolled, max: g.max_students })}</span>${g.schedule ? html`<span>· ${g.schedule}</span>` : ''}</div>
        <div class="tiny muted">${g.next_lesson_at ? `${t('next_lesson')}: ${fmtDateTime(g.next_lesson_at)}` : t('no_lesson_scheduled')}</div>
        <div class="row-wrap">
          <button class="btn btn-soft btn-sm" data-action="group-students" data-id="${g.id}">${icon('users')} ${t('students')}</button>
          <button class="btn btn-outline btn-sm" data-action="group-edit" data-id="${g.id}">${icon('edit')} ${t('edit')}</button>
          <button class="btn btn-ghost btn-sm" data-action="group-delete" data-id="${g.id}" aria-label="${t('delete')}">${icon('trash')}</button>
        </div></div>`;
    })}</div>` : html`<div class="card">${empty('🏫', t('no_classes_admin'), t('no_classes_admin_text'))}</div>`}`);
}

async function groupForm(group = null) {
  if (!cache.tutors) {
    try { cache.tutors = (await api('/api/admin/tutors')).filter((x) => x.tutor_status === 'approved' && !x.is_blocked); } catch (err) { return toastError(err); }
  }
  const g = group || { category: 'language', subject: 'en', price_period: 'month', max_students: 5, is_published: true };
  sheetRef = openSheet({
    title: group ? t('edit_class') : t('create_class'),
    wide: true,
    body: html`<form class="form-grid" data-submit="group-save" data-id="${group?.id || ''}">
      <label class="field full"><span>${t('class_title')}</span><input class="input" name="title" required minlength="2" maxlength="160" value="${g.title || ''}" placeholder="${t('class_title_placeholder')}"></label>
      <label class="field full"><span>${t('course_code')} <span class="faint">(${t('optional')})</span></span>
        <input class="input mono" name="code" maxlength="20" pattern="[A-Za-z0-9][A-Za-z0-9\-]{1,19}" style="text-transform:uppercase"
          value="${g.code || ''}" placeholder="${t('course_code_placeholder')}" autocomplete="off">
        <span class="hint">${group ? t('course_code_hint_edit') : t('course_code_hint')}</span></label>
      <div class="field full"><span>${t('poster')} <span class="faint">(${t('optional')})</span></span>
        <label class="file-drop poster-drop" data-poster-drop>
          <input type="file" name="poster" accept="image/jpeg,image/png,image/webp" data-change="poster-picked">
          ${g.poster_url ? html`<img src="${g.poster_url}" alt="" data-poster-preview>` : html`<span style="font-size:28px">🖼️</span>`}
          <span class="bold" data-poster-label>${g.poster_url ? t('change_poster') : t('upload_poster')}</span>
          <span class="tiny">${t('poster_hint', { mb: state.config.max_upload_mb || 5 })}</span>
        </label>
        ${g.poster_url ? html`<label class="check small"><input type="checkbox" name="remove_poster"> ${t('remove_poster')}</label>` : ''}
      </div>
      <div class="field full"><span>${t('category')}</span><div class="seg block" data-category>
        <button type="button" class="${g.category === 'language' ? 'active' : ''}" data-action="cat-pick" data-v="language">🗣️ ${t('cat_language')}</button>
        <button type="button" class="${g.category === 'other' ? 'active' : ''}" data-action="cat-pick" data-v="other">📘 ${t('cat_other')}</button></div>
        <input type="hidden" name="category" value="${g.category}"></div>
      <label class="field" data-lang-field ${g.category === 'language' ? '' : 'hidden'}><span>${t('language')}</span>
        <select class="select" name="subject_lang">${LANGUAGE_CODES.map((c) => html`<option value="${c}" ${g.subject === c ? 'selected' : ''}>${subjectName(c)}</option>`)}</select></label>
      <label class="field" data-other-field ${g.category === 'other' ? '' : 'hidden'}><span>${t('subject')}</span>
        <input class="input" name="subject_other" maxlength="80" list="subject-suggestions" value="${g.category === 'other' ? g.subject : ''}" placeholder="${t('subject_placeholder')}">
        <datalist id="subject-suggestions">${['Mathematics', 'Programming', 'Physics', 'Chemistry', 'Biology', 'History', 'Economics', 'Design'].map((x) => html`<option value="${x}">`)}</datalist></label>
      <label class="field"><span>${t('level')} <span class="faint">(${t('optional')})</span></span><input class="input" name="level" maxlength="40" value="${g.level || ''}" placeholder="A1, B2, Beginner…"></label>
      <label class="field"><span>${t('price')} (${t('currency')})</span><input class="input" name="price" type="number" min="0" step="1000" required value="${g.price ?? ''}"></label>
      <label class="field"><span>${t('price_period')}</span><select class="select" name="price_period">
        ${['month', 'course', 'lesson'].map((p) => html`<option value="${p}" ${g.price_period === p ? 'selected' : ''}>${t(`per_${p}`)}</option>`)}</select></label>
      <label class="field"><span>${t('schedule')}</span><input class="input" name="schedule" maxlength="160" value="${g.schedule || ''}" placeholder="${t('schedule_placeholder')}"></label>
      <label class="field"><span>${t('max_students')}</span><input class="input" name="max_students" type="number" min="1" max="100" required value="${g.max_students}"></label>
      <label class="field full"><span>${t('teacher')}</span><select class="select" name="tutor_id">
        <option value="">— ${t('not_assigned')} —</option>
        ${cache.tutors.map((x) => html`<option value="${x.id}" ${g.tutor?.id === x.id ? 'selected' : ''}>${x.full_name}${x.subjects ? ` (${x.subjects})` : ''}</option>`)}</select>
        ${cache.tutors.length ? '' : html`<span class="hint">${t('no_approved_teachers')}</span>`}</label>
      <label class="field full"><span>${t('description')}</span><textarea class="textarea" name="description" maxlength="4000" placeholder="${t('description_placeholder')}">${g.description || ''}</textarea></label>
      <label class="check full"><input type="checkbox" name="is_published" ${g.is_published ? 'checked' : ''}> ${t('publish_in_catalog')}</label>
      <button class="btn btn-primary btn-lg full" type="submit">${group ? t('save') : t('create_class')}</button>
    </form>`,
  });
}

on('group-new', () => groupForm());
on('group-edit', (el) => groupForm(cache.groups.find((g) => g.id === Number(el.dataset.id))));
on('cat-pick', (el) => {
  const form = el.closest('form');
  el.parentElement.querySelectorAll('button').forEach((b) => b.classList.toggle('active', b === el));
  form.category.value = el.dataset.v;
  form.querySelector('[data-lang-field]').hidden = el.dataset.v !== 'language';
  form.querySelector('[data-other-field]').hidden = el.dataset.v !== 'other';
});
on('group-save', async (form) => {
  const d = formData(form);
  const subject = d.category === 'language' ? d.subject_lang : (d.subject_other || '').trim();
  if (!subject) return toast(t('subject_required'), 'warning');
  const body = {
    code: (d.code || '').trim().toUpperCase(),
    title: d.title, category: d.category, subject, level: d.level, description: d.description,
    price: Number(d.price), price_period: d.price_period, schedule: d.schedule, max_students: Number(d.max_students),
    tutor_id: d.tutor_id ? Number(d.tutor_id) : null, is_published: form.is_published.checked,
  };
  const id = form.dataset.id;
  const posterFile = form.poster.files?.[0];
  const maxMb = state.config.max_upload_mb || 5;
  if (posterFile && !/^image\/(jpeg|png|webp)$/.test(posterFile.type)) return toast(t('poster_type_hint'), 'warning');
  if (posterFile && posterFile.size > maxMb * 1024 * 1024) return toast(t('file_too_large', { mb: maxMb }), 'warning');
  await busy(form.querySelector('[type=submit]'), async () => {
    let saved;
    try {
      saved = await api(id ? `/api/admin/groups/${id}` : '/api/admin/groups', { method: id ? 'PUT' : 'POST', body });
    } catch (err) { toastError(err); return; }
    try {
      // The class is saved first; the poster is a separate upload so a bad image never loses the form.
      if (posterFile) {
        const fd = new FormData();
        fd.append('poster', posterFile);
        await api(`/api/admin/groups/${saved.id}/poster`, { method: 'POST', form: fd });
      } else if (form.remove_poster?.checked) {
        await api(`/api/admin/groups/${saved.id}/poster`, { method: 'DELETE' });
      }
      toast(id ? t('saved') : t('class_created'), 'success');
    } catch (err) {
      toast(`${t('class_saved_poster_failed')} ${err.message}`, 'error');
    }
    sheetRef?.close();
    go('/admin/classes');
  });
});
on('poster-picked', (input) => {
  const file = input.files?.[0];
  const drop = input.closest('[data-poster-drop]');
  if (!file || !drop) return;
  drop.querySelectorAll('img, span[style]').forEach((n) => n.remove());
  const img = document.createElement('img');
  img.src = URL.createObjectURL(file);
  img.alt = '';
  drop.insertBefore(img, drop.querySelector('[data-poster-label]'));
  drop.querySelector('[data-poster-label]').textContent = `✓ ${file.name}`;
  const remove = input.form.remove_poster;
  if (remove) remove.checked = false;
});
on('group-delete', async (el) => {
  const g = cache.groups.find((x) => x.id === Number(el.dataset.id));
  if (!(await confirmSheet(t('delete_class_confirm', { title: g.title, n: g.enrolled }), { okText: t('delete'), danger: true }))) return;
  try {
    await api(`/api/admin/groups/${g.id}`, { method: 'DELETE' });
    toast(t('deleted'), 'success');
    reload();
  } catch (err) { toastError(err); }
});
on('group-students', async (el) => {
  const g = cache.groups.find((x) => x.id === Number(el.dataset.id));
  let students = [];
  try { students = await api('/api/admin/users', { query: { role: 'student' } }); } catch (err) { return toastError(err); }
  const enrolledIds = new Set(g.students.map((s) => s.id));
  const available = students.filter((s) => !enrolledIds.has(s.id) && !s.is_blocked);
  sheetRef = openSheet({
    title: `${g.title} · ${g.enrolled}/${g.max_students}`,
    wide: true,
    body: html`
      ${g.students.length ? html`<div class="list">${g.students.map((s) => html`
        <div class="list-item">${avatar(s, 'avatar-sm')}<div class="grow"><div class="bold small">${s.full_name}</div>
          <div class="tiny muted">${s.telegram_username || ''} · ${t('joined')} ${fmtDate(s.joined_at)}</div></div>
          ${strikesDots(s.strikes)}
          <button class="btn btn-ghost btn-sm" data-action="student-remove" data-group="${g.id}" data-student="${s.id}">${t('remove')}</button></div>`)}</div>`
        : html`<p class="muted">${t('no_students_yet')}</p>`}
      <div class="divider"></div>
      <form class="row" data-submit="student-add" data-group="${g.id}" style="flex-wrap:wrap">
        <select class="select grow" name="student_id" required style="min-width:200px">
          <option value="">${t('choose_student')}</option>
          ${available.map((s) => html`<option value="${s.id}">${s.full_name}${s.phone ? ` · ${s.phone}` : ''}</option>`)}</select>
        <button class="btn btn-primary" type="submit" ${g.enrolled >= g.max_students ? 'disabled' : ''}>${icon('plus')} ${t('add_student')}</button>
      </form>
      <p class="tiny faint mt">${t('add_student_hint')}</p>`,
  });
});
on('student-add', async (form) => {
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      await api(`/api/admin/groups/${form.dataset.group}/students`, { method: 'POST', body: { student_id: Number(form.student_id.value) } });
      sheetRef?.close();
      toast(t('student_added'), 'success');
      go('/admin/classes');
    } catch (err) { toastError(err); }
  });
});
on('student-remove', async (el) => {
  if (!(await confirmSheet(t('remove_student_confirm'), { okText: t('remove'), danger: true }))) return;
  try {
    await api(`/api/admin/groups/${el.dataset.group}/students/${el.dataset.student}`, { method: 'DELETE' });
    sheetRef?.close();
    toast(t('student_removed'), 'success');
    go('/admin/classes');
  } catch (err) { toastError(err); }
});

// ---------- teachers ----------
async function teachers(body, _query, alive) {
  const list = await api('/api/admin/tutors');
  if (!alive()) return;
  mount(body, list.length ? html`<div class="grid grid-2">${list.map((x) => html`
    <div class="card card-pad stack">
      <div class="row">${avatar(x)}<div class="grow"><div class="bold">${x.full_name}</div>
        <div class="tiny muted">${[x.phone, x.telegram_username].filter(Boolean).join(' · ')}</div></div>
        <span class="badge badge-${x.tutor_status === 'approved' ? 'success' : x.tutor_status === 'rejected' ? 'danger' : 'warning'}">${t(`status_${x.tutor_status || 'pending'}`)}</span></div>
      ${x.subjects ? html`<div class="small"><b>${t('subjects')}:</b> ${x.subjects}</div>` : ''}
      ${x.bio ? html`<p class="small muted prose">${x.bio}</p>` : ''}
      <div><div class="label">${t('certificates')} (${x.documents.length})</div>${documentList(x.documents, x.id)}</div>
      ${x.review_note ? html`<div class="tiny muted">💬 ${t('rejection_reason')}: ${x.review_note}</div>` : ''}
      <div class="row-wrap small">${ratingBadge(x)}<span class="muted">· ${t('classes_count', { n: x.groups_count })}</span><span class="tiny faint">· ${fmtDate(x.created_at)}</span></div>
      <div class="row-wrap">
        ${x.tutor_status !== 'approved' ? html`<button class="btn btn-success btn-sm" data-action="tutor-decide" data-id="${x.id}" data-v="approved"
          ${x.documents.length ? '' : html`disabled title="${t('approve_needs_docs')}"`}>${icon('check')} ${t('approve')}</button>` : ''}
        ${x.tutor_status !== 'rejected' ? html`<button class="btn btn-danger-soft btn-sm" data-action="tutor-decide" data-id="${x.id}" data-v="rejected">${x.tutor_status === 'approved' ? t('revoke') : t('reject')}</button>` : ''}
        ${x.tutor_status === 'approved' ? html`<a class="btn btn-ghost btn-sm" href="#/teacher/${x.id}">${t('view_profile')}</a>` : ''}
      </div>
    </div>`)}</div>` : html`<div class="card">${empty('🧑‍🏫', t('no_teachers'), t('no_teachers_text'))}</div>`);
}
on('tutor-decide', async (el) => {
  if (el.dataset.v === 'rejected') {
    sheetRef = openSheet({
      title: t('reject_teacher'),
      body: html`<form class="stack" data-submit="tutor-reject" data-id="${el.dataset.id}">
        <p class="small muted">${t('reject_teacher_confirm')}</p>
        <label class="field"><span>${t('reason_for_teacher')}</span>
          <textarea class="textarea" name="comment" maxlength="500" placeholder="${t('reject_teacher_placeholder')}"></textarea></label>
        <button class="btn btn-danger btn-block" type="submit">${t('reject')}</button></form>`,
    });
    return;
  }
  try {
    await api(`/api/admin/tutors/${el.dataset.id}/decision`, { method: 'POST', body: { status: 'approved' } });
    toast(t('saved'), 'success');
    reload();
  } catch (err) { toastError(err); }
});
on('tutor-reject', async (form) => {
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      await api(`/api/admin/tutors/${form.dataset.id}/decision`, { method: 'POST', body: { status: 'rejected', comment: form.comment.value } });
      sheetRef?.close();
      toast(t('saved'), 'success');
      reload();
    } catch (err) { toastError(err); }
  });
});
on('doc-view', async (el) => {
  try {
    const blob = await api(`/api/admin/tutors/${el.dataset.tutor}/documents/${el.dataset.id}`, { blob: true });
    const url = URL.createObjectURL(blob);
    receiptUrls.push(url);
    if (el.dataset.pdf) { window.open(url, '_blank', 'noopener'); return; }
    openSheet({ title: t('certificates'), wide: true, body: html`<img src="${url}" alt="" style="margin:0 auto;max-height:75vh;border-radius:12px">` });
  } catch (err) { toastError(err); }
});

// ---------- users ----------
async function users(body, query, alive) {
  const role = ['student', 'tutor', 'admin'].includes(query.role) ? query.role : 'all';
  const list = await api('/api/admin/users', { query: { role, q: query.q || '' } });
  if (!alive()) return;
  mount(body, html`
    <form class="row-wrap" data-submit="users-search" style="margin-bottom:16px">
      <div class="search grow" style="min-width:220px">${icon('search')}<input class="input" name="q" type="search" value="${query.q || ''}" placeholder="${t('search_users')}" style="min-height:42px"></div>
      <div class="seg">${['all', 'student', 'tutor', 'admin'].map((r) =>
        html`<button type="button" class="${r === role ? 'active' : ''}" data-action="nav" data-to="/admin/users?role=${r}">${t(r === 'all' ? 'all' : `role_${r}`)}</button>`)}</div>
      <input type="hidden" name="role" value="${role}">
    </form>
    ${list.length ? html`<div class="card card-pad list">${list.map((u) => html`
      <div class="list-item">${avatar(u)}<div class="grow"><div class="bold small">${u.full_name}
          ${u.is_blocked ? html`<span class="badge badge-danger">${t('blocked')}</span>` : ''}</div>
        <div class="tiny muted">${t(`role_${u.role}`)}${u.phone ? ` · ${u.phone}` : ''}${u.telegram_username ? ` · ${u.telegram_username}` : ''} · ${fmtDate(u.created_at)}</div></div>
        ${u.role !== 'admin' ? html`<button class="btn ${u.is_blocked ? 'btn-outline' : 'btn-danger-soft'} btn-sm" data-action="user-block" data-id="${u.id}" data-v="${u.is_blocked ? '0' : '1'}">
          ${u.is_blocked ? t('unblock') : t('block')}</button>` : ''}
      </div>`)}</div>` : html`<div class="card">${empty('👤', t('no_users_found'))}</div>`}`);
}
on('users-search', (form) => go(`/admin/users?role=${form.role.value}&q=${encodeURIComponent(form.q.value.trim())}`));
on('user-block', async (el) => {
  const block = el.dataset.v === '1';
  if (block && !(await confirmSheet(t('block_confirm'), { okText: t('block'), danger: true }))) return;
  try {
    await api(`/api/admin/users/${el.dataset.id}/block`, { method: 'POST', body: { is_blocked: block } });
    toast(t('saved'), 'success');
    reload();
  } catch (err) { toastError(err); }
});

// ---------- discipline (3-strike rule) ----------
async function discipline(body, _query, alive) {
  const list = await api('/api/admin/violations');
  if (!alive()) return;
  mount(body, html`
    <div class="notice notice-info small" style="margin-bottom:16px"><span class="ico">⚖️</span><div>${t('strike_rule_text')}</div></div>
    ${list.length ? html`<div class="card card-pad list">${list.map((v) => html`
      <div class="list-item" style="flex-wrap:wrap">${avatar(v.student)}
        <div class="grow" style="min-width:180px"><div class="bold small">${v.student.full_name}</div>
          <div class="tiny muted">${v.group.title}${v.tutor ? ` · ${v.tutor.full_name}` : ''}</div></div>
        ${strikesDots(v.strikes)}
        ${v.access_revoked ? html`<span class="badge badge-danger">${t('access_closed')}</span>` : html`<span class="badge badge-warning">${t('at_risk')}</span>`}
        <div class="row-wrap">
          <button class="btn btn-outline btn-sm" data-action="admin-strike" data-group="${v.group.id}" data-student="${v.student.id}" data-op="remove">−1</button>
          <button class="btn btn-outline btn-sm" data-action="admin-strike" data-group="${v.group.id}" data-student="${v.student.id}" data-op="reset">${t('reset_strikes')}</button>
          <button class="btn btn-danger-soft btn-sm" data-action="admin-expel" data-group="${v.group.id}" data-student="${v.student.id}">${t('remove_from_class')}</button>
        </div>
      </div>`)}</div>` : html`<div class="card">${empty('✅', t('no_violations'))}</div>`}`);
}
on('admin-strike', async (el) => {
  try {
    await api('/api/admin/strikes', { method: 'POST', body: { group_id: Number(el.dataset.group), student_id: Number(el.dataset.student), action: el.dataset.op } });
    toast(t('saved'), 'success');
    reload();
  } catch (err) { toastError(err); }
});
on('admin-expel', async (el) => {
  if (!(await confirmSheet(t('remove_student_confirm'), { okText: t('remove'), danger: true }))) return;
  try {
    await api(`/api/admin/groups/${el.dataset.group}/students/${el.dataset.student}`, { method: 'DELETE' });
    toast(t('student_removed'), 'success');
    reload();
  } catch (err) { toastError(err); }
});

const PAGES = { overview, payments, classes, teachers, users, discipline };
