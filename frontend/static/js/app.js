/* ─── Screendex Frontend App ───────────────────────────────────────────────
   Pure vanilla JS — no framework dependencies.
   Communicates with the FastAPI backend via fetch().
────────────────────────────────────────────────────────────────────────── */

const API = '';  // Same-origin — no base URL needed

// ─── View navigation ──────────────────────────────────────────────────────

const views = document.querySelectorAll('.view');
const navBtns = document.querySelectorAll('.nav-btn');

navBtns.forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.dataset.view;
    views.forEach(v => v.classList.toggle('active', v.id === `view-${target}`));
    navBtns.forEach(b => b.classList.toggle('active', b === btn));
    if (target === 'library') loadLibrary();
  });
});

// ─── Stats pill ───────────────────────────────────────────────────────────

async function loadStats() {
  try {
    const res = await fetch(`${API}/api/search/stats`);
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('statsIndexed').textContent = data.indexed.toLocaleString();
  } catch (_) {}
}

loadStats();
setInterval(loadStats, 15_000);

// ─── Search ───────────────────────────────────────────────────────────────

const searchInput  = document.getElementById('searchInput');
const searchBtn    = document.getElementById('searchBtn');
const suggestBox   = document.getElementById('suggestBox');
const resultsSection = document.getElementById('resultsSection');
const resultsMeta  = document.getElementById('resultsMeta');
const resultsGrid  = document.getElementById('resultsGrid');

let suggestTimeout = null;

searchInput.addEventListener('input', () => {
  clearTimeout(suggestTimeout);
  const q = searchInput.value.trim();
  if (q.length < 2) { suggestBox.style.display = 'none'; return; }
  suggestTimeout = setTimeout(() => fetchSuggestions(q), 200);
});

searchInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') runSearch();
  if (e.key === 'Escape') { suggestBox.style.display = 'none'; }
});

searchBtn.addEventListener('click', runSearch);

document.addEventListener('click', e => {
  if (!suggestBox.contains(e.target) && e.target !== searchInput) {
    suggestBox.style.display = 'none';
  }
});

async function fetchSuggestions(q) {
  try {
    const res = await fetch(`${API}/api/search/suggest?q=${encodeURIComponent(q)}&limit=8`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.suggestions.length) { suggestBox.style.display = 'none'; return; }
    suggestBox.innerHTML = data.suggestions
      .map(s => `<div class="suggest-item">${escHtml(s)}</div>`)
      .join('');
    suggestBox.querySelectorAll('.suggest-item').forEach(item => {
      item.addEventListener('click', () => {
        searchInput.value = item.textContent;
        suggestBox.style.display = 'none';
        runSearch();
      });
    });
    suggestBox.style.display = 'block';
  } catch (_) {}
}

async function runSearch() {
  const q = searchInput.value.trim();
  if (!q) return;
  suggestBox.style.display = 'none';

  const mode = document.getElementById('searchMode').value;
  const type = document.getElementById('searchType').value;
  const conf = document.getElementById('searchConf').value;

  resultsSection.style.display = 'block';
  resultsMeta.textContent = '';
  resultsGrid.innerHTML = '<div class="spinner"></div>';

  const params = new URLSearchParams({ q, mode, limit: 30 });
  if (type) params.append('image_type', type);
  if (conf) params.append('confidence_min', conf);

  try {
    const t0 = performance.now();
    const res = await fetch(`${API}/api/search/?${params}`);
    const ms = Math.round(performance.now() - t0);

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    resultsMeta.textContent =
      `${data.result_count} result${data.result_count !== 1 ? 's' : ''} · ${ms}ms · mode: ${mode}`;

    if (!data.results.length) {
      resultsGrid.innerHTML = `
        <div class="empty" style="grid-column:1/-1">
          <div class="empty-icon">🔍</div>
          <p>No images found for "<strong>${escHtml(q)}</strong>".<br/>
          Try a different keyword or check that images have been uploaded and indexed.</p>
        </div>`;
      return;
    }

    resultsGrid.innerHTML = data.results.map(r => buildResultCard(r, q)).join('');
    resultsGrid.querySelectorAll('.result-card').forEach(card => {
      card.addEventListener('click', () => openModal(card.dataset.imageId));
    });
  } catch (err) {
    resultsGrid.innerHTML = `<p style="color:var(--red);font-family:var(--mono);font-size:0.82rem;">Search failed: ${escHtml(err.message)}</p>`;
  }
}

