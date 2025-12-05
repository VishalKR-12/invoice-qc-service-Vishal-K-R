# Dual-Source Invoice Extraction System

## Overview

The Invoicely project now features an advanced **dual-source extraction system** that intelligently combines extraction from two independent sources:

1. **Local PDF Extraction** (`pdf_extractor.py`) - Using pdfplumber + regex + Gemini AI
2. **Google Vision Extraction** (`extraction_merger.py`) - Using Google Generative AI Vision

The system compares results field-by-field and selects the most reliable value for each field, with full transparency and debugging information.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER UPLOADS PDF                         │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ↓
        ┌────────────────────────┐
        │ /api/extract-dual-source
        │ (NEW ENDPOINT)         │
        └────────────┬───────────┘
                     │
        ┌────────────┴─────────────┐
        │                          │
        ↓                          ↓
    ┌─────────────┐         ┌──────────────┐
    │   PDF.PY    │         │ GOOGLE VISION│
    │ (pdfplumber │         │  (Gemini AI) │
    │  + Gemini)  │         │              │
    └──────┬──────┘         └───────┬──────┘
           │                        │
           └────────┬───────────────┘
                    ↓
        ┌──────────────────────────┐
        │  ExtractionMerger        │
        │  .extract_and_merge()    │
        │                          │
        │ 1. Compare fields        │
        │ 2. Score reliability     │
        │ 3. Select best value     │
        │ 4. Flag mismatches       │
        └────────────┬─────────────┘
                     │
                     ↓
        ┌──────────────────────────┐
        │    MergedExtractionResult │
        │                          │
        │ - pdf_data               │
        │ - google_data            │
        │ - final_output           │
        │ - field_comparisons      │
        │ - mismatches             │
        │ - quality_score          │
        │ - recommendation         │
        └────────────┬─────────────┘
                     │
                     ↓
                 RESPONSE
```

---

## New Files

### 1. `backend/extraction_merger.py` (new)
**Purpose**: Orchestrate dual-source extraction and intelligent merging

**Key Classes:**
- `ExtractionMerger` - Main orchestrator
- `ExtractionSource` - Metadata about each source
- `FieldComparison` - Detailed comparison for each field
- `ExtractionMergeResult` - Complete merge result with debugging info

**Key Methods:**
```python
extract_and_merge(pdf_path: str) -> ExtractionMergeResult
  ├─ _extract_with_google_vision() - Google extraction
  ├─ _compare_and_merge() - Field comparison
  └─ _calculate_quality_metrics() - Quality scoring

_select_best_value() - Intelligent value selection
  ├─ _compare_numeric() - For numeric fields
  ├─ _compare_text() - For text fields
  └─ _compare_line_items() - For line items list

_calculate_similarity() - String similarity matching (0-1)
```

---

## API Endpoint

### New Endpoint: `POST /api/extract-dual-source`

**Purpose**: Extract and merge invoice data from dual sources

**Request:**
```bash
POST /api/extract-dual-source
Content-Type: multipart/form-data

