from datetime import datetime, timedelta
import httpx
from sqlalchemy.orm import Session
from models import User

FREE_DOWNLOADS_PER_DAY = 10

class UserService:
    @staticmethod
    def get_or_create_user(db: Session, identifier: str) -> User:
        """ইউজারের আইপি বা আইডি দিয়ে তাকে ডেটাবেসে খুঁজুন বা নতুন তৈরি করুন"""
        user = db.query(User).filter(User.identifier == identifier).first()
        if not user:
            user = User(identifier=identifier)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def reset_daily_limit(user: User):
        """নতুন দিন শুরু হলে ইউজারের দৈনিক লিমিট রিসেট করুন"""
        if not user.last_download_date or user.last_download_date.date() < datetime.utcnow().date():
            user.downloads_today = 0
            user.last_download_date = datetime.utcnow()

    @staticmethod
    def can_download(user: User, db: Session):
        """ইউজার ডাউনলোড করতে পারবে কি তা চেক করুন"""
        # প্রিমিয়াম ইউজারদের জন্য কোনো লিমিট নেই
        if user.is_premium and user.premium_until and user.premium_until > datetime.utcnow():
            return True, "প্রিমিয়াম ব্যবহারকারী"
        
        # ফ্রি ইউজারদের জন্য দৈনিক লিমিট চেক করুন
        UserService.reset_daily_limit(user)
        
        if user.downloads_today >= FREE_DOWNLOADS_PER_DAY:
            return False, f"আজকের {FREE_DOWNLOADS_PER_DAY} ডাউনলোডের লিমিট শেষ। প্রিমিয়াম আপগ্রেড করুন।"
        
        return True, "ডাউনলোড অনুমোদিত"

    @staticmethod
    def increment_download(db: Session, user: User):
        """ইউজারের ডাউনলোড সংখ্যা ১ বাড়িয়ে দিন"""
        user.downloads_today += 1
        user.last_download_date = datetime.utcnow()
        db.commit()


class CobaltService:
    @staticmethod
    async def extract_video(video_url: str, api_key: str = None) -> dict:
        """Cobalt API ব্যবহার করে ভিডিও লিঙ্ক এক্সট্র্যাক্ট করুন"""
        api_url = "https://cobalt.tools"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            
        payload = {
            "url": video_url,
            "vQuality": "720"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(api_url, json=payload, headers=headers)
            if response.status_code == 200:
                res_data = response.json()
                formats_list = []
                
                if res_data.get('status') == 'stream':
                    formats_list.append({
                        'quality': 'Video (Best Quality)',
                        'ext': 'mp4',
                        'url': res_data.get('url')
                    })
                    return {'success': True, 'formats': formats_list}
                elif res_data.get('status') == 'picker':
                    for item in res_data.get('picker', []):
                        formats_list.append({
                            'quality': f"{item.get('type', 'Media')} ({item.get('quality', 'Default')})",
                            'ext': 'link',
                            'url': item.get('url')
                        })
                    return {'success': True, 'formats': formats_list}
            
            # কোনো কারণে ব্যর্থ হলে বা এরর দিলে
            raise Exception("Cobalt API could not parse the video link.")


class PaymentService:
    @staticmethod
    def process_premium_upgrade(db: Session, user: User, amount: float) -> bool:
        """Moyasar পেমেন্ট সফল হলে ইউজারকে ৩০ দিনের জন্য প্রিমিয়াম করে দিন"""
        # সৌদি রিয়াল বা পেমেন্ট ভ্যালিডেশন লজিক (আপাতত টেস্ট বেসড)
        if amount >= 10.0: # উদাহরণস্বরূপ ১০ রিয়াল
            user.is_premium = True
            user.premium_until = datetime.utcnow() + timedelta(days=30)
            db.commit()
            return True
        return False
