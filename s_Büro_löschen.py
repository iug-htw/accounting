import os
import django
import json

# Django-Umgebung initialisieren
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "young_wolf.settings")
django.setup()

from posts.models import Buchung

zielwert = "Büromaterialien"  # oder "B\u00fcromaterialien"

def safe_parse(val):
    if isinstance(val, str):
        try:
            return json.loads(val or "[]")
        except Exception as e:
            print(f"⚠️ Fehler beim JSON-Decode: {val} → {e}")
            return []
    return val or []

anzahl = 0

for buchung in Buchung.objects.all():
    soll = safe_parse(buchung.antwort_konten_soll)
    haben = safe_parse(buchung.antwort_konten_haben)

    if zielwert in soll or zielwert in haben:
        print(f"🗑️ Lösche Buchung {buchung.pk} (enthält '{zielwert}')")
        buchung.delete()
        anzahl += 1

print(f"\n✅ {anzahl} Buchungen mit '{zielwert}' gelöscht.")
