from __future__ import annotations

from .config import Settings, load_settings
from .mailer import Mailer
from .nextcloud_client import NextcloudClient
from .oracle_client import OracleClient
from .path_builder import build_target_paths
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


def _recipient_name(row: dict[str, object], settings: Settings) -> str:
    if settings.use_dummy_values and settings.dummy_email_name:
        return settings.dummy_email_name
    vorname = str(row.get("VORNAME") or row.get("vorname") or "").strip()
    name = str(row.get("NAME") or row.get("name") or "").strip()
    return " ".join(part for part in (vorname, name) if part).strip() or "Mieter/in"


def run() -> dict[str, object]:
    settings = load_settings()
    safety = Safety(settings)
    safety.validate()
    if settings.use_dummy_values:
        _log_dummy_values(settings)

    oracle = OracleClient(settings)
    nextcloud = NextcloudClient(settings, safety)
    mailer = Mailer(settings, safety)

    rows = oracle.fetch_mieter()
    oracle_rows = rows
    print(f"Oracle records read: {len(rows)}")

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
        "shares_created": 0,
        "shares_updated": 0,
        "shares_skipped": 0,
        "mails_prepared_or_sent": 0,
        "mail_previews_created": 0,
        "warnings": 0,
        "errors": 0,
    }
    results = []

    for row in rows:
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

            mail_result = mailer.send_tenant_file_mail(
                mail_to,
                person_id=row.get("PERSON_ID") or row.get("person_id"),
                recipient_name=_recipient_name(row, settings),
                share_link=share_link,
                share_password=str(share_password or ""),
                expiration_date=expiration_date,
            )
            if settings.use_dummy_values and settings.dummy_email_to and mail_result.get("prepared"):
                print(f"Dummy email recipient: {settings.dummy_email_to}")
            if mail_result.get("prepared") or mail_result.get("sent"):
                stats["mails_prepared_or_sent"] += 1
            if mail_result.get("preview"):
                stats["mail_previews_created"] += 1
            if str(mail_result.get("reason", "")).startswith("missing_"):
                stats["warnings"] += 1

            results.append(
                {
                    "person_id": row.get("PERSON_ID") or row.get("person_id"),
                    "person_path": paths.person_path,
                    "folders": folder_results,
                    "share": share_result,
                    "mail": mail_result,
                }
            )
        except Exception as exc:
            stats["errors"] += 1
            print(f"ERROR Failed to process record {row.get('PERSON_ID')}: {exc}")

    print(f"Target paths calculated: {stats['target_paths']}")
    print(f"Folders created: {stats['folders_created']}")
    print(f"Existing folders skipped: {stats['folders_skipped_existing']}")
    print(f"Shares created: {stats['shares_created']}")
    print(f"Shares updated: {stats['shares_updated']}")
    print(f"Shares skipped: {stats['shares_skipped']}")
    print(f"Mails prepared/sent: {stats['mails_prepared_or_sent']}")
    print(f"Mail previews created: {stats['mail_previews_created']}")
    print(f"Warnings: {stats['warnings']}")
    print(f"Errors: {stats['errors']}")

    return {
        "safety": safety.describe(),
        "processed": len(rows),
        "stats": stats,
        "results": results,
    }


def main() -> None:
    result = run()
    print(result)


if __name__ == "__main__":
    main()
