"""
NEXUS Media Extraction Terminal — FastAPI Backend
Stack: FastAPI + yt-dlp + Moyasar Payment + Rate Limiting
"""

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import yt_dlp
import os, uuid, time, httpx, hashlib
from collections import defaultdict
from pathlib import Path

app = FastAPI(title="NEXUS Downloader API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ──────────────────────────────────────────────
MOYASAR_SECRET   = os.getenv("MOYASAR_SECRET_KEY", "sk_test_YOUR_KEY_HERE")
MOYASAR_API      = "https://api.moyasar.com/v1"
DOWNLOAD_DIR     = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

FREE_LIMIT_PER_DAY = 10          # Free downloads per IP per day
PAID_PLAN_PRICE    = 1500        # SAR 15.00 in halalas (Moyasar uses halalas)

# ── In-memory stores (replace with Redis/DB in production) ──
ip_downloads: dict = defaultdict(lambda: {"count": 0, "date": ""})
paid_users:   set  = set()       # store tokens of paid users
pending_payments: dict = {}      # payment_id -> ip

# ── Models ──────────────────────────────────────────────
class DownloadRequest(BaseModel):
    url: str
    quality: str = "1080p"
    format: str  = "mp4"
    subtitles: bool = False
    user_token: str = ""          # paid user token

class PaymentRequest(BaseModel):
    amount: int = PAID_PLAN_PRICE
    currency: str = "SAR"
    description: str = "NEXUS Pro — Unlimited Downloads"
    callback_url: str
    source: dict                  # Moyasar source object (card/applepay/stcpay)

# ── Helpers ─────────────────────────────────────────────
def get_today() -> str:
    return time.strftime("%Y-%m-%d")

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    return forwarded.split(",")[0] if forwarded else request.client.host

def is_paid(token: str) -> bool:
    return token in paid_users

def check_rate_limit(ip: str, token: str):
    """Returns (allowed, remaining)"""
    if is_paid(token):
        return True, 999
    today = get_today()
    record = ip_downloads[ip]
    if record["date"] != today:
        record["count"] = 0
        record["date"]  = today
    remaining = FREE_LIMIT_PER_DAY - record["count"]
    return remaining > 0, max(0, remaining)

def increment_count(ip: str):
    today = get_today()
    record = ip_downloads[ip]
    if record["date"] != today:
        record["count"] = 0
        record["date"]  = today
    record["count"] += 1

def cleanup_file(path: str, delay: int = 300):
    """Delete file after delay seconds"""
    import threading
    def _delete():
        time.sleep(delay)
        try: os.remove(path)
        except: pass
    threading.Thread(target=_delete, daemon=True).start()

# ── Routes ──────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse("templates/index.html")

@app.get("/api/status")
async def status(request: Request, token: str = ""):
    ip = get_client_ip(request)
    allowed, remaining = check_rate_limit(ip, token)
    return {
        "ip": ip,
        "free_limit": FREE_LIMIT_PER_DAY,
        "remaining": remaining,
        "is_pro": is_paid(token),
        "status": "online"
    }

@app.post("/api/analyze")
async def analyze(req: DownloadRequest, request: Request):
    """Fetch metadata without downloading"""
    ip = get_client_ip(request)
    allowed, remaining = check_rate_limit(ip, req.user_token)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "DAILY_LIMIT_REACHED",
                "message": f"Free limit of {FREE_LIMIT_PER_DAY} downloads/day reached.",
                "upgrade": True
            }
        )
    ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
            formats = []
            seen = set()
            for f in (info.get("formats") or []):
                label = f.get("format_note") or f.get("height") or ""
                key = f"{label}-{f.get('ext','')}"
                if key in seen: continue
                seen.add(key)
                if f.get("vcodec") != "none" or f.get("acodec") != "none":
                    formats.append({
                        "format_id": f["format_id"],
                        "label": str(label),
                        "ext": f.get("ext",""),
                        "filesize": f.get("filesize") or f.get("filesize_approx"),
                        "vcodec": f.get("vcodec",""),
                        "acodec": f.get("acodec",""),
                    })
            return {
                "title":       info.get("title",""),
                "duration":    info.get("duration"),
                "thumbnail":   info.get("thumbnail",""),
                "uploader":    info.get("uploader",""),
                "view_count":  info.get("view_count"),
                "platform":    info.get("extractor",""),
                "formats":     formats[-20:],   # top 20
                "remaining":   remaining,
            }
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail={"error": "EXTRACT_FAILED", "message": str(e)})

