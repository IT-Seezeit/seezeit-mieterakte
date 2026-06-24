from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Settings

try:
    import oracledb
except ModuleNotFoundError:
    oracledb = None


class OracleClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch_mieter(self) -> list[dict[str, object]]:
        sql_path = Path(__file__).resolve().parents[1] / "sql" / "oracle_mieter_select.sql"
        query = sql_path.read_text(encoding="utf-8")

        if not self._has_oracle_config():
            print("WARN Oracle config is incomplete; using one local dummy record.")
            return [self._dummy_record(query)]

        if oracledb is None:
            raise RuntimeError("Package 'oracledb' is not installed. Run 'pip install -r requirements.txt'.")

        dsn = oracledb.makedsn(
            self.settings.oracle_host,
            self.settings.oracle_port,
            service_name=self.settings.oracle_service_name,
        )

        with oracledb.connect(
            user=self.settings.oracle_user,
            password=self.settings.oracle_password,
            dsn=dsn,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)
                columns = [col[0].upper() for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def _has_oracle_config(self) -> bool:
        return all(
            [
                self.settings.oracle_host,
                self.settings.oracle_service_name,
                self.settings.oracle_user,
                self.settings.oracle_password,
            ]
        )

    def _dummy_record(self, query: str) -> dict[str, Any]:
        return {
            "PERSVV_ID": "dummy-pvv-1",
            "PERSON_ID": "173884",
            "NAME": "Weber",
            "VORNAME": "Michael",
            "EMAIL": "dummy@example.invalid",
            "WEBPASSWORT": "dummy-passwort",
            "WOHNHEIM_ID": "810",
            "WOHNHEIM_SUCHNAME": "810",
            "WOHNHEIM_NAME": "Sonnenbuehl West I",
            "VO_ID": "dummy-vo-1",
            "VO_SUCHNAME": "810-83-F2-79-0",
            "ART": "",
            "BEGINN": None,
            "ENDE": None,
            "PERSPERSONENARTID": None,
            "VERTRAGSART_ID": None,
            "STATUS": 2,
            "STATUSNAME": "Aktiv",
            "QUERY_LOADED": bool(query.strip()),
        }
