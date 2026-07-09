from datetime import date, timedelta
from types import SimpleNamespace
from unittest import TestCase

from src.main import _forced_dummy_mail_types, _mail_already_sent
from src.safety import Safety


def force_settings(**overrides: object) -> SimpleNamespace:
    values = {
        "dry_run": False,
        "use_dummy_values": True,
        "only_dummy_person": True,
        "effective_dummy_person_ids": ("123",),
        "create_shares": False,
        "send_emails": False,
        "preview_emails": True,
        "force_dummy_mail_send": True,
        "dummy_share_password": "",
        "dummy_share_expiration_date_is_valid": False,
        "mail_type": "move_out",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class ForceDummyMailSafetyTests(TestCase):
    def test_valid_dummy_override_is_allowed(self) -> None:
        Safety(force_settings()).validate()

    def test_override_requires_only_dummy_person(self) -> None:
        settings = force_settings(only_dummy_person=False)

        with self.assertRaisesRegex(RuntimeError, "ONLY_DUMMY_PERSON=true"):
            Safety(settings).validate()

    def test_override_requires_dummy_values(self) -> None:
        settings = force_settings(use_dummy_values=False)

        with self.assertRaisesRegex(RuntimeError, "USE_DUMMY_VALUES=true"):
            Safety(settings).validate()

    def test_override_requires_exactly_one_dummy_person(self) -> None:
        settings = force_settings(effective_dummy_person_ids=("123", "456"))

        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            Safety(settings).validate()


class ForcedDummyMailTypeTests(TestCase):
    def test_explicit_mail_type_is_preserved(self) -> None:
        settings = force_settings(mail_type="move_out")

        self.assertEqual(_forced_dummy_mail_types({}, settings), ["move_out"])

    def test_auto_uses_move_in_before_contract_start(self) -> None:
        settings = force_settings(mail_type="auto")
        row = {"BEGINN": date.today() + timedelta(days=30)}

        self.assertEqual(_forced_dummy_mail_types(row, settings), ["move_in"])

    def test_auto_uses_move_out_after_contract_start(self) -> None:
        settings = force_settings(mail_type="auto")
        row = {
            "BEGINN": date.today() - timedelta(days=30),
            "ENDE": date.today() + timedelta(days=30),
        }

        self.assertEqual(_forced_dummy_mail_types(row, settings), ["move_out"])

    def test_postgres_sent_state_still_blocks_forced_real_send(self) -> None:
        settings = force_settings(send_emails=True, preview_emails=False)
        state = {"move_out_mail_sent_at": "2026-07-09T10:00:00+00:00"}

        self.assertTrue(_mail_already_sent(state, settings, "move_out"))

    def test_preview_is_not_blocked_by_sent_state(self) -> None:
        settings = force_settings(send_emails=True, preview_emails=True)
        state = {"move_out_mail_sent_at": "2026-07-09T10:00:00+00:00"}

        self.assertFalse(_mail_already_sent(state, settings, "move_out"))
