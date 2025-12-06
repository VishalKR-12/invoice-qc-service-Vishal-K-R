from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
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

class FieldCorrection(BaseModel):
    """Represents a single field correction from Google API verification"""
    field_name: str
    original_value: Any
    corrected_value: Any
    confidence: float  # 0-100
    source: str
    reasoning: str
    source_url: Optional[str] = None
    requires_review: bool = False

class GoogleVerificationResult(BaseModel):
    """Result from Google API verification"""
    invoice_number: str
    original_data: Dict[str, Any]
    corrected_data: Dict[str, Any]
    corrections: List[FieldCorrection] = []
    overall_confidence: float = 0.0
    status: str  # "Verified", "Review Needed", "High Confidence", "Low Confidence"
    summary: str = ""
    timestamp: str = ""
    critical_issues: List[str] = []
    warnings: List[str] = []

class ValidationResult(BaseModel):
    invoice_id: Optional[str] = None
    invoice_number: Optional[str] = None
    is_valid: bool
    score: int
    errors: List[str] = []
    warnings: List[str] = []
    extracted_data: Optional[InvoiceSchema] = None
    google_verification: Optional[GoogleVerificationResult] = None

class FieldComparisonModel(BaseModel):
    """Field comparison from extraction merger"""
    field_name: str
    pdf_value: Optional[Any] = None
    google_value: Optional[Any] = None
    selected_value: Optional[Any] = None
    selection_reason: str
    confidence_score: float
    is_mismatch: bool
    recommendation: Optional[str] = None


class MergedExtractionResponse(BaseModel):
    """Response from dual-source extraction merger"""
    pdf_data: Dict[str, Any]
    google_data: Dict[str, Any]
    final_output: Dict[str, Any]
    field_comparisons: List[FieldComparisonModel] = []
    notes: List[str] = []
    mismatches: List[str] = []
    merge_timestamp: str
    quality_score: float
    recommendation: str  # "approve", "review", "reject"


class ProcessResponse(BaseModel):
    success: bool
    invoice_id: Optional[str] = None
    validation_result: Optional[ValidationResult] = None
    merged_extraction: Optional[MergedExtractionResponse] = None
    extraction_metadata: Optional[Dict[str, Any]] = None  # New field for model info
    message: str
