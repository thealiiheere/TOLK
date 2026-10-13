// Reusable rendering blocks shared by several pages.
import {
  avatar, fmtDate, fmtNumber, fmtPrice, fmtRelative, html, icon, meetingPlatform, mount, on, periodLabel, ratingBadge,
  codeBadge, stars, state, subjectIcon, subjectInfo,
} from '../core.js';
import { t } from '../i18n.js';

export function seatsInfo(g) {
  const tone = g.seats_left === 0 ? 'danger' : g.seats_left <= 1 ? 'warning' : 'success';
  const label = g.seats_left === 0 ? t('class_full') : t('seats_left', { n: g.seats_left });
  return html`<span class="badge badge-${tone}">${label}</span>`;
}

export function classCard(g) {
  const s = subjectInfo(g);
  return html`
    <a class="card class-card" href="#/class/${g.id}">
      <div class="cover" style="--h:${s.hue}">
        ${subjectIcon(s, 'lg')}<span class="subject">${s.label}</span>
        ${g.level ? html`<span class="tag badge">${g.level}</span>` : ''}
      </div>
      <div class="body">
        <div>${codeBadge(g.code)}<h3 style="margin-top:6px">${g.title}</h3></div>
        ${g.tutor ? html`<div class="row">${avatar(g.tutor, 'avatar-sm')}
          <div class="grow"><div class="small bold truncate">${g.tutor.full_name}</div>${ratingBadge(g.tutor)}</div></div>` : ''}
        <div class="meta">
          ${g.schedule ? html`<span>${icon('calendar')}${g.schedule}</span>` : ''}
          <span>${icon('users')}${t('group_size', { n: g.enrolled, max: g.max_students })}</span>
        </div>
        <div class="foot">
          <div class="price">${fmtPrice(g.price)} <small>/ ${periodLabel(g.price_period)}</small></div>
          ${seatsInfo(g)}
        </div>
      </div>
    </a>`;
}

export function classGrid(groups) {
  return html`<div class="grid grid-3">${groups.map(classCard)}</div>`;
}

export function ratingSummary(avg, count, breakdown) {
  const total = Object.values(breakdown || {}).reduce((a, b) => a + b, 0) || 1;
  return html`
    <div class="row" style="align-items:flex-start;gap:20px;flex-wrap:wrap">
      <div class="center" style="min-width:110px">
        <div style="font-size:40px;font-weight:800;line-height:1">${count ? avg.toFixed(1) : '—'}</div>
        <div class="mt">${stars(avg || 0)}</div>
        <div class="tiny muted mt">${t('ratings_count', { n: count || 0 })}</div>
      </div>
      <div class="bars grow" style="min-width:180px">
        ${[5, 4, 3, 2, 1].map((s) => {
          const n = (breakdown || {})[s] || 0;
          return html`<div class="bar-row"><span>${s} ★</span><span class="bar"><i style="width:${(n / total) * 100}%"></i></span><span>${n}</span></div>`;
        })}
      </div>
    </div>`;
}

export function reviewList(reviews) {
  if (!reviews?.length) return html`<p class="muted small">${t('no_reviews')}</p>`;
  return html`<div>${reviews.map((r) => html`
    <div class="review">
      <div class="between"><div class="row"><span class="bold small">${r.student_name}</span>${stars(r.stars)}</div>
        <span class="tiny faint">${fmtDate(r.created_at)}</span></div>
      ${r.comment ? html`<p class="small mt" style="margin-top:6px">${r.comment}</p>` : ''}
      ${r.group_title ? html`<div class="tiny faint" style="margin-top:4px">${r.group_title}</div>` : ''}
    </div>`)}</div>`;
}

