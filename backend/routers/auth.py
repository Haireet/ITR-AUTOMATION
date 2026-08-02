"""
Authentication router - handles login, register, token management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import get_db
from schemas import (
    UserRegister, 
    UserLogin, 
    UserResponse, 
    UserLoginResponse,
    MessageResponse,
    CARegister
)
from services.auth_service import AuthService
from utils.security import get_current_user
from models import User

router = APIRouter()


@router.post(
    "/register", 
    response_model=UserResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Register a new user account with email, password, and profile information"
)
async def register(
    user_data: UserRegister, 
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new user account
    
    - **email**: Valid email address (must be unique)
    - **password**: Strong password (min 8 chars, uppercase, lowercase, digit)
    - **full_name**: User's full name
    - **phone_number**: Optional Indian mobile number (10 digits, starts with 6-9)
    - **pan_number**: Optional PAN card number (format: ABCDE1234F)
    
    Returns:
        UserResponse: Created user details (without password)
    
    Raises:
        400: Email or PAN already registered
        422: Validation error (invalid format)
        500: Server error
    """
    # Get client IP address
    ip_address = request.client.host if request.client else None
    
    # Register user
    return AuthService.register_user(db, user_data, ip_address)


@router.post(
    "/register-ca",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register CA / Chartered Accountant",
    description="Register a Chartered Accountant account with ICAI membership number"
)
async def register_ca(
    ca_data: CARegister,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new CA account

    - **ca_license_number**: ICAI Membership Number (min 6 chars)
    - All other fields same as regular registration
    - Account is created with AUDITOR role (CA access)
    """
    ip_address = request.client.host if request.client else None
    return AuthService.register_ca(db, ca_data, ca_data.ca_license_number, ip_address)


@router.post(
    "/login", 
    response_model=UserLoginResponse,
    summary="User login",
    description="Authenticate user and receive JWT access token"
)
async def login(
    login_data: UserLogin, 
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token
    
    - **email**: Registered email address
    - **password**: User password
    
    Returns:
        UserLoginResponse: JWT token and user details
        - token: JWT access token (expires in 30 minutes by default)
        - user: User profile information
    
    Raises:
        401: Invalid credentials
        403: Account inactive
        422: Validation error
    
    Example:
        ```
        {
          "email": "user@example.com",
          "password": "SecurePass123"
        }
        ```
    
    Response:
        ```
        {
          "token": {
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
            "token_type": "bearer"
          },
          "user": {
            "id": 1,
            "email": "user@example.com",
            "full_name": "John Doe",
            ...
          }
        }
        ```
    """
    # Get client IP and user agent for audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    
    # Authenticate user
    return AuthService.authenticate_user(db, login_data, ip_address, user_agent)


@router.post(
    "/logout", 
    response_model=MessageResponse,
    summary="User logout",
    description="Logout user (client-side token removal)"
)
async def logout():
    """
    Logout user
    
    Note: JWT tokens are stateless, so logout is handled client-side
    by removing the token from storage. This endpoint confirms the action.
    
    Returns:
        MessageResponse: Logout confirmation
    """
    return MessageResponse(
        message="Logged out successfully",
        detail="Please remove the access token from client storage"
    )


@router.get(
    "/me", 
    response_model=UserResponse,
    summary="Get current user",
    description="Get currently authenticated user's profile"
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user details
    
    Requires: Authorization header with valid JWT token
    
    Header:
        Authorization: Bearer <access_token>
    
    Returns:
        UserResponse: Current user's profile information
    
    Raises:
        401: Invalid or expired token
        403: Inactive user account
    """
    return UserResponse.model_validate(current_user)


@router.post(
    "/refresh",
    response_model=UserLoginResponse,
    summary="Refresh access token",
    description="Get a new access token for authenticated user"
)
async def refresh_token(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Refresh access token
    
    Requires: Authorization header with valid JWT token
    
    Returns:
        UserLoginResponse: New JWT token and user details
    
    Note: This generates a fresh token with updated expiration time.
    The old token will remain valid until its expiration.
    """
    from datetime import timedelta
    from utils.security import create_access_token
    from schemas import Token
    from config import settings
    
    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": current_user.email, "user_id": current_user.id},
        expires_delta=access_token_expires
    )
    
    # Create audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent", None)
    
    AuthService._create_audit_log(
        db=db,
        user_id=current_user.id,
        action="token_refresh",
        action_type="authentication",
        description=f"Token refreshed for user: {current_user.email}",
        ip_address=ip_address,
        user_agent=user_agent,
        status="success"
    )
    
    token = Token(access_token=access_token, token_type="bearer")
    user_response = UserResponse.model_validate(current_user)
    
    return UserLoginResponse(token=token, user=user_response)
