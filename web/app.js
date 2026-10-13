// FlipCheck: photo -> what it is -> what it's worth -> a listing. Each step renders as soon as it's ready.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = (n) => (n == null ? '–' : `$${n >= 100 ? Math.round(n) : n.toFixed(2)}`);
const loading = (text) => `<p class="loading">${esc(text)}</p>`;
const safeUrl = (u) => (/^https:\/\//.test(u || '') ? u : '#');
let examples = {};
fetch('examples/results.json').then((r) => (r.ok ? r.json() : {})).then((j) => { examples = j; }).catch(() => {});

async function shrink(file) {
  // Upload at most 1280 px: faster on mobile data, and the model doesn't need more.
  const bitmap = await createImageBitmap(file);
  const k = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height));
  const canvas = new OffscreenCanvas(Math.round(bitmap.width * k), Math.round(bitmap.height * k));
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return canvas.convertToBlob({ type: 'image/jpeg', quality: 0.88 });
}

async function api(path, body) {
  const res = await fetch(path, { method: 'POST', ...(body instanceof FormData ? { body } : { body: JSON.stringify(body), headers: { 'Content-Type': 'application/json' } }) });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Something went wrong (${res.status})`);
  return res.json();
}

function renderItem(photoUrl, item) {
  $('item-card').innerHTML = `<div class="item"><img src="${photoUrl}" alt="Your photo"><div>
      <h2>${esc(item.title)}</h2><div class="meta">${esc(item.condition)} · ${esc(item.confidence)} confidence</div></div></div>
    <form class="search" id="search"><input id="query" value="${esc(item.search_query)}" aria-label="eBay search">
      <button type="submit">Re-check</button></form>`;
}

function renderPrice(p) {
  if (p.status !== 'ok') {
    $('price-card').innerHTML = `<div class="label">Price</div><p>Not enough live listings for this search (${p.comps_used}). Try a simpler search above.</p>`;
    return;
  }
  const span = Math.max(1, p.market_high - p.market_low), at = (v) => `${Math.min(100, Math.max(0, ((v - p.market_low) / span) * 100))}%`;
  $('price-card').innerHTML = `<div class="label">Fair price</div>
    <div class="fair">${money(p.fair)}</div>
    <div class="split"><div><small>Quick sale</small><b>${money(p.quick)}</b></div><div><small>If you can wait</small><b>${money(p.patient)}</b></div></div>
    <div class="range" aria-hidden="true"><i style="left:${at(p.quick)};right:calc(100% - ${at(p.patient)})"></i><b style="left:${at(p.fair)}"></b></div>
    <div class="ends"><span>${money(p.market_low)}</span><span>${p.comps_used} live listings</span><span>${money(p.market_high)}</span></div>
    <div class="comps">${p.nearest.map((c) => `<a href="${esc(safeUrl(c.link))}" target="_blank" rel="noopener noreferrer">
      <img src="${esc(safeUrl(c.thumbnail))}" alt="" loading="lazy"><span><b>${money(c.price)}</b><br>${esc(c.condition)}</span></a>`).join('')}</div>
    <p class="note">${p.method === 'tabpfn' ? 'Priced for your item\'s condition by TabPFN, from' : 'Middle of'} current eBay asking prices. Sold prices are usually a bit lower.</p>`;
}

function renderListing(l) {
  const specifics = l.specifics.map((s) => `${s.name}: ${s.value}`).join('\n');
  $('listing-card').innerHTML = `<div class="label">Your listing</div>
    <div class="copyrow"><span class="listing-title">${esc(l.title)}</span><button type="button" data-copy="${esc(l.title)}">Copy</button></div>
    <div class="copyrow"><span class="label">Description</span><button type="button" data-copy="${esc(l.description)}">Copy</button></div>
    <p class="listing-desc">${esc(l.description)}</p>
    <div class="copyrow"><span class="label">Item specifics</span><button type="button" data-copy="${esc(specifics)}">Copy</button></div>
    <table>${l.specifics.map((s) => `<tr><td>${esc(s.name)}</td><td>${esc(s.value)}</td></tr>`).join('')}</table>`;
}

async function run(file, cached) {
  document.body.classList.remove('home');
  $('home').hidden = true;
  $('result').hidden = false;
  scrollTo(0, 0);
  const photoUrl = URL.createObjectURL(file);
  $('item-card').innerHTML = loading('Looking at your photo…');
  $('price-card').innerHTML = '';
  $('listing-card').innerHTML = '';
  try {
    const photo = cached ? null : await shrink(file);
    const form = () => { const f = new FormData(); f.append('photo', photo, 'photo.jpg'); return f; };
    const item = cached ? cached.item : await api('/api/identify', form());
    renderItem(photoUrl, item);

    const priceFor = async (query) => {
      $('price-card').innerHTML = loading('Checking live eBay listings…');
      const p = cached && query === cached.item.search_query ? cached.price
        : await api('/api/price', { query, condition: item.condition });
      renderPrice(p);
      return p;
    };
    const pricing = await priceFor(item.search_query);
    $('search').addEventListener('submit', (ev) => { ev.preventDefault(); priceFor($('query').value).catch(showError('price-card')); });

    $('listing-card').innerHTML = loading('Writing your listing…');
    let listing = cached?.listing;
    if (!listing) {
      const f = form();
      f.append('item', JSON.stringify(item));
      f.append('pricing', JSON.stringify(pricing));
      listing = await api('/api/listing', f);
    }
    renderListing(listing);
  } catch (err) {
    showError('item-card')(err);
  }
}

const showError = (card) => (err) => { $(card).innerHTML = `<p class="error">${esc(err.message)}</p>`; };

$('camera').addEventListener('change', (ev) => { if (ev.target.files[0]) run(ev.target.files[0]); ev.target.value = ''; });
document.querySelectorAll('[data-example]').forEach((btn) => btn.addEventListener('click', async () => {
  const name = btn.dataset.example;
  const blob = await (await fetch(`examples/${name}.jpg`)).blob();
  run(new File([blob], `${name}.jpg`, { type: blob.type }), examples[name]);  // pre-computed when available: instant
}));
document.addEventListener('click', async (ev) => {
  const btn = ev.target.closest('[data-copy]');
  if (!btn) return;
  await navigator.clipboard.writeText(btn.dataset.copy).catch(() => {});
  btn.textContent = 'Copied ✓';
  setTimeout(() => { btn.textContent = 'Copy'; }, 1500);
});
