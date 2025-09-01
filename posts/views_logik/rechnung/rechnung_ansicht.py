# -*- coding: utf-8 -*-
# Kurzerklärung: Diese Datei teilt die ursprüngliche View in kleine, fokussierte Hilfsfunktionen (<10 Zeilen) auf.

from posts.views_logik.bibliotheken import _
from posts.views_logik.bibliotheken import *
from posts.views_logik.utils import *
from posts.views import ermittle_guv_konto, send_korrektur_mail
from .buchung import handle_nutzer_buchung, is_buchung_korrekt

'''
Hier wird die Ansicht verarbeitet, welche die Studierenden sehen, wenn die Buchungsmaske geöffnet wird. 
Jede Aufgabe hat eine Ansicht, die hier erstellt wird. Die wichtigsten Bestandteile sind dabei die Objekte: Buchungen, Status und Feedback. 
Jede Aufgabe hat Feedback abhängig von der Nutzergruppe. Ist diese ungerade, dann wird KI Feedback erstellt, ansonsten wird vordefiniertes Feedback verwendet. Das Textbasiert Feedback ist im Aufgabe Objekt hinterlegt. Zusätzlich zu diesem Textbasiertem Feedback
gibt es die Info Konto bzw. Betrag Korrekt, welche hier ebenfalls geladen und angezeigt werden. 
Für jede Buchung zu einer Aufgabe wird die Information übermittelt, ob Betrag und/oder Konten richtig sind und aus dieser Information wird für jede Buchung der Status ermittelt, ob eine Aufgabe richtig oder falsch bearbeitet wurde.
Wenn also Buchung 1 Falsch ist und Buchung 2 richtig, dann wird das dem Template so übergeben und im Endeffekt auch so als Status angezeigt. 
Darüber hinaus dient der Status als Information, um weitere Buchungen zu einer Aufgabe zu verhindern, falls die letzte Buchung falsch ist. Dann wird über JS auf rechnung.html der Postbutton gesperrt und es muss zunächst eine Korrekturbuchung durchgeführt werden.
FYI: Der Status wird aus der Buchung und der Nutzeraufgabe ermittelt. In der Nutzeraufgabe steht der korrekte Buchungssatz, welcher dann mit der Nutzereingabe abgeglichen wird.
Zusätzlich wird das GuV Konto als Buchungskonto ausgeschlossen, da nicht direkt an dieses Konto gebucht werden soll (fachlich).
Das genaue Template ist auf HTML bei posts/rechnung.html sichtbar.
'''

# Liefert Aufgabe und NutzerAufgabe (erstellt sie bei Bedarf mit Defaults).
def get_aufgabe_und_nutzeraufgabe(request, aufgabe_id):
    aufgabe = get_object_or_404(Aufgabe_neu, id=aufgabe_id)
    defaults = {'soll_konto': '', 'haben_konto': '', 'betrag': 0, 'bearbeitungsstand': 'offen'}
    nutzer_aufgabe, _ = NutzerAufgabe.objects.get_or_create(aufgabe=aufgabe, nutzer=request.user, defaults=defaults)
    return aufgabe, nutzer_aufgabe

# Holt die Kontenplan-ID aus den Aufgabendetails.
def get_kontenplan_id(aufgabe):
    return (AufgabeDetail.objects.filter(aufgabe=aufgabe)
            .values_list("kontenplan_id", flat=True).first())

# Liefert alle Buchungen des Nutzers zu einer Aufgabe (sortiert).
def get_buchungen(aufgabe, user):
    return Buchung.objects.filter(aufgabe=aufgabe, nutzer=user).order_by('buchung_id')

# Liefert die nächste Aufgabe mit höherer ID (oder None).
def get_next_aufgabe(aufgabe_id):
    return Aufgabe_neu.objects.filter(id__gt=aufgabe_id).order_by('id').first()

# Ermittelt den Namen des GuV-Kontos des Nutzers.
def get_guv_konto_name(request):
    return ermittle_guv_konto(request).name

# Liefert alle Konten außer dem GuV-Konto (sortiert nach Nummer und Name).
def get_konten_ohne_guv(guv_konto_name):
    return Konto.objects.exclude(name=guv_konto_name).order_by('kontonummer', 'name')

