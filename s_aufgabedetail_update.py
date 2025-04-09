import os
import django
import json

# Django-Umgebung initialisieren
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "young_wolf.settings")
django.setup()
from posts.models import Konto, Aufgabe_neu, AufgabeDetail

konto_ids = [
    25, 23, 1, 26, 23, 3, 3, 2, 6, 13,
    17, 2, 2, 27, 27, 1, 3, 2, 28, 23,
    6, 2, 29, 24, 26, 23, 3, 2, 13, 24,
    2, 30, 24, 31, 23, 3, 6, 13, 24, 32,
    26, 32, 26, 31, 4, 2, 2, 13, 5, 13,
    8, 8, 8, 7, 4, 23, 7, 6, 4
]

# Alle AufgabeDetail-Einträge, sortiert nach ID
details = AufgabeDetail.objects.all().order_by("id")

# Sicherheitscheck
if len(details) < len(konto_ids):
    print(f"❌ Fehler: Es gibt nur {len(details)} AufgabeDetail-Einträge, aber {len(konto_ids)} Konto-IDs.")
else:
    for detail, konto_id in zip(details, konto_ids):
        detail.konto_id = konto_id
        detail.save(update_fields=["konto"])
        print(f"✅ AufgabeDetail {detail.id}: konto_id → {konto_id}")