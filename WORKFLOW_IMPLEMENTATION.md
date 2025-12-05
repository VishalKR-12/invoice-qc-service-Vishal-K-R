# Complete Workflow Implementation Guide

## **System Architecture Overview**

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Netlify)                       │
│                        HTML/CSS/JavaScript                      │
│                                                                 │
│  User uploads PDF → Display loading → Send to API              │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP POST /api/upload
                      │ (with PDF file)
                      ↓
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND (Render.com FastAPI)                  │
│                   Python FastAPI + MongoDB                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## **Step-by-Step Workflow (End-to-End)**

### **STEP 1: USER UPLOADS FILE**
```
Frontend (app.js)
├─ User selects PDF or drag-drops file
├─ Browser validates: .pdf extension, <35MB
├─ Calls: fetch(`${API_BASE_URL}/api/upload`, {POST, file})
└─ Shows loading indicator
```

**Location**: `frontend/app.js` lines 168-250
```javascript
async function handleFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_BASE_URL}/api/upload`, {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    // result contains: invoice_id, validation_result, message
}
```

---

### **STEP 2: BACKEND RECEIVES FILE**
```
FastAPI Endpoint: POST /api/upload
Location: backend/main.py lines 67-165

Entry Point Function:
async def upload_and_process(file: UploadFile = File(...))
```

**Process:**
1. **Validates file**
   - Check extension: .pdf, .jpg, .png, .docx
   - Check size: max 35MB
   - Check not empty

2. **Saves temp file**
   ```python
   with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
       temp_file.write(content)
       temp_file_path = temp_file.name
   ```

3. **Routes to extraction**
   ```python
   if file_type == 'pdf':
       extracted_data = extractor.extract_from_pdf(temp_file_path)
   ```

---

### **STEP 3: PDF EXTRACTION**
```
Module: backend/pdf_extractor.py
Class: PDFExtractor

Method: extract_from_pdf(pdf_path)
```

**Extraction Process:**

#### **3a. Try Text-Based Extraction First**
```python
def extract_from_pdf(self, pdf_path: str) -> InvoiceSchema:
    # Try pdfplumber (fastest - for digital PDFs)
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
    
    is_scanned = False  # Digital PDF flag
```

**Result**: Text content + metadata

#### **3b. If Text is Minimal → Use OCR**
```python
if len(text) < 100:  # Likely scanned/image
    # Convert PDF pages to images
    images = convert_from_path(pdf_path)
    
    # Use Tesseract OCR
    ocr_text = pytesseract.image_to_string(images[0])
    
    is_scanned = True  # Mark as OCR result
```

#### **3c. Extract Fields Using Regex + Gemini AI**
```python
# Initialize invoice schema (empty)
invoice = InvoiceSchema()

# Pattern-based extraction (FAST)
invoice.invoice_number = self._extract_invoice_number(text)
invoice.vendor_name = self._extract_vendor_name(text)
invoice.total_amount = self._extract_total_amount(text)

# AI-enhanced extraction (ACCURATE)
if self.use_gemini:
    # Send to Gemini for intelligent extraction
    prompt = f"""
    Extract invoice data from this text:
    {text}
    
    Return JSON with fields:
    - invoice_number
    - vendor_name
    - buyer_name
    - total_amount
    - currency
    - invoice_date
    - due_date
    - line_items
    """
    response = self.gemini_text_model.generate_content(prompt)
    # Parse JSON response and merge with regex results
```

**Output**: `InvoiceSchema` object with all fields populated

**Location**: `backend/pdf_extractor.py` lines 80-200

---

### **STEP 4: VALIDATION (Business Rules)**
```
Module: backend/validator.py
Class: InvoiceValidator

