# Backend - Invoice Extraction API

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install Tesseract OCR (for scanned document support):
   
   **Windows:**
   - Download from: https://github.com/UB-Mannheim/tesseract/wiki
   - Install and add to PATH
   - Download German language pack: https://github.com/tesseract-ocr/tessdata
   - Place `deu.traineddata` in Tesseract's `tessdata` folder
   
   **macOS:**
   ```bash
   brew install tesseract
   brew install tesseract-lang  # Includes German
   ```
   
   **Linux (Ubuntu/Debian):**
   ```bash
   sudo apt-get install tesseract-ocr
   sudo apt-get install tesseract-ocr-deu  # German language pack
   ```

3. Set up environment variables:
   - Copy `.env.example` to `.env` (if it doesn't exist)
   - Add your MongoDB URL and Gemini API key:
   ```
   MONGODB_URL=mongodb://localhost:27017/
   MONGODB_DATABASE_NAME=invoicely
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

4. Run the server:
```bash
python main.py
```

The API will be available at http://localhost:8000

## Features

- **PDF Extraction**: Extracts structured invoice data from PDF documents
- **OCR Support**: Handles scanned PDFs using Tesseract OCR
- **Multi-Language**: Supports English and German invoices
- **Fallback Strategies**: Regex-based extraction fallback for flexible parsing
- **Comprehensive Validation**: Validates extracted data with scoring system (14+ rules)
- **MongoDB Storage**: Stores processed invoices with full metadata using GridFS
- **Batch Processing**: Process up to 50 files concurrently with controls

## Supported Document Types

- **Text-based PDFs**: Direct text extraction using pdfplumber
- **Scanned PDFs**: OCR using Tesseract (English + German support)
- **Language Support**: English and German invoices

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Endpoints

### Health & Status
- `GET /` - Root endpoint
- `GET /health` - Health check

### Upload & Process
- `POST /api/upload` - Upload single PDF file → Extract + Validate
- `POST /api/upload/batch` - Upload multiple PDF files → Batch processing (max 50 files)

### Validation
- `POST /api/validate` - Validate single invoice JSON object
- `POST /validate-json` - Validate list of invoice JSON objects (returns summary)

### Invoice Management
- `GET /api/invoices` - Get all invoices (with pagination)
- `GET /api/invoices/{id}` - Get single invoice by ID
- `GET /api/invoices/{id}/file` - Download stored file
- `DELETE /api/invoices/{id}` - Delete invoice and associated file

### Dashboard
- `GET /api/dashboard/stats` - Get dashboard statistics (total, valid/invalid, average score)

## Supported File Types

- **PDF Files Only**: Text-based and scanned PDFs
  - **Text PDFs**: Extracted via pdfplumber direct text parsing
  - **Scanned PDFs**: Requires Tesseract OCR setup for extraction
- **File Size Limit**: 35MB per file
- **Batch Limit**: Maximum 50 files per batch upload

## File Size Limits

- **Single file**: Max 35MB
- **Batch upload**: Max 50 files per batch

## Performance Notes

- Batch processing uses async/await with semaphore limiting (max 5 concurrent files)
- MongoDB GridFS used for reliable file storage
- API uses CORS for frontend integration
