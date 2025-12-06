"""
Enhanced PDF Extractor with Layout-Aware Rules and Fallback Heuristics

This module implements advanced extraction strategies:
- Layout-aware field detection
- Multiple fallback strategies for each field
- Fuzzy matching for buyer/vendor names
- Confidence scoring for extracted fields
- Priority-based extraction (Google > Layout > Regex)
"""

import pdfplumber
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from models import InvoiceSchema, LineItem
from datetime import datetime
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)

# Try importing optional libraries
try:
    import google.generativeai as genai
    from config import GEMINI_API_KEY
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Gemini API not available")

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR libraries not available")


class FieldExtraction:
    """Container for extracted field with confidence score"""
    def __init__(self, value: Any, confidence: float, source: str):
        self.value = value
        self.confidence = confidence  # 0-100
        self.source = source  # 'google', 'layout', 'regex', 'computed'


class EnhancedPDFExtractor:
    """Enhanced PDF extractor with layout-aware rules and confidence scoring"""
    
    def __init__(self):
        # Enhanced invoice number patterns
        self.invoice_number_patterns = [
            r'INV[-#]?(\d+)',
            r'#(\d{4,})',
            r'Invoice\s*#?\s*:?\s*([A-Z0-9\-]+)',
            r'Invoice\s+Number\s*:?\s*([A-Z0-9\-]+)',
            r'Rechnung(?:s)?(?:nummer|nr|#)?\s*:?\s*([A-Z0-9\-]+)',
        ]
        
        # Enhanced date patterns with formats
        self.date_patterns = [
            (r'(\d{4})-(\d{2})-(\d{2})', 'YYYY-MM-DD'),
            (r'(\d{2})/(\d{2})/(\d{4})', 'DD/MM/YYYY'),
            (r'(\d{2})-(\d{2})-(\d{4})', 'DD-MM-YYYY'),
            (r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})', 'DD Mon YYYY'),
        ]
        
        # Buyer name fuzzy match keywords
        self.buyer_keywords = [
            'Bill To', 'Ship To', 'Sold To', 'Customer', 'Buyer',
            'Kunde', 'Käufer', 'Rechnungsempfänger', 'An'
        ]
        
        # Initialize Gemini if available
        self.gemini_available = False
        if GEMINI_AVAILABLE and GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                # Use gemini-2.5-flash (latest model with best performance)
                self.gemini_model = genai.GenerativeModel('gemini-2.5-flash')
                self.gemini_available = True
                logger.info("Gemini API initialized successfully with gemini-2.5-flash")
            except Exception as e:
                logger.warning(f"Gemini API initialization failed: {e}")
    
    def extract_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract invoice data with confidence scores
        
        Returns:
            Dict with extracted fields and confidence scores
        """
        # Extract text from PDF
        text, layout_data = self._extract_text_with_layout(pdf_path)
        
        if not text or len(text.strip()) < 50:
            logger.warning("PDF appears to be scanned or empty")
            if OCR_AVAILABLE:
                text = self._extract_with_ocr(pdf_path)
        
        # Extract using multiple strategies
        extractions = {}
        
        # Strategy 1: Google Gemini (highest priority)
        google_data = None
        if self.gemini_available and text:
            google_data = self._extract_with_gemini(text)
        
        # Strategy 2: Layout-aware extraction
        layout_extractions = self._extract_with_layout_rules(text, layout_data)
        
        # Strategy 3: Regex fallback
        regex_extractions = self._extract_with_regex(text)
        
        # Merge extractions with priority: Google > Layout > Regex
        final_data = self._merge_extractions(google_data, layout_extractions, regex_extractions)
        
        # Apply fallback heuristics
        final_data = self._apply_fallback_heuristics(final_data, text, layout_data)
        
        # Compute missing fields
        final_data = self._compute_missing_fields(final_data)
        
        # Convert to InvoiceSchema
        invoice_data = self._to_invoice_schema(final_data)
        
        return invoice_data
    
    def _extract_text_with_layout(self, pdf_path: str) -> Tuple[str, List[Dict]]:
        """Extract text while preserving layout information"""
        text = ""
        layout_data = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
                    
                    # Extract words with positions
                    words = page.extract_words()
                    for word in words:
                        layout_data.append({
                            'text': word['text'],
                            'x0': word['x0'],
                            'y0': word['top'],
                            'x1': word['x1'],
                            'y1': word['bottom'],
                            'page': page_num
                        })
        except Exception as e:
            logger.error(f"Error extracting PDF layout: {e}")
        
        return text, layout_data
    
    def _extract_with_gemini(self, text: str) -> Optional[Dict]:
        """Extract using Google Gemini with structured prompt"""
        prompt = f"""Extract invoice data from this text. Return ONLY valid JSON with this exact structure:
{{
  "invoice_number": "string or null",
  "vendor_name": "string or null",
  "buyer_name": "string or null",
  "vendor_address": "string or null",
  "buyer_address": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "currency": "USD/EUR/GBP/INR or null",
  "subtotal": number or null,
  "tax_amount": number or null,
  "total_amount": number or null,
  "payment_terms": "string or null",
  "line_items": []
}}

