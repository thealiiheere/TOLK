// Explore / catalog page with filters (category, subjects, price range, teacher rating, free seats) and sorting.
import { api, empty, errorBox, fmtNumber, html, icon, loading, mount, on, openSheet } from '../core.js';
import { subjectName, t } from '../i18n.js';
import { classGrid } from './components.js';

const RATING_OPTIONS = [0, 3, 4, 4.5];
let filters = null; // options from /api/catalog/filters
let f = {}; // current filter values
let alive = () => true;
let sheet = null;
let searchTimer = null;

function readQuery(query) {
  return {
    cat: query.cat || '',
    s: (query.s || '').split(',').filter(Boolean),
    min: query.min ? Number(query.min) : null,
    max: query.max ? Number(query.max) : null,
    r: Number(query.r) || 0,
    q: query.q || '',
    sort: query.sort || 'rating',
    seats: query.seats === '1',
  };
}

function queryString() {
  const q = new URLSearchParams();
  if (f.cat) q.set('cat', f.cat);
  if (f.s.length) q.set('s', f.s.join(','));
  if (f.min != null) q.set('min', f.min);
  if (f.max != null) q.set('max', f.max);
  if (f.r) q.set('r', f.r);
  if (f.q) q.set('q', f.q);
  if (f.sort !== 'rating') q.set('sort', f.sort);
  if (f.seats) q.set('seats', '1');
  return q.toString();
}

function activeCount() {
  return (f.cat ? 1 : 0) + f.s.length + (f.min != null || f.max != null ? 1 : 0) + (f.r ? 1 : 0) + (f.seats ? 1 : 0);
}

export async function render(view, _params, query, isAlive) {
  alive = isAlive;
  f = readQuery(query);
  mount(view, html`
    <div class="container">
      <section class="hero">
        <h1>${t('hero_title_a')}<br><span class="hl">${t('hero_title_b')}</span></h1>
        <p>${t('hero_text')}</p>
        <form class="search" data-submit="f-search" role="search">
          ${icon('search')}
          <input class="input" name="q" type="search" value="${f.q}" placeholder="${t('search_placeholder')}" data-input="f-search-typing" autocomplete="off">
        </form>
        <div class="hero-points"><span>${t('hero_point_1')}</span><span>${t('hero_point_2')}</span><span>${t('hero_point_3')}</span></div>
      </section>
      <div class="seg" id="cat-tabs" style="margin-bottom:16px">${catTabs()}</div>
      <div class="explore">
        <aside class="filters-panel card card-pad" id="filters-aside">${loading()}</aside>
        <section>
          <div class="results-bar">
            <div class="results-controls">
              <button class="btn btn-outline filters-toggle" data-action="f-open">${icon('filter')} ${t('filters')}
                <span id="filters-count">${activeCount() ? html`<span class="count-dot">${activeCount()}</span>` : ''}</span></button>
              <select class="select" data-change="f-sort" aria-label="${t('sort_by')}">
                ${['rating', 'price_asc', 'price_desc', 'newest'].map((s) => html`<option value="${s}" ${f.sort === s ? 'selected' : ''}>${t(`sort_${s}`)}</option>`)}
              </select>
            </div>
            <h2 id="results-count" class="results-count">${t('classes')}</h2>
          </div>
          <div id="results">${loading()}</div>
        </section>
      </div>
    </div>`);

  try {
    filters = await api('/api/catalog/filters');
    if (!alive()) return;
    renderPanels();
    await loadResults();
  } catch (err) {
    if (alive()) mount(document.getElementById('results'), errorBox(err));
  }
}

function catTabs() {
  return [['', t('cat_all')], ['language', t('cat_language')], ['other', t('cat_other')]].map(
    ([v, label]) => html`<button type="button" class="${f.cat === v ? 'active' : ''}" data-action="f-cat" data-v="${v}">${label}</button>`,
  );
}

function priceStep() {
  const span = (filters?.price_max || 0) - (filters?.price_min || 0);
  return span > 200000 ? 10000 : span > 20000 ? 1000 : 100;
}

