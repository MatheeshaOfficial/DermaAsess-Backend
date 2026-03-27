import os
from dotenv import load_dotenv

load_dotenv()

# Database
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# Telegram Bot
API_ID = os.getenv("API_ID", "0")
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

# APIs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "")
USDA_API_KEY = os.getenv("USDA_API_KEY", "")

# Email
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "DermaAssess AI")

# App Auth & Web
JWT_SECRET = os.getenv("JWT_SECRET", "your-jwt-secret-min-32-chars-long")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,https://your-app.vercel.app")

#URL
FRONTEND_URL = ALLOWED_ORIGINS
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
