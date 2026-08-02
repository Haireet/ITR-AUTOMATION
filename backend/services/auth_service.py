"""
Authentication service - business logic for auth operations
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from models import User, AuditLog, UserRole
from schemas import UserRegister, UserLogin, Token, UserResponse, UserLoginResponse
from utils.security import (
    get_password_hash, 
    verify_password, 
    create_access_token
)
from config import settings


class AuthService:
    """Service class for authentication operations"""
    
    @staticmethod
    def register_user(db: Session, user_data: UserRegister, ip_address: str = None) -> UserResponse:
        """
        Register a new user
        
        Args:
            db: Database session
            user_data: User registration data
            ip_address: User's IP address for audit log
        
        Returns:
            Created user response
        
        Raises:
            HTTPException: If email or PAN already exists
        """
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Check if PAN already exists (if provided)
        if user_data.pan_number:
            existing_pan = db.query(User).filter(User.pan_number == user_data.pan_number).first()
            if existing_pan:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="PAN number already registered"
                )
        
        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Create new user
        new_user = User(
            email=user_data.email,
            password_hash=hashed_password,
            full_name=user_data.full_name,
            phone_number=user_data.phone_number,
            pan_number=user_data.pan_number,
            role=UserRole.USER,
            is_active=True,
            is_verified=False,
            created_at=datetime.utcnow()
        )
        
        try:
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            # Create audit log for registration
            AuthService._create_audit_log(
                db=db,
                user_id=new_user.id,
                action="user_registration",
                action_type="authentication",
                description=f"User registered with email: {user_data.email}",
                ip_address=ip_address,
                status="success"
            )
            
            return UserResponse.model_validate(new_user)
            
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User registration failed due to duplicate data"
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"User registration failed: {str(e)}"
            )
    
    @staticmethod
    def register_ca(db: Session, user_data: UserRegister, ca_license: str, ip_address: str = None) -> UserResponse:
        """
        Register a new CA/Auditor user.
        Requires a valid CA license number.
        """
        if not ca_license or len(ca_license.strip()) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Valid CA license/membership number is required (minimum 6 characters)"
            )

        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        if user_data.pan_number:
            existing_pan = db.query(User).filter(User.pan_number == user_data.pan_number).first()
            if existing_pan:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="PAN number already registered")

        hashed_password = get_password_hash(user_data.password)

        new_user = User(
            email=user_data.email,
            password_hash=hashed_password,
            full_name=user_data.full_name,
            phone_number=user_data.phone_number,
            pan_number=user_data.pan_number,
            role=UserRole.AUDITOR,
            is_active=True,
            is_verified=False,
            created_at=datetime.utcnow()
        )

        try:
            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            AuthService._create_audit_log(
                db=db,
                user_id=new_user.id,
                action="ca_registration",
                action_type="authentication",
                description=f"CA registered: {user_data.email}, license: {ca_license}",
                ip_address=ip_address,
                status="success"
            )

            return UserResponse.model_validate(new_user)

        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration failed due to duplicate data")
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Registration failed: {str(e)}")

    @staticmethod
    def authenticate_user(
        db: Session, 
        login_data: UserLogin, 
        ip_address: str = None,
        user_agent: str = None
    ) -> UserLoginResponse:
        """
        Authenticate user and return JWT token
        
        Args:
            db: Database session
            login_data: User login credentials
            ip_address: User's IP address for audit log
            user_agent: User's browser/client info
        
        Returns:
            Token and user response
        
        Raises:
            HTTPException: If credentials are invalid
        """
        # Get user by email
        user = db.query(User).filter(User.email == login_data.email).first()
        
        # Check if user exists
        if not user:
            AuthService._create_audit_log(
                db=db,
                user_id=None,
                action="login_failed",
                action_type="authentication",
                description=f"Login attempt with non-existent email: {login_data.email}",
                ip_address=ip_address,
                user_agent=user_agent,
                status="failed",
                error_message="User not found"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(login_data.password, user.password_hash):
            AuthService._create_audit_log(
                db=db,
                user_id=user.id,
                action="login_failed",
                action_type="authentication",
                description=f"Failed login attempt for user: {user.email}",
                ip_address=ip_address,
                user_agent=user_agent,
                status="failed",
                error_message="Invalid password"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Check if user is active
        if not user.is_active:
            AuthService._create_audit_log(
                db=db,
                user_id=user.id,
                action="login_failed",
                action_type="authentication",
                description=f"Login attempt by inactive user: {user.email}",
                ip_address=ip_address,
                user_agent=user_agent,
                status="failed",
                error_message="User account is inactive"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        # Update last login timestamp
        user.last_login = datetime.utcnow()
        db.commit()
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id},
            expires_delta=access_token_expires
        )
        
        # Create audit log for successful login
        AuthService._create_audit_log(
            db=db,
            user_id=user.id,
            action="login_success",
            action_type="authentication",
            description=f"User logged in: {user.email}",
            ip_address=ip_address,
            user_agent=user_agent,
            status="success"
        )
        
        # Return token and user data
        token = Token(access_token=access_token, token_type="bearer")
        user_response = UserResponse.model_validate(user)
        
        return UserLoginResponse(token=token, user=user_response)
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User:
        """
        Get user by email
        
        Args:
            db: Database session
            email: User email address
        
        Returns:
            User object or None
        """
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def _create_audit_log(
        db: Session,
        user_id: int,
        action: str,
        action_type: str,
        description: str = None,
        ip_address: str = None,
        user_agent: str = None,
        status: str = "success",
        error_message: str = None
    ):
        """
        Internal method to create audit log entries
        
        Args:
            db: Database session
            user_id: User ID (can be None for failed login attempts)
            action: Action performed
            action_type: Type of action
            description: Detailed description
            ip_address: User's IP address
            user_agent: User's browser/client info
            status: Action status (success/failed/warning)
            error_message: Error message if action failed
        """
        try:
            audit_log = AuditLog(
                user_id=user_id,
                action=action,
                action_type=action_type,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                status=status,
                error_message=error_message,
                timestamp=datetime.utcnow()
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            db.rollback()
            print(f"Failed to create audit log: {str(e)}")
