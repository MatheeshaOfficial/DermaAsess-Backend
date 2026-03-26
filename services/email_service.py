import os
import httpx
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@yourdomain.com")

async def send_email(to: str, subject: str, html_body: str) -> bool:
    if not RESEND_API_KEY:
        print("RESEND_API_KEY not configured, skipping email.")
        return False
        
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "html": html_body
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Email failure: {e}")
            return False
