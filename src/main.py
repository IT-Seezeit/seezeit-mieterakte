from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from .config import Settings, load_settings
from .mailer import Mailer
from .nextcloud_client import NextcloudClient
from .oracle_client import OracleClient
from .path_builder import build_initial_template_names, build_target_paths
from .postgres_client import PostgresClient
from .safety import Safety


TEST_CANDIDATE_FIELDS = [
    ("PERSON_ID", "PERSON_ID"),
    ("Vorname", "VORNAME"),
    ("Name", "NAME"),
    ("EMail", "EMAIL"),
    ("Wohnheim_Suchname", "WOHNHEIM_SUCHNAME"),
    ("Wohnheim_Name", "WOHNHEIM_NAME"),
    ("VO_Suchname", "VO_SUCHNAME"),
    ("Beginn", "BEGINN"),
    ("Ende", "ENDE"),
    ("StatusName", "STATUSNAME"),
]


def _value(row: dict[str, object], key: str) -> object:
    return row.get(key) or row.get(key.lower()) or ""


def _log_test_candidates(rows: list[dict[str, object]], limit: int = 10) -> None:
    candidates = rows[:limit]
    print(f"DRY-RUN possible test candidates, max {limit}: {len(candidates)} shown")
    for index, row in enumerate(candidates, start=1):
        values = [
            f"{label}={_value(row, key)}"
            for label, key in TEST_CANDIDATE_FIELDS
        ]
        print(f"Candidate {index}: " + " | ".join(values))


def _log_dummy_values(settings: Settings) -> None:
    print("Dummy values active: true")
    print(f"Dummy share password set: {bool(settings.dummy_share_password)}")
    if settings.dummy_share_expiration_date:
        print(f"Dummy share expiration date: {settings.dummy_share_expiration_date}")
    if settings.dummy_email_to and not settings.send_emails:
        print(f"Dummy email recipient: {settings.dummy_email_to}")


