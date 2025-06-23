
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render,redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Unternehmen,Absender, AufgabeDetail, Aufgabe_neu, NutzerAufgabe, Buchung, Aufgabenkategorie, Mail, Konto, Anfangsbestand, Kontenplan
from .forms import  Aufgabe_neu_Form, AufgabenkategorieForm, UnternehmenForm, AufgabeBearbeitenForm, AufgabeDetailBearbeitenForm,KontoForm,AufgabeImportForm
from django.contrib import messages
import json, random, hashlib,openpyxl,threading,requests
from random import choice
from openpyxl import load_workbook
from django.urls import reverse
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.core.mail import send_mail
from django.db.models import Count, Q, F
from django.contrib.auth import get_user_model
from .absender import vornamen, nachnamen, straßen, staedte, plz, emailsuffix
from decimal import Decimal  
from collections import defaultdict
from django.utils.html import format_html
from django.views.decorators.http import require_GET
from decouple import config
from django.utils.translation import gettext as _
#passt


def safe_parse(val):
    if isinstance(val, str):
        return json.loads(val or "[]")
    return val or []
# Für Lehrkräfte
def lehrkraft_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.role == 'teacher' or request.user.is_superuser):
            return view_func(request, *args, **kwargs)
        else:
           return fehlende_berechtigung_response()
    return _wrapped_view_func

# Für Studierende
def student_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != 'student':
            return fehlende_berechtigung_response()
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func

