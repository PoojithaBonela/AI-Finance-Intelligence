import logging
from google import genai
from google.genai import types
from app.config import settings
from .schemas import ReceiptExtraction
from .prompts import EXTRACTION_PROMPT
from .date_normalizer import normalize_and_validate_date

logger = logging.getLogger(__name__)

# Lazily initialized Gemini Client
_gemini_client = None


def get_gemini_client() -> genai.Client:
    """Returns a shared, lazily initialized Gemini Client."""
    global _gemini_client
    if _gemini_client is None:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        logger.info("Initializing Google GenAI Client...")
        _gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("Google GenAI Client initialized successfully.")
    return _gemini_client


def process_document_gemini(parts: list) -> dict:
    """
    Sends one or more document image Parts to Gemini Vision for structured extraction.
    When multiple images are provided they are treated as segments of a single receipt.
    """
    client = get_gemini_client()

    try:
        logger.info(f"Calling Gemini structured extraction on {len(parts)} image(s)...")
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[*parts, EXTRACTION_PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReceiptExtraction,
            ),
        )

        # Parse output as structured dictionary / Pydantic model
        parsed = response.parsed
        if parsed:
            if hasattr(parsed, "purchase_date") and parsed.purchase_date:
                parsed.purchase_date = normalize_and_validate_date(parsed.purchase_date)
            if hasattr(parsed, "due_date") and parsed.due_date:
                parsed.due_date = normalize_and_validate_date(parsed.due_date)
        return parsed
    except Exception as e:
        logger.error(f"Gemini API structured extraction failed: {e}")
        raise RuntimeError(f"Gemini structured extraction failed: {str(e)}")
