# seezeit-mieterakte

## Projektziel

Technischer MVP fuer die Synchronisation von Oracle-Mieterdaten in eine Nextcloud-Mieteraktenstruktur.

## Systemueberblick

- Oracle: lesende Quelle der Mieterdaten
- Nextcloud: Ziel fuer Teamordner, Ordnerstruktur und Dummy-Linkfreigaben
- Windmill: spaetere Ausfuehrung und Orchestrierung
- Git: Code, SQL und Konfiguration

## MVP-Scope

- Oracle-SELECT aus `sql/oracle_mieter_select.sql`
- Parsing von `VO.Suchname`
- sichere Nextcloud-Ordnernamen
- Berechnung und optionale WebDAV-Erstellung der Ordnerstruktur
- Dummy-Share und Mailvorschau bzw. Mailversand nur fuer Person `173884`
- Konsolenlogging und Dry-Run

## Sicherheitsmodi

- `DRY_RUN=true`: keine Nextcloud-Aenderungen, keine echten Mails
- `CREATE_FOLDERS=true` mit `DRY_RUN=false`: Ordner werden idempotent per WebDAV erstellt
- `CREATE_SHARES=true`: nur mit `ONLY_DUMMY_PERSON=true` und expliziter Dummy-ID
- `SEND_EMAILS=true`: nur mit `ONLY_DUMMY_PERSON=true` und genau einer Dummy-ID
- `PREVIEW_EMAILS=true`: nur mit `ONLY_DUMMY_PERSON=true`; erzeugt eine zweisprachige Mailvorschau aus `templates/` ohne Versand
- `USE_DUMMY_VALUES=true`: nur mit `ONLY_DUMMY_PERSON=true`; kann Test-Passwort, Ablaufdatum und Mailadresse fuer Dummy-Laeufe ueberschreiben
- `MAIL_TYPE=auto|move_in|move_out`: waehlt die faellige Einzugs- oder Auszugsmail
- `MAIL_SEND_WINDOW_DAYS=7`: Versandfenster vor `PVV.Beginn` bzw. `PVV.Ende`

## Mailtemplates

Mailversand und Preview verwenden `templates/mail_move_in.*` und `templates/mail_move_out.*` als multipart/alternative. Die unterstuetzten Platzhalter sind in `templates/README.md` dokumentiert. Preview-HTML wird lokal unter `logs/` abgelegt; echte Passwoerter werden in normalen Previews maskiert.

## Nextcloud-Pfade

Der konfigurierte `NEXTCLOUD_TEAMFOLDER_PATH` bleibt unveraendert. Die dynamischen Ordnersegmente enthalten Wohnheim, WG und Zimmer entsprechend ihrer Ebene, zum Beispiel `1160_810-Sonnenbuehl-West-I`, `1160_810-WG-45`, `1160_810-45-Zi-01-52-0` und `1160_810-45-01-52-0-202575-Tabea-Bentele`. Die statischen Unterordner werden ohne `WG` beziehungsweise `Zi` im Namen als `1160_810-45-Historie`, `1160_810-45-01-52-0-Historie` und `1160_810-45-01-52-0-Vergangene-Mieter` erzeugt.

Mit `COPY_INITIAL_TEMPLATES=true` werden `Auszugsprotokoll.pdf` und `Einzugsprotokoll.pdf` aus `NEXTCLOUD_TEMPLATE_FOLDER_PATH` einmalig in einen Mieterordner kopiert, jedoch ausschliesslich wenn dieser im aktuellen Lauf neu erstellt wurde. Bestehende Mieterordner werden weder geprueft noch nachtraeglich repariert. Im `DRY_RUN` werden nur die geplanten Kopien angezeigt.

## Optionales Postgres

Postgres kann mit `USE_POSTGRES=true` als technischer Oracle-Snapshot sowie als persistenter Status- und Run-Speicher aktiviert werden. Oracle bleibt die fuehrende, ausschliesslich lesend verwendete Datenquelle. Das Schema wird nicht automatisch migriert: Vor der Aktivierung muss [sql/postgres_schema.sql](sql/postgres_schema.sql) manuell in der vorgesehenen Datenbank ausgefuehrt werden.

Mit `PROCESS_FROM_POSTGRES=false` werden nach dem Snapshot weiterhin die aktuellen Oracle-Datensaetze verarbeitet. `PROCESS_FROM_POSTGRES=true` liest sie stattdessen aus dem soeben aktualisierten Snapshot. Bei aktivem Postgres verhindert der gespeicherte Versandstatus den erneuten echten Versand desselben Mailtyps; Previews setzen keinen Versandstatus.

`FORCE_DUMMY_MAIL_SEND=true` kann die Fälligkeitsprüfung ausschliesslich fuer einen einzelnen, mit `ONLY_DUMMY_PERSON=true` und `USE_DUMMY_VALUES=true` abgesicherten Testdatensatz uebersteuern. Der Postgres-Doppelversandschutz bleibt aktiv. Fuer gezielte Tests sollte `MAIL_TYPE=move_in` oder `MAIL_TYPE=move_out` explizit gesetzt werden.

## Benoetigte Umgebungsvariablen

Siehe `.env.example`. Echte Secrets gehoeren nicht ins Repository.

## Ausfuehrung lokal

```bash
pip install -r requirements.txt
python -m src.main
```

## Ausfuehrung ueber Windmill

`windmill/mieterakte_sync.py` ist der Windmill-kompatible Einstiegspunkt. Secrets sollen spaeter ueber Windmill-Variablen oder Ressourcen gepflegt werden.
