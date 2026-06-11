from dotenv import load_dotenv
import os

load_dotenv()

# API কনফিগুরেশন
COBALT_API_URL = "https://api.cobalt.tools/api/v1"
COBALT_API_KEY = os.getenv("COBALT_API_KEY", "your-cobalt-api-key")

# পেমেন্ট গেটওয়ে
MOYASAR_API_KEY = os.getenv("MOYASAR_API_KEY", "your-moyasar-api-key")
MOYASAR_API_URL = "https://api.moyasar.com/v1"

# ডাটাবেস
DATABASE_URL = "sqlite:///./nexus.db"

# সাবস্ক্রিপশন লিমিট
FREE_DOWNLOADS_PER_DAY = 10
SUBSCRIPTION_PRICE = 999  # মূল্য (Fils - সৌদি রিয়ালের ছোট একক)

# CORS
ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:3000",
    "http://127.0.0.1:8000",
]
