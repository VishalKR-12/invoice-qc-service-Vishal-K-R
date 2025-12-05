# Invoice Extraction & Quality Control Service

A full-stack invoice processing system that extracts structured data from PDF invoices, validates the extracted information against business rules, and provides quality control reports through multiple interfaces.

---

## Overview

### What You Built

This project implements a complete **Invoice Extraction & Quality Control Service** with the following components:

1. **PDF Extraction Module** - Extracts structured data from PDF invoices using text parsing and pattern matching
2. **Validation Core** - Validates extracted data against completeness, format, business logic, and anomaly detection rules
3. **CLI Tool** - Command-line interface for batch processing of invoices
4. **HTTP API** - RESTful API built with FastAPI for programmatic access
5. **Web UI** - Full-featured web application for interactive invoice processing and quality control

### Parts Completed

- ✅ **Extraction** - Complete PDF extraction module with support for multiple invoice formats
- ✅ **Validation** - Comprehensive validation engine with 14+ rules and scoring system
- ✅ **CLI** - Full command-line interface with extract, validate, and full-run commands
- ✅ **API** - Complete HTTP API with all required endpoints plus batch processing
- ✅ **UI** - Full-stack web application with dashboard, upload, results, and invoice management

---

## Schema & Validation Design

### Fields Chosen

The system extracts the following invoice-level fields:

#### Core Invoice Fields (12 fields)

| Field | Type | Description | Rationale |
|-------|------|-------------|-----------|
| `invoice_number` | String | Unique invoice identifier | **Critical** - Required for invoice tracking and duplicate detection |
| `vendor_name` | String | Name of the seller/vendor | **Critical** - Essential for accounting and vendor management |
| `buyer_name` | String | Name of the buyer/customer | **Important** - Required for B2B invoice processing |
| `vendor_address` | String | Vendor's complete address | Useful for tax and compliance purposes |
| `buyer_address` | String | Buyer's complete address | Useful for shipping and billing verification |
| `invoice_date` | String | Date invoice was issued | **Critical** - Required for payment terms and aging analysis |
| `due_date` | String | Payment due date | Important for cash flow management |
| `currency` | String | Currency code (USD, EUR, etc.) | Required for multi-currency support |
| `subtotal` | Number | Amount before tax | Essential for tax calculations |
| `tax_amount` | Number | Tax/VAT amount | Required for tax reporting |
| `total_amount` | Number | Final invoice amount | **Critical** - Core financial field |
| `payment_terms` | String | Payment terms description | Useful for payment scheduling |

#### Line Items Structure

Line items are included as an optional JSON array:

```json
{
  "description": "Product/Service name",
  "quantity": 2,
  "price": 100.00,
  "total": 200.00
}
```

**Rationale for Line Items**: Line items are optional because:
- Many invoices have complex table formatting that makes extraction unreliable without advanced ML models
- Core invoice-level data (totals, dates, parties) is sufficient for most accounting workflows
- Line item extraction accuracy varies significantly with invoice format
- When available, line items provide additional validation opportunities (e.g., sum matches subtotal)

---

### Validation Rules

The validation system implements 14+ rules across four categories:

#### 1. Completeness Rules (4 rules)

| Rule | Description | Rationale | Score Impact |
|------|-------------|-----------|--------------|
| Invoice Number Present | Validates invoice number exists and is at least 3 characters | Invoice number is the primary identifier - without it, invoice cannot be tracked | -15 points |
| Vendor Name Present | Ensures vendor name is extracted | Vendor identification is critical for accounts payable | -15 points |
| Total Amount Present | Validates total amount field exists | Financial amount is essential for accounting | -15 points |
| Invoice Date Present | Ensures invoice date is extracted | Date is required for payment terms and aging | -15 points |

**Rationale**: These four fields are the absolute minimum required for invoice processing. Missing any makes the invoice unusable for financial records.

#### 2. Format & Type Validation Rules (4 rules)

