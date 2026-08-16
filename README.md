# AI Expense Intelligence

A production-style MVP platform where users can upload physical receipts/bills as images and digital receipts/invoices as PDF files for further automated AI parsing and analytics.

---

## Project Structure
- **`frontend/`**: Vite + React + TypeScript + Tailwind CSS v4 frontend.
- **`backend/`**: Python + FastAPI + Uvicorn + MongoDB backend.

---

## Getting Started

### 1. Prerequisite: MongoDB
Ensure you have MongoDB running locally, or configure a connection string in `.env`.
Default: `mongodb://localhost:27017/expense_intel`

### 2. Backend Setup
1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create your `.env` file (copied from `.env.example` at root):
   ```bash
   # Copy or create backend/.env
   ```
5. Run the FastAPI development server:
   ```bash
   python run.py
   ```
   The backend will be available at [http://localhost:8000](http://localhost:8000).

### 3. Frontend Setup
1. Navigate to the `frontend/` directory:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   The frontend will be available at [http://localhost:5173](http://localhost:5173).
