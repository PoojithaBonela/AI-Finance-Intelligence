import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import supabase_client
from .routers import upload, receipts, exchange

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # No explicit async startup/shutdown required for Supabase client
    yield

app = FastAPI(
    title="AI Expense Intelligence API",
    description="Backend API for AI Expense Intelligence platform",
    version="1.0.0",
    lifespan=lifespan
)

# Set up CORS middleware
origins = [origin.strip() for origin in settings.ALLOWED_ORIGINS.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(upload.router)
app.include_router(receipts.router)
app.include_router(exchange.router)

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "AI Expense Intelligence API",
        "supabase_connected": db_connected()
    }

def db_connected() -> bool:
    return supabase_client is not None