Body: {
  "file": <PDF file>
}
```

**Response:**
```json
{
  "success": true,
  "merged_extraction": {
    "pdf_data": {
      "invoice_number": "INV-001",
      "vendor_name": "ABC Corp",
      "total_amount": 1500.00,
      ...
    },
    "google_data": {
      "invoice_number": "INV-001",
      "vendor_name": "ABC Corporation",
      "total_amount": 1500.50,
      ...
    },
    "final_output": {
      "invoice_number": "INV-001",
      "vendor_name": "ABC Corporation",
      "total_amount": 1500.50,
      ...
    },
    "field_comparisons": [
      {
        "field_name": "vendor_name",
        "pdf_value": "ABC Corp",
        "google_value": "ABC Corporation",
        "selected_value": "ABC Corporation",
        "selection_reason": "Different values (similarity=80.5%), using Google",
        "confidence_score": 90.0,
        "is_mismatch": true,
        "recommendation": "Values differ significantly, review recommended"
      },
      ...
    ],
    "notes": [
      "Google extraction successful",
      "Quality Score: 87.5% (Completeness=100%, Mismatches=1)"
    ],
    "mismatches": [
      "vendor_name: PDF=ABC Corp, Google=ABC Corporation, Selected=ABC Corporation (Different values (similarity=80.5%), using Google)"
    ],
    "merge_timestamp": "2024-12-06T14:30:00.000000",
    "quality_score": 87.5,
    "recommendation": "review"
  },
  "message": "Dual-source extraction completed successfully"
}
```

---

## Response Format

### `final_output` (Best Merged Values)
```json
{
  "invoice_number": "string",
  "vendor_name": "string",
  "vendor_address": "string",
  "buyer_name": "string",
  "buyer_address": "string",
  "invoice_date": "YYYY-MM-DD",
  "due_date": "YYYY-MM-DD",
  "currency": "string",
  "subtotal": number,
  "tax_amount": number,
  "total_amount": number,
  "payment_terms": "string",
  "line_items": [
    {
      "description": "string",
      "quantity": number,
      "price": number,
      "total": number
    }
  ]
}
```

### `field_comparisons` (Detailed Comparison)
```json
{
  "field_name": "vendor_name",
  "pdf_value": "ABC Corp",
  "google_value": "ABC Corporation",
  "selected_value": "ABC Corporation",
  "selection_reason": "String match reason",
  "confidence_score": 90.0,
  "is_mismatch": true,
  "recommendation": "Manual review recommended"
}
```

### `mismatches` (Human-Readable)
```json
[
  "vendor_name: PDF=ABC Corp, Google=ABC Corporation, Selected=ABC Corporation (Reason)"
]
```

### Quality Metrics
```json
{
  "quality_score": 87.5,        // 0-100%
  "recommendation": "review",    // "approve", "review", or "reject"
  "notes": [
    "Google extraction successful",
    "Quality Score: 87.5% (Completeness=100%, Mismatches=1)"
  ]
}
```

---

## Intelligent Value Selection Logic

### Priority Rules

**For EACH field:**

1. **Both values missing** → None (confidence: 0%)

2. **Only one source available** → Use that value
   - PDF only → Use PDF (confidence: 85%)
   - Google only → Use Google (confidence: 95%)

3. **Both available - Numeric fields:**
   - Calculate difference percentage
   - If diff > 5% → Flag as mismatch
   - Always prefer Google (more reliable for OCR/Vision)
   - Confidence: 90%

4. **Both available - Text fields:**
   - Calculate similarity (0-1 scale)
   - If similarity > 85% → Considered "match"
     - Either is fine, prefer Google
     - Confidence: 90%
   - If similarity ≤ 85% → Different values
     - Use Google (more reliable)
     - Flag as mismatch
     - Confidence: 80-90%

5. **Line Items:**
   - If Google has more items → Use Google (more complete)
   - If same count → Use Google
   - If PDF has more → Use Google anyway (unlikely)
   - Flag count mismatch if different

### Field Reliability Weights

```python
field_weights = {
    "invoice_number": {"pdf": 0.85, "google": 0.95},
    "vendor_name": {"pdf": 0.80, "google": 0.90},
    "vendor_address": {"pdf": 0.75, "google": 0.85},
    "buyer_name": {"pdf": 0.80, "google": 0.90},
    "buyer_address": {"pdf": 0.75, "google": 0.85},
    "invoice_date": {"pdf": 0.85, "google": 0.95},
    "due_date": {"pdf": 0.80, "google": 0.90},
    "currency": {"pdf": 0.90, "google": 0.95},
    "subtotal": {"pdf": 0.85, "google": 0.90},
    "tax_amount": {"pdf": 0.85, "google": 0.90},
    "total_amount": {"pdf": 0.90, "google": 0.95},
    "payment_terms": {"pdf": 0.70, "google": 0.80},
    "line_items": {"pdf": 0.75, "google": 0.85},
}
```

Higher values = Higher reliability if source provides that field.

---

## Quality Scoring

**Calculation:**
```
completeness_score = (required_fields_present / total_required) × 100
mismatch_penalty = number_of_mismatches × 5
quality_score = completeness_score - mismatch_penalty

