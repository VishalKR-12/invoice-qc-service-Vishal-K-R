# Enhanced Extraction Endpoint Documentation
"""
To use the enhanced extractor, add this code after line 357 in main.py:

@app.post("/api/upload-enhanced", response_model=ProcessResponse)
async def upload_and_process_enhanced(file: UploadFile = File(...)):
    '''
    Upload and process invoice using ENHANCED layout-aware extraction.
    
    Features:
    - Layout-aware field detection
    - Multiple fallback strategies  
    - Fuzzy matching for buyer/vendor names
    - Confidence scoring for each field
    - Priority-based extraction (Google > Layout > Regex)
    - Automatic field computation (tax from total-subtotal)
    '''
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename_lower = file.filename.lower()
    if not filename_lower.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for enhanced extraction")

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
        # Write to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name

        # Use ENHANCED extractor with layout-aware rules
        logger.info(f"Using enhanced extractor for {file.filename}")
        extracted_data = enhanced_extractor.extract_from_pdf(temp_file_path)

        # Clean up temp file immediately after extraction
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            temp_file_path = None

        # Validate extracted data
        validation_result = validator.validate(extracted_data)

        # Save file to GridFS
        try:
            content_type = mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
            file_id = db.save_file(content, file.filename, content_type)
        except Exception as file_error:
            logger.warning(f"File save failed: {str(file_error)}")

        # Save to database
        try:
            invoice_data_dict = extracted_data.model_dump() if extracted_data else {}
            invoice_data_dict["file_name"] = file.filename
            invoice_data_dict["file_type"] = "pdf"
            invoice_data_dict["extraction_method"] = "enhanced"
            
            invoice_id = db.save_invoice(
                invoice_data_dict,
                validation_result.model_dump(),
                file_id=file_id
            )
            validation_result.invoice_id = invoice_id
        except Exception as db_error:
            logger.warning(f"Database save failed: {str(db_error)}")
            invoice_id = None

        return ProcessResponse(
            success=True,
            invoice_id=invoice_id,
            validation_result=validation_result,
            message="Invoice processed successfully with enhanced extraction"
        )

    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {str(e)}")
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except OSError as cleanup_error:
                logger.warning(f"Failed to delete temp file during error cleanup: {cleanup_error}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
"""

# Usage Instructions:
# 1. Copy the code above (without the triple quotes)
# 2. Paste it into main.py after line 357
# 3. The server will auto-reload
# 4. Access the enhanced endpoint at: POST /api/upload-enhanced

# Frontend Integration:
# To use the enhanced extractor from the frontend, change the upload URL in app.js:
# From: `${API_BASE_URL}/api/upload`
# To: `${API_BASE_URL}/api/upload-enhanced`