| Rule | Description | Rationale | Score Impact |
|------|-------------|-----------|--------------|
| Date Format Validation | Validates invoice_date and due_date are parseable dates | Invalid dates break downstream systems and calculations | -10 points each |
| Amount Type Validation | Ensures amounts are numeric and non-negative | Negative amounts indicate errors; non-numeric breaks calculations | -15 points |
| Currency Code Validation | Checks currency is a valid ISO code (USD, EUR, etc.) | Invalid currency codes cause exchange rate errors | -3 points (warning) |
| Invoice Number Length | Minimum 3 characters for invoice number | Very short invoice numbers are likely extraction errors | -10 points |

**Rationale**: Proper data types and formats prevent data corruption in downstream accounting systems and ensure automated processing works correctly.

#### 3. Business Logic Rules (4 rules)

| Rule | Description | Rationale | Score Impact |
|------|-------------|-----------|--------------|
| Due Date After Invoice Date | Due date must not be before invoice date | Logically impossible - indicates data entry error | -15 points |
| Amount Calculation | Subtotal + Tax = Total (with 0.01 tolerance) | Mathematical consistency is critical for financial integrity | -20 points |
| Line Items Total Match | Sum of line items should match subtotal | Ensures line item extraction accuracy | -5 points (warning) |
| Payment Terms Reasonability | Payment terms should not exceed 365 days | Unusually long payment terms may indicate errors | -5 points (warning) |

**Rationale**: These rules catch common data entry errors and ensure mathematical consistency, which is critical for financial accuracy and preventing fraud.

#### 4. Anomaly Detection Rules (3+ rules)

| Rule | Description | Rationale | Score Impact |
|------|-------------|-----------|--------------|
| Duplicate Vendor/Buyer Check | Flags if vendor and buyer names are identical | B2B invoices should have different parties | -5 points (warning) |
| Unusual Amount Detection | Flags amounts over $1M (warning) or $10M (error) | Very large amounts may indicate errors or require special approval | -3 to -10 points |
| Date Reasonability | Flags invoices dated >2 years old or >30 days in future | Old invoices may be duplicates; future dates are errors | -3 to -5 points |

**Rationale**: These rules identify potential fraud, errors, or unusual cases that require manual review before processing.

#### Validation Scoring System

- **Starting Score**: 100 points
- **Valid Invoice**: Score ≥ 80 (can be processed automatically)
- **Warning Level**: Score 60-79 (review recommended before processing)
- **Invalid Invoice**: Score < 60 (requires correction before processing)

---

## Architecture

### Folder Structure

```
project/
├── backend/
│   ├── main.py              # FastAPI application & API routes
│   ├── models.py            # Pydantic data models (InvoiceSchema, ValidationResult)
│   ├── pdf_extractor.py     # PDF extraction logic (text parsing, pattern matching)
│   ├── validator.py          # Validation rules engine (14+ rules)
│   ├── database.py          # MongoDB operations (GridFS for file storage)
│   ├── config.py            # Configuration management (environment variables)
│   ├── cli.py               # Command-line interface (extract, validate, full-run)
│   ├── requirements.txt     # Python dependencies
│   ├── .env.example         # Environment variables template
│   ├── test_connection.py   # Database connection test utility
│   └── README.md            # Backend documentation
│
├── frontend/
│   ├── index.html           # Single-page application (all views)
│   ├── styles.css           # Complete styling (responsive design)
│   ├── app.js               # JavaScript logic (API calls, UI interactions)
│   └── README.md            # Frontend documentation
│
├── README.md                # This file
├── VALIDATION_RULES.md      # Detailed validation rules documentation
└── .gitignore               # Git ignore rules
```

### Extraction Pipeline

**Location**: `backend/pdf_extractor.py`

The extraction pipeline processes PDFs through the following steps:

1. **PDF Text Extraction**: Uses `pdfplumber` to extract raw text from PDF pages
2. **Text Normalization**: Cleans and normalizes extracted text (whitespace, encoding)
3. **Pattern Matching**: Applies regex patterns to find invoice fields:
   - Searches for labels (e.g., "Invoice No", "Invoice Number", "Rechnungsnummer")
   - Extracts values following labels
   - Handles multiple languages (English, German)