def _safe_error_text(exc: Exception, settings: Settings) -> str:
    text = str(exc)
    secrets = (
        settings.oracle_password,
        settings.nextcloud_app_password,
        settings.mail_password,
        settings.postgres_password,
        settings.dummy_share_password,
    )
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def _recipient_name(row: dict[str, object], settings: Settings) -> str:
    if settings.use_dummy_values and settings.dummy_email_name:
        return settings.dummy_email_name
    vorname = str(row.get("VORNAME") or row.get("vorname") or "").strip()
    name = str(row.get("NAME") or row.get("name") or "").strip()
    return " ".join(part for part in (vorname, name) if part).strip() or "Mieter/in"


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            pass
    for fmt in ("%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _in_send_window(today: date, target_date: date | None, window_days: int) -> bool:
    if target_date is None:
        return False
    return target_date - timedelta(days=window_days) <= today <= target_date


def _folder_or_share_created(folder_results: list[dict[str, object]], share_result: dict[str, object]) -> bool:
    return any(result.get("created") for result in folder_results) or bool(share_result.get("created"))


def _due_mail_types(
    row: dict[str, object],
    settings: Settings,
    folder_results: list[dict[str, object]],
    share_result: dict[str, object],
) -> list[str]:
    today = date.today()
    beginn = _parse_date(row.get("BEGINN") or row.get("beginn"))
    ende = _parse_date(row.get("ENDE") or row.get("ende"))
    window_days = settings.mail_send_window_days

    move_in_due = _in_send_window(today, beginn, window_days)
    if (
        not move_in_due
        and settings.allow_short_notice_move_in
        and beginn is not None
        and today >= beginn
        and _folder_or_share_created(folder_results, share_result)
    ):
        move_in_due = True

    move_out_due = _in_send_window(today, ende, window_days)

    if settings.mail_type == "move_in":
        return ["move_in"] if move_in_due else []
    if settings.mail_type == "move_out":
        return ["move_out"] if move_out_due else []

    due = []
    if move_in_due:
        due.append("move_in")
    if move_out_due:
        due.append("move_out")
    return due


def run() -> dict[str, object]:
    settings = load_settings()
    safety = Safety(settings)
    safety.validate()
    postgres = None
    run_id = None
    if settings.use_postgres:
        postgres = PostgresClient(settings)
        postgres.connect()
        run_id = uuid4()
        postgres.insert_run_log_start(run_id)
        print(f"Postgres persistence active: true, run_id={run_id}")
    print(f"Copy initial templates active: {settings.copy_initial_templates}")
    if settings.copy_initial_templates:
        print(f"Nextcloud template folder: {settings.nextcloud_template_folder_path}")
        if not settings.create_folders:
            print("WARN Initial templates skipped: reason=create_folders_disabled")
    if settings.use_dummy_values:
        _log_dummy_values(settings)

    oracle = OracleClient(settings)
    nextcloud = NextcloudClient(settings, safety)
    mailer = Mailer(settings, safety)

    rows = oracle.fetch_mieter()
    oracle_rows = list(rows)
    print(f"Oracle records read: {len(rows)}")
    if postgres is not None:
        postgres.upsert_oracle_snapshot(rows)
        print(f"Oracle snapshot records upserted: {len(rows)}")
        if settings.process_from_postgres:
            rows = postgres.get_snapshot_records_for_processing()
            print(f"Records loaded from Postgres snapshot: {len(rows)}")

    if settings.only_dummy_person:
        dummy_person_ids = set(settings.effective_dummy_person_ids)
        rows = [
            row for row in rows
            if str(row.get("PERSON_ID") or row.get("person_id")) in dummy_person_ids
        ]
    print(f"Records after dummy filter: {len(rows)}")
    if settings.dry_run and settings.only_dummy_person and not rows:
        _log_test_candidates(oracle_rows)

    stats = {
        "target_paths": 0,
        "folders_created": 0,
        "folders_skipped_existing": 0,
        "template_files_copied": 0,
        "template_files_skipped": 0,
        "template_copy_errors": 0,
        "shares_created": 0,
        "shares_updated": 0,
        "shares_skipped": 0,
        "mails_prepared_or_sent": 0,
        "mail_previews_created": 0,
        "warnings": 0,
        "errors": 0,
    }
    results = []
    mailed_keys = set()

    for row in rows:
        persvv_id = row.get("PERSVV_ID") or row.get("persvv_id")
        person_id = row.get("PERSON_ID") or row.get("person_id")
        try:
            paths = build_target_paths(settings.nextcloud_teamfolder_path, row)
            stats["target_paths"] += 1
            print(f"Target person folder: {paths.person_path}")

            folder_results = []
            for folder in paths.folders:
                result = nextcloud.ensure_folder(folder)
                folder_results.append(result)
                if result.get("created"):
                    stats["folders_created"] += 1
                if result.get("skipped_existing"):
                    stats["folders_skipped_existing"] += 1
                if result.get("dry_run"):
                    print(f"DRY-RUN folder: {folder}")

            person_folder_result = folder_results[-1]
            template_result = {
                "copied": 0,
                "skipped": 0,
                "errors": 0,
                "reason": "disabled",
            }
            template_names = (
                build_initial_template_names(row)
                if settings.copy_initial_templates
                else {}
            )
            if settings.copy_initial_templates and settings.create_folders:
                if person_folder_result.get("created") or person_folder_result.get("dry_run"):
                    template_result = nextcloud.copy_initial_templates(
                        settings.nextcloud_template_folder_path,
                        paths.person_path,
                        template_names,
                    )
                    print(
                        f"Initial templates for {paths.person_path}: "
                        f"copied={template_result['copied']} "
                        f"skipped={template_result['skipped']} "
                        f"errors={template_result['errors']}"
                    )
                else:
                    template_result["reason"] = "person_folder_not_created"
                    template_result["skipped"] = len(template_names)
                    print(
                        f"Initial templates skipped for {paths.person_path}: "
                        "reason=person_folder_not_created"
                    )
            elif settings.copy_initial_templates:
                template_result["reason"] = "create_folders_disabled"
                template_result["skipped"] = len(template_names)

            stats["template_files_copied"] += int(template_result["copied"])
            stats["template_files_skipped"] += int(template_result["skipped"])
            stats["template_copy_errors"] += int(template_result["errors"])
            if template_result["errors"]:
                stats["errors"] += 1

            share_password = row.get("WEBPASSWORT") or row.get("webpasswort")
            share_expiration_date = None
            if settings.use_dummy_values:
                share_password = settings.dummy_share_password
                share_expiration_date = settings.dummy_share_expiration_date

            share_result = nextcloud.create_share(
                paths.person_path,
                share_password,
                row.get("ENDE") or row.get("ende"),
                expiration_date=share_expiration_date,
            )
            if share_result.get("created"):
                stats["shares_created"] += 1
            if share_result.get("updated"):
                stats["shares_updated"] += 1
            if share_result.get("skipped") or share_result.get("dry_run"):
                stats["shares_skipped"] += 1
            if share_result.get("warning"):
                stats["warnings"] += 1

            mail_to = row.get("EMAIL") or row.get("email")
            if settings.use_dummy_values and settings.dummy_email_to:
                mail_to = settings.dummy_email_to
            share_link = str(share_result.get("share_link") or "")
            expiration_date = str(share_result.get("expire_date") or share_expiration_date or "")

            postgres_state = postgres.get_state(persvv_id) if postgres is not None else None
            due_mail_types = _due_mail_types(row, settings, folder_results, share_result)
            mail_results = []
            sent_mail_types = []

            if not due_mail_types:
                print(f"mail skipped, reason=not_due person_id={person_id}")
                mail_results.append({"sent": False, "prepared": False, "skipped": True, "reason": "not_due"})

            for mail_type in due_mail_types:
                sent_field = f"{mail_type}_mail_sent_at"
                if (
                    postgres_state
                    and settings.send_emails
                    and not settings.preview_emails
                    and postgres_state.get(sent_field)
                ):
                    print(
                        f"mail skipped, reason=already_sent person_id={person_id} "
                        f"mail_type={mail_type}"
                    )
                    mail_results.append(
                        {
                            "sent": False,
                            "prepared": False,
                            "skipped": True,
                            "reason": "already_sent",
                            "mail_type": mail_type,
                        }
                    )
                    continue
                mail_key = (str(person_id), mail_type)
                if mail_key in mailed_keys:
                    print(f"mail skipped, reason=duplicate_in_run person_id={person_id} mail_type={mail_type}")
                    mail_results.append(
                        {"sent": False, "prepared": False, "skipped": True, "reason": "duplicate_in_run"}
                    )
                    continue
                mailed_keys.add(mail_key)

                mail_result = mailer.send_tenant_file_mail(
                    mail_to,
                    person_id=person_id,
                    mail_type=mail_type,
                    recipient_name=_recipient_name(row, settings),
                    share_link=share_link,
                    share_password=str(share_password or ""),
                    expiration_date=expiration_date,
                )
                mail_result["mail_type"] = mail_type
                mail_results.append(mail_result)

                if settings.use_dummy_values and settings.dummy_email_to and mail_result.get("prepared"):
                    print(f"Dummy email recipient: {settings.dummy_email_to}")
                if mail_result.get("prepared") or mail_result.get("sent"):
                    stats["mails_prepared_or_sent"] += 1
                if mail_result.get("preview"):
                    stats["mail_previews_created"] += 1
                if mail_result.get("sent"):
                    sent_mail_types.append(mail_type)
                if str(mail_result.get("reason", "")).startswith("missing_"):
                    stats["warnings"] += 1

            if postgres is not None:
                postgres.upsert_state(
                    persvv_id=persvv_id,
                    person_id=person_id,
                    vo_id=row.get("VO_ID") or row.get("vo_id"),
                    wohnheim_id=row.get("WOHNHEIM_ID") or row.get("wohnheim_id"),
                    person_path=paths.person_path,
                    last_status="ok",
                    last_error=None,
                    folder_created=bool(person_folder_result.get("created")),
                )
                if template_result.get("copied"):
                    postgres.mark_templates_copied(persvv_id)
                if (
                    share_result.get("share_id")
                    or share_result.get("share_link")
                    or share_result.get("expire_date")
                ):
                    postgres.mark_share(
                        persvv_id,
                        share_result.get("share_id"),
                        share_result.get("share_link"),
                        share_result.get("expire_date"),
                    )
                for sent_mail_type in sent_mail_types:
                    postgres.mark_mail_sent(persvv_id, sent_mail_type)

            results.append(
                {
                    "person_id": row.get("PERSON_ID") or row.get("person_id"),
                    "person_path": paths.person_path,
                    "folders": folder_results,
                    "templates": template_result,
                    "share": share_result,
                    "mail": mail_results,
                }
            )
        except Exception as exc:
            stats["errors"] += 1
            safe_error = _safe_error_text(exc, settings)
            print(f"ERROR Failed to process record {person_id}: {safe_error}")
            if postgres is not None:
                postgres.upsert_state(
                    persvv_id=persvv_id,
                    person_id=person_id,
                    vo_id=row.get("VO_ID") or row.get("vo_id"),
                    wohnheim_id=row.get("WOHNHEIM_ID") or row.get("wohnheim_id"),
                    last_status="error",
                    last_error=safe_error,
                )

    print(f"Target paths calculated: {stats['target_paths']}")
    print(f"Folders created: {stats['folders_created']}")
    print(f"Existing folders skipped: {stats['folders_skipped_existing']}")
    print(f"Template files copied: {stats['template_files_copied']}")
    print(f"Template files skipped: {stats['template_files_skipped']}")
    print(f"Template copy errors: {stats['template_copy_errors']}")
    print(f"Shares created: {stats['shares_created']}")
    print(f"Shares updated: {stats['shares_updated']}")
    print(f"Shares skipped: {stats['shares_skipped']}")
    print(f"Mails prepared/sent: {stats['mails_prepared_or_sent']}")
    print(f"Mail previews created: {stats['mail_previews_created']}")
    print(f"Warnings: {stats['warnings']}")
    print(f"Errors: {stats['errors']}")

    result = {
        "safety": safety.describe(),
        "processed": len(rows),
        "stats": stats,
        "results": results,
    }
    if postgres is not None:
        postgres.update_run_log_finish(
            run_id=run_id,
            oracle_records_read=len(oracle_rows),
            records_processed=len(rows),
            stats=stats,
            result=result,
        )
    return result


def main() -> None:
    result = run()
    print(result)


if __name__ == "__main__":
    main()
