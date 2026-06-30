# Mailtemplates

Diese Dateien werden vom Mailer relativ zum Projektroot geladen.

Aktive Templates:

- `mail_move_in.txt` und `mail_move_in.html`
- `mail_move_out.txt` und `mail_move_out.html`

Unterstützte Platzhalter:

- `{{ recipient_name }}`
- `{{ share_link }}`
- `{{ share_password }}`
- `{{ expiration_date }}`
- `{{ online_portal_link }}`

HTML-Werte werden beim Rendern escaped. Plain-Text-Werte werden unverändert eingesetzt. Passwörter dürfen nicht in normalen Logs erscheinen.