function buildResultCard(r, query) {
  const score     = Math.round(r.final_score * 100);
  const conf      = Math.round((r.avg_confidence || 0) * 100);
  const typeLabel = r.image_type === 'born_digital' ? 'Born-Digital'
                  : r.image_type === 'scene_text'   ? 'Scene Text'
                  : r.image_type || 'Unknown';

  const snippetText = (r.matched_regions.length
    ? r.matched_regions.map(rg => rg.text).join(' … ')
    : r.full_text
  ).slice(0, 240);

  const highlightedSnippet = highlightQuery(escHtml(snippetText), query);

  return `
    <div class="result-card" data-image-id="${r.image_id}">
      <img class="result-thumb"
           src="${API}/api/images/${r.image_id}/file"
           alt="${escHtml(r.original_filename)}"
           loading="lazy"
           onerror="this.outerHTML='<div class=\\'result-thumb-placeholder\\'>No preview</div>'" />
      <div class="result-body">
        <div class="result-filename">${escHtml(r.original_filename)}</div>
        <div class="result-text">${highlightedSnippet}</div>
        <div class="result-footer">
          <span class="badge badge-score">Score ${score}%</span>
          <span class="badge badge-conf">Conf ${conf}%</span>
          <span class="badge badge-type">${typeLabel}</span>
          ${r.region_count ? `<span class="badge badge-regions">${r.region_count} regions</span>` : ''}
        </div>
      </div>
    </div>`;
}

function highlightQuery(html, query) {
  const terms = query.trim().split(/\s+/).filter(Boolean);
  let result = html;
  terms.forEach(term => {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    result = result.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>');
  });
  return result;
}

// ─── Library ──────────────────────────────────────────────────────────────

const libGrid   = document.getElementById('libGrid');
const libPagination = document.getElementById('libPagination');
let libPage = 1;

document.getElementById('libRefreshBtn').addEventListener('click', () => {
  libPage = 1;
  loadLibrary();
});
document.getElementById('libStatusFilter').addEventListener('change', () => { libPage = 1; loadLibrary(); });
document.getElementById('libTypeFilter').addEventListener('change',  () => { libPage = 1; loadLibrary(); });

