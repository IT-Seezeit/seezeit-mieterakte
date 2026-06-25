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
- `PREVIEW_EMAILS=true`: nur mit `ONLY_DUMMY_PERSON=true`; erzeugt eine Mailvorschau ohne Versand
- `USE_DUMMY_VALUES=true`: nur mit `ONLY_DUMMY_PERSON=true`; kann Test-Passwort, Ablaufdatum und Mailadresse fuer Dummy-Laeufe ueberschreiben

## Benoetigte Umgebungsvariablen

Siehe `.env.example`. Echte Secrets gehoeren nicht ins Repository.

## Ausfuehrung lokal

```bash
pip install -r requirements.txt
python -m src.main
```

## Ausfuehrung ueber Windmill

`windmill/mieterakte_sync.py` ist der Windmill-kompatible Einstiegspunkt. Secrets sollen spaeter ueber Windmill-Variablen oder Ressourcen gepflegt werden.
