import logging
from typing import Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from ..config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation result schema
# ---------------------------------------------------------------------------
class DocumentValidationResult(BaseModel):
    is_valid_purchase_document: bool = Field(
        description=(
            "True if the document is a receipt, invoice, bill, order confirmation, "
            "food delivery bill, restaurant bill, service bill, or any similar "
            "proof-of-purchase document. False for resumes, ID cards, random photos, "
            "handwritten notes unrelated to a purchase, or any non-transaction document."
        )
    )
    is_single_document: bool = Field(
        description=(
            "True if all provided images clearly belong to the same single physical "
            "receipt or invoice. When only one image is provided, always True. "
            "False if the images appear to be from different receipts or transactions."
        )
    )
    is_native_digital: bool = Field(
        description=(
            "True if the document appears to be a native digital file (e.g., a digitally "
            "generated e-invoice). False if it consists of photographs or scans of "
            "physical paper receipts (shadows, paper texture, crinkles, background visible)."
        )
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description=(
            "A concise, user-facing explanation of why the document was rejected. "
            "Null when both checks pass."
        )
    )
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0 for the overall validation decision."
    )


_gemini_client_validator = None


def _get_validation_client() -> genai.Client:
    """Reuses the Gemini client singleton for validation (separate from extraction)."""
    global _gemini_client_validator
    if _gemini_client_validator is None:
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        logger.info("Initializing Google GenAI Client for validation...")
        _gemini_client_validator = genai.Client(api_key=settings.GEMINI_API_KEY)
        logger.info("Validation GenAI client ready.")
    return _gemini_client_validator


VALIDATION_PROMPT = """
You are a document validation engine for an expense management system.

You will receive one or more document images. Perform TWO independent checks and
return a single structured result.

CHECK 1 — is_valid_purchase_document
Determine whether the document(s) represent a purchase-related record.

ACCEPT:
  - Retail/grocery/electronics store receipts and bills
  - Restaurant dine-in or takeaway bills
  - Food delivery (Swiggy, Zomato, DoorDash, etc.) order receipts
  - E-commerce invoices or order confirmations (Amazon, Flipkart, etc.)
  - Service bills (plumber, electrician, salon, etc.)
  - Hotel folios or accommodation receipts
  - Travel, flight, or ride-hailing (Uber, Ola, etc.) receipts
  - Handwritten cash memos or purchase receipts
  - Utility/phone bills that constitute a payment receipt

REJECT (is_valid_purchase_document = false):
  - Resumes / CVs
  - Government or personal ID documents (passport, Aadhaar, driving license)
  - Medical reports or lab results unrelated to billing
  - Random personal photos, selfies, or landscape images
  - Handwritten notes, diaries, or letters unrelated to any purchase
  - Screenshots of chat conversations, emails, or social media
  - Legal documents, contracts, or academic certificates
  - Anything that is clearly not a record of a financial transaction

CHECK 2 — is_single_document
If only ONE image is provided: set is_single_document = true unconditionally.
If MULTIPLE images are provided: determine whether they all belong to the same
physical receipt or invoice. Use these signals to reason:
  1. Matching merchant name across all images
  2. Matching date and/or time if visible
  3. Matching invoice/order/bill/transaction number if present
  4. Visual and layout continuity (same paper, font, format style)
  5. Textual continuity — the last item on one photo plausibly precedes or
     follows items on another (no duplicated totals or headers mid-receipt
     unless it's a multi-page invoice)
  6. Line-item or sequence numbering continuity if printed

Set is_single_document = false if the images clearly show different merchants,
different dates, or different receipt contexts with no continuity signals.

CHECK 3 — is_native_digital
Determine whether the document appears to be a native digital file (e.g., a digitally generated e-invoice or PDF receipt) versus a photograph or scan of a physical paper receipt.
- Set true if it is purely a native digital document.
- Set false if it consists of photos or scans of physical paper receipts (e.g., shadows, paper texture, uneven lighting, visible background) OR a mixture of digital pages and scanned physical pages.

REJECTION REASON
If any check fails (is_valid_purchase_document=false, is_single_document=false, or is_native_digital=false), set rejection_reason to a short, user-facing message explaining the failure.
If is_native_digital fails, clearly ask the user to "use the Physical Receipt upload flow for photos or scans of physical receipts."
If all checks pass, set rejection_reason = null.

CONFIDENCE
Return a confidence score (0.0–1.0) reflecting certainty in your combined verdict.
"""


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
