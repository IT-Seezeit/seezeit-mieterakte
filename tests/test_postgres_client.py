from datetime import date
from unittest import TestCase

from src.postgres_client import sanitize_for_run_log, source_hash


class PostgresHelpersTests(TestCase):
    def test_source_hash_is_stable_across_key_order(self) -> None:
        first = {
            "PERSVV_ID": 1,
            "PERSON_ID": 2,
            "NAME": "Muster",
            "BEGINN": date(2026, 1, 2),
        }
        second = {
            "BEGINN": date(2026, 1, 2),
            "NAME": "Muster",
            "PERSON_ID": 2,
            "PERSVV_ID": 1,
        }

        self.assertEqual(source_hash(first), source_hash(second))

    def test_source_hash_changes_with_relevant_field(self) -> None:
        first = {"PERSVV_ID": 1, "PERSON_ID": 2, "STATUS": 1}
        second = {"PERSVV_ID": 1, "PERSON_ID": 2, "STATUS": 2}

        self.assertNotEqual(source_hash(first), source_hash(second))

    def test_run_log_sanitizer_removes_nested_password_fields(self) -> None:
        value = {
            "result": {
                "WEBPASSWORT": "tenant-secret",
                "postgres_password": "database-secret",
                "share_link": "https://nextcloud.invalid/s/abc",
            },
            "items": [{"mailPassword": "smtp-secret"}, {"status": "ok"}],
        }

        sanitized = sanitize_for_run_log(value)

        self.assertEqual(
            sanitized,
            {
                "result": {"share_link": "https://nextcloud.invalid/s/abc"},
                "items": [{}, {"status": "ok"}],
            },
        )
