from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Unternehmen,Absender, AufgabeDetail, Aufgabe_neu, NutzerAufgabe, Buchung, Aufgabenkategorie, Mail, Konto, Anfangsbestand
from .forms import  Aufgabe_neu_Form, AufgabenkategorieForm, UnternehmenForm, AufgabeBearbeitenForm, AufgabeDetailBearbeitenForm,KontoForm
from django.contrib import messages
import json, random, hashlib
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from .absender import vornamen, nachnamen, straßen, staedte, plz, emailsuffix
import io
from decimal import Decimal
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

def admin_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            return HttpResponse(f'Fehlende Berechtigung <br><a href="{reverse("index")}">Zurück zur Startseite</a>')
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

@admin_required
def aufgabe_neu_erstellen(request):
    if request.method == 'POST':
        form = Aufgabe_neu_Form(request.POST)
        if form.is_valid():
            aufgabe = form.save()
            aufgabe.save()
            speichere_aufgabe_details(request, aufgabe)
            messages.success(request, 'Aufgabe und Details erfolgreich erstellt.')
            return redirect('frontpage')
        else:
            messages.error(request, 'Das Formular ist nicht gültig.')
    else:
        form = Aufgabe_neu_Form()
    
    konten = Konto.objects.all().order_by("name")  # Konten abrufen
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
    bezugs_konto_namen = request.POST.getlist('bezugs_konto[]')

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
        if i < len(bezugs_konto_namen) and bezugs_konto_namen[i]:  
            aufgabe_detail.bezugs_konto = bezugs_konto_namen[i]  # ✅ Speichert den Kontonamen direkt
            aufgabe_detail.save()

@login_required
def rechnung_detail_view(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    nutzer_aufgabe, _ = NutzerAufgabe.objects.get_or_create(
        aufgabe=aufgabe, nutzer=request.user,
        defaults={'soll_konto': '', 'haben_konto': '', 'betrag': 0, 'bearbeitungsstand': 'offen'}
    )
    #print(f"nutzeraufgabe:{nutzer_aufgabe}")
    #print(f"nutzeraufgabe:{type(aufgabe.rechnungsbetrag)}")
    #print(f"nutzeraufgabe:{type(Decimal(sum(nutzer_aufgabe.haben_betraege)))}")
    buchungen = Buchung.objects.filter(aufgabe=aufgabe, nutzer=request.user).order_by('buchung_id')
    next_aufgabe = Aufgabe_neu.objects.filter(id__gt=aufgabe_id).order_by('id').first()
    konten = Konto.objects.exclude(name="GuV").order_by('name')

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
        #'anschrift_kunde': aufgabe.anschrift_kunde,
        'eigene_ansicht': aufgabe.eigene_ansicht,
        'beschreibung': aufgabe.beschreibung,
        'rechnungsbetrag': Decimal(sum(nutzer_aufgabe.haben_betraege)),
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
        'block_buchung': block_buchung,
        'absender': nutzer_aufgabe.absender
    }

    return render(request, 'posts/rechnung.html', context)

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

def generiere_zufaellige_werte(aufgabe, tiefe=0):
    if tiefe < 50:

        soll_konten_queryset = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Soll")
        haben_konten_queryset = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Haben")

        soll_konten, soll_betraege, referenz_betraege_soll, haben_konten, haben_betraege, referenz_betraege_haben  = berechne_zufaellige_betraege(soll_konten_queryset, haben_konten_queryset)
        referenz_betraege = referenz_betraege_soll + referenz_betraege_haben
        
        summe_soll = sum(soll_betraege)
        summe_haben = sum(haben_betraege)
        differenz = summe_soll - summe_haben
        
        # Anpassung bei Differenz
        if differenz != 0:
            soll_betraege, haben_betraege = differenzausgleich_wertegenerierung(aufgabe, soll_konten, haben_konten, soll_betraege, haben_betraege, differenz)
            for betrag in soll_betraege:
                betrag = round(betrag,2)
            for betrag in haben_betraege:
                betrag = round(betrag,2)
                
            soll_betraege = [float(Decimal(str(betrag)).quantize(Decimal("0.01"))) for betrag in soll_betraege]
            haben_betraege = [float(Decimal(str(betrag)).quantize(Decimal("0.01"))) for betrag in haben_betraege]
            # Erneute Überprüfung nach der Anpassung
            summe_soll = round(sum(soll_betraege),2)
            summe_haben = round(sum(haben_betraege),2)

            # Überprüfung der angepassten Werte mit Referenzwerten
            for i, betrag in enumerate(soll_betraege + haben_betraege):
                referenzwert = referenz_betraege[i % len(referenz_betraege)]
                if not (referenzwert * 0.5 <= betrag <= referenzwert * 1.75):
                    print(f"Angepasster Betrag {betrag} außerhalb des zulässigen Bereichs ({referenzwert * 0.5} - {referenzwert * 1.75})")
                    return generiere_zufaellige_werte(aufgabe, tiefe + 1)

       # print(f"Erfolgreich generiert nach {tiefe} Versuchen")
        return {
            'soll_konten': soll_konten,
            'haben_konten': haben_konten,
            'soll_betraege': soll_betraege,
            'haben_betraege': haben_betraege
        }

