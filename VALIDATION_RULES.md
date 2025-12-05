# Validation Rules Documentation

This document provides detailed information about the validation rules implemented in Invoicely.

## Overview

The validation system uses a scoring mechanism starting at 100 points. Each violation deducts points based on severity. An invoice is considered:

- ✅ **Valid**: Score ≥ 80
- ⚠️ **Warning**: Score 60-79
- ❌ **Invalid**: Score < 60

## Rule Categories

### 1. Completeness Checks (Required Fields)

These rules ensure critical fields are present.

#### 1.1 Invoice Number Required
- **Field**: `invoice_number`
- **Check**: Field must exist and not be empty
- **Score Impact**: -15 points
- **Error Message**: "Missing required field: Invoice Number"
- **Rationale**: Invoice number is the primary identifier for tracking and referencing invoices in accounting systems.

#### 1.2 Vendor Name Required
- **Field**: `vendor_name`
- **Check**: Field must exist and not be empty
- **Score Impact**: -15 points
- **Error Message**: "Missing required field: Vendor Name"
- **Rationale**: Essential for identifying who is billing, required for payment processing and vendor management.

#### 1.3 Total Amount Required
- **Field**: `total_amount`
- **Check**: Field must exist and not be null
- **Score Impact**: -15 points
- **Error Message**: "Missing required field: Total Amount"
- **Rationale**: The total amount is critical for payment processing and financial records.

#### 1.4 Invoice Date Required
- **Field**: `invoice_date`
- **Check**: Field must exist and not be empty
- **Score Impact**: -15 points
- **Error Message**: "Missing required field: Invoice Date"
- **Rationale**: Required for proper accounting period assignment and aging reports.

#### 1.5 Important Fields (Warnings)

These fields are important but not critical:

**Buyer Name**
- Score Impact: -5 points
- Error Type: Warning
- Message: "Missing important field: Buyer Name"

**Currency**
- Score Impact: -5 points
- Error Type: Warning
- Message: "Missing important field: Currency"

**Due Date**
- Score Impact: -5 points
- Error Type: Warning
- Message: "Missing important field: Due Date"

### 2. Format & Type Validation

These rules ensure data is in the correct format and type.

#### 2.1 Invoice Number Length
- **Check**: Length must be at least 3 characters
- **Score Impact**: -10 points
- **Error Message**: "Invoice number is too short (minimum 3 characters)"
- **Rationale**: Very short invoice numbers are likely extraction errors or invalid identifiers.

#### 2.2 Invoice Date Format
- **Check**: Must be parseable as a valid date
- **Score Impact**: -10 points
- **Error Message**: "Invalid invoice date format: {date}"
- **Supported Formats**:
  - YYYY-MM-DD
  - MM/DD/YYYY
  - DD-MM-YYYY
  - DD Month YYYY
- **Rationale**: Invalid date formats cause issues in downstream systems.

#### 2.3 Due Date Format
- **Check**: Must be parseable as a valid date
- **Score Impact**: -10 points
- **Error Message**: "Invalid due date format: {date}"
- **Rationale**: Required for payment scheduling and aging calculations.

#### 2.4 Amount Type Validation
- **Check**: Must be numeric and non-negative
- **Score Impact**: -15 points (negative) or -5 points (zero)
- **Error Messages**:
  - "Total amount cannot be negative"
  - "Total amount is zero" (warning)
- **Rationale**: Negative amounts indicate data errors; zero amounts are unusual but possible.

#### 2.5 Currency Code Validation
- **Check**: Must be a valid ISO currency code
- **Score Impact**: -3 points
- **Error Type**: Warning
- **Valid Codes**: USD, EUR, GBP, INR, CAD, AUD, JPY
- **Error Message**: "Uncommon currency code: {code}"
- **Rationale**: Unusual currency codes may indicate extraction errors.

### 3. Business Logic Validation

These rules enforce business rules and mathematical consistency.

#### 3.1 Due Date After Invoice Date
- **Check**: Due date must not be before invoice date
- **Score Impact**: -15 points
- **Error Message**: "Due date cannot be before invoice date"
- **Rationale**: Logically impossible and indicates data error or extraction issue.

#### 3.2 Payment Term Reasonability
- **Check**: Due date should not be more than 365 days after invoice date
- **Score Impact**: -5 points
- **Error Type**: Warning
- **Error Message**: "Unusually long payment term: {days} days"
- **Rationale**: Very long payment terms are unusual in business and may indicate extraction errors.

#### 3.3 Amount Calculation Validation
- **Check**: Subtotal + Tax = Total (within $0.01 tolerance)
- **Score Impact**: -20 points
- **Error Message**: "Amount mismatch: Subtotal ({subtotal}) + Tax ({tax}) does not equal Total ({total})"
- **Rationale**: Mathematical inconsistency indicates serious data quality issues.
- **Tolerance**: 1 cent to account for rounding

#### 3.4 Line Items Total Match
- **Check**: Sum of line item totals should match subtotal
- **Score Impact**: -5 points
- **Error Type**: Warning
- **Error Message**: "Line items total ({line_total}) does not match subtotal ({subtotal})"
- **Rationale**: Discrepancy may indicate missing line items or extraction errors.
- **Tolerance**: $0.01

### 4. Anomaly Detection

These rules identify unusual patterns that may require review.

#### 4.1 High Amount Detection

**Warning Level**
- **Check**: Total amount > $1,000,000
- **Score Impact**: -3 points
- **Error Type**: Warning
- **Error Message**: "Unusually high amount: {amount}"

