from typing import List, Optional
from datetime import date
from pydantic import BaseModel, Field

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
    
    # Cloudinary fields
    cloudinary_public_id: Optional[str] = None
    cloudinary_resource_type: Optional[str] = None
    original_filename: Optional[str] = None
    
    # Items
    items: List[ReceiptItemCreate] = []

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
    cloudinary_public_id: Optional[str] = None
    cloudinary_resource_type: Optional[str] = None
    original_filename: Optional[str] = None
    created_at: str
    items: List[ReceiptItemResponse] = []
