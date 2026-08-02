"""
Custom validators for Indian tax-specific validations
"""
import re
from typing import Optional

def validate_pan(pan: str) -> bool:
    """
    Validate PAN number format
    Format: ABCDE1234F
    - First 5 characters: Alphabets
    - Next 4 characters: Numbers
    - Last character: Alphabet
    """
    pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$'
    return bool(re.match(pattern, pan))

def validate_aadhaar(aadhaar: str) -> bool:
    """
    Validate Aadhaar number format
    Format: 12 digit number
    """
    pattern = r'^\d{12}$'
    return bool(re.match(pattern, aadhaar))

def validate_assessment_year(year: str) -> bool:
    """
    Validate assessment year format
    Format: YYYY-YY (e.g., 2024-25)
    """
    pattern = r'^\d{4}-\d{2}$'
    if not re.match(pattern, year):
        return False
    
    # Validate year continuity
    start_year = int(year[:4])
    end_year = int(year[5:])
    expected_end = (start_year + 1) % 100
    
    return end_year == expected_end

def validate_ifsc(ifsc: str) -> bool:
    """
    Validate IFSC code format
    Format: 4 letters + 0 + 6 alphanumeric
    Example: SBIN0001234
    """
    pattern = r'^[A-Z]{4}0[A-Z0-9]{6}$'
    return bool(re.match(pattern, ifsc))

def validate_gstin(gstin: str) -> bool:
    """
    Validate GSTIN format
    Format: 15 characters
    - 2 digits (state code)
    - 10 characters (PAN)
    - 1 digit (entity number)
    - 1 character (Z by default)
    - 1 check digit
    """
    pattern = r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}[Z]{1}[A-Z\d]{1}$'
    return bool(re.match(pattern, gstin))

def validate_mobile_number(mobile: str) -> bool:
    """
    Validate Indian mobile number
    Format: 10 digits starting with 6-9
    """
    pattern = r'^[6-9]\d{9}$'
    return bool(re.match(pattern, mobile))
