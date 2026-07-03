/* Screendex — Search Page JS */

const API = '';
let currentPage = 1;
let currentQuery = '';
let currentType = '';
let currentCategory = '';
let suggestTimer = null;

// ── On Load ────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  setupSearch();

  // Pre-fill from URL query params
  const params = new URLSearchParams(window.location.search);
  const q = params.get('q');
  if (q) {
    document.getElementById('searchInput').value = q;
    doSearch(q, 1);
  }
});

// ── Stats ──────────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const res = await fetch(`${API}/api/search/stats`);
    const data = await res.json();
    document.getElementById('statTotal').textContent    = data.total_images.toLocaleString();
    document.getElementById('statKeywords').textContent = data.total_keywords.toLocaleString();
    document.getElementById('statDigital').textContent  = data.born_digital.toLocaleString();
    document.getElementById('statScene').textContent    = data.scene_text.toLocaleString();
  } catch (e) {
    console.warn('Stats unavailable', e);
  }
}

// ── Search Setup ───────────────────────────────────────────────────────────────
function setupSearch() {
  const form  = document.getElementById('searchForm');
  const input = document.getElementById('searchInput');
  const suggs = document.getElementById('suggestions');

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    currentQuery = q;
    currentType  = document.getElementById('imageTypeFilter').value;
    currentCategory = document.getElementById('categoryFilter').value;
    currentPage  = 1;
    doSearch(q, 1);
    suggs.classList.remove('show');
  });

  input.addEventListener('input', () => {
    clearTimeout(suggestTimer);
    const val = input.value.trim();
    if (val.length < 2) { suggs.classList.remove('show'); return; }
    suggestTimer = setTimeout(() => fetchSuggestions(val), 300);
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-bar-wrap')) suggs.classList.remove('show');
  });
}

async function fetchSuggestions(q) {
  try {
    const res  = await fetch(`${API}/api/search/suggest?q=${encodeURIComponent(q)}&limit=6`);
    const data = await res.json();
    const suggs = document.getElementById('suggestions');

    if (!data.length) { suggs.classList.remove('show'); return; }

    suggs.innerHTML = data.map(s => `
      <div class="suggestion-item" onclick="selectSuggestion('${escHtml(s.keyword)}')">
        <span>${escHtml(s.keyword)}</span>
        <span class="suggestion-freq">×${s.frequency}</span>
      </div>
    `).join('');
    suggs.classList.add('show');
  } catch (e) { /* ignore */ }
}

function selectSuggestion(kw) {
  document.getElementById('searchInput').value = kw;
  document.getElementById('suggestions').classList.remove('show');
  document.getElementById('searchForm').dispatchEvent(new Event('submit'));
}

// ── Search Execution ───────────────────────────────────────────────────────────
async function doSearch(q, page) {
  document.getElementById('featuresSection').style.display = 'none';
  document.getElementById('resultsSection').style.display  = 'block';
  document.getElementById('emptyState').style.display      = 'none';
  document.getElementById('resultsGrid').innerHTML = '<div class="loading">Searching...</div>';

  const typeParam = currentType ? `&image_type=${currentType}` : '';
  const catParam  = currentCategory ? `&category=${currentCategory}` : '';
  const isSemantic = document.getElementById('semanticToggle')?.checked;
  const semanticParam = isSemantic ? `&semantic=true` : '';
  const url = `${API}/api/search/?q=${encodeURIComponent(q)}&page=${page}&page_size=12${typeParam}${catParam}${semanticParam}`;

  try {
    const res  = await fetch(url);
    const data = await res.json();

    // Update URL
    history.replaceState(null, '', `/?q=${encodeURIComponent(q)}`);

    document.getElementById('resultsTitle').textContent = `Results for "${q}"`;
    document.getElementById('resultCount').textContent  = `${data.total_results} found`;

    if (!data.results.length) {
      document.getElementById('resultsGrid').innerHTML = '';
      document.getElementById('emptyState').style.display = 'block';
      document.getElementById('pagination').innerHTML = '';
      return;
    }

    renderResults(data.results);
    renderPagination(data.total_results, data.page, data.page_size, q);
  } catch (e) {
    document.getElementById('resultsGrid').innerHTML = `<div class="loading">Error: ${e.message}</div>`;
  }
}

function renderResults(results) {
  const grid = document.getElementById('resultsGrid');
  grid.innerHTML = results.map(r => {
    const thumb    = r.thumbnail_path
      ? `/static/uploads/thumbnails/thumb_${r.filename}`
      : null;
    const snippet  = r.matched_snippets[0] || '';
    const typeLabel = r.image_type === 'born_digital' ? 'Born-Digital' : 'Scene Text';
    const typeClass = r.image_type === 'scene_text' ? 'scene' : '';
    const snipHtml  = snippet.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    return `
      <div class="image-card" onclick="window.location='/image/${r.id}'">
        <div class="card-thumb">
          ${thumb
            ? `<img src="${thumb}" alt="${escHtml(r.filename)}" loading="lazy" />`
            : '🖼️'
          }
        </div>
        <div class="card-body">
          <div class="card-title">${escHtml(r.filename)}</div>
          ${r.subject ? `<div class="card-summary" style="font-size:0.8rem; margin: 4px 0; font-style: italic;">"${escHtml(r.subject)}"</div>` : ''}
          ${snippet ? `<div class="card-snippet">${snipHtml}</div>` : ''}
          <div class="card-meta">
            <span class="card-type ${typeClass}">${typeLabel}</span>
            ${r.category ? `<span class="card-category">${escHtml(r.category)}</span>` : ''}
            ${r.is_duplicate ? `<span class="card-duplicate">Duplicate</span>` : ''}
            <span class="card-score">${r.relevance_score}% match</span>
          </div>
        </div>
      </div>`;
  }).join('');
}

function renderPagination(total, page, pageSize, q) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) { document.getElementById('pagination').innerHTML = ''; return; }

  const pag = document.getElementById('pagination');
  let html = '';
  if (page > 1) html += `<button class="page-btn" onclick="goPage(${page-1},'${escHtml(q)}')">← Prev</button>`;
  for (let i = 1; i <= totalPages; i++) {
    if (Math.abs(i - page) <= 2 || i === 1 || i === totalPages) {
      html += `<button class="page-btn ${i===page?'active':''}" onclick="goPage(${i},'${escHtml(q)}')">${i}</button>`;
    } else if (Math.abs(i - page) === 3) {
      html += `<span style="padding:0.5rem;color:var(--text-muted)">…</span>`;
    }
  }
  if (page < totalPages) html += `<button class="page-btn" onclick="goPage(${page+1},'${escHtml(q)}')">Next →</button>`;
  pag.innerHTML = html;
}

function goPage(page, q) {
  currentPage = page;
  doSearch(q, page);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
