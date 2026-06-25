from __future__ import annotations

import smtplib
from email.message import EmailMessage

from .config import Settings
from .safety import Safety


class Mailer:
    def __init__(self, settings: Settings, safety: Safety) -> None:
        self.settings = settings
        self.safety = safety

    def send_mail(
        self,
        to_address: object,
        subject: str,
        body: str,
        share_link: str = "",
        expiration_date: str = "",
        dummy_password_set: bool = False,
    ) -> dict[str, object]:
        preview = {"to": str(to_address or ""), "subject": subject, "body": body}
        if self.settings.preview_emails:
            if not share_link:
                print("WARN Email preview skipped: no share link available.")
                return {"sent": False, "prepared": False, "skipped": True, "reason": "missing_share_link"}
            preview_body = self._preview_body(
                to_address=to_address,
                subject=subject,
                body=body,
                share_link=share_link,
                expiration_date=expiration_date,
                dummy_password_set=dummy_password_set,
            )
            print(preview_body)
            return {
                "sent": False,
                "prepared": True,
                "preview": True,
                "to": str(to_address or ""),
                "subject": subject,
                "body": body,
                "share_link": share_link,
                "expiration_date": expiration_date,
            }
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

        return {"sent": True, "prepared": False}

    def _preview_body(
        self,
        to_address: object,
        subject: str,
        body: str,
        share_link: str,
        expiration_date: str,
        dummy_password_set: bool,
    ) -> str:
        lines = [
            "MAIL PREVIEW",
            f"To: {to_address or ''}",
            f"Subject: {subject}",
            "",
            body,
            "",
            f"Share link: {share_link}",
            f"Expiration date: {expiration_date or 'unknown'}",
            "Password notice: Das Passwort wird separat mitgeteilt.",
        ]
        if self.settings.use_dummy_values:
            lines.append(f"Dummy-Passwort gesetzt: {'ja' if dummy_password_set else 'nein'}")
        return "\n".join(lines)

    def _has_smtp_config(self) -> bool:
        return bool(self.settings.mail_smtp_host and self.settings.mail_from)