Method: validate(invoice: InvoiceSchema)
```

**Validation Rules:**

```python
def validate(self, invoice: InvoiceSchema) -> ValidationResult:
    errors = []
    warnings = []
    score = 100  # Start with perfect score
    
    # COMPLETENESS CHECKS
    if not invoice.invoice_number:
        errors.append("Missing invoice number")
        score -= 20
    
    if not invoice.vendor_name:
        errors.append("Missing vendor name")
        score -= 15
    
    # FORMAT CHECKS
    if invoice.total_amount and invoice.total_amount < 0:
        errors.append("Negative total amount")
        score -= 25
    
    # CONSISTENCY CHECKS
    if invoice.subtotal and invoice.tax_amount:
        calculated_total = invoice.subtotal + invoice.tax_amount
        if abs(invoice.total_amount - calculated_total) > 0.01:
            warnings.append("Total doesn't match subtotal + tax")
            score -= 10
    
    # LINE ITEMS VALIDATION
    if invoice.line_items:
        for item in invoice.line_items:
            if item.quantity and item.price:
                expected_total = item.quantity * item.price
                if abs(item.total - expected_total) > 0.01:
                    warnings.append(f"Line item {item.description} total mismatch")
    
    # Final scoring
    is_valid = len(errors) == 0 and score >= 70
    
    return ValidationResult(
        invoice_number=invoice.invoice_number,
        is_valid=is_valid,
        score=max(0, score),
        errors=errors,
        warnings=warnings,
        extracted_data=invoice
    )
```

**Output**: `ValidationResult` with score (0-100) and status

**Location**: `backend/validator.py` lines 1-150

---

### **STEP 5: GOOGLE VERIFICATION (AI-Powered)**
```
Module: backend/google_verifier.py
Class: GoogleVerifier

Method: verify_invoice(invoice: InvoiceSchema)
```

**This is OPTIONAL - only if user requests Google verification**

#### **5a. Initialize Gemini Model**
```python
def __init__(self):
    genai.configure(api_key=GEMINI_API_KEY)
    self.model = genai.GenerativeModel('gemini-1.5-flash')
```

#### **5b. Verify Each Field**

**Field 1: Vendor Name**
```python
def _verify_vendor_name(self, vendor_name: str, invoice: InvoiceSchema):
    prompt = f"""
    Verify this vendor/company name:
    Name: {vendor_name}
    
    Respond with JSON:
    {{
        "is_valid": true/false,
        "corrected_name": "corrected or original",
        "confidence": 0-100,
        "reasoning": "explanation"
    }}
    """
    
    response = self.model.generate_content(prompt)
    data = json.loads(response.text)
    
    # If corrected name differs, create correction
    if data['corrected_name'] != vendor_name:
        return FieldCorrection(
            field_name='vendor_name',
            original_value=vendor_name,
            corrected_value=data['corrected_name'],
            confidence=data['confidence'],
            source='Google Generative AI',
            reasoning=data['reasoning']
        )
```

**Field 2: Total Amount (Recalculation)**
```python
def _verify_total_amount(self, total_amount: float, invoice):
    if invoice.line_items and invoice.subtotal:
        calculated_total = invoice.subtotal + (invoice.tax_amount or 0)
        
        if abs(total_amount - calculated_total) > 0.01:
            return FieldCorrection(
                field_name='total_amount',
                original_value=total_amount,
                corrected_value=calculated_total,
                confidence=90,
                source='Line Items Recalculation',
                reasoning=f'Calculated: {invoice.subtotal} + {invoice.tax_amount}',
                requires_review=True
            )
```

**Field 3: Date Standardization**
```python
def _verify_date(self, date_str: str, field_name: str, invoice):
    prompt = f"""
    Standardize this date to YYYY-MM-DD format:
    Original: {date_str}
    
    Respond with JSON:
    {{
        "is_valid_date": true/false,
        "standardized_date": "YYYY-MM-DD",
        "confidence": 0-100
    }}
    """
    
    # Convert "01/15/2024" → "2024-01-15"
```

#### **5c. Calculate Confidence Score**
```python
# Confidence = average of all field corrections
overall_confidence = sum(correction.confidence for correction in corrections) / len(corrections)

# Determine status
if overall_confidence >= 85:
    status = "Verified"
elif overall_confidence >= 60:
    status = "Review Needed"
else:
    status = "Low Confidence"
```

**Output**: `VerificationResult` with corrections, confidence, and status

**Location**: `backend/google_verifier.py` lines 60-300

---

### **STEP 6: SAVE TO DATABASE**
```
Module: backend/database.py
Class: Database

