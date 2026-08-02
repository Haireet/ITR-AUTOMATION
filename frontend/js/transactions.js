/**
 * Transactions Page Logic
 * Lists, filters and allows re-categorisation of extracted transactions
 */

const CATEGORIES = [
    { value: 'salary',             label: 'Salary Income' },
    { value: 'interest',           label: 'Interest Income' },
    { value: 'dividend',           label: 'Dividend' },
    { value: 'capital_gains',      label: 'Capital Gains' },
    { value: 'rental_income',      label: 'Rental Income' },
    { value: 'business_income',    label: 'Business / Professional Income' },
    { value: 'deduction_80c',      label: 'Deduction 80C' },
    { value: 'deduction_80d',      label: 'Deduction 80D (Health Insurance)' },
    { value: 'home_loan_interest', label: 'Home Loan Interest (Sec 24b)' },
    { value: 'donation',           label: 'Donation (80G)' },
    { value: 'expense',            label: 'Expense' },
    { value: 'transfer',           label: 'Fund Transfer' },
    { value: 'uncategorized',      label: 'Uncategorized' },
];

// Page state
let currentStatementId = null;
let allTransactions    = [];       // full loaded set for current statement
let pendingChanges     = {};       // { transactionId: { category, notes } }
let detectedAnomalies  = [];       // anomalies detected by AI

document.addEventListener('DOMContentLoaded', async function () {
    console.log('Transactions page loading...');
    
    // CA users should not access this page - redirect to CA dashboard
    if (!Auth.requireRegularUser()) {
        console.log('Auth check failed - redirecting');
        return;
    }
    
    console.log('Auth check passed, loading statements...');
    await loadStatementSelector();
    console.log('Statements loaded');

    // Filter/search
    document.getElementById('filterBtn').addEventListener('click', renderTable);
    document.getElementById('searchInput').addEventListener('input', debounce(renderTable, 300));
    document.getElementById('categoryFilter').addEventListener('change', renderTable);

    // Save / discard
    document.getElementById('saveChangesBtn').addEventListener('click', saveChanges);
    document.getElementById('discardChangesBtn').addEventListener('click', discardChanges);

    // Export buttons
    document.getElementById('exportTxnPDF').addEventListener('click', async () => {
        if (!currentStatementId) return alert('Please select a statement first');
        try { await API.export.downloadWithAuth(API.export.transactionsPDF(currentStatementId)); }
        catch (e) { alert('Export failed: ' + e.message); }
    });
    document.getElementById('exportTxnJSON').addEventListener('click', async () => {
        if (!currentStatementId) return alert('Please select a statement first');
        try {
            const data = await API.export.transactionsJSON(currentStatementId);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
            a.download = `Transactions_${currentStatementId}.json`; a.click(); URL.revokeObjectURL(a.href);
        } catch (e) { alert('Export failed: ' + e.message); }
    });

    // Modal
    document.getElementById('closeModal').addEventListener('click',  closeModal);
    document.getElementById('cancelModalBtn').addEventListener('click', closeModal);
    document.getElementById('saveModalBtn').addEventListener('click', saveModalChange);

    // If statement id is in URL, pre-select it
    const params = new URLSearchParams(window.location.search);
    if (params.get('statement')) {
        const sel = document.getElementById('statementSelector');
        if (sel) sel.value = params.get('statement');
        await loadTransactions(params.get('statement'));
    }
});

// ────────────────────────────────────────────────────────────────────────────
//  Statement selector
// ────────────────────────────────────────────────────────────────────────────