(Capped at 0-100%)
```

**Required Fields:**
- invoice_number
- vendor_name
- total_amount
- invoice_date

**Thresholds:**
```
quality_score >= 85% → recommendation: "approve"
quality_score >= 60% → recommendation: "review"
quality_score < 60%  → recommendation: "reject"
```

---

## Duplicate Upload Prevention (Frontend)

### Problem Solved
Prevents accidental duplicate uploads due to:
- Double-clicking upload button
- Repeated onChange events on file input
- Network latency causing user to retry

### Implementation

**Global State Flags:**
```javascript
let isUploading = false;              // Currently uploading
let lastUploadedFileName = null;      // Last file name
let lastUploadTimestamp = 0;          // Last upload time
const UPLOAD_COOLDOWN_MS = 1000;      // 1 second minimum between uploads
```

**Check Before Upload:**
```javascript
function canProceedWithUpload(fileName) {
    if (isUploading) return false;    // Already uploading
    if (fileName === lastUploadedFileName && 
        Date.now() - lastUploadTimestamp < UPLOAD_COOLDOWN_MS) {
        return false;  // Same file too soon
    }
    return true;
}
```

**Lifecycle:**

1. **User initiates upload**
   ```javascript
   if (!canProceedWithUpload(fileName)) {
       alert('File is already being uploaded. Please wait.');
       return;
   }
   ```

2. **Mark upload started**
   ```javascript
   markUploadStarted(fileName);
   // isUploading = true
   ```

3. **Processing...**
   - Display loading indicator
   - Disable upload button (implied by isUploading flag)
   - Send to backend

4. **On completion (success or error)**
   ```javascript
   markUploadFinished();
   // isUploading = false
   // lastUploadTimestamp = Date.now()
   ```

5. **Clear form state**
   ```javascript
   fileInput.value = '';  // Clear file input
   ```

**Additional Safeguards:**
```javascript
// Prevent rapid re-selection
fileInput.addEventListener('change', (e) => {
    // ... handle upload
    e.target.value = '';  // Clear so same file can be selected again
});

// Handle batch uploads similarly
```

---

## Usage Examples

### Example 1: Basic Dual-Source Extraction

**JavaScript Frontend:**
```javascript
const formData = new FormData();
formData.append('file', invoiceFile);

const response = await fetch('/api/extract-dual-source', {
    method: 'POST',
    body: formData
});

const result = await response.json();

// Access merged data
console.log(result.merged_extraction.final_output);

// Check for mismatches
if (result.merged_extraction.mismatches.length > 0) {
    console.warn('Mismatches found:', result.merged_extraction.mismatches);
}

// Review recommendation
if (result.merged_extraction.recommendation === 'review') {
    // Flag for manual review
}
```

### Example 2: Processing Response

```javascript
const { merged_extraction } = result;

// 1. Get best merged values
const bestData = merged_extraction.final_output;
console.log(`Invoice: ${bestData.invoice_number}`);
console.log(`Vendor: ${bestData.vendor_name}`);
console.log(`Amount: ${bestData.total_amount}`);

// 2. Review field-by-field comparisons
merged_extraction.field_comparisons.forEach(comparison => {
    if (comparison.is_mismatch) {
        console.log(`⚠️ ${comparison.field_name}:`);
        console.log(`   PDF: ${comparison.pdf_value}`);
        console.log(`   Google: ${comparison.google_value}`);
        console.log(`   Selected: ${comparison.selected_value}`);
        console.log(`   Confidence: ${comparison.confidence_score}%`);
    }
});

// 3. Check quality score
console.log(`Quality: ${merged_extraction.quality_score.toFixed(1)}%`);
console.log(`Recommendation: ${merged_extraction.recommendation}`);