Methods:
- save_invoice()
- save_file() [GridFS]
```

#### **6a. Save Invoice Data**
```python
def save_invoice(self, invoice_data, validation_result, file_id=None):
    """Save invoice to MongoDB"""
    
    document = {
        "invoice_number": invoice_data.get('invoice_number'),
        "vendor_name": invoice_data.get('vendor_name'),
        "buyer_name": invoice_data.get('buyer_name'),
        "total_amount": invoice_data.get('total_amount'),
        "currency": invoice_data.get('currency'),
        "invoice_date": invoice_data.get('invoice_date'),
        "is_valid": validation_result['is_valid'],
        "validation_score": validation_result['score'],
        "validation_errors": validation_result['errors'],
        "validation_warnings": validation_result['warnings'],
        "file_id": file_id,
        "created_at": datetime.utcnow(),
        "file_name": invoice_data.get('file_name'),
        "file_type": invoice_data.get('file_type')
    }
    
    result = db.invoices.insert_one(document)
    return str(result.inserted_id)  # Return MongoDB ObjectId
```

#### **6b. Save File to GridFS**
```python
def save_file(self, file_content, filename, content_type):
    """Save binary file (PDF, image) to GridFS"""
    
    file_id = self.fs.put(
        file_content,
        filename=filename,
        content_type=content_type,
        upload_date=datetime.utcnow()
    )
    return file_id
```

**Database Schema:**
```javascript
{
  "_id": ObjectId("..."),
  "invoice_number": "INV-2024-001",
  "vendor_name": "ABC Corp",
  "buyer_name": "XYZ Ltd",
  "total_amount": 1500.00,
  "currency": "USD",
  "invoice_date": "2024-01-15",
  "due_date": "2024-02-15",
  "is_valid": true,
  "validation_score": 92,
  "validation_errors": [],
  "validation_warnings": ["Tax amount seems high"],
  "file_id": ObjectId("..."),  // GridFS reference
  "file_name": "invoice.pdf",
  "file_type": "pdf",
  "created_at": ISODate("2024-01-15T10:30:00Z"),
  "line_items": [
    {
      "description": "Service",
      "quantity": 10,
      "price": 150,
      "total": 1500
    }
  ]
}
```

**Location**: `backend/database.py` lines 50-120

---

### **STEP 7: RETURN RESPONSE TO FRONTEND**
```
Backend returns: ProcessResponse

{
  "success": true,
  "invoice_id": "507f1f77bcf86cd799439011",
  "validation_result": {
    "invoice_id": "507f1f77bcf86cd799439011",
    "invoice_number": "INV-2024-001",
    "is_valid": true,
    "score": 92,
    "errors": [],
    "warnings": ["Tax amount seems high"],
    "extracted_data": {
      "invoice_number": "INV-2024-001",
      "vendor_name": "ABC Corp",
      "buyer_name": "XYZ Ltd",
      "total_amount": 1500.00,
      "currency": "USD",
      "invoice_date": "2024-01-15",
      "line_items": [...]
    }
  },
  "message": "Invoice processed successfully"
}
```

**Location**: `backend/main.py` lines 155-165

---

### **STEP 8: DISPLAY RESULTS IN FRONTEND**
```javascript
// frontend/app.js lines 300-400

