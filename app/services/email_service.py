

from typing import Optional, Dict, Any
from ..common.config import settings
from datetime import datetime
import smtplib
from email.message import EmailMessage
from ..utils.logger import get_logger
logger = get_logger(__name__)


# SMTP configuration (move to config/settings if needed)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587  # TLS
SMTP_USER = "kumawatr196@gmail.com"
SMTP_PASS = "tnnv rafe surl igon"  # Use app password for Gmail

def send_reset_email(to_email: str, token: str) -> bool:
    try:
        print("Enter in SEnd Reset mail fucntion")
        msg = EmailMessage()
        msg["Subject"] = "Password Reset"
        msg["From"] = SMTP_USER
        msg["To"] = to_email

        frontend = settings.FRONTEND_URL or ""
        # reset_link = f"https://your-frontend/reset-password?token={reset_token}"
        reset_link = f"{frontend.rstrip('/')}" + f"/auth/set-password/{token}"
        
        # msg.set_content(
        #     f"Hello,\n\nUse the following token to reset your password (copy it exactly, no spaces or line breaks):\n\n{reset_link}\n\nIf you have issues, try pasting the token into a text editor first to remove any extra spaces.\n\nRegards."
        # )

        # msg.set_content(
        #     f"Hello,\n\n"
        #     f"Use the following link to reset your password:\n\n"
        #     f"{reset_link}\n\n"
        #     f"If you have issues, try pasting the link into a browser.\n\n"
        #     f"Regards."
        # )

        msg.add_alternative(
            f"""
            <html>
                <body>
                    <p>Hello,</p>
                    <p>
                        Use the following link to reset your password:<br>
                        <a href="{reset_link}" style="color:#1a73e8; text-decoration:underline;">Reset Password
                        </a>
                    </p>
                    <p>If you have issues, try pasting the link into your browser.</p>
                    <p>Regards.</p>
                </body>
            </html>
            """,
            subtype="html"
        )


        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        logger.info(f"Password reset email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email to {to_email}: {e}")
        return False

# Optionally, keep the stub for dev/testing, but it no longer logs to MongoDB
async def send_email_stub(
    to_email: str,
    subject: str,
    template_name: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        logger.info(f"[DEV EMAIL STUB] Would send to {to_email} | subject: {subject} | payload: {payload}")
    except Exception as e:
        logger.error(f"Failed to log email stub for {to_email}: {e}")





def send_invite_email(to_email: str, temp_pass, user_name: str, org_name: str, invite_token) -> bool:
    try:
        print("Enter in SSend Invite mail function")
        msg = EmailMessage()
        msg["Subject"] = "Invitation to Join"
        msg["From"] = SMTP_USER
        msg["To"] = to_email

        frontend = settings.FRONTEND_URL or ""
        login_url = f"{frontend.rstrip('/')}" + f"/auth/login/?invite_token={invite_token}"

        msg.add_alternative(
            f"""
            <html>
                <body>
                    <p>Hello {user_name},</p>

                    <p>
                        You have been invited to join <strong>{org_name}</strong> on our platform.
                    </p>

                    <p>
                        By accepting this invitation, you’ll be able to access the organization’s resources
                        and collaborate with the team.
                    </p>

                    <p>
                        Please click the link below to accept the invitation and complete your setup:<br>
                        <a href="{login_url}" style="color:#1a73e8; text-decoration:underline;">
                            Accept Invitation
                        </a>
                    </p>
                    <p>
                        This link will expire in 24 hours.
                    </p>
                    
                    <p>
                        Please find your login details below:
                    </p>
                    
                    <p>
                        Email: <strong>{to_email}</strong><br>
                        Your temporary password is: <strong>{temp_pass}</strong><br>
                        (Please change your password after logging in for the first time.)
                    </p>


                    <p>
                        If you face any issues, try pasting the link into your browser.
                    </p>

                    <p>Regards,<br>
                    Team EOB
                    </p>
                </body>
            </html>
            """,
            subtype="html"
        )

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)
        logger.info(f"Password reset email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email to {to_email}: {e}")
        return False
