from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Unternehmen, AufgabeDetail, Aufgabe_neu, NutzerAufgabe, Buchung, Aufgabenkategorie, Mail, Konto
from .forms import  Aufgabe_neu_Form, AufgabenkategorieForm, UnternehmenForm, AufgabeBearbeitenForm, AufgabeDetailBearbeitenForm,KontoForm
from django.contrib import messages
import json, random
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.core.mail import send_mail
from django.db.models import Count
from django.contrib.auth import get_user_model

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
    kontonamen = request.POST.getlist('kontoname[]')
    soll_haben = request.POST.getlist('soll_haben[]')
    betraege = request.POST.getlist('betrag[]')
    monatsangaben = request.POST.getlist('monatsangabe[]')
    monate = request.POST.getlist('monat[]')

    for i in range(len(kontonamen)):
        AufgabeDetail.objects.create(
            aufgabe=aufgabe,
            kontoname=kontonamen[i],
            soll_haben=soll_haben[i],
            betrag=float(betraege[i]),
            monatsangabe=(monatsangaben[i].lower() == 'true'),
            monat=(int(monate[i]) if monate[i] else None)
        )

def is_buchung_korrekt(buchung, nutzer_aufgabe):
    # JSON-Daten der Buchung laden
    soll_konten_nutzer = [konto.strip() for konto in json.loads(buchung.antwort_konten_soll)]
    haben_konten_nutzer = [konto.strip() for konto in json.loads(buchung.antwort_konten_haben)]
    betraege_soll_nutzer = [round(float(betrag), 0) for betrag in json.loads(buchung.antwort_betrag_soll)]
    betraege_haben_nutzer = [round(float(betrag), 0) for betrag in json.loads(buchung.antwort_betrag_haben)]

    # Erwartete Werte aus der Nutzeraufgabe
    soll_konto_aufgabe = nutzer_aufgabe.soll_konto.strip()
    haben_konto_aufgabe = nutzer_aufgabe.haben_konto.strip()
    betrag_aufgabe = round(float(nutzer_aufgabe.betrag), 0)

    # Prüfen, ob Soll- und Haben-Konten korrekt sind
    soll_konto_korrekt = soll_konto_aufgabe in soll_konten_nutzer
    haben_konto_korrekt = haben_konto_aufgabe in haben_konten_nutzer
    betrag_korrekt = betrag_aufgabe in betraege_soll_nutzer

    # Ergebnis zurückgeben: Alle drei Bedingungen müssen erfüllt sein
    return soll_konto_korrekt and haben_konto_korrekt and betrag_korrekt


def rechnung_view(request):
    aufgabe = Aufgabe_neu.objects.first()  # Beispiel für eine zufällige Aufgabe
    return render(request, 'posts/rechnung.html', {'aufgabe': aufgabe})

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

    buchung_status = [
        {'buchung': buchung, 'korrekt': is_buchung_korrekt(buchung, nutzer_aufgabe)}
        for buchung in buchungen
    ]

    return render(request, 'posts/rechnung.html', {
        'aufgabe': aufgabe,
        'nutzer_aufgabe': nutzer_aufgabe,
        'next_aufgabe': next_aufgabe,
        'buchungen': buchungen,
        'buchung_status': buchung_status,
        'konten': konten
    })

def update_buchung_status(buchung, ist_korrekt):
    if ist_korrekt:
        buchung.status = 'korrekt'
    else:
        buchung.status = 'bearbeitet'
    buchung.save()

