import aiosmtplib
from email.message import EmailMessage
from typing import Optional

from config import settings



import sys
from pathlib import Path

# Add app directory to path for imports
sys.path.append(str(Path(__file__).resolve().parents[1]))

class EmailService:
    @staticmethod
    async def send_email(to_email: str, subject: str, text: str, html: Optional[str] = None) -> None:
        msg = EmailMessage()
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(text)
        if html:
            msg.add_alternative(html, subtype="html")

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            start_tls=True,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
        )


