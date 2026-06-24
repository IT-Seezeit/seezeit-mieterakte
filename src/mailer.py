from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings
from .safety import Safety


class Mailer:
    def __init__(self, settings: Settings, safety: Safety) -> None:
        self.settings = settings
        self.safety = safety

    def send_mail(self, to_address: object, subject: str, body: str) -> dict[str, object]:
        preview = {"to": str(to_address or ""), "subject": subject, "body": body}
        if not self.settings.send_emails:
            return {"sent": False, "prepared": False, "skipped": True, **preview}
        if self.safety.dry_run or not self._has_smtp_config():
            print(f"MAIL PREVIEW to={preview['to']} subject={subject}\n{body}")
            return {"sent": False, "prepared": True, **preview}

        message = EmailMessage()
        message["From"] = self.settings.mail_from
        message["To"] = str(to_address)
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(self.settings.mail_smtp_host, self.settings.mail_smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if self.settings.mail_username:
                smtp.login(self.settings.mail_username, self.settings.mail_password)
            smtp.send_message(message)

        return {"sent": True, "prepared": False, **preview}

    def _has_smtp_config(self) -> bool:
        return bool(self.settings.mail_smtp_host and self.settings.mail_from)
