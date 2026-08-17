import logging
from pydantic import BaseModel, Field
from typing import List, Optional
from google import genai
from google.genai import types
from ..config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic output schema – matches the agreed JSON contract exactly
# ---------------------------------------------------------------------------
class FieldConfidences(BaseModel):
    merchant_name: float
    purchase_date: float
    due_date: float
    currency: float
    items: float
    tax: float
    total_amount: float
    payment_method: float
    warranty_period_days: float

class ReceiptItem(BaseModel):
    name: str = Field(
        description="The name of the purchased product or service as it appears on the receipt."
    )
    quantity: Optional[float] = Field(
        default=None,
        description=(
            "Number of units purchased. Set to 1 only when the receipt format makes "
            "a single-unit purchase unambiguous (e.g. a single dish with no quantity "
            "column). Otherwise null."
        )
    )
    unit_price: Optional[float] = Field(
        default=None,
        description="Price per unit if clearly shown on the receipt, otherwise null."
    )
    total_price: float = Field(
        description="Total price for this line item (quantity × unit_price, or the line total as printed)."
    )

class ReceiptExtraction(BaseModel):
    merchant_name: str = Field(description="Name of the merchant, store, restaurant, or service provider.")
    purchase_date: Optional[str] = Field(
        default=None,
        description="Date of the transaction as printed on the receipt (any format). Null if not present."
    )
    currency: Optional[str] = Field(
        default=None,
        description=(
            "ISO 4217 currency code inferred from currency symbols or context "
            "(e.g. USD, INR, EUR). Detect only when clearly identifiable. "
            "If ambiguous or not present, return null. Do not assume a default."
        )
    )
    items: List[ReceiptItem] = Field(
        description=(
            "List of purchased goods or services only. "
            "DO NOT include fees, taxes, delivery charges, platform charges, "
            "service charges, tips, discounts, subtotals, or payment lines here."
        )
    )
    tax: Optional[float] = Field(
        default=None,
        description="Total tax amount if a dedicated tax line is clearly present, otherwise null."
    )
    total_amount: float = Field(
        description=(
            "The final payable amount after all fees, taxes, and discounts, "
            "as printed on the receipt (look for 'Total', 'Grand Total', "
            "'Amount Paid', 'Net Payable', etc.). Extract the value; do not calculate it."
        )
    )
    payment_method: Optional[str] = Field(
        default=None,
        description="Payment method used (e.g. Cash, Debit, UPI, Visa). Null if not present."
    )
    warranty_period_days: Optional[int] = Field(
        default=None,
        description="Warranty duration in days if clearly stated on the receipt, otherwise null."
    )
    due_date: Optional[str] = Field(
        default=None,
        description=(
            "Payment deadline as printed on the document "
            "(e.g. 'Due Date', 'Pay By', 'Last Date for Payment'). "
            "Separate from purchase_date (the issue/billing date). "
            "Null when not clearly present. Never guess."
        )
    )
    is_incomplete: bool = Field(
        default=False,
        description=(
            "True if there are visual signs of an incomplete upload (e.g. receipt continuing beyond the image boundary, "
            "cut-off top/bottom, truncated item list, missing final totals). False if the receipt appears fully visible."
        )
    )
    field_confidences: FieldConfidences = Field(
        description=(
            "Per-field confidence scores from 0.0 (uncertain) to 1.0 (certain). "
            "Score based on text legibility, ambiguity, and inference distance."
        )
    )

# Lazily initialized Gemini Client
_gemini_client = None

