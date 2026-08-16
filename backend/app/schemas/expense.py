from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ExpenseDocumentBase(BaseModel):
    filename: str
    original_filename: str
    file_type: str  # 'physical' or 'digital'
    mime_type: str
    file_size: int
    local_path: str

class ExpenseDocumentCreate(ExpenseDocumentBase):
    pass

class ExpenseDocumentResponse(ExpenseDocumentBase):
    id: str = Field(alias="_id")
    uploaded_at: datetime
    status: str = "uploaded"  # uploaded, processed, error

    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