async function handleFileUpload(file) {
    const response = await fetch(`${API_BASE_URL}/api/upload`, {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    currentInvoiceData = result;  // Store in global variable
    
    displayResults(result, file.name);  // Render on page
    navigateToPage('results');  // Navigate to results page
}

function displayResults(data, filename) {
    // Display extracted fields in grid
    const validationResult = data.validation_result;
    const extractedData = validationResult.extracted_data;
    
    // Show invoice number, vendor, buyer, etc.
    const dataGrid = document.getElementById('data-grid');
    dataGrid.innerHTML = '';
    
    const fields = [
        { key: 'invoice_number', label: 'Invoice Number' },
        { key: 'vendor_name', label: 'Vendor Name' },
        { key: 'buyer_name', label: 'Buyer Name' },
        { key: 'total_amount', label: 'Total Amount' }
    ];
    
    fields.forEach(field => {
        const value = extractedData[field.key];
        const fieldElement = document.createElement('div');
        fieldElement.className = 'data-field';
        fieldElement.innerHTML = `
            <div class="field-label">${field.label}</div>
            <div class="field-value">${value || 'Not found'}</div>
        `;
        dataGrid.appendChild(fieldElement);
    });
    
    // Show validation score
    const statusBadge = document.getElementById('status-badge');
    statusBadge.textContent = `Score: ${validationResult.score}`;
    
    // Color code: Green (80+), Yellow (60-79), Red (<60)
    if (validationResult.score >= 80) {
        statusBadge.style.background = '#28A745';  // Green
    } else if (validationResult.score >= 60) {
        statusBadge.style.background = '#FFC107';  // Yellow
    } else {
        statusBadge.style.background = '#DC3545';  // Red
    }
}
```

---

## **Complete Data Flow Diagram**

```
USER UPLOADS PDF
        ↓
   ┌────────────────────┐
   │ FRONTEND           │
   │ app.js             │
   │ handleFileUpload() │
   └────────┬───────────┘
            │ HTTP POST /api/upload
            ↓
   ┌────────────────────────────┐
   │ BACKEND                    │
   │ main.py                    │
   │ upload_and_process()       │
   └────────┬───────────────────┘
            │
            ├─→ ┌─────────────────────┐
            │   │ EXTRACT             │
            │   │ pdf_extractor.py    │
            │   │ extract_from_pdf()  │
            │   │                     │
            │   │ ├─ Regex extraction │
            │   │ ├─ Gemini AI        │
            │   │ └─ OCR (if needed)  │
            │   └──────────┬──────────┘
            │              │
            │              ↓ InvoiceSchema
            │
            ├─→ ┌──────────────────────────┐
            │   │ VALIDATE                 │
            │   │ validator.py             │
            │   │ validate()               │
            │   │                          │
            │   │ ├─ Completeness check    │
            │   │ ├─ Format check          │
            │   │ ├─ Consistency check     │
            │   │ └─ Business logic        │
            │   └──────────┬───────────────┘
            │              │
            │              ↓ ValidationResult (score, errors, warnings)
            │
            ├─→ ┌───────────────────────────┐
            │   │ VERIFY [OPTIONAL]         │
            │   │ google_verifier.py        │
            │   │ verify_invoice()          │
            │   │                           │
            │   │ ├─ Vendor verification    │
            │   │ ├─ Amount recalculation   │
            │   │ ├─ Date standardization   │
            │   │ └─ Confidence scoring     │
            │   └──────────┬────────────────┘
            │              │
            │              ↓ VerificationResult (corrections, confidence)
            │
            ├─→ ┌──────────────────────────┐
            │   │ SAVE TO DATABASE         │
            │   │ database.py              │
            │   │ save_invoice()           │
            │   │ save_file() [GridFS]     │
            │   └──────────┬───────────────┘
            │              │
            │              ↓ MongoDB
            │
            └─→ ┌──────────────────────────┐
                │ RETURN RESPONSE          │
                │ ProcessResponse          │
                │ {success, invoice_id,    │
                │  validation_result, ...} │
                └──────────┬───────────────┘
                           │
                           ↓ HTTP 200 JSON
                    ┌──────────────────┐
                    │ FRONTEND         │
                    │ displayResults() │
                    │ Render grid,     │
                    │ show score,      │
                    │ display warnings │
                    └──────────────────┘
```

---

## **Advanced Workflows**

### **Batch Processing Workflow**
```
POST /api/upload/batch (multiple files)
        ↓
For each file:
├─ Extract
├─ Validate
├─ Save to DB
└─ Collect results
        ↓
Return statistics:
{
  "total_files": 5,
  "successful": 4,
  "failed": 1,
  "success_rate": "80%",
  "results": [...]
}
```

**Location**: `frontend/app.js` lines 250-350, `backend/main.py` lines 360-420

### **Combined Validation + Verification**
```
POST /api/verify-and-validate
        ↓
1. Run standard validation
2. Run Google verification
3. Merge results
4. Generate recommendations
        ↓
Return combined response with approval recommendations
```

**Location**: `backend/main.py` lines 215-235

---

## **Error Handling Flow**

```
Any Step Fails
        ↓
Caught by try/except
        ↓
Log error to console
        ↓
Clean up temp files (if exists)
        ↓
Return HTTPException (status 500, error message)
        ↓
Frontend shows alert to user
```

**Example:**
```python
try:
    extracted_data = extractor.extract_from_pdf(temp_file_path)
except Exception as e:
    if temp_file_path and os.path.exists(temp_file_path):
        os.unlink(temp_file_path)  # Cleanup
    raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
```

---

## **Production vs Local Differences**

| Aspect | Local | Production (Render) |
|--------|-------|-------------------|
| **API URL** | `http://localhost:8000` | `https://invoice-qc-service-vishal-k-r.onrender.com` |
| **Database** | MongoDB Atlas (cloud) | MongoDB Atlas (cloud) |
| **Environment Variables** | `.env` file | Render dashboard |
| **File Storage** | GridFS on MongoDB | GridFS on MongoDB |
| **CORS** | Allow all (`*`) | Restrict to Netlify domain |
| **SSL/TLS** | No | Yes (HTTPS) |

---

## **Key Files in Workflow**

| File | Purpose | Key Functions |
|------|---------|---|
| `frontend/app.js` | UI/UX | `handleFileUpload()`, `displayResults()` |
| `backend/main.py` | API endpoints | `/api/upload`, `/api/verify-google` |
| `backend/pdf_extractor.py` | PDF → Text | `extract_from_pdf()` |
| `backend/validator.py` | Business rules | `validate()` |
| `backend/google_verifier.py` | AI verification | `verify_invoice()` |
| `backend/database.py` | Database CRUD | `save_invoice()`, `save_file()` |
| `backend/models.py` | Data schemas | `InvoiceSchema`, `ValidationResult` |

---

## **Quick Reference: Response Objects**

### **InvoiceSchema** (Extracted Data)
```python
{
    "invoice_number": "INV-001",
    "vendor_name": "ABC Corp",
    "buyer_name": "XYZ Ltd",
    "invoice_date": "2024-01-15",
    "due_date": "2024-02-15",
    "currency": "USD",
    "subtotal": 1000.00,
    "tax_amount": 100.00,
    "total_amount": 1100.00,
    "line_items": [
        {
            "description": "Service",
            "quantity": 10,
            "price": 100.00,
            "total": 1000.00
        }
    ]
}
```

### **ValidationResult**
```python
{
    "invoice_id": "507f1f77bcf86cd799439011",
    "invoice_number": "INV-001",
    "is_valid": true,
    "score": 92,
    "errors": [],
    "warnings": ["Field X is missing"],
    "extracted_data": {...}
}
```

### **VerificationResult** (Google AI)
```python
{
    "invoice_number": "INV-001",
    "overall_confidence": 87.5,
    "status": "Verified",
    "corrections": [
        {
            "field_name": "vendor_name",
            "original_value": "ABC Corp",
            "corrected_value": "ABC Corporation",
            "confidence": 92,
            "source": "Google Generative AI",
            "reasoning": "Standardized to official company name"
        }
    ]
}
```

---

## **How to Trace a Request**

1. **Frontend**: Open DevTools → Network tab → look for POST `/api/upload`
2. **Request body**: See file being sent
3. **Response**: See full JSON response with invoice_id
4. **Backend logs**: `python main.py` shows processing steps
5. **Database**: Check MongoDB Atlas to verify invoice saved
6. **File storage**: GridFS contains the PDF file

---

## **Performance Metrics**

| Operation | Typical Time |
|-----------|--------------|
| File upload | 1-2 seconds |
| PDF extraction | 2-5 seconds |
| Validation | <1 second |
| Google verification | 5-10 seconds (per field) |
| Database save | 1-2 seconds |
| **Total end-to-end** | **10-20 seconds** |

---

