#!/usr/bin/env python3
"""
CLI tool for Invoice Extraction & Quality Control Service

Supports:
- extract: Extract invoice data from PDF file or directory
- validate: Validate extracted JSON invoices
- full-run: Extract + Validate end-to-end
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Import extractors
from pdf_extractor import PDFExtractor
from enhanced_pdf_extractor import EnhancedPDFExtractor
from document_ai_extractor import GoogleDocumentAIExtractor
from validator import InvoiceValidator
from models import InvoiceSchema

def get_extractor(method: str = "auto"):
    """
    Select appropriate extractor based on method and availability.
    Returns tuple (extractor_instance, method_name)
    """
    doc_ai = GoogleDocumentAIExtractor()
    gemini = EnhancedPDFExtractor()
    local_pdf = PDFExtractor()

    if method == "auto":
        # Priority 1: Document AI (Premium + Enabled)
        if doc_ai.is_enabled:
            return doc_ai, "google_document_ai"
        
        # Priority 2: Gemini
        if gemini.gemini_available:
            return gemini, "gemini_extraction"
            
        # Priority 3: Local regex
        return local_pdf, "pdf_extractor"

    elif method == "google_document_ai":
        if not doc_ai.is_enabled:
            print("Error: Google Document AI is a premium feature and is currently disabled.")
            sys.exit(1)
        return doc_ai, "google_document_ai"

    elif method == "gemini_extraction":
        return gemini, "gemini_extraction"
    
    elif method == "pdf_extractor":
        return local_pdf, "pdf_extractor"
    
    else:
        print(f"Warning: Unknown method '{method}'. Falling back to auto.")
        return get_extractor("auto")

def process_file(extractor, file_path: Path) -> Optional[Dict]:
    """Process a single file with the given extractor"""
    try:
        if isinstance(extractor, GoogleDocumentAIExtractor):
            result = extractor.extract_from_pdf(str(file_path))
            return result.to_dict() if result else None
            
        # Generalized handling for other extractors
        result = extractor.extract_from_pdf(str(file_path))
        
        # Convert Pydantic models to dict
        if hasattr(result, 'dict'):
             return result.dict()
        elif hasattr(result, 'to_dict'):
             return result.to_dict()
        elif isinstance(result, dict):
             return result
        else:
             print(f"Warning: Unknown return type {type(result)} from extractor")
             return None
             
    except Exception as e:
        print(f"Extraction failed for {file_path.name}: {e}")
        return None

def extract_command(args):
    """Handle extract command"""
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None
    
    if not input_path.exists():
        print(f"Error: Path '{input_path}' not found.")
        sys.exit(1)

    # Initialize extractor
    extractor, method_name = get_extractor(args.method)
    print(f"Using Extraction Method: {method_name}")

    results = []

    if input_path.is_file():
        print(f"Processing single file: {input_path.name}")
        data = process_file(extractor, input_path)
        if data:
            data['source_file'] = input_path.name
            results.append(data)
            # Print to stdout if no output file
            if not output_path:
                print(json.dumps(data, indent=2, default=str))

    elif input_path.is_dir():
        pdf_files = list(input_path.glob("*.pdf"))
        print(f"Found {len(pdf_files)} PDF files in directory.")
        
        for p in pdf_files:
            print(f"Processing {p.name}...")
            data = process_file(extractor, p)
            if data:
                data['source_file'] = p.name
                results.append(data)

    # Save to file if requested
    if output_path and results:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to {output_path}")

def validate_command(args):
    """Handle validate command"""
    input_file = args.input
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)

    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        sys.exit(1)
    
    if not isinstance(data, list):
         data = [data]

    validator = InvoiceValidator()
    valid_count = 0
    results = []
    
    print(f"Validating {len(data)} invoice(s)...")
    print("=" * 60)

    for i, item in enumerate(data, 1):
        try:
            # Clean up metadata if present
            invoice_data = {k:v for k,v in item.items() if k not in ['source_file', 'extraction_metadata']}
            
            invoice = InvoiceSchema(**invoice_data)
            res = validator.validate(invoice)
            
            status = "✓ VALID" if res.is_valid else "✗ INVALID"
            print(f"[{i}] Invoice #{invoice.invoice_number or 'N/A'}: {status} (Score: {res.score})")
            
            if not res.is_valid:
                for err in res.errors:
                    print(f"    - {err}")

            if res.is_valid: valid_count += 1
            if args.report:
                results.append(res.dict())
        except Exception as e:
            print(f"[{i}] Validation error: {e}")

    print("=" * 60)
    print(f"Summary: {valid_count}/{len(data)} valid.")
    
    if args.report:
        with open(args.report, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Report saved to {args.report}")

def main():
    parser = argparse.ArgumentParser(description="Invoice Extraction CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Extract
    extract_parser = subparsers.add_parser("extract", help="Extract data from PDF(s)")
    extract_parser.add_argument("input", help="Input PDF file or directory")
    extract_parser.add_argument("--output", help="Output JSON file (optional)")
    extract_parser.add_argument("--method", choices=["auto", "google_document_ai", "gemini_extraction", "pdf_extractor"], default="auto", help="Extraction method")
    extract_parser.set_defaults(func=extract_command)

    # Validate
    validate_parser = subparsers.add_parser("validate", help="Validate JSON output")
    validate_parser.add_argument("input", help="Input JSON file")
    validate_parser.add_argument("--report", help="Output validation report JSON")
    validate_parser.set_defaults(func=validate_command)
    
    # Legacy Batch Support with --pdf-dir
    batch_parser = subparsers.add_parser("process-batch", help="Legacy batch processing")
    batch_parser.add_argument("--pdf-dir", required=True)
    batch_parser.add_argument("--output", required=True)
    batch_parser.set_defaults(func=lambda args: extract_command(argparse.Namespace(input=args.pdf_dir, output=args.output, method="auto")))

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
