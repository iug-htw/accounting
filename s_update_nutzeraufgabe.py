import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "young_wolf.settings")
django.setup()

from posts.models import NutzerAufgabe, Konto

# 🔧 Manuelles Mapping für Sonderfälle
sonderfaelle = {
    "Geb\u00e4ude": "8",
    "Zinsertr\u00e4ge": "14",
    "Betriebs- und Gesch\u00e4ftsausstattung": "25",
    "Umsatzerl\u00f6se": "13",  # Du hast zwei leere Stellen, wir nehmen eine ID
    "Provisionserl\u00f6se": "13",  # Ggf. gleiches Konto
    "Anlageverm\u00f6gen": "15",  # Bei zwei IDs: erste als Haupt-ID, zweite ignorieren
    "R\u00fcckstellungen": "12",
    "Verbindlichkeiten": "3",
    "B\u00fcromaterialien": "25",
    "Kundenskotno": "29",
    "Forderungen": "6",
    "Büromaterialien": "25",
}

# 💡 Dynamisches Mapping aus der Datenbank
name_to_id = {konto.name: str(konto.id) for konto in Konto.objects.all()}

def konvertiere_konten_liste(liste):
    def normalize(e):
        if not isinstance(e, str):
            return e

        # 1. Manuelles Mapping zuerst prüfen (auch bei Unicode-Form)
        try:
            unicode_klarname = e.encode('utf-8').decode('unicode_escape')
            if unicode_klarname in sonderfaelle:
                return sonderfaelle[unicode_klarname]
        except:
            pass

        # 2. Mapping aus Datenbank
        try:
            return name_to_id.get(e.encode('utf-8').decode('unicode_escape'), name_to_id.get(e, e))
        except:
            return name_to_id.get(e, e)

    return [normalize(e) for e in liste]

anzahl = 0

for buchung in NutzerAufgabe.objects.all():
    soll_raw = buchung.soll_konten or "[]"
    haben_raw = buchung.haben_konten or "[]"

    neue_soll = konvertiere_konten_liste(soll_raw)
    neue_haben = konvertiere_konten_liste(haben_raw)

    if neue_soll != soll_raw or neue_haben != haben_raw:
        buchung.soll_konten = neue_soll
        buchung.haben_konten = neue_haben
        buchung.save()
        anzahl += 1
        print(f"✅ Buchung {buchung.pk} aktualisiert.")

print(f"\n🎉 {anzahl} Buchungen erfolgreich aktualisiert.")
