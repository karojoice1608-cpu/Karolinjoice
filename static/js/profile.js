
async function fetchStats() {
  try {
    const res = await fetch("/api/search/stats");
    if (!res.ok) throw new Error("Failed to fetch stats");
    const data = await res.json();
    
    document.getElementById("statTotal").textContent = data.total_images;
    document.getElementById("statKeywords").textContent = data.total_keywords;
    document.getElementById("statProcessed").textContent = data.processed_images;
    document.getElementById("statFailed").textContent = data.failed_images;

    // Build Progress Bar
    const limit = 500;
    const used = data.total_images;
    const pct = Math.min((used / limit) * 100, 100);
    document.getElementById("quotaUsed").textContent = used;
    setTimeout(() => {
        document.getElementById("quotaBar").style.width = pct + "%";
    }, 100);

    // Build Pie Chart
    const total = data.born_digital + data.scene_text || 1;
    const digitalPct = Math.round((data.born_digital / total) * 100);
    const scenePct = 100 - digitalPct;
    setTimeout(() => {
        document.getElementById("pieChart").style.background = `conic-gradient(var(--primary) 0% ${digitalPct}%, var(--accent) ${digitalPct}% 100%)`;
    }, 100);
    document.getElementById("labelDigital").textContent = `Born-Digital (${digitalPct}%)`;
    document.getElementById("labelScene").textContent = `Scene Text (${scenePct}%)`;

  } catch (err) {
    console.error("Error fetching stats:", err);
  }
}

async function fetchActivity() {
    try {
        const res = await fetch("/api/images/?page=1&page_size=5");
        if (!res.ok) throw new Error();
        const images = await res.json();
        
        const container = document.getElementById("timelineContainer");
        if (!images.length) {
            container.innerHTML = '<p style="color:var(--text-muted); font-size:0.9rem;">No recent activity tracked.</p>';
            return;
        }

        let html = '';
        images.forEach(img => {
            const date = new Date(img.uploaded_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            html += `
            <div style="display: flex; gap: 1rem; align-items: flex-start; position: relative;">
                <div style="width: 2px; height: 100%; background: var(--border); position: absolute; left: 5px; top: 15px; z-index: 0;"></div>
                <div style="width: 12px; height: 12px; border-radius: 50%; background: var(--success); margin-top: 4px; flex-shrink: 0; box-shadow: 0 0 0 4px rgba(76, 175, 80, 0.15); z-index: 1;"></div>
                <div style="z-index: 1; background: var(--surface); width: 100%;">
                    <div style="font-size: 0.95rem; font-weight: 700;">Uploaded <a href="/image/${img.id}">#${img.id}</a></div>
                    <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.1rem;">${escHTML(img.original_name)}</div>
                    <div style="font-size: 0.75rem; font-weight: 600; color: var(--primary); margin-top: 0.3rem;">${date}</div>
                </div>
            </div>
            `;
        });
        container.innerHTML = html;
    } catch(err) {
        document.getElementById("timelineContainer").innerHTML = '<p style="color:var(--danger); font-size:0.9rem;">Failed to load activity.</p>';
    }
}

function escHTML(str) {
    if(!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

document.addEventListener("DOMContentLoaded", () => {
    fetchStats();
    fetchActivity();
});
