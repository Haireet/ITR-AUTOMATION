/**
 * Merge Statements & Calculate ITR — frontend logic
 */
(function () {
    'use strict';

    // ── Auth guard ─────────────────────────────────────────────────
    const token = localStorage.getItem('authToken');
    if (!token) { window.location.href = 'login.html'; return; }

    const userData = JSON.parse(localStorage.getItem('userData') || '{}');
    
    // CA users should not access this page - redirect to CA dashboard
    const role = String(userData.role || '').toLowerCase();
    if (role === 'auditor' || role === 'admin') {
        window.location.href = 'ca-review.html';
        return;
    }

    document.getElementById('userName').textContent = userData.full_name || userData.email || '';

    // Show CA link if auditor/admin (not needed here anymore but kept for safety)
    if (role === 'auditor' || role === 'admin') {
        const caLink = document.getElementById('caReviewLink');
        if (caLink) caLink.style.display = '';
    }

    document.getElementById('logoutBtn').addEventListener('click', () => {
        localStorage.removeItem('authToken');
        localStorage.removeItem('userData');
        window.location.href = 'login.html';
    });

    // ── State ──────────────────────────────────────────────────────
    let statements = [];
    let selectedIds = new Set();
    let mergedData = null;
    let taxData = null;

    const fmt = n => '₹' + Number(n || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 });

    // ── Step navigation ────────────────────────────────────────────
    function showStep(n) {
        [1, 2, 3].forEach(i => {
            document.getElementById('step' + i).style.display = i === n ? '' : 'none';
            const ind = document.getElementById('step' + i + 'Indicator');
            ind.classList.remove('active', 'done');
            if (i < n) ind.classList.add('done');
            if (i === n) ind.classList.add('active');
        });
        document.getElementById('filingResult').style.display = 'none';
    }

    // ── STEP 1: Load statements ────────────────────────────────────
    async function loadStatements() {
        const grid = document.getElementById('stmtGrid');
        try {
            const res = await API.statements.list(0, 100);
            const allStatements = res.statements || res || [];
            statements = allStatements.filter(s => s.processing_status === 'completed');

            if (allStatements.length === 0) {
                grid.innerHTML = '<div class="empty-state"><div class="icon">📄</div><p>No bank statements found. <a href="upload.html">Upload bank statements</a> first.</p></div>';
                return;
            }

            if (statements.length === 0) {
                const pendingCount = allStatements.length;
                grid.innerHTML = `<div class="empty-state"><div class="icon">⏳</div><p>You have ${pendingCount} statement(s) but none are processed yet.<br><a href="upload.html">Go to Upload page</a> to process them.</p></div>`;
                return;
            }

            grid.innerHTML = statements.map(s => {
                const start = s.statement_period_start ? new Date(s.statement_period_start).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }) : '—';
                const end = s.statement_period_end ? new Date(s.statement_period_end).toLocaleDateString('en-IN', { month: 'short', year: 'numeric' }) : '—';
                return `<div class="stmt-card" data-id="${s.id}">
                    <div class="name">${escHtml(s.filename)}</div>
                    <div class="meta">🏦 ${escHtml(s.bank_name || 'Unknown Bank')}</div>
                    <div class="meta">📅 ${start} – ${end}</div>
                    <div class="meta">🔢 Account: ${s.account_number || '—'}</div>
                    <div class="meta" style="margin-top:6px;color:#22c55e;font-weight:600">✓ Processed</div>
                </div>`;
            }).join('');

            // Click to toggle selection
            grid.querySelectorAll('.stmt-card').forEach(card => {
                card.addEventListener('click', () => {
                    const id = parseInt(card.dataset.id);
                    if (selectedIds.has(id)) {
                        selectedIds.delete(id);
                        card.classList.remove('selected');
                    } else {
                        selectedIds.add(id);
                        card.classList.add('selected');
                    }
                    updateSelectionUI();
                });
            });
        } catch (e) {
            grid.innerHTML = `<div class="alert alert-error">${e.message}</div>`;
        }
    }

    function updateSelectionUI() {
        document.getElementById('selectedCount').textContent = selectedIds.size + ' selected';
        document.getElementById('mergeBtn').disabled = selectedIds.size === 0;
    }

    document.getElementById('selectAllBtn').addEventListener('click', () => {
        statements.forEach(s => selectedIds.add(s.id));
        document.querySelectorAll('.stmt-card').forEach(c => c.classList.add('selected'));
        updateSelectionUI();
    });

    document.getElementById('deselectAllBtn').addEventListener('click', () => {
        selectedIds.clear();
        document.querySelectorAll('.stmt-card').forEach(c => c.classList.remove('selected'));
        updateSelectionUI();
    });

    // ── Merge button ───────────────────────────────────────────────
    document.getElementById('mergeBtn').addEventListener('click', async () => {
        const btn = document.getElementById('mergeBtn');
        btn.disabled = true;
        btn.textContent = '⏳ Merging...';
        try {
            const fy = document.getElementById('fySelect').value;
            mergedData = await API.consolidation.merge(Array.from(selectedIds), fy);
            renderMergedSummary();
            showStep(2);
        } catch (e) {
            alert('Merge failed: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = '🔗 Merge Selected Statements';
        }
    });

    // ── STEP 2: Render merged summary ──────────────────────────────
    function renderMergedSummary() {
        const d = mergedData;
        document.getElementById('summaryCards').innerHTML = `
            <div class="summary-card"><div class="label">Statements Merged</div><div class="value">${d.statements_merged}</div></div>
            <div class="summary-card"><div class="label">Total Transactions</div><div class="value">${d.total_transactions}</div></div>
            <div class="summary-card"><div class="label">Duplicates Removed</div><div class="value" style="color:#ef4444">${d.duplicates_removed}</div></div>
            <div class="summary-card"><div class="label">Total Credits</div><div class="value" style="color:#22c55e">${fmt(d.total_credit)}</div></div>
            <div class="summary-card"><div class="label">Total Debits</div><div class="value" style="color:#ef4444">${fmt(d.total_debit)}</div></div>
            <div class="summary-card"><div class="label">Net Balance</div><div class="value">${fmt(d.net_balance)}</div></div>
        `;

        const tbody = document.getElementById('catBreakdown');
        if (!d.category_breakdown || d.category_breakdown.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#6b7280">No categorised transactions</td></tr>';
            return;
        }
        tbody.innerHTML = d.category_breakdown.map(c => `
            <tr>
                <td><strong>${c.category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</strong></td>
                <td>${c.transaction_count}</td>
                <td style="color:#22c55e">${fmt(c.total_credit)}</td>
                <td style="color:#ef4444">${fmt(c.total_debit)}</td>
                <td style="font-weight:600">${fmt(c.net_amount)}</td>
            </tr>
        `).join('');
    }

    document.getElementById('backToStep1').addEventListener('click', () => showStep(1));

    // ── Download merged statement ──────────────────────────────────
    document.getElementById('downloadMergedPDF').addEventListener('click', async () => {
        const btn = document.getElementById('downloadMergedPDF');
        btn.disabled = true;
        btn.textContent = '⏳ Generating...';
        try {
            const fy = document.getElementById('fySelect').value;
            await API.export.downloadMergedPDF(Array.from(selectedIds), fy);
        } catch (e) {
            alert('PDF export failed: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = '📥 Download PDF';
        }
    });

    document.getElementById('downloadMergedJSON').addEventListener('click', async () => {
        const btn = document.getElementById('downloadMergedJSON');
        btn.disabled = true;
        btn.textContent = '⏳ Generating...';
        try {
            const fy = document.getElementById('fySelect').value;
            const data = await API.export.mergedJSON(Array.from(selectedIds), fy);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `Merged_Statement_${fy}.json`;
            a.click();
            URL.revokeObjectURL(a.href);
        } catch (e) {
            alert('JSON export failed: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = '📥 Download JSON';
        }
    });

    // ── STEP 3: Calculate tax ──────────────────────────────────────
    document.getElementById('calcTaxBtn').addEventListener('click', async () => {
        const btn = document.getElementById('calcTaxBtn');
        btn.disabled = true;
        btn.textContent = '⏳ Calculating...';
        try {
            const fy = document.getElementById('fySelect').value;
            taxData = await API.consolidation.calculateTax(fy, 'both', Array.from(selectedIds));
            renderTaxCalculation();
            showStep(3);
        } catch (e) {
            alert('Tax calculation failed: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = '📐 Calculate Income Tax';
        }
    });

    function renderTaxCalculation() {
        const rec = taxData.recommended || taxData;

        // Income breakdown
        const incomeItems = [
            ['Salary Income', rec.salary_income],
            ['Interest Income', rec.interest_income],
            ['Dividend Income', rec.dividend_income],
            ['Rental Income', rec.rental_income],
            ['Capital Gains', rec.capital_gains],
            ['Business Income', rec.business_income],
            ['Other Income', rec.other_income || 0],
        ];
        document.getElementById('incomeBreakdown').innerHTML = incomeItems.map(([lbl, amt]) =>
            `<div class="income-item"><span class="lbl">${lbl}</span><span class="amt">${fmt(amt)}</span></div>`
        ).join('') + `<div class="income-item" style="background:#e0f2fe;font-weight:700"><span class="lbl">Gross Total Income</span><span class="amt">${fmt(rec.gross_total_income)}</span></div>`;

        // Tax comparison
        const oldR = taxData.old || taxData;
        const newR = taxData.new || taxData;

        document.getElementById('taxComparison').innerHTML = renderRegimeCard(oldR, 'Old Regime', rec.recommended_regime === 'old')
            + renderRegimeCard(newR, 'New Regime', rec.recommended_regime === 'new');

        // Savings box
        if (rec.savings > 0) {
            const box = document.getElementById('savingsBox');
            box.style.display = '';
            box.innerHTML = `💡 <strong>${rec.recommended_regime === 'new' ? 'New' : 'Old'} Regime</strong> saves you <strong>${fmt(rec.savings)}</strong> in taxes!`;
        }

        // Pre-select recommended regime for filing
        document.getElementById('regimeForFiling').value = rec.recommended_regime || 'new';
    }

    function renderRegimeCard(data, title, isRecommended) {
        const cls = isRecommended ? 'tax-regime-card recommended' : 'tax-regime-card';
        const badge = isRecommended ? '<span class="badge">✓ Recommended</span>' : '';

        let slabHtml = '';
        if (data.slab_details && data.slab_details.length) {
            slabHtml = `<table class="slab-table"><thead><tr><th>Slab</th><th>Rate</th><th>Taxable</th><th>Tax</th></tr></thead><tbody>` +
                data.slab_details.map(s => `<tr><td>${s.slab}</td><td>${s.rate}</td><td>${fmt(s.taxable_amount)}</td><td>${fmt(s.tax)}</td></tr>`).join('') +
                `</tbody></table>`;
        }

        return `<div class="${cls}">
            <h3>${title}${badge}</h3>
            <div class="income-item"><span class="lbl">Total Deductions</span><span class="amt">${fmt(data.total_deductions)}</span></div>
            <div class="income-item"><span class="lbl">Taxable Income</span><span class="amt">${fmt(data.taxable_income)}</span></div>
            ${slabHtml}
            <div class="income-item"><span class="lbl">Tax Before Cess</span><span class="amt">${fmt(data.tax_before_cess)}</span></div>
            <div class="income-item"><span class="lbl">Rebate u/s 87A</span><span class="amt" style="color:#22c55e">- ${fmt(data.rebate_87a)}</span></div>
            <div class="income-item"><span class="lbl">Health & Edu Cess (4%)</span><span class="amt">${fmt(data.health_education_cess)}</span></div>
            <div class="total-row"><span>Total Tax Liability</span><span>${fmt(data.total_tax_liability)}</span></div>
        </div>`;
    }

    document.getElementById('backToStep2').addEventListener('click', () => showStep(2));

    // ── Create Filing ──────────────────────────────────────────────
    document.getElementById('createFilingBtn').addEventListener('click', async () => {
        const btn = document.getElementById('createFilingBtn');
        if (!confirm('Create a draft ITR filing from the calculated tax data?')) return;
        btn.disabled = true;
        btn.textContent = '⏳ Creating...';
        try {
            const fy = document.getElementById('fySelect').value;
            const regime = document.getElementById('regimeForFiling').value;
            const result = await API.consolidation.createFiling(fy, regime, 'ITR-1', Array.from(selectedIds));

            // Show success
            document.getElementById('step3').style.display = 'none';
            const resDiv = document.getElementById('filingResult');
            resDiv.style.display = '';
            document.getElementById('filingResultTitle').textContent = '✅ ITR Filing Created!';
            document.getElementById('filingResultMsg').innerHTML =
                `Filing ID: <strong>${result.filing_id}</strong> · AY: <strong>${result.assessment_year}</strong> · Regime: <strong>${result.tax_regime.toUpperCase()}</strong><br>` +
                `Total Tax Liability: <strong>${fmt(result.total_tax_liability)}</strong><br>` +
                `Status: <strong>${result.status}</strong> · Review: <strong>${result.review_status.replace(/_/g, ' ')}</strong>`;
        } catch (e) {
            alert('Failed to create filing: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.textContent = '📄 Create ITR Filing';
        }
    });

    document.getElementById('startOverBtn').addEventListener('click', () => {
        selectedIds.clear();
        document.querySelectorAll('.stmt-card').forEach(c => c.classList.remove('selected'));
        updateSelectionUI();
        mergedData = null;
        taxData = null;
        document.getElementById('savingsBox').style.display = 'none';
        showStep(1);
    });

    // ── Helpers ────────────────────────────────────────────────────
    function escHtml(s) {
        const d = document.createElement('div');
        d.textContent = s || '';
        return d.innerHTML;
    }

    // ── Init ──────────────────────────────────────────────────────
    loadStatements();
})();