4. **Date Parsing**: Uses `python-dateutil` to parse various date formats
5. **Amount Extraction**: Extracts monetary values with currency detection
6. **Line Item Extraction**: Attempts to extract tabular line items (basic implementation)
7. **Fallback Strategies**: Multiple fallback patterns for different invoice formats
8. **Output**: Returns structured `InvoiceSchema` object

**Key Design Decisions**:
- Modular extraction functions per field family (dates, amounts, parties)
- Multiple pattern fallbacks for robustness
- Graceful degradation (returns null for missing fields rather than failing)

### Validation Core

**Location**: `backend/validator.py`

The validation core applies rules in four phases:

1. **Completeness Validation**: Checks required fields exist
2. **Format Validation**: Validates data types and formats
3. **Business Logic Validation**: Applies domain-specific rules
4. **Anomaly Detection**: Flags unusual patterns

**Scoring Algorithm**:
- Starts at 100 points
- Deducts points for each violation (weighted by severity)
- Errors deduct more than warnings
- Returns `ValidationResult` with score, errors, warnings, and validity status

**Key Design Decisions**:
- Weighted scoring based on field criticality
- Separate errors vs warnings for different severity levels
- Extensible rule system (easy to add new rules)

### CLI

**Location**: `backend/cli.py`

The CLI provides three main commands:

1. **`extract`**: Processes PDF directory → JSON file
   - Scans directory for PDF files
   - Extracts data from each PDF
   - Outputs structured JSON array

2. **`validate`**: Validates JSON file → Report
   - Reads invoices from JSON
   - Applies all validation rules
   - Prints summary statistics
   - Optionally saves detailed report
   - Exits with non-zero code if invalid invoices found

3. **`full-run`**: Extract + Validate end-to-end
   - Combines extraction and validation
   - Single command for complete workflow
   - Saves final validation report

