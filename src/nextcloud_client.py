from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import quote

from .config import Settings
from .safety import Safety

try:
    import requests
except ModuleNotFoundError:
    requests = None


class NextcloudClient:
    def __init__(self, settings: Settings, safety: Safety) -> None:
        self.settings = settings
        self.safety = safety

    def ensure_folder(self, path: str) -> dict[str, object]:
        if self.safety.dry_run or not self.settings.create_folders:
            return {"path": path, "created": False, "dry_run": True}

        self._require_requests()
        response = requests.request(
            "MKCOL",
            self._webdav_url(path),
            auth=(self.settings.nextcloud_username, self.settings.nextcloud_app_password),
            timeout=30,
        )
        if response.status_code == 201:
            return {"path": path, "created": True, "skipped_existing": False}
        if response.status_code == 405:
            return {"path": path, "created": False, "skipped_existing": True}
        response.raise_for_status()
        return {"path": path, "created": False, "skipped_existing": False}

    def create_share(self, path: str, password: object, end_date: object) -> dict[str, object]:
        if not self.settings.create_shares:
            return {"path": path, "created": False, "skipped": True, "reason": "disabled"}
        if self.safety.dry_run:
            return {"path": path, "created": False, "dry_run": True}
        if not password:
            print(f"WARN No WebPasswort for {path}; skipping share.")
            return {"path": path, "created": False, "skipped": True, "reason": "missing_password"}

        self._require_requests()
        expire_date = self._expire_date(end_date)
        response = requests.post(
            self._ocs_url(),
            auth=(self.settings.nextcloud_username, self.settings.nextcloud_app_password),
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            data={
                "path": path,
                "shareType": 3,
                "permissions": 1,
                "password": str(password),
                "expireDate": expire_date,
            },
            timeout=30,
        )
        response.raise_for_status()
        return {"path": path, "created": True, "expire_date": expire_date}

    def _webdav_url(self, path: str) -> str:
        base_url = self.settings.nextcloud_base_url.rstrip("/")
        username = quote(self.settings.nextcloud_username.strip("/"))
        encoded_path = "/".join(quote(part) for part in path.strip("/").split("/"))
        return f"{base_url}/remote.php/dav/files/{username}/{encoded_path}"

    def _ocs_url(self) -> str:
        return f"{self.settings.nextcloud_base_url.rstrip('/')}/ocs/v2.php/apps/files_sharing/api/v1/shares"

    def _expire_date(self, value: object) -> str:
        if isinstance(value, datetime):
            end = value.date()
        elif isinstance(value, date):
            end = value
        elif value:
            end = datetime.fromisoformat(str(value)[:10]).date()
        else:
            end = date.today()
        return (end + timedelta(days=30)).isoformat()

    def _require_requests(self) -> None:
        if requests is None:
            raise RuntimeError("Package 'requests' is not installed. Run 'pip install -r requirements.txt'.")
