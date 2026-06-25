from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv() -> bool:
        return False


@dataclass(frozen=True)
class Settings:
    dry_run: bool
    create_folders: bool
    create_shares: bool
    send_emails: bool
    only_dummy_person: bool
    dummy_person_id: str
    dummy_person_ids: tuple[str, ...]
    use_dummy_values: bool
    dummy_share_password: str
    dummy_share_expiration_date: str
    dummy_email_to: str
    dummy_email_name: str
    nextcloud_base_url: str
    nextcloud_username: str
    nextcloud_app_password: str
    nextcloud_teamfolder_path: str
    nextcloud_teamfolder_id: str
    oracle_host: str
    oracle_port: int
    oracle_service_name: str
    oracle_user: str
    oracle_password: str
    mail_smtp_host: str
    mail_smtp_port: int
    mail_username: str
    mail_password: str
    mail_from: str

    @property
    def effective_dummy_person_ids(self) -> tuple[str, ...]:
        if self.dummy_person_ids:
            return self.dummy_person_ids
        if self.dummy_person_id:
            return (self.dummy_person_id,)
        return ()

    @property
    def dummy_share_expiration_date_is_valid(self) -> bool:
        if not self.dummy_share_expiration_date:
            return False
        try:
            parsed = datetime.strptime(self.dummy_share_expiration_date, "%Y-%m-%d")
        except ValueError:
            return False
        return parsed.strftime("%Y-%m-%d") == self.dummy_share_expiration_date


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _validate_person_id(value: str, env_name: str) -> str:
    person_id = value.strip()
    if not person_id:
        return ""
    if not person_id.isdigit():
        raise ValueError(f"{env_name} contains invalid Person-ID {value!r}. Only digits are allowed.")
    return person_id


def _parse_dummy_person_ids(value: str) -> tuple[str, ...]:
    raw_value = value.strip()
    if not raw_value:
        return ()

    ids = []
    for part in raw_value.split(","):
        person_id = part.strip()
        if not person_id:
            raise ValueError("DUMMY_PERSON_IDS contains an empty value. Use comma-separated numeric IDs.")
        ids.append(_validate_person_id(person_id, "DUMMY_PERSON_IDS"))
    return tuple(ids)


def load_settings() -> Settings:
    load_dotenv()
    dummy_person_id = _validate_person_id(os.getenv("DUMMY_PERSON_ID", ""), "DUMMY_PERSON_ID")
    dummy_person_ids = _parse_dummy_person_ids(os.getenv("DUMMY_PERSON_IDS", ""))

    return Settings(
        dry_run=_bool_env("DRY_RUN", True),
        create_folders=_bool_env("CREATE_FOLDERS", False),
        create_shares=_bool_env("CREATE_SHARES", False),
        send_emails=_bool_env("SEND_EMAILS", False),
        only_dummy_person=_bool_env("ONLY_DUMMY_PERSON", True),
        dummy_person_id=dummy_person_id,
        dummy_person_ids=dummy_person_ids,
        use_dummy_values=_bool_env("USE_DUMMY_VALUES", False),
        dummy_share_password=os.getenv("DUMMY_SHARE_PASSWORD", "").strip(),
        dummy_share_expiration_date=os.getenv("DUMMY_SHARE_EXPIRATION_DATE", "").strip(),
        dummy_email_to=os.getenv("DUMMY_EMAIL_TO", "").strip(),
        dummy_email_name=os.getenv("DUMMY_EMAIL_NAME", "").strip(),
        nextcloud_base_url=os.getenv("NEXTCLOUD_BASE_URL", ""),
        nextcloud_username=os.getenv("NEXTCLOUD_USERNAME", ""),
        nextcloud_app_password=os.getenv("NEXTCLOUD_APP_PASSWORD", ""),
        nextcloud_teamfolder_path=os.getenv(
            "NEXTCLOUD_TEAMFOLDER_PATH",
            "1000_Leistungsabteilungen/1100_SW/1160_SW_Mieterakten",
        ),
        nextcloud_teamfolder_id=os.getenv("NEXTCLOUD_TEAMFOLDER_ID", ""),
        oracle_host=os.getenv("ORACLE_HOST", ""),
        oracle_port=int(os.getenv("ORACLE_PORT", "1521")),
        oracle_service_name=os.getenv("ORACLE_SERVICE_NAME", ""),
        oracle_user=os.getenv("ORACLE_USER", ""),
        oracle_password=os.getenv("ORACLE_PASSWORD", ""),
        mail_smtp_host=os.getenv("MAIL_SMTP_HOST", ""),
        mail_smtp_port=int(os.getenv("MAIL_SMTP_PORT", "587")),
        mail_username=os.getenv("MAIL_USERNAME", ""),
        mail_password=os.getenv("MAIL_PASSWORD", ""),
        mail_from=os.getenv("MAIL_FROM", ""),
    )
