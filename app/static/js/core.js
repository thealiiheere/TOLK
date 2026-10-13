// Core runtime shared by all pages: state, safe HTML templating, API client, router, UI primitives, formatting.
import { t, getLang, subjectName, LANG_LOCALES } from './i18n.js';

// ---------- storage (can throw in private mode / embedded webviews) ----------
export const storage = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) {
    try { value == null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch { /* ignore */ }
  },
};

export const state = {
  user: null,
  token: storage.get('tolk_token'),
  config: {},
  tg: window.Telegram?.WebApp || null,
};

export const inTelegram = () => Boolean(state.tg && state.tg.initData);

export function setToken(token) {
  state.token = token;
  storage.set('tolk_token', token);
}

// ---------- safe HTML templating: every interpolated value is escaped unless wrapped in raw() ----------
class Safe { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Safe(String(s ?? ''));
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ESC[c]);
function piece(v) {
  if (v == null || v === false) return '';
  if (v instanceof Safe) return v.s;
  if (Array.isArray(v)) return v.map(piece).join('');
  return esc(v);
}
export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((v, i) => { out += piece(v) + strings[i + 1]; });
  return new Safe(out);
}
export function mount(el, content) { el.innerHTML = piece(content); }

// ---------- API ----------
export class ApiError extends Error {
  constructor(message, status, code) { super(message); this.status = status; this.code = code; }
}

export async function api(path, { method = 'GET', body, form, query, blob = false } = {}) {
  const headers = { 'X-Lang': getLang() };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let url = path;
  if (query) {
    const q = new URLSearchParams();
    Object.entries(query).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '' && v !== false) q.set(k, v); });
    if (q.toString()) url += `?${q}`;
  }
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }

  let res;
  try {
    res = await fetch(url, { method, headers, body: payload });
  } catch {
    throw new ApiError(t('err_network'), 0, 'network');
  }
  if (res.ok && blob) return res.blob();
  const data = (res.headers.get('content-type') || '').includes('application/json') ? await res.json().catch(() => null) : null;
  if (!res.ok) {
    if (res.status === 401 && state.token) {
      setToken(null);
      state.user = null;
      document.dispatchEvent(new CustomEvent('tolk:signed-out'));
    }
    throw new ApiError(data?.detail || t('err_generic'), res.status, data?.code);
  }
  return data;
}

// ---------- haptics ----------
export function haptic(kind = 'light') {
  const h = state.tg?.HapticFeedback;
  if (!h) return;
  try {
    if (['success', 'error', 'warning'].includes(kind)) h.notificationOccurred(kind);
    else if (kind === 'select') h.selectionChanged();
    else h.impactOccurred(kind);
  } catch { /* old clients */ }
}

// ---------- toasts ----------
export function toast(message, type = 'info') {
  const box = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  box.appendChild(el);
  if (type === 'success' || type === 'error') haptic(type);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; }, 3800);
  setTimeout(() => el.remove(), 4200);
}
export const toastError = (err) => toast(err?.message || t('err_generic'), 'error');

// ---------- event delegation: data-action (click), data-submit (form), data-change / data-input ----------
const handlers = {};
export function on(name, fn) { handlers[name] = fn; }
document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (!el || el.disabled) return;
  const fn = handlers[el.dataset.action];
  if (fn) { e.preventDefault(); fn(el, e); }
});
document.addEventListener('submit', (e) => {
  const form = e.target.closest('form[data-submit]');
  if (!form) return;
  e.preventDefault();
  handlers[form.dataset.submit]?.(form, e);
});
for (const type of ['change', 'input']) {
  document.addEventListener(type, (e) => {
    const el = e.target.closest(`[data-${type}]`);
    if (el) handlers[el.dataset[type]]?.(el, e);
  });
}

export async function busy(btn, fn) {
  if (!btn) return fn();
  const original = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>';
  try { return await fn(); } finally { btn.disabled = false; btn.innerHTML = original; }
}

export function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

// ---------- sheets (bottom sheet on mobile, dialog on desktop) ----------
export function openSheet({ title, body, foot = '', wide = false, onClose } = {}) {
  const overlay = document.createElement('div');
  overlay.className = 'overlay';
  overlay.innerHTML = String(html`
    <div class="sheet ${wide ? 'wide' : ''}" role="dialog" aria-modal="true" aria-label="${title}">
      <div class="sheet-head"><h3>${title}</h3>
        <button class="btn btn-ghost btn-icon" data-close aria-label="${t('close')}">${icon('x')}</button></div>
      <div class="sheet-body">${body}</div>
      ${foot ? html`<div class="sheet-foot">${foot}</div>` : ''}
    </div>`);
  const close = () => {
    overlay.remove();
    document.removeEventListener('keydown', onKey);
    if (!document.querySelector('.overlay')) document.body.style.overflow = '';
    onClose?.();
  };
  const onKey = (e) => { if (e.key === 'Escape') close(); };
  overlay.addEventListener('click', (e) => { if (e.target === overlay || e.target.closest('[data-close]')) close(); });
  document.addEventListener('keydown', onKey);
  document.body.appendChild(overlay);
  document.body.style.overflow = 'hidden';
  return { el: overlay.querySelector('.sheet'), close };
}

