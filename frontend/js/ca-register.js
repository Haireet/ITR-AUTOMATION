/**
 * CA Registration Page Logic
 */
document.addEventListener('DOMContentLoaded', function () {
    if (Auth.isAuthenticated()) {
        window.location.href = 'dashboard.html';
        return;
    }

    const form = document.getElementById('caRegisterForm');
    const globalError = document.getElementById('globalError');
    const globalSuccess = document.getElementById('globalSuccess');
    const registerBtn = document.getElementById('registerBtn');
    const registerBtnText = document.getElementById('registerBtnText');
    const registerBtnLoader = document.getElementById('registerBtnLoader');

    function clearErrors() {
        document.querySelectorAll('.error-message').forEach(el => el.textContent = '');
        globalError.style.display = 'none';
        globalSuccess.style.display = 'none';
    }

    function showError(msg) {
        globalError.textContent = msg;
        globalError.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function showSuccess(msg) {
        globalSuccess.textContent = msg;
        globalSuccess.style.display = 'block';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Auto-uppercase PAN
    document.getElementById('pan').addEventListener('input', function () {
        this.value = this.value.toUpperCase();
    });

    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        clearErrors();

        const fullName = document.getElementById('fullName').value.trim();
        const email = document.getElementById('email').value.trim();
        const caLicense = document.getElementById('caLicense').value.trim();
        const phone = document.getElementById('phone').value.trim();
        const pan = document.getElementById('pan').value.trim();
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        const agreeTerms = document.getElementById('agreeTerms').checked;

        // Validation
        let hasErrors = false;

        if (!fullName) {
            document.getElementById('fullNameError').textContent = 'Full name is required';
            hasErrors = true;
        }
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            document.getElementById('emailError').textContent = 'Valid email is required';
            hasErrors = true;
        }
        if (!caLicense || caLicense.length < 6) {
            document.getElementById('caLicenseError').textContent = 'CA license number is required (min 6 characters)';
            hasErrors = true;
        }
        if (phone && !/^[6-9]\d{9}$/.test(phone)) {
            document.getElementById('phoneError').textContent = 'Enter a valid 10-digit mobile number';
            hasErrors = true;
        }
        if (pan && !/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(pan)) {
            document.getElementById('panError').textContent = 'Invalid PAN format';
            hasErrors = true;
        }
        if (!password || password.length < 8 || !/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/\d/.test(password)) {
            document.getElementById('passwordError').textContent = 'Password needs 8+ chars, uppercase, lowercase, and a digit';
            hasErrors = true;
        }
        if (password !== confirmPassword) {
            document.getElementById('confirmPasswordError').textContent = 'Passwords do not match';
            hasErrors = true;
        }
        if (!agreeTerms) {
            document.getElementById('agreeTermsError').textContent = 'You must agree to the terms';
            hasErrors = true;
        }

        if (hasErrors) return;

        // Submit
        registerBtn.disabled = true;
        registerBtnText.style.display = 'none';
        registerBtnLoader.style.display = 'inline-block';

        try {
            await API.auth.registerCA({
                email: email,
                password: password,
                full_name: fullName,
                phone_number: phone || null,
                pan_number: pan || null,
                ca_license_number: caLicense
            });

            showSuccess('✓ CA account created successfully! Redirecting to login...');
            form.reset();

            setTimeout(() => {
                window.location.href = 'login.html';
            }, 2000);
        } catch (error) {
            showError(error.message || 'Registration failed. Please try again.');
            registerBtn.disabled = false;
            registerBtnText.style.display = 'inline';
            registerBtnLoader.style.display = 'none';
        }
    });
});
