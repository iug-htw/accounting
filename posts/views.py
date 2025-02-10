from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Unternehmen, AufgabeDetail, Aufgabe_neu, NutzerAufgabe, Buchung, Aufgabenkategorie, Mail
from .forms import  Aufgabe_neu_Form, AufgabenkategorieForm, UnternehmenForm, AufgabeBearbeitenForm, AufgabeDetailBearbeitenForm
from django.contrib import messages
import json, random
from django.urls import reverse
from django.http import HttpResponse
from django.core.mail import send_mail

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
    return render(request, 'posts/aufgabe_erstellen.html', {'form': form})

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
    soll_konten_nutzer = json.loads(buchung.antwort_konten_soll)
    haben_konten_nutzer = json.loads(buchung.antwort_konten_haben)
    betraege_soll_nutzer = json.loads(buchung.antwort_betrag_soll)

    return (
        nutzer_aufgabe.soll_konto in soll_konten_nutzer and
        nutzer_aufgabe.haben_konto in haben_konten_nutzer and
        nutzer_aufgabe.betrag in betraege_soll_nutzer
    )

def rechnung_view(request):
    aufgabe = Aufgabe_neu.objects.first()  # Beispiel für eine zufällige Aufgabe
    return render(request, 'posts/rechnung.html', {'aufgabe': aufgabe})

@login_required
def rechnung_detail_view(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    nutzer_aufgabe, _ = NutzerAufgabe.objects.get_or_create(
        aufgabe=aufgabe, nutzer=request.user,
        defaults={'soll_konto': '', 'haben_konto': '', 'betrag': 0, 'geloest': False}
    )

    buchungen = Buchung.objects.filter(aufgabe=aufgabe, nutzer=request.user).order_by('buchung_id')
    next_aufgabe = Aufgabe_neu.objects.filter(id__gt=aufgabe_id).order_by('id').first()

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
        'buchung_status': buchung_status
    })

def handle_nutzer_buchung(request, aufgabe):
    soll_konten = request.POST.getlist('soll_konto[]')
    haben_konten = request.POST.getlist('haben_konto[]')
    betraege_soll = request.POST.getlist('soll_betrag[]')
    betraege_haben = request.POST.getlist('haben_betrag[]')

    # Erstelle oder speichere die Buchung und gib sie zurück
    buchung = Buchung.objects.create(
        aufgabe=aufgabe,
        nutzer=request.user,
        antwort_konten_soll=json.dumps(soll_konten),
        antwort_konten_haben=json.dumps(haben_konten),
        antwort_betrag_soll=json.dumps([float(b) for b in betraege_soll]),
        antwort_betrag_haben=json.dumps([float(b) for b in betraege_haben]),
        korrekturbuchung=False
    )
    return buchung

def is_buchung_korrekt(buchung, nutzer_aufgabe):
    soll_konten_nutzer = json.loads(buchung.antwort_konten_soll)
    haben_konten_nutzer = json.loads(buchung.antwort_konten_haben)
    betraege_soll_nutzer = json.loads(buchung.antwort_betrag_soll)

    return (
        nutzer_aufgabe.soll_konto in soll_konten_nutzer and
        nutzer_aufgabe.haben_konto in haben_konten_nutzer and
        nutzer_aufgabe.betrag in betraege_soll_nutzer
    )

@login_required
def zufaellige_aufgabe_zuweisen(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    zufaelliger_betrag = random.randint(int(aufgabe.min_wert), int(aufgabe.max_wert))
    soll_konto, haben_konto = get_fallback_konten(aufgabe)

    NutzerAufgabe.objects.update_or_create(
        aufgabe=aufgabe,
        nutzer=request.user,
        defaults={
            'soll_konto': soll_konto,
            'haben_konto': haben_konto,
            'betrag': zufaelliger_betrag,
            'geloest': False
        }
    )
    # Mail erstellen
    betreff = f"Offene Rechnung: {aufgabe.fragentyp.name}"
    mailtext = aufgabe.mailtext

    Mail.objects.create(
        nutzer=request.user,
        aufgabe=aufgabe,
        betreff=betreff,
        mailtext=mailtext
    )
    messages.success(request, "Die Aufgabe wurde erfolgreich zugewiesen!")
    return redirect('posts:rechnung_detail', aufgabe_id=aufgabe.id)


def get_fallback_konten(aufgabe):
    soll_konto = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Soll").first()
    haben_konto = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Haben").first()
    return (soll_konto.kontoname if soll_konto else "Unbekannt",
            haben_konto.kontoname if haben_konto else "Unbekannt")


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
    create_buchung(
        aufgabe=buchung.aufgabe,
        nutzer=request.user,
        soll_konten=json.loads(buchung.antwort_konten_haben),
        haben_konten=json.loads(buchung.antwort_konten_soll),
        betraege_soll=json.loads(buchung.antwort_betrag_haben),
        betraege_haben=json.loads(buchung.antwort_betrag_soll),
        korrekturbuchung=True
    )
    messages.success(request, 'Korrekturbuchung erfolgreich durchgeführt.')
    return redirect('posts:rechnung_detail', aufgabe_id=buchung.aufgabe.id)

@login_required
def posteingang(request):
    mails = Mail.objects.filter(nutzer=request.user).order_by('-datum')
    return render(request, 'posts/posteingang.html', {'mails': mails})

@login_required
def mail_detail(request, mail_id):
    mail = get_object_or_404(Mail, id=mail_id, nutzer=request.user)
    aufgabe_link = reverse('posts:rechnung_detail', args=[mail.aufgabe.id])
    return render(request, 'posts/mail_detail.html', {
        'mail': mail,
        'aufgabe_link': aufgabe_link
    })

def send_korrektur_mail(nutzer, aufgabe, aufgabenkategorie):
    mail_betreff = f"Anfrage Korrekturbuchung - {aufgabenkategorie.name}"
    mail_text = (
        f"Sehr geehrte/r {nutzer.username},\n\n"
        f"Ihre Buchung zur Aufgabe '{aufgabe.fragentyp_text}' enthält einen Fehler. "
        "Bitte korrigieren Sie Ihre Eingaben über den folgenden Link:\n"
        f"http://localhost:8000{reverse('posts:rechnung_detail', args=[aufgabe.id])}\n\n"
        "Vielen Dank.\nIhr Buchhaltungsteam"
    )

    # Speichern der Mail im Postfach
    Mail.objects.create(
        nutzer=nutzer,
        aufgabe=aufgabe,
        betreff=mail_betreff,
        mailtext=mail_text,
    )

    # Optionale echte E-Mail-Versendung
    send_mail(
        mail_betreff,
        mail_text,
        'system@secure-net.de',  # Absender
        [nutzer.email],
        fail_silently=True,
    )
