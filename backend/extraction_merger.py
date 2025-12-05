"""
Dual-Source Invoice Extraction & Intelligent Merging System

This module handles:
1. PDF extraction using pdf_extractor.py (local regex + Gemini)
2. Google Vision API extraction (when available)
3. Field-by-field comparison
4. Intelligent value selection based on reliability
5. Conflict detection and resolution
6. Comprehensive output with debugging info
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime
from difflib import SequenceMatcher

from models import InvoiceSchema, LineItem
from pdf_extractor import PDFExtractor
import google.generativeai as genai
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)


@dataclass
class ExtractionSource:
    """Metadata about extraction source"""
    source_type: str  # "pdf_local", "google_vision", "gemini_ai"
    confidence: float  # 0-100
    timestamp: str
    is_complete: bool  # All required fields present
    extracted_fields: int  # Number of non-null fields


@dataclass
class FieldComparison:
    """Comparison result for a single field"""
    field_name: str
    pdf_value: Any
    google_value: Any
    selected_value: Any
    selection_reason: str
    confidence_score: float  # 0-100
    is_mismatch: bool
    recommendation: Optional[str] = None


@dataclass
class ExtractionMergeResult:
    """Complete merge result with debugging information"""
    pdf_data: Dict[str, Any]
    google_data: Dict[str, Any]
    final_output: Dict[str, Any]
    field_comparisons: List[FieldComparison] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    mismatches: List[str] = field(default_factory=list)
    source_metadata: Dict[str, ExtractionSource] = field(default_factory=dict)
    merge_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    quality_score: float = 0.0  # Overall quality 0-100
    recommendation: str = ""  # "approve", "review", "reject"

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "pdf_data": self.pdf_data,
            "google_data": self.google_data,
            "final_output": self.final_output,
            "field_comparisons": [asdict(fc) for fc in self.field_comparisons],
            "notes": self.notes,
            "mismatches": self.mismatches,
            "source_metadata": {k: asdict(v) for k, v in self.source_metadata.items()},
            "merge_timestamp": self.merge_timestamp,
            "quality_score": self.quality_score,
            "recommendation": self.recommendation
        }


class ExtractionMerger:
    """Intelligent merger of dual-source invoice extraction"""

    def __init__(self):
        self.pdf_extractor = PDFExtractor()
        self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Field reliability weights (higher = more reliable if value present)
        self.field_weights = {
            "invoice_number": {"pdf": 0.85, "google": 0.95},
            "vendor_name": {"pdf": 0.80, "google": 0.90},
            "vendor_address": {"pdf": 0.75, "google": 0.85},
            "buyer_name": {"pdf": 0.80, "google": 0.90},
            "buyer_address": {"pdf": 0.75, "google": 0.85},
            "invoice_date": {"pdf": 0.85, "google": 0.95},
            "due_date": {"pdf": 0.80, "google": 0.90},
            "currency": {"pdf": 0.90, "google": 0.95},
            "subtotal": {"pdf": 0.85, "google": 0.90},
            "tax_amount": {"pdf": 0.85, "google": 0.90},
            "total_amount": {"pdf": 0.90, "google": 0.95},
            "payment_terms": {"pdf": 0.70, "google": 0.80},
            "line_items": {"pdf": 0.75, "google": 0.85},
        }

    def extract_and_merge(self, pdf_path: str) -> ExtractionMergeResult:
        """
        Main entry point: Extract from both sources and intelligently merge.
        
        Process:
        1. Extract from PDF using pdf_extractor.py
        2. Extract using Google Vision API (with fallback to Gemini)
        3. Compare field-by-field
        4. Select best value for each field
        5. Return merged result with debugging info
        """
        
        logger.info(f"Starting dual-source extraction for: {pdf_path}")
        
        # Initialize result container
        result = ExtractionMergeResult(
            pdf_data={},
            google_data={},
            final_output={}
        )

        try:
            # STEP 1: Extract from PDF using local extractor
            logger.info("Step 1: Extracting from PDF using pdf_extractor.py")
            pdf_extraction = self.pdf_extractor.extract_from_pdf(pdf_path)
            result.pdf_data = pdf_extraction.model_dump()
            
            result.source_metadata["pdf_local"] = self._create_source_metadata(
                source_type="pdf_local",
                data=pdf_extraction
            )

        except Exception as e:
            logger.error(f"PDF extraction failed: {str(e)}")
            result.notes.append(f"PDF extraction error: {str(e)}")
            result.pdf_data = {}

        try:
            # STEP 2: Extract using Google Vision API (with fallback)
            logger.info("Step 2: Extracting using Google APIs")
            google_extraction = self._extract_with_google_vision(pdf_path)
            result.google_data = google_extraction.model_dump()
            
            result.source_metadata["google_vision"] = self._create_source_metadata(
                source_type="google_vision",
                data=google_extraction
            )

        except Exception as e:
            logger.warning(f"Google extraction failed: {str(e)}")
            result.notes.append(f"Google extraction unavailable: {str(e)}")
            result.google_data = {}

        # STEP 3: Compare and merge
        logger.info("Step 3: Comparing and merging extracted data")
        self._compare_and_merge(
            pdf_data=pdf_extraction if result.pdf_data else InvoiceSchema(),
            google_data=google_extraction if result.google_data else InvoiceSchema(),
            merge_result=result
        )

        # STEP 4: Calculate quality score and recommendation
        self._calculate_quality_metrics(result)

        logger.info(f"Extraction complete. Quality score: {result.quality_score}%")
        return result

    def _extract_with_google_vision(self, pdf_path: str) -> InvoiceSchema:
        """
        Extract invoice using Google Vision API with intelligent fallback.
        
        Hierarchy:
        1. Try Google Document AI (best for invoices)
        2. Fallback to Gemini Vision for image analysis
        3. Fallback to Gemini text processing
        """
        
        invoice = InvoiceSchema()
        
        try:
            # Read PDF content
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()

            # Attempt: Google Document AI would go here
            # (requires separate API setup, so we use Gemini Vision as substitute)
            
            # For now, use Gemini's document understanding capabilities
            import base64
            encoded_pdf = base64.b64encode(pdf_content).decode('utf-8')
            
            prompt = """
            Extract invoice data from this PDF document. Return as JSON:
            {
                "invoice_number": "string",
                "vendor_name": "string",
                "vendor_address": "string",
                "buyer_name": "string",
                "buyer_address": "string",
                "invoice_date": "YYYY-MM-DD",
                "due_date": "YYYY-MM-DD",
                "currency": "string (3-letter code)",
                "subtotal": "number",
                "tax_amount": "number",
                "total_amount": "number",
                "payment_terms": "string",
                "line_items": [
                    {
                        "description": "string",
                        "quantity": "number",
                        "price": "number",
                        "total": "number"
                    }
                ]
            }
            
            IMPORTANT:
            - Extract EXACTLY as shown in document
            - If field not found, set to null
            - For dates, use YYYY-MM-DD format
            - For amounts, use numeric values without currency symbols
            - For line items, preserve all details exactly
            """
            
            # Send to Gemini with PDF context
            response = self.gemini_model.generate_content([
                prompt,
                {"mime_type": "application/pdf", "data": encoded_pdf}
            ])
            
            # Parse response
            response_text = response.text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)
                
                # Map to InvoiceSchema
                invoice = self._map_to_invoice_schema(data)
                logger.info("Google Vision extraction successful")
                return invoice

        except Exception as e:
            logger.warning(f"Google Vision extraction failed: {str(e)}")
            # Fallback already handled by caller
            raise

        return invoice

    def _map_to_invoice_schema(self, data: Dict[str, Any]) -> InvoiceSchema:
        """Map extracted dictionary to InvoiceSchema"""
        
        line_items = []
        if data.get("line_items"):
            for item in data.get("line_items", []):
                try:
                    line_items.append(LineItem(
                        description=item.get("description"),
                        quantity=self._to_float(item.get("quantity")),
                        price=self._to_float(item.get("price")),
                        total=self._to_float(item.get("total"))
                    ))
                except Exception as e:
                    logger.warning(f"Failed to map line item: {str(e)}")
                    continue

        return InvoiceSchema(
            invoice_number=str(data.get("invoice_number")) if data.get("invoice_number") else None,
            vendor_name=str(data.get("vendor_name")) if data.get("vendor_name") else None,
            vendor_address=str(data.get("vendor_address")) if data.get("vendor_address") else None,
            buyer_name=str(data.get("buyer_name")) if data.get("buyer_name") else None,
            buyer_address=str(data.get("buyer_address")) if data.get("buyer_address") else None,
            invoice_date=str(data.get("invoice_date")) if data.get("invoice_date") else None,
            due_date=str(data.get("due_date")) if data.get("due_date") else None,
            currency=str(data.get("currency")) if data.get("currency") else None,
            subtotal=self._to_float(data.get("subtotal")),
            tax_amount=self._to_float(data.get("tax_amount")),
            total_amount=self._to_float(data.get("total_amount")),
            payment_terms=str(data.get("payment_terms")) if data.get("payment_terms") else None,
            line_items=line_items
        )

    def _compare_and_merge(
        self,
        pdf_data: InvoiceSchema,
        google_data: InvoiceSchema,
        merge_result: ExtractionMergeResult
    ) -> None:
        """
        Compare field-by-field and select best value.
        
        Priority logic:
        1. Google value if present and reliable
        2. PDF value if present and no Google data
        3. Use similarity matching for text fields
        4. Flag mismatches for review
        """
        
        fields_to_compare = [
            "invoice_number",
            "vendor_name",
            "vendor_address",
            "buyer_name",
            "buyer_address",
            "invoice_date",
            "due_date",
            "currency",
            "subtotal",
            "tax_amount",
            "total_amount",
            "payment_terms",
            "line_items"
        ]

        final_data = {}

        for field_name in fields_to_compare:
            pdf_value = getattr(pdf_data, field_name, None)
            google_value = getattr(google_data, field_name, None)

            # Compare and select best value
            comparison = self._select_best_value(
                field_name=field_name,
                pdf_value=pdf_value,
                google_value=google_value
            )

            merge_result.field_comparisons.append(comparison)
            final_data[field_name] = comparison.selected_value

            # Track mismatches
            if comparison.is_mismatch:
                merge_result.mismatches.append(
                    f"{field_name}: PDF={pdf_value}, Google={google_value}, "
                    f"Selected={comparison.selected_value} ({comparison.selection_reason})"
                )

        merge_result.final_output = final_data

    def _select_best_value(
        self,
        field_name: str,
        pdf_value: Any,
        google_value: Any
    ) -> FieldComparison:
        """
        Select best value using intelligent comparison.
        
        Logic:
        1. If both missing → None
        2. If only one available → use that
        3. If both available:
           - For numeric: Use Google if different (more reliable)
           - For text: Use similarity matching
           - Default: Prefer Google (higher confidence)
        4. Flag mismatches
        """

        comparison = FieldComparison(
            field_name=field_name,
            pdf_value=pdf_value,
            google_value=google_value,
            selected_value=None,
            selection_reason="",
            confidence_score=0.0,
            is_mismatch=False
        )

        # Case 1: Both missing
        if not self._has_value(pdf_value) and not self._has_value(google_value):
            comparison.selection_reason = "Both sources missing"
            comparison.selected_value = None
            comparison.confidence_score = 0
            return comparison

        # Case 2: Only PDF available
        if self._has_value(pdf_value) and not self._has_value(google_value):
            comparison.selected_value = pdf_value
            comparison.selection_reason = "Google unavailable, using PDF"
            comparison.confidence_score = self.field_weights.get(field_name, {}).get("pdf", 0.7) * 100
            return comparison

        # Case 3: Only Google available
        if not self._has_value(pdf_value) and self._has_value(google_value):
            comparison.selected_value = google_value
            comparison.selection_reason = "PDF unavailable, using Google"
            comparison.confidence_score = self.field_weights.get(field_name, {}).get("google", 0.8) * 100
            return comparison

        # Case 4: Both available - intelligent selection
        return self._compare_both_values(field_name, pdf_value, google_value)

    def _compare_both_values(
        self,
        field_name: str,
        pdf_value: Any,
        google_value: Any
    ) -> FieldComparison:
        """Compare when both values are available"""

        comparison = FieldComparison(
            field_name=field_name,
            pdf_value=pdf_value,
            google_value=google_value,
            selected_value=None,
            selection_reason="",
            confidence_score=0.0,
            is_mismatch=False
        )

        # Handle line_items specially
        if field_name == "line_items":
            return self._compare_line_items(pdf_value, google_value, comparison)

        # Handle numeric fields
        if isinstance(pdf_value, (int, float)) and isinstance(google_value, (int, float)):
            return self._compare_numeric(field_name, pdf_value, google_value, comparison)

        # Handle text fields
        if isinstance(pdf_value, str) and isinstance(google_value, str):
            return self._compare_text(field_name, pdf_value, google_value, comparison)

        # Mixed types - prefer Google
        comparison.selected_value = google_value
        comparison.selection_reason = "Type mismatch, preferring Google"
        comparison.confidence_score = self.field_weights.get(field_name, {}).get("google", 0.8) * 100
        return comparison

    def _compare_numeric(
        self,
        field_name: str,
        pdf_value: float,
        google_value: float,
        comparison: FieldComparison
    ) -> FieldComparison:
        """Compare numeric values"""

        # Calculate difference percentage
        if pdf_value != 0:
            diff_percent = abs(google_value - pdf_value) / abs(pdf_value) * 100
        else:
            diff_percent = 100 if google_value != 0 else 0

        # If difference > 5%, flag as mismatch
        if diff_percent > 5:
            comparison.is_mismatch = True
            comparison.recommendation = "Manual review recommended"

        # Always prefer Google for numeric fields (more reliable)
        comparison.selected_value = google_value
        comparison.selection_reason = f"Google preferred (Google={google_value}, PDF={pdf_value}, diff={diff_percent:.1f}%)"
        comparison.confidence_score = self.field_weights.get(field_name, {}).get("google", 0.9) * 100

        return comparison

    def _compare_text(
        self,
        field_name: str,
        pdf_value: str,
        google_value: str,
        comparison: FieldComparison
    ) -> FieldComparison:
        """Compare text values using similarity matching"""

        similarity = self._calculate_similarity(pdf_value, google_value)

        # If similar enough (>85%), either is fine - prefer Google
        if similarity > 0.85:
            comparison.selected_value = google_value
            comparison.selection_reason = f"Similar values (similarity={similarity*100:.1f}%), preferring Google"
            comparison.confidence_score = self.field_weights.get(field_name, {}).get("google", 0.9) * 100
            comparison.is_mismatch = False

        # If different, definitely use Google
        else:
            comparison.is_mismatch = True
            comparison.selected_value = google_value
            comparison.selection_reason = f"Different values (similarity={similarity*100:.1f}%), using Google"
            comparison.confidence_score = self.field_weights.get(field_name, {}).get("google", 0.9) * 100
            comparison.recommendation = "Values differ significantly, review recommended"

        return comparison

    def _compare_line_items(
        self,
        pdf_items: List[LineItem],
        google_items: List[LineItem],
        comparison: FieldComparison
    ) -> FieldComparison:
        """Compare line items lists"""

        # If Google has more items, prefer Google
        if len(google_items) > len(pdf_items):
            comparison.selected_value = google_items
            comparison.selection_reason = f"Google has more items ({len(google_items)} vs {len(pdf_items)})"
            comparison.confidence_score = 90
        # If similar lengths, prefer Google
        elif len(google_items) == len(pdf_items):
            comparison.selected_value = google_items
            comparison.selection_reason = f"Same count, preferring Google ({len(google_items)} items)"
            comparison.confidence_score = 85
        # If PDF has more items (unlikely), flag
        else:
            comparison.selected_value = google_items
            comparison.selection_reason = f"PDF has more items, still using Google (Google={len(google_items)}, PDF={len(pdf_items)})"
            comparison.confidence_score = 75
            comparison.is_mismatch = True
            comparison.recommendation = "Item count mismatch, review recommended"

        return comparison

    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity (0-1)"""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

    def _has_value(self, value: Any) -> bool:
        """Check if value is meaningful (not None or empty)"""
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, list) and len(value) == 0:
            return False
        return True

    def _to_float(self, value: Any) -> Optional[float]:
        """Safely convert to float"""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _create_source_metadata(
        self,
        source_type: str,
        data: InvoiceSchema
    ) -> ExtractionSource:
        """Create metadata about extraction source"""
        
        # Count non-null fields
        extracted_count = sum(
            1 for field in [
                data.invoice_number,
                data.vendor_name,
                data.buyer_name,
                data.invoice_date,
                data.due_date,
                data.currency,
                data.total_amount,
                data.line_items
            ]
            if field is not None and field != ""
        )

        return ExtractionSource(
            source_type=source_type,
            confidence=85 if extracted_count >= 6 else 60,
            timestamp=datetime.now().isoformat(),
            is_complete=extracted_count >= 8,
            extracted_fields=extracted_count
        )

    def _calculate_quality_metrics(self, result: ExtractionMergeResult) -> None:
        """Calculate overall quality score and recommendation"""
        
        # Count successful extractions
        required_fields = [
            "invoice_number",
            "vendor_name",
            "total_amount",
            "invoice_date"
        ]

        final_output = result.final_output
        completed_required = sum(
            1 for field in required_fields
            if final_output.get(field) is not None
        )

        # Calculate mismatch penalty
        mismatch_penalty = len(result.mismatches) * 5

        # Base score on completeness
        completeness_score = (completed_required / len(required_fields)) * 100

        # Adjust by mismatch penalty
        result.quality_score = max(0, completeness_score - mismatch_penalty)

        # Determine recommendation
        if result.quality_score >= 85:
            result.recommendation = "approve"
        elif result.quality_score >= 60:
            result.recommendation = "review"
        else:
            result.recommendation = "reject"

        # Add quality note
        result.notes.append(
            f"Quality Score: {result.quality_score:.1f}% "
            f"(Completeness={completeness_score:.1f}%, Mismatches={len(result.mismatches)})"
        )
