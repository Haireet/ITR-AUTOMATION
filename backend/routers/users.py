"""
Users router - handles user profile management
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import User, UserRole
from utils.security import get_current_user
from schemas import UserResponse, UserUpdate, MessageResponse

router = APIRouter()

def _normalized_role(user: User) -> str:
    if hasattr(user.role, "value"):
        return str(user.role.value).lower()
    return str(user.role).lower()


@router.get("/", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all users (CA/Admin only) — used for CA review user selection
    """
    if _normalized_role(current_user) not in ("admin", "auditor"):
        raise HTTPException(status_code=403, detail="CA/Admin access required")
    users = db.query(User).filter(User.is_active == True).order_by(User.full_name).all()
    return users


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current logged-in user profile"""
    return current_user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update current logged-in user profile"""
    # Check if PAN is being updated and already exists for another user
    if user_data.pan_number:
        existing = db.query(User).filter(
            User.pan_number == user_data.pan_number,
            User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="PAN number already registered")
    
    # Update fields if provided
    if user_data.full_name is not None:
        current_user.full_name = user_data.full_name
    if user_data.phone_number is not None:
        current_user.phone_number = user_data.phone_number
    if user_data.pan_number is not None:
        current_user.pan_number = user_data.pan_number
    
    db.commit()
    db.refresh(current_user)
    return current_user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update user profile (Admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.phone_number is not None:
        user.phone_number = user_data.phone_number
    if user_data.pan_number is not None:
        existing = db.query(User).filter(
            User.pan_number == user_data.pan_number,
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="PAN number already registered")
        user.pan_number = user_data.pan_number
    
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete user account (Admin only or self)"""
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    return MessageResponse(message="User deleted successfully")
