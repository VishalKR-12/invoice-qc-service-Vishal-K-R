from pymongo import MongoClient
from pymongo.collection import Collection
try:
    from gridfs import GridFS
except ImportError:
    from pymongo.gridfs import GridFS
from bson import ObjectId
from config import MONGODB_URL, MONGODB_DATABASE_NAME
from typing import List, Dict, Any, Optional
from datetime import datetime

class Database:
    def __init__(self):
        try:
            self.client: MongoClient = MongoClient(
    MONGODB_URL,
    serverSelectionTimeoutMS=5000,
    tls=True,
    tlsAllowInvalidCertificates=True
)

            # Test the connection
            self.client.server_info()
            self.db = self.client[MONGODB_DATABASE_NAME]
            self.collection: Collection = self.db["invoices"]
            self.fs = GridFS(self.db, collection="files")  # GridFS for file storage
            
            # Create indexes for better query performance
            self._create_indexes()
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MongoDB: {str(e)}. Please check your MONGODB_URL in .env file.")

    def _create_indexes(self):
        """Create indexes for common queries"""
        self.collection.create_index("invoice_number")
        self.collection.create_index("created_at", background=True)
        self.collection.create_index("is_valid", background=True)
        self.collection.create_index("vendor_name", background=True)

    def save_file(self, file_content: bytes, filename: str, content_type: str = None) -> str:
        """Save a file to GridFS and return the file_id"""
        try:
            file_id = self.fs.put(
                file_content,
                filename=filename,
                content_type=content_type or "application/octet-stream"
            )
            return str(file_id)
        except Exception as e:
            print(f"Error saving file to GridFS: {str(e)}")
            raise

    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a file from GridFS by file_id"""
        try:
            if not ObjectId.is_valid(file_id):
                return None
            
            grid_file = self.fs.get(ObjectId(file_id))
            if grid_file:
                return {
                    "content": grid_file.read(),
                    "filename": grid_file.filename,
                    "content_type": grid_file.content_type,
                    "length": grid_file.length
                }
            return None
        except Exception as e:
            print(f"Error retrieving file from GridFS: {str(e)}")
            return None

    def delete_file(self, file_id: str) -> bool:
        """Delete a file from GridFS by file_id"""
        try:
            if not ObjectId.is_valid(file_id):
                return False
            
            self.fs.delete(ObjectId(file_id))
            return True
        except Exception as e:
            print(f"Error deleting file from GridFS: {str(e)}")
            return False

    def save_invoice(self, invoice_data: Dict[str, Any], validation_result: Dict[str, Any], file_id: Optional[str] = None) -> str:
        invoice_record = {
            "invoice_number": invoice_data.get("invoice_number"),
            "vendor_name": invoice_data.get("vendor_name"),
            "buyer_name": invoice_data.get("buyer_name"),
            "vendor_address": invoice_data.get("vendor_address"),
            "buyer_address": invoice_data.get("buyer_address"),
            "invoice_date": invoice_data.get("invoice_date"),
            "due_date": invoice_data.get("due_date"),
            "currency": invoice_data.get("currency") or "USD",
            "subtotal": invoice_data.get("subtotal"),
            "tax_amount": invoice_data.get("tax_amount"),
            "total_amount": invoice_data.get("total_amount"),
            "payment_terms": invoice_data.get("payment_terms"),
            "line_items": invoice_data.get("line_items", []),
            "is_valid": validation_result.get("is_valid", False),
            "validation_score": validation_result.get("score", 0),
            "validation_errors": validation_result.get("errors", []),
            "validation_warnings": validation_result.get("warnings", []),
            "file_id": file_id,  # Store reference to file in GridFS
            "file_name": invoice_data.get("file_name"),  # Store original filename
            "file_type": invoice_data.get("file_type"),  # Store file type/extension
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }

        result = self.collection.insert_one(invoice_record)
        return str(result.inserted_id)

    def get_invoice(self, invoice_id: str) -> Optional[Dict[str, Any]]:
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(invoice_id):
                return None
            
            invoice = self.collection.find_one({"_id": ObjectId(invoice_id)})
            if invoice:
                # Convert ObjectId to string for JSON serialization
                invoice["id"] = str(invoice.pop("_id"))
                return invoice
            return None
        except Exception:
            return None

    def get_all_invoices(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        invoices = list(
            self.collection.find()
            .sort("created_at", -1)
            .skip(offset)
            .limit(limit)
        )
        
        # Convert ObjectId to string for each invoice
        for invoice in invoices:
            invoice["id"] = str(invoice.pop("_id"))
        
        return invoices

    def get_invoices_count(self) -> int:
        return self.collection.count_documents({})

    def delete_invoice(self, invoice_id: str) -> bool:
        """Delete an invoice by ID. Also deletes associated file if exists. Returns True if deleted, False if not found."""
        try:
            # Validate ObjectId format
            if not ObjectId.is_valid(invoice_id):
                return False
            
            # Get invoice to find file_id before deleting
            invoice = self.collection.find_one({"_id": ObjectId(invoice_id)})
            if invoice:
                # Delete associated file if exists
                file_id = invoice.get("file_id")
                if file_id:
                    try:
                        self.delete_file(file_id)
                    except Exception as file_error:
                        print(f"Warning: Could not delete file {file_id}: {str(file_error)}")
            
            result = self.collection.delete_one({"_id": ObjectId(invoice_id)})
            return result.deleted_count > 0
        except Exception as e:
            print(f"Error deleting invoice: {str(e)}")
            return False

    def get_dashboard_stats(self) -> Dict[str, Any]:
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total_invoices": {"$sum": 1},
                    "valid_invoices": {
                        "$sum": {"$cond": ["$is_valid", 1, 0]}
                    },
                    "total_amount": {
                        "$sum": {"$ifNull": ["$total_amount", 0]}
                    },
                    "total_score": {
                        "$sum": {"$ifNull": ["$validation_score", 0]}
                    }
                }
            }
        ]
        
        result = list(self.collection.aggregate(pipeline))
        
        if result:
            stats = result[0]
            total_invoices = stats.get("total_invoices", 0)
            valid_invoices = stats.get("valid_invoices", 0)
            invalid_invoices = total_invoices - valid_invoices
            total_amount = stats.get("total_amount", 0)
            total_score = stats.get("total_score", 0)
            
            avg_score = (total_score / total_invoices) if total_invoices > 0 else 0
        else:
            total_invoices = 0
            valid_invoices = 0
            invalid_invoices = 0
            total_amount = 0
            avg_score = 0

        return {
            "total_invoices": total_invoices,
            "valid_invoices": valid_invoices,
            "invalid_invoices": invalid_invoices,
            "total_amount": round(total_amount, 2),
            "average_validation_score": round(avg_score, 2)
        }
