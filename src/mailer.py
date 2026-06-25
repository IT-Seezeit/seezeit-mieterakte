from __future__ import annotations

from html import escape
from pathlib import Path
import re
import smtplib
from email.message import EmailMessage

from .config import Settings
from .safety import Safety


TENANT_FILE_SUBJECT = "Ihre digitale Mieterakte / Your digital tenant file"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEXT_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "tenant_file_email.txt"
HTML_TEMPLATE_PATH = PROJECT_ROOT / "templates" / "tenant_file_email.html"
PREVIEW_LOG_DIR = PROJECT_ROOT / "logs"
MAIL_TEMPLATES = {
    "move_in": (
        PROJECT_ROOT / "templates" / "tenant_file_move_in.txt",
        PROJECT_ROOT / "templates" / "tenant_file_move_in.html",
    ),
    "move_out": (
        PROJECT_ROOT / "templates" / "tenant_file_move_out.txt",
        PROJECT_ROOT / "templates" / "tenant_file_move_out.html",
    ),
}


class Mailer:
    def __init__(self, settings: Settings, safety: Safety) -> None:
        self.settings = settings
        self.safety = safety

    def build_tenant_file_body(
        self,
        mail_type: str,
        recipient_name: str,
        share_link: str,
        share_password: str,
        expiration_date: str,
    ) -> str:
        values = self._template_values(recipient_name, share_link, share_password, expiration_date)
        text_template_path, _ = self._template_paths(mail_type)
        return self._render_template(text_template_path, values, html_mode=False)

    def send_tenant_file_mail(
        self,
        to_address: object,
        person_id: object,
        mail_type: str,
        recipient_name: str,
        share_link: str,
        share_password: str,
        expiration_date: str,
    ) -> dict[str, object]:
        if not self.settings.preview_emails and not self.settings.send_emails:
            return {"sent": False, "prepared": False, "skipped": True, "reason": "disabled"}

        missing = self._missing_required_values(
            {
                "recipient_email": to_address,
                "recipient_name": recipient_name,
                "share_link": share_link,
                "share_password": share_password,
                "expiration_date": expiration_date,
            }
        )
        if missing:
            action = "preview" if self.settings.preview_emails else "sending"
            print(f"WARN Email {action} skipped: missing required value {missing}.")
            return {"sent": False, "prepared": False, "skipped": True, "reason": f"missing_{missing}"}

        values = self._template_values(recipient_name, share_link, share_password, expiration_date)
        text_template_path, html_template_path = self._template_paths(mail_type)
        text_body = self._render_template(text_template_path, values, html_mode=False)
        html_body = self._render_template(html_template_path, values, html_mode=True)

        return self.send_mail(
            to_address=to_address,
            person_id=person_id,
            mail_type=mail_type,
            subject=TENANT_FILE_SUBJECT,
            text_body=text_body,
            html_body=html_body,
            share_link=share_link,
            expiration_date=expiration_date,
            share_password_set=True,
        )

    def send_mail(
        self,
        to_address: object,
        person_id: object,
        mail_type: str,
        subject: str,
        text_body: str,
        html_body: str,
        share_link: str = "",
        expiration_date: str = "",
        share_password_set: bool = False,
    ) -> dict[str, object]:
        preview = {"to": str(to_address or ""), "subject": subject}
        if self.settings.preview_emails:
            if not share_link:
                print("WARN Email preview skipped: no share link available.")
                return {"sent": False, "prepared": False, "skipped": True, "reason": "missing_share_link"}
            if not share_password_set:
                print("WARN Email preview skipped: no share password available.")
                return {"sent": False, "prepared": False, "skipped": True, "reason": "missing_share_password"}
            safe_text_body, safe_html_body = self._preview_bodies(text_body, html_body)
            preview_body = self._preview_body(
                to_address=to_address,
                subject=subject,
                text_body=safe_text_body,
            )
            print(preview_body)
            preview_path = self._write_html_preview(person_id, mail_type, safe_html_body)
            print(f"MAIL PREVIEW HTML: {preview_path}")
            return {
                "sent": False,
                "prepared": True,
                "preview": True,
                "to": str(to_address or ""),
                "subject": subject,
                "share_link": share_link,
                "expiration_date": expiration_date,
            }
        if not self.settings.send_emails:
            return {"sent": False, "prepared": False, "skipped": True}
        if not share_link:
            print("WARN Email sending skipped: no share link available.")
            return {"sent": False, "prepared": False, "skipped": True, "reason": "missing_share_link"}
        if not share_password_set:
            print("WARN Email sending skipped: no share password available.")
            return {"sent": False, "prepared": False, "skipped": True, "reason": "missing_share_password"}
        if self.safety.dry_run or not self._has_smtp_config():
            safe_text_body, safe_html_body = self._preview_bodies(text_body, html_body)
            print(self._preview_body(to_address=to_address, subject=subject, text_body=safe_text_body))
            preview_path = self._write_html_preview(person_id, mail_type, safe_html_body)
            print(f"MAIL PREVIEW HTML: {preview_path}")
            return {"sent": False, "prepared": True, "to": str(to_address or ""), "subject": subject}

        message = EmailMessage()
        message["From"] = self.settings.mail_from
        message["To"] = str(to_address)
        message["Subject"] = subject
        message.set_content(text_body)
        message.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(self.settings.mail_smtp_host, self.settings.mail_smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if self.settings.mail_username:
                smtp.login(self.settings.mail_username, self.settings.mail_password)
            smtp.send_message(message)

        return {"sent": True, "prepared": False}

    def _template_values(
        self,
        recipient_name: str,
        share_link: str,
        share_password: str,
        expiration_date: str,
    ) -> dict[str, str]:
        return {
            "recipient_name": str(recipient_name),
            "share_link": str(share_link),
            "share_password": str(share_password),
            "expiration_date": str(expiration_date),
        }

    def _missing_required_values(self, values: dict[str, object]) -> str:
        for key, value in values.items():
            if not str(value or "").strip():
                return key
        return ""

    def _render_template(self, path: Path, values: dict[str, str], html_mode: bool) -> str:
        template = path.read_text(encoding="utf-8")
        rendered = template
        for key, value in values.items():
            replacement = escape(value, quote=True) if html_mode else value
            rendered = rendered.replace(f"{{{{ {key} }}}}", replacement)
        return rendered

    def _template_paths(self, mail_type: str) -> tuple[Path, Path]:
        try:
            return MAIL_TEMPLATES[mail_type]
        except KeyError as exc:
            raise ValueError(f"Unsupported mail type: {mail_type}") from exc

    def _preview_bodies(self, text_body: str, html_body: str) -> tuple[str, str]:
        if self.settings.use_dummy_values:
            return text_body, html_body
        return self._mask_password(text_body), self._mask_password(html_body)

    def _mask_password(self, body: str) -> str:
        masked = re.sub(r"(Web-Passwort:\n)[^\n]*", r"\1***", body)
        masked = re.sub(r"(Web password:\n)[^\n]*", r"\1***", masked)
        masked = re.sub(r"(Web-Passwort:<br>\s*)[^<\n]*", r"\1***", masked)
        return re.sub(r"(Web password:<br>\s*)[^<\n]*", r"\1***", masked)

    def _write_html_preview(self, person_id: object, mail_type: str, html_body: str) -> Path:
        PREVIEW_LOG_DIR.mkdir(exist_ok=True)
        safe_person_id = re.sub(r"[^A-Za-z0-9_-]+", "_", str(person_id or "unknown")).strip("_") or "unknown"
        safe_mail_type = re.sub(r"[^A-Za-z0-9_-]+", "_", mail_type).strip("_") or "mail"
        path = PREVIEW_LOG_DIR / f"mail_preview_{safe_person_id}_{safe_mail_type}.html"
        path.write_text(html_body, encoding="utf-8")
        return path

    def _preview_body(
        self,
        to_address: object,
        subject: str,
        text_body: str,
    ) -> str:
        return "\n".join(["MAIL PREVIEW PLAIN TEXT", f"To: {to_address or ''}", f"Subject: {subject}", "", text_body])

    def _has_smtp_config(self) -> bool:
        return bool(self.settings.mail_smtp_host and self.settings.mail_from)
