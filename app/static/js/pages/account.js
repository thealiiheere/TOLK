// Sign in, first-time sign-up (student or teacher) and profile settings.
import {
  api, avatar, busy, completeLogin, errorBox, formData, go, homeFor, html, icon, inTelegram, loading, mount, on,
  setToken, setUser, state, storage, toast, toastError,
} from '../core.js';
import { LANGS, getLang, setLang, t } from '../i18n.js';
import { certificatesError, certificatesField } from './components.js';

const NEXT_KEY = 'tolk_next';

export async function telegramLogin() {
  const data = await api('/api/auth/telegram', { method: 'POST', body: { init_data: state.tg.initData } });
  setToken(data.token);
  state.user = data.user;
  return data;
}

/** Telegram Login Widget redirects back with ?id=..&hash=.. in the query string. */
export async function widgetLoginFromUrl() {
  const params = new URLSearchParams(location.search);
  if (!params.get('hash') || !params.get('id') || !params.get('auth_date')) return null;
  const body = {};
  ['id', 'first_name', 'last_name', 'username', 'photo_url', 'auth_date', 'hash'].forEach((k) => {
    if (params.has(k)) body[k] = ['id', 'auth_date'].includes(k) ? Number(params.get(k)) : params.get(k);
  });
  const next = sessionStorage.getItem(NEXT_KEY) || '';
  history.replaceState(null, '', `${location.pathname}#${next || '/'}`);
  const data = await api('/api/auth/telegram-widget', { method: 'POST', body });
  setToken(data.token);
  state.user = data.user;
  return { data, next };
}

export async function renderLogin(view, _params, query, alive) {
  const next = query.next || '';
  try { sessionStorage.setItem(NEXT_KEY, next); } catch { /* ignore */ }
  const cfg = state.config;
  mount(view, html`
    <div class="container"><div class="auth-wrap stack-lg">
      <div class="card card-pad stack center">
        <div class="brand-mark" style="width:56px;height:56px;font-size:26px;margin:0 auto;border-radius:16px">T</div>
        <h2>${t('login_title')}</h2>
        <p class="muted">${t('login_text')}</p>
        ${inTelegram() ? html`<button class="btn btn-primary btn-lg btn-block" data-action="tg-login" data-next="${next}">${t('continue_with_telegram')}</button>`
          : cfg.bot_username ? html`
            <div id="tg-widget" style="min-height:48px;display:flex;justify-content:center"></div>
            <div class="faint tiny">${t('or')}</div>
            <a class="btn btn-outline btn-block" href="https://t.me/${cfg.bot_username}" target="_blank" rel="noopener">${t('open_in_telegram')}</a>`
          : html`<div class="notice notice-warning small"><span class="ico">⚠️</span><div>${t('tg_login_unavailable')}</div></div>`}
      </div>
      ${cfg.demo_mode ? html`<div class="card card-pad"><h3>${t('demo_accounts')}</h3>
        <p class="small muted" style="margin:4px 0 12px">${t('demo_accounts_text')}</p><div id="demo-users">${loading()}</div></div>` : ''}
    </div></div>`);

  if (!inTelegram() && cfg.bot_username) {
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.dataset.telegramLogin = cfg.bot_username;
    script.dataset.size = 'large';
    script.dataset.radius = '12';
    script.dataset.requestAccess = 'write';
    script.dataset.authUrl = `${location.origin}/`;
    script.dataset.lang = getLang();
    document.getElementById('tg-widget')?.appendChild(script);
  }
  if (cfg.demo_mode) {
    try {
      const users = await api('/api/auth/demo-users');
      if (!alive()) return;
      const roles = [['admin', t('role_admin')], ['tutor', t('role_tutor')], ['student', t('role_student')]];
      mount(document.getElementById('demo-users'), html`<div class="stack">${roles.map(([role, label]) => {
        const list = users.filter((u) => u.role === role);
        return list.length ? html`<div><div class="label" style="margin-bottom:6px">${label}</div><div class="stack" style="gap:6px">
          ${list.map((u) => html`<button class="demo-user" data-action="demo-login" data-id="${u.id}" data-next="${next}">
            ${avatar(u, 'avatar-sm')}<span class="grow bold small">${u.full_name}</span>
            ${u.tutor_status === 'pending' ? html`<span class="badge badge-warning">${t('status_pending')}</span>` : ''}
            ${icon('arrow')}</button>`)}</div></div>` : '';
      })}</div>`);
    } catch (err) {
      if (alive()) mount(document.getElementById('demo-users'), errorBox(err));
    }
  }
}

on('tg-login', async (el) => {
  await busy(el, async () => {
    try { completeLogin(await telegramLogin(), el.dataset.next); } catch (err) { toastError(err); }
  });
});
on('demo-login', async (el) => {
  try {
    completeLogin(await api('/api/auth/demo-login', { method: 'POST', body: { user_id: Number(el.dataset.id) } }), el.dataset.next);
  } catch (err) { toastError(err); }
});

// ---------- onboarding ----------
let chosenRole = 'student';