async function loadLibrary() {
  libGrid.innerHTML = '<div class="spinner"></div>';
  const status = document.getElementById('libStatusFilter').value;
  const type   = document.getElementById('libTypeFilter').value;
  const params = new URLSearchParams({ page: libPage, page_size: 24 });
  if (status) params.append('status', status);
  if (type)   params.append('image_type', type);

  try {
    const res  = await fetch(`${API}/api/images/?${params}`);
    const data = await res.json();

    if (!data.images.length) {
      libGrid.innerHTML = `
        <div class="empty" style="grid-column:1/-1">
          <div class="empty-icon">🖼️</div>
          <p>No images found. Upload some images to get started.</p>
        </div>`;
      libPagination.innerHTML = '';
      return;
    }

    libGrid.innerHTML = data.images.map(img => `
      <div class="lib-card" data-image-id="${img.image_id}">
        <img class="lib-thumb"
             src="${API}/api/images/${img.image_id}/file"
             alt="${escHtml(img.original_filename)}"
             loading="lazy"
             onerror="this.outerHTML='<div class=\\'lib-thumb-ph\\'>No preview</div>'" />
        <div class="lib-info">
          <div class="lib-name">${escHtml(img.original_filename)}</div>
          <span class="lib-status status-${img.status}">${img.status}</span>
        </div>
      </div>
    `).join('');

    libGrid.querySelectorAll('.lib-card').forEach(card => {
      card.addEventListener('click', () => openModal(card.dataset.imageId));
    });

    // Simple prev/next pagination
    libPagination.innerHTML = `
      ${libPage > 1 ? `<button class="page-btn" id="libPrev">&#8592;</button>` : ''}
      <button class="page-btn active">${libPage}</button>
      ${data.images.length === 24 ? `<button class="page-btn" id="libNext">&#8594;</button>` : ''}
    `;
    document.getElementById('libPrev')?.addEventListener('click', () => { libPage--; loadLibrary(); });
    document.getElementById('libNext')?.addEventListener('click', () => { libPage++; loadLibrary(); });

  } catch (err) {
    libGrid.innerHTML = `<p style="color:var(--red)">Failed to load library: ${escHtml(err.message)}</p>`;
  }
}

// ─── Upload ───────────────────────────────────────────────────────────────

const dropzone       = document.getElementById('dropzone');
const browseBtn      = document.getElementById('browseBtn');
const fileInput      = document.getElementById('fileInput');
const uploadQueue    = document.getElementById('uploadQueue');
const uploadActions  = document.getElementById('uploadActions');
const uploadSubmitBtn= document.getElementById('uploadSubmitBtn');
const uploadClearBtn = document.getElementById('uploadClearBtn');
const uploadLog      = document.getElementById('uploadLog');

let queuedFiles = [];

browseBtn.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('click', e => { if (e.target === dropzone || e.target.closest('.drop-inner')) fileInput.click(); });

fileInput.addEventListener('change', () => {
  addToQueue([...fileInput.files]);
  fileInput.value = '';
});

dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('drag-over'); });
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('drag-over');
  addToQueue([...e.dataTransfer.files]);
});

function addToQueue(files) {
  const imageFiles = files.filter(f => f.type.startsWith('image/'));
  queuedFiles = [...queuedFiles, ...imageFiles].slice(0, 50);
  renderQueue();
}

function renderQueue() {
  uploadQueue.innerHTML = queuedFiles.map((f, i) => `
    <div class="queue-item">
      <img class="queue-thumb" src="${URL.createObjectURL(f)}" alt="${escHtml(f.name)}" />
      <div class="queue-name">${escHtml(f.name)}</div>
      <button class="queue-remove" data-idx="${i}">&times;</button>
    </div>
  `).join('');

  uploadQueue.querySelectorAll('.queue-remove').forEach(btn => {
    btn.addEventListener('click', () => {
      queuedFiles.splice(parseInt(btn.dataset.idx), 1);
      renderQueue();
    });
  });

  uploadActions.style.display = queuedFiles.length ? 'flex' : 'none';
}

uploadClearBtn.addEventListener('click', () => {
  queuedFiles = [];
  renderQueue();
  uploadLog.innerHTML = '';
});

uploadSubmitBtn.addEventListener('click', async () => {
  if (!queuedFiles.length) return;
  uploadSubmitBtn.disabled = true;
  uploadSubmitBtn.textContent = 'Uploading…';
  uploadLog.innerHTML = '';

  const formData = new FormData();
  queuedFiles.forEach(f => formData.append('files', f));

  try {
    const res = await fetch(`${API}/api/images/upload`, {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

    addLog(`✓ ${data.uploaded} image${data.uploaded !== 1 ? 's' : ''} uploaded and queued for indexing.`, 'success');
    data.images.forEach(img => {
      addLog(`  • ${img.original_filename} — ID: ${img.image_id}`, 'info');
    });

    queuedFiles = [];
    renderQueue();
    loadStats();
  } catch (err) {
    addLog(`✗ Upload failed: ${err.message}`, 'error');
  } finally {
    uploadSubmitBtn.disabled = false;
    uploadSubmitBtn.textContent = 'Upload & Index';
  }
});

function addLog(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `log-entry ${type}`;
  el.textContent = msg;
  uploadLog.appendChild(el);
}

// ─── Modal ────────────────────────────────────────────────────────────────

const modalOverlay = document.getElementById('modalOverlay');
const modalBody    = document.getElementById('modalBody');
const modalClose   = document.getElementById('modalClose');

modalClose.addEventListener('click', closeModal);
modalOverlay.addEventListener('click', e => { if (e.target === modalOverlay) closeModal(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

function closeModal() {
  modalOverlay.style.display = 'none';
  modalBody.innerHTML = '';
}

async function openModal(imageId) {
  modalOverlay.style.display = 'flex';
  modalBody.innerHTML = '<div class="spinner"></div>';

  try {
    const [imgRes, regRes] = await Promise.all([
      fetch(`${API}/api/images/${imageId}`),
      fetch(`${API}/api/images/${imageId}/regions`),
    ]);
    const img = await imgRes.json();
    const reg = await regRes.json();

    const typeLabel = img.image_type === 'born_digital' ? 'Born-Digital'
                    : img.image_type === 'scene_text'   ? 'Scene Text'
                    : img.image_type || '—';

    const keywords = (img.keywords || []).map(k => `<span class="kw-chip">${escHtml(k)}</span>`).join('');
    const regionsHtml = reg.regions.slice(0, 20).map(r => `
      <div style="margin-bottom:0.5rem;padding:0.5rem 0.7rem;background:var(--surface2);border-radius:6px">
        <span style="font-size:0.68rem;font-family:var(--mono);color:var(--muted)">
          Conf: ${Math.round(r.confidence * 100)}% · ${r.ocr_engine} · bbox(${r.bbox.x},${r.bbox.y})
        </span>
        <div style="font-size:0.85rem;margin-top:0.2rem">${escHtml(r.cleaned_text || r.raw_text)}</div>
      </div>
    `).join('');

    modalBody.innerHTML = `
      <div class="modal-image-wrap" style="margin-top:0.5rem">
        <img src="${API}/api/images/${imageId}/file" alt="${escHtml(img.original_filename)}"
             onerror="this.outerHTML='<p style=\\'color:var(--muted)\\'>Image file unavailable</p>'" />
      </div>

      <div class="modal-meta">
        <h3>${escHtml(img.original_filename)}</h3>
        <div class="meta-grid">
          <div class="meta-item">
            <div class="meta-label">Status</div>
            <div class="meta-value"><span class="lib-status status-${img.status}">${img.status}</span></div>
          </div>
          <div class="meta-item">
            <div class="meta-label">Type</div>
            <div class="meta-value">${typeLabel}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">OCR Confidence</div>
            <div class="meta-value">${img.avg_confidence != null ? Math.round(img.avg_confidence * 100) + '%' : '—'}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">Text Regions</div>
            <div class="meta-value">${img.region_count ?? '—'}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">OCR Engine</div>
            <div class="meta-value" style="font-family:var(--mono);font-size:0.82rem">${img.ocr_engine_used || '—'}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">Dimensions</div>
            <div class="meta-value">${img.width_px && img.height_px ? `${img.width_px} × ${img.height_px}` : '—'}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">Uploaded</div>
            <div class="meta-value" style="font-size:0.82rem">${img.uploaded_at ? new Date(img.uploaded_at).toLocaleString() : '—'}</div>
          </div>
          <div class="meta-item">
            <div class="meta-label">File size</div>
            <div class="meta-value">${img.file_size_bytes ? formatBytes(img.file_size_bytes) : '—'}</div>
          </div>
        </div>
      </div>

      ${keywords ? `<div class="modal-text"><h4>Keywords</h4><div class="keywords-wrap">${keywords}</div></div>` : ''}

      ${img.full_text ? `
        <div class="modal-text">
          <h4>Extracted Text</h4>
          <div class="modal-fulltext">${escHtml(img.full_text)}</div>
        </div>` : ''}

      ${reg.regions.length ? `
        <div class="modal-text">
          <h4>Text Regions (${reg.region_count}${reg.region_count > 20 ? ', showing first 20' : ''})</h4>
          ${regionsHtml}
        </div>` : ''}

      ${img.error_message ? `
        <div style="margin-top:1rem;padding:0.75rem 1rem;border:1px solid var(--red);border-radius:8px;color:var(--red);font-family:var(--mono);font-size:0.78rem">
          Error: ${escHtml(img.error_message)}
        </div>` : ''}
    `;
  } catch (err) {
    modalBody.innerHTML = `<p style="color:var(--red);padding:2rem;font-family:var(--mono)">Failed to load: ${escHtml(err.message)}</p>`;
  }
}

// ─── Utilities ────────────────────────────────────────────────────────────

function escHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatBytes(bytes) {
  if (bytes < 1024)       return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}
