/* Screendex — Image Detail Page JS */

const API = '';

document.addEventListener('DOMContentLoaded', () => loadDetail(IMAGE_ID));

async function loadDetail(id) {
  try {
    const res  = await fetch(`${API}/api/images/${id}`);
    if (!res.ok) { renderError(`Image #${id} not found`); return; }
    const img = await res.json();
    renderDetail(img);
  } catch (e) {
    renderError(`Failed to load: ${e.message}`);
  }
}

function renderDetail(img) {
  const typeLabel = img.image_type === 'born_digital' ? 'Born-Digital' : 'Scene Text';
  const typeClass = img.image_type === 'scene_text' ? 'scene' : '';
  const dateStr   = img.uploaded_at ? new Date(img.uploaded_at).toLocaleDateString() : 'Unknown';
  const imgUrl    = `/static/uploads/${img.filename}`;
  const fullText  = img.full_text || img.extracted_texts?.map(t => t.text_content).join(' ') || '';

  const html = `
    <div class="detail-header" style="grid-column:1/-1;margin-bottom:0.5rem;">
      <a href="/gallery" style="color:var(--text-muted);font-size:0.9rem;">← Gallery</a>
    </div>

    <!-- IMAGE + BBOX OVERLAY -->
    <div class="detail-image-wrap">
      <h1 style="font-size:1.2rem;font-weight:700;margin-bottom:0.75rem;">${esc(img.original_name)}</h1>
      <div class="detail-image-canvas" id="imageCanvas">
        <img src="${imgUrl}" alt="${esc(img.original_name)}"
             id="mainImage" onload="renderBboxes()" style="width:100%;border-radius:12px;" />
      </div>
      <div class="detail-meta" style="margin-top:0.75rem;">
        <span class="meta-badge card-type ${typeClass}">${typeLabel}</span>
        <span class="meta-badge">${img.status}</span>
        <span class="meta-badge">${img.width || '?'}×${img.height || '?'}px</span>
        <span class="meta-badge">📅 ${dateStr}</span>
        ${img.category ? `<span class="meta-badge category" style="background:var(--accent-glow);color:var(--accent);">🏷️ ${esc(img.category)} (${(img.category_conf*100).toFixed(0)}%)</span>` : ''}
        ${img.is_duplicate ? `<span class="meta-badge duplicate" style="background:#FFEBEE;color:#D32F2F;">⚠️ Duplicate of #${img.original_id}</span>` : ''}
      </div>
      ${img.subject ? `
      <div class="detail-ai-summary" style="margin-top: 1rem; padding: 1rem; background: var(--surface-2); border-left: 4px solid var(--accent); border-radius: 4px;">
        <h4 style="margin: 0 0 0.5rem 0; font-size: 0.9rem; color: var(--accent);">🤖 AI Summary (${(img.subject_conf*100).toFixed(0)}%)</h4>
        <p style="margin: 0; font-size: 0.95rem; line-height: 1.4;">${esc(img.subject)}</p>
      </div>` : ''}
      <div class="detail-actions" style="margin-top:1rem;">
        <a href="${imgUrl}" target="_blank" class="btn-outline" style="font-size:0.85rem;">View Full Image</a>
        <button class="btn-outline" style="font-size:0.85rem;" onclick="reprocess(${img.id})">🔄 Reprocess</button>
        <button class="btn-danger" onclick="deleteImg(${img.id})">🗑 Delete</button>
      </div>
    </div>

    <!-- INFO PANEL -->
    <div class="detail-info">
      <!-- FULL TEXT -->
      <div class="detail-section">
        <h3>📄 Extracted Text (${img.extracted_texts?.length || 0} regions)</h3>
        ${img.extracted_texts?.length
          ? img.extracted_texts.map((t, i) => `
            <div class="text-region" onclick="highlightRegion(${i})">
              <div>${esc(t.text_content)}</div>
              <div class="text-region-meta">Confidence: ${(t.confidence * 100).toFixed(1)}%</div>
            </div>`).join('')
          : '<p style="color:var(--text-muted);font-size:0.9rem;">No text extracted yet.</p>'
        }
      </div>

      <!-- KEYWORDS -->
      <div class="detail-section">
        <h3>🔑 Indexed Keywords (${img.keywords?.length || 0})</h3>
        <div class="keyword-cloud">
          ${img.keywords?.length
            ? img.keywords
                .filter(k => !k.is_stopword)
                .sort((a, b) => b.frequency - a.frequency)
                .slice(0, 50)
                .map(k => `
                  <span class="keyword-chip" onclick="searchKeyword('${esc(k.keyword)}')"
                        title="Frequency: ${k.frequency}">
                    ${esc(k.keyword)}
                    <span style="font-size:0.65rem;opacity:0.7"> ×${k.frequency}</span>
                  </span>`).join('')
            : '<p style="color:var(--text-muted);font-size:0.9rem;">No keywords yet.</p>'
          }
        </div>
      </div>

      <!-- FULL TEXT BOX -->
      ${fullText ? `
        <div class="detail-section">
          <h3>📋 Full Extracted Text</h3>
          <div class="full-text-box">${esc(fullText)}</div>
        </div>` : ''
      }
    </div>
  `;

  document.getElementById('detailContainer').innerHTML = html;

  // Store extracted texts for bbox rendering
  window._texts  = img.extracted_texts || [];
  window._imgObj = img;
}

// ── Bounding Box Overlay ───────────────────────────────────────────────────────
function renderBboxes() {
  const imgEl  = document.getElementById('mainImage');
  const canvas = document.getElementById('imageCanvas');
  const texts  = window._texts || [];

  // Remove old overlays
  canvas.querySelectorAll('.bbox-overlay').forEach(el => el.remove());

  const W = imgEl.naturalWidth  || 1;
  const H = imgEl.naturalHeight || 1;
  const rW = imgEl.offsetWidth  / W;
  const rH = imgEl.offsetHeight / H;

  texts.forEach((t, idx) => {
    if (!t.bbox_x && !t.bbox_y) return;

    const el = document.createElement('div');
    el.className = 'bbox-overlay';
    el.id = `bbox-${idx}`;
    el.style.left   = `${t.bbox_x   * 100}%`;
    el.style.top    = `${t.bbox_y   * 100}%`;
    el.style.width  = `${t.bbox_width  * 100}%`;
    el.style.height = `${t.bbox_height * 100}%`;
    el.title = `${t.text_content} (${(t.confidence*100).toFixed(0)}%)`;
    el.addEventListener('click', () => highlightRegion(idx));
    canvas.appendChild(el);
  });
}

function highlightRegion(idx) {
  document.querySelectorAll('.bbox-overlay').forEach(el => el.style.background = 'rgba(108,99,255,0.1)');
  const el = document.getElementById(`bbox-${idx}`);
  if (el) el.style.background = 'rgba(108,99,255,0.4)';
}

function searchKeyword(kw) {
  window.location = `/?q=${encodeURIComponent(kw)}`;
}

async function reprocess(id) {
  try {
    await fetch(`/api/images/${id}/reprocess`, { method: 'POST' });
    showToast('Reprocessing started…', 'info');
    setTimeout(() => loadDetail(id), 3000);
  } catch (e) { showToast('Reprocess failed', 'error'); }
}

async function deleteImg(id) {
  if (!confirm('Delete this image and all its data?')) return;
  try {
    const res = await fetch(`/api/images/${id}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Delete failed');
    }
    window.location = '/gallery';
  } catch (e) { showToast(e.message || 'Delete failed', 'error'); }
}

function renderError(msg) {
  document.getElementById('detailContainer').innerHTML =
    `<div style="text-align:center;padding:4rem;color:var(--text-muted)">
       <div style="font-size:3rem;">⚠️</div>
       <h3>${msg}</h3>
       <a href="/gallery" class="btn-primary" style="margin-top:1rem;display:inline-block;">← Back to Gallery</a>
     </div>`;
}

function esc(str) { return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}