def differenzausgleich_wertegenerierung(aufgabe, soll_konten, haben_konten, soll_betraege, haben_betraege, differenz):
    nicht_referenzierte_soll_konten = [
        konto for konto in soll_konten 
        if konto not in [k.bezugs_konto for k in AufgabeDetail.objects.filter(aufgabe=aufgabe) if k.bezugs_konto]
    ]
    nicht_referenzierte_haben_konten = [
        konto for konto in haben_konten 
        if konto not in [k.bezugs_konto for k in AufgabeDetail.objects.filter(aufgabe=aufgabe) if k.bezugs_konto]
    ]

    # Höchste Beträge und deren Indizes
    max_soll_index = soll_betraege.index(max(soll_betraege))
    max_haben_index = haben_betraege.index(max(haben_betraege))

    max_soll_konto = soll_konten[max_soll_index]
    max_haben_konto = haben_konten[max_haben_index]

    # Prüfen, ob die höchsten Werte referenziert sind
    max_soll_referenziert = max_soll_konto not in nicht_referenzierte_soll_konten
    max_haben_referenziert = max_haben_konto not in nicht_referenzierte_haben_konten
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

def berechne_zufaellige_betraege(soll_konten_queryset, haben_konten_queryset):
    #print("🔍 Starte Berechnung zufälliger Beträge...")
    soll_konten, haben_konten = [], []
    soll_betraege, haben_betraege = [], []
    referenz_betraege_soll,referenz_betraege_haben = [], []
    berechnete_werte = {}  # Speichert bereits berechnete Werte für Bezugskonten
    
    # Normale und Faktor-Konten trennen
    normale_soll_konten = soll_konten_queryset.exclude(formel_typ="faktor")
    faktor_soll_konten = soll_konten_queryset.filter(formel_typ="faktor")
    normale_haben_konten = haben_konten_queryset.exclude(formel_typ="faktor")
    faktor_haben_konten = haben_konten_queryset.filter(formel_typ="faktor")
    
    #print(f"Normale Soll-Konten: {list(normale_soll_konten)}")
    #print(f"Normale Haben-Konten: {list(normale_haben_konten)}")
    #print(f"Faktor Soll-Konten: {list(faktor_soll_konten)}")
    #print(f"Faktor Haben-Konten: {list(faktor_haben_konten)}")
    
    # Zuerst die normalen Konten berechnen
    for konto in normale_soll_konten.union(normale_haben_konten):
        referenz_betrag = konto.betrag
        min_betrag = referenz_betrag * 0.25
        max_betrag = referenz_betrag * 1.75
        zufallswert = random.randint(int(min_betrag), int(max_betrag))
        if konto in normale_haben_konten:
            haben_konten.append(konto.kontoname)
            haben_betraege.append(round(zufallswert,0))
            referenz_betraege_haben.append(zufallswert)
        else:
            soll_konten.append(konto.kontoname)
            soll_betraege.append(round(zufallswert,0))
            referenz_betraege_soll.append(zufallswert)
        berechnete_werte[konto.kontoname] = zufallswert  # Speichert den berechneten Wert
        #print(f"📌 Konto {konto.kontoname} erhält {zufallswert} (Referenzbetrag: {referenz_betrag})")
    
    # Faktor-Konten basierend auf berechneten Werten der Referenzkonten berechnen
    for konto in faktor_soll_konten.union(faktor_haben_konten):
        if konto.bezugs_konto in berechnete_werte:
            faktor_wert = round(berechnete_werte[konto.bezugs_konto] * konto.faktor, 2)
        else:
            # Falls das Bezugskonto nicht vorhanden ist, Standardwert setzen
            faktor_wert = round(random.randint(100, 1000) * konto.faktor, 2)
        if konto in faktor_haben_konten:
            haben_konten.append(konto.kontoname)
            haben_betraege.append(faktor_wert)
            referenz_betraege_haben.append(faktor_wert)
        else:
            soll_konten.append(konto.kontoname)
            soll_betraege.append(faktor_wert)
            referenz_betraege_soll.append(faktor_wert)

        berechnete_werte[konto.kontoname] = faktor_wert  # Speichert den berechneten Wert für zukünftige Berechnungen
        #print(f"🔗 Faktor-Konto {konto.kontoname} basiert auf {konto.bezugs_konto}, Wert: {faktor_wert}")
    
    #print("✅ Berechnung abgeschlossen!")
    return soll_konten, soll_betraege, referenz_betraege_soll, haben_konten, haben_betraege, referenz_betraege_haben