@app.post("/api/download")
async def download(req: DownloadRequest, request: Request, background_tasks: BackgroundTasks):
    """Download and return file"""
    ip = get_client_ip(request)
    allowed, remaining = check_rate_limit(ip, req.user_token)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "DAILY_LIMIT_REACHED",
                "message": f"You've used all {FREE_LIMIT_PER_DAY} free downloads today.",
                "upgrade": True
            }
        )

    file_id  = str(uuid.uuid4())
    out_path = DOWNLOAD_DIR / f"{file_id}.%(ext)s"

    # Build yt-dlp options
    quality_map = {
        "8k":"bestvideo[height<=4320]+bestaudio/best",
        "4k":"bestvideo[height<=2160]+bestaudio/best",
        "1080p":"bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "720p":"bestvideo[height<=720]+bestaudio/best[height<=720]",
        "480p":"bestvideo[height<=480]+bestaudio/best[height<=480]",
        "audio":"bestaudio/best",
        "best":"bestvideo+bestaudio/best",
    }
    fmt_str = quality_map.get(req.quality, "bestvideo+bestaudio/best")

    ydl_opts = {
        "format":           fmt_str,
        "outtmpl":          str(out_path),
        "quiet":            True,
        "no_warnings":      True,
        "writesubtitles":   req.subtitles,
        "merge_output_format": req.format if req.format in ("mp4","mkv","webm") else "mp4",
        "postprocessors": [{
            "key": "FFmpegVideoConvertor",
            "preferedformat": req.format,
        }] if req.format in ("mp4","webm","mkv","mov") else [],
    }

    # Audio-only
    if req.format in ("mp3","m4a","flac"):
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": req.format,
            "preferredquality": "320" if req.format == "mp3" else "0",
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            title = info.get("title","download")

        # Find the output file
        found = list(DOWNLOAD_DIR.glob(f"{file_id}.*"))
        if not found:
            raise HTTPException(status_code=500, detail={"error":"FILE_NOT_FOUND"})

        real_path = found[0]
        increment_count(ip)
        background_tasks.add_task(cleanup_file, str(real_path), 600)  # delete after 10 min

        safe_title = "".join(c for c in title if c.isalnum() or c in " -_")[:60]
        return FileResponse(
            path=str(real_path),
            filename=f"{safe_title}{real_path.suffix}",
            media_type="application/octet-stream",
            headers={"X-Downloads-Remaining": str(remaining - 1)}
        )
    except yt_dlp.utils.DownloadError as e:
        raise HTTPException(status_code=400, detail={"error":"DOWNLOAD_FAILED","message":str(e)})

# ── Moyasar Payment ──────────────────────────────────────

@app.post("/api/payment/create")
async def create_payment(req: PaymentRequest, request: Request):
    """Create Moyasar payment — returns payment URL"""
    ip = get_client_ip(request)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MOYASAR_API}/payments",
            auth=(MOYASAR_SECRET, ""),
            json={
                "amount":      req.amount,
                "currency":    req.currency,
                "description": req.description,
                "callback_url": req.callback_url,
                "source":      req.source,
                "metadata":    {"ip": ip}
            }
        )
    data = resp.json()
    if resp.status_code != 201:
        raise HTTPException(status_code=400, detail=data)

    payment_id = data["id"]
    pending_payments[payment_id] = ip
    return {
        "payment_id": payment_id,
        "status":     data["status"],
        "redirect":   data.get("source", {}).get("transaction_url", ""),
    }

@app.get("/api/payment/callback")
async def payment_callback(id: str, status: str):
    """Moyasar calls this after payment"""
    if status != "paid":
        return JSONResponse({"success": False, "message": "Payment not completed"})

    # Verify with Moyasar
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{MOYASAR_API}/payments/{id}", auth=(MOYASAR_SECRET,""))
    data = resp.json()

    if data.get("status") != "paid":
        return JSONResponse({"success": False})

    # Generate user token
    ip = pending_payments.pop(id, "unknown")
    token = hashlib.sha256(f"{id}{ip}{time.time()}".encode()).hexdigest()[:32]
    paid_users.add(token)

    return JSONResponse({
        "success": True,
        "token":   token,
        "message": "Pro access activated — unlimited downloads!"
    })

@app.get("/api/payment/verify/{token}")
async def verify_token(token: str):
    return {"valid": token in paid_users, "pro": token in paid_users}

# ── Run ──────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
