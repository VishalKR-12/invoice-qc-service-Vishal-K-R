from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    price: Optional[float] = None
    total: Optional[float] = None

class InvoiceSchema(BaseModel):
    invoice_number: Optional[str] = None
    vendor_name: Optional[str] = None
    buyer_name: Optional[str] = None
    vendor_address: Optional[str] = None
    buyer_address: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    currency: Optional[str] = None
    subtotal: Optional[float] = None
    tax_amount: Optional[float] = None
    total_amount: Optional[float] = None
    payment_terms: Optional[str] = None
    line_items: Optional[List[LineItem]] = []

class ValidationResult(BaseModel):
    invoice_id: Optional[str] = None
    invoice_number: Optional[str] = None
    is_valid: bool
    score: int
    errors: List[str] = []
    warnings: List[str] = []
    extracted_data: Optional[InvoiceSchema] = None

class ProcessResponse(BaseModel):
    success: bool
    invoice_id: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    message: str