export function renderOnboarding(view) {
  const u = state.user;
  if (u.onboarded) return go(homeFor(u));
  mount(view, html`
    <div class="container"><div class="auth-wrap" style="max-width:560px">
      <div class="card card-pad stack-lg">
        <div><h2>${t('welcome_title', { name: u.full_name.split(' ')[0] })}</h2><p class="muted mt">${t('welcome_text')}</p></div>
        <div class="role-cards" id="role-cards">${roleCards()}</div>
        <form class="stack" data-submit="onboard">
          <label class="field"><span>${t('full_name')}</span><input class="input" name="full_name" required minlength="2" maxlength="120" value="${u.full_name}"></label>
          <label class="field"><span>${t('phone')} <span class="faint">(${t('optional')})</span></span>
            <input class="input" name="phone" type="tel" maxlength="32" placeholder="+998 90 123 45 67" value="${u.phone}"></label>
          <div id="tutor-fields" class="stack" ${chosenRole === 'tutor' ? '' : 'hidden'}>
            <label class="field"><span>${t('subjects_you_teach')}</span><input class="input" name="subjects" maxlength="255" placeholder="${t('subjects_placeholder')}"></label>
            <label class="field"><span>${t('about_you')}</span><textarea class="textarea" name="bio" maxlength="1500" placeholder="${t('bio_placeholder')}"></textarea>
              <span class="hint">${t('bio_hint')}</span></label>
            ${certificatesField()}
            <div class="notice notice-info small"><span class="ico">🛡️</span><div>${t('tutor_review_note')}</div></div>
          </div>
          <button class="btn btn-primary btn-lg btn-block" type="submit">${t('finish_sign_up')}</button>
        </form>
      </div>
    </div></div>`);
}

function roleCards() {
  return [['student', '🎓', t('i_am_student'), t('i_am_student_text')], ['tutor', '🧑‍🏫', t('i_am_teacher'), t('i_am_teacher_text')]].map(
    ([role, emoji, title, text]) => html`<button type="button" class="role-card ${chosenRole === role ? 'active' : ''}" data-action="pick-role" data-role="${role}">
      <div class="emoji">${emoji}</div><h3>${title}</h3><p>${text}</p></button>`,
  );
}

on('pick-role', (el) => {
  chosenRole = el.dataset.role;
  mount(document.getElementById('role-cards'), roleCards());
  document.getElementById('tutor-fields').hidden = chosenRole !== 'tutor';
});
on('onboard', async (form) => {
  const data = formData(form);
  if (chosenRole === 'tutor') {
    if ((data.bio || '').trim().length < 20 || !(data.subjects || '').trim()) return toast(t('tutor_fields_required'), 'warning');
    const certError = certificatesError(form.certificates.files);
    if (certError) return toast(certError, 'warning');
  }
  const fd = new FormData();
  fd.append('role', chosenRole);
  ['full_name', 'phone', 'subjects', 'bio'].forEach((k) => fd.append(k, data[k] || ''));
  if (chosenRole === 'tutor') [...form.certificates.files].forEach((f) => fd.append('certificates', f));
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      const user = await api('/api/auth/onboarding', { method: 'POST', form: fd });
      setUser(user);
      toast(chosenRole === 'tutor' ? t('tutor_application_sent') : t('welcome_aboard'), 'success');
      const next = sessionStorage.getItem(NEXT_KEY);
      go(chosenRole === 'student' && next ? next : homeFor(user));
    } catch (err) { toastError(err); }
  });
});

// ---------- profile ----------
export function renderProfile(view) {
  const u = state.user;
  const roleLabel = t(`role_${u.role}`);
  mount(view, html`
    <div class="container" style="max-width:680px">
      <div class="page-head"><div><h1>${t('profile')}</h1></div></div>
      <div class="card card-pad stack-lg">
        <div class="row">${avatar(u, 'avatar-lg')}<div class="grow"><h3>${u.full_name}</h3>
          <div class="row-wrap mt"><span class="badge badge-primary">${roleLabel}</span>
            ${u.role === 'tutor' ? html`<span class="badge badge-${u.tutor_status === 'approved' ? 'success' : u.tutor_status === 'rejected' ? 'danger' : 'warning'}">${t(`status_${u.tutor_status || 'pending'}`)}</span>` : ''}
            ${u.telegram_username ? html`<span class="badge">${u.telegram_username}</span>` : ''}</div></div></div>
        <form class="stack" data-submit="profile-save">
          <label class="field"><span>${t('full_name')}</span><input class="input" name="full_name" required minlength="2" maxlength="120" value="${u.full_name}"></label>
          <label class="field"><span>${t('phone')}</span><input class="input" name="phone" type="tel" maxlength="32" value="${u.phone}"></label>
          <label class="field"><span>${t('interface_language')}</span><select class="select" name="lang">
            ${Object.entries(LANGS).map(([code, name]) => html`<option value="${code}" ${u.lang === code ? 'selected' : ''}>${name}</option>`)}</select></label>
          ${u.role === 'tutor' ? html`
            <label class="field"><span>${t('subjects_you_teach')}</span><input class="input" name="subjects" maxlength="255" value="${u.subjects}"></label>
            <label class="field"><span>${t('about_you')}</span><textarea class="textarea" name="bio" maxlength="1500">${u.bio}</textarea></label>` : ''}
          <div class="row-wrap"><button class="btn btn-primary" type="submit">${t('save')}</button>
            ${u.role === 'tutor' && u.tutor_status === 'approved' ? html`<a class="btn btn-outline" href="#/teacher/${u.id}">${t('view_public_profile')}</a>` : ''}</div>
        </form>
        ${state.config.support_contact ? html`<div class="notice notice-info small"><span class="ico">💬</span><div>${t('support_text', { contact: state.config.support_contact })}</div></div>` : ''}
        <div class="divider" style="margin:0"></div>
        <button class="btn btn-danger-soft" data-action="logout">${icon('logout')} ${t('sign_out')}</button>
      </div>
    </div>`);
}

on('profile-save', async (form) => {
  const data = formData(form);
  await busy(form.querySelector('[type=submit]'), async () => {
    try {
      const user = await api('/api/auth/me', { method: 'PATCH', body: data });
      storage.set('tolk_lang', user.lang);
      setLang(user.lang);
      setUser(user);
      toast(t('saved'), 'success');
      go('/profile');
    } catch (err) { toastError(err); }
  });
});
