from __future__ import annotations

from datetime import date, datetime, timedelta
from urllib.parse import quote
from xml.etree import ElementTree

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
        if response.status_code == 409:
            if self.folder_exists(path):
                print(f"folder exists after conflict, skipped: {path}")
                return {"path": path, "created": False, "skipped_existing": True}
            print(f"ERROR WebDAV MKCOL conflict for {path}. Response body: {response.text}")
        response.raise_for_status()
        return {"path": path, "created": False, "skipped_existing": False}

    def folder_exists(self, path: str) -> bool:
        self._require_requests()
        response = requests.request(
            "PROPFIND",
            self._webdav_url(path),
            auth=(self.settings.nextcloud_username, self.settings.nextcloud_app_password),
            headers={"Depth": "0"},
            timeout=30,
        )
        if response.status_code in {200, 207}:
            return True
        if response.status_code == 404:
            return False
        print(f"WARN WebDAV PROPFIND failed for {path}. HTTP status code: {response.status_code}")
        print(f"Response body: {response.text}")
        return False

    def create_share(
        self,
        path: str,
        password: object,
        end_date: object,
        expiration_date: str | None = None,
    ) -> dict[str, object]:
        if not self.settings.create_shares:
            return {"path": path, "created": False, "skipped": True, "reason": "disabled"}
        if self.safety.dry_run:
            return {"path": path, "created": False, "dry_run": True}

        self._require_requests()
        expire_date = expiration_date or self._expire_date(end_date)
        share_type = 3
        permissions = 1
        existing_shares = self._list_matching_public_shares(path)
        if existing_shares:
            if len(existing_shares) > 1:
                print(f"WARN Found {len(existing_shares)} existing public link shares for {path}.")
            selected_share = self._select_share(existing_shares)
            share_id = str(selected_share.get("id", ""))
            share_link = self._share_url(selected_share)
            existing_expire_date = self._normalize_expire_date(
                selected_share.get("expiration")
                or selected_share.get("expiration_date")
                or selected_share.get("expireDate")
            )
            if existing_expire_date == expire_date:
                print(f"Share skipped unchanged: path={path} share_id={share_id} expire_date={expire_date}")
                return {
                    "path": path,
                    "created": False,
                    "updated": False,
                    "skipped": True,
                    "reason": "unchanged",
                    "share_id": share_id,
                    "share_link": share_link,
                    "expire_date": expire_date,
                    "warning": len(existing_shares) > 1,
                }

            response = requests.put(
                f"{self._ocs_url()}/{quote(share_id)}",
                auth=(self.settings.nextcloud_username, self.settings.nextcloud_app_password),
                headers={"OCS-APIRequest": "true", "Accept": "application/json"},
                data={"expireDate": expire_date},
                timeout=30,
            )
            if not response.ok:
                self._log_share_api_error(
                    response=response,
                    path=path,
                    share_type=share_type,
                    permissions=permissions,
                    expire_date=expire_date,
                    password_set=bool(password),
                    action="update expiration",
                    share_id=share_id,
                )
            response.raise_for_status()
            print(f"Share updated expiration: path={path} share_id={share_id} expire_date={expire_date}")
            return {
                "path": path,
                "created": False,
                "updated": True,
                "skipped": False,
                "share_id": share_id,
                "share_link": share_link,
                "expire_date": expire_date,
                "warning": len(existing_shares) > 1,
            }

        if not password:
            print(f"WARN No WebPasswort for {path}; skipping share creation.")
            return {"path": path, "created": False, "skipped": True, "reason": "missing_password"}

        response = requests.post(
            self._ocs_url(),
            auth=(self.settings.nextcloud_username, self.settings.nextcloud_app_password),
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            data={
                "path": path,
                "shareType": share_type,
                "permissions": permissions,
                "password": str(password),
                "expireDate": expire_date,
            },
            timeout=30,
        )
        if not response.ok:
            self._log_share_api_error(
                response=response,
                path=path,
                share_type=share_type,
                permissions=permissions,
                expire_date=expire_date,
                password_set=bool(password),
                action="create",
            )
        response.raise_for_status()
        share_data = self._extract_ocs_data(response)
        share_link = self._share_url(share_data) if isinstance(share_data, dict) else ""
        print(f"Share created: path={path} expire_date={expire_date}")
        return {"path": path, "created": True, "expire_date": expire_date, "share_link": share_link}

    def _webdav_url(self, path: str) -> str:
        base_url = self.settings.nextcloud_base_url.rstrip("/")
        username = quote(self.settings.nextcloud_username.strip("/"))
        encoded_path = "/".join(quote(part) for part in path.strip("/").split("/"))
        return f"{base_url}/remote.php/dav/files/{username}/{encoded_path}"

    def _ocs_url(self) -> str:
        return f"{self.settings.nextcloud_base_url.rstrip('/')}/ocs/v2.php/apps/files_sharing/api/v1/shares"

    def _list_matching_public_shares(self, path: str) -> list[dict[str, object]]:
        response = requests.get(
            self._ocs_url(),
            auth=(self.settings.nextcloud_username, self.settings.nextcloud_app_password),
            headers={"OCS-APIRequest": "true", "Accept": "application/json"},
            params={"path": path, "reshares": "false"},
            timeout=30,
        )
        if not response.ok:
            self._log_share_api_error(
                response=response,
                path=path,
                share_type=3,
                permissions=1,
                expire_date="",
                password_set=False,
                action="list",
            )
        response.raise_for_status()

        shares = self._extract_ocs_data(response)
        if isinstance(shares, dict):
            shares = [shares]
        if not isinstance(shares, list):
            return []

        return [
            share for share in shares
            if isinstance(share, dict)
            and str(share.get("share_type")) == "3"
            and self._same_share_path(str(share.get("path", "")), path)
        ]

    def _select_share(self, shares: list[dict[str, object]]) -> dict[str, object]:
        def sort_key(share: dict[str, object]) -> tuple[int, int, int, str]:
            owner = str(share.get("uid_owner") or share.get("uid_file_owner") or "")
            owner_rank = 0 if owner == self.settings.nextcloud_username else 1
            share_id = share.get("id", "")
            try:
                return (owner_rank, 0, int(str(share_id)), "")
            except ValueError:
                return (owner_rank, 1, 0, str(share_id))

        return sorted(shares, key=sort_key)[0]

    def _same_share_path(self, actual_path: str, expected_path: str) -> bool:
        return actual_path.strip("/") == expected_path.strip("/")

    def _share_url(self, share: object) -> str:
        if not isinstance(share, dict):
            return ""
        return str(share.get("url") or share.get("share_url") or "")

    def _extract_ocs_data(self, response: object) -> object:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            return payload.get("ocs", {}).get("data", [])

        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError:
            return []

        data = None
        for element in root.iter():
            if element.tag.lower().endswith("data"):
                data = element
                break
        if data is None:
            return []

        shares = []
        for child in list(data):
            if not list(child):
                continue
            share = {}
            for field in list(child):
                key = field.tag.split("}", 1)[-1]
                share[key] = field.text or ""
            if share:
                shares.append(share)
        return shares

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

    def _normalize_expire_date(self, value: object) -> str:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if not value:
            return ""

        text = str(value).strip()
        if not text:
            return ""
        for candidate in (text[:10], text):
            try:
                return datetime.fromisoformat(candidate).date().isoformat()
            except ValueError:
                pass
        for fmt in ("%d.%m.%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                pass
        return text

    def _log_share_api_error(
        self,
        response: object,
        path: str,
        share_type: int,
        permissions: int,
        expire_date: str,
        password_set: bool,
        action: str,
        share_id: str = "",
    ) -> None:
        print("ERROR Nextcloud share API request failed.")
        print(f"Share API action: {action}")
        print(f"Share path: {path}")
        if share_id:
            print(f"Share ID: {share_id}")
        print(f"Share type: {share_type}")
        print(f"Permissions: {permissions}")
        print(f"Expiration date: {expire_date}")
        print(f"Password set: {password_set}")
        print(f"HTTP status code: {response.status_code}")
        print(f"Response body: {response.text}")

        ocs_message = self._extract_ocs_meta_message(response)
        if ocs_message:
            print(f"OCS meta message: {ocs_message}")

    def _extract_ocs_meta_message(self, response: object) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            meta = payload.get("ocs", {}).get("meta", {})
            message = meta.get("message")
            if message:
                return str(message)

        try:
            root = ElementTree.fromstring(response.text)
        except ElementTree.ParseError:
            return ""

        for element in root.iter():
            if element.tag.lower().endswith("message") and element.text:
                return element.text
        return ""

    def _require_requests(self) -> None:
        if requests is None:
            raise RuntimeError("Package 'requests' is not installed. Run 'pip install -r requirements.txt'.")