Text:
{text[:6000]}"""
        
        try:
            response = self.gemini_model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean response
            response_text = response_text.replace('```json', '').replace('```', '').strip()
            
            data = json.loads(response_text)
            logger.info("Gemini extraction successful")
            return data
        except Exception as e:
            logger.warning(f"Gemini extraction failed: {e}")
            return None
    
    def _extract_with_layout_rules(self, text: str, layout_data: List[Dict]) -> Dict[str, FieldExtraction]:
        """Extract using layout-aware rules"""
        extractions = {}
        
        # Extract vendor name (usually at top of document)
        vendor = self._extract_vendor_layout_aware(layout_data)
        if vendor:
            extractions['vendor_name'] = FieldExtraction(vendor, 85, 'layout')
        
        # Extract buyer name using layout proximity
        buyer = self._extract_buyer_layout_aware(text, layout_data)
        if buyer:
            extractions['buyer_name'] = FieldExtraction(buyer, 80, 'layout')
        
        # Extract invoice number with high confidence
        inv_num = self._extract_invoice_number_reliable(text)
        if inv_num:
            extractions['invoice_number'] = FieldExtraction(inv_num, 90, 'layout')
        
        # Extract dates with format detection
        inv_date = self._extract_date_with_format(text, 'invoice')
        if inv_date:
            extractions['invoice_date'] = FieldExtraction(inv_date, 85, 'layout')
        
        due_date = self._extract_date_with_format(text, 'due')
        if due_date:
            extractions['due_date'] = FieldExtraction(due_date, 85, 'layout')
        
        # Extract amounts with normalization
        total = self._extract_amount_normalized(text, 'total')
        if total:
            extractions['total_amount'] = FieldExtraction(total, 90, 'layout')
        
        subtotal = self._extract_amount_normalized(text, 'subtotal')
        if subtotal:
            extractions['subtotal'] = FieldExtraction(subtotal, 85, 'layout')
        
        tax = self._extract_amount_normalized(text, 'tax')
        if tax:
            extractions['tax_amount'] = FieldExtraction(tax, 85, 'layout')
        
        return extractions
    
    def _extract_vendor_layout_aware(self, layout_data: List[Dict]) -> Optional[str]:
        """Extract vendor name from top of document"""
        if not layout_data:
            return None
        
        # Get words from top 20% of first page
        top_words = [w for w in layout_data if w['page'] == 0 and w['y0'] < 150]
        
        # Find first substantial text block (not keywords)
        keywords = ['invoice', 'bill', 'date', 'rechnung', 'datum']
        for word in top_words[:10]:
            text = word['text'].strip()
            if len(text) > 3 and not any(k in text.lower() for k in keywords):
                return text
        
        return None
    
    def _extract_buyer_layout_aware(self, text: str, layout_data: List[Dict]) -> Optional[str]:
        """Extract buyer name using fuzzy matching and layout proximity"""
        # Try fuzzy matching on buyer keywords
        for keyword in self.buyer_keywords:
            # Find keyword position
            pattern = re.escape(keyword) + r'\s*:?\s*\n\s*([^\n]+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: Find text near "To" or "An"
        for keyword in ['To:', 'An:', 'Customer:']:
            if keyword in text:
                idx = text.index(keyword)
                # Get next line
                next_line_match = re.search(r'\n\s*([^\n]+)', text[idx:])
                if next_line_match:
                    return next_line_match.group(1).strip()
        
        return None
    
    def _extract_invoice_number_reliable(self, text: str) -> Optional[str]:
        """Extract invoice number using reliable regex patterns"""
        for pattern in self.invoice_number_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                inv_num = match.group(1) if match.lastindex else match.group(0)
                # Validate: should be at least 3 characters
                if len(inv_num) >= 3:
                    return inv_num.strip()
        return None
    
    def _extract_date_with_format(self, text: str, date_type: str) -> Optional[str]:
        """Extract date and normalize to YYYY-MM-DD"""
        # Define search patterns based on type
        if date_type == 'invoice':
            search_patterns = [
                r'Invoice\s+Date\s*:?\s*([^\n]+)',
                r'Date\s*:?\s*([^\n]+)',
                r'Datum\s*:?\s*([^\n]+)',
            ]
        else:  # due date
            search_patterns = [
                r'Due\s+Date\s*:?\s*([^\n]+)',
                r'Payment\s+Due\s*:?\s*([^\n]+)',
                r'Fälligkeitsdatum\s*:?\s*([^\n]+)',
            ]
        
        # Find date string
        date_str = None
        for pattern in search_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                break
        
        if not date_str:
            return None
        
        # Parse and normalize date
        for pattern, format_type in self.date_patterns:
            match = re.search(pattern, date_str, re.IGNORECASE)
            if match:
                try:
                    if format_type == 'YYYY-MM-DD':
                        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                    elif format_type == 'DD/MM/YYYY':
                        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
                    elif format_type == 'DD-MM-YYYY':
                        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"
                    elif format_type == 'DD Mon YYYY':
                        month_map = {
                            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
                            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
                            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
                        }
                        month = month_map.get(match.group(2).lower()[:3], '01')
                        day = match.group(1).zfill(2)
                        return f"{match.group(3)}-{month}-{day}"
                except Exception:
                    continue
        
        return None
    
    def _extract_amount_normalized(self, text: str, amount_type: str) -> Optional[float]:
        """Extract and normalize amounts (handles commas and decimals)"""
        if amount_type == 'total':
            patterns = [
                r'Total\s*:?\s*[$€£₹]?\s*([\d,]+\.?\d*)',
                r'Total\s+Amount\s*:?\s*[$€£₹]?\s*([\d,]+\.?\d*)',
                r'Gesamtbetrag\s*:?\s*[$€£₹]?\s*([\d,]+\.?\d*)',
            ]
        elif amount_type == 'subtotal':
            patterns = [
                r'Subtotal\s*:?\s*[$€£₹]?\s*([\d,]+\.?\d*)',
                r'Zwischensumme\s*:?\s*[$€£₹]?\s*([\d,]+\.?\d*)',
            ]
        else:  # tax
            patterns = [
                r'Tax\s*:?\s*[$€£₹]?\s*([\d,]+\.?\d*)',
                r'VAT\s*:?\s*[$€£₹]?\s*([\d,]+\.?\d*)',
                r'MwSt\.?\s*:?\s*[$€£₹]?\s*([\d,]+\.?\d*)',
            ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1)
                # Normalize: remove commas, handle decimals
                normalized = amount_str.replace(',', '')
                try:
                    return float(normalized)
                except ValueError:
                    # Try European format (1.234,56 -> 1234.56)
                    if ',' in amount_str and '.' in amount_str:
                        normalized = amount_str.replace('.', '').replace(',', '.')
                        try:
                            return float(normalized)
                        except ValueError:
                            continue
        
        return None
    
    def _extract_with_regex(self, text: str) -> Dict[str, FieldExtraction]:
        """Basic regex extraction as fallback"""
        extractions = {}
        
        # Simple patterns with lower confidence
        inv_match = re.search(r'#(\d+)', text)
        if inv_match:
            extractions['invoice_number'] = FieldExtraction(inv_match.group(1), 60, 'regex')
        
        # Extract currency
        if '$' in text or 'USD' in text:
            extractions['currency'] = FieldExtraction('USD', 70, 'regex')
        elif '€' in text or 'EUR' in text:
            extractions['currency'] = FieldExtraction('EUR', 70, 'regex')
        
        return extractions
    
    def _merge_extractions(self, google_data: Optional[Dict], 
                          layout_data: Dict[str, FieldExtraction],
                          regex_data: Dict[str, FieldExtraction]) -> Dict[str, FieldExtraction]:
        """Merge extractions with priority: Google > Layout > Regex"""
        merged = {}
        
        # Start with regex (lowest priority)
        merged.update(regex_data)
        
        # Override with layout data
        for key, extraction in layout_data.items():
            if key not in merged or extraction.confidence > merged[key].confidence:
                merged[key] = extraction
        
        # Override with Google data (highest priority)
        if google_data:
            for key, value in google_data.items():
                if value is not None:
                    merged[key] = FieldExtraction(value, 95, 'google')
        
        return merged
    
    def _apply_fallback_heuristics(self, data: Dict[str, FieldExtraction], 
                                   text: str, layout_data: List[Dict]) -> Dict[str, FieldExtraction]:
        """Apply fallback heuristics for missing fields"""
        
        # If vendor name missing, use first non-keyword line
        if 'vendor_name' not in data or not data['vendor_name'].value:
            lines = text.split('\n')
            keywords = ['invoice', 'bill', 'date']
            for line in lines[:10]:
                line = line.strip()
                if line and len(line) > 3 and not any(k in line.lower() for k in keywords):
                    data['vendor_name'] = FieldExtraction(line, 50, 'heuristic')
                    break
        
        # If buyer name missing, search near address-like text
        if 'buyer_name' not in data or not data['buyer_name'].value:
            # Find first address pattern
            addr_match = re.search(r'\d+\s+\w+\s+(?:street|st|avenue|ave|road)', text, re.IGNORECASE)
            if addr_match:
                # Get text before address
                before_addr = text[:addr_match.start()]
                lines_before = before_addr.split('\n')
                if lines_before:
                    potential_buyer = lines_before[-1].strip()
                    if len(potential_buyer) > 3:
                        data['buyer_name'] = FieldExtraction(potential_buyer, 50, 'heuristic')
        
        return data
    
    def _compute_missing_fields(self, data: Dict[str, FieldExtraction]) -> Dict[str, FieldExtraction]:
        """Compute missing fields from available data"""
        
        # Compute tax if missing but subtotal and total available
        if ('tax_amount' not in data or not data['tax_amount'].value):
            if ('total_amount' in data and data['total_amount'].value and 
                'subtotal' in data and data['subtotal'].value):
                total = data['total_amount'].value
                subtotal = data['subtotal'].value
                if abs(total - subtotal) < total * 0.5:  # Sanity check
                    tax = total - subtotal
                    data['tax_amount'] = FieldExtraction(tax, 80, 'computed')
        
        # Compute subtotal if missing
        if ('subtotal' not in data or not data['subtotal'].value):
            if ('total_amount' in data and data['total_amount'].value and 
                'tax_amount' in data and data['tax_amount'].value):
                total = data['total_amount'].value
                tax = data['tax_amount'].value
                subtotal = total - tax
                if subtotal > 0:
                    data['subtotal'] = FieldExtraction(subtotal, 80, 'computed')
        
        return data
    
    def _to_invoice_schema(self, data: Dict[str, FieldExtraction]) -> InvoiceSchema:
        """Convert extracted data to InvoiceSchema"""
        invoice_dict = {}
        
        # Extract values from FieldExtraction objects
        for key, extraction in data.items():
            if extraction and extraction.value is not None:
                invoice_dict[key] = extraction.value
        
        # Add confidence scores as metadata (optional)
        confidence_scores = {
            key: extraction.confidence 
            for key, extraction in data.items() 
            if extraction
        }
        
        # Log confidence scores
        logger.info(f"Extraction confidence scores: {confidence_scores}")
        
        return InvoiceSchema(**invoice_dict)
    
    def _extract_with_ocr(self, pdf_path: str) -> Optional[str]:
        """Extract text using OCR for scanned documents"""
        if not OCR_AVAILABLE:
            return None
        
        try:
            images = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=3)
            text_parts = []
            for image in images:
                text = pytesseract.image_to_string(image, lang='eng+deu')
                text_parts.append(text)
            return '\n'.join(text_parts)
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return None
