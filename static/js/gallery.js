/* Screendex — Gallery Page JS */

const API = '';
let currentPage = 1;

document.addEventListener('DOMContentLoaded', () => {
  loadStats();
  loadGallery(1);

  document.getElementById('statusFilter').addEventListener('change', () => loadGallery(1));
  document.getElementById('typeFilter').addEventListener('change',   () => loadGallery(1));
  document.getElementById('categoryFilter').addEventListener('change', () => loadGallery(1));
});

async function loadStats() {
  try {
    const res  = await fetch(`${API}/api/search/stats`);
    const data = await res.json();
    document.getElementById('galleryStats').innerHTML = `
      <div class="gallery-stat">📊 <strong>${data.total_images}</strong> Total Images</div>
      <div class="gallery-stat">✅ <strong>${data.processed_images}</strong> Indexed</div>
      <div class="gallery-stat">📱 <strong>${data.born_digital}</strong> Born-Digital</div>
      <div class="gallery-stat">📸 <strong>${data.scene_text}</strong> Scene Text</div>
      <div class="gallery-stat">🔑 <strong>${data.total_keywords}</strong> Keywords</div>
    `;
  } catch (e) { /* ignore */ }
}

async function loadGallery(page) {
  currentPage = page;
  const status = document.getElementById('statusFilter').value;
  const type   = document.getElementById('typeFilter').value;
  const category = document.getElementById('categoryFilter').value;

  let url = `${API}/api/images/?page=${page}&page_size=12`;
  if (status) url += `&status=${status}`;
  if (type)   url += `&image_type=${type}`;
  if (category) url += `&category=${category}`;

  document.getElementById('galleryGrid').innerHTML = '<div class="loading">Loading...</div>';

  try {
    const res    = await fetch(url);
    const images = await res.json();

    if (!images.length) {
      document.getElementById('galleryGrid').innerHTML = `
        <div style="grid-column:1/-1;text-align:center;padding:3rem;color:var(--text-muted)">
          No images found. <a href="/upload">Upload some images</a> to get started.
        </div>`;
      document.getElementById('pagination').innerHTML = '';
      return;
    }

    renderGallery(images);
    // Simple next page button (no total from this endpoint — refactor if needed)
    document.getElementById('pagination').innerHTML = images.length === 12
      ? `<button class="page-btn" onclick="loadGallery(${page - 1})" ${page === 1 ? 'disabled' : ''}>← Prev</button>
         <button class="page-btn" onclick="loadGallery(${page + 1})">Next →</button>`
      : page > 1
        ? `<button class="page-btn" onclick="loadGallery(${page - 1})">← Prev</button>`
        : '';
  } catch (e) {
    document.getElementById('galleryGrid').innerHTML = `<div class="loading">Error: ${e.message}</div>`;
  }
}

function renderGallery(images) {
  const grid = document.getElementById('galleryGrid');
  grid.innerHTML = images.map(img => {
    const thumb = img.thumbnail_path
      ? `/static/uploads/thumbnails/thumb_${img.filename}`
      : null;
    const typeLabel = img.image_type === 'born_digital' ? 'Born-Digital' : 'Scene Text';
    const typeClass = img.image_type === 'scene_text' ? 'scene' : '';
    const keyCount  = img.keywords?.length || 0;
    const textCount = img.extracted_texts?.length || 0;

    return `
      <div class="image-card" onclick="window.location='/image/${img.id}'">
        <div class="status-badge status-${img.status}">${img.status}</div>
        <div class="card-thumb">
          ${thumb && img.status === 'completed'
            ? `<img src="${thumb}" alt="${esc(img.original_name)}" loading="lazy" />`
            : `<span style="font-size:3rem;">🖼️</span>`
          }
        </div>
        <div class="card-body">
          <div class="card-title">${esc(img.original_name)}</div>
          ${img.subject ? `<div class="card-summary" style="font-size:0.8rem; margin: 4px 0; font-style: italic;">"${esc(img.subject)}"</div>` : ''}
          <div class="card-snippet" style="font-size:0.75rem;color:var(--text-muted)">
            ${textCount} text regions · ${keyCount} keywords
          </div>
          <div class="card-meta">
            <span class="card-type ${typeClass}">${typeLabel}</span>
            ${img.category ? `<span class="card-category">${esc(img.category)}</span>` : ''}
            ${img.is_duplicate ? `<span class="card-duplicate">Duplicate</span>` : ''}
            <button class="btn-danger" style="font-size:0.7rem;padding:2px 8px;"
              onclick="deleteImage(event, ${img.id})">Delete</button>
          </div>
        </div>
      </div>`;
  }).join('');
}

async function deleteImage(e, id) {
  e.stopPropagation();
  if (!confirm('Delete this image and all its indexed data?')) return;
  try {
    const res = await fetch(`${API}/api/images/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Delete failed');
    }
    showToast('Image deleted', 'success');
    loadGallery(currentPage);
    loadStats();
  } catch (err) {
    showToast(err.message || 'Delete failed', 'error');
  }
}

function esc(str) { return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}
