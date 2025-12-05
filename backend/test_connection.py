#!/usr/bin/env python3
"""
Quick diagnostic script to test MongoDB connection and backend setup
"""

import sys
import os

def test_imports():
    """Test if all required packages are installed"""
    print("Testing imports...")
    try:
        import fastapi
        import pymongo
        import pdfplumber
        import pydantic
        print("✓ All required packages are installed")
        return True
    except ImportError as e:
        print(f"✗ Missing package: {e}")
        print("  Run: pip install -r requirements.txt")
        return False

def test_env_file():
    """Test if .env file exists and has required variables"""
    print("\nTesting .env file...")
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    
    if not os.path.exists(env_path):
        print("✗ .env file not found in backend directory")
        print("  Create it from .env.example")
        return False
    
    print("✓ .env file exists")
    
    # Try to load and check variables
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        
        mongodb_url = os.getenv("MONGODB_URL")
        mongodb_db = os.getenv("MONGODB_DATABASE_NAME")
        
        if not mongodb_url:
            print("✗ MONGODB_URL not set in .env")
            return False
        
        if not mongodb_db:
            print("✗ MONGODB_DATABASE_NAME not set in .env")
            return False
        
        print(f"✓ MONGODB_URL: {mongodb_url[:30]}...")
        print(f"✓ MONGODB_DATABASE_NAME: {mongodb_db}")
        return True
    except Exception as e:
        print(f"✗ Error reading .env: {e}")
        return False

def test_mongodb_connection():
    """Test MongoDB connection"""
    print("\nTesting MongoDB connection...")
    try:
        from config import MONGODB_URL, MONGODB_DATABASE_NAME
        from pymongo import MongoClient
        
        client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
        # Test connection
        server_info = client.server_info()
        print(f"✓ Connected to MongoDB")
        print(f"  Version: {server_info.get('version', 'unknown')}")
        
        # Test database access
        db = client[MONGODB_DATABASE_NAME]
        collections = db.list_collection_names()
        print(f"✓ Database '{MONGODB_DATABASE_NAME}' accessible")
        print(f"  Collections: {collections if collections else 'None (will be created on first insert)'}")
        
        client.close()
        return True
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
        print("\n  Troubleshooting:")
        print("  1. Ensure MongoDB is running:")
        print("     - Windows: net start MongoDB")
        print("     - macOS: brew services start mongodb-community")
        print("     - Linux: sudo systemctl start mongodb")
        print("  2. Check MONGODB_URL in .env file")
        print("  3. For MongoDB Atlas, verify network access settings")
        return False

def test_database_class():
    """Test Database class initialization"""
    print("\nTesting Database class...")
    try:
        from database import Database
        db = Database()
        print("✓ Database class initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Database class initialization failed: {e}")
        return False

def main():
    print("=" * 60)
    print("Invoicely Backend Diagnostic Tool")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Environment", test_env_file()))
    results.append(("MongoDB Connection", test_mongodb_connection()))
    results.append(("Database Class", test_database_class()))
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    
    if all_passed:
        print("\n✓ All checks passed! Backend should work correctly.")
        print("\nStart the backend with:")
        print("  python main.py")
    else:
        print("\n✗ Some checks failed. Please fix the issues above.")
        print("\nSee TROUBLESHOOTING.md for detailed help.")
        sys.exit(1)

if __name__ == "__main__":
    main()