/** A lesson row. `actions` is rendered on the right (join button, edit...). */
export function lessonRow(lesson, { title, actions = '', sub = '' } = {}) {
  const d = new Date(lesson.starts_at);
  const time = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit', hour12: false }).format(d);
  return html`
    <div class="lesson ${lesson.is_live ? 'live' : ''}">
      <div class="datebox"><div class="d">${d.getDate()}</div><div class="m">${fmtDate(lesson.starts_at, { month: 'short' })}</div></div>
      <div class="grow">
        <div class="bold truncate">${title || lesson.topic || t('lesson')}</div>
        ${title && lesson.topic ? html`<div class="small muted truncate">${lesson.topic}</div>` : ''}
        <div class="row-wrap tiny muted" style="margin-top:4px">
          ${lesson.is_live ? html`<span class="badge badge-success"><span class="live-dot"></span> ${t('live_now')}</span>`
            : html`<span>${icon('clock')}</span><span>${fmtDate(lesson.starts_at, { weekday: 'short' })}, ${time} · ${fmtRelative(lesson.starts_at)}</span>`}
          ${lesson.meet_link ? html`<span class="badge">${icon('video')} ${meetingPlatform(lesson.meet_link)}</span>` : ''}
        </div>
        ${sub}
      </div>
      ${actions ? html`<div class="lesson-actions">${actions}</div>` : ''}
    </div>`;
}

export function paymentStatus(status) {
  const tone = { pending: 'warning', approved: 'success', rejected: 'danger' }[status] || '';
  return html`<span class="badge badge-${tone}">${t(`payment_${status}`)}</span>`;
}

// ---------- teacher certificates ----------
export const MAX_CERTS_PER_UPLOAD = 5;
const CERT_ACCEPT = 'image/jpeg,image/png,image/webp,application/pdf';

/** File picker for certificates / diplomas (multiple files). Lives inside a <form>; field name "certificates". */
export function certificatesField() {
  return html`<div class="field"><span>${t('certificates')}</span>
    <label class="file-drop">
      <input type="file" name="certificates" multiple accept="${CERT_ACCEPT}" data-change="certs-picked">
      <span style="font-size:28px">🎓</span>
      <span class="bold">${t('upload_certificates')}</span>
      <span class="tiny">${t('certificates_hint', { n: MAX_CERTS_PER_UPLOAD, mb: state.config.max_upload_mb || 5 })}</span>
      <span class="small stack" style="gap:2px" data-cert-list></span>
    </label></div>`;
}

/** Client-side check before uploading; returns an error message or ''. The server validates again. */
export function certificatesError(files) {
  const mb = state.config.max_upload_mb || 5;
  if (!files?.length) return t('certificates_required_ui');
  if (files.length > MAX_CERTS_PER_UPLOAD) return t('too_many_certs', { n: MAX_CERTS_PER_UPLOAD });
  if ([...files].some((f) => f.size > mb * 1024 * 1024)) return t('file_too_large', { mb });
  return '';
}

on('certs-picked', (input) => {
  const list = input.closest('.file-drop').querySelector('[data-cert-list]');
  mount(list, [...input.files].map((f) => html`<span>✓ ${f.name}</span>`));
});

/** List of uploaded documents. With `tutorId` (admin view) each item gets a "View" button. */
export function documentList(docs, tutorId = null) {
  if (!docs?.length) return html`<p class="small" style="color:var(--danger)">${t('no_documents')}</p>`;
  return html`<div class="list">${docs.map((d) => html`
    <div class="list-item" style="padding:8px 0">
      <span style="font-size:20px">${d.content_type === 'application/pdf' ? '📄' : '🖼️'}</span>
      <div class="grow"><div class="small bold truncate">${d.name}</div><div class="tiny faint">${fmtDate(d.created_at)}</div></div>
      ${tutorId ? html`<button class="btn btn-soft btn-sm" data-action="doc-view" data-tutor="${tutorId}" data-id="${d.id}"
        data-pdf="${d.content_type === 'application/pdf' ? '1' : ''}">${t('view')}</button>` : ''}
    </div>`)}</div>`;
}

export { fmtNumber };
