from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime

from database import init_db, get_db
from models import Download, Payment
from schemas import DownloadRequest, DownloadResponse, UserStats, PaymentRequest
from services import CobaltService, UserService, PaymentService
from config import ALLOWED_ORIGINS, FREE_DOWNLOADS_PER_DAY

# FastAPI অ্যাপ্লিকেশন
app = FastAPI(
    title="NEXUS Media Downloader",
    description="সাইবারপাঙ্ক থিমযুক্ত মিডিয়া ডাউনলোডার",
    version="1.0.0"
)

# CORS মিডলওয়্যার
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# স্ট্যাটিক ফাইল সেবা (ফ্রন্টএন্ড)
frontend_path = Path(__file__).parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

# ========== স্টার্টআপ ইভেন্ট ==========

@app.on_event("startup")
async def startup():
    """অ্যাপ্লিকেশন শুরু হওয়ার সময় ডাটাবেস ইনিশিয়ালাইজ করুন"""
    init_db()
    print("✅ ডাটাবেস ইনিশিয়ালাইজ সম্পন্ন")

# ========== প্রাথমিক এন্ডপয়েন্ট ==========

@app.get("/", response_class=HTMLResponse)
async def root():
    """হোম পেজে সরাসরি index.html ফাইলের ভেতরের নিয়ন কোড লোড করুন"""
    try:
        # এটি আপনার ফোল্ডার থেকে সরাসরি index.html ফাইলের ভেতরের ডিজাইনটি পড়ে ব্রাউজারে রান করবে
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        try:
            # যদি ফোল্ডারের নাম বড় হাতের 'Frontend' হয়ে থাকে, তবে এটি ব্যাকআপ হিসেবে কাজ করবে
            with open("Frontend/index.html", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "<h3>Error: index.html file not found in frontend folder! Please check your folder name.</h3>"


# ========== ডাউনলোড এন্ডপয়েন্ট ==========

@app.post("/api/download", response_model=DownloadResponse)
async def download(request: DownloadRequest, db: Session = Depends(get_db)):
    """মিডিয়া ডাউনলোড করুন"""
    
    try:
        # ইউজার পান বা তৈরি করুন
        user = UserService.get_or_create_user(db, request.user_id)
        
        # ডাউনলোড অনুমোদন চেক করুন
        can_download, message = UserService.can_download(user, db)
        
        if not can_download:
            return DownloadResponse(
                success=False,
                message=message,
                downloads_remaining=max(0, FREE_DOWNLOADS_PER_DAY - user.downloads_today),
                is_premium=user.is_premium
            )
        
        # Cobalt API থেকে ডাউনলোড করুন
        cobalt_result = await CobaltService.download(
            url=request.url,
            quality=request.quality,
            format=request.format
        )
        
        # প্ল্যাটফর্ম নির্ণয়
        try:
            platform = request.url.split('/')[2].replace('www.', '')
        except:
            platform = "unknown"
        
        if not cobalt_result["success"]:
            # ব্যর্থ ডাউনলোড রেকর্ড করুন
            download_record = Download(
                user_id=request.user_id,
                url=request.url,
                platform=platform,
                status="failed"
            )
            db.add(download_record)
            db.commit()
            
            return DownloadResponse(
                success=False,
                message=f"ডাউনলোড ব্যর্থ: {cobalt_result.get('error', 'Unknown error')}",
                downloads_remaining=max(0, FREE_DOWNLOADS_PER_DAY - user.downloads_today),
                is_premium=user.is_premium
            )
        
        # সফল ডাউনলোড - কাউন্ট বৃদ্ধি করুন
        UserService.increment_download_count(user, db)
        
        # সফল ডাউনলোড রেকর্ড করুন
        download_record = Download(
            user_id=request.user_id,
            url=request.url,
            platform=platform,
            status="completed"
        )
        db.add(download_record)
        db.commit()
        
        return DownloadResponse(
            success=True,
            message="ডাউনলোড সফল! 🎉",
            download_url=cobalt_result.get("download_url"),
            downloads_remaining=max(0, FREE_DOWNLOADS_PER_DAY - user.downloads_today),
            is_premium=user.is_premium
        )
    
    except Exception as e:
        return DownloadResponse(
            success=False,
            message=f"সার্ভার এরর: {str(e)}",
            downloads_remaining=0,
            is_premium=False
        )

# ========== ইউজার স্ট্যাটিস্টিক্স ==========

@app.get("/api/user-stats/{user_id}", response_model=UserStats)
async def get_user_stats(user_id: str, db: Session = Depends(get_db)):
    """ইউজার স্ট্যাটিস্টিক্স পান"""
    
    try:
        user = UserService.get_or_create_user(db, user_id)
        UserService.reset_daily_limit(user)
        db.commit()
        
        return UserStats(
            user_id=user.user_id,
            downloads_today=user.downloads_today,
            downloads_remaining=max(0, FREE_DOWNLOADS_PER_DAY - user.downloads_today),
            is_premium=user.is_premium,
            premium_until=user.premium_until
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== পেমেন্ট এন্ডপয়েন্ট ==========

@app.post("/api/create-payment")
async def create_payment(request: PaymentRequest, db: Session = Depends(get_db)):
    """প্রিমিয়াম সাবস্ক্রিপশনের জন্য পেমেন্ট তৈরি করুন"""
    
    try:
        user = UserService.get_or_create_user(db, request.user_id)
        
        # Moyasar এ পেমেন্ট তৈরি করুন
        payment_result = await PaymentService.create_payment(
            user_id=request.user_id,
            amount=request.amount
        )
        
        if not payment_result["success"]:
            return {
                "success": False,
                "message": "পেমেন্ট তৈরি ব্যর্থ",
                "error": payment_result.get("error")
            }
        
        # পেমেন্ট রেকর্ড সংরক্ষণ করুন
        payment = Payment(
            user_id=request.user_id,
            transaction_id=payment_result["transaction_id"],
            amount=request.amount,
            status="pending"
        )
        db.add(payment)
        db.commit()
        
        return {
            "success": True,
            "transaction_id": payment_result["transaction_id"],
            "payment_url": payment_result["payment_url"],
            "message": "পেমেন্ট পৃষ্ঠায় পুনঃনির্দেশিত হচ্ছে..."
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

@app.post("/api/verify-payment/{transaction_id}")
async def verify_payment(transaction_id: str, db: Session = Depends(get_db)):
    """পেমেন্ট ভেরিফাই করুন এবং প্রিমিয়াম সক্রিয় করুন"""
    
    try:
        payment = db.query(Payment).filter(
            Payment.transaction_id == transaction_id
        ).first()
        
        if not payment:
            return {
                "success": False,
                "message": "পেমেন্ট পাওয়া যায়নি"
            }
        
        # ইউজার পান
        user = UserService.get_or_create_user(db, payment.user_id)
        
        # প্রিমিয়াম সক্রিয় করুন
        PaymentService.activate_premium(db, user, days=30)
        
        payment.status = "success"
        db.commit()
        
        return {
            "success": True,
            "message": "প্রিমিয়াম সক্রিয় হয়েছে! 🌟",
            "premium_until": user.premium_until
        }
    
    except Exception as e:
        return {
            "success": False,
            "message": str(e)
        }

# ========== হেলথ চেক ==========

@app.get("/health")
async def health_check():
    """সার্ভার স্টেটাস চেক করুন"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

# ========== এরর হ্যান্ডলার ==========

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """HTTP এক্সেপশন হ্যান্ডেল করুন"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# যদি সরাসরি এই ফাইল চালান
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
