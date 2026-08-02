"""
Pydantic schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import re

# ============== Auth Schemas ==============

class UserRegister(BaseModel):
    """Schema for user registration"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., 
        min_length=8, 
        max_length=100,
        description="Password (min 8 characters)"
    )
    full_name: str = Field(
        ..., 
        min_length=2, 
        max_length=100,
        description="User full name"
    )
    phone_number: Optional[str] = Field(
        None, 
        pattern=r'^[6-9][0-9]{9}$',
        description="Indian mobile number (10 digits starting with 6-9)"
    )
    pan_number: Optional[str] = Field(
        None,
        pattern=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$',
        description="PAN card number (Format: ABCDE1234F)"
    )
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'\d', v):
            raise ValueError('Password must contain at least one digit')
        return v
    
    @field_validator('pan_number')
    @classmethod
    def validate_pan_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate and uppercase PAN number"""
        if v:
            v = v.upper()
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v):
                raise ValueError('Invalid PAN format. Expected: ABCDE1234F')
        return v

class CARegister(UserRegister):
    """Schema for CA registration — extends user registration with license number"""
    ca_license_number: str = Field(
        ...,
        min_length=6,
        max_length=20,
        description="ICAI Membership / CA License Number"
    )

class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

class Token(BaseModel):
    """Schema for JWT token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")

class TokenData(BaseModel):
    """Schema for decoded token data"""
    email: Optional[str] = None
    user_id: Optional[int] = None

# ============== User Response Schemas ==============

class UserResponse(BaseModel):
    """Schema for user data response"""
    id: int
    email: str
    full_name: str
    role: str
    pan_number: Optional[str] = None
    phone_number: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    
    model_config = {
        "from_attributes": True
    }

class UserUpdate(BaseModel):
    """Schema for updating user profile"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=100)
    phone_number: Optional[str] = Field(None, pattern=r'^[6-9][0-9]{9}$')
    pan_number: Optional[str] = Field(None, pattern=r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$')
    
    @field_validator('pan_number')
    @classmethod
    def validate_pan_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate and uppercase PAN number"""
        if v:
            v = v.upper()
            if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', v):
                raise ValueError('Invalid PAN format. Expected: ABCDE1234F')
        return v

class UserLoginResponse(BaseModel):
    """Schema for successful login response"""
    token: Token
    user: UserResponse

# ============== Generic Response Schemas ==============

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str = Field(..., description="Response message")
    detail: Optional[str] = Field(None, description="Additional details")

class ErrorResponse(BaseModel):
    """Error response schema"""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")

# ============== ITR Schemas ==============

class ITRFilingBase(BaseModel):
    """Base schema for ITR filing"""
    assessment_year: str = Field(..., pattern=r'^\d{4}-\d{2}$')
    form_type: str = Field(..., pattern=r'^ITR-[1-7]$')

class ITRFilingCreate(ITRFilingBase):
    """Schema for creating ITR filing"""
    data: Optional[str] = None

class ITRFilingUpdate(BaseModel):
    """Schema for updating ITR filing"""
    data: Optional[str] = None
    status: Optional[str] = Field(None, pattern=r'^(draft|completed|filed)$')
    acknowledgement_number: Optional[str] = None

class ITRFilingResponse(ITRFilingBase):
    """Schema for ITR filing response"""
    id: int
    user_id: int
    status: str
    review_status: str = "pending_review"
    filing_date: Optional[datetime]
    acknowledgement_number: Optional[str]
    ca_comments: Optional[str] = None
    reviewed_by: Optional[int] = None
    approved_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = {
        "from_attributes": True
    }

# ============== Tax Computation Schemas ==============

class TaxComputationBase(BaseModel):
    """Base schema for tax computation"""
    gross_total_income: float = 0.0
    total_deductions: float = 0.0
    taxable_income: float = 0.0
    tax_on_total_income: float = 0.0
    rebate_87a: float = 0.0
    health_education_cess: float = 0.0
    total_tax_liability: float = 0.0
    tax_regime: str = Field(default="old", pattern=r'^(old|new)$')

class TaxComputationCreate(TaxComputationBase):
    """Schema for creating tax computation"""
    itr_filing_id: int

class TaxComputationResponse(TaxComputationBase):
    """Schema for tax computation response"""
    id: int
    itr_filing_id: int
    created_at: datetime
    
    model_config = {
        "from_attributes": True
    }
