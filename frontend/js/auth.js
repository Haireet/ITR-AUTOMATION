/**
 * Authentication Module
 * Handles user authentication state
 */

const Auth = {
    normalizeRole(role) {
        return String(role || '').toLowerCase();
    },
    /**
     * Check if user is authenticated
     */
    isAuthenticated() {
        const token = localStorage.getItem('authToken');
        return !!token;
    },
    
    /**
     * Get stored user data
     */
    getUserData() {
        const userData = localStorage.getItem('userData');
        if (!userData) return null;
        try {
            return JSON.parse(userData);
        } catch (e) {
            console.error('Invalid userData in localStorage, clearing it.', e);
            localStorage.removeItem('userData');
            return null;
        }
    },
    
    /**
     * Store authentication data
     */
    setAuth(token, userData) {
        localStorage.setItem('authToken', token);
        localStorage.setItem('userData', JSON.stringify(userData));
    },
    
    /**
     * Clear authentication data
     */
    clearAuth() {
        localStorage.removeItem('authToken');
        localStorage.removeItem('userData');
    },
    
    /**
     * Redirect to login if not authenticated
     */
    requireAuth() {
        if (!this.isAuthenticated()) {
            window.location.href = 'login.html';
            return false;
        }
        return true;
    },
    
    /**
     * Check if user has specific role
     */
    hasRole(role) {
        const userData = this.getUserData();
        return userData && this.normalizeRole(userData.role) === this.normalizeRole(role);
    },
    
    /**
     * Check if user is CA/Admin/Auditor
     */
    isReviewer() {
        const userData = this.getUserData();
        if (!userData) return false;
        return ['admin', 'auditor'].includes(this.normalizeRole(userData.role));
    },

    /**
     * Check if user is regular user (not CA)
     */
    isRegularUser() {
        const userData = this.getUserData();
        return userData && this.normalizeRole(userData.role) === 'user';
    },

    /**
     * Redirect CA to their dashboard if they access user-only pages
     */
    requireRegularUser() {
        if (!this.requireAuth()) return false;
        if (this.isReviewer()) {
            window.location.href = 'ca-review.html';
            return false;
        }
        return true;
    },

    /**
     * Redirect regular users away from CA-only pages
     */
    requireReviewer() {
        if (!this.requireAuth()) return false;
        if (!this.isReviewer()) {
            window.location.href = 'dashboard.html';
            return false;
        }
        return true;
    }
};

// Logout functionality (used across all pages)
document.addEventListener('DOMContentLoaded', function() {
    const logoutBtn = document.getElementById('logoutBtn');
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function() {
            if (confirm('Are you sure you want to logout?')) {
                Auth.clearAuth();
                window.location.href = 'login.html';
            }
        });
    }
    
    // Display user name in navbar
    const userNameEl = document.getElementById('userName');
    if (userNameEl) {
        const userData = Auth.getUserData();
        if (userData) {
            userNameEl.textContent = userData.full_name || userData.email;
        }
    }
    
    // Show/hide CA review link based on role
    const caReviewLink = document.getElementById('caReviewLink');
    if (caReviewLink && Auth.isReviewer()) {
        caReviewLink.style.display = 'block';
    }
});
