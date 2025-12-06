import pdfplumber
import re
import json
import base64
import io
import os
from typing import Dict, Any, List, Optional
from models import InvoiceSchema, LineItem
from datetime import datetime
import google.generativeai as genai
from config import GEMINI_API_KEY
from PIL import Image

# Try importing OCR libraries
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("Warning: OCR libraries not available. Install pytesseract and pdf2image for scanned document support.")

class PDFExtractor:
    def __init__(self):
        # English date patterns
        self.date_patterns = [
            r'\d{4}-\d{2}-\d{2}',
            r'\d{2}/\d{2}/\d{4}',
            r'\d{2}-\d{2}-\d{4}',
            r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}',
            # German date patterns
            r'\d{1,2}\.\d{1,2}\.\d{4}',
            r'\d{1,2}\s+(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)[a-z]*\s+\d{4}',
            r'\d{1,2}\s+(?:Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)[a-z]*\s+\d{4}'
        ]
        
        self.currency_patterns = [
            r'\$', r'USD', r'EUR', r'€', r'GBP', r'£', r'INR', r'₹'
        ]
        
        # German invoice keywords
        self.german_keywords = {
            'invoice': ['Rechnung', 'Rechnungsnummer', 'Rechnungs-Nr'],
            'invoice_number': ['Rechnungsnummer', 'Rechnungs-Nr', 'Rechnung Nr', 'Rechnung #'],
            'vendor': ['Verkäufer', 'Lieferant', 'Von', 'Absender'],
            'buyer': ['Kunde', 'Käufer', 'An', 'Empfänger', 'Rechnungsempfänger'],
            'date': ['Datum', 'Rechnungsdatum', 'Ausstellungsdatum'],
            'due_date': ['Fälligkeitsdatum', 'Fällig am', 'Zahlungsziel'],
            'total': ['Gesamtbetrag', 'Gesamtsumme', 'Endbetrag', 'Summe'],
            'subtotal': ['Zwischensumme', 'Zwischen-Summe'],
            'tax': ['MwSt', 'Mehrwertsteuer', 'Umsatzsteuer', 'Steuer', 'MwSt.', 'USt'],
            'payment_terms': ['Zahlungsbedingungen', 'Zahlungsziel', 'Zahlbar bis']
        }
        
        # Initialize Gemini API
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            # Use gemini-2.5-flash (latest model with best performance)
            self.gemini_text_model = genai.GenerativeModel('gemini-2.5-flash')
            # Vision is now integrated in gemini-2.5-flash
            try:
                self.gemini_vision_model = genai.GenerativeModel('gemini-2.5-flash')
                self.vision_available = True
            except Exception:
                self.gemini_vision_model = None
                self.vision_available = False
            self.use_gemini = True
        except Exception as e:
            print(f"Warning: Gemini API initialization failed: {str(e)}. Falling back to regex extraction.")
            self.use_gemini = False
            self.gemini_text_model = None
            self.gemini_vision_model = None
            self.vision_available = False

    def extract_from_pdf(self, pdf_path: str) -> InvoiceSchema:
        """Extract invoice data from PDF, handling both text-based and scanned PDFs"""
        # First, try to extract text directly from PDF
        text = ""
        is_scanned = False
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text += page_text
                    
                # Check if PDF is scanned (very little or no text extracted)
                if len(text.strip()) < 50:
                    is_scanned = True
        except Exception as e:
            print(f"Error reading PDF with pdfplumber: {str(e)}")
            is_scanned = True
        
        # If scanned or image-based, use OCR
        if is_scanned and OCR_AVAILABLE:
            print("Detected scanned PDF, using OCR...")
            ocr_text = self._extract_with_ocr(pdf_path)
            if ocr_text:
                text = ocr_text
            else:
                # Try Gemini Vision API for image-based PDFs
                if self.vision_available:
                    print("Trying Gemini Vision API for image-based PDF...")
                    vision_result = self._extract_with_gemini_vision(pdf_path)
                    if vision_result:
                        return vision_result
        
        # If we have text (from PDF or OCR), use Gemini text API
        if self.use_gemini and text.strip():
            try:
                gemini_result = self._extract_with_gemini(text)
                if gemini_result:
                    return gemini_result
            except Exception as e:
                print(f"Gemini extraction failed: {str(e)}. Falling back to regex extraction.")
        
        # Fall back to regex-based extraction
        return self._parse_invoice_text(text)
    
    def _extract_with_ocr(self, pdf_path: str) -> Optional[str]:
        """Extract text from scanned PDF using Tesseract OCR with German language support"""
        try:
            # Convert PDF pages to images
            images = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=5)
            
            all_text = []
            for image in images:
                # Use German + English language for OCR
                text = pytesseract.image_to_string(image, lang='deu+eng')
                all_text.append(text)
            
            return '\n'.join(all_text)
        except Exception as e:
            print(f"OCR extraction failed: {str(e)}")
            return None
    
    def _extract_with_gemini_vision(self, pdf_path: str) -> Optional[InvoiceSchema]:
        """Extract invoice data using Gemini Vision API for image-based PDFs"""
        try:
            # Convert first page to image
            images = convert_from_path(pdf_path, dpi=200, first_page=1, last_page=1)
            if not images:
                return None
            
            # Convert PIL image to format Gemini can use
            img_byte_arr = io.BytesIO()
            images[0].save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            
            prompt = """Analyze this invoice image and extract structured data. The invoice may be in English or German. 
Return ONLY a valid JSON object with the following structure. Do not include any explanations or markdown formatting, just the JSON:

{
  "invoice_number": "string or null",
  "vendor_name": "string or null",
  "buyer_name": "string or null",
  "vendor_address": "string or null",
  "buyer_address": "string or null",
  "invoice_date": "YYYY-MM-DD format or null",
  "due_date": "YYYY-MM-DD format or null",
  "currency": "USD/EUR/GBP/INR etc or null",
  "subtotal": number or null,
  "tax_amount": number or null,
  "total_amount": number or null,
  "payment_terms": "string or null",
  "line_items": [
    {
      "description": "string",
      "quantity": number or null,
      "price": number or null,
      "total": number or null
    }
  ]
}

Common German terms:
- Rechnung = Invoice
- Rechnungsnummer = Invoice Number
- Kunde/Käufer = Buyer/Customer
- Verkäufer/Lieferant = Vendor
- Datum = Date
- Fälligkeitsdatum = Due Date
- Gesamtbetrag = Total Amount
- MwSt/Umsatzsteuer = Tax/VAT
- Zwischensumme = Subtotal"""
            
            response = self.gemini_vision_model.generate_content([prompt, Image.open(img_byte_arr)])
            response_text = response.text.strip()
            
            # Clean up response
            response_text = self._clean_json_response(response_text)
            
            # Parse JSON response
            data = json.loads(response_text)
            
            # Convert to InvoiceSchema
            return InvoiceSchema(**data)
            
        except Exception as e:
            print(f"Gemini Vision API error: {str(e)}")
            return None
    
    def _extract_with_gemini(self, text: str) -> Optional[InvoiceSchema]:
        """Extract invoice data using Gemini API with multi-language support"""
        prompt = """Analyze the following invoice text and extract structured data. The invoice may be in English or German.
Return ONLY a valid JSON object with the following structure. Do not include any explanations or markdown formatting, just the JSON:

{
  "invoice_number": "string or null",
  "vendor_name": "string or null",
  "buyer_name": "string or null",
  "vendor_address": "string or null",
  "buyer_address": "string or null",
  "invoice_date": "YYYY-MM-DD format or null",
  "due_date": "YYYY-MM-DD format or null",
  "currency": "USD/EUR/GBP/INR etc or null",
  "subtotal": number or null,
  "tax_amount": number or null,
  "total_amount": number or null,
  "payment_terms": "string or null",
  "line_items": [
    {
      "description": "string",
      "quantity": number or null,
      "price": number or null,
      "total": number or null
    }
  ]
}

Common German invoice terms:
- Rechnung/Rechnungsnummer = Invoice/Invoice Number
- Kunde/Käufer/Rechnungsempfänger = Buyer/Customer
- Verkäufer/Lieferant = Vendor
- Datum/Rechnungsdatum = Date/Invoice Date
- Fälligkeitsdatum/Fällig am = Due Date
- Gesamtbetrag/Gesamtsumme = Total Amount
- Zwischensumme = Subtotal
- MwSt/Mehrwertsteuer/Umsatzsteuer = Tax/VAT
- Zahlungsbedingungen/Zahlungsziel = Payment Terms

Invoice Text:
""" + text[:8000]  # Limit text to avoid token limits

        try:
            response = self.gemini_text_model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Clean up response
            response_text = self._clean_json_response(response_text)
            
            # Parse JSON response
            data = json.loads(response_text)
            
            # Convert to InvoiceSchema
            return InvoiceSchema(**data)
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse Gemini JSON response: {str(e)}")
            if 'response_text' in locals():
                print(f"Response was: {response_text[:500]}")
            return None
        except Exception as e:
            print(f"Gemini API error: {str(e)}")
            return None
    
    def _clean_json_response(self, response_text: str) -> str:
        """Clean up JSON response from Gemini API"""
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        return response_text.strip()

    def _parse_invoice_text(self, text: str) -> InvoiceSchema:
        """Parse invoice text using regex patterns (supports English and German)"""
        lines = text.split('\n')

        invoice_data = {
            "invoice_number": self._extract_invoice_number(text),
            "vendor_name": self._extract_vendor_name(lines),
            "buyer_name": self._extract_buyer_name(text),
            "vendor_address": self._extract_address(text, "vendor"),
            "buyer_address": self._extract_address(text, "buyer"),
            "invoice_date": self._extract_date(text, "invoice"),
            "due_date": self._extract_date(text, "due"),
            "currency": self._extract_currency(text),
            "total_amount": self._extract_total_amount(text),
            "subtotal": self._extract_subtotal(text),
            "tax_amount": self._extract_tax(text),
            "payment_terms": self._extract_payment_terms(text),
            "line_items": self._extract_line_items(text)
        }

        return InvoiceSchema(**invoice_data)

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """Extract invoice number (English and German)"""
        patterns = [
            # English patterns
            r'Invoice\s*#?\s*:?\s*([A-Z0-9\-]+)',
            r'Invoice\s+Number\s*:?\s*([A-Z0-9\-]+)',
            r'INV[-#]?(\d+)',
            r'#\s*(\d{4,})',
            # German patterns
            r'Rechnung\s*(?:Nr|Nummer|#)?\s*:?\s*([A-Z0-9\-]+)',
            r'Rechnungsnummer\s*:?\s*([A-Z0-9\-]+)',
            r'Rechnungs-Nr\s*:?\s*([A-Z0-9\-]+)',
            r'Rechnung\s+#?\s*:?\s*([A-Z0-9\-]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_vendor_name(self, lines: List[str]) -> Optional[str]:
        """Extract vendor name"""
        keywords = ['invoice', 'date', 'bill to', 'ship to', 'rechnung', 'datum', 'kunde']
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            if line and not any(keyword in line.lower() for keyword in keywords):
                if len(line) > 2 and len(line) < 100:
                    return line
        return None

    def _extract_buyer_name(self, text: str) -> Optional[str]:
        """Extract buyer name (English and German)"""
        patterns = [
            # English
            r'Bill\s+To\s*:?\s*\n\s*([^\n]+)',
            r'Buyer\s*:?\s*\n\s*([^\n]+)',
            r'Customer\s*:?\s*\n\s*([^\n]+)',
            # German
            r'Kunde\s*:?\s*\n\s*([^\n]+)',
            r'Käufer\s*:?\s*\n\s*([^\n]+)',
            r'Rechnungsempfänger\s*:?\s*\n\s*([^\n]+)',
            r'An\s*:?\s*\n\s*([^\n]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_address(self, text: str, address_type: str) -> Optional[str]:
        """Extract address (supports German addresses)"""
        if address_type == "vendor":
            lines = text.split('\n')[:15]
        else:
            patterns = [
                r'Bill\s+To\s*:?\s*\n((?:[^\n]+\n){1,4})',
                r'Kunde\s*:?\s*\n((?:[^\n]+\n){1,4})',
                r'Rechnungsempfänger\s*:?\s*\n((?:[^\n]+\n){1,4})'
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            return None

        address_lines = []
        for line in lines:
            # English and German address patterns
            if re.search(r'\d+.*(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|way|straße|strasse|weg|platz|allee)', line, re.IGNORECASE):
                address_lines.append(line.strip())
            elif re.search(r'\d{5}(?:-\d{4})?', line):  # ZIP code pattern
                address_lines.append(line.strip())
                break

        return ' '.join(address_lines) if address_lines else None

    def _extract_date(self, text: str, date_type: str) -> Optional[str]:
        """Extract date (English and German)"""
        if date_type == "invoice":
            patterns = [
                r'Invoice\s+Date\s*:?\s*([^\n]+)',
                r'Date\s*:?\s*([^\n]+)',
                r'Issued\s*:?\s*([^\n]+)',
                r'Datum\s*:?\s*([^\n]+)',
                r'Rechnungsdatum\s*:?\s*([^\n]+)',
                r'Ausstellungsdatum\s*:?\s*([^\n]+)'
            ]
        else:
            patterns = [
                r'Due\s+Date\s*:?\s*([^\n]+)',
                r'Payment\s+Due\s*:?\s*([^\n]+)',
                r'Fälligkeitsdatum\s*:?\s*([^\n]+)',
                r'Fällig\s+am\s*:?\s*([^\n]+)',
                r'Zahlungsziel\s*:?\s*([^\n]+)'
            ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                for date_pattern in self.date_patterns:
                    date_match = re.search(date_pattern, date_str, re.IGNORECASE)
                    if date_match:
                        return date_match.group(0)
        return None

    def _extract_currency(self, text: str) -> Optional[str]:
        """Extract currency"""
        for currency in self.currency_patterns:
            if re.search(currency, text):
                currency_map = {
                    r'\$': 'USD', 'USD': 'USD',
                    'EUR': 'EUR', r'€': 'EUR',
                    'GBP': 'GBP', r'£': 'GBP',
                    'INR': 'INR', r'₹': 'INR'
                }
                for pattern, code in currency_map.items():
                    if re.search(pattern, currency):
                        return code
        return 'EUR'  # Default to EUR for German invoices

    def _extract_total_amount(self, text: str) -> Optional[float]:
        """Extract total amount (English and German)"""
        patterns = [
            # English
            r'Total\s*:?\s*\$?\s*([\d,]+\.?\d*)',
            r'Total\s+Amount\s*:?\s*\$?\s*([\d,]+\.?\d*)',
            r'Amount\s+Due\s*:?\s*\$?\s*([\d,]+\.?\d*)',
            r'Grand\s+Total\s*:?\s*\$?\s*([\d,]+\.?\d*)',
            # German
            r'Gesamtbetrag\s*:?\s*€?\s*([\d,]+\.?\d*)',
            r'Gesamtsumme\s*:?\s*€?\s*([\d,]+\.?\d*)',
            r'Endbetrag\s*:?\s*€?\s*([\d,]+\.?\d*)',
            r'Summe\s*:?\s*€?\s*([\d,]+\.?\d*)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '').replace('.', '').replace(' ', '')
                # Handle German number format (1.234,56)
                if ',' in match.group(1) and '.' in match.group(1):
                    parts = match.group(1).split(',')
                    amount_str = parts[0].replace('.', '') + '.' + parts[1]
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None

    def _extract_subtotal(self, text: str) -> Optional[float]:
        """Extract subtotal (English and German)"""
        patterns = [
            r'Subtotal\s*:?\s*\$?\s*([\d,]+\.?\d*)',
            r'Sub\s+Total\s*:?\s*\$?\s*([\d,]+\.?\d*)',
            r'Zwischensumme\s*:?\s*€?\s*([\d,]+\.?\d*)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '').replace('.', '').replace(' ', '')
                if ',' in match.group(1) and '.' in match.group(1):
                    parts = match.group(1).split(',')
                    amount_str = parts[0].replace('.', '') + '.' + parts[1]
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None

    def _extract_tax(self, text: str) -> Optional[float]:
        """Extract tax/VAT (English and German)"""
        patterns = [
            r'Tax\s*:?\s*\$?\s*([\d,]+\.?\d*)',
            r'VAT\s*:?\s*\$?\s*([\d,]+\.?\d*)',
            r'GST\s*:?\s*\$?\s*([\d,]+\.?\d*)',
            r'MwSt\s*:?\s*€?\s*([\d,]+\.?\d*)',
            r'MwSt\.\s*:?\s*€?\s*([\d,]+\.?\d*)',
            r'Mehrwertsteuer\s*:?\s*€?\s*([\d,]+\.?\d*)',
            r'Umsatzsteuer\s*:?\s*€?\s*([\d,]+\.?\d*)',
            r'USt\s*:?\s*€?\s*([\d,]+\.?\d*)',
            r'Steuer\s*:?\s*€?\s*([\d,]+\.?\d*)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '').replace('.', '').replace(' ', '')
                if ',' in match.group(1) and '.' in match.group(1):
                    parts = match.group(1).split(',')
                    amount_str = parts[0].replace('.', '') + '.' + parts[1]
                try:
                    return float(amount_str)
                except ValueError:
                    continue
        return None

    def _extract_payment_terms(self, text: str) -> Optional[str]:
        """Extract payment terms (English and German)"""
        patterns = [
            r'Payment\s+Terms\s*:?\s*([^\n]+)',
            r'Terms\s*:?\s*([^\n]+)',
            r'Net\s+\d+',
            r'Due\s+(?:on|in)\s+[^\n]+',
            r'Zahlungsbedingungen\s*:?\s*([^\n]+)',
            r'Zahlungsziel\s*:?\s*([^\n]+)',
            r'Zahlbar\s+bis\s*:?\s*([^\n]+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0 if 'Net' in pattern or 'Due' in pattern else 1).strip()
        return None

    def _extract_line_items(self, text: str) -> List[LineItem]:
        """Extract line items (English and German)"""
        line_items = []
        lines = text.split('\n')

        in_items_section = False
        for line in lines:
            # Check for item section header (English and German)
            if (re.search(r'description|item|product|service|beschreibung|artikel|position|posten', line, re.IGNORECASE) and 
                re.search(r'qty|quantity|price|amount|total|menge|preis|betrag|summe', line, re.IGNORECASE)):
                in_items_section = True
                continue

            if in_items_section:
                if re.search(r'subtotal|total|tax|payment|zwischensumme|gesamt|steuer|zahlung', line, re.IGNORECASE):
                    break

                numbers = re.findall(r'([\d,]+\.?\d*)', line)
                if len(numbers) >= 2:
                    description_match = re.match(r'^([A-Za-zÄÖÜäöüß\s\(\)\.\-]+)', line)
                    if description_match:
                        description = description_match.group(1).strip()

                        try:
                            nums = [float(n.replace(',', '').replace('.', '')) for n in numbers]
                            if len(nums) >= 3:
                                line_items.append(LineItem(
                                    description=description,
                                    quantity=nums[0],
                                    price=nums[1],
                                    total=nums[2]
                                ))
                            elif len(nums) == 2:
                                line_items.append(LineItem(
                                    description=description,
                                    quantity=nums[0],
                                    price=None,
                                    total=nums[1]
                                ))
                        except (ValueError, IndexError):
                            continue

        return line_items
