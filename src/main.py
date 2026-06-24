from __future__ import annotations

from .config import load_settings
from .mailer import Mailer
from .nextcloud_client import NextcloudClient
from .oracle_client import OracleClient
from .path_builder import build_target_paths
from .safety import Safety


def run() -> dict[str, object]:
    settings = load_settings()
    safety = Safety(settings)
    safety.validate()

    oracle = OracleClient(settings)
    nextcloud = NextcloudClient(settings, safety)
    mailer = Mailer(settings, safety)

    rows = oracle.fetch_mieter()
    print(f"Oracle records read: {len(rows)}")

    if settings.only_dummy_person:
        rows = [
            row for row in rows
            if str(row.get("PERSON_ID") or row.get("person_id")) == settings.dummy_person_id
        ]
    print(f"Records after dummy filter: {len(rows)}")

    stats = {
        "target_paths": 0,
        "folders_created": 0,
        "folders_skipped_existing": 0,
        "shares_created": 0,
        "shares_skipped": 0,
        "mails_prepared_or_sent": 0,
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

            share_result = nextcloud.create_share(
                paths.person_path,
                row.get("WEBPASSWORT") or row.get("webpasswort"),
                row.get("ENDE") or row.get("ende"),
            )
            if share_result.get("created"):
                stats["shares_created"] += 1
            if share_result.get("skipped") or share_result.get("dry_run"):
                stats["shares_skipped"] += 1

            mail_result = mailer.send_mail(
                row.get("EMAIL") or row.get("email"),
                "Ihre Mieterakte",
                f"Ihre Mieterakte ist vorbereitet: {paths.person_path}",
            )
            if mail_result.get("prepared") or mail_result.get("sent"):
                stats["mails_prepared_or_sent"] += 1

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
    print(f"Shares skipped: {stats['shares_skipped']}")
    print(f"Mails prepared/sent: {stats['mails_prepared_or_sent']}")
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
