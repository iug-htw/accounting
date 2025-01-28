from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Unternehmen, AufgabeDetail, Aufgabe_neu, NutzerAufgabe, Buchung, Aufgabenkategorie
from users.models import CustomUser, Studiengang, Semester
from .forms import  Aufgabe_neu_Form, BuchungForm, AufgabenkategorieForm, UnternehmenForm
from django.contrib import messages
from django.utils import timezone
import json, random
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from random import uniform

# Für Lehrkräfte
def lehrkraft_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'teacher':
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponse(f'Fehlende Berechtigung <br><a href="{reverse("index")}">Zurück zur Startseite</a>')
    return _wrapped_view_func

# Für Studierende
def student_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'student':
            return HttpResponse(f'Fehlende Berechtigung <br><a href="{reverse("index")}">Zurück zur Startseite</a>')
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

def aufgabe_neu_erstellen(request):
    if request.method == 'POST':
        form = Aufgabe_neu_Form(request.POST)
        if form.is_valid():
            aufgabe = form.save()

            # Verarbeite die Listenfelder
            kontonamen = request.POST.getlist('kontoname[]')
            soll_haben = request.POST.getlist('soll_haben[]')
            betraege = request.POST.getlist('betrag[]')
            monatsangaben = request.POST.getlist('monatsangabe[]')
            monate = request.POST.getlist('monat[]')

            # Erstelle Einträge für AufgabeDetail
            for i in range(len(kontonamen)):
                AufgabeDetail.objects.create(
                    aufgabe=aufgabe,
                    kontoname=kontonamen[i],
                    soll_haben=soll_haben[i],
                    betrag=float(betraege[i]),
                    monatsangabe=monatsangaben[i] == "true",
                    monat=int(monate[i]) if monate[i] else None,
                )

            return redirect('frontpage')
        else:
            messages.error(request, "Das Formular ist nicht gültig.")
    else:
        form = Aufgabe_neu_Form()

    return render(request, 'posts/aufgabe_erstellen.html', {'form': form})


def rechnung_view(request):
    aufgabe = Aufgabe_neu.objects.first()  # Beispiel für eine zufällige Aufgabe
    return render(request, 'posts/rechnung.html', {'aufgabe': aufgabe})

@login_required
def rechnung_detail_view(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)

    # Nutzer-Aufgabe abrufen oder neue erstellen, falls nicht vorhanden
    nutzer_aufgabe, created = NutzerAufgabe.objects.get_or_create(
        aufgabe=aufgabe,
        nutzer=request.user,
        defaults={'soll_konto': '', 'haben_konto': '', 'betrag': 0, 'geloest': False}
    )

    # Nächste Aufgabe abrufen
    next_aufgabe = Aufgabe_neu.objects.filter(id__gt=aufgabe_id).order_by('id').first()

    if request.method == 'POST':
        soll_konten = request.POST.getlist('soll_konto[]')
        haben_konten = request.POST.getlist('haben_konto[]')
        betraege_soll = request.POST.getlist('soll_betrag[]')
        betraege_haben = request.POST.getlist('haben_betrag[]')

        # Debugging-Ausgabe zur Überprüfung der übermittelten Daten
        print(f"Soll-Konten: {soll_konten}")
        print(f"Haben-Konten: {haben_konten}")
        print(f"Beträge Soll: {betraege_soll}")
        print(f"Beträge Haben: {betraege_haben}")

        # Speichere die Nutzereingaben als Buchung in der Datenbank
        Buchung.objects.create(
            aufgabe=aufgabe,
            nutzer=request.user,
            antwort_konten_soll=json.dumps(soll_konten),
            antwort_konten_haben=json.dumps(haben_konten),
            antwort_betrag_soll=json.dumps([float(b) for b in betraege_soll]),
            antwort_betrag_haben=json.dumps([float(b) for b in betraege_haben]),
        )

        # Überprüfe, ob die Eingabe korrekt ist
        korrekt = (nutzer_aufgabe.soll_konto in soll_konten and
                   nutzer_aufgabe.haben_konto in haben_konten and
                   str(nutzer_aufgabe.betrag) in betraege_soll)

        if korrekt:
            nutzer_aufgabe.geloest = True
            nutzer_aufgabe.save()
            messages.success(request, "Aufgabe erfolgreich gelöst!")
        else:
            messages.error(request, "Die Lösung ist falsch.")

    return render(request, 'posts/rechnung.html', {
        'aufgabe': aufgabe,
        'nutzer_aufgabe': nutzer_aufgabe,
        'next_aufgabe': next_aufgabe
    })



@login_required
def zufaellige_aufgabe_zuweisen(request, aufgabe_id):
    """ Erstellt oder überschreibt eine zufällige Aufgabe für den Nutzer basierend auf min/max-Werten """
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)

    # Zufällige Beträge als Ganzzahl generieren
    zufaelliger_betrag = random.randint(int(aufgabe.min_wert), int(aufgabe.max_wert))

    # Konten aus AufgabeDetail abrufen
    soll_konto_detail = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Soll").first()
    haben_konto_detail = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Haben").first()

    # Fallback-Werte, falls keine Konten gefunden wurden
    soll_konto = soll_konto_detail.kontoname if soll_konto_detail else "Unbekannt"
    haben_konto = haben_konto_detail.kontoname if haben_konto_detail else "Unbekannt"

    # Falls bereits vorhanden, Eintrag überschreiben
    nutzer_aufgabe, created = NutzerAufgabe.objects.update_or_create(
        aufgabe=aufgabe,
        nutzer=request.user,
        defaults={
            'soll_konto': soll_konto,
            'haben_konto': haben_konto,
            'betrag': zufaelliger_betrag,
            'geloest': False
        }
    )

    messages.success(request, "Die Aufgabe wurde erfolgreich zugewiesen!")
    return redirect('posts:rechnung_detail', aufgabe_id=aufgabe.id)

@lehrkraft_required
def unternehmen_verwalten(request):
    if request.method == 'POST':
        form = UnternehmenForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('posts:unternehmen_verwalten')
    else:
        form = UnternehmenForm()

    unternehmen = Unternehmen.objects.all()
    return render(request, 'posts/neues_unternehmen.html', {
        'form': form,
        'unternehmen': unternehmen
    })

@lehrkraft_required
def unternehmen_loeschen(request, unternehmen_id):
    unternehmen = get_object_or_404(Unternehmen, id=unternehmen_id)
    unternehmen.delete()
    return redirect('posts:unternehmen_verwalten')

@lehrkraft_required
def aufgabenkategorie_verwalten(request):
    if request.method == 'POST':
        form = AufgabenkategorieForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('posts:aufgabenkategorie_verwalten')
    else:
        form = AufgabenkategorieForm()

    aufgabenkategorien = Aufgabenkategorie.objects.all()
    return render(request, 'posts/neue_kategorie.html', {
        'form': form,
        'aufgabenkategorien': aufgabenkategorien
    })

@lehrkraft_required
def aufgabenkategorie_loeschen(request, kategorie_id):
    kategorie = get_object_or_404(Aufgabenkategorie, id=kategorie_id)
    kategorie.delete()
    return redirect('posts:aufgabenkategorie_verwalten')
