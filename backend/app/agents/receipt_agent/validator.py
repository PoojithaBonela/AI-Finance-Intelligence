import logging
from google import genai
from google.genai import types
from app.config import settings
from .schemas import DocumentValidationResult
from .prompts import VALIDATION_PROMPT

logger = logging.getLogger(__name__)

_gemini_client_validator = None


def _get_validation_client() -> genai.Client:
    """Reuses the Gemini client singleton for validation."""
    global _gemini_client_validator
    if _gemini_client_validator is None:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        logger.info("Initializing Google GenAI Client for validation...")
        _gemini_client_validator = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("Validation GenAI client ready.")
    return _gemini_client_validator


def validate_documents(parts: list) -> DocumentValidationResult:
    """
    Validates one or more document image Parts via a single Gemini call.
    Returns a DocumentValidationResult describing whether the document is a
    valid purchase document and, for multi-image uploads, whether all images
    belong to the same receipt.
    """
    client = _get_validation_client()

    try:
        logger.info(f"Running document validation on {len(parts)} image(s)...")
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[*parts, VALIDATION_PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=DocumentValidationResult,
            ),
        )
        result: DocumentValidationResult = response.parsed
        logger.info(
            f"Validation complete — valid_purchase={result.is_valid_purchase_document}, "
            f"single_doc={result.is_single_document}, confidence={result.confidence:.2f}"
        )
        return result
    except Exception as e:
        logger.error(f"Document validation Gemini call failed: {e}")
        raise RuntimeError(f"Document validation failed: {str(e)}")
