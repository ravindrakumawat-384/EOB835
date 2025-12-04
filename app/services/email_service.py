
from typing import Optional, Dict, Any
from ..common.config import settings
from datetime import datetime
import smtplib
from email.message import EmailMessage


# SMTP configuration (move to config/settings if needed)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587  # TLS
SMTP_USER = "kumawatr196@gmail.com"
SMTP_PASS = "tnnv rafe surl igon"  # Use app password for Gmail

def send_reset_email(to_email: str, token: str) -> bool:
    try:
        msg = EmailMessage()
        msg["Subject"] = "Password Reset"
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg.set_content(
            f"Hello,\n\nUse the following token to reset your password (copy it exactly, no spaces or line breaks):\n\n{token}\n\nIf you have issues, try pasting the token into a text editor first to remove any extra spaces.\n\nRegards."
        )

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print("Failed to send reset email:", e)
        return False

# Optionally, keep the stub for dev/testing, but it no longer logs to MongoDB
async def send_email_stub(
    to_email: str,
    subject: str,
    template_name: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    print(f"[DEV EMAIL STUB] Would send to {to_email} | subject: {subject} | payload: {payload}")
