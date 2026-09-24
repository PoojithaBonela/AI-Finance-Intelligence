import logging
import asyncio
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .database import supabase_client
from .routers import upload, receipts, exchange, analytics, insights
from .services.cloudinary_service import delete_from_cloudinary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("app")

async def cleanup_deleted_receipts_loop():
    """Background task to permanently delete receipts softly deleted > 30 days ago."""
    while True:
        try:
            if supabase_client:
                thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                
                # Find expired receipts
                res = supabase_client.table("receipts").select("id, cloudinary_public_id, cloudinary_resource_type").not_.is_("deleted_at", "null").lt("deleted_at", thirty_days_ago).execute()
                expired_receipts = res.data or []
                
                for r in expired_receipts:
                    receipt_id = r["id"]
                    pub_id = r.get("cloudinary_public_id")
                    res_type = r.get("cloudinary_resource_type") or "image"
                    
                    # 1. Delete image from Cloudinary if it exists
                    if pub_id:
                        try:
                            # cloudinary_service uses 'pdf'/'image' for file_type mapping
                            file_type = "pdf" if res_type == "raw" else "image"
                            delete_from_cloudinary(pub_id, file_type)
                        except Exception as img_e:
                            logger.error(f"Failed to delete Cloudinary image {pub_id} for receipt {receipt_id}: {img_e}")
                    
                    # 2. Delete the receipt from DB (cascades to receipt_items)
                    del_res = supabase_client.table("receipts").delete().eq("id", receipt_id).execute()
                    if del_res.data:
                        logger.info(f"Permanently deleted receipt {receipt_id}")
            
            # Sleep for 24 hours
            await asyncio.sleep(86400)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in cleanup_deleted_receipts_loop: {e}")
            await asyncio.sleep(3600)  # Retry in 1 hour if error

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start cleanup task
    cleanup_task = asyncio.create_task(cleanup_deleted_receipts_loop())
    yield
    # Cancel cleanup task on shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

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
app.include_router(analytics.router)
app.include_router(insights.router)

@app.get("/")
async def root():
    return {
        "status": "healthy",
        "service": "AI Expense Intelligence API",
        "supabase_connected": db_connected()
    }

def db_connected() -> bool:
    return supabase_client is not None
