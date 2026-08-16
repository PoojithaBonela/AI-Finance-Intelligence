import logging
from supabase import create_client, Client
from .config import settings

logger = logging.getLogger(__name__)

supabase_client: Client = None

def init_supabase():
    global supabase_client
    if settings.SUPABASE_URL and settings.SUPABASE_KEY:
        try:
            supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
            logger.info("Supabase client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
    else:
        logger.warning("SUPABASE_URL or SUPABASE_KEY is missing. Supabase functionality will not work.")

# Call it upon import to setup client
init_supabase()