async function loadStatementSelector() {
    const container = document.getElementById('statementSelectorContainer');
    if (!container) return;
    
    try {
        const data = await API.statements.list();
        const statements = data.statements || [];

        if (statements.length === 0) {
            container.innerHTML = `
                <div class="alert alert-warning">
                    No statements uploaded yet.
                    <a href="upload.html" class="btn btn-link">Upload one now →</a>
                </div>`;
            return;
        }

        const processed = statements.filter(s => s.processing_status === 'completed');

        // Show helpful info about non-processed statements
        const pending = statements.filter(s => s.processing_status !== 'completed');
        let pendingInfo = '';
        if (pending.length > 0 && processed.length === 0) {
            const statusMessages = pending.map(s => {
                const status = s.processing_status || 'pending';
                if (status === 'pending') return `"${s.filename}" - needs processing`;
                if (status === 'processing') return `"${s.filename}" - currently processing`;
                if (status === 'password_required') return `"${s.filename}" - password required`;
                if (status === 'failed') return `"${s.filename}" - processing failed`;
                return `"${s.filename}" - ${status}`;
            });
            pendingInfo = `
                <div class="alert alert-info" style="margin-top: 12px;">
                    <strong>📋 You have ${pending.length} statement(s) that need processing:</strong>
                    <ul style="margin: 8px 0 0 20px;">
                        ${statusMessages.map(m => `<li>${m}</li>`).join('')}
                    </ul>
                    <a href="upload.html" class="btn btn-link" style="padding-left: 0;">Go to Upload page to process →</a>
                </div>`;
        }

        container.innerHTML = `
            <div class="form-group" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
                <label class="form-label" style="margin:0;white-space:nowrap">Statement:</label>
                <select id="statementSelector" class="form-select" style="max-width:420px">
                    <option value="">— Select a processed statement —</option>
                    ${processed.map(s => `
                        <option value="${s.id}">
                            ${escHtml(s.filename)}${s.bank_name ? ' — ' + escHtml(s.bank_name) : ''}
                            ${s.statement_period_start ? ' (' + formatDate(s.statement_period_start) + ' – ' + formatDate(s.statement_period_end) + ')' : ''}
                        </option>`).join('')}
                </select>
                ${processed.length === 0
                    ? `<span class="text-muted">No processed statements found.</span>`
                    : ''}
            </div>
            ${pendingInfo}`;

        document.getElementById('statementSelector').addEventListener('change', function () {
            pendingChanges = {};
            detectedAnomalies = [];
            document.getElementById('anomalyAlert').style.display = 'none';
            updateActionButtons();
            if (this.value) loadTransactions(this.value);
            else {
                document.getElementById('transactionsBody').innerHTML =
                    `<tr><td colspan="7" class="text-center text-muted">Select a statement above</td></tr>`;
            }
        });

    } catch (err) {
        console.error('Failed to load statements:', err);
        container.innerHTML = `
            <div class="alert alert-error" style="background: #fef2f2; border: 1px solid #fecaca; color: #dc2626; padding: 16px; border-radius: 8px;">
                <strong>⚠️ Failed to load statements</strong><br>
                ${err.message || 'Please check your connection and try refreshing the page.'}
            </div>`;
    }
}

// ────────────────────────────────────────────────────────────────────────────
//  Load transactions
// ────────────────────────────────────────────────────────────────────────────

async function loadTransactions(statementId) {
    currentStatementId = statementId;
    allTransactions    = [];
    document.getElementById('transactionsBody').innerHTML =
        `<tr><td colspan="7" class="text-center text-muted">Loading…</td></tr>`;

    try {
        // Fetch up to 1000 transactions (paginated in batches of 500)
        let skip = 0;
        let fetched;
        do {
            const res = await API.statements.getTransactions(statementId, skip, 500);
            fetched = res.transactions || [];
            allTransactions.push(...fetched);
            skip += fetched.length;
        } while (fetched.length === 500);

        renderTable();
        updateSummaryBadge();
    } catch (err) {
        document.getElementById('transactionsBody').innerHTML =
            `<tr><td colspan="7" class="text-center text-muted">Error: ${escHtml(err.message)}</td></tr>`;
    }
}

