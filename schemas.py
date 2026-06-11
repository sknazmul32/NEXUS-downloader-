from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class DownloadRequest(BaseModel):
    url: str
    user_id: str
    format: str = "mp4"
    quality: str = "720"

class DownloadResponse(BaseModel):
    success: bool
    message: str
    download_url: Optional[str] = None
    downloads_remaining: int  # ✅ এটি যোগ করুন
    is_premium: bool

class UserStats(BaseModel):
    user_id: str
    downloads_today: int
    downloads_remaining: int
    is_premium: bool
    premium_until: Optional[datetime] = None

class PaymentRequest(BaseModel):
    user_id: str
    amount: float = 9.99
    description: str = "NEXUS Premium Subscription (1 Month)"

class PaymentResponse(BaseModel):
    success: bool
    transaction_id: Optional[str] = None
    payment_url: Optional[str] = None
    message: str
