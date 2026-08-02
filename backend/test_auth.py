"""
Test script for authentication endpoints
Run after starting the server: python main.py
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/auth"

def test_register():
    """Test user registration"""
    print("=" * 50)
    print("Testing User Registration")
    print("=" * 50)
    
    data = {
        "email": "test@example.com",
        "password": "SecurePass123",
        "full_name": "Test User",
        "phone_number": "9876543210",
        "pan_number": "ABCDE1234F"
    }
    
    response = requests.post(f"{BASE_URL}/register", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()
    
    return response.json()

def test_login():
    """Test user login"""
    print("=" * 50)
    print("Testing User Login")
    print("=" * 50)
    
    data = {
        "email": "test@example.com",
        "password": "SecurePass123"
    }
    
    response = requests.post(f"{BASE_URL}/login", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()
    
    if response.status_code == 200:
        return response.json()["token"]["access_token"]
    return None

def test_get_current_user(token):
    """Test getting current user profile"""
    print("=" * 50)
    print("Testing Get Current User")
    print("=" * 50)
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.get(f"{BASE_URL}/me", headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_refresh_token(token):
    """Test token refresh"""
    print("=" * 50)
    print("Testing Token Refresh")
    print("=" * 50)
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    response = requests.post(f"{BASE_URL}/refresh", headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_duplicate_registration():
    """Test duplicate email registration"""
    print("=" * 50)
    print("Testing Duplicate Registration (Should Fail)")
    print("=" * 50)
    
    data = {
        "email": "test@example.com",
        "password": "AnotherPass456",
        "full_name": "Another User"
    }
    
    response = requests.post(f"{BASE_URL}/register", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_invalid_login():
    """Test login with wrong password"""
    print("=" * 50)
    print("Testing Invalid Login (Should Fail)")
    print("=" * 50)
    
    data = {
        "email": "test@example.com",
        "password": "WrongPassword123"
    }
    
    response = requests.post(f"{BASE_URL}/login", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_weak_password():
    """Test registration with weak password"""
    print("=" * 50)
    print("Testing Weak Password (Should Fail)")
    print("=" * 50)
    
    data = {
        "email": "weak@example.com",
        "password": "weak",
        "full_name": "Weak User"
    }
    
    response = requests.post(f"{BASE_URL}/register", json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

if __name__ == "__main__":
    print("\n🚀 Starting Auto ITR Authentication Tests\n")
    
    # Test 1: Register new user
    test_register()
    
    # Test 2: Login
    token = test_login()
    
    if token:
        # Test 3: Get current user
        test_get_current_user(token)
        
        # Test 4: Refresh token
        test_refresh_token(token)
    
    # Test 5: Duplicate registration
    test_duplicate_registration()
    
    # Test 6: Invalid login
    test_invalid_login()
    
    # Test 7: Weak password
    test_weak_password()
    
    print("\n✅ All tests completed!\n")