def speichere_nutzer_aufgabe(nutzer, aufgabe, zufaellige_werte):
    # Prüfe, ob bereits eine NutzerAufgabe existiert
    nutzer_aufgabe, created = NutzerAufgabe.objects.get_or_create(
        aufgabe=aufgabe,
        nutzer=nutzer,
        defaults={
            'soll_konten': zufaellige_werte['soll_konten'],
            'haben_konten': zufaellige_werte['haben_konten'],
            'soll_betraege': zufaellige_werte['soll_betraege'],
            'haben_betraege': zufaellige_werte['haben_betraege'],
            'bearbeitungsstand': 'offen',
        }
    )

    if not nutzer_aufgabe.absender:
        absender = generate_random_absender()
        nutzer_aufgabe.absender = absender
        nutzer_aufgabe.save(update_fields=["absender"])
        print(f"✅ Neuer Absender gesetzt für Nutzer {nutzer.username}, Aufgabe {aufgabe.id}: {absender.id}")
    else:
        print(f"⚠️ Nutzer {nutzer.username}, Aufgabe {aufgabe.id} hat bereits einen Absender: {nutzer_aufgabe.absender_id}")

    print(f"✅ Absender für {nutzer.username} - Aufgabe {aufgabe.id}: {nutzer_aufgabe.absender}")
    return nutzer_aufgabe

def berechne_naechsten_versuch(nutzer, aufgabe):
    letzter_mail_versuch = Mail.objects.filter(aufgabe=aufgabe, nutzer=nutzer).order_by('-versuch').first()
    letzter_buchung_versuch = Buchung.objects.filter(aufgabe=aufgabe, nutzer=nutzer).order_by('-versuch').first()

    hoechster_versuch = max(
        (letzter_mail_versuch.versuch if letzter_mail_versuch else 0),
        (letzter_buchung_versuch.versuch if letzter_buchung_versuch else 0)
    )
    return hoechster_versuch + 1

def erstelle_aufgaben_mail(nutzer, aufgabe, versuch, absender):
    #print(f"📧 Mail wird erstellt für {nutzer.username} - Aufgabe {aufgabe.id} - Versuch {versuch}")
    if versuch == 1:
        betreff = f"{aufgabe.fragentyp_text}"
    else:
        v = round((versuch/2) + 1,0)
        betreff = f"{aufgabe.fragentyp_text} Versuch {v}"
    mailtext = f"{aufgabe.mailtext}"

    Mail.objects.create(
        nutzer=nutzer,
        aufgabe=aufgabe,
        betreff=betreff,
        mailtext=mailtext,
        versuch=versuch,
        absender=absender,  # Speichert die Absender-Referenz
        status='nicht bearbeitet'
    )

def get_fallback_konten(aufgabe):
    soll_konto = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Soll").order_by('?').first()
    haben_konto = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Haben").order_by('?').first()
    return (soll_konto.kontoname if soll_konto else "Soll-Konto-Standard",
            haben_konto.kontoname if haben_konto else "Haben-Konto-Standard")

@admin_required
def unternehmen_verwalten(request):
    """ Zeigt eine Liste der Unternehmen an und ermöglicht das Hinzufügen. """
    if request.method == 'POST':
        form = UnternehmenForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Unternehmen erfolgreich hinzugefügt.")
            return redirect('posts:unternehmen_verwalten')
        else:
            messages.error(request, "Fehler beim Speichern des Unternehmens.")
    else:
        form = UnternehmenForm()

    unternehmen = Unternehmen.objects.all()
    return render(request, 'posts/neues_unternehmen.html', {'form': form, 'unternehmen': unternehmen})


