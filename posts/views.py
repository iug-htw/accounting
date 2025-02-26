from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Unternehmen, AufgabeDetail, Aufgabe_neu, NutzerAufgabe, Buchung, Aufgabenkategorie, Mail, Konto, Anfangsbestand
from .forms import  Aufgabe_neu_Form, AufgabenkategorieForm, UnternehmenForm, AufgabeBearbeitenForm, AufgabeDetailBearbeitenForm,KontoForm
from django.contrib import messages
import json, random, hashlib
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from .absender import ZUFÄLLIGE_ABSENDER
import io
#passt

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

def handle_form_submission(request, form_class, success_message, redirect_url, instance=None):
    form = form_class(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        messages.success(request, success_message)
        return redirect(redirect_url)
    else:
        messages.error(request, "Das Formular ist nicht gültig.")
        return None

def create_buchung(aufgabe, nutzer, soll_konten, haben_konten, betraege_soll, betraege_haben, korrekturbuchung=False):
    Buchung.objects.create(
        aufgabe=aufgabe,
        nutzer=nutzer,
        antwort_konten_soll=json.dumps(soll_konten),
        antwort_konten_haben=json.dumps(haben_konten),
        antwort_betrag_soll=json.dumps([float(b) for b in betraege_soll]),
        antwort_betrag_haben=json.dumps([float(b) for b in betraege_haben]),
        korrekturbuchung=korrekturbuchung
    )

def aufgabe_neu_erstellen(request):
    if request.method == 'POST':
        form = Aufgabe_neu_Form(request.POST)
        if form.is_valid():
            aufgabe = form.save()
            speichere_aufgabe_details(request, aufgabe)
            messages.success(request, 'Aufgabe und Details erfolgreich erstellt.')
            return redirect('frontpage')
        else:
            messages.error(request, 'Das Formular ist nicht gültig.')
    else:
        form = Aufgabe_neu_Form()
    
    konten = Konto.objects.all()  # Konten abrufen
    return render(request, 'posts/aufgabe_erstellen.html', {'form': form, 'konten': konten})

def speichere_aufgabe_details(request, aufgabe):
    """Speichert die Details der erstellten Aufgabe und verarbeitet Abhängigkeiten korrekt"""
    kontonamen = request.POST.getlist('kontoname[]')
    soll_haben = request.POST.getlist('soll_haben[]')
    betraege = request.POST.getlist('betrag[]')
    monatsangaben = request.POST.getlist('monatsangabe[]')
    monate = request.POST.getlist('monat[]')

    # Neue Felder für Abhängigkeiten
    formel_typen = request.POST.getlist('formel_typ[]')
    festbetraege = request.POST.getlist('festbetrag[]')
    faktoren = request.POST.getlist('faktor[]')
    bezugs_konto_ids = request.POST.getlist('bezugs_konto[]')  # Nur gültige Zahlen übernehmen
    print("Gefilterte Bezugs-Konten-IDs:", bezugs_konto_ids)  # Debug-Print    print(f"{bezugs_konto_ids}")

    aufgabe_details = []  # Zwischenspeicher für bulk_create()

    # **Erster Schritt: Speichere alle Details ohne Bezugskonto**
    for i in range(len(kontonamen)):
        aufgabe_detail = AufgabeDetail.objects.create(
            aufgabe=aufgabe,
            kontoname=kontonamen[i],
            soll_haben=soll_haben[i],
            betrag=float(betraege[i]) if betraege[i] else None,
            monatsangabe=(monatsangaben[i].lower() == 'true'),
            monat=(int(monate[i]) if monate[i] else None),
            formel_typ=formel_typen[i],
            festbetrag=float(festbetraege[i]) if festbetraege[i] else None,
            faktor=float(faktoren[i]) if faktoren[i] else None
        )
        aufgabe_details.append(aufgabe_detail)

    for i, aufgabe_detail in enumerate(AufgabeDetail.objects.filter(aufgabe=aufgabe)):
        if i < len(bezugs_konto_ids) and bezugs_konto_ids[i]:  # Stelle sicher, dass der Index existiert und kein leerer Wert vorliegt
            aufgabe_detail.bezugs_konto_id = int(bezugs_konto_ids[i])  # ✅ ID direkt in das Feld speichern
            aufgabe_detail.save()
            print(f"AufgabeDetail ID {aufgabe_detail.id}: Bezugskonto-ID gesetzt auf {bezugs_konto_ids[i]}")




def is_buchung_korrekt(buchung, nutzer_aufgabe):
    # JSON-Daten der Buchung laden
    soll_konten_nutzer = json.loads(buchung.antwort_konten_soll)
    haben_konten_nutzer = json.loads(buchung.antwort_konten_haben)
    soll_betraege_nutzer = [round(float(b), 2) for b in json.loads(buchung.antwort_betrag_soll)]
    haben_betraege_nutzer = [round(float(b), 2) for b in json.loads(buchung.antwort_betrag_haben)]

    # Erwartete Werte aus der Nutzeraufgabe
    soll_konten_aufgabe = nutzer_aufgabe.soll_konten
    haben_konten_aufgabe = nutzer_aufgabe.haben_konten
    soll_betraege_aufgabe = [round(float(b), 2) for b in nutzer_aufgabe.soll_betraege]
    haben_betraege_aufgabe = [round(float(b), 2) for b in nutzer_aufgabe.haben_betraege]

    # Prüfen, ob die Konten und Beträge übereinstimmen
    konten_soll_korrekt = set(soll_konten_nutzer) == set(soll_konten_aufgabe)
    konten_haben_korrekt = set(haben_konten_nutzer) == set(haben_konten_aufgabe)
    betraege_soll_korrekt = sum(soll_betraege_nutzer) == sum(soll_betraege_aufgabe)
    betraege_haben_korrekt = sum(haben_betraege_nutzer) == sum(haben_betraege_aufgabe)

    # Prüfen, ob Summe Soll = Summe Haben
    summe_soll_nutzer = sum(soll_betraege_nutzer)
    summe_haben_nutzer = sum(haben_betraege_nutzer)
    summe_korrekt = summe_soll_nutzer == summe_haben_nutzer

    # Ergebnis zurückgeben
    return konten_soll_korrekt and konten_haben_korrekt and betraege_soll_korrekt and betraege_haben_korrekt and summe_korrekt


@login_required
def rechnung_detail_view(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    nutzer_aufgabe, _ = NutzerAufgabe.objects.get_or_create(
        aufgabe=aufgabe, nutzer=request.user,
        defaults={'soll_konto': '', 'haben_konto': '', 'betrag': 0, 'bearbeitungsstand': 'offen'}
    )

    buchungen = Buchung.objects.filter(aufgabe=aufgabe, nutzer=request.user).order_by('buchung_id')
    next_aufgabe = Aufgabe_neu.objects.filter(id__gt=aufgabe_id).order_by('id').first()
    konten = Konto.objects.all()

    if request.method == 'POST':
        buchung = handle_nutzer_buchung(request, aufgabe)
        if not is_buchung_korrekt(buchung, nutzer_aufgabe):
            send_korrektur_mail(request.user, aufgabe, aufgabe.fragentyp)
        return redirect('posts:rechnung_detail', aufgabe_id=aufgabe.id)

    letzte_buchung = buchungen.last()

    block_buchung = False
    if letzte_buchung:
        ist_falsch = letzte_buchung.status != 'korrekt'
        ist_korrekturbuchung = letzte_buchung.korrekturbuchung

        # Blockieren NUR wenn falsch UND KEINE Korrekturbuchung
        block_buchung = ist_falsch and not ist_korrekturbuchung

    # Status für jede Buchung vorbereiten
    buchung_status = []
    for buchung in buchungen:
        buchung_status.append({
            'buchung': buchung,
            'korrekt': is_buchung_korrekt(buchung, nutzer_aufgabe),
            'is_letzte_falsche': buchung == letzte_buchung and block_buchung
        })

    # Template für den Rechnungstyp auswählen
    template_map = {
        'eingehend': 'posts/rechnungen/rechnung_eingehend.html',
        'ausgehend': 'posts/rechnungen/rechnung_ausgehend.html',
        'intern': 'posts/rechnungen/rechnung_intern.html',
    }

    rechnungs_template = template_map.get(aufgabe.rechnungstyp, 'posts/rechnungen/rechnung_basis.html')

    # Kontext mit allen notwendigen Daten
    context = {
        'rechnungs_template': rechnungs_template,  # Dynamisch gewähltes Template
        'rechnungsnummer': aufgabe.rechnungsnummer,
        'datum': aufgabe.datum,
        'anschrift_kunde': aufgabe.anschrift_kunde,
        'eigene_ansicht': aufgabe.eigene_ansicht,
        'beschreibung': aufgabe.beschreibung,
        'rechnungsbetrag': aufgabe.rechnungsbetrag,
        'zahlweise': aufgabe.zahlweise,
        'verabschiedung': aufgabe.verabschiedung,
        'kontakt': aufgabe.kontakt,
        'rechnungstyp': aufgabe.get_rechnungstyp_display(),
        'aufgabe': aufgabe,
        'nutzer_aufgabe': nutzer_aufgabe,
        'next_aufgabe': next_aufgabe,
        'buchungen': buchungen,
        'buchung_status': buchung_status,
        'konten': konten,
        'block_buchung': block_buchung
    }

    return render(request, 'posts/rechnung.html', context)



def update_buchung_status(buchung, ist_korrekt):
    if ist_korrekt:
        buchung.status = 'korrekt'
    else:
        buchung.status = 'bearbeitet'
    buchung.save()

def handle_nutzer_buchung(request, aufgabe):
    letzte_buchung = Buchung.objects.filter(aufgabe=aufgabe, nutzer=request.user).order_by('-versuch').first()
    neuer_versuch = (letzte_buchung.versuch + 1) if letzte_buchung else 1

    # Buchung erstellen
    buchung = Buchung.objects.create(
        aufgabe=aufgabe,
        nutzer=request.user,
        antwort_konten_soll=json.dumps(request.POST.getlist('soll_konto[]')),
        antwort_konten_haben=json.dumps(request.POST.getlist('haben_konto[]')),
        antwort_betrag_soll=json.dumps(request.POST.getlist('soll_betrag[]')),
        antwort_betrag_haben=json.dumps(request.POST.getlist('haben_betrag[]')),
        status='bearbeitet',
        versuch=neuer_versuch
    )

    # Nutzeraufgabe laden
    nutzer_aufgabe = NutzerAufgabe.objects.get(aufgabe=aufgabe, nutzer=request.user)

    # JSON-Daten der Buchung laden
    soll_konten_nutzer = json.loads(buchung.antwort_konten_soll)
    haben_konten_nutzer = json.loads(buchung.antwort_konten_haben)
    betraege_soll_nutzer = [round(float(betrag), 2) for betrag in json.loads(buchung.antwort_betrag_soll)]
    betraege_haben_nutzer = [round(float(betrag), 2) for betrag in json.loads(buchung.antwort_betrag_haben)]

    # Erwartete Werte laden
    soll_konten_aufgabe = nutzer_aufgabe.soll_konten
    haben_konten_aufgabe = nutzer_aufgabe.haben_konten
    soll_betraege_aufgabe = [round(float(b), 2) for b in nutzer_aufgabe.soll_betraege]
    haben_betraege_aufgabe = [round(float(b), 2) for b in nutzer_aufgabe.haben_betraege]

    # Fehlerstatus für Konten setzen
    if set(soll_konten_nutzer) != set(soll_konten_aufgabe) and set(haben_konten_nutzer) != set(haben_konten_aufgabe):
        konto_status = 3  # Beide falsch
    elif set(soll_konten_nutzer) != set(soll_konten_aufgabe):
        konto_status = 1  # Soll falsch
    elif set(haben_konten_nutzer) != set(haben_konten_aufgabe):
        konto_status = 2  # Haben falsch
    else:
        konto_status = 0  # Beide korrekt

    # Fehlerstatus für Beträge setzen
    if sum(betraege_soll_nutzer) != sum(soll_betraege_aufgabe) and sum(betraege_haben_nutzer) != sum(haben_betraege_aufgabe):
        betrag_status = 3  # Beide falsch
    elif sum(betraege_soll_nutzer) != sum(soll_betraege_aufgabe):
        betrag_status = 1  # Soll falsch
    elif sum(betraege_haben_nutzer) != sum(haben_betraege_aufgabe):
        betrag_status = 2  # Haben falsch
    else:
        betrag_status = 0  # Beide korrekt

    # Summe Soll = Summe Haben prüfen
    summe_soll_nutzer = sum(betraege_soll_nutzer)
    summe_haben_nutzer = sum(betraege_haben_nutzer)
    summe_korrekt = summe_soll_nutzer == summe_haben_nutzer

    # Speichern der Fehlerstatus in der Datenbank
    buchung.konto_korrekt = konto_status
    buchung.betrag_korrekt = betrag_status
    buchung.save()

    # Neue Bedingung für die Aufgabe als korrekt
    if konto_status == 0 and betrag_status == 0 and summe_korrekt:
        buchung.status = "korrekt"
        nutzer_aufgabe.bearbeitungsstand = "korrekt"
    else:
        buchung.status = "bearbeitet"
        nutzer_aufgabe.bearbeitungsstand = "bearbeitet"

    buchung.save()
    nutzer_aufgabe.save()

    return buchung

@login_required
def zufaellige_aufgabe_zuweisen(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    
    # Generiere zufällige Werte und speichere oder aktualisiere Nutzeraufgabe
    zufaellige_werte = generiere_zufaellige_werte(aufgabe)
    nutzer_aufgabe = speichere_nutzer_aufgabe(request.user, aufgabe, zufaellige_werte)
    
    # Berechne den nächsten Versuchswert
    naechster_versuch = berechne_naechsten_versuch(request.user, aufgabe)
    
    # Erstelle eine Mail für den neuen Versuch
    erstelle_aufgaben_mail(request.user, aufgabe, naechster_versuch)
    
    messages.success(request, "Die Aufgabe wurde erfolgreich zugewiesen!")
    return redirect('posts:rechnung_detail', aufgabe_id=aufgabe.id)

def generiere_zufaellige_werte(aufgabe, tiefe=0):
    if tiefe < 50:
        print(f"Aufruf {tiefe}: Generiere Werte für Aufgabe ID {aufgabe.id}")

        # Alle Soll- und Haben-Konten abrufen
        soll_konten_queryset = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Soll")
        haben_konten_queryset = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Haben")

        soll_konten, soll_betraege, referenz_betraege_soll = berechne_zufaellige_betraege(soll_konten_queryset)
        haben_konten, haben_betraege, referenz_betraege_haben = berechne_zufaellige_betraege(haben_konten_queryset)
        referenz_betraege = referenz_betraege_soll + referenz_betraege_haben

        summe_soll = sum(soll_betraege)
        summe_haben = sum(haben_betraege)
        differenz = summe_soll - summe_haben

        # Anpassung bei Differenz
        if differenz != 0:
            soll_betraege, haben_betraege = differenzausgleich_wertegenerierung(aufgabe, soll_konten, haben_konten, soll_betraege, haben_betraege, differenz)
            # Erneute Überprüfung nach der Anpassung
            summe_soll = sum(soll_betraege)
            summe_haben = sum(haben_betraege)
            print(f"Neue Summe Soll: {summe_soll}, Neue Summe Haben: {summe_haben}")

            # Überprüfung der angepassten Werte mit Referenzwerten
            for i, betrag in enumerate(soll_betraege + haben_betraege):
                referenzwert = referenz_betraege[i % len(referenz_betraege)]
                if not (referenzwert * 0.5 <= betrag <= referenzwert * 1.75):
                    print(f"Angepasster Betrag {betrag} außerhalb des zulässigen Bereichs ({referenzwert * 0.5} - {referenzwert * 1.75})")
                    return generiere_zufaellige_werte(aufgabe, tiefe + 1)

        print(f"Erfolgreich generiert nach {tiefe} Versuchen")
        return {
            'soll_konten': soll_konten,
            'haben_konten': haben_konten,
            'soll_betraege': soll_betraege,
            'haben_betraege': haben_betraege
        }

def differenzausgleich_wertegenerierung(aufgabe, soll_konten, haben_konten, soll_betraege, haben_betraege, differenz):
    nicht_referenzierte_soll_konten = [
        konto for konto in soll_konten 
        if konto not in [k.bezugs_konto_id for k in AufgabeDetail.objects.filter(aufgabe=aufgabe) if k.bezugs_konto_id]
    ]
    nicht_referenzierte_haben_konten = [
        konto for konto in haben_konten 
        if konto not in [k.bezugs_konto_id for k in AufgabeDetail.objects.filter(aufgabe=aufgabe) if k.bezugs_konto_id]
    ]

    # Höchste Beträge und deren Indizes
    max_soll_index = soll_betraege.index(max(soll_betraege))
    max_haben_index = haben_betraege.index(max(haben_betraege))

    max_soll_konto = soll_konten[max_soll_index]
    max_haben_konto = haben_konten[max_haben_index]

    # Prüfen, ob die höchsten Werte referenziert sind
    max_soll_referenziert = max_soll_konto in nicht_referenzierte_soll_konten
    max_haben_referenziert = max_haben_konto in nicht_referenzierte_haben_konten

    # Entscheidung, welchen Betrag anzupassen
    if soll_betraege[max_soll_index] >= haben_betraege[max_haben_index]:
        if max_soll_referenziert:  # Falls max. Soll-Konto referenziert ist, Haben nehmen
            haben_betraege[max_haben_index] += differenz
        else:
            soll_betraege[max_soll_index] -= differenz
    else:
        if max_haben_referenziert:  # Falls max. Haben-Konto referenziert ist, Soll nehmen
            soll_betraege[max_soll_index] -= differenz
        else:
            haben_betraege[max_haben_index] += differenz

    return soll_betraege, haben_betraege

def berechne_zufaellige_betraege(konten_queryset):
    konten = []
    betraege = []
    referenz_betraege = []
    
    normale_konten = konten_queryset.exclude(formel_typ="faktor")
    faktor_konten = konten_queryset.filter(formel_typ="faktor")
    
    berechnete_werte = {}  # Speichert bereits berechnete Werte für Bezugskonten
    
    for konto in normale_konten:
        referenz_betrag = konto.betrag
        min_betrag = referenz_betrag * 0.25
        max_betrag = referenz_betrag * 1.75
        zufallswert = random.randint(int(min_betrag), int(max_betrag))
        konten.append(konto.kontoname)
        betraege.append(round(zufallswert, 0))
        referenz_betraege.append(zufallswert)
        berechnete_werte[int(konto.kontoname)] = zufallswert  # Speichert den berechneten Wert
    
    for konto in faktor_konten:
        if konto.bezugs_konto_id in berechnete_werte:
            faktor_wert = round(berechnete_werte[konto.bezugs_konto_id] * konto.faktor,2)

        konten.append(konto.kontoname)
        betraege.append(faktor_wert)
        referenz_betraege.append(faktor_wert)
        berechnete_werte[konto.id] = faktor_wert  # Speichert den berechneten Wert auch für faktor-Konten
    
    return konten, betraege, referenz_betraege



def speichere_nutzer_aufgabe(nutzer, aufgabe, zufaellige_werte):
    nutzer_aufgabe, created = NutzerAufgabe.objects.get_or_create(
        aufgabe=aufgabe,
        nutzer=nutzer,
        defaults={
            'soll_konten': zufaellige_werte['soll_konten'],
            'haben_konten': zufaellige_werte['haben_konten'],
            'soll_betraege': zufaellige_werte['soll_betraege'],
            'haben_betraege': zufaellige_werte['haben_betraege'],
            'bearbeitungsstand': 'offen'
        }
    )

    if not created:
        nutzer_aufgabe.soll_konten = zufaellige_werte['soll_konten']
        nutzer_aufgabe.haben_konten = zufaellige_werte['haben_konten']
        nutzer_aufgabe.soll_betraege = zufaellige_werte['soll_betraege']
        nutzer_aufgabe.haben_betraege = zufaellige_werte['haben_betraege']
        nutzer_aufgabe.bearbeitungsstand = 'offen'
        nutzer_aufgabe.save()

    return nutzer_aufgabe


def berechne_naechsten_versuch(nutzer, aufgabe):
    letzter_mail_versuch = Mail.objects.filter(aufgabe=aufgabe, nutzer=nutzer).order_by('-versuch').first()
    letzter_buchung_versuch = Buchung.objects.filter(aufgabe=aufgabe, nutzer=nutzer).order_by('-versuch').first()

    hoechster_versuch = max(
        (letzter_mail_versuch.versuch if letzter_mail_versuch else 0),
        (letzter_buchung_versuch.versuch if letzter_buchung_versuch else 0)
    )
    return hoechster_versuch + 1

def erstelle_aufgaben_mail(nutzer, aufgabe, versuch):
    absender = random.choice(ZUFÄLLIGE_ABSENDER)
    betreff = f"Neue Aufgabe Versuch {versuch}"
    mailtext = f"Bitte bearbeiten Sie die Aufgabe: {aufgabe.fragentyp_text}"

    Mail.objects.create(
        nutzer=nutzer,
        aufgabe=aufgabe,
        betreff=betreff,
        mailtext=mailtext,
        versuch=versuch,
        von=absender["email"],  # Setze zufällige Email
        absender_name=absender["name"],  # Setze zufälligen Namen
        absender_adresse=absender["adresse"],  # Setze zufällige Adresse
        status='nicht bearbeitet'
    )

def get_fallback_konten(aufgabe):
    soll_konto = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Soll").order_by('?').first()
    haben_konto = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Haben").order_by('?').first()
    return (soll_konto.kontoname if soll_konto else "Soll-Konto-Standard",
            haben_konto.kontoname if haben_konto else "Haben-Konto-Standard")


@lehrkraft_required
def unternehmen_verwalten(request):
    return handle_post_request(request, UnternehmenForm, 'posts:unternehmen_verwalten', 'posts/neues_unternehmen.html')


def handle_post_request(request, form_class, redirect_url, template_name):
    if request.method == 'POST':
        result = handle_form_submission(request, form_class, "Erfolgreich gespeichert.", redirect_url)
        if result:
            return result
    form = form_class()
    return render(request, template_name, {'form': form})

@lehrkraft_required
def unternehmen_loeschen(request, unternehmen_id):
    unternehmen = get_object_or_404(Unternehmen, id=unternehmen_id)
    unternehmen.delete()
    return redirect('posts:unternehmen_verwalten')

@lehrkraft_required
def aufgabenkategorie_verwalten(request):
    return handle_post_request(request, AufgabenkategorieForm, 'posts:aufgabenkategorie_verwalten', 'posts/neue_kategorie.html')


@lehrkraft_required
def aufgabenkategorie_loeschen(request, kategorie_id):
    kategorie = get_object_or_404(Aufgabenkategorie, id=kategorie_id)
    kategorie.delete()
    return redirect('posts:aufgabenkategorie_verwalten')

@login_required
def hauptbuch_view(request):
    user = request.user

    # Falls noch keine anfangsbestaende existieren, generiere sie
    generate_user_anfangsbestaende(user)

    # anfangsbestaende des Nutzers abrufen
    anfangsbestaende = Anfangsbestand.objects.filter(nutzer=user)

    # Alle Buchungen des Nutzers abrufen
    buchungen = Buchung.objects.filter(nutzer=user)

    # T-Konten erstellen mit anfangsbestaenden UND Buchungen
    t_konten = build_t_konten(buchungen, anfangsbestaende)

    return render(request, "posts/hauptbuch.html", {"t_konten": t_konten})


def generate_color(aufgabe_id):
    hash_value = int(hashlib.md5(str(aufgabe_id).encode()).hexdigest(), 16)
    hue = hash_value % 360
    return f"hsl({hue}, 70%, 85%)"

def build_t_konten(buchungen, anfangsbestände):
    t_konten = {}
    aufgabe_farben = {}

    # Anfangsbestände in die T-Konten-Struktur aufnehmen
    for bestand in anfangsbestände:
        konto_name = bestand.konto.name
        t_konten.setdefault(konto_name, {"soll": [], "haben": []})

        if bestand.konto.unterkategorie == "Aktiva":  # EBK für Aktivkonten auf Soll-Seite
            t_konten[konto_name]["soll"].append(("EBK", bestand.betrag, "#D3D3D3"))
        elif bestand.konto.unterkategorie == "Passiva":  # EBK für Passivkonten auf Haben-Seite
            t_konten[konto_name]["haben"].append(("EBK", bestand.betrag, "#D3D3D3"))

    # Bestehende Buchungen hinzufügen (Originalfunktion bleibt erhalten)
    for buchung in buchungen:
        aufgabe_id = buchung.aufgabe.id

        if aufgabe_id not in aufgabe_farben:
            aufgabe_farben[aufgabe_id] = generate_color(aufgabe_id)

        soll_konten = json.loads(buchung.antwort_konten_soll or "[]")
        haben_konten = json.loads(buchung.antwort_konten_haben or "[]")
        soll_betraege = json.loads(buchung.antwort_betrag_soll or "[]")
        haben_betraege = json.loads(buchung.antwort_betrag_haben or "[]")

        for konto, betrag in zip(soll_konten, soll_betraege):
            farbe = aufgabe_farben[aufgabe_id]
            t_konten.setdefault(konto, {"soll": [], "haben": []})["soll"].append((aufgabe_id, betrag, farbe))

        for konto, betrag in zip(haben_konten, haben_betraege):
            farbe = aufgabe_farben[aufgabe_id]
            t_konten.setdefault(konto, {"soll": [], "haben": []})["haben"].append((aufgabe_id, betrag, farbe))

    return t_konten

@login_required
def aufgabe_bearbeiten(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    details = AufgabeDetail.objects.filter(aufgabe=aufgabe)

    if request.method == 'POST':
        result = handle_form_submission(request, AufgabeBearbeitenForm, "Aufgabe erfolgreich bearbeitet.", 'posts:hauptbuch', instance=aufgabe)
        if result:
            for detail in details:
                detail_form = AufgabeDetailBearbeitenForm(request.POST, prefix=str(detail.id), instance=detail)
                if detail_form.is_valid():
                    detail_form.save()
                else:
                    messages.error(request, "Fehler beim Bearbeiten der Details.")
            return result

    form = AufgabeBearbeitenForm(instance=aufgabe)
    detail_forms = [AufgabeDetailBearbeitenForm(prefix=str(detail.id), instance=detail) for detail in details]
    return render(request, 'posts/aufgabe_bearbeiten.html', {'form': form, 'detail_forms': detail_forms})

@login_required
def aufgabe_loeschen(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)

    if request.method == "POST":
        aufgabe.delete()
        messages.success(request, "Aufgabe erfolgreich gelöscht.")
        return redirect('posts:hauptbuch')

    return render(request, 'posts/aufgabe_loeschen.html', {'aufgabe': aufgabe})


@login_required
def korrekturbuchung_durchfuehren(request, buchung_id):
    buchung = get_object_or_404(Buchung, buchung_id=buchung_id)

    letzte_buchung = Buchung.objects.filter(aufgabe=buchung.aufgabe, nutzer=request.user).order_by('-versuch').first()
    naechster_versuch = (letzte_buchung.versuch + 1) if letzte_buchung else 1

    neue_buchung = Buchung.objects.create(
        aufgabe=buchung.aufgabe,
        nutzer=request.user,
        antwort_konten_soll=buchung.antwort_konten_haben,
        antwort_konten_haben=buchung.antwort_konten_soll,
        antwort_betrag_soll=buchung.antwort_betrag_haben,
        antwort_betrag_haben=buchung.antwort_betrag_soll,
        status='bearbeitet',
        korrekturbuchung=True,
        versuch=naechster_versuch
    )

    messages.success(request, f'Korrekturbuchung im Versuch {naechster_versuch} erfolgreich durchgeführt.')
    return redirect('posts:rechnung_detail', aufgabe_id=buchung.aufgabe.id)

@login_required
def posteingang(request):
    mails = Mail.objects.filter(nutzer=request.user).order_by('-datum')

    for mail in mails:
        # Prüfen, ob eine Buchung für den aktuellen Versuch existiert
        buchung_vorhanden = Buchung.objects.filter(
            aufgabe=mail.aufgabe,
            nutzer=request.user,
            versuch=mail.versuch  # Korrekte Zuordnung zum Versuch
        ).exists()

        # Status aktualisieren
        if buchung_vorhanden:
            mail.status = 'bearbeitet'
        mail.save()

    return render(request, 'posts/posteingang.html', {'mails': mails})

@login_required
def mail_detail(request, mail_id):
    mail = get_object_or_404(Mail, id=mail_id, nutzer=request.user)

    # Mail-Status auf "bearbeitet" setzen
    mail.status = 'bearbeitet'
    mail.save()

    # Standardlink zur Aufgabe setzen, falls vorhanden
    aufgabe_link = None
    if mail.aufgabe:
        aufgabe_link = reverse('posts:rechnung_detail', args=[mail.aufgabe.id])
    
    # Falls die Mail zur Namens- & Passwortänderung ist, ersetze den Link
    elif "Bitte aktualisieren Sie Ihren Anzeigenamen" in mail.betreff:
        aufgabe_link = reverse('users:update_profile')

    return render(request, 'posts/mail_detail.html', {
        'mail': mail,
        'aufgabe_link': aufgabe_link
    })

def send_korrektur_mail(nutzer, aufgabe, aufgabenkategorie):
    # Den höchsten bisherigen Versuch aus der Buchungs- oder Mail-Tabelle ermitteln
    letzter_mail_versuch = Mail.objects.filter(aufgabe=aufgabe, nutzer=nutzer).order_by('-versuch').first()
    letzter_buchung_versuch = Buchung.objects.filter(aufgabe=aufgabe, nutzer=nutzer).order_by('-versuch').first()

    # Höchsten Versuch ermitteln
    hoechster_versuch = max(
        (letzter_mail_versuch.versuch if letzter_mail_versuch else 0),
        (letzter_buchung_versuch.versuch if letzter_buchung_versuch else 0)
    )

    naechster_versuch = hoechster_versuch + 1  # Neuer Versuch = Höchster + 1

    mail_betreff = f"Korrekturbuchung Versuch {naechster_versuch} - {aufgabenkategorie.name}"
    mail_text = (
        f"Sehr geehrte/r {nutzer.username},\n\n"
        f"Ihre Buchung zur Aufgabe '{aufgabe.fragentyp_text}' enthält einen Fehler. "
        "Bitte korrigieren Sie Ihre Eingaben über den folgenden Link:\n"
        f"http://localhost:8000{reverse('posts:rechnung_detail', args=[aufgabe.id])}\n\n"
        "Vielen Dank.\nIhr Buchhaltungsteam"
    )

    # Neue Mail mit dem korrekten Versuchswert erstellen
    Mail.objects.create(
        nutzer=nutzer,
        aufgabe=aufgabe,
        betreff=mail_betreff,
        mailtext=mail_text,
        versuch=naechster_versuch,  # Dynamischer Versuchswert
        status='nicht bearbeitet'
    )

@lehrkraft_required
def konten_verwalten(request):
    if request.method == 'POST':
        form = KontoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Konto erfolgreich hinzugefügt.")
            return redirect('posts:konten_verwalten')
        else:
            messages.error(request, "Fehler: Überprüfe deine Eingaben.")
    else:
        form = KontoForm()

    konten = Konto.objects.all().order_by('kategorie', 'unterkategorie')

    return render(request, 'posts/konten_verwalten.html', {'form': form, 'konten': konten})

@lehrkraft_required
def konto_bearbeiten(request, konto_id):
    konto = get_object_or_404(Konto, id=konto_id)

    if request.method == 'POST':
        form = KontoForm(request.POST, instance=konto)
        if form.is_valid():
            form.save()
            messages.success(request, "Konto erfolgreich aktualisiert.")
            return redirect('posts:konten_verwalten')
        else:
            messages.error(request, "Fehler: Überprüfe deine Eingaben.")
    else:
        form = KontoForm(instance=konto)

    return render(request, 'posts/konto_bearbeiten.html', {'form': form, 'konto': konto})


@lehrkraft_required
def konto_loeschen(request, konto_id):
    konto = get_object_or_404(Konto, id=konto_id)
    konto.delete()
    messages.success(request, f"Konto '{konto.name}' wurde erfolgreich gelöscht.")
    return redirect('posts:konten_verwalten')

@login_required
def nutzer_fortschritt(request):
    # Anzahl aller Aufgaben des Nutzers
    gesamt_aufgaben = NutzerAufgabe.objects.filter(nutzer=request.user).count()
    # Bearbeitungsstand der Aufgaben berechnen
    offen = NutzerAufgabe.objects.filter(nutzer=request.user, bearbeitungsstand="offen").count()
    bearbeitet = NutzerAufgabe.objects.filter(nutzer=request.user, bearbeitungsstand="bearbeitet").count()
    korrekt = NutzerAufgabe.objects.filter(nutzer=request.user, bearbeitungsstand="korrekt").count()
    # Sicherstellen, dass keine Division durch 0 stattfindet
    prozent_korrekt = round((korrekt / gesamt_aufgaben) * 100) if gesamt_aufgaben > 0 else 0
    return JsonResponse({
        'gesamt': gesamt_aufgaben,'offen': offen,'bearbeitet': bearbeitet,'korrekt': korrekt,'prozent': prozent_korrekt
    })


User = get_user_model()
@login_required
def lehrer_fortschritt(request):
    """Hauptfunktion, die den Fortschritt der Studierenden für Lehrer berechnet."""
    if request.user.role != 'teacher':
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)
    studenten = get_studenten(request)
    if not studenten.exists():
        return JsonResponse({'gesamt_aufgaben': 0, 'bearbeitet': 0, 'korrekt': 0})
    nutzer_aufgaben = get_nutzer_aufgaben(studenten, request.GET.get('aufgabe'))
    gesamt_aufgaben = nutzer_aufgaben.count()
    bearbeitet, korrekt = get_bearbeitungsstand(nutzer_aufgaben)
    return JsonResponse({
        'gesamt_aufgaben': gesamt_aufgaben,
        'bearbeitet': bearbeitet,
        'korrekt': korrekt
    })

def get_studenten(request):
    """Liefert alle Studierenden eines Lehrers mit optionalen Filtern."""
    studenten = User.objects.filter(role='student', professor=request.user)
    semester_id = request.GET.get('semester')
    studiengang_id = request.GET.get('studiengang')
    if semester_id:
        studenten = studenten.filter(semester_id=semester_id)
    if studiengang_id:
        studenten = studenten.filter(studiengang_id=studiengang_id)
    return studenten

def get_nutzer_aufgaben(studenten, aufgabe_id):
    """Holt alle Nutzer-Aufgaben der gefilterten Studierenden."""
    nutzer_aufgaben = NutzerAufgabe.objects.filter(nutzer__in=studenten)
    if aufgabe_id:
        nutzer_aufgaben = nutzer_aufgaben.filter(aufgabe_id=aufgabe_id)
    return nutzer_aufgaben

def get_bearbeitungsstand(nutzer_aufgaben):
    """Berechnet die Anzahl bearbeiteter und korrekt gelöster Aufgaben."""
    bearbeitungsstand_data = nutzer_aufgaben.values('bearbeitungsstand').annotate(count=Count('id'))
    bearbeitet = sum(item['count'] for item in bearbeitungsstand_data if item['bearbeitungsstand'] in ['bearbeitet', 'korrekt'])
    korrekt = sum(item['count'] for item in bearbeitungsstand_data if item['bearbeitungsstand'] == 'korrekt')
    return bearbeitet, korrekt

@lehrkraft_required
def lehrer_filter_daten(request):
    # Lade alle Studierenden des Lehrers
    studenten = User.objects.filter(role='student', professor=request.user).values('id', 'first_name', 'last_name', 'username')
    studierende_liste = [
        {"id": s["id"], "name": f"{s['first_name']} {s['last_name']}".strip() or s["username"]}
        for s in studenten
    ]
    semesters = list(User.objects.filter(role='student').values('semester_id', 'semester__name').distinct())
    studiengaenge = list(User.objects.filter(role='student').values('studiengang_id', 'studiengang__name').distinct())
    aufgaben = list(Aufgabe_neu.objects.values('id', 'fragentyp_text'))

    return JsonResponse({
        'semesters': semesters,
        'studiengaenge': studiengaenge,
        'aufgaben': aufgaben,
        'studierende': studierende_liste  # Studierendenliste hinzufügen
    })


@login_required
def lehrer_studi_fortschritt(request, student_id):
    """Zeigt den Fortschritt eines einzelnen Studierenden für den Lehrer."""
    if request.user.role != 'teacher':
        return JsonResponse({'error': 'Keine Berechtigung'}, status=403)

    student = get_student(student_id, request.user)
    if not student:
        return JsonResponse({'error': 'Studierender nicht gefunden'}, status=404)

    nutzer_aufgaben = NutzerAufgabe.objects.filter(nutzer=student)
    gesamt_aufgaben = nutzer_aufgaben.count()

    bearbeitet, korrekt = get_bearbeitungsstand(nutzer_aufgaben)

    return JsonResponse({
        'studi_name': student.get_full_name(),
        'gesamt_aufgaben': gesamt_aufgaben,
        'bearbeitet': bearbeitet,
        'korrekt': korrekt
    })

def get_student(student_id, lehrer):
    """Gibt den Studierenden zurück, falls er dem Lehrer zugeordnet ist."""
    return User.objects.filter(id=student_id, role='student', professor=lehrer).first()

@login_required
def guv_uebersicht(request):
    # GuV-Konto holen (zur späteren Filterung)
    guv_konto = Konto.objects.get(name="GuV")
    
    # Filtere alle Konten außer GuV
    konten = Konto.objects.exclude(name="GuV")
    
    # Filtere Buchungen ohne GuV (SOLL und HABEN)
    buchungen = Buchung.objects.filter(nutzer=request.user).exclude(
        antwort_konten_soll__icontains="GuV"
    ).exclude(
        antwort_konten_haben__icontains="GuV"
    )

    # Anfangsbestände ohne GuV
    anfangsbestaende = Anfangsbestand.objects.filter(nutzer=request.user).exclude(konto=guv_konto)

    # Baue T-Konten-Struktur
    t_konten = build_t_konten(buchungen, anfangsbestaende)

    # ✅ Filtere das GuV-Konto auch aus den T-Konten heraus
    if "GuV" in t_konten:
        del t_konten["GuV"]

    # Verknüpfe Konten mit Kategorien
    konto_kategorien = {konto.name: konto.kategorie for konto in konten}

    return render(request, "posts/guv.html", {
        "t_konten": t_konten,
        "konten": konten,
        "konto_kategorien": konto_kategorien
    })


def generate_user_anfangsbestaende(user):
    """
    Erstellt anfangsbestaende für einen Nutzer, falls diese noch nicht existieren.
    """
    bestandskonten = Konto.objects.filter(kategorie="Bestandskonto")

    for konto in bestandskonten:
        # Prüfen, ob bereits ein Anfangsbestand existiert
        if not Anfangsbestand.objects.filter(nutzer=user, konto=konto).exists():
            betrag = random.choice(range(5000, 10001, 100))  # Zufälliger Wert (durch 100 teilbar)
            Anfangsbestand.objects.create(nutzer=user, konto=konto, betrag=betrag)

@login_required
def speichere_guv_ergebnis(request):
    if request.method == "POST":
        try:
            guv_result = float(request.POST.get("guv_result"))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Ungültiger Betrag"}, status=400)

        # GuV Konto holen oder erstellen
        guv_konto, created = Konto.objects.get_or_create(
            name="GuV",
            defaults={"kategorie": "Erfolgskonto"}
        )

        # SBK-Betrag speichern (mit Vorzeichen)
        Anfangsbestand.objects.update_or_create(
            nutzer=request.user,
            konto=guv_konto,
            defaults={"betrag": guv_result}
        )

        return JsonResponse({"success": True})
    return JsonResponse({"error": "Nur POST erlaubt"}, status=400)


@login_required
def bilanz_uebersicht(request):
    user = request.user

    # Alle Bestandskonten abrufen
    bestandskonten = Konto.objects.filter(kategorie="Bestandskonto").exclude(kategorie="Erfolgskonto")
    buchungen = Buchung.objects.filter(nutzer=request.user)
    anfangsbestaende = Anfangsbestand.objects.filter(nutzer=request.user)

    # T-Konten nur für Bestandskonten erstellen
    t_konten_all = build_t_konten(buchungen, anfangsbestaende)
    konto_kategorien = {konto.name: konto.unterkategorie for konto in bestandskonten}
    t_konten = {k: v for k, v in t_konten_all.items() if k in konto_kategorien}

    # Filteroptionen für Aktiv- und Passivkonten
    aktive_konten = [konto.name for konto in bestandskonten if konto.unterkategorie == "Aktiva"]
    passive_konten = [konto.name for konto in bestandskonten if konto.unterkategorie == "Passiva"]

    return render(request, "posts/bilanz.html", {
        "t_konten": t_konten,
        "aktive_konten": aktive_konten,
        "passive_konten": passive_konten,
        "bestandskonten": bestandskonten
    })

@login_required
def rechnungsuebersicht(request):
    user = request.user

    # Alle NutzerAufgaben für den aktuellen Nutzer abrufen
    nutzer_aufgaben = NutzerAufgabe.objects.filter(nutzer=user)

    rechnungsdaten = []

    for nutzer_aufgabe in nutzer_aufgaben:
        aufgabe = nutzer_aufgabe.aufgabe
        buchungen = Buchung.objects.filter(aufgabe=aufgabe, nutzer=user)
        
        # Anzahl Buchungen und Korrekturbuchungen zählen
        anzahl_buchungen = buchungen.count()
        anzahl_korrekturbuchungen = buchungen.filter(korrekturbuchung=True).count()

        rechnungsdaten.append({
            'rechnungsnr': aufgabe.id,
            'fragentyp_text': aufgabe.fragentyp_text,
            'anzahl_buchungen': anzahl_buchungen,
            'anzahl_korrekturbuchungen': anzahl_korrekturbuchungen,
            'aufgabenstatus': nutzer_aufgabe.bearbeitungsstand
        })

    return render(request, 'posts/rechnungsuebersicht.html', {'rechnungsdaten': rechnungsdaten})
