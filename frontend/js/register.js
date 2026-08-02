/**
 * Registration Page Logic
 */

document.addEventListener('DOMContentLoaded', function() {
    // Redirect if already logged in
    if (Auth.isAuthenticated()) {
        window.location.href = 'dashboard.html';
        return;
    }
    
    const registerForm = document.getElementById('registerForm');
    const fullNameInput = document.getElementById('fullName');
    const emailInput = document.getElementById('email');
    const phoneInput = document.getElementById('phone');
    const panInput = document.getElementById('pan');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const agreeTermsCheckbox = document.getElementById('agreeTerms');
    
    const registerBtn = document.getElementById('registerBtn');
    const registerBtnText = document.getElementById('registerBtnText');
    const registerBtnLoader = document.getElementById('registerBtnLoader');
    
    const globalError = document.getElementById('globalError');
    const globalSuccess = document.getElementById('globalSuccess');
    
    // Clear error messages
    function clearErrors() {
        document.getElementById('fullNameError').textContent = '';
        document.getElementById('emailError').textContent = '';
        document.getElementById('phoneError').textContent = '';
        document.getElementById('panError').textContent = '';
        document.getElementById('passwordError').textContent = '';
        document.getElementById('confirmPasswordError').textContent = '';
        document.getElementById('agreeTermsError').textContent = '';
        globalError.style.display = 'none';
        globalError.textContent = '';
        globalSuccess.style.display = 'none';
        globalSuccess.textContent = '';
    }
    
    // Show error message
    function showError(message) {
        globalError.textContent = message;
        globalError.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    
    // Show success message
    function showSuccess(message) {
        globalSuccess.textContent = message;
        globalSuccess.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    
    // Validate email
    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }
    
    // Validate phone number (Indian format)
    function validatePhone(phone) {
        if (!phone) return true; // Optional field
        const re = /^[6-9]\d{9}$/;
        return re.test(phone);
    }
    
    // Validate PAN format
    function validatePAN(pan) {
        if (!pan) return true; // Optional field
        const re = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/;
        return re.test(pan.toUpperCase());
    }
    
    // Validate password strength
    function validatePassword(password) {
        const errors = [];
        
        if (password.length < 8) {
            errors.push('at least 8 characters');
        }
        if (!/[A-Z]/.test(password)) {
            errors.push('one uppercase letter');
        }
        if (!/[a-z]/.test(password)) {
            errors.push('one lowercase letter');
        }
        if (!/\d/.test(password)) {
            errors.push('one number');
        }
        
        return {
            isValid: errors.length === 0,
            message: errors.length > 0 ? `Password must contain ${errors.join(', ')}` : ''
        };
    }
    
    // Real-time validation
    emailInput.addEventListener('blur', function() {
        const email = emailInput.value.trim();
        if (email && !validateEmail(email)) {
            document.getElementById('emailError').textContent = 'Please enter a valid email address';
        } else {
            document.getElementById('emailError').textContent = '';
        }
    });
    
    phoneInput.addEventListener('blur', function() {
        const phone = phoneInput.value.trim();
        if (phone && !validatePhone(phone)) {
            document.getElementById('phoneError').textContent = 'Please enter a valid 10-digit mobile number starting with 6-9';
        } else {
            document.getElementById('phoneError').textContent = '';
        }
    });
    
    panInput.addEventListener('blur', function() {
        const pan = panInput.value.trim();
        if (pan && !validatePAN(pan)) {
            document.getElementById('panError').textContent = 'Invalid PAN format. Expected: ABCDE1234F';
        } else {
            document.getElementById('panError').textContent = '';
        }
    });
    
    passwordInput.addEventListener('blur', function() {
        const password = passwordInput.value;
        const validation = validatePassword(password);
        if (password && !validation.isValid) {
            document.getElementById('passwordError').textContent = validation.message;
        } else {
            document.getElementById('passwordError').textContent = '';
        }
    });
    
    confirmPasswordInput.addEventListener('blur', function() {
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        if (confirmPassword && password !== confirmPassword) {
            document.getElementById('confirmPasswordError').textContent = 'Passwords do not match';
        } else {
            document.getElementById('confirmPasswordError').textContent = '';
        }
    });
    
    // Auto-uppercase PAN input
    panInput.addEventListener('input', function() {
        this.value = this.value.toUpperCase();
    });
    
    // Handle form submission
    registerForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        clearErrors();
        
        const fullName = fullNameInput.value.trim();
        const email = emailInput.value.trim();
        const phone = phoneInput.value.trim();
        const pan = panInput.value.trim();
        const password = passwordInput.value;
        const confirmPassword = confirmPasswordInput.value;
        const agreeTerms = agreeTermsCheckbox.checked;
        
        // Client-side validation
        let hasErrors = false;
        
        if (!fullName) {
            document.getElementById('fullNameError').textContent = 'Full name is required';
            hasErrors = true;
        }
        
        if (!email) {
            document.getElementById('emailError').textContent = 'Email is required';
            hasErrors = true;
        } else if (!validateEmail(email)) {
            document.getElementById('emailError').textContent = 'Please enter a valid email';
            hasErrors = true;
        }
        
        if (phone && !validatePhone(phone)) {
            document.getElementById('phoneError').textContent = 'Please enter a valid mobile number';
            hasErrors = true;
        }
        
        if (pan && !validatePAN(pan)) {
            document.getElementById('panError').textContent = 'Invalid PAN format';
            hasErrors = true;
        }
        
        if (!password) {
            document.getElementById('passwordError').textContent = 'Password is required';
            hasErrors = true;
        } else {
            const validation = validatePassword(password);
            if (!validation.isValid) {
                document.getElementById('passwordError').textContent = validation.message;
                hasErrors = true;
            }
        }
        
        if (!confirmPassword) {
            document.getElementById('confirmPasswordError').textContent = 'Please confirm your password';
            hasErrors = true;
        } else if (password !== confirmPassword) {
            document.getElementById('confirmPasswordError').textContent = 'Passwords do not match';
            hasErrors = true;
        }
        
        if (!agreeTerms) {
            document.getElementById('agreeTermsError').textContent = 'You must agree to the terms';
            hasErrors = true;
        }
        
        if (hasErrors) {
            return;
        }
        
        // Disable button and show loader
        registerBtn.disabled = true;
        registerBtnText.style.display = 'none';
        registerBtnLoader.style.display = 'inline-block';
        
        try {
            // Prepare registration data
            const registrationData = {
                email: email,
                password: password,
                full_name: fullName,
                phone_number: phone || null,
                pan_number: pan || null
            };
            
            // Call registration API
            const response = await API.auth.register(registrationData);
            
            // Show success message
            showSuccess('✓ Account created successfully! Redirecting to login...');
            
            // Clear form
            registerForm.reset();
            
            // Redirect to login after 2 seconds
            setTimeout(() => {
                window.location.href = 'login.html';
            }, 2000);
            
        } catch (error) {
            // Show error message
            showError(error.message || 'Registration failed. Please try again.');
            
            // Re-enable button
            registerBtn.disabled = false;
            registerBtnText.style.display = 'inline';
            registerBtnLoader.style.display = 'none';
        }
    });
});