#!/usr/bin/env python3
"""
CLI tool for Invoice Extraction & Quality Control Service

Supports:
- extract: Extract invoice data from PDF directory
- validate: Validate extracted JSON invoices
- full-run: Extract + Validate end-to-end
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from pdf_extractor import PDFExtractor
from validator import InvoiceValidator
from models import InvoiceSchema, ValidationResult


def extract_from_directory(pdf_dir: str, output_file: str) -> None:
    """Extract invoice data from all PDFs in a directory"""
    pdf_dir_path = Path(pdf_dir)
    if not pdf_dir_path.exists():
        print(f"Error: Directory '{pdf_dir}' does not exist")
        sys.exit(1)
    
    if not pdf_dir_path.is_dir():
        print(f"Error: '{pdf_dir}' is not a directory")
        sys.exit(1)
    
    # Find all PDF files
    pdf_files = list(pdf_dir_path.glob("*.pdf"))
    if not pdf_files:
        print(f"Warning: No PDF files found in '{pdf_dir}'")
        sys.exit(1)
    
    print(f"Found {len(pdf_files)} PDF file(s)")
    print("=" * 60)
    
    extractor = PDFExtractor()
    extracted_invoices = []
    
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
        try:
            invoice_data = extractor.extract_from_pdf(str(pdf_file))
            # Convert to dict for JSON serialization
            invoice_dict = invoice_data.dict()
            # Add source file info
            invoice_dict["source_file"] = pdf_file.name
            extracted_invoices.append(invoice_dict)
            print(f"  ✓ Extracted: Invoice #{invoice_data.invoice_number or 'N/A'}")
        except Exception as e:
            print(f"  ✗ Error extracting from {pdf_file.name}: {str(e)}")
            continue
    
    # Write output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(extracted_invoices, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print(f"✓ Extraction complete!")
    print(f"  Total processed: {len(extracted_invoices)}/{len(pdf_files)}")
    print(f"  Output saved to: {output_path.absolute()}")


def validate_json(input_file: str, report_file: str = None) -> None:
    """Validate invoices from JSON file"""
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"Error: File '{input_file}' does not exist")
        sys.exit(1)
    
    # Read JSON file
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            invoices_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in '{input_file}': {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)
    
    if not isinstance(invoices_data, list):
        print("Error: JSON file must contain an array of invoices")
        sys.exit(1)
    
    print(f"Validating {len(invoices_data)} invoice(s)...")
    print("=" * 60)
    
    validator = InvoiceValidator()
    validation_results = []
    error_counts = {}
    
    for i, invoice_data in enumerate(invoices_data, 1):
        try:
            # Create InvoiceSchema from dict
            invoice = InvoiceSchema(**invoice_data)
            # Validate
            result = validator.validate(invoice)
            
            # Convert to dict for JSON serialization
            result_dict = result.dict()
            validation_results.append(result_dict)
            
            # Count errors
            for error in result.errors:
                error_counts[error] = error_counts.get(error, 0) + 1
            
            status = "✓ VALID" if result.is_valid else "✗ INVALID"
            print(f"[{i}/{len(invoices_data)}] {status} - Invoice #{result.invoice_number or 'N/A'} (Score: {result.score})")
            
            if result.errors:
                for error in result.errors:
                    print(f"    Error: {error}")
            if result.warnings:
                for warning in result.warnings:
                    print(f"    Warning: {warning}")
        
        except Exception as e:
            print(f"[{i}/{len(invoices_data)}] ✗ Error processing invoice: {str(e)}")
            continue
    
    # Calculate summary
    total_invoices = len(validation_results)
    valid_invoices = sum(1 for r in validation_results if r.get("is_valid", False))
    invalid_invoices = total_invoices - valid_invoices
    
    # Print summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total invoices: {total_invoices}")
    print(f"Valid: {valid_invoices} ({valid_invoices/total_invoices*100:.1f}%)" if total_invoices > 0 else "Valid: 0")
    print(f"Invalid: {invalid_invoices} ({invalid_invoices/total_invoices*100:.1f}%)" if total_invoices > 0 else "Invalid: 0")
    
    if error_counts:
        print("\nTop Error Types:")
        sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)
        for error, count in sorted_errors[:5]:
            print(f"  - {error}: {count} occurrence(s)")
    
    # Create summary object
    summary = {
        "total_invoices": total_invoices,
        "valid_invoices": valid_invoices,
        "invalid_invoices": invalid_invoices,
        "error_counts": error_counts
    }
    
    # Write report if specified
    if report_file:
        report_path = Path(report_file)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        report_data = {
            "summary": summary,
            "results": validation_results
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Report saved to: {report_path.absolute()}")
    
    # Exit with non-zero code if there are invalid invoices
    if invalid_invoices > 0:
        print(f"\n⚠ {invalid_invoices} invalid invoice(s) found")
        sys.exit(1)
    else:
        print("\n✓ All invoices are valid!")
        sys.exit(0)


def full_run(pdf_dir: str, report_file: str) -> None:
    """Extract from PDFs and validate in one step"""
    import tempfile
    
    print("=" * 60)
    print("FULL RUN: Extract + Validate")
    print("=" * 60)
    
    # Create temporary file for extracted data
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        tmp_extracted_file = tmp_file.name
    
    try:
        # Step 1: Extract
        print("\n[STEP 1/2] Extracting invoice data from PDFs...")
        extract_from_directory(pdf_dir, tmp_extracted_file)
        
        # Step 2: Validate
        print("\n[STEP 2/2] Validating extracted invoices...")
        validate_json(tmp_extracted_file, report_file)
    
    finally:
        # Clean up temporary file
        if os.path.exists(tmp_extracted_file):
            os.unlink(tmp_extracted_file)


def main():
    parser = argparse.ArgumentParser(
        description="Invoice Extraction & Quality Control CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Extract invoice data from PDFs
  python cli.py extract --pdf-dir ./invoices --output extracted.json
  
  # Validate extracted JSON
  python cli.py validate --input extracted.json --report validation_report.json
  
  # Extract and validate in one step
  python cli.py full-run --pdf-dir ./invoices --report final_report.json
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Extract command
    extract_parser = subparsers.add_parser('extract', help='Extract invoice data from PDF directory')
    extract_parser.add_argument('--pdf-dir', required=True, help='Directory containing PDF files')
    extract_parser.add_argument('--output', required=True, help='Output JSON file path')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate extracted JSON invoices')
    validate_parser.add_argument('--input', required=True, help='Input JSON file with invoices')
    validate_parser.add_argument('--report', help='Output validation report JSON file (optional)')
    
    # Full-run command
    fullrun_parser = subparsers.add_parser('full-run', help='Extract and validate end-to-end')
    fullrun_parser.add_argument('--pdf-dir', required=True, help='Directory containing PDF files')
    fullrun_parser.add_argument('--report', required=True, help='Output validation report JSON file')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'extract':
            extract_from_directory(args.pdf_dir, args.output)
        elif args.command == 'validate':
            validate_json(args.input, args.report)
        elif args.command == 'full-run':
            full_run(args.pdf_dir, args.report)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