function panel() {
  if (!filters) return loading();
  const langs = filters.languages || [];
  const others = filters.other_subjects || [];
  const lo = filters.price_min;
  const hi = filters.price_max;
  const curMin = f.min ?? lo;
  const curMax = f.max ?? hi;
  const showLangs = f.cat !== 'other' && langs.length;
  const showOthers = f.cat !== 'language' && others.length;
  return html`
    ${showLangs ? html`<div class="filter-group"><h4>${t('filter_languages')}</h4><div class="chips">
      ${langs.map((l) => html`<button type="button" class="chip ${f.s.includes(l.code) ? 'active' : ''}" data-action="f-subj" data-v="${l.code}">
        ${subjectName(l.code)} <span class="n">${l.count}</span></button>`)}
    </div></div>` : ''}
    ${showOthers ? html`<div class="filter-group"><h4>${t('filter_other_subjects')}</h4><div class="chips">
      ${others.map((o) => html`<button type="button" class="chip ${f.s.includes(o.name.toLowerCase()) ? 'active' : ''}" data-action="f-subj" data-v="${o.name.toLowerCase()}">
        ${o.name} <span class="n">${o.count}</span></button>`)}
    </div></div>` : ''}
    ${hi > lo ? html`<div class="filter-group"><h4>${t('filter_price')} (${t('currency')})</h4>
      <div class="range" data-range>
        <div class="track"></div><div class="fill" data-fill></div>
        <input type="range" min="${lo}" max="${hi}" step="${priceStep()}" value="${curMin}" data-input="f-price-drag" data-change="f-price" data-end="min" aria-label="${t('price_from')}">
        <input type="range" min="${lo}" max="${hi}" step="${priceStep()}" value="${curMax}" data-input="f-price-drag" data-change="f-price" data-end="max" aria-label="${t('price_to')}">
      </div>
      <div class="price-inputs">
        <input class="input" inputmode="numeric" value="${fmtNumber(curMin)}" data-change="f-price-num" data-end="min" aria-label="${t('price_from')}">
        <span class="faint">—</span>
        <input class="input" inputmode="numeric" value="${fmtNumber(curMax)}" data-change="f-price-num" data-end="max" aria-label="${t('price_to')}">
      </div></div>` : ''}
    <div class="filter-group"><h4>${t('filter_rating')}</h4><div class="rating-opts">
      ${RATING_OPTIONS.map((r) => html`<label><input type="radio" name="min-rating" value="${r}" ${f.r === r ? 'checked' : ''} data-change="f-rating">
        ${r ? html`<span class="stars" style="--v:${r}"></span> ${t('rating_from', { n: r })}` : t('any_rating')}</label>`)}
    </div></div>
    <div class="filter-group">
      <label class="check"><input type="checkbox" ${f.seats ? 'checked' : ''} data-change="f-seats"> ${t('only_free_seats')}</label>
    </div>
    ${activeCount() ? html`<div class="filter-group"><button class="btn btn-ghost btn-sm btn-block" data-action="f-clear">${t('clear_filters')}</button></div>` : ''}`;
}

function renderPanels() {
  const aside = document.getElementById('filters-aside');
  if (aside) mount(aside, panel());
  if (sheet && document.body.contains(sheet.el)) mount(sheet.el.querySelector('.sheet-body'), panel());
  document.querySelectorAll('[data-range]').forEach(updateFill);
  const tabs = document.getElementById('cat-tabs');
  if (tabs) mount(tabs, catTabs());
  const count = document.getElementById('filters-count');
  if (count) mount(count, activeCount() ? html`<span class="count-dot">${activeCount()}</span>` : '');
}

function updateFill(range) {
  const [a, b] = range.querySelectorAll('input[type=range]');
  const lo = Number(a.min);
  const span = Number(a.max) - lo || 1;
  const fill = range.querySelector('[data-fill]');
  const x1 = ((Math.min(a.value, b.value) - lo) / span) * 100;
  const x2 = ((Math.max(a.value, b.value) - lo) / span) * 100;
  fill.style.left = `${x1}%`;
  fill.style.width = `${x2 - x1}%`;
}