**Key Features**:
- Uses `argparse` for argument parsing
- Human-readable progress output
- Exit codes for automation/CI integration
- Error handling per file (failures don't stop batch)

### API

**Location**: `backend/main.py`

The API provides the following endpoints:

**Core Endpoints**:
- `GET /health` - Health check endpoint
- `POST /api/upload` - Upload single PDF file → Extract + Validate
- `POST /api/upload/batch` - Upload multiple PDF files → Batch processing
- `POST /api/validate` - Validate single invoice JSON object
- `POST /validate-json` - Validate list of invoice JSON objects (returns summary)
- `GET /api/invoices` - Get all invoices (with pagination)
- `GET /api/invoices/{id}` - Get single invoice by ID
- `GET /api/invoices/{id}/file` - Download stored file
- `DELETE /api/invoices/{id}` - Delete invoice and associated file
- `GET /api/dashboard/stats` - Get dashboard statistics

**Key Features**:
- FastAPI framework (async support, automatic docs)
- File storage using MongoDB GridFS
- Batch processing with concurrency control (max 5 concurrent)
- CORS enabled for frontend integration
- Comprehensive error handling

### Frontend

**Location**: `frontend/`

The frontend is a single-page application (SPA) with multiple views:

1. **Dashboard**: Statistics overview (total invoices, valid/invalid counts, average score)
2. **Upload & Process**: File upload interface with drag-and-drop, batch processing support
3. **Extraction Results**: View extracted data, validation results, file preview with zoom/navigation
4. **All Invoices**: Browse all processed invoices, filter, view details
5. **Documentation**: Project documentation

**Key Features**:
- Vanilla JavaScript (no frameworks)
- Responsive design (mobile-friendly)
- Enhanced PDF preview (PDF.js with zoom and navigation)
- Zoom and navigation controls
- Batch results navigation (back button)
- Real-time progress indicators

### System Flow Diagram

```
┌─────────────┐
│   PDF Files │
│  (Input)    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────┐
│   Extraction Pipeline           │
│   (pdf_extractor.py)            │
│   • Text extraction              │
│   • Pattern matching             │
│   • Field extraction             │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Structured JSON               │
│   (InvoiceSchema)               │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Validation Core               │
│   (validator.py)                │
│   • Completeness checks         │
│   • Format validation            │
│   • Business logic               │
│   • Anomaly detection           │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Validation Results            │
│   • Score (0-100)                │
│   • Errors/Warnings              │
│   • Valid/Invalid status         │
└──────┬──────────────────────────┘
       │
       ├──────────────────┬──────────────────┐
       ▼                  ▼                  ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│   Reports   │   │     API     │   │     UI      │
│   (JSON)    │   │  (FastAPI)  │   │  (Web App)  │
└─────────────┘   └─────────────┘   └─────────────┘
       │                  │                  │
       └──────────────────┴──────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │   MongoDB       │
                 │   (Storage)     │
                 └─────────────────┘
```

---

## Setup & Installation

### Python Version

**Required**: Python 3.8 or higher

Check your Python version:
```bash
python --version
# or
python3 --version
```

### Backend Setup

1. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

2. **Create virtual environment** (recommended):
   ```bash
   # On Windows
   python -m venv venv
   venv\Scripts\activate

   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   This installs:
   - FastAPI (web framework)
   - pdfplumber (PDF extraction)
   - pymongo (MongoDB client)
   - gridfs (MongoDB file storage)
   - pydantic (data validation)
   - python-dateutil (date parsing)
   - And other dependencies

4. **Configure environment variables**:
   ```bash
   # Copy example file
   cp .env.example .env

   # Edit .env file with your MongoDB credentials
   ```

   **`.env` file contents**:
   ```env
   MONGODB_URL=mongodb://localhost:27017/
   MONGODB_DATABASE_NAME=invoicely
   GEMINI_API_KEY=your_gemini_api_key_here  # Optional, for advanced OCR
   ```

   **For MongoDB Atlas (cloud)**:
   ```env
   MONGODB_URL=mongodb+srv://username:password@cluster.mongodb.net/
   MONGODB_DATABASE_NAME=invoicely
   ```

5. **Set up MongoDB**:
   - **Local**: Install MongoDB and ensure it's running
   - **Atlas**: Create free cluster at https://www.mongodb.com/cloud/atlas
   - Configure `MONGODB_URL` in `.env` file:

6. **Test database connection** (optional):
   ```bash
   python test_connection.py
   ```

### Running the API

**Option 1: Using Python directly**:
```bash
cd backend
   python main.py
   ```

**Option 2: Using uvicorn** (recommended for development):
   ```bash
cd backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

   The API will be available at `http://localhost:8000`

**API Documentation**: Once running, visit `http://localhost:8000/docs` for interactive API documentation.

### Running the CLI

The CLI can be run from the backend directory:

**Extract command**:
```bash
cd backend
python cli.py extract --pdf-dir ./invoices --output extracted.json
```

**Validate command**:
```bash
cd backend
python cli.py validate --input extracted.json --report validation_report.json
```

**Full-run command**:
```bash
cd backend
python cli.py full-run --pdf-dir ./invoices --report final_report.json
```

**Note**: Make sure the backend dependencies are installed and virtual environment is activated (if using one).

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Update API endpoint** (if backend runs on different port):
   - Open `app.js`
   - Modify `API_BASE_URL` on line 1:
     ```javascript
     const API_BASE_URL = 'http://localhost:8000';
     ```

3. **Serve the frontend**:

   **Option A: Using Python**:
   ```bash
   python -m http.server 3000
   ```

   **Option B: Using Node.js**:
   ```bash
   npx http-server -p 3000
   ```

   **Option C: Using any web server**:
   - Serve the `frontend/` directory on port 3000

4. **Access the application**:
   - Open browser: `http://localhost:3000`
   - Ensure backend API is running on `http://localhost:8000`

---

## Usage

### CLI Usage

#### Extract Invoice Data from PDFs

```bash
cd backend
python cli.py extract --pdf-dir ./invoices --output extracted.json
```

**What it does**:
- Scans directory for all PDF files
- Extracts invoice data from each PDF
- Saves extracted data to JSON file

**Example output**:
```
Found 5 PDF file(s)
============================================================

[1/5] Processing: invoice1.pdf
  ✓ Extracted: Invoice #INV-001
[2/5] Processing: invoice2.pdf
  ✓ Extracted: Invoice #INV-002
...

✓ Extraction complete!
  Total processed: 5/5
  Output saved to: /path/to/extracted.json
```

#### Validate Extracted JSON

```bash
cd backend
python cli.py validate --input extracted.json --report validation_report.json
```

**What it does**:
- Reads invoices from JSON file
- Validates each invoice against all rules
- Prints summary statistics
- Saves detailed report (optional)

**Example output**:
```
Validating 5 invoice(s)...
============================================================
[1/5] ✓ VALID - Invoice #INV-001 (Score: 85)
[2/5] ✗ INVALID - Invoice #INV-002 (Score: 45)
    Error: Missing required field: Invoice Date
...

============================================================
VALIDATION SUMMARY
============================================================
Total invoices: 5
Valid: 4 (80.0%)
Invalid: 1 (20.0%)

Top Error Types:
  - Missing required field: Invoice Date: 1 occurrence(s)

✓ Report saved to: validation_report.json
```

**Exit codes**:
- `0`: All invoices are valid
- `1`: One or more invoices are invalid
- `130`: Operation cancelled (Ctrl+C)

#### Full Run (Extract + Validate)

```bash
cd backend
python cli.py full-run --pdf-dir ./invoices --report final_report.json
```

**What it does**:
1. Extracts invoice data from all PDFs
2. Validates all extracted invoices
3. Saves complete validation report

This is equivalent to running `extract` followed by `validate` in one command.

### API Usage

#### 1. Health Check

```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "service": "Invoicely API",
  "database": "connected"
}
```

#### 2. Upload and Process Single PDF File

```bash
curl -X POST "http://localhost:8000/api/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@invoice.pdf"
```

**Note**: Only PDF files are supported.

**Response**:
```json
{
  "success": true,
  "invoice_id": "507f1f77bcf86cd799439011",
  "validation_result": {
    "invoice_number": "INV-001",
    "is_valid": true,
    "score": 85,
    "errors": [],
    "warnings": ["Missing important field: Due Date"],
    "extracted_data": {
      "invoice_number": "INV-001",
      "vendor_name": "Acme Corp",
      "buyer_name": "Tech Solutions",
      "total_amount": 1500.00,
      ...
    }
  },
  "message": "Invoice processed successfully"
}
```

#### 3. Batch Upload Multiple PDF Files

```bash
curl -X POST "http://localhost:8000/api/upload/batch" \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf" \
  -F "files=@invoice3.pdf"
```

**Note**: Only PDF files are supported. Maximum 50 files per batch.

**Response**:
```json
{
  "success": true,
  "total_files": 3,
  "successful": 2,
  "failed": 1,
  "results": [
    {
      "invoice_id": "...",
      "validation_result": {...},
      "filename": "invoice1.pdf"
    },
    ...
  ],
  "errors": [
    {
      "filename": "invoice3.pdf",
      "error": "File size exceeds 35MB limit"
    }
  ]
}
```

#### 4. Validate Single Invoice JSON

```bash
curl -X POST "http://localhost:8000/api/validate" \
  -H "Content-Type: application/json" \
  -d '{
    "invoice_number": "INV-001",
    "vendor_name": "Acme Corp",
    "buyer_name": "Tech Solutions",
    "invoice_date": "2024-01-15",
    "total_amount": 1500.00,
    "currency": "USD"
  }'
```

**Response**:
```json
{
  "invoice_number": "INV-001",
  "is_valid": true,
  "score": 85,
  "errors": [],
  "warnings": ["Missing important field: Due Date"],
  "extracted_data": {...}
}
```

#### 5. Validate Multiple Invoices (JSON Array)

```bash
curl -X POST "http://localhost:8000/validate-json" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "invoice_number": "INV-001",
      "vendor_name": "Acme Corp",
      "total_amount": 1500.00,
      "invoice_date": "2024-01-15"
    },
    {
      "invoice_number": "INV-002",
      "vendor_name": "Tech Solutions",
      "total_amount": 2500.00,
      "invoice_date": "2024-01-20"
    }
  ]'
```

**Response**:
```json
{
  "summary": {
    "total_invoices": 2,
    "valid_invoices": 1,
    "invalid_invoices": 1,
    "error_counts": {
      "Missing required field: Invoice Date": 1
    }
  },
  "results": [
    {
      "invoice_number": "INV-001",
      "is_valid": true,
      "score": 85,
      "errors": [],
      "warnings": []
    },
    {
      "invoice_number": "INV-002",
      "is_valid": false,
      "score": 45,
      "errors": ["Missing required field: Invoice Date"],
      "warnings": []
    }
  ]
}
```

#### 6. Get All Invoices

```bash
curl "http://localhost:8000/api/invoices?limit=50&offset=0"
```

#### 7. Get Single Invoice

```bash
curl "http://localhost:8000/api/invoices/507f1f77bcf86cd799439011"
```

#### 8. Get Invoice File

```bash
curl "http://localhost:8000/api/invoices/507f1f77bcf86cd799439011/file" \
  --output invoice_file.pdf
```

#### 9. Delete Invoice

```bash
curl -X DELETE "http://localhost:8000/api/invoices/507f1f77bcf86cd799439011"
```

#### 10. Get Dashboard Statistics

```bash
curl "http://localhost:8000/api/dashboard/stats"
```

**Response**:
```json
{
  "total_invoices": 10,
  "valid_invoices": 8,
  "invalid_invoices": 2,
  "total_amount": 50000.00,
  "average_validation_score": 82.5
}
```

### Frontend Usage

#### Basic Operation

1. **Dashboard**:
   - View statistics: total invoices, valid/invalid counts, average score
   - Click "Get Started" to begin processing

2. **Upload & Process**:
   - **Single file**: Drag and drop or click "Upload Now" (PDF files only)
   - **Batch upload**: Select multiple PDF files (Ctrl+Click or drag multiple)
   - System processes files automatically
   - Batch results displayed with success/failure counts

3. **View Results**:
   - Click on any batch result item to view details
   - Use "Back to Batch Results" button to return to batch list
   - View extracted data in "Refined view" or "JSON view"
   - Use zoom controls for PDF preview
   - Download data as CSV or JSON

4. **All Invoices**:
   - Browse all processed invoices
   - Click "View" to see detailed results
   - Click "Delete" to remove invoices

#### PDF Preview Features

- **Zoom Controls**: Zoom in/out, fit to width, fit to page
- **Navigation**: Previous/next page navigation
- **Keyboard Shortcuts**: 
  - `Ctrl/Cmd + +/-` for zoom
  - `Ctrl/Cmd + 0` for fit to page
  - `Ctrl/Cmd + Left/Right` for page navigation

#### Dark Theme

The application includes a **pitch-black dark theme** with full accessibility support:

**Enabling Dark Theme**:
- Click the **theme toggle button** (sun/moon icon) in the top-right header
- Theme preference is automatically saved to browser localStorage
- Theme persists across page reloads and sessions

**Theme Features**:
- **Pitch-black background** (#0A0A0A) for reduced eye strain
- **High contrast** text (#E8E8E8) for readability
- **Accessibility compliant** - WCAG AA contrast ratios maintained
- **Smooth transitions** between light and dark modes
- **All components supported** - Dashboard, upload area, results, PDF previews, tables

**Theme Architecture**:
- Uses CSS custom properties (CSS variables) for theming
- `data-theme="dark"` attribute on `<html>` element controls theme
- Theme state managed via JavaScript and localStorage
- Responsive to system preferences (can be extended)

**Accessibility Features**:
- High contrast mode support via `@media (prefers-contrast: high)`
- Reduced motion support via `@media (prefers-reduced-motion: reduce)`
- Proper color contrast ratios (WCAG AA compliant)
- Theme toggle includes ARIA labels for screen readers

**Implementation Details**:
- Theme toggle located in header actions (top-right)
- Icon changes dynamically (sun for dark mode, moon for light mode)
- All UI components use CSS variables that adapt to theme
- PDF preview area properly styled for dark theme
- Tables, cards, and forms maintain readability in both themes

---

## AI Usage Notes

### AI Tools Used

This project was developed with assistance from **Claude (Anthropic)** AI assistant.

### How AI Was Used

#### 1. Architecture Design
- **Tool**: Claude AI
- **Usage**: Designed overall system architecture, recommended FastAPI, MongoDB, and modular structure
- **Contribution**: ~95% of initial architecture planning

#### 2. PDF Extraction Logic
- **Tool**: Claude AI + pdfplumber documentation
- **Usage**: Developed regex patterns for field extraction, created fallback strategies
- **Challenges**: Initial patterns were too strict, missed edge cases
  - **Solution**: Iteratively refined patterns with multiple test cases
- **AI Contribution**: ~80% of pattern development

#### 3. Validation Rules Implementation
- **Tool**: Claude AI
- **Usage**: Designed validation rule set, implemented scoring algorithm
- **AI Contribution**: ~90% of rule design and implementation

#### 4. Frontend Development
- **Tool**: Claude AI
- **Usage**: Implemented UI components, responsive design, interactive features
- **AI Contribution**: ~85% of frontend code

#### 5. CLI Tool Development
- **Tool**: Claude AI
- **Usage**: Designed CLI interface, implemented argument parsing, error handling
- **AI Contribution**: ~90% of CLI implementation

#### 6. API Endpoint Design
- **Tool**: Claude AI + FastAPI documentation
- **Usage**: Designed RESTful endpoints, error handling, batch processing
- **AI Contribution**: ~85% of API implementation

### Example Where AI's Suggestion Was Wrong/Incomplete

#### Challenge: Batch File Processing

**AI's Initial Suggestion**: Process files sequentially to avoid memory issues.

**Problem**: Sequential processing was too slow for batch operations.

**What I Did Instead**: 
- Implemented parallel processing with `asyncio.gather()`
- Added concurrency control using `asyncio.Semaphore` (max 5 concurrent)
- This improved performance significantly while maintaining resource control

**Lesson**: AI suggestions are starting points - performance requirements and system constraints require human judgment.

### AI Chat Topics

Key discussions with AI covered:
1. Schema design and field selection rationale
2. Validation rule prioritization and scoring weights
3. PDF extraction library comparison (pdfplumber vs PyPDF2 vs pdfminer)
4. Database choice (MongoDB vs PostgreSQL/Supabase)
5. Frontend framework selection (vanilla JS vs React vs Vue)
6. API endpoint structure and REST best practices
7. Error handling strategies
8. Security considerations (file upload validation, XSS prevention)
9. Batch processing architecture
10. File storage strategies (GridFS vs file system)

---

## Assumptions & Limitations

### What Was Intentionally Simplified

#### 1. Line Item Extraction
- **Simplification**: Basic line item extraction implemented
- **Reason**: Complex table extraction requires advanced ML models or specialized libraries
- **Impact**: Line items may be missed for complex invoice layouts
- **Future**: Could integrate ML-based table extraction (e.g., AWS Textract, Google Document AI)

#### 2. OCR Support
- **Simplification**: OCR support added but requires external dependencies (Tesseract)
- **Reason**: OCR adds complexity and dependencies
- **Impact**: Scanned PDFs may not extract correctly without OCR setup
- **Future**: Could integrate cloud OCR services (Google Vision, AWS Textract)

#### 3. Multi-language Support
- **Simplification**: Optimized for English and German invoices
- **Reason**: Pattern matching requires language-specific keywords
- **Impact**: Other languages may have lower extraction accuracy
- **Future**: Could add language detection and language-specific patterns

#### 4. Currency Conversion
- **Simplification**: No automatic currency conversion
- **Reason**: Requires real-time exchange rate APIs and adds complexity
- **Impact**: Multi-currency invoices stored as-is
- **Future**: Could integrate exchange rate APIs

#### 5. Duplicate Detection Across Database
- **Simplification**: Duplicate detection only checks vendor/buyer names within single invoice
- **Reason**: Cross-invoice duplicate detection requires database queries and matching algorithms
- **Impact**: Duplicate invoices across time may not be detected
- **Future**: Could implement fuzzy matching for duplicate detection

#### 6. User Authentication
- **Simplification**: No user authentication implemented
- **Reason**: Focus on core extraction/validation functionality
- **Impact**: All users have access to all invoices
- **Future**: Could add JWT-based authentication

#### 7. Real-time Progress Updates
- **Simplification**: Batch processing shows progress but not real-time per-file updates
- **Reason**: Would require WebSockets or Server-Sent Events
- **Impact**: Users see progress bar but not individual file status during processing
- **Future**: Could implement WebSocket for real-time updates

### Edge Cases That Might Break

#### 1. Large PDF Files
- **Issue**: Large PDF files may take longer to process
- **Current Limit**: 35MB file size limit
- **Mitigation**: File size validation enforced at upload time

#### 2. Scanned PDFs Without OCR
- **Issue**: Image-based PDFs without text layer will extract minimal data
- **Current Behavior**: Returns mostly empty fields
- **Mitigation**: OCR support available but requires Tesseract setup

#### 3. Non-Standard Invoice Formats
- **Issue**: Invoices with unusual layouts may have low extraction accuracy
- **Current Behavior**: Returns partial data, validation flags missing fields
- **Mitigation**: Multiple fallback patterns, but some formats may not be supported

#### 4. Corrupted PDF Files
- **Issue**: Corrupted PDFs may cause extraction to fail
- **Current Behavior**: Error returned, file marked as failed in batch
- **Mitigation**: Try-catch blocks prevent crashes

#### 5. Concurrent Batch Uploads
- **Issue**: Multiple users uploading large batches simultaneously may overwhelm server
- **Current Behavior**: No rate limiting implemented
- **Mitigation**: Concurrency control per batch (max 5 files), but no global rate limiting

#### 6. Database Connection Loss
- **Issue**: If MongoDB connection is lost, file processing continues but storage fails
- **Current Behavior**: Error logged, but processing continues
- **Mitigation**: Graceful degradation, but files may not be stored

#### 7. Very Long Invoice Numbers
- **Issue**: Extremely long invoice numbers (>100 chars) may cause display issues
- **Current Behavior**: No length limit enforced
- **Mitigation**: UI may truncate, but data stored correctly

#### 8. Special Characters in Text
- **Issue**: Invoices with unusual encoding or special characters may parse incorrectly
- **Current Behavior**: UTF-8 handling, but some edge cases may fail
- **Mitigation**: Text normalization, but not comprehensive

### Known Limitations

1. **PDF Only**: Only PDF files are supported for uploads (no images or DOCX files)
2. **PDF Format Dependency**: Only text-based PDFs fully supported (scanned PDFs require OCR setup)
3. **Template Variability**: Extraction accuracy varies significantly with invoice format
4. **Line Item Extraction**: Basic implementation - complex tables may be missed
5. **Language Support**: Optimized for English and German only
6. **Currency Conversion**: No automatic conversion between currencies
7. **File Size**: Limited to 35MB per file
8. **Batch Size**: Maximum 50 files per batch
9. **No Authentication**: All data accessible to anyone with API access
10. **No Rate Limiting**: API endpoints can be called without limits
11. **Single Database**: No replication or backup strategy implemented

---

## 📝 License

This project is provided as-is for educational and demonstration purposes.

---

## 📧 Support

For issues or questions, please refer to the documentation files:
- `README.md` - Main project documentation
- `VALIDATION_RULES.md` - Validation rules documentation
- Backend API docs: `http://localhost:8000/docs` (when running)

---