// 4. Display notes
merged_extraction.notes.forEach(note => console.log(`ℹ️ ${note}`));
```

### Example 3: Handling Different Scenarios

**Scenario A: Perfect Match (No Mismatches)**
```json
{
  "quality_score": 95.0,
  "recommendation": "approve",
  "mismatches": [],
  "notes": ["Quality Score: 95.0% (Completeness=100%, Mismatches=0)"]
}
```
→ Auto-approve, no review needed

**Scenario B: Minor Mismatches**
```json
{
  "quality_score": 82.5,
  "recommendation": "review",
  "mismatches": [
    "vendor_name: PDF=ABC Corp, Google=ABC Corporation..."
  ],
  "notes": ["Quality Score: 82.5% (Completeness=100%, Mismatches=1)"]
}
```
→ Human review recommended, likely just formatting differences

**Scenario C: Major Issues**
```json
{
  "quality_score": 45.0,
  "recommendation": "reject",
  "mismatches": [
    "total_amount: PDF=1500, Google=2500...",
    "invoice_date: PDF=2024-01-15, Google=2024-12-15..."
  ],
  "notes": ["Quality Score: 45.0% (Completeness=75%, Mismatches=3)"]
}
```
→ Reject, requires manual re-extraction or correction

---

## Debugging & Transparency

### View PDF Extraction Only
```javascript
result.merged_extraction.pdf_data
// {
//   "invoice_number": "INV-001",
//   "vendor_name": "ABC Corp",
//   ...
// }
```

### View Google Extraction Only
```javascript
result.merged_extraction.google_data
// {
//   "invoice_number": "INV-001",
//   "vendor_name": "ABC Corporation",
//   ...
// }
```

### View Field-by-Field Comparison
```javascript
result.merged_extraction.field_comparisons
// [
//   {
//     "field_name": "vendor_name",
//     "pdf_value": "ABC Corp",
//     "google_value": "ABC Corporation",
//     "selected_value": "ABC Corporation",
//     "selection_reason": "Different values (similarity=80.5%), using Google",
//     "confidence_score": 90,
//     "is_mismatch": true
//   }
// ]
```

### Export Full Result
```javascript
const fullDebugInfo = JSON.stringify(
    result.merged_extraction,
    null,
    2
);
console.log(fullDebugInfo);

// Or save to file
const blob = new Blob([fullDebugInfo], { type: 'application/json' });
const url = URL.createObjectURL(blob);
const a = document.createElement('a');
a.href = url;
a.download = 'extraction_debug.json';
a.click();
```

---

## Integration with Existing System

### Existing Endpoint: `/api/upload`
```
Still works as before
Uses only pdf_extractor.py
Returns: ValidationResult
```

### New Endpoint: `/api/extract-dual-source`
```
New advanced extraction
Uses both pdf_extractor.py + Google Vision
Returns: MergedExtractionResponse with full debugging
```

### Can Use Either:
- Use `/api/upload` for quick standard extraction
- Use `/api/extract-dual-source` for advanced dual-source with transparency

---

## Error Handling

### Common Errors

**PDF Extraction Failed:**
```json
{
  "notes": ["PDF extraction error: could not read file"]
}
```

**Google Extraction Unavailable:**
```json
{
  "notes": ["Google extraction unavailable: API error"],
  "google_data": {}
}
```

**Invalid PDF:**
```json
{
  "success": false,
  "error": "Error in dual-source extraction: PDF corrupted"
}
```

---

## Performance

| Operation | Typical Time |
|-----------|--------------|
| PDF extraction | 2-5 sec |
| Google extraction | 5-10 sec |
| Comparison & merge | <1 sec |
| **Total** | **8-15 sec** |

---

## Testing

### Test with Sample PDF
```bash
curl -X POST http://localhost:8000/api/extract-dual-source \
  -F "file=@sample_invoice.pdf"
```

### Verify Dual Extraction
```json
// Should see both pdf_data and google_data populated
{
  "merged_extraction": {
    "pdf_data": {...},
    "google_data": {...},
    "final_output": {...}
  }
}
```

### Check Mismatch Detection
```bash
# Use invoice with variations (e.g., "ABC Corp" vs "ABC Corporation")
# Should see:
curl -X POST http://localhost:8000/api/extract-dual-source \
  -F "file=@variance_invoice.pdf" \
  | jq '.merged_extraction.mismatches'

# Output:
[
  "vendor_name: PDF=ABC Corp, Google=ABC Corporation..."
]
```

---

## Future Enhancements

1. **Machine Learning**: Learn from corrected mismatches to improve selection logic
2. **Confidence Weighting**: Adjust field weights based on historical accuracy
3. **Multiple Source Average**: Combine >2 sources for better accuracy
4. **Custom Selection Rules**: Allow users to set preferred sources per field
5. **Batch Dual Extraction**: Process multiple files with dual extraction
6. **Historical Comparison**: Compare against previous invoices from same vendor

---

## Summary

**Key Features:**
✅ Dual-source extraction (PDF + Google Vision)
✅ Intelligent field-by-field comparison
✅ Automatic best-value selection
✅ Full transparency with debugging info
✅ Quality scoring (0-100%)
✅ Mismatch detection and flagging
✅ Duplicate upload prevention
✅ Confidence scoring per field
✅ Source tracking
✅ Human-readable output

**Result:** More accurate invoices with complete visibility into extraction sources and reasoning.

