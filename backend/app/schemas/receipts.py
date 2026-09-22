from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field, field_validator
from ..agents.receipt_agent.date_normalizer import normalize_and_validate_date

class ReceiptItemCreate(BaseModel):
    item_name: str = Field(..., min_length=1)
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: float

class ReceiptItemResponse(ReceiptItemCreate):
    id: str
    receipt_id: str
    created_at: str

class ReceiptCreate(BaseModel):
    merchant_name: str = Field(..., min_length=1)
    purchase_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = None
    total_amount: float
    tax: Optional[float] = None
    payment_method: Optional[str] = None
    warranty_period_days: Optional[int] = None
    document_type: Optional[str] = None
    category: Optional[str] = None
    
    # Cloudinary fields
    cloudinary_public_id: Optional[str] = None
    cloudinary_resource_type: Optional[str] = None
    original_filename: Optional[str] = None
    cloudinary_assets: Optional[list] = None
    
    # Items
    items: List[ReceiptItemCreate] = []

    @field_validator("purchase_date", "due_date", mode="before")
    @classmethod
    def normalize_dates(cls, v):
        if isinstance(v, str):
            norm = normalize_and_validate_date(v)
            return norm
        return v

class ReceiptResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    merchant_name: str
    purchase_date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = None
    total_amount: float
    tax: Optional[float] = None
    payment_method: Optional[str] = None
    warranty_period_days: Optional[int] = None
    document_type: Optional[str] = None
    category: Optional[str] = None
    cloudinary_public_id: Optional[str] = None
    cloudinary_resource_type: Optional[str] = None
    original_filename: Optional[str] = None
    cloudinary_assets: Optional[list] = None
    created_at: str
    items: List[ReceiptItemResponse] = []
