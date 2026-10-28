// App boot: Telegram integration, session restore, shell (top bar + bottom tabs), routing.
import {
  api, avatar, currentRoute, findRoute, go, homeFor, html, icon, inTelegram, mount, nextRender, on, route, setToken,
  setUser, state, storage, toastError,
} from './core.js';
import { LANGS, detectLang, getLang, setLang, t } from './i18n.js';
import * as account from './pages/account.js';
import * as catalog from './pages/class.js';
import * as admin from './pages/admin.js';
import * as explore from './pages/explore.js';
import * as student from './pages/student.js';
import * as tutor from './pages/tutor.js';

route('/', explore.render, { tab: 'explore' });
route('/class/:id', catalog.renderClass, { tab: 'explore', back: true });
route('/teacher/:id', catalog.renderTeacher, { tab: 'explore', back: true });
route('/login', account.renderLogin, { tab: 'login', guest: true });
route('/welcome', account.renderOnboarding, { auth: true });
route('/profile', account.renderProfile, { tab: 'profile', auth: true });
route('/my', student.render, { tab: 'my', role: ['student', 'tutor'] }); // teachers may study too
route('/teach', tutor.render, { tab: 'teach', role: 'tutor' });
route('/admin', admin.render, { tab: 'admin', role: 'admin' });
route('/admin/:tab', admin.render, { tab: 'admin', role: 'admin', back: true });

// ---------- theme ----------
function applyTheme() {
  const tg = state.tg;
  // telegram-web-app.js reports colorScheme 'light' even outside Telegram, so only trust it inside the Mini App
  const dark = inTelegram() && tg?.colorScheme ? tg.colorScheme === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  const surface = getComputedStyle(document.documentElement).getPropertyValue('--surface').trim();
  const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
  try { tg?.setHeaderColor?.(bg); tg?.setBackgroundColor?.(bg); tg?.setBottomBarColor?.(surface); } catch { /* old clients */ }
}

function initTelegram() {
  const tg = state.tg;
  if (!tg) return;
  try {
    tg.ready();
    tg.expand();
    tg.disableVerticalSwipes?.();
    tg.onEvent?.('themeChanged', applyTheme);
    tg.BackButton?.onClick(() => (history.length > 1 ? history.back() : go('/')));
    setupDesktopFullscreen(tg);
  } catch { /* running outside Telegram or an old client */ }
}

// ---------- full screen on desktop Telegram ----------
const MOBILE_PLATFORMS = new Set(['android', 'android_x', 'ios']);

/**
 * Telegram Desktop, macOS and Telegram Web open Mini Apps in a small phone-sized window. There we ask for full
 * screen (Bot API 8.0+) so the desktop layout gets the whole screen. Phones are left alone. Returns true if enabled.
 */
export function setupDesktopFullscreen(tg) {
  if (!tg?.initData || !tg.platform || tg.platform === 'unknown' || MOBILE_PLATFORMS.has(tg.platform)) return false;
  if (typeof tg.requestFullscreen !== 'function' || !tg.isVersionAtLeast?.('8.0')) return false;
  state.fullscreenCapable = true;
  const refresh = () => renderShell(findRoute(currentRoute().path)?.tab);
  tg.onEvent?.('fullscreenChanged', refresh);
  tg.onEvent?.('fullscreenFailed', () => { state.fullscreenCapable = false; refresh(); });
  if (!tg.isFullscreen) tg.requestFullscreen();
  return true;
}

// ---------- session ----------
async function restoreSession() {
  try {
    const widget = await account.widgetLoginFromUrl();
    if (widget) return;
  } catch (err) { toastError(err); }
  if (state.token) {
    try { state.user = await api('/api/auth/me'); } catch { setToken(null); state.user = null; }
  }
  if (!state.user && inTelegram()) {
    try { await account.telegramLogin(); } catch (err) { toastError(err); }
  }
}

// ---------- shell ----------
function navItems() {
  const u = state.user;
  const items = [{ tab: 'explore', href: '#/', icon: 'compass', label: t('nav_explore') }];
  if (!u) items.push({ tab: 'login', href: '#/login', icon: 'login', label: t('nav_sign_in'), mobileOnly: true });
  else if (u.onboarded && u.role === 'student') items.push({ tab: 'my', href: '#/my', icon: 'book', label: t('nav_my_learning') });
  else if (u.onboarded && u.role === 'tutor') {
    // teachers can also take classes: both sides get a tab
    items.push({ tab: 'teach', href: '#/teach', icon: 'board', label: t('nav_teaching') });
    items.push({ tab: 'my', href: '#/my', icon: 'book', label: t('nav_my_learning') });
  }
  else if (u.onboarded && u.role === 'admin') items.push({ tab: 'admin', href: '#/admin', icon: 'shield', label: t('nav_admin') });
  if (u?.onboarded) items.push({ tab: 'profile', href: '#/profile', icon: 'user', label: t('nav_profile'), mobileOnly: true });
  return items;
}