# Behandelt POST: legt Buchung an, verschickt ggf. Korrekturmail und leitet weiter.
def process_post(request, aufgabe, nutzer_aufgabe):
    buchung = handle_nutzer_buchung(request, aufgabe, ist_frei=False)
    if not is_buchung_korrekt(buchung, nutzer_aufgabe):
        send_korrektur_mail(request.user, nutzer_aufgabe.aufgabe, request, nutzer_aufgabe.rn_nummer)
    return redirect('frontpage')

# Gibt die letzte Buchung in der Liste zurück.
def get_letzte_buchung(buchungen):
    return buchungen.last()

# Bestimmt, ob weitere Buchung blockiert ist (falsch und keine Korrekturbuchung).
def is_block_buchung(letzte_buchung):
    if not letzte_buchung:
        return False
    ist_falsch = letzte_buchung.status != 'korrekt'
    ist_korrekturbuchung = letzte_buchung.korrekturbuchung
    return ist_falsch and not ist_korrekturbuchung

# Baut die Statusliste für alle Buchungen inkl. Parsing der Felder.
def build_buchung_status(buchungen, nutzer_aufgabe, letzte_buchung, block_buchung):
    status = []
    for b in buchungen:
        status.append({
            'buchung': b,
            'korrekt': is_buchung_korrekt(b, nutzer_aufgabe),
            'is_letzte_falsche': b == letzte_buchung and block_buchung,
            'soll_konten_liste': safe_parse(b.antwort_konten_soll),
            'haben_konten_liste': safe_parse(b.antwort_konten_haben),
            'soll_betraege_liste': safe_parse(b.antwort_betrag_soll),
            'haben_betraege_liste': safe_parse(b.antwort_betrag_haben),
            'original_soll_konten': safe_parse(b.original_konten_soll),
            'original_haben_konten': safe_parse(b.original_konten_haben),
        })
    return status

# Liefert den Template-Pfad passend zum Rechnungstyp.
def get_rechnungs_template(typ):
    mapping = {
        'eingehend': 'posts/rechnungen/rechnung_eingehend.html',
        'ausgehend': 'posts/rechnungen/rechnung_ausgehend.html',
        'intern': 'posts/rechnungen/rechnung_intern.html',
        'non': 'posts/rechnungen/rechnung_intern.html'
    }
    return mapping.get(typ, 'posts/rechnungen/rechnung_basis.html')

# Prüft, ob Nutzer Lehrkraft oder Superuser ist (1/0).
def is_lehrkraft_flag(user):
    return 1 if user.role == 'teacher' or user.is_superuser else 0


# Holt individuelle Feedbacktexte der letzten Buchung.
def get_feedback_individuell(letzte_buchung):
    if not letzte_buchung:
        return []
    ids = letzte_buchung.feedback_bereiche_json or []
    return list(Feedbackbereich.objects.filter(id__in=ids).values_list('feedback_text', flat=True))

# Berechnet Rechnungsbeträge (brutto, netto, Steuer, Rabattbetrag).
def compute_rechnungswerte(nutzer_aufgabe, mwst=Decimal("1.19"), r_faktor=Decimal("0.95")):
    brutto = Decimal(round(sum(nutzer_aufgabe.haben_betraege), 2))
    netto = round(brutto / mwst, 2)
    steuer = brutto - netto
    rabatt_betrag = round(((brutto / mwst) / r_faktor) * mwst, 2)
    return brutto, netto, steuer, rabatt_betrag


# Erstellt eine ID→Name-Lookup-Tabelle für Konten eines Kontenplans.
def build_konten_id_to_name(kontenplan_id):
    qs = Konto.objects.filter(kontenplan=kontenplan_id)
    return {k.id: k.name for k in qs}

