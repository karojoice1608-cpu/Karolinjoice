/* Screendex — Admin Dashboard JS */

document.getElementById('extractBtn').addEventListener('click', loadBills);

async function loadBills() {
    const container = document.getElementById('billsContainer');
    container.innerHTML = '<div class="loading">Evaluating bounding boxes and extracting structured data...</div>';
    
    try {
        const res = await fetch('/api/admin/bills');
        if (!res.ok) throw new Error("Failed to load bills data");
        const data = await res.json();
        
        if (!data.bills || data.bills.length === 0) {
            container.innerHTML = '<div class="empty-state">No uploaded images found in the system.</div>';
            return;
        }
        
        let html = '';
        data.bills.forEach(bill => {
            html += `
            <div class="detail-section" style="margin-bottom: 2.5rem; border-left: 4px solid var(--primary);">
                <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <h3 style="margin-bottom: 0; font-size: 1.2rem;">📄 ${escHTML(bill.title)}</h3>
                    <span class="meta-badge category" style="background:var(--accent-glow);color:var(--accent);">Processed Elements: ${bill.items.length}</span>
                </div>
            `;
            
            if (bill.items.length === 0) {
                html += `<p style="color: var(--text-muted); font-size: 0.95rem;">No explicit product/price pairs matched on this image.</p>`;
            } else {
                html += `
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.95rem; border-radius: 8px; overflow: hidden; border: 1px solid var(--border);">
                        <thead>
                            <tr style="border-bottom: 2px solid var(--border); background: var(--surface2); text-align: left;">
                                <th style="padding: 12px 16px; width: 8%;">S.No</th>
                                <th style="padding: 12px 16px; width: 32%;">Title of the Image</th>
                                <th style="padding: 12px 16px; width: 45%;">Products</th>
                                <th style="padding: 12px 16px; width: 15%; text-align: right;">Price</th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                bill.items.forEach((item, idx) => {
                    const bg = idx % 2 === 0 ? "var(--surface)" : "var(--surface2)";
                    html += `
                            <tr style="border-bottom: 1px solid var(--border); background-color: ${bg};">
                                <td style="padding: 12px 16px; font-weight: 600; color: var(--text-muted);">${item.s_no}</td>
                                <td style="padding: 12px 16px; font-weight: 500;">${escHTML(bill.title)}</td>
                                <td style="padding: 12px 16px; color: var(--primary);"><strong>${escHTML(item.product)}</strong></td>
                                <td style="padding: 12px 16px; text-align: right; color: var(--success); font-weight: 700; font-family: monospace; font-size: 1.1rem;">${escHTML(item.price)}</td>
                            </tr>
                    `;
                });
                
                html += `
                        </tbody>
                    </table>
                </div>
                `;
            }
            
            html += `</div>`;
        });
        
        container.innerHTML = html;
        
    } catch(err) {
        container.innerHTML = `<div class="empty-state" style="color: var(--danger)"><h3>Load Failed</h3><p>${escHTML(err.message)}</p></div>`;
    }
}

function escHTML(str) {
    if(!str) return '';
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
