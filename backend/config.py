import os
from dotenv import load_dotenv

load_dotenv()

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
MONGODB_DATABASE_NAME = os.getenv("MONGODB_DATABASE_NAME", "invoicely")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
