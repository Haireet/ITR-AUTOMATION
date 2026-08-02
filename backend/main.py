"""
Auto ITR - FastAPI Backend
Main application entry point
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from database import engine, Base
from routers import auth, users, itr, statements, review, balance_sheet, export, consolidation, analytics, ai

# Import all models so they're registered with Base.metadata
from models import (
    User, BankStatement, Transaction, 
    AuditLog, ITRFiling, TaxComputation,
    BalanceSheet, BalanceSheetItem
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler - creates tables on startup"""
    # Startup: Create database tables
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables created")
    yield
    # Shutdown: cleanup if needed
    print("[OK] Application shutdown")

# Initialize FastAPI app
app = FastAPI(
    title="Auto ITR API",
    description="Automated Income Tax Return Filing System for India",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Auto ITR API",
        "version": "1.0.0"
    }

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(itr.router, prefix="/api/itr", tags=["ITR"])
app.include_router(statements.router, prefix="/api/statements", tags=["Bank Statements"])
app.include_router(review.router, prefix="/api/review", tags=["CA Review"])
app.include_router(balance_sheet.router, prefix="/api/balance-sheet", tags=["Balance Sheet"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(consolidation.router, prefix="/api/consolidation", tags=["Consolidation"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI & Automation"])

# Serve frontend static files (must be LAST — API routes take priority)
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
