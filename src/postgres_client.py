from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from typing import Any

from .config import Settings

try:
    import psycopg
except ModuleNotFoundError:
    psycopg = None


SNAPSHOT_FIELDS = (
    "PERSVV_ID", "PERSON_ID", "NAME", "VORNAME", "EMAIL", "WEBPASSWORT",
    "WOHNHEIM_ID", "WOHNHEIM_SUCHNAME", "WOHNHEIM_NAME", "VO_ID",
    "VO_SUCHNAME", "ART", "BEGINN", "ENDE", "PERSPERSONENARTID",
    "VERTRAGSART_ID", "STATUS", "STATUSNAME",
)
SECRET_KEY_PARTS = ("PASSWORD", "PASSWORT")


def _value(record: dict[str, object], field: str) -> object:
    return record.get(field) if field in record else record.get(field.lower())


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def source_hash(record: dict[str, object]) -> str:
    payload = {field: _value(record, field) for field in SNAPSHOT_FIELDS}
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def sanitize_for_run_log(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): sanitize_for_run_log(item)
            for key, item in value.items()
            if not any(part in str(key).upper() for part in SECRET_KEY_PARTS)
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_for_run_log(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


class PostgresClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connection: Any = None

    def connect(self) -> None:
        if psycopg is None:
            raise RuntimeError(
                "Package 'psycopg' is not installed. Run 'pip install -r requirements.txt'."
            )
        try:
            self.connection = psycopg.connect(
                host=self.settings.postgres_host,
                port=self.settings.postgres_port,
                dbname=self.settings.postgres_db,
                user=self.settings.postgres_user,
                password=self.settings.postgres_password,
                sslmode=self.settings.postgres_sslmode,
            )
        except Exception as exc:
            message = str(exc)
            if self.settings.postgres_password:
                message = message.replace(self.settings.postgres_password, "***")
            raise RuntimeError(f"Postgres connection failed: {message}") from exc

    def upsert_oracle_snapshot(self, records: list[dict[str, object]]) -> None:
        sql = """
            insert into mieterakte_oracle_snapshot (
                persvv_id, person_id, name, vorname, email, webpasswort,
                wohnheim_id, wohnheim_suchname, wohnheim_name, vo_id, vo_suchname,
                art, beginn, ende, perspersonenartid, vertragsart_id, status,
                statusname, source_hash, raw_json, last_changed_at
            ) values (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, now()
            )
            on conflict (persvv_id) do update set
                person_id=excluded.person_id, name=excluded.name,
                vorname=excluded.vorname, email=excluded.email,
                webpasswort=excluded.webpasswort, wohnheim_id=excluded.wohnheim_id,
                wohnheim_suchname=excluded.wohnheim_suchname,
                wohnheim_name=excluded.wohnheim_name, vo_id=excluded.vo_id,
                vo_suchname=excluded.vo_suchname, art=excluded.art,
                beginn=excluded.beginn, ende=excluded.ende,
                perspersonenartid=excluded.perspersonenartid,
                vertragsart_id=excluded.vertragsart_id, status=excluded.status,
                statusname=excluded.statusname, raw_json=excluded.raw_json,
                last_seen_at=now(),
                last_changed_at=case
                    when mieterakte_oracle_snapshot.source_hash is distinct from excluded.source_hash
                    then now() else mieterakte_oracle_snapshot.last_changed_at end,
                source_hash=excluded.source_hash
        """
        with self._connection().cursor() as cursor:
            for record in records:
                values = [_value(record, field) for field in SNAPSHOT_FIELDS]
                cursor.execute(
                    sql,
                    (*values, source_hash(record), json.dumps(record, default=_json_default)),
                )
        self._connection().commit()

    def get_snapshot_records_for_processing(self) -> list[dict[str, object]]:
        with self._connection().cursor() as cursor:
            cursor.execute(
                "select raw_json from mieterakte_oracle_snapshot order by persvv_id"
            )
            rows = cursor.fetchall()
        return [
            raw_json if isinstance(raw_json, dict) else json.loads(raw_json)
            for (raw_json,) in rows
        ]

    def get_state(self, persvv_id: object) -> dict[str, object] | None:
        with self._connection().cursor() as cursor:
            cursor.execute(
                """
                select persvv_id, move_in_mail_sent_at, move_out_mail_sent_at,
                       share_id, share_link, share_expiration_date
                from mieterakte_state where persvv_id=%s
                """,
                (persvv_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [description.name for description in cursor.description]
        return dict(zip(columns, row))

    def upsert_state(
        self,
        persvv_id: object,
        person_id: object,
        vo_id: object = None,
        wohnheim_id: object = None,
        person_path: str = "",
        last_status: str = "ok",
        last_error: str | None = None,
        folder_created: bool = False,
    ) -> None:
        with self._connection().cursor() as cursor:
            cursor.execute(
                """
                insert into mieterakte_state (
                    persvv_id, person_id, vo_id, wohnheim_id, person_path,
                    folder_created_at, last_processed_at, last_status, last_error
                ) values (%s, %s, %s, %s, %s,
                    case when %s then now() else null end, now(), %s, %s)
                on conflict (persvv_id) do update set
                    person_id=excluded.person_id, vo_id=excluded.vo_id,
                    wohnheim_id=excluded.wohnheim_id, person_path=excluded.person_path,
                    folder_created_at=coalesce(
                        mieterakte_state.folder_created_at, excluded.folder_created_at),
                    last_seen_at=now(), last_processed_at=now(),
                    last_status=excluded.last_status, last_error=excluded.last_error,
                    updated_at=now()
                """,
                (
                    persvv_id, person_id, vo_id, wohnheim_id, person_path,
                    folder_created, last_status, last_error,
                ),
            )
        self._connection().commit()

    def mark_templates_copied(self, persvv_id: object) -> None:
        self._update_state_timestamp(persvv_id, "templates_copied_at")

    def mark_share(
        self,
        persvv_id: object,
        share_id: object,
        share_link: object,
        expiration_date: object,
    ) -> None:
        with self._connection().cursor() as cursor:
            cursor.execute(
                """
                update mieterakte_state set share_id=%s, share_link=%s,
                    share_expiration_date=%s, updated_at=now()
                where persvv_id=%s
                """,
                (share_id or None, share_link or None, expiration_date or None, persvv_id),
            )
        self._connection().commit()

    def mark_mail_sent(self, persvv_id: object, mail_type: str) -> None:
        columns = {
            "move_in": "move_in_mail_sent_at",
            "move_out": "move_out_mail_sent_at",
        }
        try:
            column = columns[mail_type]
        except KeyError as exc:
            raise ValueError(f"Unsupported mail type: {mail_type}") from exc
        self._update_state_timestamp(persvv_id, column)

    def insert_run_log_start(self, run_id: object) -> None:
        with self._connection().cursor() as cursor:
            cursor.execute(
                """
                insert into mieterakte_run_log (
                    run_id, dry_run, create_folders, create_shares, send_emails,
                    preview_emails, use_postgres, process_from_postgres
                ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id, self.settings.dry_run, self.settings.create_folders,
                    self.settings.create_shares, self.settings.send_emails,
                    self.settings.preview_emails, self.settings.use_postgres,
                    self.settings.process_from_postgres,
                ),
            )
        self._connection().commit()

    def update_run_log_finish(
        self,
        run_id: object,
        oracle_records_read: int,
        records_processed: int,
        stats: dict[str, object],
        result: dict[str, object],
    ) -> None:
        fields = (
            "folders_created", "folders_skipped_existing", "shares_created",
            "shares_updated", "shares_skipped", "mails_prepared_or_sent",
            "mail_previews_created", "template_files_copied",
            "template_files_skipped", "template_copy_errors", "warnings", "errors",
        )
        values = [int(stats.get(field, 0)) for field in fields]
        safe_result = sanitize_for_run_log(result)
        with self._connection().cursor() as cursor:
            cursor.execute(
                """
                update mieterakte_run_log set finished_at=now(),
                    oracle_records_read=%s, records_processed=%s,
                    folders_created=%s, folders_skipped_existing=%s,
                    shares_created=%s, shares_updated=%s, shares_skipped=%s,
                    mails_prepared_or_sent=%s, mail_previews_created=%s,
                    template_files_copied=%s, template_files_skipped=%s,
                    template_copy_errors=%s, warnings=%s, errors=%s,
                    result_json=%s::jsonb
                where run_id=%s
                """,
                (
                    oracle_records_read, records_processed, *values,
                    json.dumps(safe_result, default=_json_default), run_id,
                ),
            )
        self._connection().commit()

    def _update_state_timestamp(self, persvv_id: object, column: str) -> None:
        allowed = {
            "templates_copied_at", "move_in_mail_sent_at", "move_out_mail_sent_at"
        }
        if column not in allowed:
            raise ValueError(f"Unsupported state timestamp: {column}")
        with self._connection().cursor() as cursor:
            cursor.execute(
                f"update mieterakte_state set {column}=now(), updated_at=now() "
                "where persvv_id=%s",
                (persvv_id,),
            )
        self._connection().commit()

    def _connection(self) -> Any:
        if self.connection is None:
            raise RuntimeError("Postgres is not connected.")
        return self.connection