async function loadResults() {
  const box = document.getElementById('results');
  if (!box) return;
  history.replaceState(null, '', `#/${queryString() ? `?${queryString()}` : ''}`);
  try {
    const groups = await api('/api/catalog/groups', {
      query: {
        category: f.cat, subjects: f.s.join(','), price_min: f.min, price_max: f.max,
        min_rating: f.r || null, q: f.q, sort: f.sort, has_seats: f.seats ? 'true' : null,
      },
    });
    if (!alive()) return;
    mount(document.getElementById('results-count'), t('classes_found', { n: groups.length }));
    const footBtn = sheet?.el.querySelector('[data-results-btn]');
    if (footBtn) footBtn.textContent = t('show_results', { n: groups.length });
    mount(box, groups.length ? classGrid(groups) : empty('🔎', t('no_classes_title'), t('no_classes_text'),
      activeCount() || f.q ? html`<button class="btn btn-soft" data-action="f-clear">${t('clear_filters')}</button>` : ''));
  } catch (err) {
    if (alive()) mount(box, errorBox(err));
  }
}

function apply() {
  renderPanels();
  loadResults();
}

// ---------- handlers ----------
on('f-cat', (el) => {
  f.cat = el.dataset.v;
  // drop selected subjects that don't belong to the new category
  const langCodes = new Set((filters?.languages || []).map((l) => l.code));
  if (f.cat === 'language') f.s = f.s.filter((s) => langCodes.has(s));
  if (f.cat === 'other') f.s = f.s.filter((s) => !langCodes.has(s));
  apply();
});
on('f-subj', (el) => {
  const v = el.dataset.v;
  f.s = f.s.includes(v) ? f.s.filter((x) => x !== v) : [...f.s, v];
  apply();
});
on('f-price-drag', (el) => {
  const range = el.closest('[data-range]');
  const [a, b] = range.querySelectorAll('input[type=range]');
  if (Number(a.value) > Number(b.value)) (el === a ? a : b).value = el === a ? b.value : a.value;
  updateFill(range);
  const nums = range.parentElement.querySelectorAll('[data-change="f-price-num"]');
  nums[0].value = fmtNumber(a.value);
  nums[1].value = fmtNumber(b.value);
});
function setPrice(minV, maxV) {
  const lo = filters.price_min;
  const hi = filters.price_max;
  const a = Math.max(lo, Math.min(minV, maxV));
  const b = Math.min(hi, Math.max(minV, maxV));
  f.min = a > lo ? a : null;
  f.max = b < hi ? b : null;
  apply();
}
on('f-price', (el) => {
  const [a, b] = el.closest('[data-range]').querySelectorAll('input[type=range]');
  setPrice(Number(a.value), Number(b.value));
});
on('f-price-num', (el) => {
  const nums = el.parentElement.querySelectorAll('[data-change="f-price-num"]');
  const parse = (input, fallback) => Number(String(input.value).replace(/\D/g, '')) || fallback;
  setPrice(parse(nums[0], filters.price_min), parse(nums[1], filters.price_max));
});
on('f-rating', (el) => { f.r = Number(el.value); apply(); });
on('f-seats', (el) => { f.seats = el.checked; apply(); });
on('f-sort', (el) => { f.sort = el.value; loadResults(); });
on('f-search', (form) => {
  clearTimeout(searchTimer);
  f.q = form.q.value.trim();
  form.q.blur();
  loadResults();
});
on('f-search-typing', (el) => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => { f.q = el.value.trim(); loadResults(); }, 350);
});
on('f-clear', () => {
  f = { ...readQuery({}), sort: f.sort };
  const input = document.querySelector('.hero .search input');
  if (input) input.value = '';
  apply();
});
on('f-open', () => {
  sheet = openSheet({
    title: t('filters'),
    body: panel(),
    foot: html`<button class="btn btn-primary btn-block" data-close data-results-btn>${t("show_results", { n: "…" })}</button>`,
    onClose: () => { sheet = null; },
  });
  sheet.el.querySelectorAll('[data-range]').forEach(updateFill);
  loadResults();
});
