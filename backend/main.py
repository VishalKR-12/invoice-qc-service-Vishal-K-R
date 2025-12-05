from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.responses import FileResponse
import os
import tempfile
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from models import ValidationResult, ProcessResponse, InvoiceSchema, GoogleVerificationResult
from pdf_extractor import PDFExtractor
from validator import InvoiceValidator
from google_verifier import GoogleVerifier
from database import Database
from pydantic import BaseModel
import mimetypes

app = FastAPI(title="Invoicely API", description="Invoice Extraction & Quality Control Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

db = Database()
extractor = PDFExtractor()
validator = InvoiceValidator()
google_verifier = GoogleVerifier()

@app.get("/")
async def root():
    return {"message": "Invoicely API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    try:
        # Test MongoDB connection
        db.client.server_info()
        return {"status": "healthy", "service": "Invoicely API", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "service": "Invoicely API", "database": "disconnected", "error": str(e)}

def get_file_type(filename: str) -> str:
    """Determine file type from filename extension"""
    if not filename:
        return "application/octet-stream"
    filename_lower = filename.lower()
    if filename_lower.endswith('.pdf'):
        return 'pdf'
    elif filename_lower.endswith(('.jpg', '.jpeg')):
        return 'image'
    elif filename_lower.endswith('.png'):
        return 'image'
    elif filename_lower.endswith('.gif'):
        return 'image'
    elif filename_lower.endswith('.webp'):
        return 'image'
    elif filename_lower.endswith('.bmp'):
        return 'image'
    elif filename_lower.endswith('.docx'):
        return 'docx'
    else:
        return 'other'

@app.post("/api/upload", response_model=ProcessResponse)
async def upload_and_process(file: UploadFile = File(...)):
    # Support multiple file types
    supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.docx']
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename_lower = file.filename.lower()
    is_supported = any(filename_lower.endswith(ext) for ext in supported_extensions)
    
    if not is_supported:
        raise HTTPException(status_code=400, detail="Only PDF, Image (JPG, PNG, GIF, WEBP, BMP), and DOCX files are supported")

    # Check file size - read content first to get actual size
    content = await file.read()
    file_size = len(content)
    
    if file_size > 35 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 35MB limit")
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    temp_file_path = None
    invoice_id = None
    file_id = None
    
    try:
        # Determine file type
        file_type = get_file_type(file.filename)
        
        # For PDF files, extract data
        extracted_data = None
        validation_result = None
        
        if file_type == 'pdf':
            # Content already read above for size check, write it to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            extracted_data = extractor.extract_from_pdf(temp_file_path)

            # Clean up temp file immediately after extraction
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                temp_file_path = None

            validation_result = validator.validate(extracted_data)
        else:
            # For non-PDF files, create minimal extracted_data structure
            from models import InvoiceSchema
            extracted_data = InvoiceSchema()
            from validator import ValidationResult as VR
            validation_result = VR(
                invoice_id=None,
                invoice_number=None,
                is_valid=False,
                score=0,
                errors=["File type not supported for extraction"],
                warnings=[],
                extracted_data=extracted_data
            )

        # Save file to GridFS
        try:
            content_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
            file_id = db.save_file(content, file.filename, content_type)
        except Exception as file_error:
            print(f"File save failed: {str(file_error)}")
            # Continue without file storage if it fails

        # Try to save to database
        try:
            invoice_data_dict = extracted_data.model_dump() if extracted_data else {}
            invoice_data_dict["file_name"] = file.filename
            invoice_data_dict["file_type"] = file_type
            
            invoice_id = db.save_invoice(
                invoice_data_dict,
                validation_result.model_dump(),
                file_id=file_id
            )
            validation_result.invoice_id = invoice_id
        except Exception as db_error:
            # If database save fails, still return the validation result
            # but log the error
            print(f"Database save failed: {str(db_error)}")
            invoice_id = None  # Explicitly set to None if save fails

        return ProcessResponse(
            success=True,
            invoice_id=invoice_id,
            validation_result=validation_result,
            message="Invoice processed successfully"
        )

    except Exception as e:
        # Clean up temp file if it still exists
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.post("/api/validate")
async def validate_invoice(invoice: InvoiceSchema):
    try:
        validation_result = validator.validate(invoice)
        return validation_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating invoice: {str(e)}")

@app.post("/api/verify-google")
async def verify_invoice_with_google(invoice: InvoiceSchema):
    """
    Verify extracted invoice data using Google APIs.
    
    Performs:
    - Vendor/buyer name validation
    - Invoice number format checking
    - Date standardization
    - Monetary field verification
    - Line item calculation validation
    - Auto-correction with confidence scoring
    
    Returns:
    - Original extracted data
    - Corrected data
    - List of corrections with confidence levels
    - Status (Verified, Review Needed, High Confidence)
    - Source citations
    """
    try:
        verification_result = google_verifier.verify_invoice(invoice)
        return verification_result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying invoice: {str(e)}")

@app.post("/api/verify-and-validate")
async def verify_and_validate(invoice: InvoiceSchema):
    """
    Complete invoice processing pipeline:
    1. Extract standard validation (completeness, format, business logic)
    2. Google API verification (auto-correction, confidence scoring)
    3. Combined results with recommendations
    """
    try:
        # Standard validation
        validation_result = validator.validate(invoice)
        
        # Google API verification
        verification_result = google_verifier.verify_invoice(invoice)
        
        # Combine results
        combined_response = {
            "invoice_number": invoice.invoice_number,
            "standard_validation": validation_result.dict(),
            "google_verification": verification_result.to_dict(),
            "recommendations": _generate_recommendations(validation_result, verification_result),
            "processed_at": datetime.now().isoformat()
        }
        
        return combined_response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in verification pipeline: {str(e)}")

@app.post("/api/verify-batch")
async def verify_batch(invoices: List[InvoiceSchema]):
    """
    Verify multiple invoices with Google APIs.
    Returns aggregated results and per-invoice corrections.
    """
    try:
        batch_results = []
        statistics = {
            "total_invoices": len(invoices),
            "verified": 0,
            "review_needed": 0,
            "high_confidence": 0,
            "low_confidence": 0,
            "total_corrections": 0,
            "average_confidence": 0.0
        }
        
        confidence_scores = []
        
        for invoice in invoices:
            verification_result = google_verifier.verify_invoice(invoice)
            result_dict = verification_result.to_dict()
            batch_results.append(result_dict)
            
            # Update statistics
            if verification_result.status == "Verified":
                statistics["verified"] += 1
            elif verification_result.status == "Review Needed":
                statistics["review_needed"] += 1
            elif verification_result.status == "High Confidence":
                statistics["high_confidence"] += 1
            else:
                statistics["low_confidence"] += 1
            
            statistics["total_corrections"] += len(verification_result.corrections)
            confidence_scores.append(verification_result.overall_confidence)
        
        if confidence_scores:
            statistics["average_confidence"] = sum(confidence_scores) / len(confidence_scores)
        
        return {
            "statistics": statistics,
            "results": batch_results,
            "processed_at": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying batch: {str(e)}")

def _generate_recommendations(validation_result, verification_result) -> Dict:
    """Generate recommendations based on validation and verification results"""
    recommendations = {
        "approval_ready": False,
        "requires_review": False,
        "required_actions": [],
        "confidence_level": "Low"
    }
    
    # Check validation errors
    if validation_result.errors:
        recommendations["requires_review"] = True
        recommendations["required_actions"].extend(validation_result.errors)
    
    # Check verification status
    if verification_result.status == "Review Needed":
        recommendations["requires_review"] = True
        for correction in verification_result.corrections:
            if correction.requires_review:
                recommendations["required_actions"].append(
                    f"Review correction for {correction.field_name}: {correction.original_value} → {correction.corrected_value}"
                )
    
    # Determine confidence level
    if verification_result.overall_confidence >= 90 and not recommendations["requires_review"]:
        recommendations["approval_ready"] = True
        recommendations["confidence_level"] = "Very High"
    elif verification_result.overall_confidence >= 80:
        recommendations["confidence_level"] = "High"
    elif verification_result.overall_confidence >= 70:
        recommendations["confidence_level"] = "Medium"
    else:
        recommendations["confidence_level"] = "Low"
    
    return recommendations

@app.post("/validate-json")
async def validate_json(invoices: List[InvoiceSchema]):
    """
    Validate a list of invoice JSON objects.
    Returns summary + per-invoice validation results.
    """
    try:
        validation_results = []
        error_counts = {}
        
        for invoice in invoices:
            result = validator.validate(invoice)
            result_dict = result.model_dump()
            validation_results.append(result_dict)
            
            # Count errors for summary
            for error in result.errors:
                error_counts[error] = error_counts.get(error, 0) + 1
        
        # Calculate summary
        total_invoices = len(validation_results)
        valid_invoices = sum(1 for r in validation_results if r.get("is_valid", False))
        invalid_invoices = total_invoices - valid_invoices
        
        summary = {
            "total_invoices": total_invoices,
            "valid_invoices": valid_invoices,
            "invalid_invoices": invalid_invoices,
            "error_counts": error_counts
        }
        
        return {
            "summary": summary,
            "results": validation_results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error validating invoices: {str(e)}")

@app.get("/api/invoices")
async def get_invoices(limit: int = 100, offset: int = 0):
    try:
        invoices = db.get_all_invoices(limit=limit, offset=offset)
        total = db.get_invoices_count()
        return {
            "invoices": invoices,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching invoices: {str(e)}")

@app.get("/api/invoices/{invoice_id}")
async def get_invoice(invoice_id: str):
    try:
        invoice = db.get_invoice(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return invoice
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching invoice: {str(e)}")

@app.delete("/api/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str):
    try:
        deleted = db.delete_invoice(invoice_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "Invoice deleted successfully"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting invoice: {str(e)}")

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    try:
        stats = db.get_dashboard_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard stats: {str(e)}")

@app.get("/api/invoices/{invoice_id}/file")
async def get_invoice_file(invoice_id: str):
    """Retrieve the file associated with an invoice"""
    try:
        invoice = db.get_invoice(invoice_id)
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        
        file_id = invoice.get("file_id")
        if not file_id:
            raise HTTPException(status_code=404, detail="No file associated with this invoice")
        
        file_data = db.get_file(file_id)
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine content type
        content_type = file_data.get("content_type", "application/octet-stream")
        filename = file_data.get("filename", "file")
        
        return Response(
            content=file_data["content"],
            media_type=content_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Content-Length": str(file_data.get("length", len(file_data["content"])))
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching file: {str(e)}")

class BatchProcessResponse(BaseModel):
    success: bool
    total_files: int
    successful: int
    failed: int
    results: List[dict]
    errors: List[dict]

async def process_single_file(file: UploadFile) -> dict:
    """Process a single file and return result or error"""
    file_info = {
        "filename": file.filename,
        "success": False,
        "result": None,
        "error": None
    }
    
    temp_file_path = None
    
    try:
        # Validate file - support multiple types
        supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.docx']
        if not file.filename:
            file_info["error"] = "No filename provided"
            return file_info
        
        filename_lower = file.filename.lower()
        is_supported = any(filename_lower.endswith(ext) for ext in supported_extensions)
        
        if not is_supported:
            file_info["error"] = "Only PDF, Image (JPG, PNG, GIF, WEBP, BMP), and DOCX files are supported"
            return file_info
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        if file_size > 35 * 1024 * 1024:
            file_info["error"] = f"File size ({file_size / 1024 / 1024:.2f}MB) exceeds 35MB limit"
            return file_info
        
        if file_size == 0:
            file_info["error"] = "File is empty"
            return file_info
        
        # Determine file type
        file_type = get_file_type(file.filename)
        
        # Extract data (only for PDFs)
        extracted_data = None
        validation_result = None
        
        if file_type == 'pdf':
            # Write to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            # Extract data
            extracted_data = extractor.extract_from_pdf(temp_file_path)
            
            # Validate
            validation_result = validator.validate(extracted_data)
        else:
            # For non-PDF files, create minimal structure
            from models import InvoiceSchema
            extracted_data = InvoiceSchema()
            from validator import ValidationResult as VR
            validation_result = VR(
                invoice_id=None,
                invoice_number=None,
                is_valid=False,
                score=0,
                errors=["File type not supported for extraction"],
                warnings=[],
                extracted_data=extracted_data
            )
        
        # Save file to GridFS
        file_id = None
        try:
            content_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
            file_id = db.save_file(content, file.filename, content_type)
        except Exception as file_error:
            print(f"File save failed for {file.filename}: {str(file_error)}")
        
        # Try to save to database
        invoice_id = None
        try:
            invoice_data_dict = extracted_data.dict() if extracted_data else {}
            invoice_data_dict["file_name"] = file.filename
            invoice_data_dict["file_type"] = file_type
            
            invoice_id = db.save_invoice(
                invoice_data_dict,
                validation_result.dict(),
                file_id=file_id
            )
            validation_result.invoice_id = invoice_id
        except Exception as db_error:
            print(f"Database save failed for {file.filename}: {str(db_error)}")
        
        file_info["success"] = True
        file_info["result"] = {
            "invoice_id": invoice_id,
            "validation_result": validation_result.dict(),
            "filename": file.filename
        }
        
        return file_info
        
    except Exception as e:
        file_info["error"] = f"Error processing file: {str(e)}"
        return file_info
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass

@app.post("/api/upload/batch", response_model=BatchProcessResponse)
async def upload_and_process_batch(files: List[UploadFile] = File(...)):
    """Process multiple files in parallel"""
    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided")
    
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files allowed per batch")
    
    # Validate all files first (basic validation)
    supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.docx']
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail=f"File has no filename")
        filename_lower = file.filename.lower()
        is_supported = any(filename_lower.endswith(ext) for ext in supported_extensions)
        if not is_supported:
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not a supported type")
    
    # Process files in parallel (limit concurrency to avoid overwhelming the system)
    semaphore = asyncio.Semaphore(5)  # Process 5 files concurrently
    
    async def process_with_semaphore(file):
        async with semaphore:
            return await process_single_file(file)
    
    # Process all files
    results = await asyncio.gather(*[process_with_semaphore(file) for file in files])
    
    # Count successes and failures
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    
    # Separate results and errors
    successful_results = [r["result"] for r in results if r["success"]]
    errors = [
        {"filename": r["filename"], "error": r["error"]}
        for r in results if not r["success"]
    ]
    
    return BatchProcessResponse(
        success=True,
        total_files=len(files),
        successful=successful,
        failed=failed,
        results=successful_results,
        errors=errors
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
