/**
 * Balance Sheet page logic
 * Handles Schedule AL, Personal summary, and Business balance sheets
 */

// Global export function (needs to be outside IIFE for onclick)
async function exportBS(bsId, format) {
    try {
        if (format === 'pdf') {
            await API.export.downloadWithAuth(API.export.balanceSheetPDF(bsId));
        } else {
            const data = await API.export.balanceSheetJSON(bsId);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `BalanceSheet_${bsId}.json`;
            a.click();
            URL.revokeObjectURL(a.href);
        }
    } catch (e) { alert('Export failed: ' + e.message); }
}

(function () {
    'use strict';

    // Auth guard - CA users redirect to CA dashboard
    const token = localStorage.getItem('authToken');
    if (!token) { window.location.href = 'login.html'; return; }

    let userData = {};
    try {
        userData = JSON.parse(localStorage.getItem('userData') || '{}') || {};
    } catch {
        userData = {};
    }
    const role = String(userData.role || '').toLowerCase();
    if (role === 'auditor' || role === 'admin') {
        window.location.href = 'ca-review.html';
        return;
    }

    // State
    let currentBsId = null;   // active balance sheet being viewed
    let editingItemId = null;  // item being edited in modal

    // ---- Tab switching ----
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        });
    });

    // ---- Helpers ----
    const fmt = n => '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const normalizeType = (v) => {
        const raw = String(v || '').toLowerCase();
        if (raw.includes('asset')) return 'asset';
        if (raw.includes('liability')) return 'liability';
        if (raw.includes('equity')) return 'equity';
        return raw;
    };

    function renderSummaryCards(container, assets, liabilities, equity) {
        const net = assets - liabilities;
        container.innerHTML = `
            <div class="bs-summary">
                <div class="bs-summary-card"><div class="label">Total Assets</div><div class="value positive">${fmt(assets)}</div></div>
                <div class="bs-summary-card"><div class="label">Total Liabilities</div><div class="value negative">${fmt(liabilities)}</div></div>
                ${equity ? `<div class="bs-summary-card"><div class="label">Total Equity</div><div class="value neutral">${fmt(equity)}</div></div>` : ''}
                <div class="bs-summary-card"><div class="label">Net Worth</div><div class="value ${net >= 0 ? 'positive' : 'negative'}">${fmt(net)}</div></div>
            </div>`;
    }

    function renderItemsTable(items, showEquity = false) {
        const assets = items.filter(i => normalizeType(i.item_type) === 'asset');
        const liabilities = items.filter(i => normalizeType(i.item_type) === 'liability');
        const equities = items.filter(i => normalizeType(i.item_type) === 'equity');

        let html = '';

        const renderSection = (title, list) => {
            if (!list.length && title === 'Equity' && !showEquity) return '';
            const total = list.reduce((s, i) => s + Number(i.amount || 0), 0);
            let h = `<h4 style="margin:16px 0 8px">${title}</h4>`;
            h += `<table class="items-table"><thead><tr>
                <th>Category</th><th>Subcategory</th><th>Description</th><th class="amount">Amount</th><th class="actions"></th>
            </tr></thead><tbody>`;
            list.forEach(i => {
                h += `<tr>
                    <td>${i.category}</td>
                    <td>${i.subcategory || '-'}</td>
                    <td>${i.description || '-'}</td>
                    <td class="amount">${fmt(i.amount)}</td>
                    <td class="actions">
                        <button class="btn-icon edit-item" data-id="${i.id}" title="Edit">✏️</button>
                        <button class="btn-icon delete-item" data-id="${i.id}" title="Delete">🗑️</button>
                    </td>
                </tr>`;
            });
            h += `<tr class="total-row"><td colspan="3"><strong>Total ${title}</strong></td><td class="amount">${fmt(total)}</td><td></td></tr>`;
            h += `</tbody></table>`;
            return h;
        };

        html += renderSection('Assets', assets);
        html += renderSection('Liabilities', liabilities);
        if (showEquity) html += renderSection('Equity', equities);

        return html;
    }

    // ---- Schedule AL ----
    const alLoad = async () => {
        const fy = document.getElementById('alFY').value;
        const container = document.getElementById('alContent');
        try {
            const res = await API.balanceSheet.list('schedule_al', fy);
            if (!res.balance_sheets || res.balance_sheets.length === 0) {
                container.innerHTML = `<div class="empty-state" id="alEmpty"><div class="icon">📒</div><p>No Schedule AL found for ${fy}.</p><p class="small text-muted">Click "+ New Schedule AL" to create one.</p></div>`;
                currentBsId = null;
                return;
            }
            const bs = res.balance_sheets[0];
            currentBsId = bs.id;
            let html = '';
            html += '<div id="alSummary"></div>';
            html += `<div class="section-header"><span class="section-title">Items</span><div>
                <button class="btn btn-secondary btn-sm" onclick="exportBS(${bs.id},'pdf')">📥 PDF</button>
                <button class="btn btn-secondary btn-sm" onclick="exportBS(${bs.id},'json')">📥 JSON</button>
                <button class="btn btn-primary btn-sm" id="alAddItemBtn">+ Add Item</button>
            </div></div>`;
            html += '<div id="alItems"></div>';
            container.innerHTML = html;

            const summaryDiv = document.getElementById('alSummary');
            renderSummaryCards(summaryDiv, bs.total_assets, bs.total_liabilities, 0);
            document.getElementById('alItems').innerHTML = renderItemsTable(bs.items || [], false);

            document.getElementById('alAddItemBtn').addEventListener('click', () => openModal(bs.id, false));
            attachItemListeners(bs.id);
        } catch (e) {
            container.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
        }
    };

    document.getElementById('alLoadBtn').addEventListener('click', alLoad);
    document.getElementById('alCreateBtn').addEventListener('click', async () => {
        const fy = document.getElementById('alFY').value;
        try {
            await API.balanceSheet.create({ sheet_type: 'schedule_al', financial_year: fy, name: `Schedule AL ${fy}`, items: [] });
            alLoad();
        } catch (e) { alert('Error: ' + e.message); }
    });

    // ---- Personal (auto-generated) ----
    document.getElementById('personalLoadBtn').addEventListener('click', async () => {
        const fy = document.getElementById('personalFY').value;
        const container = document.getElementById('personalContent');
        try {
            const summary = await API.balanceSheet.getSummary(fy);
            let html = '';
            html += `<div class="bs-summary">
                <div class="bs-summary-card"><div class="label">Total Income</div><div class="value positive">${fmt(summary.total_income)}</div></div>
                <div class="bs-summary-card"><div class="label">Total Expenses</div><div class="value negative">${fmt(summary.total_expenses)}</div></div>
                <div class="bs-summary-card"><div class="label">Net Worth (Income - Expenses)</div><div class="value ${summary.net_worth >= 0 ? 'positive' : 'negative'}">${fmt(summary.net_worth)}</div></div>
            </div>`;

            const renderBreakdown = (title, data) => {
                const entries = Object.entries(data);
                if (!entries.length) return `<div class="card"><div class="card-header"><h3 class="card-title">${title}</h3></div><div class="card-body"><p class="text-muted">No data</p></div></div>`;
                let h = `<div class="card"><div class="card-header"><h3 class="card-title">${title}</h3></div><div class="card-body"><ul class="breakdown-list">`;
                entries.sort((a, b) => b[1] - a[1]).forEach(([cat, amt]) => {
                    h += `<li class="breakdown-item"><span class="breakdown-cat">${cat.replace(/_/g, ' ')}</span><span class="breakdown-amt">${fmt(amt)}</span></li>`;
                });
                h += `</ul></div></div>`;
                return h;
            };

            html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">';
            html += renderBreakdown('Income Breakdown', summary.income_breakdown);
            html += renderBreakdown('Expense Breakdown', summary.expense_breakdown);
            html += '</div>';
            container.innerHTML = html;
        } catch (e) {
            container.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
        }
    });

    // ---- Business ----
    const bizLoad = async () => {
        const fy = document.getElementById('bizFY').value;
        const container = document.getElementById('bizContent');
        try {
            const res = await API.balanceSheet.list('business', fy);
            if (!res.balance_sheets || res.balance_sheets.length === 0) {
                container.innerHTML = `<div class="empty-state" id="bizEmpty"><div class="icon">🏢</div><p>No Business balance sheet found for ${fy}.</p><p class="small text-muted">Click "+ New Business BS" to create one.</p></div>`;
                currentBsId = null;
                return;
            }
            const bs = res.balance_sheets[0];
            currentBsId = bs.id;
            let html = '<div id="bizSummary"></div>';
            html += `<div class="section-header"><span class="section-title">Items</span><div>
                <button class="btn btn-secondary btn-sm" onclick="exportBS(${bs.id},'pdf')">📥 PDF</button>
                <button class="btn btn-secondary btn-sm" onclick="exportBS(${bs.id},'json')">📥 JSON</button>
                <button class="btn btn-primary btn-sm" id="bizAddItemBtn">+ Add Item</button>
            </div></div>`;
            html += '<div id="bizItems"></div>';
            container.innerHTML = html;

            const summaryDiv = document.getElementById('bizSummary');
            renderSummaryCards(summaryDiv, bs.total_assets, bs.total_liabilities, bs.total_equity);
            document.getElementById('bizItems').innerHTML = renderItemsTable(bs.items || [], true);

            document.getElementById('bizAddItemBtn').addEventListener('click', () => openModal(bs.id, true));
            attachItemListeners(bs.id);
        } catch (e) {
            container.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
        }
    };

    document.getElementById('bizLoadBtn').addEventListener('click', bizLoad);
    document.getElementById('bizCreateBtn').addEventListener('click', async () => {
        const fy = document.getElementById('bizFY').value;
        try {
            await API.balanceSheet.create({ sheet_type: 'business', financial_year: fy, name: `Business BS ${fy}`, items: [] });
            bizLoad();
        } catch (e) { alert('Error: ' + e.message); }
    });

    // ---- Modal logic ----
    const modal = document.getElementById('addItemModal');
    const modalClose = () => { modal.style.display = 'none'; editingItemId = null; };

    document.getElementById('modalClose').addEventListener('click', modalClose);
    document.getElementById('modalCancel').addEventListener('click', modalClose);

    function openModal(bsId, showEquity = false) {
        currentBsId = bsId;
        editingItemId = null;
        document.getElementById('modalTitle').textContent = 'Add Item';
        document.getElementById('itemType').value = 'asset';
        document.getElementById('itemCategory').value = '';
        document.getElementById('itemSubcategory').value = '';
        document.getElementById('itemDescription').value = '';
        document.getElementById('itemAmount').value = '';
        // Show/hide equity option
        const typeSelect = document.getElementById('itemType');
        const eqOption = typeSelect.querySelector('option[value="equity"]');
        eqOption.style.display = showEquity ? '' : 'none';
        modal.style.display = 'flex';
    }

    document.getElementById('modalSave').addEventListener('click', async () => {
        const data = {
            item_type: document.getElementById('itemType').value,
            category: document.getElementById('itemCategory').value.trim(),
            subcategory: document.getElementById('itemSubcategory').value.trim() || null,
            description: document.getElementById('itemDescription').value.trim() || null,
            amount: parseFloat(document.getElementById('itemAmount').value) || 0,
        };
        if (!data.category) { alert('Category is required'); return; }
        try {
            if (editingItemId) {
                await API.balanceSheet.updateItem(editingItemId, data);
            } else {
                await API.balanceSheet.addItem(currentBsId, data);
            }
            modalClose();
            // Reload current tab
            const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
            if (activeTab === 'schedule_al') alLoad();
            else if (activeTab === 'business') bizLoad();
        } catch (e) { alert('Error: ' + e.message); }
    });

    // ---- Edit & Delete item listeners ----
    function attachItemListeners(bsId) {
        document.querySelectorAll('.edit-item').forEach(btn => {
            btn.addEventListener('click', async () => {
                const itemId = parseInt(btn.dataset.id);
                try {
                    const bs = await API.balanceSheet.get(bsId);
                    const item = (bs.items || []).find(i => i.id === itemId);
                    if (!item) return;
                    editingItemId = itemId;
                    currentBsId = bsId;
                    document.getElementById('modalTitle').textContent = 'Edit Item';
                    document.getElementById('itemType').value = normalizeType(item.item_type);
                    document.getElementById('itemCategory').value = item.category;
                    document.getElementById('itemSubcategory').value = item.subcategory || '';
                    document.getElementById('itemDescription').value = item.description || '';
                    document.getElementById('itemAmount').value = item.amount;
                    modal.style.display = 'flex';
                } catch (e) { alert('Error loading item'); }
            });
        });

        document.querySelectorAll('.delete-item').forEach(btn => {
            btn.addEventListener('click', async () => {
                if (!confirm('Delete this item?')) return;
                try {
                    await API.balanceSheet.deleteItem(parseInt(btn.dataset.id));
                    const activeTab = document.querySelector('.tab-btn.active').dataset.tab;
                    if (activeTab === 'schedule_al') alLoad();
                    else if (activeTab === 'business') bizLoad();
                } catch (e) { alert('Error: ' + e.message); }
            });
        });
    }

    // ---- Header / session UI ----
    const userNameEl = document.getElementById('userName');
    if (userNameEl) {
        userNameEl.textContent = userData.full_name || userData.email || 'User';
    }
    document.getElementById('logoutBtn').addEventListener('click', () => {
        localStorage.removeItem('authToken');
        localStorage.removeItem('userData');
        window.location.href = 'login.html';
    });

    // Initial load
    alLoad();

})();
