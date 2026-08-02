/**
 * Upload Page Logic
 * Handles file selection, drag-and-drop, upload and auto-processing.
 * For PDFs: shows an optional password field BEFORE upload so encrypted PDFs work on first try.
 */

// PDF file waiting for user to click "Upload & Process"
let pendingPdfFile = null;

document.addEventListener('DOMContentLoaded', function () {
    // CA users should not access this page - redirect to CA dashboard
    if (!Auth.requireRegularUser()) return;

    const uploadArea = document.getElementById('uploadArea');
    const fileInput  = document.getElementById('fileInput');
    const browseBtn  = document.getElementById('browseBtn');

    browseBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        fileInput.click();
    });
    uploadArea.addEventListener('click', function () { fileInput.click(); });

    // Drag-and-drop
    uploadArea.addEventListener('dragover', function (e) { e.preventDefault(); uploadArea.classList.add('drag-over'); });
    uploadArea.addEventListener('dragleave', function () { uploadArea.classList.remove('drag-over'); });
    uploadArea.addEventListener('drop', function (e) {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        if (e.dataTransfer.files.length > 0) handleFile(e.dataTransfer.files[0]);
    });

    fileInput.addEventListener('change', function () {
        if (this.files.length > 0) handleFile(this.files[0]);
    });

    // PDF password section buttons
    document.getElementById('uploadPdfBtn').addEventListener('click', function () {
        if (!pendingPdfFile) return;
        const password = document.getElementById('pdfPassword').value || null;
        const file = pendingPdfFile;
        pendingPdfFile = null;
        document.getElementById('pdfPasswordSection').style.display = 'none';
        uploadAndProcess(file, password);
    });

    document.getElementById('cancelPdfBtn').addEventListener('click', function () {
        pendingPdfFile = null;
        document.getElementById('pdfPasswordSection').style.display = 'none';
        document.getElementById('pdfPassword').value = '';
        document.getElementById('uploadArea').style.display = 'block';
        fileInput.value = '';
    });

    loadStatements();
});

// ────────────────────────────────────────────────────────────────────────────
const ALLOWED_EXTS = ['.csv', '.xls', '.xlsx', '.pdf'];
const MAX_SIZE_MB  = 10;

function handleFile(file) {
    hideMessages();

    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
        showError(`Invalid file type "${ext}". Allowed: ${ALLOWED_EXTS.join(', ')}`);
        return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        showError(`File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max: ${MAX_SIZE_MB} MB`);
        return;
    }

    // PDF → pause and show optional password field
    if (ext === '.pdf') {
        pendingPdfFile = file;
        document.getElementById('uploadArea').style.display = 'none';
        document.getElementById('pdfFileName').textContent = file.name;
        document.getElementById('pdfPassword').value = '';
        document.getElementById('pdfPasswordSection').style.display = 'block';
        document.getElementById('pdfPassword').focus();
        return;
    }

    // Non-PDF → upload immediately
    uploadAndProcess(file, null);
}

async function uploadAndProcess(file, pdfPassword) {
    const uploadArea     = document.getElementById('uploadArea');
    const uploadProgress = document.getElementById('uploadProgress');
    const fileNameEl     = document.getElementById('fileName');
    const fileSizeEl     = document.getElementById('fileSize');
    const progressBar    = document.getElementById('progressBar');
    const progressText   = document.getElementById('progressText');

    uploadArea.style.display = 'none';
    document.getElementById('pdfPasswordSection').style.display = 'none';
    uploadProgress.style.display = 'block';
    fileNameEl.textContent = file.name;
    fileSizeEl.textContent = formatFileSize(file.size);

    animateProgress(progressBar, 0, 60, 800);
    progressText.textContent = 'Uploading…';

    try {
        const uploadResult = await API.statements.upload(file);
        const statementId  = uploadResult.statement.id;

        animateProgress(progressBar, 60, 90, 600);
        progressText.textContent = 'Processing transactions…';

        let processResult;
        try {
            processResult = await API.statements.process(statementId, pdfPassword);
        } catch (procErr) {
            progressText.textContent = '';
            uploadProgress.style.display = 'none';

            if (procErr.message && procErr.message.includes('PDF_PASSWORD_REQUIRED')) {
                uploadArea.style.display = 'block';
                showError(
                    pdfPassword
                        ? 'Incorrect PDF password. Upload saved — use the 🔄 Process button below to retry.'
                        : 'This PDF is password protected. Upload saved — use the 🔄 Process button below to retry with a password.'
                );
                loadStatements().catch(() => {});
                return;
            }

            showSuccess(
                `Statement uploaded (${file.name}). Processing failed: ${procErr.message || 'unknown error'}. You can retry from the list below.`,
                statementId
            );
            loadStatements().catch(() => {});
            return;
        }

        animateProgress(progressBar, 90, 100, 200);
        progressText.textContent = '';

        const txnCount = processResult.transactions_extracted || 0;
        const warnings = processResult.warnings || [];
        let msg = `Statement uploaded and processed successfully! ${txnCount} transaction${txnCount !== 1 ? 's' : ''} extracted.`;
        if (warnings.length) msg += ` (${warnings.length} warning${warnings.length > 1 ? 's' : ''})`;
        showSuccess(msg, statementId);
        await loadStatements();

    } catch (err) {
        uploadProgress.style.display = 'none';
        uploadArea.style.display = 'block';
        showError(err.message || 'Upload failed. Please try again.');
    }
}

