from __future__ import annotations

import os
from dataclasses import dataclass

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


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        dry_run=_bool_env("DRY_RUN", True),
        create_folders=_bool_env("CREATE_FOLDERS", False),
        create_shares=_bool_env("CREATE_SHARES", False),
        send_emails=_bool_env("SEND_EMAILS", False),
        only_dummy_person=_bool_env("ONLY_DUMMY_PERSON", True),
        dummy_person_id=os.getenv("DUMMY_PERSON_ID", "173884"),
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