def handle_post_request(request, form_class, redirect_url, template_name):
    if request.method == 'POST':
        result = handle_form_submission(request, form_class, "Erfolgreich gespeichert.", redirect_url)
        if result:
            return result
    form = form_class()
    return render(request, template_name, {'form': form})

@admin_required
def unternehmen_loeschen(request, unternehmen_id):
    """ Löscht ein Unternehmen und gibt eine Bestätigung aus. """
    unternehmen = get_object_or_404(Unternehmen, id=unternehmen_id)
    unternehmen.delete()
    messages.success(request, f"Das Unternehmen '{unternehmen.name}' wurde gelöscht.")
    return redirect('posts:unternehmen_verwalten')

@admin_required
def aufgabenkategorie_verwalten(request):
    """ Zeigt eine Liste der Kategorien an und ermöglicht das Hinzufügen. """
    if request.method == 'POST':
        form = AufgabenkategorieForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Kategorie erfolgreich hinzugefügt.")
            return redirect('posts:aufgabenkategorie_verwalten')
        else:
            messages.error(request, "Fehler beim Speichern der Kategorie.")
    else:
        form = AufgabenkategorieForm()

    aufgabenkategorien = Aufgabenkategorie.objects.all()
    return render(request, 'posts/neue_kategorie.html', {'form': form, 'aufgabenkategorien': aufgabenkategorien})

@admin_required
def aufgabenkategorie_loeschen(request, kategorie_id):
    """ Löscht eine Kategorie und gibt eine Bestätigung aus. """
    kategorie = get_object_or_404(Aufgabenkategorie, id=kategorie_id)
    kategorie.delete()
    messages.success(request, f"Die Kategorie '{kategorie.name}' wurde gelöscht.")
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
        aufgabe_id_mit_versuch = f"{buchung.aufgabe.id} {buchung.versuch})"

        if buchung.aufgabe.id not in aufgabe_farben:
            aufgabe_farben[buchung.aufgabe.id] = generate_color(buchung.aufgabe.id)

        farbe = aufgabe_farben[buchung.aufgabe.id]

        soll_konten = json.loads(buchung.antwort_konten_soll or "[]")
        haben_konten = json.loads(buchung.antwort_konten_haben or "[]")
        soll_betraege = json.loads(buchung.antwort_betrag_soll or "[]")
        haben_betraege = json.loads(buchung.antwort_betrag_haben or "[]")

        for konto, betrag in zip(soll_konten, soll_betraege):
            t_konten.setdefault(konto, {"soll": [], "haben": []})["soll"].append((aufgabe_id_mit_versuch, betrag, farbe))

        for konto, betrag in zip(haben_konten, haben_betraege):
            t_konten.setdefault(konto, {"soll": [], "haben": []})["haben"].append((aufgabe_id_mit_versuch, betrag, farbe))

    return t_konten

