from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Validation result schema (Agent 1 - Step 1: Pre-extraction validation)
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


# ---------------------------------------------------------------------------
# Pydantic extraction output schema (Agent 1 - Step 2: Structured extraction)
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
        description=(
            "Date of the transaction as printed on the receipt, normalized to 'YYYY-MM-DD' format if recognized. "
            "Preserve the exact year, month, and day from the receipt. Accept historical/past years (e.g. 2024, 2023, 2022). "
            "Never invent a current date when the receipt is from an earlier year. Null if not present."
        )
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
            "(e.g. 'Due Date', 'Pay By', 'Last Date for Payment'), normalized to 'YYYY-MM-DD' format if present. "
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
