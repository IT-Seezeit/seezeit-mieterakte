from __future__ import annotations

from dataclasses import dataclass

from .config import Settings


@dataclass(frozen=True)
class Safety:
    settings: Settings

    @property
    def dry_run(self) -> bool:
        return self.settings.dry_run

    def describe(self) -> str:
        if self.dry_run:
            return "dry_run: external write actions are skipped"
        return "live: explicitly enabled write actions may run"

    def validate(self) -> None:
        if self.settings.use_dummy_values:
            self._require_dummy_values_mode()
        if self.settings.only_dummy_person and not self.settings.effective_dummy_person_ids:
            raise RuntimeError(
                "ONLY_DUMMY_PERSON=true requires DUMMY_PERSON_ID or DUMMY_PERSON_IDS to be set."
            )
        if self.settings.create_shares:
            self._require_share_dummy_mode()
        if self.settings.send_emails:
            self._require_email_dummy_mode()
        if self.settings.preview_emails:
            self._require_email_preview_mode()

    def _require_share_dummy_mode(self) -> None:
        if not self.settings.only_dummy_person:
            raise RuntimeError("CREATE_SHARES=true is only allowed with ONLY_DUMMY_PERSON=true.")
        if not self.settings.effective_dummy_person_ids:
            raise RuntimeError("CREATE_SHARES=true requires DUMMY_PERSON_ID or DUMMY_PERSON_IDS to be set.")

    def _require_email_dummy_mode(self) -> None:
        if not self.settings.only_dummy_person:
            raise RuntimeError("SEND_EMAILS=true is only allowed with ONLY_DUMMY_PERSON=true.")
        if not self.settings.effective_dummy_person_ids:
            raise RuntimeError("SEND_EMAILS=true requires DUMMY_PERSON_ID or DUMMY_PERSON_IDS to be set.")
        if len(self.settings.effective_dummy_person_ids) != 1:
            raise RuntimeError(
                "SEND_EMAILS=true is only allowed when exactly one dummy person is configured."
            )

    def _require_email_preview_mode(self) -> None:
        if not self.settings.only_dummy_person:
            raise RuntimeError("PREVIEW_EMAILS=true is only allowed with ONLY_DUMMY_PERSON=true.")
        if not self.settings.effective_dummy_person_ids:
            raise RuntimeError("PREVIEW_EMAILS=true requires DUMMY_PERSON_ID or DUMMY_PERSON_IDS to be set.")

    def _require_dummy_values_mode(self) -> None:
        if not self.settings.only_dummy_person:
            raise RuntimeError("USE_DUMMY_VALUES=true is only allowed with ONLY_DUMMY_PERSON=true.")
        if self.settings.create_shares and not self.settings.dummy_share_password:
            raise RuntimeError("CREATE_SHARES=true with USE_DUMMY_VALUES=true requires DUMMY_SHARE_PASSWORD.")
        if self.settings.create_shares and not self.settings.dummy_share_expiration_date_is_valid:
            raise RuntimeError(
                "CREATE_SHARES=true with USE_DUMMY_VALUES=true requires "
                "DUMMY_SHARE_EXPIRATION_DATE in YYYY-MM-DD format."
            )
