import re
from typing import List, Tuple
from datetime import datetime
from dateutil import parser
from models import InvoiceSchema, ValidationResult

class InvoiceValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.score = 100

    def validate(self, invoice: InvoiceSchema) -> ValidationResult:
        self.errors = []
        self.warnings = []
        self.score = 100

        self._validate_completeness(invoice)
        self._validate_formats(invoice)
        self._validate_business_logic(invoice)
        self._validate_anomalies(invoice)

        is_valid = len(self.errors) == 0

        return ValidationResult(
            invoice_number=invoice.invoice_number,
            is_valid=is_valid,
            score=max(0, self.score),
            errors=self.errors,
            warnings=self.warnings,
            extracted_data=invoice
        )

    def _validate_completeness(self, invoice: InvoiceSchema):
        required_fields = {
            'invoice_number': 'Invoice Number',
            'vendor_name': 'Vendor Name',
            'total_amount': 'Total Amount',
            'invoice_date': 'Invoice Date'
        }

        for field, label in required_fields.items():
            value = getattr(invoice, field, None)
            if not value:
                self.errors.append(f"Missing required field: {label}")
                self.score -= 15

        important_fields = {
            'buyer_name': 'Buyer Name',
            'currency': 'Currency',
            'due_date': 'Due Date'
        }

        for field, label in important_fields.items():
            value = getattr(invoice, field, None)
            if not value:
                self.warnings.append(f"Missing important field: {label}")
                self.score -= 5

    def _validate_formats(self, invoice: InvoiceSchema):
        if invoice.invoice_number:
            if len(invoice.invoice_number) < 3:
                self.errors.append("Invoice number is too short (minimum 3 characters)")
                self.score -= 10

        if invoice.invoice_date:
            if not self._is_valid_date(invoice.invoice_date):
                self.errors.append(f"Invalid invoice date format: {invoice.invoice_date}")
                self.score -= 10

        if invoice.due_date:
            if not self._is_valid_date(invoice.due_date):
                self.errors.append(f"Invalid due date format: {invoice.due_date}")
                self.score -= 10

        if invoice.total_amount is not None:
            if invoice.total_amount < 0:
                self.errors.append("Total amount cannot be negative")
                self.score -= 15
            if invoice.total_amount == 0:
                self.warnings.append("Total amount is zero")
                self.score -= 5

        if invoice.currency:
            valid_currencies = ['USD', 'EUR', 'GBP', 'INR', 'CAD', 'AUD', 'JPY']
            if invoice.currency not in valid_currencies:
                self.warnings.append(f"Uncommon currency code: {invoice.currency}")
                self.score -= 3

    def _validate_business_logic(self, invoice: InvoiceSchema):
        if invoice.invoice_date and invoice.due_date:
            try:
                inv_date = parser.parse(invoice.invoice_date)
                due_date = parser.parse(invoice.due_date)

                if due_date < inv_date:
                    self.errors.append("Due date cannot be before invoice date")
                    self.score -= 15

                days_diff = (due_date - inv_date).days
                if days_diff > 365:
                    self.warnings.append(f"Unusually long payment term: {days_diff} days")
                    self.score -= 5
            except (ValueError, TypeError, parser.ParserError) as e:
                # Date parsing failed, continue without error
                pass

        if invoice.subtotal and invoice.tax_amount and invoice.total_amount:
            calculated_total = invoice.subtotal + invoice.tax_amount
            if abs(calculated_total - invoice.total_amount) > 0.01:
                self.errors.append(
                    f"Amount mismatch: Subtotal ({invoice.subtotal}) + Tax ({invoice.tax_amount}) "
                    f"does not equal Total ({invoice.total_amount})"
                )
                self.score -= 20

        if invoice.line_items:
            line_items_total = sum(item.total or 0 for item in invoice.line_items if item.total)
            if invoice.subtotal and line_items_total > 0:
                if abs(line_items_total - invoice.subtotal) > 0.01:
                    self.warnings.append(
                        f"Line items total ({line_items_total}) does not match subtotal ({invoice.subtotal})"
                    )
                    self.score -= 5

    def _validate_anomalies(self, invoice: InvoiceSchema):
        if invoice.total_amount:
            if invoice.total_amount > 1000000:
                self.warnings.append(f"Unusually high amount: {invoice.total_amount}")
                self.score -= 3
            elif invoice.total_amount > 10000000:
                self.errors.append(f"Suspiciously high amount: {invoice.total_amount}")
                self.score -= 10

        if invoice.vendor_name and invoice.buyer_name:
            vendor_lower = invoice.vendor_name.lower()
            buyer_lower = invoice.buyer_name.lower()
            if vendor_lower == buyer_lower:
                self.warnings.append("Vendor and buyer names are identical")
                self.score -= 5

        if invoice.invoice_date:
            try:
                inv_date = parser.parse(invoice.invoice_date)
                today = datetime.now()
                days_old = (today - inv_date).days

                if days_old < -30:
                    self.warnings.append(f"Invoice date is {abs(days_old)} days in the future")
                    self.score -= 5
                elif days_old > 730:
                    self.warnings.append(f"Invoice is {days_old} days old")
                    self.score -= 3
            except (ValueError, TypeError, parser.ParserError) as e:
                # Date parsing failed, continue without error
                pass

    def _is_valid_date(self, date_str: str) -> bool:
        try:
            parser.parse(date_str)
            return True
        except (ValueError, TypeError, parser.ParserError):
            return False
