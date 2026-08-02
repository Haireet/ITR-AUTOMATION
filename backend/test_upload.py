"""
Test script for bank statement upload functionality
Run after starting the server and creating a test user
"""
import requests
import json
import io

BASE_URL = "http://localhost:8000/api"

# First, login to get token
def get_auth_token():
    """Login and get authentication token"""
    print("=" * 50)
    print("Getting Authentication Token")
    print("=" * 50)
    
    # Register a test user first (if not exists)
    register_data = {
        "email": "test@example.com",
        "password": "SecurePass123",
        "full_name": "Test User"
    }
    
    # Try to register (may fail if user exists)
    try:
        requests.post(f"{BASE_URL}/auth/register", json=register_data)
    except:
        pass
    
    # Login
    login_data = {
        "email": "test@example.com",
        "password": "SecurePass123"
    }
    
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code == 200:
        token = response.json()["token"]["access_token"]
        print(f"✓ Got token: {token[:20]}...")
        print()
        return token
    else:
        print(f"✗ Login failed: {response.text}")
        return None

def test_upload_csv(token):
    """Test CSV file upload"""
    print("=" * 50)
    print("Testing CSV Upload")
    print("=" * 50)
    
    # Create a sample CSV file in memory
    csv_content = """Date,Description,Debit,Credit,Balance
2024-01-01,Opening Balance,,,10000.00
2024-01-05,Salary Credit,,50000.00,60000.00
2024-01-10,Rent Payment,15000.00,,45000.00
2024-01-15,Grocery Shopping,2500.00,,42500.00
"""
    
    files = {
        'file': ('test_statement.csv', io.BytesIO(csv_content.encode()), 'text/csv')
    }
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    response = requests.post(
        f"{BASE_URL}/statements/upload",
        files=files,
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()
    
    if response.status_code == 201:
        return response.json()["statement"]["id"]
    return None

def test_upload_invalid_type(token):
    """Test upload with invalid file type"""
    print("=" * 50)
    print("Testing Invalid File Type (Should Fail)")
    print("=" * 50)
    
    # Create a text file (not allowed)
    text_content = "This is not a valid statement file"
    
    files = {
        'file': ('invalid.txt', io.BytesIO(text_content.encode()), 'text/plain')
    }
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    response = requests.post(
        f"{BASE_URL}/statements/upload",
        files=files,
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_upload_large_file(token):
    """Test upload with large file"""
    print("=" * 50)
    print("Testing Large File Upload (Should Fail)")
    print("=" * 50)
    
    # Create a file larger than 10 MB
    large_content = "X" * (11 * 1024 * 1024)  # 11 MB
    
    files = {
        'file': ('large_statement.csv', io.BytesIO(large_content.encode()), 'text/csv')
    }
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    response = requests.post(
        f"{BASE_URL}/statements/upload",
        files=files,
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_get_statements(token):
    """Test getting user's statements"""
    print("=" * 50)
    print("Testing Get User Statements")
    print("=" * 50)
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    response = requests.get(
        f"{BASE_URL}/statements",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_get_statement_by_id(token, statement_id):
    """Test getting specific statement"""
    print("=" * 50)
    print(f"Testing Get Statement by ID: {statement_id}")
    print("=" * 50)
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    response = requests.get(
        f"{BASE_URL}/statements/{statement_id}",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_delete_statement(token, statement_id):
    """Test deleting statement"""
    print("=" * 50)
    print(f"Testing Delete Statement: {statement_id}")
    print("=" * 50)
    
    headers = {
        'Authorization': f'Bearer {token}'
    }
    
    response = requests.delete(
        f"{BASE_URL}/statements/{statement_id}",
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_upload_without_auth():
    """Test upload without authentication"""
    print("=" * 50)
    print("Testing Upload Without Authentication (Should Fail)")
    print("=" * 50)
    
    csv_content = "Date,Description,Amount\n2024-01-01,Test,100"
    
    files = {
        'file': ('test.csv', io.BytesIO(csv_content.encode()), 'text/csv')
    }
    
    response = requests.post(
        f"{BASE_URL}/statements/upload",
        files=files
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

if __name__ == "__main__":
    print("\n🚀 Starting Bank Statement Upload Tests\n")
    
    # Test 1: Get authentication token
    token = get_auth_token()
    
    if not token:
        print("✗ Failed to get authentication token. Exiting.")
        exit(1)
    
    # Test 2: Upload CSV file
    statement_id = test_upload_csv(token)
    
    # Test 3: Get all statements
    test_get_statements(token)
    
    if statement_id:
        # Test 4: Get specific statement
        test_get_statement_by_id(token, statement_id)
    
    # Test 5: Invalid file type
    test_upload_invalid_type(token)
    
    # Test 6: Large file
    test_upload_large_file(token)
    
    # Test 7: Upload without auth
    test_upload_without_auth()
    
    if statement_id:
        # Test 8: Delete statement
        test_delete_statement(token, statement_id)
    
    print("\n✅ All upload tests completed!\n")
