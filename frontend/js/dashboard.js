/**
 * Dashboard Page Logic
 */

document.addEventListener('DOMContentLoaded', async function() {
    // Require authentication - CA users redirect to CA dashboard
    if (!Auth.requireRegularUser()) return;
    
    const userData = Auth.getUserData();
    
    // Load dashboard data
    await loadDashboardStats();
    await loadNextSteps();
});

/**
 * Load dashboard statistics
 */
async function loadDashboardStats() {
    try {
        // Get bank statements and derive transaction stats
        const statementsRes = await API.statements.list(0, 100);
        const statements = statementsRes.statements || [];
        document.getElementById('statStatements').textContent = statementsRes.total || statements.length || 0;

        const processed = statements.filter(s => s.processing_status === 'completed');
        let transactionCount = 0;
        let reviewedCount = 0;
        for (const st of processed.slice(0, 20)) { // keep dashboard fast
            const txRes = await API.statements.getTransactions(st.id, 0, 500);
            const txns = txRes.transactions || [];
            transactionCount += txns.length;
            reviewedCount += txns.filter(t => t.manually_labeled).length;
        }

        const filings = await API.itr.list();
        const latestFiling = (filings || []).sort((a, b) => new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at))[0];
        const itrStatus = latestFiling ? (latestFiling.review_status || latestFiling.status || 'Draft') : 'Not Started';

        document.getElementById('statTransactions').textContent = transactionCount.toLocaleString('en-IN');
        document.getElementById('statReviewed').textContent = reviewedCount.toLocaleString('en-IN');
        document.getElementById('statITRStatus').textContent = String(itrStatus).replace(/_/g, ' ');
        
    } catch (error) {
        console.error('Error loading dashboard stats:', error);
        showError('Failed to load dashboard statistics. Please refresh.');
    }
}

/**
 * Load next steps guidance
 */
async function loadNextSteps() {
    const container = document.getElementById('nextStepsContainer');
    
    try {
        // Get statements count
        const statements = await API.statements.list(0, 1);
        
        const steps = [];
        
        if (statements.total === 0) {
            steps.push({
                title: 'Upload Bank Statement',
                description: 'Start by uploading your bank statement to extract transactions',
                action: 'upload.html',
                actionText: 'Upload Now',
                priority: 'high'
            });
        } else {
            steps.push({
                title: 'Review Transactions',
                description: 'Review and categorize your transactions for accurate tax calculation',
                action: 'transactions.html',
                actionText: 'Review Transactions',
                priority: 'medium'
            });
            
            steps.push({
                title: 'View ITR Summary',
                description: 'Check your tax summary and prepare for filing',
                action: 'itr-summary.html',
                actionText: 'View Summary',
                priority: 'low'
            });
        }
        
        // Render steps
        container.innerHTML = steps.map(step => `
            <div class="next-step ${step.priority}">
                <div class="step-content">
                    <h4>${step.title}</h4>
                    <p class="text-muted">${step.description}</p>
                </div>
                <a href="${step.action}" class="btn btn-primary">${step.actionText}</a>
            </div>
        `).join('');
        
    } catch (error) {
        console.error('Error loading next steps:', error);
        container.innerHTML = '<p class="text-muted">Unable to load guidance</p>';
    }
}

/**
 * Show error message
 */
function showError(message) {
    alert(message); // Simple error handling for now
}