@admin_required
def aufgabe_bearbeiten(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    details = AufgabeDetail.objects.filter(aufgabe=aufgabe)

    if request.method == 'POST':
        result = handle_form_submission(request, AufgabeBearbeitenForm, "Aufgabe erfolgreich bearbeitet.", 'posts:aufgaben_verwalten', instance=aufgabe)
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
def korrekturbuchung_durchfuehren(request, buchung_id):
    buchung = get_object_or_404(Buchung, buchung_id=buchung_id)
    aufgabe = get_object_or_404(Aufgabe_neu, id=buchung.aufgabe_id)
    nutzeraufgabe = NutzerAufgabe.objects.get(aufgabe=aufgabe, nutzer=request.user)
    absender = get_object_or_404(Absender, id=nutzeraufgabe.absender_id)

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

    erstelle_aufgaben_mail(request.user, aufgabe, naechster_versuch+1, absender)
    messages.success(request, f'Korrekturbuchung im Versuch {naechster_versuch} erfolgreich durchgeführt.')
    return redirect('posts:rechnung_detail', aufgabe_id=buchung.aufgabe.id)

@login_required
def posteingang(request):
    mails = Mail.objects.filter(nutzer_id=request.user.id).order_by('-datum')
    #print(f"📨 nutzer_id {nutzer_id}")  # Debugging

    #print(f"Request user id{request.user.id}")  # Debugging

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

    mail_betreff = f"Korrekturbuchung - {aufgabenkategorie.name}"
    mail_text = (
        f"Sehr geehrte/r {nutzer.username},\n\n"
        f"Ihre Buchung zur Aufgabe '{aufgabe.fragentyp_text}' enthält einen Fehler. "
        "Bitte korrigieren Sie Ihre Eingaben über den folgenden Link:\n"
        f"http://localhost:8000{reverse('posts:rechnung_detail', args=[aufgabe.id])}\n\n"
        "Vielen Dank.\nIhr Buchhaltungsteam"
    )

    absender, _ = Absender.objects.get_or_create(
        name="SecureNet",
        email="SecureNet@gmail.com",
        straße="Treskowallee 8",
        stadt="Berlin",
        plz="10318"
    )
    # Neue Mail mit dem korrekten Versuchswert erstellen
    Mail.objects.create(
        nutzer=nutzer,
        aufgabe=aufgabe,
        betreff=mail_betreff,
        absender=absender,
        mailtext=mail_text,
        versuch=naechster_versuch,  # Dynamischer Versuchswert
        status='nicht bearbeitet'
    )

@admin_required
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

@admin_required
def konto_bearbeiten(request, konto_id):
    konto = get_object_or_404(Konto, id=konto_id).order_by("name")

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


@admin_required
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

@lehrkraft_required
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
    # Definiere relevante Konten
    relevante_konten_namen = [
        "Kasse", "Bank", "Forderungen aLuL", "Warenbestand", "Gebäude",
        "Technische Anlagen und Maschinen", "Büromaterialien", "Verbindlichkeiten aLuL",
        "Rückstellungen"
    ]

    aktiva_summe = 0
    passiva_summe = 0

    # 🔎 Prüfe, ob Konten existieren
    for konto_name in relevante_konten_namen:
        konto = Konto.objects.filter(name=konto_name).first()
        if not konto:
            continue  # Überspringe dieses Konto
        if Anfangsbestand.objects.filter(nutzer=user, konto=konto).exists():
            continue  # Überspringe, falls bereits ein Anfangsbestand existiert
        betrag = random.randint(5000, 20000)  # Zufallsbetrag
        Anfangsbestand.objects.create(nutzer=user, konto=konto, betrag=betrag)

        # Aktiva oder Passiva Summe berechnen
        if konto.unterkategorie == "Aktiva":
            aktiva_summe += betrag
        else:
            passiva_summe += betrag

    # 🔎 Eigenkapital berechnen
    eigenkapital_konto = Konto.objects.filter(name="Eigenkapital").first()
    if not eigenkapital_konto:
        return  # Abbrechen, wenn Eigenkapital-Konto fehlt

    eigenkapital_betrag = aktiva_summe - passiva_summe
    if not Anfangsbestand.objects.filter(nutzer=user, konto=eigenkapital_konto).exists():
        Anfangsbestand.objects.create(nutzer=user, konto=eigenkapital_konto, betrag=eigenkapital_betrag)

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

def generate_random_absender():
    vorname = random.choice(vornamen)
    nachname = random.choice(nachnamen)
    email = f"{nachname.lower()}@{random.choice(emailsuffix)}"
    print(f"email:{email}")
    straße = f"{random.choice(straßen)} {random.randint(1, 100)}"
    stadt = f"{random.choice(staedte)}"
    voller_name = f"{vorname} {nachname}"

    # Zufällige Kombination erstellen
    absender, created = Absender.objects.get_or_create(
        name=voller_name,
        email=email,
        straße=straße,
        stadt=stadt,
        plz=random.choice(plz)
    )
    print(f"📌 Generierter Absender: {absender.name}, ID: {absender.id}, Neu erstellt: {created}")    
    return absender

@lehrkraft_required
def aufgaben_verwalten(request):
    """ Zeigt eine Liste aller Aufgaben und ermöglicht das Löschen. """
    aufgaben = Aufgabe_neu.objects.all()
    return render(request, 'posts/aufgaben_verwalten.html', {'aufgaben': aufgaben})

@admin_required
def aufgabe_loeschen(request, aufgabe_id):
    """ Löscht eine Aufgabe und gibt eine Bestätigung aus. """
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    aufgabe.delete()
    messages.success(request, f"Die Aufgabe '{aufgabe.fragentyp_text}' wurde gelöscht.")
    return redirect('posts:aufgaben_verwalten')