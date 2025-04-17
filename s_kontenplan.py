# posts/scripts/update_aufgabendetail_kontenplan.py

from posts.models import AufgabeDetail, Kontenplan
from django.db import transaction

def update_aufgabendetail_kontenplan():
    try:
        # Kontenplan 1 abrufen
        kontenplan_standard = Kontenplan.objects.get(id=1)
    except Kontenplan.DoesNotExist:
        print("❌ Kontenplan mit ID 1 existiert nicht!")
        return

    # Alle AufgabeDetails finden, deren Aufgabe-ID <= 19 ist
    details = AufgabeDetail.objects.filter(aufgabe__id__lte=19)

    if not details.exists():
        print("⚠️ Keine passenden AufgabeDetails gefunden.")
        return

    with transaction.atomic():
        for detail in details:
            detail.kontenplan = kontenplan_standard
            detail.save()

    print(f"✅ {details.count()} AufgabeDetails erfolgreich auf Kontenplan 1 aktualisiert.")

if __name__ == "__main__":
    update_aufgabendetail_kontenplan()
