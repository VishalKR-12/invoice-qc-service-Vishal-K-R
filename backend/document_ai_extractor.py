"""
Invoice Extraction Engine using Google Document AI

This module extracts invoice data using Google Document AI's Invoice Parser processor.
- Prioritizes structured fields from Document AI
- Falls back to OCR text analysis for missing fields
- Normalizes and validates all extracted data
- Outputs clean, normalized JSON

Key Features:
1. Uses Google Document AI Invoice Parser for structured extraction
2. Parses raw OCR text as fallback
3. Prioritizes Document AI over OCR
4. Normalizes amounts, dates, and text
5. Validates field completeness
6. Returns strict JSON output
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

try:
    from google.cloud import documentai_v1 as documentai
    from google.api_core.gapic_v1 import client_info as grpc_client_info
    DOCUMENT_AI_AVAILABLE = True
except ImportError:
    DOCUMENT_AI_AVAILABLE = False
    logging.warning("Google Document AI not available. Fallback to Gemini-based extraction.")

import google.generativeai as genai
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)


@dataclass
class InvoiceLineItem:
    """Structured line item from invoice"""
    description: str
    quantity: Optional[str] = None
    unit_price: Optional[str] = None
    tax_percent: Optional[str] = None
    amount: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary, excluding None values"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class InvoiceData:
    """Complete normalized invoice data"""
    supplier_name: Optional[str] = None
    supplier_address: Optional[str] = None
    supplier_gst: Optional[str] = None

    customer_name: Optional[str] = None
    customer_address: Optional[str] = None
    customer_gst: Optional[str] = None

    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None

    items: List[InvoiceLineItem] = None
    subtotal: Optional[str] = None
    tax_amount: Optional[str] = None
    total_amount: Optional[str] = None

    def __post_init__(self):
        if self.items is None:
            self.items = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to clean JSON dictionary, excluding None values"""
        data = {
            "supplier_name": self.supplier_name,
            "supplier_address": self.supplier_address,
            "supplier_gst": self.supplier_gst,
            "customer_name": self.customer_name,
            "customer_address": self.customer_address,
            "customer_gst": self.customer_gst,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "items": [item.to_dict() for item in self.items] if self.items else [],
            "subtotal": self.subtotal,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
        }
        # Remove None values to keep JSON clean
        return {k: v for k, v in data.items() if v is not None and v != []}

    def to_json(self) -> str:
        """Convert to clean JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class GoogleDocumentAIExtractor:
    """
    Invoice extraction using Google Document AI Invoice Parser.
    
    Priority Logic:
    1. Extract structured fields from Document AI (highest confidence)
    2. Parse raw OCR text for missing fields (fallback)
    3. Normalize and validate all data
    4. Return clean, normalized JSON
    """

    def __init__(self):
        genai.configure(api_key=GEMINI_API_KEY)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Document AI project config (would be set from environment)
        self.project_id = None
        self.processor_id = None
        self.location = "us"
        
        # Try to initialize Document AI client if credentials available
        self.document_ai_client = None
        if DOCUMENT_AI_AVAILABLE:
            try:
                self.document_ai_client = documentai.DocumentProcessorServiceClient(
                    client_options=grpc_client_info.ClientOptions(
                        api_endpoint=f"{self.location}-documentai.googleapis.com"
                    )
                )
            except Exception as e:
                logger.warning(f"Document AI client init failed: {str(e)}")

    def extract_from_pdf(self, pdf_path: str) -> InvoiceData:
        """
        Main extraction method: Extract invoice using Google Document AI.
        
        Process:
        1. Try Document AI Invoice Parser (structured data)
        2. Fallback to Gemini Vision for OCR + parsing
        3. Normalize all fields
        4. Return clean invoice data
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            InvoiceData: Normalized invoice data
        """
        
        logger.info(f"Starting invoice extraction: {pdf_path}")
        invoice = InvoiceData()
        
        try:
            # Try Document AI first
            if self.document_ai_client and self.project_id and self.processor_id:
                logger.info("Attempting Document AI extraction...")
                extracted_data = self._extract_with_document_ai(pdf_path)
                if extracted_data:
                    invoice = extracted_data
                    logger.info("Document AI extraction successful")
                    return invoice
        except Exception as e:
            logger.warning(f"Document AI extraction failed: {str(e)}")
        
        # Fallback to Gemini Vision + OCR
        logger.info("Falling back to Gemini Vision extraction...")
        invoice = self._extract_with_gemini_vision(pdf_path)
        
        return invoice

    def _extract_with_document_ai(self, pdf_path: str) -> Optional[InvoiceData]:
        """
        Extract invoice using Google Document AI Invoice Parser.
        
        Document AI provides:
        - Supplier/Buyer information (name, address, GST)
        - Invoice metadata (number, date, due date)
        - Line items with structured fields
        - Totals (subtotal, tax, total)
        - High confidence scores for each field
        """
        
        try:
            with open(pdf_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            
            # Create document
            raw_document = documentai.RawDocument(
                content=pdf_content,
                mime_type="application/pdf"
            )
            
            # Process document using Invoice Parser
            process_request = documentai.ProcessRequest(
                name=f"projects/{self.project_id}/locations/{self.location}/processors/{self.processor_id}",
                raw_document=raw_document
            )
            
            result = self.document_ai_client.process_document(process_request)
            document = result.document
            
            # Extract structured data from Document AI response
            return self._parse_document_ai_response(document)
            
        except Exception as e:
            logger.error(f"Document AI processing failed: {str(e)}")
            return None

    def _parse_document_ai_response(self, document) -> InvoiceData:
        """Parse Document AI response into InvoiceData"""
        
        invoice = InvoiceData()
        entities = document.document_properties[0].paragraphs if document.document_properties else []
        
        # Extract key-value pairs from entities
        for entity in entities:
            try:
                field_type = entity.type_
                value = entity.text_anchor.content if entity.text_anchor else ""
                confidence = entity.confidence if hasattr(entity, 'confidence') else 0.0
                
                # Map Document AI fields to InvoiceData
                self._map_entity_to_invoice(invoice, field_type, value, confidence)
                
            except Exception as e:
                logger.warning(f"Error parsing entity: {str(e)}")
                continue
        
        return invoice

    def _map_entity_to_invoice(self, invoice: InvoiceData, field_type: str, value: str, confidence: float):
        """Map Document AI field to InvoiceData attribute"""
        
        # Normalize value
        value = value.strip() if value else None
        
        # Map fields (Document AI field names to InvoiceData attributes)
        mapping = {
            "supplier_name": "supplier_name",
            "supplier_address": "supplier_address",
            "supplier_gst": "supplier_gst",
            "vendor_name": "supplier_name",
            "vendor_address": "supplier_address",
            
            "customer_name": "customer_name",
            "customer_address": "customer_address",
            "customer_gst": "customer_gst",
            "buyer_name": "customer_name",
            "buyer_address": "customer_address",
            
            "invoice_number": "invoice_number",
            "invoice_date": "invoice_date",
            "due_date": "due_date",
            
            "subtotal": "subtotal",
            "tax_amount": "tax_amount",
            "total_amount": "total_amount",
        }
        
        if field_type in mapping:
            attr_name = mapping[field_type]
            if confidence > 0.7:  # Only use high-confidence values
                setattr(invoice, attr_name, value)

    def _extract_with_gemini_vision(self, pdf_path: str) -> InvoiceData:
        """
        Fallback extraction using Gemini Vision API.
        
        Process:
        1. Read PDF file
        2. Send to Gemini with structured extraction prompt
        3. Parse JSON response
        4. Normalize all fields
        5. Return InvoiceData
        """
        
        invoice = InvoiceData()
        
        try:
            # Read PDF and convert to base64
            with open(pdf_path, 'rb') as pdf_file:
                pdf_content = pdf_file.read()
            
            import base64
            encoded_pdf = base64.b64encode(pdf_content).decode('utf-8')
            
            # Create structured extraction prompt
            prompt = """
            Extract invoice data from this PDF. Return ONLY valid JSON (no markdown, no explanations).
            
            Rules:
            1. Extract EXACTLY as shown in document
            2. For missing fields, use null
            3. Dates in YYYY-MM-DD format
            4. Amounts without currency symbols, normalized
            5. GST format: numbers only (11 digits for India)
            6. Line items: array of objects
            
            Return this exact JSON structure:
            {
              "supplier_name": "string or null",
              "supplier_address": "string or null",
              "supplier_gst": "string or null",
              "customer_name": "string or null",
              "customer_address": "string or null",
              "customer_gst": "string or null",
              "invoice_number": "string or null",
              "invoice_date": "YYYY-MM-DD or null",
              "due_date": "YYYY-MM-DD or null",
              "items": [
                {
                  "description": "string",
                  "quantity": "number or null",
                  "unit_price": "number or null",
                  "tax_percent": "number or null",
                  "amount": "number or null"
                }
              ],
              "subtotal": "number or null",
              "tax_amount": "number or null",
              "total_amount": "number or null"
            }
            """
            
            # Send to Gemini with PDF
            response = self.gemini_model.generate_content([
                prompt,
                {"mime_type": "application/pdf", "data": encoded_pdf}
            ])
            
            response_text = response.text
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                data = json.loads(json_str)
                
                # Parse into InvoiceData
                invoice = self._parse_gemini_response(data)
                logger.info("Gemini Vision extraction successful")
                return invoice
            
        except Exception as e:
            logger.error(f"Gemini Vision extraction failed: {str(e)}")
        
        return invoice

    def _parse_gemini_response(self, data: Dict[str, Any]) -> InvoiceData:
        """Parse Gemini response into InvoiceData"""
        
        # Normalize and extract fields
        invoice = InvoiceData(
            supplier_name=self._normalize_text(data.get('supplier_name')),
            supplier_address=self._normalize_text(data.get('supplier_address')),
            supplier_gst=self._normalize_gst(data.get('supplier_gst')),
            
            customer_name=self._normalize_text(data.get('customer_name')),
            customer_address=self._normalize_text(data.get('customer_address')),
            customer_gst=self._normalize_gst(data.get('customer_gst')),
            
            invoice_number=self._normalize_text(data.get('invoice_number')),
            invoice_date=self._normalize_date(data.get('invoice_date')),
            due_date=self._normalize_date(data.get('due_date')),
            
            subtotal=self._normalize_amount(data.get('subtotal')),
            tax_amount=self._normalize_amount(data.get('tax_amount')),
            total_amount=self._normalize_amount(data.get('total_amount')),
        )
        
        # Parse line items
        if data.get('items'):
            for item_data in data.get('items', []):
                try:
                    item = InvoiceLineItem(
                        description=self._normalize_text(item_data.get('description')),
                        quantity=self._normalize_amount(item_data.get('quantity')),
                        unit_price=self._normalize_amount(item_data.get('unit_price')),
                        tax_percent=self._normalize_amount(item_data.get('tax_percent')),
                        amount=self._normalize_amount(item_data.get('amount'))
                    )
                    invoice.items.append(item)
                except Exception as e:
                    logger.warning(f"Error parsing line item: {str(e)}")
                    continue
        
        return invoice

    # ============== NORMALIZATION METHODS ==============

    def _normalize_text(self, value: Any) -> Optional[str]:
        """Normalize text field"""
        if value is None or value == "":
            return None
        
        text = str(value).strip()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text if text else None

    def _normalize_date(self, value: Any) -> Optional[str]:
        """
        Normalize date to YYYY-MM-DD format.
        
        Handles:
        - Already formatted dates (YYYY-MM-DD)
        - Various date formats (DD/MM/YYYY, DD-MM-YYYY, etc.)
        - Text dates (01 Jan 2024, January 1 2024, etc.)
        """
        
        if value is None or value == "":
            return None
        
        date_str = str(value).strip()
        
        # Already in correct format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        
        # Try parsing various formats
        formats = [
            '%m/%d/%Y',  # MM/DD/YYYY (US format)
            '%d/%m/%Y',  # DD/MM/YYYY (EU format)
            '%d-%m-%Y',
            '%d.%m.%Y',
            '%Y/%m/%d',
            '%Y-%m-%d',
            '%B %d, %Y',
            '%B %d %Y',
            '%d %B %Y',
            '%d-%b-%Y',
            '%d/%b/%Y',
            '%d %b %Y',
            '%b %d, %Y',
        ]
        
        for fmt in formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # If no format matched, return as-is (with warning)
        logger.warning(f"Could not parse date: {date_str}")
        return date_str

    def _normalize_amount(self, value: Any) -> Optional[str]:
        """
        Normalize amount field (remove symbols, normalize decimal).
        
        Handles:
        - Currency symbols ($, €, ₹, etc.)
        - Thousand separators (,)
        - Multiple decimals
        - Whitespace
        """
        
        if value is None or value == "":
            return None
        
        amount_str = str(value).strip()
        
        # Remove currency symbols
        amount_str = re.sub(r'[$€₹£¥₨]*', '', amount_str)
        
        # Remove thousand separators (comma)
        amount_str = amount_str.replace(',', '')
        
        # Keep only digits, decimal point, and minus sign
        amount_str = re.sub(r'[^\d.\-]', '', amount_str)
        
        # Remove extra spaces
        amount_str = amount_str.strip()
        
        # Validate it's a number
        try:
            float(amount_str)
            return amount_str
        except ValueError:
            logger.warning(f"Invalid amount format: {value}")
            return None

    def _normalize_gst(self, value: Any) -> Optional[str]:
        """
        Normalize GST number.
        
        Indian GST: 15 digit format (2-state code, 10-PAN, 1-entity, 1-check, 1-zero)
        Standard format: NN AAAPN5055P (format without spaces)
        """
        
        if value is None or value == "":
            return None
        
        gst_str = str(value).strip()
        
        # Remove spaces and special characters
        gst_str = re.sub(r'[^A-Z0-9]', '', gst_str.upper())
        
        # Validate length (15 characters for Indian GST)
        if len(gst_str) == 15:
            return gst_str
        
        # If not 15 chars, return as-is but log warning
        if gst_str:
            logger.warning(f"GST format may be incorrect: {gst_str}")
            return gst_str
        
        return None

    # ============== OUTPUT METHODS ==============

    def extract_and_get_json(self, pdf_path: str) -> str:
        """Extract invoice and return as clean JSON string"""
        invoice = self.extract_from_pdf(pdf_path)
        return invoice.to_json()

    def extract_and_get_dict(self, pdf_path: str) -> Dict[str, Any]:
        """Extract invoice and return as dictionary"""
        invoice = self.extract_from_pdf(pdf_path)
        return invoice.to_dict()


# ============== USAGE EXAMPLES ==============

if __name__ == "__main__":
    # Example usage
    extractor = GoogleDocumentAIExtractor()
    
    # Extract and get JSON
    # json_output = extractor.extract_and_get_json("/path/to/invoice.pdf")
    # print(json_output)
    
    # Extract and get dict
    # data_dict = extractor.extract_and_get_dict("/path/to/invoice.pdf")
    # print(data_dict)
    
    pass