# Baut Grundkontext mit Template, Stammdaten und Summen.
def build_base_context(aufgabe, nutzer_aufgabe, rechnungs_template, feedback, is_lehrkraft,
                       rechnungswerte, konten, block_buchung, id_to_name, kontenplan_id):
    brutto, netto, steuer, rabatt = rechnungswerte
    return {
        'rechnungs_template': rechnungs_template,
        'rechnungsnummer': nutzer_aufgabe.rn_nummer,
        'feedbackbereich': feedback,
        'is_lehrkraft': is_lehrkraft,
        'datum': nutzer_aufgabe.erstellt_am,
        'unternehmen_name': aufgabe.unternehmen_kategorie.anzeigename,
        'hat_leistungszeitraum': aufgabe.hat_leistungszeitraum,
        'betrag_steuer': steuer,
        'betrag_netto': netto,
        'eigene_ansicht': aufgabe.eigene_ansicht,
        'leistungszeitraum_anfang': nutzer_aufgabe.leistungszeitraum_anfang,
        'leistungszeitraum_ende': nutzer_aufgabe.leistungszeitraum_ende,
        'beschreibung': aufgabe.beschreibung,
        'rechnungsbetrag': brutto,
        'rabatt_betrag': rabatt,
        'zahlweise': aufgabe.zahlweise,
        'verabschiedung': aufgabe.verabschiedung,
        'kontakt': aufgabe.kontakt,
        'umsatzsteuerfrei': aufgabe.umsatzsteuerfrei,
        'konten': konten,
        'block_buchung': block_buchung,
        'absender': nutzer_aufgabe.absender,
        'konten_namen': id_to_name,
        'kontenplan_id': kontenplan_id,
    }

# Ergänzt Kontext um Anzeige-/Navigationsinfos.
def extend_context_with_meta(context, aufgabe, nutzer_aufgabe, buchungen, buchung_status, next_aufgabe):
    context.update({
        'rechnungstyp': aufgabe.get_rechnungstyp_display(),
        'aufgabe': aufgabe,
        'nutzer_aufgabe': nutzer_aufgabe,
        'next_aufgabe': next_aufgabe,
        'buchungen': buchungen,
        'buchung_status': buchung_status,
    })
    return context

# Fügt nutzergruppenbasierte Flag (ungerade Gruppe) hinzu.
def add_nutzergruppen_flag(request, context):
    gruppe = getattr(request.user, "nutzergruppe", 0) or 0
    context["nutzergruppe"] = (gruppe % 2 == 1)
    return context

# Orchestriert alle Teilschritte zur Kontext-Erstellung.
def assemble_context(request, aufgabe, nutzer_aufgabe, kontenplan_id, buchungen, next_aufgabe, konten):
    letzte = get_letzte_buchung(buchungen)
    block = is_block_buchung(letzte)
    status = build_buchung_status(buchungen, nutzer_aufgabe, letzte, block)
    tpl = get_rechnungs_template(aufgabe.rechnungstyp)
    feedback = get_feedback_individuell(letzte)
    rechnungswerte = compute_rechnungswerte(nutzer_aufgabe)
    id_to_name = build_konten_id_to_name(kontenplan_id)
    base = build_base_context(aufgabe, nutzer_aufgabe, tpl, feedback, is_lehrkraft_flag(request.user),
                              rechnungswerte, konten, block, id_to_name, kontenplan_id)
    meta = extend_context_with_meta(base, aufgabe, nutzer_aufgabe, buchungen, status, next_aufgabe)
    return add_nutzergruppen_flag(request, meta)

# Haupt-View: Koordiniert Datenbeschaffung, ggf. POST-Verarbeitung und Rendern.
@login_required
def rechnung_detail_view(request, aufgabe_id):
    aufgabe, nutzer_aufgabe = get_aufgabe_und_nutzeraufgabe(request, aufgabe_id)
    if request.method == 'POST':
        return process_post(request, aufgabe, nutzer_aufgabe)
    kontenplan_id = get_kontenplan_id(aufgabe)
    buchungen = get_buchungen(aufgabe, request.user)
    next_aufgabe = get_next_aufgabe(aufgabe_id)
    guv_name = get_guv_konto_name(request)
    konten = get_konten_ohne_guv(guv_name)
    context = assemble_context(request, aufgabe, nutzer_aufgabe, kontenplan_id, buchungen, next_aufgabe, konten)
    return render(request, 'posts/rechnung.html', context)