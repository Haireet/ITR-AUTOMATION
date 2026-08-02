# Auto ITR — Research & System Overview
Automated Indian Income Tax Return assistant that ingests bank statements, auto-categorizes transactions, generates analytics and tax optimizations, and supports CA review. Backend is FastAPI + SQLite/SQLAlchemy; frontend is static HTML/CSS/JS served by the API.

## Abstract
Auto ITR reduces taxpayer effort by turning raw bank statements into tax-ready data. It couples deterministic tax rules with heuristic AI: a smart categorizer, anomaly detector, tax optimizer, and an Indian-tax chatbot (KB-first with optional LLM). CA review provides human assurance before filing.

## Problem & Objectives
- Problem: Manual statement cleanup and tax computation are error-prone, especially when mixing salary, investments, and deductions (80C/80D/24b/80CCD) across banks.
- Objectives: (1) Automate ingestion and categorization; (2) Surface anomalies and tax-saving gaps early; (3) Provide explainable suggestions; (4) Keep a CA-in-the-loop for compliance; (5) Offer defensible, auditable outputs.

## Architecture
- Backend: FastAPI app (`backend/main.py`) with routers for auth, users, statements, analytics, AI, ITR, balance sheet, review, export, consolidation.
- Data: SQLite (`auto_itr.db`) via SQLAlchemy models (users, bank_statements, transactions, audit_logs, itr_filings, tax_computations, balance_sheets/items).
- Frontend: Static HTML/CSS/JS (dashboard, uploads, merge, transactions, analytics, balance sheet, CA review, chatbot) served via FastAPI `StaticFiles`.
- Security: JWT (python-jose) + bcrypt password hashing; CORS-configurable; audit logging on key operations.
- Files: Uploaded under `uploads/bank_statements/{userId}`; parsers (CSV/XLS/XLSX/PDF) via ParserFactory, pandas, pdfplumber, tabula-py, PyPDF2.

## Data Flow
1) User uploads statement → StatementService validates size/type → saves file → audit log.
2) Process statement → ParserFactory extracts transactions → TransactionClassifier seeds categories/confidence → DB persist.
3) Optional auto-categorize uncategorized → SmartCategorizer refines labels using patterns, amounts, dates, recurrence, and user-learned corrections.
4) Analytics endpoints aggregate income/expense/deductions, compute monthly trends, tax estimates, tax-saving suggestions.
5) AI endpoints: chatbot (KB-first, optional OpenAI), anomaly detection (z-score/duplicate/category checks), tax optimizer (old vs new regime).
6) CA review/export: reviewers can inspect, approve, and export filings (PDF via fpdf2).

## Algorithms & Heuristics
- SmartCategorizer: keyword/pattern matching, amount ranges, typical day-of-month (salary), recurrence detection; confidence thresholds (0.5/0.7/0.9); user corrections stored per user to personalize.
- AnomalyDetector: mean/std baseline with z-score outliers, round-amount flags, duplicates (amount+desc+date key), category vs credit/debit mismatch, large-cash keywords; severity-ranked summaries.
- TaxOptimizer: computes taxable income for old/new regimes, applies 87A rebate, 4% cess, break-even deduction estimate, regime recommendation with tips (e.g., max 80C/NPS/80D).
- Analytics: sums income vs expenses/deductions per category, monthly trends, yearly comparisons; tax-saving suggestions estimate marginal-rate benefits for 80C/80D/24b/80CCD(1B).
- Chatbot: knowledge-base responses for Indian tax topics; optional LLM (OpenAI) with short history; follow-up suggestions for next queries.

## Tech Stack
- Python 3.11+, FastAPI, uvicorn, SQLAlchemy 2.x, Pydantic 2.x, pydantic-settings.
- Auth/security: python-jose, passlib[bcrypt], email-validator, pycryptodome.
- Parsing/data: pandas, openpyxl, xlrd, tabula-py, PyPDF2, pdfplumber, python-multipart.
- PDF export: fpdf2. Testing: pytest suites (`test_auth.py`, `test_upload.py`).

## Configuration
Create `.env` (see `.env.example`):
```
SECRET_KEY=change-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
DATABASE_URL=sqlite:///./auto_itr.db
ALLOWED_ORIGINS=*
OPENAI_API_KEY=         # optional
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1/chat/completions
OPENAI_TIMEOUT_SECONDS=25
```

## Setup & Run
```bash
python -m venv .venv && .venv\Scripts\activate
pip install -r backend/requirements.txt
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Frontend is served from `/`; API docs at `/api/docs`, Redoc at `/api/redoc`, health at `/api/health`.

## Key API Surfaces
- Auth: `/api/auth/*`, Users: `/api/users`
- Statements: `/api/statements` (upload/process/list/transactions/delete), auto-categorization under `/api/ai`
- Analytics: `/api/analytics/*`
- AI: `/api/ai/chat`, `/api/ai/anomalies*`, `/api/ai/optimize-tax*`
- ITR/Review/Export: `/api/itr/*`, `/api/review/*`, `/api/export/*`
- Balance Sheet: `/api/balance-sheet/*`
Flow: upload → process (pdf password optional) → categorize/adjust → analytics/tax optimize → CA review → export/submit.

## Evaluation Notes (for publication)
- Categorization: measure precision/recall vs labeled set; track lift from user corrections; report confidence calibration.
- Anomaly detection: false-positive/false-negative rates on seeded anomalies; sensitivity tuning via z-thresholds.
- Tax optimizer: compare recommended regime tax vs ground-truth slab calculators; report average tax delta.
- Latency: parsing throughput (PDF vs XLSX), categorization/anomaly batch times, chatbot fallback latency with/without LLM.
- Human-in-loop: CA review acceptance rate of auto-categorized items; number of manual overrides.

## Privacy, Security, Compliance
- JWT auth, per-user ownership checks, audit logs for uploads/processing/deletes, bcrypt passwords.
- Reminder: change default `SECRET_KEY`, scope `ALLOWED_ORIGINS`, secure file storage; consider encryption at rest in production.
- Data residency: SQLite/files local; plan for managed DB + encrypted object storage for deployment.
- No tax-evasion guidance; chatbot prompt enforces compliance; anomaly flags highlight risky patterns (e.g., large cash).

## Limitations & Future Work
- Current DB is SQLite; move to Postgres for concurrency and backups.
- Categorizer is heuristic; could add lightweight ML embeddings and federated feedback.
- Anomaly detector uses simple stats; could incorporate seasonal baselines and peer groups.
- HRA/NPS specifics partly user-provided; consider ingestion from Form 16/26AS AIS for higher fidelity.
- Add end-to-end filing integration with ITD APIs and stronger PDF parsing for non-standard layouts.

## Frontend Experience
- Auth, dashboard KPIs, statement upload, merge, transactions table with category edits, analytics charts, balance sheet editor, CA review panel, and chatbot widget, all in vanilla JS modules under `frontend/js`.

## Research Summary
Auto ITR demonstrates a hybrid rule+heuristic system for Indian tax prep: deterministic slab math for explainability, heuristic categorization with user-in-the-loop learning for adaptability, anomaly surfacing for trust, and CA review for governance. Publication can focus on precision/recall of categorization, anomaly detection utility, and tax outcome accuracy, with human feedback as a stabilizing loop.
