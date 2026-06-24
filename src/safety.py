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
        if self.settings.create_shares:
            self._require_dummy_mode("CREATE_SHARES")
        if self.settings.send_emails:
            self._require_dummy_mode("SEND_EMAILS")

    def _require_dummy_mode(self, feature: str) -> None:
        if not self.settings.only_dummy_person:
            raise RuntimeError(f"{feature}=true is only allowed with ONLY_DUMMY_PERSON=true.")
        if self.settings.dummy_person_id != "173884":
            raise RuntimeError(f"{feature}=true is only allowed with DUMMY_PERSON_ID=173884.")
