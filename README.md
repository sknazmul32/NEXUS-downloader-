# NEXUS Media Extraction Terminal
## Full Stack: FastAPI + yt-dlp + Moyasar + AdSense + VPN Affiliates

---

## 📁 Project Structure
```
nexus/
├── main.py              ← FastAPI backend
├── requirements.txt     ← Python dependencies
├── render.yaml          ← Render.com auto-deploy config
└── templates/
    └── index.html       ← Full frontend UI
```

---

## 🚀 Deploy on Render.com (Free)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "NEXUS downloader — full stack"
git remote add origin https://github.com/YOUR_USERNAME/nexus-downloader.git
git push -u origin main
```

### Step 2 — Create Render Web Service
1. Go to https://render.com → New → Web Service
2. Connect your GitHub repo
3. Settings:
   - **Environment:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Step 3 — Add Environment Variables on Render
```
MOYASAR_SECRET_KEY = sk_live_YOUR_MOYASAR_KEY
```

---

## 💰 Affiliate Links — Replace These

In `templates/index.html`, find and replace:

| Placeholder | Replace with |
|---|---|
| `YOUR_AFFILIATE_ID` (NordVPN) | Your NordVPN affiliate link from partners.nordvpn.com |
| `YOUR_AFFILIATE_ID` (ExpressVPN) | Your ExpressVPN link from expressvpn.com/affiliates |
| `ca-pub-XXXXXXXXXXXXXXXX` | Your Google AdSense publisher ID |
| `1234567890` (ad slot) | Your AdSense ad slot ID |

---

## 💳 Moyasar Setup
1. Sign up at https://moyasar.com
2. Get your API keys from dashboard
3. Set `MOYASAR_SECRET_KEY` in Render environment variables
4. Update `callback_url` in payment to your Render domain

---

## 📊 Revenue Streams
| Source | Est. Monthly (1000 users/day) |
|---|---|
| Google AdSense | SAR 50–200 |
| NordVPN affiliate ($30-100/signup) | SAR 500–2000+ |
| ExpressVPN affiliate | SAR 300–1500+ |
| NEXUS Pro (SAR 15/mo) | SAR 500–5000+ |

---

## ⚠️ Legal Note
This tool uses yt-dlp for downloading. Only download content
you have rights to download. Check platform ToS before deploying commercially.