def get_gemini_client():
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
        prompt = """
You are a receipt-parsing engine. Your job is to extract structured data from any
purchase document.

*** CRITICAL FIRST STEP: COMPLETENESS CHECK ***
Before extracting data, visually inspect the edges and bottom of the receipt.
Set `is_incomplete` to TRUE if ANY of these are true:
- The receipt is cut off at the bottom or top (e.g. text is sliced).
- The items list ends abruptly without a subtotal or total.
- Essential receipt parts (like the final Total Amount) are visibly out of frame.
- The receipt visibly continues beyond the edge of the photograph.
If the entire receipt from top to bottom is visible, set it to FALSE.

When multiple images are provided, they are segments of the same physical receipt, BUT THEY MAY BE UPLOADED OUT OF ORDER.
Before extraction, you MUST:
- Analyze all uploaded images together.
- Determine the correct logical page/image order using visual continuity, text continuation, item sequence, receipt edges, overlapping content, and header/footer structure.
- Mentally reconstruct the images in the correct chronological order to form one continuous receipt.
- Handle overlapping photos using SEQUENCE-LEVEL deduplication:
  - Identify overlapping regions using multiple consecutive receipt elements.
  - DO NOT deduplicate an item merely because the same product name appears twice.
  - Only remove duplicates when there is strong evidence of an overlap in the reconstructed order.

Before extracting, mentally classify every line on the document into exactly one bucket:
  (A) Purchased item – a distinct good or service the customer actively chose to acquire.
      Examples: "Paneer Butter Masala", "Men's T-Shirt", "Cab ride to Airport", "Room charge 1 night"
  (B) Financial adjustment – any line that adjusts, breaks down, or explains how the
      total was calculated, rather than naming a distinct good or service the customer
      chose to acquire. Includes:
        • Retail/delivery: delivery fee, packing charge, platform fee, service charge,
          tip, convenience fee, coupon discount, round-off, loyalty points
        • Taxes and statutory levies: GST, CGST, SGST, VAT, Electricity Duty, Cess,
          any named surcharge
        • Utility/service tariff components: Energy Charge, Fixed Charge, Customer
          Charge, FPPCA, Fuel Surcharge, regulatory charge, wheeling charge — and any
          similar component that represents a rate tier or regulatory levy on a service
        • Adjustments and credits: rebate, government subsidy, bill adjustment,
          arrears, advance payment
      Rule of thumb: if removing the line would not change what the customer received,
      it is bucket (B).
  (C) Non-data – headers, merchant address, phone, thank-you note, barcode, etc.

Extraction rules:
1. items[] – include ONLY bucket (A) lines. Never include bucket (B) or (C) here.
2. tax – if a dedicated tax line (e.g. GST, VAT, Electricity Duty, Cess) is clearly
   printed, capture its total numeric value. If multiple tax lines exist, sum them.
   Set null if absent.
3. total_amount – extract the single bottom-line amount the customer paid or owes,
   labelled e.g. Total, Grand Total, Amount Payable, Net Payable, Bill Amount.
   Do NOT calculate it.
4. currency – infer from symbols (₹→INR, $→USD, €→EUR) or text. Detect only when
   clearly identifiable. If ambiguous or not present, return null. Do NOT assume
   USD, INR, or any default currency.
5. NUMERICS & LOCALE FORMATS – Preserve monetary values exactly as printed on the receipt.
   Correctly interpret locale-specific decimal separators (e.g., 43.000 vs 13,500) based on
   the context of the receipt. Do not arbitrarily remove or add zeros. Never invent missing digits,
   items, totals, or subtotals.
6. quantity – set to 1 only when a single-unit purchase is unambiguous. Otherwise null.
7. All optional fields (currency, purchase_date, due_date, unit_price, quantity, tax,
   payment_method, warranty_period_days) must be null when not clearly present.
   Never guess or infer.
8. Zero-item documents: utility bills (electricity, water, gas), subscription invoices,
   and simple service bills often have no discrete purchased goods — only tariff
   components that all belong to bucket (B). For these documents items[] MUST be an
   empty array []. Do not populate items[] with billing components, and do not
   fabricate a synthetic item to represent the billed service.
9. COMPLETENESS CHECK – Before returning extraction results, check whether the entire
   receipt/document is visible. Detect visual signs of an incomplete upload: receipt
   continuing beyond the image boundary, cut-off bottom/top, truncated item list,
   missing final totals, or clearly missing sections. Set `is_incomplete` to true if
   it appears incomplete, otherwise false. Do not treat extracted data as complete
   if the receipt is cut off.
10. field_confidences: for every top-level field in the output, assign a confidence
   score from 0.0 to 1.0:
     1.0  → clearly and unambiguously printed
     0.9+ → printed but minor legibility issue
     0.7–0.9 → inferred from context with high probability
     0.5–0.7 → partial inference or low legibility
     <0.5 → very uncertain or not found (use null for the value instead when possible)
   For items, score reflects confidence in the items list as a whole.
   Include a key for every field listed in field_confidences description.
"""
        
        logger.info(f"Calling Gemini structured extraction on {len(parts)} image(s)...")
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[*parts, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ReceiptExtraction,
            ),
        )
        
        # Parse output as structured dictionary
        return response.parsed
    except Exception as e:
        logger.error(f"Gemini API structured extraction failed: {e}")
        raise RuntimeError(f"Gemini structured extraction failed: {str(e)}")