export function confirmSheet(message, { okText = t('confirm'), danger = false } = {}) {
  return new Promise((resolve) => {
    let result = false;
    const sheet = openSheet({
      title: t('are_you_sure'),
      body: html`<p>${message}</p>`,
      foot: html`<button class="btn btn-outline" data-close>${t('cancel')}</button>
        <button class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-ok>${okText}</button>`,
      onClose: () => resolve(result),
    });
    sheet.el.querySelector('[data-ok]').addEventListener('click', () => { result = true; sheet.close(); });
  });
}

// ---------- router (hash based: #/path?query) ----------
const routes = [];
let renderSeq = 0;
export function route(pattern, handler, opts = {}) {
  const keys = [];
  const re = new RegExp(`^${pattern.replace(/:(\w+)/g, (_, k) => { keys.push(k); return '([^/]+)'; })}$`);
  routes.push({ re, keys, handler, ...opts });
}
export function currentRoute() {
  const hash = location.hash.replace(/^#/, '') || '/';
  const [path, qs = ''] = hash.split('?');
  return { path: path || '/', query: Object.fromEntries(new URLSearchParams(qs)) };
}
export function go(path) {
  if (location.hash === `#${path}`) window.dispatchEvent(new HashChangeEvent('hashchange'));
  else location.hash = path;
}
export function findRoute(path) {
  for (const r of routes) {
    const m = path.match(r.re);
    if (m) return { ...r, params: Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])])) };
  }
  return null;
}
/** Each render gets an `alive()` check so a slow, outdated request never overwrites a newer page. */
export function nextRender() {
  const id = ++renderSeq;
  return () => id === renderSeq;
}