def admin_required(view_func):
    def _wrapped_view_func(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            return fehlende_berechtigung_response()
    return _wrapped_view_func

def fehlende_berechtigung_response():
    return HttpResponse(
        _('Fehlende Berechtigung<br><a href="%(link)s">Zurück zur Startseite</a>') % {
            "link": reverse("index")
        }
    )

def handle_form_submission(request, form_class, success_message, redirect_url, instance=None):
    form = form_class(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        messages.success(request, success_message)
        return redirect(redirect_url)
    else:
        messages.error(request, _("Das Formular ist nicht gültig."))
        return None

@lehrkraft_required
def aufgabe_neu_erstellen(request):
    if request.method == 'POST':
        form = Aufgabe_neu_Form(request.POST, user=request.user)
        if form.is_valid():
            aufgabe = form.save(commit=False)
            aufgabe.ersteller = request.user.id
            aufgabe.rechnungsnummer = f"RE-{random.randint(10000, 99999)}"
            kontenplan = form.cleaned_data['kontenplan']
            aufgabe.aufgabeninfo = form.cleaned_data.get('aufgabeninfo', '')
            aufgabe.save()
            speichere_aufgabe_details(request, aufgabe, kontenplan)
            messages.success(request, _("Aufgabe und Details erfolgreich erstellt."))
            return redirect('frontpage')
        else:
            messages.error(request, _("Das Formular ist nicht gültig."))
    else:
        form = Aufgabe_neu_Form(user=request.user)

    konten = Konto.objects.filter(
        Q(kontenplan__nutzer=request.user) | Q(kontenplan__nutzer__is_superuser=True)
    ).order_by("name")
    return render(request, 'posts/aufgabe_erstellen.html', {'form': form, 'konten': konten})


@lehrkraft_required
def aufgabe_import_form(request):
    if request.method == "POST":
        form = AufgabeImportForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            kontenplan = form.cleaned_data['kontenplan']
            excel_datei = request.FILES['excel_datei']
            wb = load_workbook(excel_datei)
            sheet = wb.active

            erfolgreich = []
            fehlgeschlagen = []

            # WICHTIG: Die Felder aus dem abgeschickten Formular lesen
            unternehmen = form.cleaned_data['unternehmen_kategorie']
            fragentyp = form.initial.get('fragentyp')
            unterkategorie = form.cleaned_data.get('unterkategorie')
            fragentyp_text = form.cleaned_data.get('fragentyp_text', 'Bitte bearbeiten Sie die Aufgabe')
            mailtext = form.cleaned_data.get('mailtext', 'Sehr geehrte Damen und Herren, bitte bearbeiten Sie die folgende Aufgabe.')
            feedback_konto_falsch = form.cleaned_data.get('feedback_konto_falsch', 'Bitte prüfen Sie das gewählte Konto.')
            feedback_betrag_falsch = form.cleaned_data.get('feedback_betrag_falsch', 'Bitte prüfen Sie den Betrag.')
            nutzungsdauer = form.cleaned_data.get('nutzungsdauer', 0)
            verabschiedung = form.cleaned_data.get('verabschiedung', 'Mit freundlichen Grüßen')
            kontakt = form.cleaned_data.get('kontakt', 'Tel: 01234 567890\nE-Mail: info@unternehmen.de')

            for zeilennr, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                beschreibung = row[0]
                rechnungsansicht = row[1]
                if rechnungsansicht == 1:
                    rechnungstyp = 'non'
                else:
                    rechnungstyp = 'intern'
                immer_feedback = row[2]
                zahlweise = row[3]

                fehlendes_konto = False
                konto_infos = []

                for i in range(4, len(row), 3):
                    konto_name = row[i]
                    soll_haben = row[i+1]
                    betrag = row[i+2]

                    if not konto_name or not soll_haben or betrag is None:
                        break

                    try:
                        # Versuche zuerst die Kontonummer (falls Zahl angegeben)
                        konto_nummer = int(konto_name)
                        konto = Konto.objects.filter(
                            kontonummer=konto_nummer,
                            kontenplan=kontenplan
                        ).first()
                    except (ValueError, TypeError):
                        # Falls keine Zahl: Suche über den Namen (wie bisher)
                        konto = Konto.objects.filter(
                            name__iexact=str(konto_name).strip(),
                            kontenplan=kontenplan
                        ).first()

                    if not konto:
                        fehlendes_konto = True
                        break

                    konto_infos.append((konto, soll_haben.strip(), float(betrag)))

                if fehlendes_konto:
                    fehlgeschlagen.append((zeilennr, beschreibung))
                    continue
                aufgabeninfo = form.cleaned_data.get('aufgabeninfo', '')
                beschreibung_textkörper = ""
                beschreibung_final = ""
                ebk_konten = [konto for konto, _, _ in konto_infos if "EBK" in konto.name.upper() or "ERÖFFNUNGSBILANZ" in konto.name.upper()]
                sbk_konten = [konto for konto, _, _ in konto_infos if "SBK" in konto.name.upper() or "SCHLUSSBILANZ" in konto.name.upper()]
                nicht_ebk_sbk_konten = [konto for konto, _, _ in konto_infos if konto not in ebk_konten + sbk_konten]

                if ebk_konten:
                    anderes_konto = nicht_ebk_sbk_konten[0].name if nicht_ebk_sbk_konten else "unbekanntes Konto"
                    beschreibung_textkörper = (
                        "Am Geschäftsjahresbeginn wurde das Anfangsvermögen erfasst, um die Buchhaltung des Unternehmens korrekt zu starten. "
                        "Erstelle die richtige Eröffnungsbilanz für das folgende Konto: "
                    )
                    beschreibung_final = f"\n{beschreibung_textkörper}\n{anderes_konto}."
                elif sbk_konten:
                    anderes_konto = nicht_ebk_sbk_konten[0].name if nicht_ebk_sbk_konten else "unbekanntes Konto"
                    beschreibung_textkörper = (
                        "Zum Geschäftsjahresende wurde die Vermögens- und Schuldenlage erfasst. "
                        "Diese Transaktion fließt in die Schlussbilanz ein und bildet die Grundlage für die Erfolgsrechnung."
                        "Folgendes Konto wird abgeschlossen: "
                    )
                    beschreibung_final = f"\n{beschreibung_textkörper}\n{anderes_konto}."
                else:
                    beschreibung_textkörper = (
                        "Diese Transaktion wurde im laufenden Geschäftsjahr vorgenommen und betrifft eine übliche Geschäftstätigkeit. "
                        "Verbuchen Sie diesen Geschäftsvorfall. "
                    )
                    beschreibung_final = f"\n{beschreibung_textkörper}\n{beschreibung}.\n"

                # Neue Aufgabe pro Zeile erstellen
                neue_aufgabe = Aufgabe_neu.objects.create(
                    unternehmen_kategorie=unternehmen,
                    rechnungstyp=rechnungstyp,
                    fragentyp=fragentyp,
                    unterkategorie=unterkategorie,
                    fragentyp_text=fragentyp_text,
                    mailtext=mailtext,
                    feedback_konto_falsch=feedback_konto_falsch,
                    feedback_betrag_falsch=feedback_betrag_falsch,
                    nutzungsdauer=nutzungsdauer,
                    verabschiedung=verabschiedung,
                    kontakt=kontakt,
                    aufgabeninfo=aufgabeninfo,
                    beschreibung_de=beschreibung_final,
                    beschreibung_en=f"\nThis transaction was carried out in the current fiscal year and relates to regular business operations. Record this business transaction.\n{beschreibung}\n",
                    zahlweise=zahlweise,
                    rechnungsbetrag=0,
                    ersteller=request.user.id,
                    immer_feedback=immer_feedback,
                    rechnungsnummer=f"RE-{random.randint(10000, 99999)}"
                )

                # Konten zuordnen
                for konto, soll_haben, betrag in konto_infos:
                    aufgabe_detail = AufgabeDetail.objects.create(
                        aufgabe=neue_aufgabe,
                        konto=konto,
                        soll_haben=soll_haben,
                        kontenplan=kontenplan,
                        betrag=betrag,
                    )
                    if konto.bilanzposition_nummer:
                        aufgabe_detail.bilanzposition = konto.bilanzposition_nummer
                        aufgabe_detail.save()

                erfolgreich.append((zeilennr, beschreibung))

            # Feedback
            if erfolgreich:
                messages.success(request, _("%(anzahl)d Aufgaben erfolgreich importiert.") % {"anzahl": len(erfolgreich)})
            if fehlgeschlagen:
                fehlermeldung = ", ".join(f"Zeile {z} ('{b}')" for z, b in fehlgeschlagen)
                messages.error(request, _("%(anzahl)d Aufgaben konnten nicht importiert werden: %(fehler)s") % {"anzahl": len(fehlgeschlagen), "fehler": fehlermeldung})
            return redirect('posts:aufgaben_verwalten')
        else:
            messages.error(request, _("Fehlerhafte Eingaben oder keine Datei hochgeladen."))

    else:
        beispiel_unternehmen = Unternehmen.objects.first()
        beispiel_kategorie = Aufgabenkategorie.objects.first()
        initial = {
            'unternehmen_kategorie': beispiel_unternehmen.id if beispiel_unternehmen else None,
            'fragentyp': beispiel_kategorie.id if beispiel_kategorie else None,
            'fragentyp_text': 'Bitte bearbeiten Sie die beiliegende Rechnung',
            'mailtext': 'Sehr geehrte Damen und Herren,\ndie folgende Rechnung ist eingegangen und muss bearbeitet werden.',
            'feedback_konto_falsch': 'Bitte prüfen Sie das gewählte Konto.',
            'feedback_betrag_falsch': 'Bitte prüfen Sie den Betrag.',
            'nutzungsdauer': 0,
            'verabschiedung': 'Mit freundlichen Grüßen',
            'kontakt': 'Tel: 01234 567890\nE-Mail: info@unternehmen.de',
        }
        form = AufgabeImportForm(initial=initial, user=request.user)

    return render(request, 'posts/aufgabe_import_form.html', {'form': form})

@login_required
def kontenplan_konten_laden(request):
    kontenplan_id = request.GET.get('kontenplan_id')
    konten = Konto.objects.filter(kontenplan_id=kontenplan_id).order_by('name')

    konten_liste = [{'id': konto.id, 'name': konto.name} for konto in konten]

    return JsonResponse({'konten': konten_liste})

def speichere_aufgabe_details(request, aufgabe,kontenplan):
    konto_ids = request.POST.getlist('konto_id[]')
    soll_haben = request.POST.getlist('soll_haben[]')
    betraege = request.POST.getlist('betrag[]')

    # Neue Felder für Abhängigkeiten

    aufgabe_details = []  # Zwischenspeicher für bulk_create()

    # **Erster Schritt: Speichere alle Details ohne Bezugskonto**
    for i in range(len(konto_ids)):
        konto = Konto.objects.get(id=konto_ids[i])
        aufgabe_detail = AufgabeDetail.objects.create(
            aufgabe=aufgabe,
            konto=konto,
            soll_haben=soll_haben[i],
            betrag=float(betraege[i]) if betraege[i] else None,
            kontenplan=kontenplan,
        )
        aufgabe_details.append(aufgabe_detail)

@login_required
def rechnung_detail_view(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    nutzer_aufgabe, _ = NutzerAufgabe.objects.get_or_create(
        aufgabe=aufgabe, nutzer=request.user,
        defaults={'soll_konto': '', 'haben_konto': '', 'betrag': 0, 'bearbeitungsstand': 'offen'}
    )
    kontenplan = (
    AufgabeDetail.objects.filter(aufgabe=aufgabe)
    .values_list("kontenplan_id", flat=True)
    .first()
    )
    #print(f"nutzeraufgabe:{nutzer_aufgabe}")
    #print(f"nutzeraufgabe:{type(aufgabe.rechnungsbetrag)}")
    #print(f"nutzeraufgabe:{type(Decimal(sum(nutzer_aufgabe.haben_betraege)))}")
    buchungen = Buchung.objects.filter(aufgabe=aufgabe, nutzer=request.user).order_by('buchung_id')
    next_aufgabe = Aufgabe_neu.objects.filter(id__gt=aufgabe_id).order_by('id').first()
    konten = Konto.objects.exclude(name="GuV").order_by('kontonummer', 'name')

    if request.method == 'POST':
        buchung = handle_nutzer_buchung(request, aufgabe)
        if not is_buchung_korrekt(buchung, nutzer_aufgabe):
            send_korrektur_mail(request.user, aufgabe, request)
        return redirect('frontpage')

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
            'is_letzte_falsche': buchung == letzte_buchung and block_buchung,
            'soll_konten_liste': safe_parse(buchung.antwort_konten_soll),
            'haben_konten_liste': safe_parse(buchung.antwort_konten_haben),
            'soll_betraege_liste': safe_parse(buchung.antwort_betrag_soll),
            'haben_betraege_liste': safe_parse(buchung.antwort_betrag_haben),
            'original_soll_konten': safe_parse(buchung.original_konten_soll),
            'original_haben_konten': safe_parse(buchung.original_konten_haben),
        })

    # Template für den Rechnungstyp auswählen
    template_map = {
        'eingehend': 'posts/rechnungen/rechnung_eingehend.html',
        'ausgehend': 'posts/rechnungen/rechnung_ausgehend.html',
        'intern': 'posts/rechnungen/rechnung_intern.html',
        'non': 'posts/rechnungen/rechnung_intern.html'
    }
    datum = nutzer_aufgabe.erstellt_am
    rechnungs_template = template_map.get(aufgabe.rechnungstyp, 'posts/rechnungen/rechnung_basis.html')
    id_to_name = {konto.id: konto.name for konto in Konto.objects.filter(kontenplan=kontenplan)}
    # Kontext mit allen notwendigen Daten
    context = {
        'rechnungs_template': rechnungs_template,  # Dynamisch gewähltes Template
        'rechnungsnummer': aufgabe.rechnungsnummer,
        'datum': datum,
        'hat_leistungszeitraum': aufgabe.hat_leistungszeitraum,
        #'anschrift_kunde': aufgabe.anschrift_kunde,
        'eigene_ansicht': aufgabe.eigene_ansicht,
        'leistungszeitraum_anfang': nutzer_aufgabe.leistungszeitraum_anfang,
        'leistungszeitraum_ende': nutzer_aufgabe.leistungszeitraum_ende,
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
        'umsatzsteuerfrei':aufgabe.umsatzsteuerfrei,
        'buchung_status': buchung_status,
        'konten': konten,
        'block_buchung': block_buchung,
        'absender': nutzer_aufgabe.absender,
        'konten_namen': id_to_name,
        'kontenplan_id': kontenplan,
    }
    nutzergruppe = getattr(request.user, "nutzergruppe", 0) or 0
    context["nutzergruppe"] = nutzergruppe % 2 == 1  # Ungerade Gruppen: 1 oder 3
    return render(request, 'posts/rechnung.html', context)

@login_required
def buchungssatz_uebersicht(request):
    nutzer = request.user
    buchungen = Buchung.objects.filter(nutzer=nutzer).select_related('aufgabe').order_by('aufgabe__id', 'versuch')

    from collections import defaultdict
    aufgaben_buchungen = defaultdict(list)
    id_to_name = {str(k.id): k.name for k in Konto.objects.all()}
    for buchung in buchungen:
        soll_konten = json.loads(buchung.antwort_konten_soll or "[]")
        soll_betraege = json.loads(buchung.antwort_betrag_soll or "[]")
        haben_konten = json.loads(buchung.antwort_konten_haben or "[]")
        haben_betraege = json.loads(buchung.antwort_betrag_haben or "[]")

        # Wir kombinieren Soll und Haben für tabellarische Darstellung
        max_len = max(len(soll_konten), len(haben_konten))
        zeilen = []
        for i in range(max_len):
            soll_text = (id_to_name.get(soll_konten[i], soll_konten[i]), f"{soll_betraege[i]} €") if i < len(soll_konten) else ("", "")
            haben_text = (id_to_name.get(haben_konten[i], haben_konten[i]), f"{haben_betraege[i]} €") if i < len(haben_konten) else ("", "")
            zeilen.append((soll_text, haben_text))

        aufgaben_buchungen[buchung.aufgabe].append({
            "buchung_nr": buchung.versuch,
            "korrekturbuchung": buchung.korrekturbuchung,
            "zeilen": zeilen
        })

    return render(request, "posts/buchungssatz_uebersicht.html", {
        "aufgaben_buchungen": dict(aufgaben_buchungen)
    })

def is_buchung_korrekt(buchung, nutzer_aufgabe):
    
    # JSON-Daten der Buchung laden
    soll_konten_nutzer = safe_parse(buchung.antwort_konten_soll)
    haben_konten_nutzer = safe_parse(buchung.antwort_konten_haben)
    soll_betraege_nutzer = [round(float(b), 2) for b in safe_parse(buchung.antwort_betrag_soll)]
    haben_betraege_nutzer = [round(float(b), 2) for b in safe_parse(buchung.antwort_betrag_haben)]

    # Erwartete Werte aus der Nutzeraufgabe
    soll_konten_aufgabe = nutzer_aufgabe.soll_konten
    haben_konten_aufgabe = nutzer_aufgabe.haben_konten
    soll_betraege_aufgabe = [round(float(b), 2) for b in nutzer_aufgabe.soll_betraege]
    haben_betraege_aufgabe = [round(float(b), 2) for b in nutzer_aufgabe.haben_betraege]

    erlaubte_soll_konten = erlaubte_konten(soll_konten_aufgabe)
    erlaubte_haben_konten = erlaubte_konten(haben_konten_aufgabe)

    konten_soll_korrekt = (
        set(soll_konten_nutzer).issubset(erlaubte_soll_konten)
        and len(soll_konten_nutzer) == len(soll_konten_aufgabe)
    )
    konten_haben_korrekt = (
        set(haben_konten_nutzer).issubset(erlaubte_haben_konten)
        and len(haben_konten_nutzer) == len(haben_konten_aufgabe)
    )
    betraege_soll_korrekt = sum(soll_betraege_nutzer) == sum(soll_betraege_aufgabe)
    betraege_haben_korrekt = sum(haben_betraege_nutzer) == sum(haben_betraege_aufgabe)

    # Prüfen, ob Summe Soll = Summe Haben
    summe_soll_nutzer = sum(soll_betraege_nutzer)
    summe_haben_nutzer = sum(haben_betraege_nutzer)
    summe_korrekt = summe_soll_nutzer == summe_haben_nutzer

    # Ergebnis zurückgeben
    return konten_soll_korrekt and konten_haben_korrekt and betraege_soll_korrekt and betraege_haben_korrekt and summe_korrekt

def erlaubte_konten(ids):
        """Erlaubt genau das Originalkonto und ggf. das Konto mit Bilanzposition als Kontonummer."""
        erlaubte_ids = set()
        for id in ids:
            konto = Konto.objects.filter(id=id).first()
            if konto:
                erlaubte_ids.add(konto.id)  # Das Konto selbst immer erlauben
                if konto.bilanzposition_nummer:
                    bilanz_konto = Konto.objects.filter(
                        kontonummer=konto.bilanzposition_nummer,
                        kontenplan=konto.kontenplan
                    ).first()
                    if bilanz_konto:
                        erlaubte_ids.add(bilanz_konto.id)  # Konto mit Bilanzposition als Kontonummer
        return set(str(eid) for eid in erlaubte_ids)

def handle_nutzer_buchung(request, aufgabe):
    letzte_buchung = Buchung.objects.filter(aufgabe=aufgabe, nutzer=request.user).order_by('-versuch').first()
    neuer_versuch = (letzte_buchung.versuch + 1) if letzte_buchung else 1

    soll_konto_ids = request.POST.getlist('soll_konto[]')
    haben_konto_ids = request.POST.getlist('haben_konto[]')
    soll_betraege = request.POST.getlist('soll_betrag[]')
    haben_betraege = request.POST.getlist('haben_betrag[]')

    # Original speichern
    original_soll_konten = soll_konto_ids
    original_haben_konten = haben_konto_ids

    def ersetze_konto_durch_bilanzpositionskonto(konto_ids):
        neue_ids = []
        for konto_id in konto_ids:
            try:
                original_konto = Konto.objects.get(id=konto_id)
                bilanznummer = original_konto.bilanzposition_nummer
                # Suche Konto mit gleicher Bilanzposition und gesetzter Kontonummer
                ersatz_konto = Konto.objects.filter(
                    bilanzposition_nummer=bilanznummer,
                    kontonummer__isnull=False,
                    kontenplan=original_konto.kontenplan
                ).first()
                if ersatz_konto:
                    neue_ids.append(str(ersatz_konto.id))
                else:
                    neue_ids.append(konto_id)  # Fallback: ursprüngliches Konto verwenden
            except Konto.DoesNotExist:
                neue_ids.append(konto_id)
        return neue_ids

    ersetzte_soll_konten = ersetze_konto_durch_bilanzpositionskonto(soll_konto_ids)
    ersetzte_haben_konten = ersetze_konto_durch_bilanzpositionskonto(haben_konto_ids)
    # Buchung erstellen
    buchung = Buchung.objects.create(
        aufgabe=aufgabe,
        nutzer=request.user,
        antwort_konten_soll=json.dumps(ersetzte_soll_konten),
        antwort_konten_haben=json.dumps(ersetzte_haben_konten),
        antwort_betrag_soll=json.dumps(soll_betraege),
        antwort_betrag_haben=json.dumps(haben_betraege),
        original_konten_soll=json.dumps(original_soll_konten),
        original_konten_haben=json.dumps(original_haben_konten),
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

    erlaubte_soll_konten = erlaubte_konten(soll_konten_aufgabe)
    erlaubte_haben_konten = erlaubte_konten(haben_konten_aufgabe)

    # Neue Konto-Status-Logik
    soll_konten_ok = set(soll_konten_nutzer).issubset(erlaubte_soll_konten) and len(soll_konten_nutzer) == len(soll_konten_aufgabe)
    haben_konten_ok = set(haben_konten_nutzer).issubset(erlaubte_haben_konten) and len(haben_konten_nutzer) == len(haben_konten_aufgabe)

    if not soll_konten_ok and not haben_konten_ok:
        konto_status = 3
    elif not soll_konten_ok:
        konto_status = 1
    elif not haben_konten_ok:
        konto_status = 2
    else:
        konto_status = 0

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
    summe_soll_nutzer = round(sum(betraege_soll_nutzer),2)
    summe_haben_nutzer = round(sum(betraege_haben_nutzer),2)
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

    if (buchung.versuch == 3) and buchung.status != "korrekt":
        threading.Thread(target=ollama_threading, args=(buchung, nutzer_aufgabe, aufgabe.beschreibung)).start()

    buchung.save()
    nutzer_aufgabe.save()

    return buchung

def generiere_zufaellige_werte(aufgabe, versuch=0):
    
    faktor = Decimal(str(random.uniform(0.25, 2.0)))
    faktor = faktor.quantize(Decimal("0.01"))  # max. 2 Nachkommastellen
    if aufgabe.unternehmen_kategorie.fallstudie:
        faktor=1

    soll_konten = []
    soll_betraege = []
    haben_konten = []
    haben_betraege = []

    soll_details = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Soll")
    haben_details = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Haben")

    for detail in soll_details:
        soll_konten.append(detail.konto.id)
        betrag = Decimal(str(detail.betrag or 0)) * faktor
        betrag = betrag.quantize(Decimal("0.01"))
        soll_betraege.append(float(betrag))

    for detail in haben_details:
        haben_konten.append(detail.konto.id)
        betrag = Decimal(str(detail.betrag or 0)) * faktor
        betrag = betrag.quantize(Decimal("0.01"))
        haben_betraege.append(float(betrag))
    summe_soll = sum(soll_betraege)
    summe_haben = sum(haben_betraege)
    if round(summe_soll, 2) == round(summe_haben, 2):
        return {
            'soll_konten': soll_konten,
            'haben_konten': haben_konten,
            'soll_betraege': soll_betraege,
            'haben_betraege': haben_betraege
        }
    else:
        return generiere_zufaellige_werte(aufgabe)

def speichere_nutzer_aufgabe(nutzer, aufgabe, zufaellige_werte):
    # Prüfe, ob bereits eine NutzerAufgabe existiert
    nutzer_aufgabe, created = NutzerAufgabe.objects.get_or_create(
        aufgabe=aufgabe,
        nutzer=nutzer,
        defaults={
            'soll_konten': [str(k) for k in zufaellige_werte['soll_konten']],
            'haben_konten': [str(k) for k in zufaellige_werte['haben_konten']],
            'soll_betraege': zufaellige_werte['soll_betraege'],
            'haben_betraege': zufaellige_werte['haben_betraege'],
            'bearbeitungsstand': 'offen',
        }
    )

    if not nutzer_aufgabe.absender:
        absender_liste = Absender.objects.all()
        nutzer_aufgabe.speichere_leistungszeitraum()
        if absender_liste.exists():
            absender = choice(absender_liste)  # zufälligen bestehenden wählen
        else:
            absender = None  # Fallback: None, falls keine existieren
        if absender:
            nutzer_aufgabe.absender = absender
            nutzer_aufgabe.save(update_fields=["absender"])

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
        betreff = f"Bitte bearbeiten Sie folgenden Geschäftsvorfall: {aufgabe.rechnungsnummer}"
        betreff_en = f"Please process the following business transaction: {aufgabe.rechnungsnummer}"
    else:
        v = round((versuch/2) + 1,0)
        betreff = f"Rechnung: {aufgabe.rechnungsnummer} Versuch {v}"
        betreff_en = f"Invoice: {aufgabe.rechnungsnummer} Try {v}"
    mailtext = f"{aufgabe.mailtext}"

    Mail.objects.create(
        nutzer=nutzer,
        aufgabe=aufgabe,
        betreff=betreff,
        betreff_de=betreff,
        betreff_en=betreff_en,
        mailtext=mailtext,
        versuch=versuch,
        absender=absender,  # Speichert die Absender-Referenz
        status='nicht bearbeitet'
    )

def get_fallback_konten(aufgabe):
    soll_detail = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Soll").order_by('?').first()
    haben_detail = AufgabeDetail.objects.filter(aufgabe=aufgabe, soll_haben="Haben").order_by('?').first()

    return (
        soll_detail.konto.id if soll_detail and soll_detail.konto else None,
        haben_detail.konto.id if haben_detail and haben_detail.konto else None
    )

@lehrkraft_required
def unternehmen_verwalten(request):
    """ Zeigt eine Liste der Unternehmen an und ermöglicht das Hinzufügen. """
    if request.method == 'POST':
        form = UnternehmenForm(request.POST)
        if form.is_valid():
            unternehmen = form.save(commit=False)  # ✅ Hier wird das Objekt erzeugt
            unternehmen.ersteller = request.user.id
            unternehmen.save()
            messages.success(request, _("Unternehmen erfolgreich hinzugefügt."))
            return redirect('posts:unternehmen_verwalten')
        else:
            messages.error(request, _("Fehler beim Speichern des Unternehmens."))
    else:
        form = UnternehmenForm()

    if request.user.is_superuser:
        unternehmen = Unternehmen.objects.all()
    else:
        unternehmen = Unternehmen.objects.filter(Q(ersteller=request.user.id) | Q(ersteller=1))
    return render(request, 'posts/neues_unternehmen.html', {'form': form, 'unternehmen': unternehmen})


def handle_post_request(request, form_class, redirect_url, template_name):
    if request.method == 'POST':
        result = handle_form_submission(request, form_class, "Erfolgreich gespeichert.", redirect_url)
        if result:
            return result
    form = form_class()
    return render(request, template_name, {'form': form})

@lehrkraft_required
def unternehmen_loeschen(request, unternehmen_id):
    """ Löscht ein Unternehmen und gibt eine Bestätigung aus. """
    unternehmen = get_object_or_404(Unternehmen, id=unternehmen_id)
    if unternehmen.ersteller != request.user.id and not request.user.is_superuser:
        return HttpResponse(_("Keine Berechtigung zum Löschen."))
    unternehmen.delete()
    messages.success(request, _("Das Unternehmen '%(name)s' wurde gelöscht.") % {"name": unternehmen.name})
    return redirect('posts:unternehmen_verwalten')

@lehrkraft_required
def aufgabenkategorie_verwalten(request):
    """ Zeigt eine Liste der Kategorien an und ermöglicht das Hinzufügen. """
    if request.method == 'POST':
        form = AufgabenkategorieForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Kategorie erfolgreich hinzugefügt."))
            return redirect('posts:aufgabenkategorie_verwalten')
        else:
            messages.error(request, _("Fehler beim Speichern der Kategorie."))
    else:
        form = AufgabenkategorieForm()

    aufgabenkategorien = Aufgabenkategorie.objects.all()
    return render(request, 'posts/neue_kategorie.html', {'form': form, 'aufgabenkategorien': aufgabenkategorien})

@admin_required
def aufgabenkategorie_loeschen(request, kategorie_id):
    """ Löscht eine Kategorie und gibt eine Bestätigung aus. """
    kategorie = get_object_or_404(Aufgabenkategorie, id=kategorie_id)
    kategorie.delete()
    messages.success(request, _("Die Kategorie '%(name)s' wurde gelöscht.") % {"name": kategorie.name})
    return redirect('posts:aufgabenkategorie_verwalten')

@login_required
def hauptbuch_view(request):
    user = request.user
    # Falls noch keine anfangsbestaende existieren, generiere sie
    generate_user_anfangsbestaende(user)
    unternehmen = user.unternehmen
    if not unternehmen or not unternehmen.kontenplan:
        konten = Konto.objects.none()
    else:
        # Konten aus dem Kontenplan des Unternehmens des Nutzers
        konten = Konto.objects.filter(kontenplan=unternehmen.kontenplan).order_by('name')

    # anfangsbestaende des Nutzers abrufen
    anfangsbestaende = Anfangsbestand.objects.filter(nutzer=user)
    # Alle Buchungen des Nutzers abrufen
    buchungen = Buchung.objects.filter(nutzer=user)
    # T-Konten erstellen mit anfangsbestaenden UND Buchungen
    t_konten = build_t_konten(buchungen, anfangsbestaende)
    aufgaben_ids = sorted({f"{buchung.aufgabe.id} {buchung.versuch})" for buchung in buchungen})

    return render(request, "posts/hauptbuch.html", {
        "t_konten": t_konten,
        "konten": konten,
        "aufgaben_ids": aufgaben_ids
    })

def generate_color(aufgabe_id):
    hash_value = int(hashlib.md5(str(aufgabe_id).encode(), usedforsecurity=False).hexdigest(), 16)
    hue = hash_value % 360
    return f"hsl({hue}, 70%, 85%)"

def build_t_konten(buchungen, anfangsbestände):
    t_konten = {}
    aufgabe_farben = {}
    id_to_name = {str(konto.id): konto.name for konto in Konto.objects.all()}
    # Anfangsbestände in die T-Konten-Struktur aufnehmen
    for bestand in anfangsbestände:
        konto_id = str(bestand.konto.id)
        t_konten.setdefault(konto_id, {"soll": [], "haben": [], "name": id_to_name.get(konto_id)})

        if bestand.konto.unterkategorie == "Aktiva":  # EBK für Aktivkonten auf Soll-Seite
            t_konten[konto_id]["soll"].append(("EBK", bestand.betrag, "#D3D3D3"))
        elif bestand.konto.unterkategorie == "Passiva":  # EBK für Passivkonten auf Haben-Seite
            t_konten[konto_id]["haben"].append(("EBK", bestand.betrag, "#D3D3D3"))

    # Bestehende Buchungen hinzufügen (Originalfunktion bleibt erhalten)
    for buchung in buchungen:
        aufgabe_id_mit_versuch = f"{buchung.aufgabe.id} {buchung.versuch})"

        if buchung.aufgabe.id not in aufgabe_farben:
            aufgabe_farben[buchung.aufgabe.id] = generate_color(buchung.aufgabe.id)

        farbe = aufgabe_farben[buchung.aufgabe.id]

        soll_konten = safe_parse(buchung.antwort_konten_soll or "[]")
        haben_konten = safe_parse(buchung.antwort_konten_haben or "[]")
        soll_betraege = safe_parse(buchung.antwort_betrag_soll or "[]")
        haben_betraege = safe_parse(buchung.antwort_betrag_haben or "[]")

        for konto_id, betrag in zip(soll_konten, soll_betraege):
            t_konten.setdefault(konto_id, {"soll": [], "haben": [], "name": id_to_name.get(konto_id)})
            t_konten[konto_id]["soll"].append((aufgabe_id_mit_versuch, betrag, farbe))

        for konto_id, betrag in zip(haben_konten, haben_betraege):
            t_konten.setdefault(konto_id, {"soll": [], "haben": [], "name": id_to_name.get(konto_id)})
            t_konten[konto_id]["haben"].append((aufgabe_id_mit_versuch, betrag, farbe))
    return t_konten

@lehrkraft_required
def aufgabe_bearbeiten(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    if aufgabe.ersteller != request.user.id and not request.user.is_superuser:
        return HttpResponse(_("Keine Berechtigung zum Bearbeiten."))
    details = AufgabeDetail.objects.filter(aufgabe=aufgabe)
    kontenplan = aufgabe.unternehmen_kategorie.kontenplan
    if request.method == 'POST':
        result = handle_form_submission(request, AufgabeBearbeitenForm, "Aufgabe erfolgreich bearbeitet.", 'posts:aufgaben_verwalten', instance=aufgabe)
        if result:
            for detail in details:
                detail_form = AufgabeDetailBearbeitenForm(request.POST, prefix=str(detail.id), instance=detail)
                if detail_form.is_valid():
                    detail_form.save()
                else:
                    messages.error(request, _("Fehler beim Bearbeiten der Details."))
            return result

    form = AufgabeBearbeitenForm(instance=aufgabe)
    detail_forms = [AufgabeDetailBearbeitenForm(prefix=str(detail.id), instance=detail, kontenplan=kontenplan) for detail in details]
    return render(request, 'posts/aufgabe_bearbeiten.html', {'form': form, 'detail_forms': detail_forms})

def name_oder_id_liste_zu_id_liste(eingabe_liste):
    """Konvertiert ggf. Kontonamen in IDs"""
    mapping = {k.name: k.id for k in Konto.objects.all()}
    return [mapping.get(x, x) for x in eingabe_liste]

@login_required
def korrekturbuchung_durchfuehren(request, buchung_id):
    buchung = get_object_or_404(Buchung, buchung_id=buchung_id)
    aufgabe = get_object_or_404(Aufgabe_neu, id=buchung.aufgabe_id)
    nutzeraufgabe = NutzerAufgabe.objects.get(aufgabe=aufgabe, nutzer=request.user)
    absender = get_object_or_404(Absender, id=nutzeraufgabe.absender_id)
    print(f"✅ Nutzeraufgabe gefunden: {nutzeraufgabe}")
    print(f"✅ Absender geladen: {absender}")
    letzte_buchung = Buchung.objects.filter(aufgabe=buchung.aufgabe, nutzer=request.user).order_by('-versuch').first()
    naechster_versuch = (letzte_buchung.versuch + 1) if letzte_buchung else 1

    # Eingabewerte laden
    soll_liste = json.loads(buchung.antwort_konten_haben or "[]")
    haben_liste = json.loads(buchung.antwort_konten_soll or "[]")

    # Prüfen ob ID oder Name enthalten ist, und ggf. umwandeln
    soll_ids = [str(k) for k in name_oder_id_liste_zu_id_liste(soll_liste)]
    haben_ids = [str(k) for k in name_oder_id_liste_zu_id_liste(haben_liste)]
    print(f"➡️ Soll-IDs: {soll_ids}")
    print(f"➡️ Haben-IDs: {haben_ids}")
    neue_buchung = Buchung.objects.create(
        aufgabe=buchung.aufgabe,
        nutzer=request.user,
        antwort_konten_soll=json.dumps(soll_ids),
        antwort_konten_haben=json.dumps(haben_ids),
        antwort_betrag_soll=buchung.antwort_betrag_haben,
        antwort_betrag_haben=buchung.antwort_betrag_soll,
        original_konten_soll=buchung.original_konten_haben,
        original_konten_haben=buchung.original_konten_soll,
        status='bearbeitet',
        korrekturbuchung=True,
        versuch=naechster_versuch
    )
    print(f"✅ Neue Korrekturbuchung gespeichert: {neue_buchung}")
    print("📧 Mail erstellt")
    erstelle_aufgaben_mail(request.user, aufgabe, naechster_versuch+1, absender)
    messages.success(request, _('Korrekturbuchung im Versuch %(versuch)s erfolgreich durchgeführt.') % {'versuch': naechster_versuch})
    return redirect('frontpage')

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
    elif "Bitte aktualisieren Sie Ihren Anzeigenamen" in mail.betreff_de:
        aufgabe_link = reverse('users:update_profile')

    return render(request, 'posts/mail_detail.html', {
        'mail': mail,
        'aufgabe_link': aufgabe_link
    })

def send_korrektur_mail(nutzer, aufgabe, request):
    # Den höchsten bisherigen Versuch aus der Buchungs- oder Mail-Tabelle ermitteln
    letzter_mail_versuch = Mail.objects.filter(aufgabe=aufgabe, nutzer=nutzer).order_by('-versuch').first()
    letzter_buchung_versuch = Buchung.objects.filter(aufgabe=aufgabe, nutzer=nutzer).order_by('-versuch').first()

    # Höchsten Versuch ermitteln
    hoechster_versuch = max(
        (letzter_mail_versuch.versuch if letzter_mail_versuch else 0),
        (letzter_buchung_versuch.versuch if letzter_buchung_versuch else 0)
    )

    naechster_versuch = hoechster_versuch + 1  # Neuer Versuch = Höchster + 1
    update_url = request.build_absolute_uri(reverse("posts:rechnung_detail", args=[aufgabe.id]))
    mail_betreff = f"Korrekturbuchung für Rechnung - {aufgabe.rechnungsnummer}"
    mail_betreff_en = f"Adjustment entry for the invoice - {aufgabe.rechnungsnummer}"
    mail_text_en = (
        f"""
        Dear {nutzer.username},
        <p>Your journal entry for the attached invoice contains an error.</p>
        
        <p>Please correct the entry by completing an adjustment entry following this link: </p>
        <p><a href="{update_url}">Correct the journal Entry</a></p>
        <p>Your previous journal entries, as well as feedback on them, are stored in the input section for the accounts. To view them, expand the entries by clicking on 'Show/Hide Entries' and then click on your most recent entry.</p> 
        <p>Thank you, <br>Your Booking Team</p>"""
    )
    mailtext = (
        f"""
        Sehr geehrte/r {nutzer.username},
        <p>Ihre Buchung zur beiliegenden Aufgabe enthält einen Fehler.</p>
        
        <p>Bitte führen Sie eine Korrekturbuchung über den folgenden Link durch: </p>
        <p><a href="{update_url}">Zur Korrekturbuchung</a></p>
        <p>Ihre alten Buchungen, sowie Feedback zu den Buchungen, ist unter in der Eingabemaske für die Konten hinterlegt. Klappen Sie dafür die Buchungen auf, indem Sie auf "Buchungen anzeigen/verstecken" und anschließend auf Ihre letzte Buchung drücken.</p> 
        <p>Vielen Dank, <br>Ihr Buchhaltungsteam</p>"""
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
        betreff_de=mail_betreff,
        betreff_en=mail_betreff_en,
        absender=absender,
        mailtext=mailtext,
        mailtext_de=mailtext,
        mailtext_en=mail_text_en,
        versuch=naechster_versuch,  # Dynamischer Versuchswert
        status='nicht bearbeitet'
    )

@lehrkraft_required
def konten_verwalten(request):
    if request.method == 'POST':
        if "neuer_kontenplan" in request.POST:
            Kontenplan.objects.create(nutzer=request.user)
            request.session["kontenplan_erfolgreich"] = True
            return redirect("posts:konten_verwalten")

        if 'importiere_excel' in request.POST:
            return verarbeite_excel_import(request)
        
        form = KontoForm(request.POST or None, user=request.user)
        if form.is_valid():
            konto = form.save(commit=False)
            konto.erstellt_von = request.user
            konto.save()
            messages.success(request, _("Konto erfolgreich hinzugefügt."))
            return redirect('posts:konten_verwalten')
        else:
            messages.error(request, _("Fehler: Überprüfe deine Eingaben."))
    else:
        form = KontoForm(user=request.user)

    # Nur Konten aus Kontenplan 1 und eigene Pläne laden
    superuser_filter = Q(erstellt_von=request.user) | Q(erstellt_von__isnull=True) | Q(erstellt_von__is_superuser=True)
    konten = Konto.objects.filter(
        Q(kontenplan__nutzer=request.user) | Q(kontenplan__nutzer__is_superuser=True)
    ).filter(
        superuser_filter
    ).order_by('kontonummer', 'name')
    kontenplaene = Kontenplan.objects.filter(
        Q(nutzer=request.user) | Q(nutzer__is_superuser=True)
    )

    # Gruppieren nach Kontenplan-ID
    konten_nach_plan = defaultdict(list)
    for konto in konten:
        konten_nach_plan[konto.kontenplan_id].append(konto)
    erfolgsmeldung = request.session.pop("kontenplan_erfolgreich", False)
    return render(request, 'posts/konten_verwalten.html', {
        'form': form,
        'konten_nach_plan': dict(konten_nach_plan),
        'kontenplaene': kontenplaene,
        "erfolgsmeldung": erfolgsmeldung,
    })

@lehrkraft_required
def kontenplan_loeschen(request, pk):
    kontenplan = get_object_or_404(Kontenplan, pk=pk)
    if request.user.is_superuser or kontenplan.nutzer == request.user:
        kontenplan.delete()
    return redirect('posts:konten_verwalten')

def importiere_konten_aus_excel(datei, kontenplan, nutzer):
    wb = openpyxl.load_workbook(datei)
    sheet = wb.active
    fehlerhafte_zeilen = []

    for index, row in enumerate(sheet.iter_rows(min_row=2, max_col=5, values_only=True), start=2):
        kontonummer, name, kategorie, unterkategorie, bilanzposition = row
        print(f"📄 Zeile {index}: {row}")
        if not name or not kategorie or str(name).strip() == "":
            fehlerhafte_zeilen.append(index)
            continue
        try:
            Konto.objects.create(
                name=name,
                kategorie=kategorie,
                unterkategorie=unterkategorie,
                kontonummer=kontonummer,
                bilanzposition_nummer=bilanzposition,
                kontenplan=kontenplan,
                erstellt_von=nutzer
            )
        except Exception as e:
            fehlerhafte_zeilen.append(index)

    return fehlerhafte_zeilen

def verarbeite_excel_import(request):
    excel_datei = request.FILES.get('excel_datei')
    kontenplan_id = request.POST.get('kontenplan_id')

    try:
        kontenplan = Kontenplan.objects.get(id=kontenplan_id)
        fehler = importiere_konten_aus_excel(excel_datei, kontenplan, request.user)

        if fehler:
            messages.warning(request, f"Einige Zeilen wurden übersprungen (Reihen: {', '.join(map(str, fehler))})")
        else:
            messages.success(request, _("Konten erfolgreich importiert."))
    except Exception as e:
        messages.error(request, f"Fehler beim Import: {str(e)}")

    return redirect('posts:konten_verwalten')

@lehrkraft_required
def konto_bearbeiten(request, konto_id):
    konto = get_object_or_404(Konto, id=konto_id)
    if konto.erstellt_von_id != request.user.id and not request.user.is_superuser:
        return HttpResponse("Keine Berechtigung zum Bearbeiten.")
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
    if konto.erstellt_von_id != request.user.id and not request.user.is_superuser:
        return HttpResponse("Keine Berechtigung zum Löschen.")
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
    buchungen = Buchung.objects.filter(nutzer__in=studenten)
    gesamt_aufgaben = nutzer_aufgaben.count()
    bearbeitet, korrekt = get_bearbeitungsstand(nutzer_aufgaben)
    anzahl_fehlerhafte_buchungen = buchungen.filter(
        Q(konto_korrekt__gt=0) | Q(betrag_korrekt__gt=0),
        korrekturbuchung=False
    ).count()
    anzahl_studierende = buchungen.values('nutzer').distinct().count()

    return JsonResponse({
        'gesamt_aufgaben': gesamt_aufgaben,
        'bearbeitet': bearbeitet,
        'korrekt': korrekt,
        'anzahl_fehlerhafte_buchungen': anzahl_fehlerhafte_buchungen,
        'anzahl_studierende': anzahl_studierende
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
    semester_id = request.GET.get('semester')
    studiengang_id = request.GET.get('studiengang')

    # Nur Studierende des aktuellen Lehrers
    studenten = User.objects.filter(role='student', professor=request.user)

    # Filter anwenden, wenn vorhanden
    if semester_id:
        studenten = studenten.filter(semester_id=semester_id)
    if studiengang_id:
        studenten = studenten.filter(studiengang_id=studiengang_id)

    # Studierendenliste bauen
    studierende_liste = [
        {"id": s.id, "name": f"{s.first_name} {s.last_name}".strip() or s.username}
        for s in studenten
    ]

    # Werte für Dropdowns
    semesters = list(User.objects.filter(role='student').values('semester_id', 'semester__name').distinct())
    studiengaenge = list(User.objects.filter(role='student').values('studiengang_id', 'studiengang__name').distinct())
    aufgaben = list(Aufgabe_neu.objects.values('id', 'fragentyp_text'))

    return JsonResponse({
        'semesters': semesters,
        'studiengaenge': studiengaenge,
        'aufgaben': aufgaben,
        'studierende': studierende_liste
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
    guv_id = str(guv_konto.id)
    if guv_id in t_konten:
        del t_konten[guv_id]
    # Verknüpfe Konten mit Kategorien
    konto_kategorien = {str(konto.id): konto.kategorie for konto in konten}
    return render(request, "posts/guv.html", {
        "t_konten": t_konten,
        "konten": konten,
        "konto_kategorien": konto_kategorien
    })

def generate_user_anfangsbestaende(user):
    if Anfangsbestand.objects.filter(nutzer=user).exists():
        return  # Bereits vorhanden – nichts tun

    if getattr(user, "unternehmen_id", None) != 1:
        return  # Nur wenn Unternehmen ID = 1
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
    konto_kategorien = {str(konto.id): konto.unterkategorie for konto in bestandskonten}
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
        beschreibung_lang = aufgabe.beschreibung or ""
        if len(beschreibung_lang) > 90:
            cutoff_index = beschreibung_lang.find(" ", 90)
            if cutoff_index != -1:
                beschreibung_kurz = beschreibung_lang[:cutoff_index] + " ..."
            else:
                beschreibung_kurz = beschreibung_lang  # Kein Leerzeichen gefunden → komplette Beschreibung behalten
        else:
            beschreibung_kurz = beschreibung_lang

        rechnungsdaten.append({
            'id': aufgabe.id,
            'rechnungsnr': aufgabe.rechnungsnummer,
            'beschreibung': beschreibung_kurz,
            'anzahl_buchungen': anzahl_buchungen,
            'anzahl_korrekturbuchungen': anzahl_korrekturbuchungen,
            'aufgabenstatus': nutzer_aufgabe.bearbeitungsstand
        })

    return render(request, 'posts/rechnungsuebersicht.html', {'rechnungsdaten': rechnungsdaten})

def generate_random_absender():
    vorname = random.choice(vornamen)
    nachname = random.choice(nachnamen)
    email = f"{nachname.lower()}@{random.choice(emailsuffix)}"
    #print(f"email:{email}")
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
    #print(f"📌 Generierter Absender: {absender.name}, ID: {absender.id}, Neu erstellt: {created}")    
    return absender

@lehrkraft_required
def aufgaben_verwalten(request):
    """ Zeigt eine Liste aller Aufgaben und ermöglicht das Löschen. """
    if request.user.is_superuser:
        aufgaben = Aufgabe_neu.objects.all()
    else:
        aufgaben = Aufgabe_neu.objects.filter(Q(ersteller=request.user.id) | Q(ersteller=1))
    aufgaben_nach_unternehmen = defaultdict(list)
    for aufgabe in aufgaben:
        aufgaben_nach_unternehmen[aufgabe.unternehmen_kategorie].append(aufgabe)

    return render(request, 'posts/aufgaben_verwalten.html', {
        'aufgaben_nach_unternehmen': dict(aufgaben_nach_unternehmen)
    })

@lehrkraft_required
def aufgabe_loeschen(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)

    # Nur löschen, wenn Ersteller übereinstimmt oder Admin
    if aufgabe.ersteller != request.user.id and not request.user.is_superuser:
        return HttpResponse(_("Keine Berechtigung zum Löschen dieser Aufgabe."))

    aufgabe.delete()
    return redirect('posts:aufgaben_verwalten')

#+ Zeile 278
OLLAMA_API_URL = config('OLLAMA_SERVER')
@admin_required
@csrf_exempt
def ollama_prompt_view(request):
    if request.method == 'POST':
        try:
            body = request.body.decode('utf-8')
            parsed = json.loads(body)
            prompt = parsed.get("prompt", "")
        except Exception as e:
            return StreamingHttpResponse(
                (f"event: error\ndata: Fehler beim Parsen: {str(e)}\n\n",),
                content_type='text/event-stream'
            )
        payload = {
            "model": "llama3.3:70b",
            "prompt": prompt,
            "stream": True
        }
        def stream_antwort():
            try:
                with requests.post(OLLAMA_API_URL, json=payload, stream=True, timeout=30) as response:
                    if response.status_code != 200:
                        yield f"event: error\ndata: Fehler von Ollama (Status {response.status_code})\n\n"
                        return
                    for line in response.iter_lines(decode_unicode=True):
                        if line:
                            try:
                                data = json.loads(line)
                                text = data.get("response", "")
                                yield f"data: {text}\n\n"
                            except json.JSONDecodeError as e:
                                yield f"event: error\ndata: JSON-Fehler: {str(e)}\n\n"
            except Exception as e:
                yield f"event: error\ndata: Ausnahme beim Streaming: {str(e)}\n\n"
        return StreamingHttpResponse(stream_antwort(), content_type='text/event-stream')
    return render(request, 'posts/ollama_prompt.html')

def generiere_feedback_von_ollama(buchung, nutzeraufgabe, beschreibung):
    id_to_name = {str(k.id): k.name for k in Konto.objects.all()}

    def id_betrag_zu_namen(paar_liste, betraege):
        return [(id_to_name.get(str(konto_id), f"Unbekannt-{konto_id}"), betrag) for konto_id, betrag in zip(paar_liste, betraege)]

    # Nutzerlösung alphabetisch
    nutzer_soll = id_betrag_zu_namen(
        json.loads(buchung.antwort_konten_soll or "[]"),
        [round(float(b), 2) for b in json.loads(buchung.antwort_betrag_soll or "[]")]
    )
    nutzer_haben = id_betrag_zu_namen(
        json.loads(buchung.antwort_konten_haben or "[]"),
        [round(float(b), 2) for b in json.loads(buchung.antwort_betrag_haben or "[]")]
    )

    # Korrekte Lösung laden
    korrekt_soll = id_betrag_zu_namen(
        nutzeraufgabe.soll_konten,
        [round(float(b), 2) for b in nutzeraufgabe.soll_betraege]
    )
    korrekt_haben = id_betrag_zu_namen(
        nutzeraufgabe.haben_konten,
        [round(float(b), 2) for b in nutzeraufgabe.haben_betraege]
    )
    prompt = (
        f"Du bist ein Tutor für Buchhaltung. Deine Aufgabe ist es, didaktisches Feedback auf fehlerhafte Buchungssätze zu geben. Das Feedback soll maximal drei Sätze lang sein.Verwende keine IDs, sondern nur Kontonamen und Beträge. Vermeide es, die richtige Lösung vollständig zu nennen, vor allem den vollständigen Namen der richtigen Konten.\n\n"
        f"Sachverhalt: \n{beschreibung}\n"
        f"Nutzereingabe:\nSoll: {nutzer_soll}, Haben: {nutzer_haben}\n"
        f"Richtige Lösung:\nSoll: {korrekt_soll}, Haben: {korrekt_haben}"
        f"Falls die gewählten Konten nicht korrekt sind, erläutere kurz, warum sie nicht passend sind, und gib einen Hinweis, welches Konto oder welche Konten stattdessen in diesem Fall sinnvoll wären. Wenn die Anzahl der Konten nicht übereinstimmt, soll ebenfalls ein zusätzlicher Hinweis gegeben werden. Unstimmige Beträge: Falls die Beträge nicht korrekt sind, weise darauf hin, dass die Summe nicht dem Rechnungsbetrag entspricht, und gib einen Tipp, wie sich der korrekte Betrag zusammensetzt. Falls nur eines der beiden fehlerhaft ist, nenne nur den entsprechenden Punkt. Falls beides falsch ist, gehe auf beide Punkte ein. Vermeide es, die richtige Lösung explizit zu nennen, sondern leite den Nutzer mit Hinweisen zur richtigen Lösung. Gib mir nur das Feedback zurück."
    )
    sprache = nutzeraufgabe.aufgabe.unternehmen_kategorie.kontenplan.sprache
    if sprache != 0:
        prompt = prompt + " Schreibe die antwort auf englisch!"
    ollama_payload = {
        "model": "llama3.3:70b",
        "prompt": prompt,
        "stream": False
    }

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json=ollama_payload,
            timeout=(5, 60)
        )
        antwort = response.json().get("response", "")
        return antwort.strip()
    except Exception as e:
        return f"Fehler bei Feedback-Generierung: {e}"
    
def ollama_threading(buchung, nutzer_aufgabe, beschreibung):
    feedback = generiere_feedback_von_ollama(buchung, nutzer_aufgabe, beschreibung)
    buchung.feedback_ollama = feedback
    buchung.save()
 
@login_required
@require_GET
def tkonto_vorschau(request):
    aufgabe_id = request.GET.get('aufgabe_id')
    soll_konten = json.loads(request.GET.get('soll_konten', '[]'))
    soll_betraege = json.loads(request.GET.get('soll_betraege', '[]'))
    haben_konten = json.loads(request.GET.get('haben_konten', '[]'))
    haben_betraege = json.loads(request.GET.get('haben_betraege', '[]'))
    relevante_konto_ids = list(set(soll_konten + haben_konten))
    # Alle bisherigen Buchungen für diese Aufgabe und diesen Nutzer
    buchungen = Buchung.objects.filter(
        aufgabe_id=aufgabe_id,
        nutzer=request.user
    )

    # Konto-ID zu Kontonamen Mapping
    id_to_name = {str(k.id): k.name for k in Konto.objects.all()}
    anfangsbestand_map = {
        str(a.konto.id): a.betrag
        for a in Anfangsbestand.objects.filter(
            nutzer=request.user,
            konto_id__in=relevante_konto_ids
        )
    }
    # Aufbau der bestehenden Buchungen
    t_konten = {}
    for konto_id, betrag in anfangsbestand_map.items():
        konto = t_konten.setdefault(konto_id, {"name": id_to_name.get(str(konto_id), f"Konto {konto_id}"), "soll": [], "haben": []})

        # Aktiva auf Soll, Passiva auf Haben (je nach Kontokategorie)
        konto_objekt = Konto.objects.get(id=konto_id)
        if konto_objekt.unterkategorie == "Aktiva":
            konto["soll"].insert(0, f"{betrag} € (EBK)")
        else:
            konto["haben"].insert(0, f"{betrag} € (EBK)")
    for buchung in buchungen:
        soll_ids = json.loads(buchung.antwort_konten_soll or "[]")
        soll_betrags = json.loads(buchung.antwort_betrag_soll or "[]")
        haben_ids = json.loads(buchung.antwort_konten_haben or "[]")
        haben_betrags = json.loads(buchung.antwort_betrag_haben or "[]")

        for konto_id, betrag in zip(soll_ids, soll_betrags):
            konto = t_konten.setdefault(konto_id, {"name": id_to_name.get(str(konto_id), f"Konto {konto_id}"), "soll": [], "haben": []})
            konto["soll"].append(f"{betrag} €")

        for konto_id, betrag in zip(haben_ids, haben_betrags):
            konto = t_konten.setdefault(konto_id, {"name": id_to_name.get(str(konto_id), f"Konto {konto_id}"), "soll": [], "haben": []})
            konto["haben"].append(f"{betrag} €")
    
    # Aktuelle Eingaben ergänzen
    for konto_id, betrag in zip(soll_konten, soll_betraege):
        konto = t_konten.setdefault(konto_id, {"name": id_to_name.get(str(konto_id), f"Konto {konto_id}"), "soll": [], "haben": []})
        konto["soll"].append(f"{betrag} € (aktuell)")

    for konto_id, betrag in zip(haben_konten, haben_betraege):
        konto = t_konten.setdefault(konto_id, {"name": id_to_name.get(str(konto_id), f"Konto {konto_id}"), "soll": [], "haben": []})
        konto["haben"].append(f"{betrag} € (aktuell)")
    
    return JsonResponse({"konten": list(t_konten.values())})