def handle_nutzer_buchung(request, aufgabe):
    # Den höchsten bisherigen Versuch ermitteln
    letzte_buchung = Buchung.objects.filter(aufgabe=aufgabe, nutzer=request.user).order_by('-versuch').first()
    neuer_versuch = (letzte_buchung.versuch + 1) if letzte_buchung else 1

    # Neue Buchung mit korrektem `versuch` erstellen
    buchung = Buchung.objects.create(
        aufgabe=aufgabe,
        nutzer=request.user,
        antwort_konten_soll=json.dumps(request.POST.getlist('soll_konto[]')),
        antwort_konten_haben=json.dumps(request.POST.getlist('haben_konto[]')),
        antwort_betrag_soll=json.dumps(request.POST.getlist('soll_betrag[]')),
        antwort_betrag_haben=json.dumps(request.POST.getlist('haben_betrag[]')),
        status='bearbeitet',
        versuch=neuer_versuch  # Hier wird der Versuch korrekt gezählt
    )
    nutzer_aufgabe = NutzerAufgabe.objects.get(aufgabe=aufgabe, nutzer=request.user)

    if is_buchung_korrekt(buchung, nutzer_aufgabe):
        update_buchung_status(buchung, ist_korrekt=True)
        nutzer_aufgabe.bearbeitungsstand = 'korrekt'  # Setzt das Feld auf 1 (True)
    else:
        update_buchung_status(buchung, ist_korrekt=False)
        nutzer_aufgabe.bearbeitungsstand = 'bearbeitet'

    nutzer_aufgabe.save()
    return buchung

    # Richtigkeit prüfen und ggf. Korrekturmail senden
    nutzer_aufgabe = NutzerAufgabe.objects.get(aufgabe=aufgabe, nutzer=request.user)
    if is_buchung_korrekt(buchung, nutzer_aufgabe):
        update_buchung_status(buchung, ist_korrekt=True)
    else:
        update_buchung_status(buchung, ist_korrekt=False)
        

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

def generiere_zufaellige_werte(aufgabe):
    soll_konto, haben_konto = get_fallback_konten(aufgabe)
    zufaelliger_betrag = round(random.uniform(aufgabe.min_wert or 100, aufgabe.max_wert or 1000), 0)
    return {'soll_konto': soll_konto, 'haben_konto': haben_konto, 'betrag': zufaelliger_betrag}

def speichere_nutzer_aufgabe(nutzer, aufgabe, zufaellige_werte):
    nutzer_aufgabe, created = NutzerAufgabe.objects.get_or_create(
        aufgabe=aufgabe,
        nutzer=nutzer,
        defaults={
            'soll_konto': zufaellige_werte['soll_konto'],
            'haben_konto': zufaellige_werte['haben_konto'],
            'betrag': zufaellige_werte['betrag'],
            'bearbeitungsstand': 'offen'
        }
    )
    
    if not created:
        nutzer_aufgabe.soll_konto = zufaellige_werte['soll_konto']
        nutzer_aufgabe.haben_konto = zufaellige_werte['haben_konto']
        nutzer_aufgabe.betrag = zufaellige_werte['betrag']
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
    betreff = f"Neue Aufgabe Versuch {versuch}"
    mailtext = f"Bitte bearbeiten Sie die Aufgabe: {aufgabe.fragentyp_text}"

    Mail.objects.create(
        nutzer=nutzer,
        aufgabe=aufgabe,
        betreff=betreff,
        mailtext=mailtext,
        versuch=versuch,
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
def hauptbuch(request):
    buchungen = Buchung.objects.filter(nutzer=request.user)
    t_konten = build_t_konten(buchungen)
    return render(request, 'posts/hauptbuch.html', {'t_konten': t_konten})

def build_t_konten(buchungen):
    t_konten = {}
    for buchung in buchungen:
        soll_konten, haben_konten = json.loads(buchung.antwort_konten_soll or "[]"), json.loads(buchung.antwort_konten_haben or "[]")
        soll_betraege, haben_betraege = json.loads(buchung.antwort_betrag_soll or "[]"), json.loads(buchung.antwort_betrag_haben or "[]")

        for konto, betrag in zip(soll_konten, soll_betraege):
            t_konten.setdefault(konto, {"soll": [], "haben": []})["soll"].append((buchung.buchung_id, betrag))
        for konto, betrag in zip(haben_konten, haben_betraege):
            t_konten.setdefault(konto, {"soll": [], "haben": []})["haben"].append((buchung.buchung_id, betrag))

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
        else:
            mail.status = 'nicht bearbeitet'
        mail.save()

    return render(request, 'posts/posteingang.html', {'mails': mails})

@login_required
def mail_detail(request, mail_id):
    mail = get_object_or_404(Mail, id=mail_id, nutzer=request.user)
    mail.status = 'bearbeitet'
    mail.save()

    aufgabe_link = reverse('posts:rechnung_detail', args=[mail.aufgabe.id])
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

def konten_verwalten(request):
    if request.method == 'POST':
        form = KontoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Konto erfolgreich hinzugefügt.")
            return redirect('posts:konten_verwalten')
    else:
        form = KontoForm()
    konten = Konto.objects.all()
    return render(request, 'posts/konten_verwalten.html', {'form': form, 'konten': konten})

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
