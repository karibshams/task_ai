import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Gemini AI Configuration (Loaded from .env / Environment)
GEMINI_AI_API_KEY = os.getenv("GEMINI_AI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.5-flash-lite")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")

# Existing Business System REST API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://staging.limoground.com/api/v1/passenger")
DEFAULT_USER_EMAIL = os.getenv("DEFAULT_USER_EMAIL", "zentixsoftsamsu@gmail.com")
DEFAULT_USER_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "Test?123")
DEFAULT_USER_COMPANY = os.getenv("DEFAULT_USER_COMPANY", "limoground2")

# Policy RAG Configuration
POLICY_PDF_PATH = os.path.join(BASE_DIR, "service_policy.pdf")
POLICY_INDEX_PATH = os.path.join(BASE_DIR, "rag", "policy_index.json")

# Application Server
PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")
SECRET_KEY = os.getenv("SECRET_KEY", "business-assistant-secret-key-2026")
DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
