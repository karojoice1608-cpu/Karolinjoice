/* Screendex — Upload Page JS */

const API = '';
let selectedFiles = [];

document.addEventListener('DOMContentLoaded', () => {
  setupDropZone();
  document.getElementById('fileInput').addEventListener('change', (e) => addFiles(e.target.files));
  document.getElementById('uploadBtn').addEventListener('click', startUpload);
  document.getElementById('clearBtn').addEventListener('click', clearFiles);
});

// ── Drop Zone ──────────────────────────────────────────────────────────────────
function setupDropZone() {
  const zone = document.getElementById('dropZone');
  zone.addEventListener('click', (e) => {
    if (!e.target.closest('button')) document.getElementById('fileInput').click();
  });
  zone.addEventListener('dragover',  (e) => { e.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', ()  => zone.classList.remove('drag-over'));
  zone.addEventListener('drop',      (e) => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
  });
}

function addFiles(fileList) {
  const allowed = ['image/jpeg','image/png','image/gif','image/bmp','image/tiff','image/webp'];
  for (const file of fileList) {
    if (!allowed.includes(file.type)) { showToast(`Skipped: ${file.name} (unsupported type)`, 'error'); continue; }
    if (file.size > 10 * 1024 * 1024)  { showToast(`Skipped: ${file.name} (over 10MB)`, 'error'); continue; }
    if (!selectedFiles.find(f => f.name === file.name)) selectedFiles.push(file);
  }
  renderPreviews();
}

function renderPreviews() {
  const grid = document.getElementById('previewGrid');
  grid.innerHTML = selectedFiles.map((file, idx) => {
    const url = URL.createObjectURL(file);
    return `
      <div class="preview-item" id="prev-${idx}">
        <img src="${url}" alt="${esc(file.name)}" />
        <button class="preview-remove" onclick="removeFile(${idx})" title="Remove">×</button>
        <div class="preview-name">${esc(file.name)}</div>
      </div>`;
  }).join('');

  const count = selectedFiles.length;
  document.getElementById('uploadActions').style.display = count ? 'flex' : 'none';
  document.getElementById('selectedCount').textContent = `${count} file${count !== 1 ? 's' : ''} selected`;
}

function removeFile(idx) {
  selectedFiles.splice(idx, 1);
  renderPreviews();
}

function clearFiles() {
  selectedFiles = [];
  renderPreviews();
  document.getElementById('progressSection').style.display = 'none';
}

// ── Upload & Poll ──────────────────────────────────────────────────────────────
async function startUpload() {
  if (!selectedFiles.length) return;

  document.getElementById('uploadBtn').disabled    = true;
  document.getElementById('progressSection').style.display = 'block';
  document.getElementById('uploadResults').innerHTML = '';

  const imageType = document.querySelector('input[name="imageType"]:checked').value;

  setStep('upload', 'active');

  const uploadedIds = [];

  for (const file of selectedFiles) {
    const fd = new FormData();
    fd.append('file', file);
    if (imageType !== 'auto') {
        fd.append('image_type', imageType);
    }

    try {
      const res  = await fetch(`${API}/api/images/upload`, { method: 'POST', body: fd });
      const data = await res.json();

      if (res.ok) {
        uploadedIds.push({ id: data.id, name: file.name });
        addResult(file.name, 'uploading', '📤 Uploaded, OCR starting…');
      } else {
        addResult(file.name, 'error', `❌ ${data.detail || 'Upload failed'}`);
      }
    } catch (e) {
      addResult(file.name, 'error', `❌ Network error: ${e.message}`);
    }
  }

  setStep('upload', 'done');
  setStep('ocr',    'active');

  // Poll processing status
  await pollStatus(uploadedIds);
}

async function pollStatus(items) {
  const completed = new Set();
  let attempts = 0;
  const maxAttempts = 120; // up to ~2 minutes

  while (completed.size < items.length && attempts < maxAttempts) {
    await sleep(1500);
    attempts++;

    for (const item of items) {
      if (completed.has(item.id)) continue;

      try {
        const res  = await fetch(`${API}/api/images/${item.id}/status`);
        const data = await res.json();

        if (data.status === 'completed') {
          completed.add(item.id);
          let msg = `✅ Done — ${data.text_regions} regions, ${data.keywords_count} keywords`;
          if (data.category) msg += ` | 🏷️ ${data.category}`;
          if (data.is_duplicate) msg += ` | ⚠️ DUPLICATE`;
          updateResult(item.name, 'done', msg);
        } else if (data.status === 'failed') {
          completed.add(item.id);
          updateResult(item.name, 'error', `❌ Failed: ${data.error_message || 'Unknown error'}`);
        } else {
          updateResult(item.name, 'processing', `🔄 ${data.status}…`);
        }
      } catch (e) { /* ignore poll errors */ }
    }

    // Update pipeline steps based on progress
    const doneCount = completed.size;
    if (doneCount > 0) {
      setStep('ocr', 'done');
      setStep('nlp', doneCount === items.length ? 'done' : 'active');
      if (doneCount === items.length) setStep('index', 'done');
    }
  }

  document.getElementById('uploadBtn').disabled = false;
  if (items.length > 0) {
    showToast(`Processing complete! View in <a href="/gallery">Gallery</a>`, 'success');
  }
}

// ── Pipeline Steps ─────────────────────────────────────────────────────────────
function setStep(name, state) {
  const el = document.querySelector(`[data-step="${name}"]`);
  if (!el) return;
  el.className = `step ${state}`;
  el.querySelector('.step-status').textContent = state === 'done' ? '✅' : state === 'active' ? '🔄' : '⏳';
}

// ── Result Items ───────────────────────────────────────────────────────────────
function addResult(name, type, msg) {
  const div = document.createElement('div');
  div.className = 'upload-result-item';
  div.id = `res-${slugify(name)}`;
  div.innerHTML = `<span class="result-status-icon">📄</span><span class="result-name">${esc(name)}</span><span class="result-msg">${msg}</span>`;
  document.getElementById('uploadResults').appendChild(div);
}

function updateResult(name, type, msg) {
  const el = document.getElementById(`res-${slugify(name)}`);
  if (el) el.querySelector('.result-msg').textContent = msg;
}

// ── Utils ──────────────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function slugify(s) { return s.replace(/[^a-z0-9]/gi, '_'); }
function esc(str) { return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function showToast(msg, type = 'info') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4000);
}