# =====================================================================
# COMMENTED PADDLEOCR IMPLEMENTATION FOR POSSIBLE FUTURE USE
# =====================================================================
# import os
# import fitz  # PyMuPDF
# from paddleocr import PaddleOCR
# 
# _ocr_engine = None
# 
# def get_ocr_engine():
#     global _ocr_engine
#     if _ocr_engine is None:
#         logger.info("Initializing PaddleOCR engine...")
#         _ocr_engine = PaddleOCR(use_textline_orientation=True, lang='en')
#         logger.info("PaddleOCR engine initialized successfully.")
#     return _ocr_engine
# 
# def extract_text_from_image(image_path: str) -> str:
#     engine = get_ocr_engine()
#     try:
#         result = engine.ocr(image_path)
#     except Exception as e:
#         logger.error(f"PaddleOCR processing error: {e}")
#         raise RuntimeError(f"OCR processing failed: {str(e)}")
# 
#     extracted_lines = []
#     if result:
#         if isinstance(result, dict):
#             texts = result.get('rec_texts', [])
#             extracted_lines.extend(texts)
#         elif isinstance(result, list) and len(result) > 0:
#             first_element = result[0]
#             if isinstance(first_element, dict):
#                 texts = first_element.get('rec_texts', [])
#                 extracted_lines.extend(texts)
#             elif isinstance(first_element, list):
#                 for line in first_element:
#                     if isinstance(line, list) and len(line) > 1 and isinstance(line[1], tuple):
#                         extracted_lines.append(line[1][0])
#             else:
#                 for line in result:
#                     if isinstance(line, list) and len(line) > 1 and isinstance(line[1], tuple):
#                         extracted_lines.append(line[1][0])
#     return "\n".join(extracted_lines)
# 
# def extract_text_from_pdf(pdf_path: str, temp_dir: str) -> str:
#     doc = fitz.open(pdf_path)
#     all_text_lines = []
#     for page_num in range(len(doc)):
#         page = doc.load_page(page_num)
#         pix = page.get_pixmap()
#         temp_img_path = os.path.join(temp_dir, f"temp_pdf_page_{page_num}.png")
#         pix.save(temp_img_path)
#         try:
#             page_text = extract_text_from_image(temp_img_path)
#             if page_text:
#                 all_text_lines.append(page_text)
#         finally:
#             if os.path.exists(temp_img_path):
#                 os.remove(temp_img_path)
#     return "\n\n".join(all_text_lines)
# 
# def process_document_ocr(file_path: str, file_extension: str, temp_dir: str) -> str:
#     ext = file_extension.lower()
#     if ext == ".pdf":
#         return extract_text_from_pdf(file_path, temp_dir)
#     elif ext in {".jpg", ".jpeg", ".png"}:
#         return extract_text_from_image(file_path)
#     else:
#         raise ValueError(f"Unsupported file type for OCR: {file_extension}")