// ---------- formatting ----------
const locale = () => LANG_LOCALES[getLang()] || 'en-GB';
export function fmtNumber(n) {
  return new Intl.NumberFormat('ru-RU').format(n || 0).replace(/,/g, ' ');
}
export function fmtPrice(n) { return `${fmtNumber(n)} ${t('currency')}`; }
export function periodLabel(p) { return t(`per_${p}`); }
export function fmtDate(iso, opts = { day: 'numeric', month: 'short', year: 'numeric' }) {
  if (!iso) return '';
  try { return new Intl.DateTimeFormat(locale(), opts).format(new Date(iso)); } catch { return new Date(iso).toLocaleDateString(); }
}
export function fmtTime(iso) { return fmtDate(iso, { hour: '2-digit', minute: '2-digit', hour12: false }); }
export function fmtDateTime(iso) {
  return fmtDate(iso, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
}
export function fmtRelative(iso) {
  const diff = (new Date(iso) - Date.now()) / 1000;
  const abs = Math.abs(diff);
  const [value, unit] = abs < 3600 ? [Math.round(diff / 60), 'minute'] : abs < 86400 ? [Math.round(diff / 3600), 'hour'] : [Math.round(diff / 86400), 'day'];
  try { return new Intl.RelativeTimeFormat(locale(), { numeric: 'auto' }).format(value, unit); } catch { return fmtDateTime(iso); }
}
/** Value for <input type="datetime-local"> in the user's local time. */
export function toLocalInput(date) {
  const d = new Date(date);
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function hue(str) {
  let h = 0;
  for (const ch of String(str)) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

export function avatar(user, size = '') {
  if (!user) return '';
  const initials = (user.full_name || '?').split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
  return html`<span class="avatar ${size}" style="--h:${hue(user.full_name || '')}">${
    user.photo_url ? html`<img src="${user.photo_url}" alt="" loading="lazy" referrerpolicy="no-referrer">` : initials}</span>`;
}

export function stars(value) {
  return html`<span class="stars" style="--v:${Number(value) || 0}" aria-label="${(Number(value) || 0).toFixed(1)} / 5"></span>`;
}

export function ratingBadge(tutor) {
  if (!tutor || !tutor.ratings_count) return html`<span class="badge badge-accent">${t('new_teacher')}</span>`;
  return html`<span class="rating">${stars(tutor.rating)} ${tutor.rating.toFixed(1)} <span class="n">(${tutor.ratings_count})</span></span>`;
}

const OTHER_EMOJI = [
  [/math|матем|matem|algebra|geometr/i, '📐'], [/program|python|java|code|it\b|dastur|програм/i, '💻'],
  [/physic|физик|fizik/i, '⚛️'], [/chem|хим|kimyo/i, '🧪'], [/bio/i, '🧬'], [/hist|истор|tarix/i, '🏛️'],
  [/music|музык|musiqa/i, '🎵'], [/art|draw|рис|rasm/i, '🎨'], [/econ|эконом|iqtisod|business|бизнес/i, '📈'],
  [/design|дизайн/i, '✏️'],
];
export function subjectInfo(group) {
  if (group.category === 'language') {
    // Language code instead of a flag emoji: flags don't render on Windows (incl. Telegram Desktop).
    return { label: subjectName(group.subject), code: group.subject.toUpperCase(), hue: hue(group.subject) };
  }
  const found = OTHER_EMOJI.find(([re]) => re.test(group.subject));
  return { label: group.subject, emoji: found ? found[1] : '📘', hue: hue(group.subject.toLowerCase()) };
}

/** Icon for a class: a language-code tile for languages, an emoji for other subjects. */
export function subjectIcon(info, size = 'md') {
  return info.code
    ? html`<span class="code-mark ${size}">${info.code}</span>`
    : html`<span class="emoji-mark ${size}">${info.emoji}</span>`;
}

/** Course code chip, e.g. "EN-101". */
export function codeBadge(code) {
  return code ? html`<span class="code-badge" title="${t('course_code')}">${code}</span>` : '';
}

export function strikesDots(n, max = 3) {
  return html`<span class="strikes ${n >= max ? 'full' : ''}" title="${n}/${max}">${
    Array.from({ length: max }, (_, i) => html`<i class="${i < n ? 'on' : ''}"></i>`)}</span>`;
}

export function meetingPlatform(link) {
  if (!link) return '';
  if (/zoom\.us/i.test(link)) return 'Zoom';
  if (/meet\.google\.com/i.test(link)) return 'Google Meet';
  if (/teams\./i.test(link)) return 'Microsoft Teams';
  return t('online_meeting');
}

export function openLink(url) {
  // Inside Telegram, external links must go through openLink so they open outside the webview.
  if (state.tg?.openLink && inTelegram()) state.tg.openLink(url);
  else window.open(url, '_blank', 'noopener');
}

export const loading = () => html`<div class="loading"><span class="spinner"></span></div>`;
export const empty = (emoji, title, text = '', action = '') =>
  html`<div class="empty"><div class="emoji">${emoji}</div><h3>${title}</h3>${text ? html`<p>${text}</p>` : ''}${
    action ? html`<div class="mt">${action}</div>` : ''}</div>`;
export const errorBox = (err) => empty('⚠️', t('err_generic'), err?.message || '');

// ---------- icons (inline SVG, stroke = currentColor) ----------
const ICONS = {
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m15.5 8.5-2 5-5 2 2-5z"/>',
  book: '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19V5"/><path d="M9 7h6"/>',
  board: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>',
  login: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5M15 12H3"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c1-3.5 3.5-5 6.5-5s5.5 1.5 6.5 5"/><path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 15c2 .7 3 2.3 3.5 5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  filter: '<path d="M4 5h16M7 12h10M10 19h4"/>',
  video: '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  check: '<path d="m5 12 5 5 9-10"/>',
  level: '<path d="M4 20V14M10 20V9M16 20V4"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  star: '<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z"/>',
};
export function icon(name) {
  return raw(`<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ''}</svg>`);
}

// ---------- session ----------
export function setUser(user) {
  state.user = user;
  document.dispatchEvent(new CustomEvent('tolk:user'));
}
export function homeFor(user) {
  if (!user) return '/';
  if (!user.onboarded) return '/welcome';
  return { student: '/my', tutor: '/teach', admin: '/admin' }[user.role] || '/';
}
/** Store a {token, user} login response and continue to `next` (or the user's home page). */
export function completeLogin(data, next) {
  setToken(data.token);
  if (data.user.lang !== getLang()) {
    // keep the language the person is using right now and remember it on their account
    data.user.lang = getLang();
    api('/api/auth/me', { method: 'PATCH', body: { lang: getLang() } }).catch(() => {});
  }
  setUser(data.user);
  const target = data.user.onboarded ? (next && next.startsWith('/') ? next : homeFor(data.user)) : '/welcome';
  go(target);
}
