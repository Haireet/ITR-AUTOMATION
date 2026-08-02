/**
 * CA Review page logic
 * Handles dashboard stats, transaction review, ITR approval, audit logs
 */
(function () {
    'use strict';

    let currentReviewFilingId = null;
    let currentReviewUserId = null;

    document.addEventListener('DOMContentLoaded', async () => {
        // Only CA/Auditors can access this page
        if (!Auth.requireReviewer()) return;
        loadDashboard();
        loadUserDropdown();
        loadFilings();
    });

    // ── Load users into dropdown ─────────────────────────────────────────
    async function loadUserDropdown() {
        const select = document.getElementById('reviewUserSelect');
        try {
            const users = await API.users.list();
            select.innerHTML = '<option value="">— Select a user —</option>';
            users.forEach(u => {
                select.innerHTML += `<option value="${u.id}">${u.full_name || u.email} (ID: ${u.id}${u.pan_number ? ', PAN: ' + u.pan_number : ''})</option>`;
            });
            select.addEventListener('change', () => loadStatementDropdown(select.value));
        } catch (e) {
            // If not CA/Admin, show a manual input fallback
            select.outerHTML = '<input class="form-input" id="reviewUserSelect" type="number" min="1" placeholder="Enter user ID" style="width:160px">';
        }
    }

    async function loadStatementDropdown(userId) {
        const stmtSelect = document.getElementById('reviewStatementSelect');
        if (!stmtSelect) return;
        stmtSelect.innerHTML = '<option value="">— All statements —</option>';
        if (!userId) return;
        try {
            const statements = await API.review.getStatements(parseInt(userId));
            statements.forEach(s => {
                stmtSelect.innerHTML += `<option value="${s.id}">${esc(s.filename)} (${s.processing_status || 'pending'})</option>`;
            });
        } catch (e) {
            console.error('Failed to load statements:', e);
        }
    }

    // ── Dashboard Stats ──────────────────────────────────────────────────
    async function loadDashboard() {
        try {
            const data = await API.review.getDashboard();
            document.getElementById('statUsers').textContent = data.assigned_users || 0;
            document.getElementById('statPending').textContent = data.pending_reviews || 0;
            document.getElementById('statApproved').textContent = data.approved_itrs || 0;
            document.getElementById('statTxnReviewed').textContent = data.total_transactions_reviewed || 0;
        } catch (e) {
            console.error('Dashboard error:', e);
            document.getElementById('statUsers').textContent = '-';
        }
    }

    // ── Transaction Review ───────────────────────────────────────────────
    const loadTxnBtn = document.getElementById('loadTxnBtn');
    if (loadTxnBtn) loadTxnBtn.addEventListener('click', async () => {
        const select = document.getElementById('reviewUserSelect');
        const userId = parseInt(select.value);
        if (!userId) { alert('Please select a user'); return; }
        currentReviewUserId = userId;
        const statementId = document.getElementById('reviewStatementSelect')?.value;

        const container = document.getElementById('txnReviewContent');
        container.innerHTML = '<p class="text-muted">Loading transactions...</p>';

        try {
            const filters = {};
            if (statementId) filters.statement_id = statementId;
            const res = await API.review.getTransactions(userId, 1, 100, filters);
            if (!res.transactions || res.transactions.length === 0) {
                container.innerHTML = '<p class="text-muted">No transactions found for this user.</p>';
                return;
            }

            let html = `<p class="small text-muted" style="margin-bottom:12px">Showing ${res.transactions.length} of ${res.total} transactions</p>`;
            html += `<div class="table-container"><table class="txn-review-table"><thead><tr>
                <th>Date</th><th>Description</th><th>Debit</th><th>Credit</th><th>Category</th><th>Reviewed</th><th>Statement</th><th>Action</th>
            </tr></thead><tbody>`;

            res.transactions.forEach(t => {
                const cat = (t.category || '').replace(/_/g, ' ');
                html += `<tr>
                    <td>${new Date(t.date).toLocaleDateString('en-IN')}</td>
                    <td>${esc(t.description).substring(0, 40)}</td>
                    <td style="color:#EF4444">${t.debit ? '₹' + fmt(t.debit) : '-'}</td>
                    <td style="color:#10B981">${t.credit ? '₹' + fmt(t.credit) : '-'}</td>
                    <td><span class="category-badge">${cat}</span></td>
                    <td>${t.manually_labeled ? '✅' : '⏳'}</td>
                    <td>#${t.statement_id}</td>
                    <td><select class="form-select" style="font-size:0.75rem;padding:2px 4px;width:120px" data-txn-id="${t.id}" onchange="updateTxnCategory(this)">
                        ${categoryOptions(t.category)}
                    </select></td>
                </tr>`;
            });

            html += '</tbody></table></div>';
            container.innerHTML = html;
        } catch (e) {
            container.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
        }
    });

    // Global function for inline category update
    window.updateTxnCategory = async function (select) {
        const txnId = select.dataset.txnId;
        const newCat = select.value;
        try {
            await API.review.updateCategory(txnId, newCat, 'CA review update');
            select.closest('tr').querySelector('td:nth-child(6)').textContent = '✅';
        } catch (e) { alert('Update failed: ' + e.message); }
    };

    function categoryOptions(current) {
        const cats = ['salary','interest','dividend','capital_gains','rental_income','business_income',
            'deduction_80c','deduction_80d','home_loan_interest','donation','expense','transfer','uncategorized'];
        return cats.map(c => `<option value="${c}" ${c === current ? 'selected' : ''}>${c.replace(/_/g, ' ')}</option>`).join('');
    }

    // ── ITR Filings ──────────────────────────────────────────────────────
    async function loadFilings() {
        const container = document.getElementById('filingsContent');
        try {
            const filings = await API.review.getFilings();
            if (!filings || filings.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="icon">📋</div><p>No ITR filings found.</p></div>';
                return;
            }

            container.innerHTML = filings.map(f => {
                const reviewClass = 'status-' + (f.review_status || 'draft').replace(/ /g, '_');
                const statusClass = 'status-' + (f.status || 'draft');

                let actions = '';
                if (f.review_status === 'pending_review' || f.review_status === 'under_review') {
                    actions += `<button class="btn btn-primary btn-sm review-btn" data-id="${f.id}">📝 Review & Approve</button>`;
                }
                if (f.review_status === 'pending_review') {
                    actions += `<button class="btn btn-secondary btn-sm start-review-btn" data-id="${f.id}">👀 Mark Under Review</button>`;
                }
                actions += `<button class="btn btn-secondary btn-sm" onclick="exportFiling(${f.id},'pdf')">📥 PDF</button>`;
                actions += `<button class="btn btn-secondary btn-sm" onclick="exportFiling(${f.id},'json')">📥 JSON</button>`;

                return `<div class="filing-card">
                    <div class="filing-header">
                        <span class="filing-title">ITR ${f.form_type} — AY ${f.assessment_year}</span>
                        <span class="status-badge ${reviewClass}">${(f.review_status || 'pending_review').replace(/_/g, ' ').toUpperCase()}</span>
                    </div>
                    <div class="filing-meta">
                        <span>👤 <strong>${esc(f.user_name)}</strong> (${esc(f.user_email)})</span>
                        <span>Status: <span class="status-badge ${statusClass}">${f.status}</span></span>
                        <span>Created: ${f.created_at ? new Date(f.created_at).toLocaleDateString('en-IN') : 'N/A'}</span>
                        ${f.filing_date ? '<span>Filed: ' + new Date(f.filing_date).toLocaleDateString('en-IN') + '</span>' : ''}
                    </div>
                    ${f.ca_comments ? `<div class="comment-box"><div class="comment-header">CA Comments</div><div class="comment-text">${esc(f.ca_comments)}</div></div>` : ''}
                    <div class="filing-actions">${actions}</div>
                </div>`;
            }).join('');

            // Attach event listeners — CA only reviews/approves
            document.querySelectorAll('.review-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    currentReviewFilingId = parseInt(btn.dataset.id);
                    document.getElementById('reviewModal').style.display = 'flex';
                });
            });
            document.querySelectorAll('.start-review-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const filingId = parseInt(btn.dataset.id);
                    try {
                        await API.review.addComment(filingId, 'CA started detailed review', 'general');
                        await loadFilings();
                        await loadDashboard();
                    } catch (e) {
                        alert('Unable to mark filing under review: ' + e.message);
                    }
                });
            });
        } catch (e) {
            container.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
        }
    }

    const refreshFilingsBtn = document.getElementById('refreshFilingsBtn');
    if (refreshFilingsBtn) refreshFilingsBtn.addEventListener('click', () => { loadFilings(); loadDashboard(); });

    // ── Export Functions ──────────────────────────────────────────────────
    window.exportFiling = async function (filingId, format) {
        try {
            if (format === 'pdf') {
                await API.export.downloadWithAuth(API.review.exportITRPDF(filingId));
            } else {
                const data = await API.review.exportITRJSON(filingId);
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = `ITR_${filingId}.json`;
                a.click();
                URL.revokeObjectURL(a.href);
            }
        } catch (e) { alert('Export failed: ' + e.message); }
    };

    const exportTxnPdfBtn = document.getElementById('exportTxnPdfBtn');
    if (exportTxnPdfBtn) exportTxnPdfBtn.addEventListener('click', async () => {
        try {
            const uid = currentReviewUserId || parseInt(document.getElementById('reviewUserSelect').value);
            if (!uid) return alert('Please select a client first');
            const sid = document.getElementById('reviewStatementSelect')?.value;
            if (!sid) return alert('Please select a statement');
            await API.export.downloadWithAuth(API.review.exportTransactionsPDF(sid, uid));
        } catch (e) { alert('Export failed: ' + e.message); }
    });

    const exportTxnJsonBtn = document.getElementById('exportTxnJsonBtn');
    if (exportTxnJsonBtn) exportTxnJsonBtn.addEventListener('click', async () => {
        try {
            const uid = currentReviewUserId || parseInt(document.getElementById('reviewUserSelect').value);
            if (!uid) return alert('Please select a client first');
            const sid = document.getElementById('reviewStatementSelect')?.value;
            if (!sid) return alert('Please select a statement');
            const data = await API.review.exportTransactionsJSON(sid, uid);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `Transactions_${sid}.json`;
            a.click();
            URL.revokeObjectURL(a.href);
        } catch (e) { alert('Export failed: ' + e.message); }
    });

    // ── Review Modal ─────────────────────────────────────────────────────
    const modal = document.getElementById('reviewModal');
    const reviewModalClose = document.getElementById('reviewModalClose');
    const reviewModalCancel = document.getElementById('reviewModalCancel');
    if (reviewModalClose && modal) reviewModalClose.addEventListener('click', () => modal.style.display = 'none');
    if (reviewModalCancel && modal) reviewModalCancel.addEventListener('click', () => modal.style.display = 'none');

    const reviewModalSubmit = document.getElementById('reviewModalSubmit');
    if (reviewModalSubmit) reviewModalSubmit.addEventListener('click', async () => {
        const approved = document.getElementById('reviewDecision').value === 'approve';
        const comments = document.getElementById('reviewComments').value.trim();

        if (!comments) { alert('Please add review comments'); return; }

        try {
            await API.review.approveITR(currentReviewFilingId, approved, comments);
            modal.style.display = 'none';
            document.getElementById('reviewComments').value = '';
            loadFilings();
            loadDashboard();
        } catch (e) { alert('Error: ' + e.message); }
    });

    // ── Helpers ───────────────────────────────────────────────────────────
    function fmt(n) { return Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
    function esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

})();