function renderShell(activeTab = '') {
  const u = state.user;
  const items = navItems();
  mount(document.getElementById('appbar'), html`
    <div class="container">
      <a class="brand" href="#/"><span class="brand-mark">T</span><span>TOLK<small>${t('tagline')}</small></span></a>
      <nav class="nav">${items.filter((i) => !i.mobileOnly).map((i) => html`<a href="${i.href}" class="${i.tab === activeTab ? 'active' : ''}">${i.label}</a>`)}</nav>
      <div class="appbar-end">
        ${state.fullscreenCapable ? html`<button class="lang-btn" data-action="toggle-fullscreen"
          aria-label="${state.tg.isFullscreen ? t('exit_fullscreen') : t('enter_fullscreen')}" title="${state.tg.isFullscreen ? t('exit_fullscreen') : t('enter_fullscreen')}">
          ${icon(state.tg.isFullscreen ? 'minimize' : 'maximize')}</button>` : ''}
        <details class="dropdown" id="lang-menu">
          <summary class="lang-btn" aria-label="${t('interface_language')}">${icon('globe')}${getLang().toUpperCase()}</summary>
          <div class="dropdown-menu">${Object.entries(LANGS).map(([code, name]) => html`
            <button class="${code === getLang() ? 'active' : ''}" data-action="set-lang" data-lang="${code}">${name}</button>`)}</div>
        </details>
        ${u ? html`<details class="dropdown" id="user-menu">
            <summary aria-label="${t('nav_profile')}">${avatar(u, 'avatar-sm')}</summary>
            <div class="dropdown-menu">
              <div style="padding:8px 12px"><div class="bold small truncate">${u.full_name}</div><div class="tiny muted">${t(`role_${u.role}`)}</div></div>
              ${u.onboarded ? html`<a href="#/profile">${icon('user')} ${t('profile')}</a>` : ''}
              <button data-action="logout">${icon('logout')} ${t('sign_out')}</button>
            </div></details>`
          : html`<a class="btn btn-primary btn-sm" href="#/login">${t('nav_sign_in')}</a>`}
      </div>
    </div>`);
  const tabbar = document.getElementById('tabbar');
  const showTabbar = items.length > 1;
  tabbar.hidden = !showTabbar;
  document.body.classList.toggle('no-tabbar', !showTabbar);
  mount(tabbar, items.map((i) => html`<a href="${i.href}" class="${i.tab === activeTab ? 'active' : ''}">${icon(i.icon)}<span>${i.label}</span></a>`));
}

let lastPath = null;
async function renderRoute() {
  const { path, query } = currentRoute();
  const r = findRoute(path) || findRoute('/');
  const u = state.user;
  if (u && !u.onboarded && path !== '/welcome') return go('/welcome');
  if ((r.auth || r.role) && !u) return go(`/login?next=${encodeURIComponent(path)}`);
  if (r.role && ![r.role].flat().includes(u.role)) return go(homeFor(u));
  if (r.guest && u) return go(homeFor(u));

  document.querySelectorAll('details.dropdown[open]').forEach((d) => { d.open = false; });
  renderShell(r.tab);
  if (state.tg?.BackButton) {
    try { (r.back ? state.tg.BackButton.show() : state.tg.BackButton.hide()); } catch { /* ignore */ }
  }
  if (path !== lastPath) window.scrollTo(0, 0);
  lastPath = path;
  const alive = nextRender();
  try {
    await r.handler(document.getElementById('view'), r.params, query, alive);
  } catch (err) {
    console.error(err);
    toastError(err);
  }
}

// ---------- global handlers ----------
on('set-lang', async (el) => {
  const lang = el.dataset.lang;
  setLang(lang);
  storage.set('tolk_lang', lang);
  document.getElementById('lang-menu').open = false;
  if (state.user) {
    try { setUser(await api('/api/auth/me', { method: 'PATCH', body: { lang } })); } catch { /* keep local choice */ }
  }
  renderRoute();
});
on('logout', async () => {
  try { await api('/api/auth/logout', { method: 'POST' }); } catch { /* ignore */ }
  setToken(null);
  state.user = null;
  go('/');
});
document.addEventListener('tolk:user', () => renderShell(findRoute(currentRoute().path)?.tab));
on('toggle-fullscreen', () => {
  try { (state.tg.isFullscreen ? state.tg.exitFullscreen() : state.tg.requestFullscreen()); } catch { /* unsupported */ }
});
document.addEventListener('tolk:signed-out', () => go('/login'));
document.addEventListener('click', (e) => {
  // close dropdowns when clicking outside / on a link inside them
  document.querySelectorAll('details.dropdown[open]').forEach((d) => {
    if (!d.contains(e.target) || e.target.closest('a')) d.open = false;
  });
});
window.addEventListener('hashchange', renderRoute);

async function boot() {
  initTelegram();
  applyTheme();
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', applyTheme);
  setLang(detectLang(storage.get('tolk_lang'), state.tg?.initDataUnsafe?.user?.language_code));
  try { state.config = await api('/api/config'); } catch { state.config = {}; }
  await restoreSession();
  if (state.user?.lang) setLang(state.user.lang); // the saved account preference wins
  await renderRoute();
}

boot();