// ────────────────────────────────────────────────────────────────────────────
//  Statement list
// ────────────────────────────────────────────────────────────────────────────

async function loadStatements() {
    const container = document.getElementById('statementsList');
    try {
        const data = await API.statements.list();
        const statements = data.statements || [];

        if (statements.length === 0) {
            container.innerHTML = '<p class="text-muted">No statements uploaded yet</p>';
            return;
        }

        container.innerHTML = `
            <table class="data-table">
                <thead><tr>
                    <th>File Name</th><th>Bank</th><th>Period</th><th>Status</th><th>Uploaded</th><th>Actions</th>
                </tr></thead>
                <tbody>${statements.map(s => statementRow(s)).join('')}</tbody>
            </table>`;

        container.querySelectorAll('.btn-delete').forEach(btn => {
            btn.addEventListener('click', () => deleteStatement(btn.dataset.id));
        });
        container.querySelectorAll('.btn-process').forEach(btn => {
            btn.addEventListener('click', () => reprocessStatement(btn.dataset.id, btn));
        });
    } catch (err) {
        container.innerHTML = `<p class="text-muted">Failed to load statements: ${err.message}</p>`;
    }
}

function statementRow(s) {
    const statusBadge = {
        completed:  '<span class="badge badge-success">✓ Processed</span>',
        processing: '<span class="badge badge-warning">⏳ Processing</span>',
        failed:     '<span class="badge badge-error">✗ Failed</span>',
        pending:    '<span class="badge badge-muted">Pending</span>',
        password_required: '<span class="badge badge-warning">🔒 Password Required</span>',
    }[s.processing_status] || `<span class="badge badge-muted">${s.processing_status}</span>`;

    const period = (s.statement_period_start && s.statement_period_end)
        ? `${formatDate(s.statement_period_start)} – ${formatDate(s.statement_period_end)}` : '—';

    const canProcess = s.processing_status !== 'processing';

    return `<tr>
        <td><strong>${escHtml(s.filename)}</strong><br><small class="text-muted">${formatFileSize(s.file_size)}</small></td>
        <td>${escHtml(s.bank_name || '—')}</td>
        <td>${period}</td>
        <td>${statusBadge}${s.error_message ? `<br><small class="text-muted">${escHtml(s.error_message)}</small>` : ''}</td>
        <td>${formatDate(s.upload_date)}</td>
        <td>
            ${canProcess ? `<button class="btn btn-sm btn-secondary btn-process" data-id="${s.id}" style="margin-right:6px">🔄 Process</button>` : ''}
            <button class="btn btn-sm btn-danger btn-delete" data-id="${s.id}">🗑 Delete</button>
        </td>
    </tr>`;
}

async function deleteStatement(id) {
    if (!confirm('Delete this statement and all its transactions?')) return;
    try { await API.statements.delete(id); await loadStatements(); }
    catch (err) { alert('Delete failed: ' + (err.message || err)); }
}

async function reprocessStatement(id, btn) {
    const password = prompt('Enter PDF password (leave empty if not protected):');
    if (password === null) return;

    btn.disabled = true;
    btn.textContent = '⏳';
    try {
        const result = await API.statements.process(id, password || null);
        alert(`Processed! ${result.transactions_extracted} transactions extracted.`);
        await loadStatements();
    } catch (err) {
        if (err.message && err.message.includes('PDF_PASSWORD_REQUIRED')) {
            alert('Incorrect password or PDF is encrypted. Please try again.');
        } else {
            alert('Processing failed: ' + (err.message || err));
        }
        btn.disabled = false;
        btn.textContent = '🔄 Process';
    }
}

// ────────────────────────────────────────────────────────────────────────────
//  UI Helpers
// ────────────────────────────────────────────────────────────────────────────

function showSuccess(message, statementId) {
    const el = document.getElementById('uploadSuccess');
    el.innerHTML = `<strong>✓ Success!</strong> ${escHtml(message)}
        <a href="transactions.html?statement=${statementId}" class="btn btn-link" style="margin-left:8px">View Transactions →</a>`;
    el.style.display = 'block';
}

function showError(message) {
    const el = document.getElementById('uploadError');
    el.textContent = message;
    el.style.display = 'block';
}

function hideMessages() {
    document.getElementById('uploadSuccess').style.display = 'none';
    document.getElementById('uploadError').style.display   = 'none';
    document.getElementById('uploadProgress').style.display = 'none';
    document.getElementById('uploadArea').style.display     = 'block';
}

function animateProgress(bar, from, to, duration) {
    const start = performance.now();
    (function step(now) {
        const frac = Math.min((now - start) / duration, 1);
        bar.style.width = (from + (to - from) * frac) + '%';
        if (frac < 1) requestAnimationFrame(step);
    })(performance.now());
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

function formatDate(iso) {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function escHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