// ────────────────────────────────────────────────────────────────────────────
//  Render table (with filters)
// ────────────────────────────────────────────────────────────────────────────

function renderTable() {
    const search   = (document.getElementById('searchInput').value || '').toLowerCase();
    const catFilter = document.getElementById('categoryFilter').value;

    const filtered = allTransactions.filter(t => {
        const matchSearch = !search || t.description.toLowerCase().includes(search);
        const matchCat    = !catFilter || t.category === catFilter;
        return matchSearch && matchCat;
    });

    const tbody = document.getElementById('transactionsBody');

    if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No transactions match your filters</td></tr>`;
        return;
    }

    tbody.innerHTML = filtered.map(t => {
        const pending    = pendingChanges[t.id];
        const category   = pending ? pending.category : t.category;
        const isChanged  = !!pending;
        const hasAnomaly = isAnomalyTransaction(t.id);
        const rowClass   = [
            category === 'uncategorized' ? 'uncategorized' : '',
            hasAnomaly ? 'anomaly-row' : ''
        ].filter(Boolean).join(' ');
        const changedMark = isChanged ? ' ✏️' : '';
        const anomalyFlags = hasAnomaly ? getAnomalyFlags(t.id) : [];

        return `
            <tr class="${rowClass}" data-id="${t.id}">
                <td>${formatDate(t.date)}</td>
                <td title="${escHtml(t.description)}">
                    ${hasAnomaly ? '<span class="anomaly-indicator" title="Anomaly detected">⚠️</span> ' : ''}
                    ${escHtml(truncate(t.description, 50))}
                </td>
                <td class="amount-debit">${t.debit > 0 ? '₹' + fmt(t.debit) : ''}</td>
                <td class="amount-credit">${t.credit > 0 ? '₹' + fmt(t.credit) : ''}</td>
                <td>${t.balance ? '₹' + fmt(t.balance) : '—'}</td>
                <td>
                    <span class="category-badge cat-${category}">${categoryLabel(category)}${changedMark}</span>
                    ${t.manually_labeled ? '<span title="Manually set" style="margin-left:4px">👤</span>' : ''}
                    ${hasAnomaly ? `<span class="anomaly-tag" title="${anomalyFlags.map(f=>f.message).join(', ')}">⚠️</span>` : ''}
                </td>
                <td>
                    <button class="btn btn-sm btn-secondary edit-btn" data-id="${t.id}">Edit</button>
                </td>
            </tr>`;
    }).join('');

    tbody.querySelectorAll('.edit-btn').forEach(btn => {
        btn.addEventListener('click', () => openModal(btn.dataset.id));
    });
}

// ────────────────────────────────────────────────────────────────────────────
//  Modal
// ────────────────────────────────────────────────────────────────────────────

let editingTransactionId = null;

function openModal(transactionId) {
    editingTransactionId = transactionId;
    const txn = allTransactions.find(t => String(t.id) === String(transactionId));
    if (!txn) return;

    const pending = pendingChanges[transactionId];
    const currentCat = pending ? pending.category : txn.category;
    const currentNotes = pending ? pending.notes : (txn.notes || '');

    document.getElementById('modalTransactionInfo').textContent =
        `${formatDate(txn.date)} — ${truncate(txn.description, 70)} — ${txn.credit > 0 ? '₹' + fmt(txn.credit) + ' Cr' : '₹' + fmt(txn.debit) + ' Dr'}`;

    const catSelect = document.getElementById('modalCategory');
    catSelect.innerHTML = CATEGORIES.map(c =>
        `<option value="${c.value}" ${currentCat === c.value ? 'selected' : ''}>${c.label}</option>`
    ).join('');

    document.getElementById('modalNotes').value = currentNotes;
    document.getElementById('categoryModal').style.display = 'flex';
}

function closeModal() {
    editingTransactionId = null;
    document.getElementById('categoryModal').style.display = 'none';
}

function saveModalChange() {
    if (!editingTransactionId) return;
    const category = document.getElementById('modalCategory').value;
    const notes    = document.getElementById('modalNotes').value.trim();

    pendingChanges[editingTransactionId] = { category, notes };
    closeModal();
    updateActionButtons();
    renderTable();
    document.getElementById('unsavedWarning').style.display = 'block';
}

// ────────────────────────────────────────────────────────────────────────────
//  Save / Discard
// ────────────────────────────────────────────────────────────────────────────

async function saveChanges() {
    const ids = Object.keys(pendingChanges);
    if (ids.length === 0) return;

    const btn = document.getElementById('saveChangesBtn');
    btn.disabled = true;
    btn.textContent = 'Saving…';

    let success = 0, failed = 0;
    for (const id of ids) {
        try {
            await API.statements.updateTransactionCategory(id, pendingChanges[id]);
            // Update local copy
            const txn = allTransactions.find(t => String(t.id) === id);
            if (txn) {
                txn.category       = pendingChanges[id].category;
                txn.notes          = pendingChanges[id].notes;
                txn.manually_labeled = true;
            }
            success++;
        } catch (err) {
            failed++;
            console.error(`Failed to update transaction ${id}:`, err);
        }
    }

    pendingChanges = {};
    updateActionButtons();
    renderTable();
    updateSummaryBadge();
    document.getElementById('unsavedWarning').style.display = 'none';
    btn.textContent = 'Save Changes';

    if (failed > 0) {
        alert(`${success} transaction(s) saved, ${failed} failed. Check console for details.`);
    }
}

function discardChanges() {
    pendingChanges = {};
    updateActionButtons();
    renderTable();
    document.getElementById('unsavedWarning').style.display = 'none';
}

function updateActionButtons() {
    const hasPending = Object.keys(pendingChanges).length > 0;
    document.getElementById('saveChangesBtn').disabled    = !hasPending;
    document.getElementById('discardChangesBtn').disabled = !hasPending;
}

// ────────────────────────────────────────────────────────────────────────────
//  Summary badge
// ────────────────────────────────────────────────────────────────────────────

function updateSummaryBadge() {
    const uncategorized = allTransactions.filter(t => t.category === 'uncategorized').length;
    const el = document.getElementById('uncategorizedCount');
    if (el) el.textContent = uncategorized > 0 ? `${uncategorized} uncategorized` : '';
}

// ────────────────────────────────────────────────────────────────────────────
//  Helpers
// ────────────────────────────────────────────────────────────────────────────

function categoryLabel(value) {
    const c = CATEGORIES.find(c => c.value === value);
    return c ? c.label : value;
}

function formatDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function fmt(n) {
    if (n == null) return '0.00';
    return Number(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function truncate(str, max) {
    if (!str) return '';
    return str.length > max ? str.substring(0, max) + '…' : str;
}

function escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function debounce(fn, ms) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), ms);
    };
}

// ────────────────────────────────────────────────────────────────────────────
//  AI Features: Auto-Categorization & Anomaly Detection
// ────────────────────────────────────────────────────────────────────────────

// Initialize AI buttons
document.addEventListener('DOMContentLoaded', () => {
    const autoCatBtn = document.getElementById('autoCategorizeBtn');
    const anomalyBtn = document.getElementById('detectAnomaliesBtn');
    const viewAnomaliesBtn = document.getElementById('viewAnomaliesBtn');

    if (autoCatBtn) autoCatBtn.addEventListener('click', autoCategorize);
    if (anomalyBtn) anomalyBtn.addEventListener('click', detectAnomalies);
    if (viewAnomaliesBtn) viewAnomaliesBtn.addEventListener('click', showAnomalyModal);
});

async function autoCategorize() {
    if (!currentStatementId) {
        alert('Please select a statement first');
        return;
    }

    const btn = document.getElementById('autoCategorizeBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '🤖 Categorizing...';

    try {
        const result = await API.ai.autoCategorize(currentStatementId);
        
        if (result.updated > 0) {
            // Reload transactions to show new categories
            await loadTransactions(currentStatementId);
            alert(`✅ Auto-categorized ${result.updated} of ${result.total} transactions!\n\n${result.skipped} transactions were skipped (low confidence).`);
        } else {
            alert('No uncategorized transactions found, or all had low confidence scores.');
        }
    } catch (error) {
        console.error('Auto-categorize failed:', error);
        alert('Auto-categorization failed: ' + (error.message || 'Unknown error'));
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

async function detectAnomalies() {
    if (!currentStatementId) {
        alert('Please select a statement first');
        return;
    }

    const btn = document.getElementById('detectAnomaliesBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '🔍 Scanning...';

    try {
        const result = await API.ai.detectAnomalies(currentStatementId);
        detectedAnomalies = result.anomalies || [];
        
        const alertBanner = document.getElementById('anomalyAlert');
        const countEl = document.getElementById('anomalyCount');
        
        if (detectedAnomalies.length > 0) {
            countEl.textContent = detectedAnomalies.length;
            alertBanner.style.display = 'block';
            
            // Mark anomalies in transaction list
            renderTable();
        } else {
            alertBanner.style.display = 'none';
            alert('✅ No anomalies detected in your transactions.');
        }
    } catch (error) {
        console.error('Anomaly detection failed:', error);
        alert('Anomaly detection failed: ' + (error.message || 'Unknown error'));
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

function isAnomalyTransaction(txnId) {
    return detectedAnomalies.some(a => a.transaction_id === txnId);
}

function getAnomalyFlags(txnId) {
    const anomaly = detectedAnomalies.find(a => a.transaction_id === txnId);
    return anomaly ? anomaly.flags : [];
}

function showAnomalyModal() {
    if (detectedAnomalies.length === 0) return;

    // Create modal HTML
    const modalHtml = `
        <div id="anomalyModal" class="modal" style="display: flex;">
            <div class="modal-content" style="max-width: 700px; max-height: 80vh; overflow-y: auto;">
                <div class="modal-header">
                    <h3>⚠️ Detected Anomalies</h3>
                    <button class="close-btn" onclick="closeAnomalyModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <p style="margin-bottom: 16px; color: #64748b;">
                        The following transactions have unusual patterns that may require review:
                    </p>
                    <div class="anomaly-list">
                        ${detectedAnomalies.map(a => `
                            <div class="anomaly-item" style="padding: 12px; border: 1px solid #fed7aa; border-radius: 8px; margin-bottom: 12px; background: #fff7ed;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                    <strong style="color: #c2410c;">${escHtml(a.description || 'Transaction')}</strong>
                                    <span style="font-weight: 600;">₹${fmt(a.amount)}</span>
                                </div>
                                <div style="font-size: 12px; color: #64748b; margin-bottom: 8px;">
                                    ${a.date ? formatDate(a.date) : ''} | ${categoryLabel(a.category)}
                                </div>
                                <div style="display: flex; flex-wrap: wrap; gap: 4px;">
                                    ${a.flags.map(f => `
                                        <span class="anomaly-flag" style="display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; background: #fef3c7; color: #b45309; border-radius: 12px; font-size: 11px;">
                                            ${getAnomalyIcon(f.type)} ${f.message}
                                        </span>
                                    `).join('')}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-primary" onclick="closeAnomalyModal()">Got it</button>
                </div>
            </div>
        </div>
    `;

    // Add to DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

function closeAnomalyModal() {
    const modal = document.getElementById('anomalyModal');
    if (modal) modal.remove();
}

function getAnomalyIcon(type) {
    const icons = {
        'large_amount': '💰',
        'duplicate': '🔄',
        'category_mismatch': '🏷️',
        'round_amount': '🎯',
        'large_cash': '💵'
    };
    return icons[type] || '⚠️';
}