**Error Level**
- **Check**: Total amount > $10,000,000
- **Score Impact**: -10 points
- **Error Type**: Error
- **Error Message**: "Suspiciously high amount: {amount}"

**Rationale**: Very high amounts may indicate:
- Extraction errors (decimal point misplacement)
- Fraudulent invoices
- Special cases requiring review

#### 4.2 Duplicate Vendor-Buyer Check
- **Check**: Vendor and buyer names are identical
- **Score Impact**: -5 points
- **Error Type**: Warning
- **Error Message**: "Vendor and buyer names are identical"
- **Rationale**: Same vendor and buyer is unusual and may indicate:
  - Extraction error
  - Internal transfer document
  - Data quality issue

#### 4.3 Invoice Date Reasonability

**Future Dated**
- **Check**: Invoice date > 30 days in the future
- **Score Impact**: -5 points
- **Error Type**: Warning
- **Error Message**: "Invoice date is {days} days in the future"

**Old Invoice**
- **Check**: Invoice date > 2 years old
- **Score Impact**: -3 points
- **Error Type**: Warning
- **Error Message**: "Invoice is {days} days old"

**Rationale**:
- Future dated invoices are unusual and may indicate extraction errors
- Very old invoices may be duplicates or archived documents being reprocessed

## Validation Score Interpretation

### 100 Points (Perfect)
- All required fields present
- All formats valid
- All business logic checks pass
- No anomalies detected

### 90-99 Points (Excellent)
- May have minor warnings
- Missing non-critical fields
- All core data is valid

### 80-89 Points (Good - Valid)
- Some warnings present
- May be missing optional fields
- Core data is reliable

### 60-79 Points (Acceptable - Review Recommended)
- Multiple warnings
- Some format issues
- Manual review suggested

### Below 60 Points (Invalid)
- Critical errors present
- Missing required fields
- Business logic violations
- Should not be processed without correction

## Validation Workflow

```
PDF Upload
    ↓
Text Extraction
    ↓
Field Parsing
    ↓
Completeness Check (4 required fields)
    ↓
Format Validation (dates, amounts, currency)
    ↓
Business Logic Validation (calculations, dates)
    ↓
Anomaly Detection (unusual patterns)
    ↓
Score Calculation
    ↓
Result (Valid/Invalid + Errors/Warnings)
```

## Error vs Warning

### Errors (Block Processing)
- Missing required fields
- Invalid data formats
- Business logic violations
- Mathematical inconsistencies
- Extremely high amounts

### Warnings (Allow Processing with Review)
- Missing optional fields
- Unusual but valid data
- Uncommon patterns
- High (but not extreme) amounts
- Old or future-dated invoices

## Examples

### Example 1: Perfect Score (100)

```json
{
  "invoice_number": "INV-2024-001",
  "vendor_name": "Acme Corporation",
  "buyer_name": "Smith Enterprises",
  "invoice_date": "2024-01-15",
  "due_date": "2024-02-15",
  "currency": "USD",
  "subtotal": 1000.00,
  "tax_amount": 80.00,
  "total_amount": 1080.00
}
```

**Result**: 100 points, Valid, No errors, No warnings

### Example 2: Missing Optional Field (95)

```json
{
  "invoice_number": "INV-2024-002",
  "vendor_name": "Tech Solutions Ltd",
  "buyer_name": "Johnson Corp",
  "invoice_date": "2024-01-20",
  "due_date": null,
  "currency": "USD",
  "total_amount": 5000.00
}
```

**Result**: 95 points, Valid, No errors, 1 warning (missing due date)

### Example 3: Invalid Amount (70)

```json
{
  "invoice_number": "INV-2024-003",
  "vendor_name": "Global Services",
  "buyer_name": "Enterprise Inc",
  "invoice_date": "2024-01-25",
  "currency": "USD",
  "subtotal": 2000.00,
  "tax_amount": 160.00,
  "total_amount": 2500.00
}
```

**Result**: 80 points, Valid, 1 error (amount mismatch: 2000 + 160 ≠ 2500)

### Example 4: Missing Critical Fields (55)

```json
{
  "invoice_number": null,
  "vendor_name": "Services Co",
  "invoice_date": null,
  "total_amount": 1000.00
}
```

**Result**: 55 points, Invalid, 3 errors (missing invoice number, date, buyer name)

## Customizing Validation Rules

To modify validation rules, edit `backend/validator.py`:

1. **Adjust Score Penalties**: Change `self.score -= X` values
2. **Add New Rules**: Add methods to `InvoiceValidator` class
3. **Modify Thresholds**: Change conditions in validation checks
4. **Add Custom Messages**: Update error/warning message strings

Example - Adding a new rule:

```python
def _validate_vendor_tax_id(self, invoice: InvoiceSchema):
    if invoice.vendor_tax_id:
        if not re.match(r'^\d{2}-\d{7}$', invoice.vendor_tax_id):
            self.errors.append("Invalid tax ID format")
            self.score -= 10
```

## Best Practices

1. **Balance Strictness**: Too strict = many false positives; Too lenient = poor data quality
2. **Meaningful Messages**: Error messages should guide users to fix issues
3. **Appropriate Penalties**: Critical errors should have higher penalties
4. **Consider Context**: Some rules may vary by industry or region
5. **Regular Review**: Update rules based on real-world usage patterns

---

**Last Updated**: December 2024
