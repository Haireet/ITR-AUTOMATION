/**
 * API Helper Module
 * Centralized API calls to backend
 */

const API_BASE_URL = 'http://localhost:8000/api';

// API Helper Class
const API = {
    /**
     * Make authenticated request
     */
    async request(endpoint, options = {}) {
        const token = localStorage.getItem('authToken');
        
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        const config = {
            ...options,
            headers
        };
        
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, config);
            
            // Handle 401 Unauthorized - redirect to login
            if (response.status === 401) {
                localStorage.removeItem('authToken');
                localStorage.removeItem('userData');
                window.location.href = 'login.html';
                throw new Error('Unauthorized');
            }
            
            // Handle 403 Forbidden
            if (response.status === 403) {
                throw new Error('Access denied');
            }
            
            // Handle 404 Not Found
            if (response.status === 404) {
                throw new Error('Resource not found');
            }
            
            // Handle 500 Server Error
            if (response.status >= 500) {
                throw new Error('Server error. Please try again later.');
            }
            
            // Parse JSON response
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Request failed');
            }
            
            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },
    
    /**
     * Upload file with multipart/form-data
     */
    async upload(endpoint, formData) {
        const token = localStorage.getItem('authToken');
        
        const headers = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: 'POST',
                headers,
                body: formData
            });
            
            if (response.status === 401) {
                localStorage.removeItem('authToken');
                localStorage.removeItem('userData');
                window.location.href = 'login.html';
                throw new Error('Unauthorized');
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Upload failed');
            }
            
            return data;
        } catch (error) {
            console.error('Upload Error:', error);
            throw error;
        }
    },
    
    // Auth endpoints
    auth: {
        login: (email, password) => 
            API.request('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ email, password })
            }),
        
        register: (userData) =>
            API.request('/auth/register', {
                method: 'POST',
                body: JSON.stringify(userData)
            }),
        
        registerCA: (caData) =>
            API.request('/auth/register-ca', {
                method: 'POST',
                body: JSON.stringify(caData)
            }),
        
        getCurrentUser: () =>
            API.request('/auth/me'),
        
        refreshToken: () =>
            API.request('/auth/refresh', { method: 'POST' })
    },

    // User endpoints
    users: {
        list: () => API.request('/users/'),
        get: (userId) => API.request(`/users/${userId}`),
        getProfile: () => API.request('/users/me'),
        updateProfile: (data) => API.request('/users/me', {
            method: 'PUT',
            body: JSON.stringify(data)
        }),
        update: (userId, data) => API.request(`/users/${userId}`, {
            method: 'PUT',
            body: JSON.stringify(data)
        }),
        delete: (userId) => API.request(`/users/${userId}`, { method: 'DELETE' })
    },
    
    // Bank statement endpoints
    statements: {
        upload: (file) => {
            const formData = new FormData();
            formData.append('file', file);
            return API.upload('/statements/upload', formData);
        },

        list: (skip = 0, limit = 100) =>
            API.request(`/statements?skip=${skip}&limit=${limit}`),

        get: (statementId) =>
            API.request(`/statements/${statementId}`),

        delete: (statementId) =>
            API.request(`/statements/${statementId}`, { method: 'DELETE' }),

        process: (statementId, pdfPassword = null) => {
            const body = pdfPassword ? { pdf_password: pdfPassword } : {};
            return API.request(`/statements/${statementId}/process`, {
                method: 'POST',
                body: JSON.stringify(body)
            });
        },

        getTransactions: (statementId, skip = 0, limit = 500) =>
            API.request(`/statements/${statementId}/transactions?skip=${skip}&limit=${limit}`),

        updateTransactionCategory: (transactionId, { category, notes }) =>
            API.request(`/statements/transactions/${transactionId}/category`, {
                method: 'PATCH',
                body: JSON.stringify({ category, notes })
            })
    },
    
    // ITR endpoints
    itr: {
        list: () =>
            API.request('/itr/filings'),
        
        get: (filingId) =>
            API.request(`/itr/filings/${filingId}`),
        
        create: (data) =>
            API.request('/itr/filings', {
                method: 'POST',
                body: JSON.stringify(data)
            }),
        
        update: (filingId, data) =>
            API.request(`/itr/filings/${filingId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            }),

        delete: (filingId) =>
            API.request(`/itr/filings/${filingId}`, { method: 'DELETE' }),

        submitForReview: (filingId) =>
            API.request(`/itr/filings/${filingId}/submit-review`, { method: 'POST' }),

        fileITR: (filingId) =>
            API.request(`/itr/filings/${filingId}/file`, { method: 'POST' }),
        
        getComputation: (filingId) =>
            API.request(`/itr/computations/${filingId}`),

        saveComputation: (data) =>
            API.request('/itr/computations', {
                method: 'POST',
                body: JSON.stringify(data)
            })
    },
    
    // CA Review endpoints
    review: {
        getFilings: (statusFilter = null) => {
            const params = statusFilter ? `?status=${statusFilter}` : '';
            return API.request(`/review/filings${params}`);
        },

        getStatements: (userId) =>
            API.request(`/review/statements/${userId}`),

        getTransactions: (userId, page = 1, pageSize = 50, filters = {}) => {
            const params = new URLSearchParams({
                page,
                page_size: pageSize,
                ...filters
            });
            return API.request(`/review/transactions/${userId}?${params}`);
        },
        
        updateCategory: (transactionId, category, notes) =>
            API.request(`/review/transactions/${transactionId}/category`, {
                method: 'PUT',
                body: JSON.stringify({ category, notes })
            }),
        
        getITR: (filingId) =>
            API.request(`/review/itr/${filingId}`),
        
        addComment: (filingId, comment, commentType = 'general') =>
            API.request(`/review/itr/${filingId}/comment`, {
                method: 'POST',
                body: JSON.stringify({ comment, comment_type: commentType })
            }),
        
        approveITR: (filingId, approved, caComments = null) =>
            API.request(`/review/itr/${filingId}/approve`, {
                method: 'POST',
                body: JSON.stringify({ approved, ca_comments: caComments })
            }),
        
        getSummary: (userId) =>
            API.request(`/review/summary/${userId}`),
        
        getDashboard: () =>
            API.request('/review/dashboard'),
        
        getAuditLogs: (page = 1, pageSize = 50, filters = {}) => {
            const params = new URLSearchParams({
                page,
                page_size: pageSize,
                ...filters
            });
            return API.request(`/review/audit-logs?${params}`);
        },

        exportITRPDF: (filingId) =>
            `${API_BASE_URL}/review/export/itr/${filingId}/pdf`,
        exportITRJSON: (filingId) =>
            API.request(`/review/export/itr/${filingId}/json`),
        exportTransactionsPDF: (statementId, userId) =>
            `${API_BASE_URL}/review/export/transactions/${statementId}/pdf?user_id=${userId}`,
        exportTransactionsJSON: (statementId, userId) =>
            API.request(`/review/export/transactions/${statementId}/json?user_id=${userId}`),
    },

    // Balance Sheet endpoints
    balanceSheet: {
        list: (sheetType = null, financialYear = null) => {
            const params = new URLSearchParams();
            if (sheetType) params.append('sheet_type', sheetType);
            if (financialYear) params.append('financial_year', financialYear);
            const qs = params.toString();
            return API.request(`/balance-sheet/${qs ? '?' + qs : ''}`);
        },

        get: (bsId) =>
            API.request(`/balance-sheet/${bsId}`),

        create: (data) =>
            API.request('/balance-sheet/', {
                method: 'POST',
                body: JSON.stringify(data)
            }),

        update: (bsId, data) =>
            API.request(`/balance-sheet/${bsId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            }),

        delete: (bsId) =>
            API.request(`/balance-sheet/${bsId}`, { method: 'DELETE' }),

        addItem: (bsId, data) =>
            API.request(`/balance-sheet/${bsId}/items`, {
                method: 'POST',
                body: JSON.stringify(data)
            }),

        updateItem: (itemId, data) =>
            API.request(`/balance-sheet/items/${itemId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            }),

        deleteItem: (itemId) =>
            API.request(`/balance-sheet/items/${itemId}`, { method: 'DELETE' }),

        getSummary: (financialYear) =>
            API.request(`/balance-sheet/summary?financial_year=${financialYear}`)
    },

    // Consolidation / Merge endpoints
    consolidation: {
        merge: (statementIds, financialYear) =>
            API.request('/consolidation/merge', {
                method: 'POST',
                body: JSON.stringify({ statement_ids: statementIds, financial_year: financialYear })
            }),

        calculateTax: (financialYear, taxRegime = 'both', statementIds = null) =>
            API.request('/consolidation/calculate-tax', {
                method: 'POST',
                body: JSON.stringify({ financial_year: financialYear, tax_regime: taxRegime, statement_ids: statementIds })
            }),

        createFiling: (financialYear, taxRegime = 'new', formType = 'ITR-1', statementIds = null) =>
            API.request('/consolidation/create-filing', {
                method: 'POST',
                body: JSON.stringify({ financial_year: financialYear, tax_regime: taxRegime, form_type: formType, statement_ids: statementIds })
            }),

        getSummary: (financialYear) =>
            API.request(`/consolidation/summary/${financialYear}`),
    },

    // Export endpoints
    export: {
        itrPDF: (filingId) =>
            `${API_BASE_URL}/export/itr/${filingId}/pdf`,
        itrJSON: (filingId) =>
            API.request(`/export/itr/${filingId}/json`),
        balanceSheetPDF: (bsId) =>
            `${API_BASE_URL}/export/balance-sheet/${bsId}/pdf`,
        balanceSheetJSON: (bsId) =>
            API.request(`/export/balance-sheet/${bsId}/json`),
        transactionsPDF: (statementId) =>
            `${API_BASE_URL}/export/transactions/${statementId}/pdf`,
        transactionsJSON: (statementId) =>
            API.request(`/export/transactions/${statementId}/json`),
        mergedPDF: (statementIds, financialYear) =>
            `${API_BASE_URL}/export/merged/pdf`,
        mergedJSON: (statementIds, financialYear) =>
            API.request('/export/merged/json', {
                method: 'POST',
                body: JSON.stringify({ statement_ids: statementIds, financial_year: financialYear })
            }),
        downloadMergedPDF: (statementIds, financialYear) => {
            const token = localStorage.getItem('authToken');
            return fetch(`${API_BASE_URL}/export/merged/pdf`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ statement_ids: statementIds, financial_year: financialYear })
            })
            .then(res => { if (!res.ok) throw new Error('Export failed'); return res.blob(); })
            .then(blob => {
                const a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = `Merged_Statement_${financialYear}.pdf`;
                a.click();
                URL.revokeObjectURL(a.href);
            });
        },
        downloadWithAuth: (url) => {
            const token = localStorage.getItem('authToken');
            return fetch(url, { headers: { 'Authorization': `Bearer ${token}` } })
                .then(res => {
                    if (!res.ok) throw new Error('Export failed');
                    return res.blob();
                })
                .then(blob => {
                    const a = document.createElement('a');
                    a.href = URL.createObjectURL(blob);
                    const cd = 'export';
                    a.download = url.split('/').pop() || 'export';
                    a.click();
                    URL.revokeObjectURL(a.href);
                });
        }
    },

    // Analytics endpoints
    analytics: {
        getSummary: (financialYear = null) => {
            const params = financialYear ? `?financial_year=${financialYear}` : '';
            return API.request(`/analytics/summary${params}`);
        },

        getIncomeTrends: (financialYear = null) => {
            const params = financialYear ? `?financial_year=${financialYear}` : '';
            return API.request(`/analytics/income-trends${params}`);
        },

        getExpenseBreakdown: (financialYear = null, type = 'expense') => {
            const params = new URLSearchParams();
            if (financialYear) params.append('financial_year', financialYear);
            params.append('type', type);
            return API.request(`/analytics/expense-breakdown?${params}`);
        },

        getTaxSavings: (financialYear = null) => {
            const params = financialYear ? `?financial_year=${financialYear}` : '';
            return API.request(`/analytics/tax-savings${params}`);
        },

        getYearComparison: () => API.request('/analytics/year-comparison')
    },

    // AI & Automation
    ai: {
        // Smart Categorization
        categorize: (description, amount, isCredit, date = null) => {
            return API.request('/ai/categorize', {
                method: 'POST',
                body: JSON.stringify({ description, amount, is_credit: isCredit, date })
            });
        },

        categorizeBulk: (transactions) => {
            return API.request('/ai/categorize-bulk', {
                method: 'POST',
                body: JSON.stringify({ transactions })
            });
        },

        autoCategorize: (statementId) => {
            return API.request(`/ai/auto-categorize/${statementId}`, { method: 'POST' });
        },

        learnCorrection: (description, correctCategory) => {
            return API.request('/ai/learn-correction', {
                method: 'POST',
                body: JSON.stringify({ description, correct_category: correctCategory })
            });
        },

        // Chatbot
        chat: (message) => {
            return API.request('/ai/chat', {
                method: 'POST',
                body: JSON.stringify({ message })
            });
        },

        getChatTopics: () => API.request('/ai/chat/topics'),

        // Anomaly Detection
        detectAnomalies: (statementId, sensitivity = 0.7) => {
            return API.request(`/ai/anomalies/${statementId}?sensitivity=${sensitivity}`);
        },

        detectAllAnomalies: (sensitivity = 0.7) => {
            return API.request(`/ai/anomalies-all?sensitivity=${sensitivity}`);
        },

        // Tax Optimization
        optimizeTax: (grossIncome, deductions) => {
            return API.request('/ai/optimize-tax', {
                method: 'POST',
                body: JSON.stringify({ gross_income: grossIncome, deductions })
            });
        },

        autoOptimizeTax: (financialYear = null) => {
            const params = financialYear ? `?financial_year=${financialYear}` : '';
            return API.request(`/ai/optimize-tax-auto${params}`);
        }
    }
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
}
