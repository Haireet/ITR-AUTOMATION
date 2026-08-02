/**
 * Login Page Logic
 */

document.addEventListener('DOMContentLoaded', function() {
    // Redirect if already logged in
    if (Auth.isAuthenticated()) {
        window.location.href = 'dashboard.html';
        return;
    }
    
    const loginForm = document.getElementById('loginForm');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const loginBtn = document.getElementById('loginBtn');
    const loginBtnText = document.getElementById('loginBtnText');
    const loginBtnLoader = document.getElementById('loginBtnLoader');
    const globalError = document.getElementById('globalError');
    
    // Clear error messages
    function clearErrors() {
        document.getElementById('emailError').textContent = '';
        document.getElementById('passwordError').textContent = '';
        globalError.style.display = 'none';
        globalError.textContent = '';
    }
    
    // Show error message
    function showError(message) {
        globalError.textContent = message;
        globalError.style.display = 'block';
    }
    
    // Validate email
    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    // Handle form submission
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        clearErrors();
        
        const email = emailInput.value.trim();
        const password = passwordInput.value;
        
        // Client-side validation
        if (!email) {
            document.getElementById('emailError').textContent = 'Email is required';
            return;
        }
        
        if (!validateEmail(email)) {
            document.getElementById('emailError').textContent = 'Please enter a valid email';
            return;
        }
        
        if (!password) {
            document.getElementById('passwordError').textContent = 'Password is required';
            return;
        }
        
        // Disable button and show loader
        loginBtn.disabled = true;
        loginBtnText.style.display = 'none';
        loginBtnLoader.style.display = 'inline-block';
        
        try {
            // Call login API
            const response = await API.auth.login(email, password);
            
            // Store authentication data
            Auth.setAuth(response.token.access_token, response.user);
            
            // Redirect to dashboard
            window.location.href = 'dashboard.html';
            
        } catch (error) {
            // Show error message
            showError(error.message || 'Login failed. Please check your credentials.');
            
            // Re-enable button
            loginBtn.disabled = false;
            loginBtnText.style.display = 'inline';
            loginBtnLoader.style.display = 'none';
        }
    });
    
    // Real-time email validation
    emailInput.addEventListener('blur', function() {
        const email = emailInput.value.trim();
        if (email && !validateEmail(email)) {
            document.getElementById('emailError').textContent = 'Please enter a valid email';
        } else {
            document.getElementById('emailError').textContent = '';
        }
    });
});