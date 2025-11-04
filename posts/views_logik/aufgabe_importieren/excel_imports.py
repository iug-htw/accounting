from posts.views_logik.bibliotheken import _
from posts.views_logik.bibliotheken import *
from posts.views_logik.utils import *

''' Logik für das Aufgabenerstellen über einen Excel-Import posts/aufgabe_import_form.html/
und
Kontenplan Import posts/konto_verwalten.html
Im wesentlichen werden hier die Daten aus den Zeilen in Excel ausgelesen und die Objekte mit ihren Attributen werden erstellt. Für die Vorlage der Excel-Dateien kann das FAQ verwendet werden. 

'''

# Liest die erste Tabelle aus der hochgeladenen Excel-Datei
def parse_excel_file(file):
    wb = load_workbook(file)
    return wb.active

# Erzeugt 3er-Gruppen (Konto, Soll/Haben, Betrag) aus einer Tabellenzeile ab Spalte 12
def iter_konto_triplets(row, start=12):
    for i in range(start, len(row), 3):
        yield row[i], row[i + 1], row[i + 2]

# Holt ein Konto entweder über Kontonummer oder Namen aus dem Kontenplan
def fetch_konto(value, kontenplan):
    try:
        num = int(value)
        return Konto.objects.filter(kontonummer=num, kontenplan=kontenplan).first()
    except (ValueError, TypeError):
        return Konto.objects.filter(name__iexact=str(value).strip(), kontenplan=kontenplan).first()

# Liest Kontoinfos aus einer Zeile und validiert, dass alle benötigten Konten existieren
def resolve_konten_from_row(row, kontenplan):
    infos = []
    for name, sh, betrag in iter_konto_triplets(row):
        if not name or not sh or betrag is None:
            break
        konto = fetch_konto(name, kontenplan)
        if not konto:
            return None
        infos.append((konto, sh.strip(), float(betrag)))
    return infos

# Prüft, ob ein Konto ein EBK-Konto ist
def is_ebk(k):
    return "EBK" in k.name.upper() or "ERÖFFNUNGSBILANZ" in k.name.upper()

# Prüft, ob ein Konto ein SBK-Konto ist
def is_sbk(k):
    return "SBK" in k.name.upper() or "SCHLUSSBILANZ" in k.name.upper()

# Wählt den Namen eines Nicht-EBK/SBK-Kontos oder liefert einen Platzhalter
def pick_other_name(konto_infos, exclude):
    for k, _, _ in konto_infos:
        if k not in exclude:
            return k.name
    return "unbekanntes Konto"

# Baut eine Beschreibung für EBK-Fälle
def beschreibung_for_ebk(anderes):
    return (f"\nAm Geschäftsjahresbeginn wurde das Anfangsvermögen erfasst, um die Buchhaltung des Unternehmens korrekt zu starten. "
            f"Erstelle die richtige Eröffnungsbilanz für das folgende Konto: \n{anderes}.")

# Baut eine Beschreibung für SBK-Fälle
def beschreibung_for_sbk(anderes):
    return (f"\nZum Geschäftsjahresende wurde die Vermögens- und Schuldenlage erfasst. "
            f"Diese Transaktion fließt in die Schlussbilanz ein und bildet die Grundlage für die Erfolgsrechnung. "
            f"Folgendes Konto wird abgeschlossen: \n{anderes}.")

# Baut eine Beschreibung für normale Geschäftsvorfälle
def beschreibung_for_normal(beschreibung):
    return (f"\nDiese Transaktion wurde im laufenden Geschäftsjahr vorgenommen und betrifft eine übliche Geschäftstätigkeit. "
            f"Verbuchen Sie diesen Geschäftsvorfall. \n{beschreibung}.\n")

# Leitet abhängig vom Kontotyp die passende Beschreibung ab
def generiere_beschreibung(konto_infos, beschreibung):
    ebk = [k for k, _, _ in konto_infos if is_ebk(k)]
    sbk = [k for k, _, _ in konto_infos if is_sbk(k)]
    anderes = pick_other_name(konto_infos, ebk + sbk)
    if ebk:
        return beschreibung_for_ebk(anderes)
    if sbk:
        return beschreibung_for_sbk(anderes)
    return beschreibung_for_normal(beschreibung)

# Baut die Formdaten aus einer Tabellenzeile
def build_form_data_from_row(row, form):
    return {'unternehmen': form.cleaned_data["unternehmen_kategorie"], 'rechnungstyp': row[1] or 'non', 'fragentyp': None, 'unterkategorie': None,
            'fragentyp_text': row[3] or '', 'mailtext': row[4] or '', 'umsatzsteuerfrei': bool(row[5]), 'hat_leistungszeitraum': bool(row[6]),
            'nutzungsdauer': int(row[7]) if row[7] else 0, 'feedback_konto_falsch': row[8] or '', 'feedback_betrag_falsch': row[9] or '',
            'zahlweise': row[10] or '', 'aufgabeninfo': row[11] or '', 'verabschiedung': 'Mit freundlichen Grüßen',
            'kontakt': 'Tel: 01234 567890\nE-Mail: info@unternehmen.de'}

# Fügt ggf. den Fragentyp anhand des Namens aus Spalte 3 hinzu
def attach_fragentyp(form_data, name):
    if not name:
        return form_data
    obj = Aufgabenkategorie.objects.filter(name=name).first()
    if obj:
        form_data['fragentyp'] = obj
    return form_data

# Baut das Daten-Dict für Aufgabe_neu.objects.create(**kwargs)
def build_aufgabe_kwargs(beschreibung_final, form_data, user):
    return {'beschreibung': beschreibung_final, 'unternehmen_kategorie': form_data['unternehmen'], 'rechnungstyp': form_data.get('rechnungstyp', 'non'),
            'fragentyp': form_data.get('fragentyp'), 'unterkategorie': form_data.get('unterkategorie'), 'fragentyp_text': form_data.get('fragentyp_text', ''),
            'mailtext': form_data.get('mailtext', ''), 'feedback_konto_falsch': form_data.get('feedback_konto_falsch', ''), 'feedback_betrag_falsch': form_data.get('feedback_betrag_falsch', ''),
            'nutzungsdauer': form_data.get('nutzungsdauer', 0), 'verabschiedung': form_data.get('verabschiedung', ''), 'kontakt': form_data.get('kontakt', ''), 'aufgabeninfo': form_data.get('aufgabeninfo', ''),
            'umsatzsteuerfrei': form_data.get('umsatzsteuerfrei', False), 'hat_leistungszeitraum': form_data.get('hat_leistungszeitraum', False), 'beschreibung_de': beschreibung_final,
            'beschreibung_en': f"This transaction was carried out in the current fiscal year and needs to be processed. {beschreibung_final}", 'zahlweise': form_data.get('zahlweise', ''),
            'rechnungsbetrag': 0, 'ersteller': user.id, 'rechnungsnummer': f"RE-{random.randint(10000, 99999)}"}

# Erzeugt die Aufgabe und gibt die Instanz zurück
def create_aufgabe_neu_from_kwargs(kwargs):
    return Aufgabe_neu.objects.create(**kwargs)

# Legt für jede Kontozeile ein AufgabeDetail an und setzt ggf. die Bilanzposition
def add_details(aufgabe, konto_infos, kontenplan):
    for konto, sh, betrag in konto_infos:
        d = AufgabeDetail.objects.create(aufgabe=aufgabe, konto=konto, soll_haben=sh, kontenplan=kontenplan, betrag=betrag)
        if konto.bilanzposition_nummer:
            d.bilanzposition = konto.bilanzposition_nummer; d.save()

# Erstellt aus einer Tabellenzeile eine Aufgabe inkl. Details
def erstelle_aufgabe_aus_zeile(beschreibung, row, konto_infos, form_data, kontenplan, user):
    beschr = generiere_beschreibung(konto_infos, beschreibung) if form_data['rechnungstyp'] == 'Keine Rechnungsansicht' else beschreibung
    kwargs = build_aufgabe_kwargs(beschr, form_data, user)
    aufgabe = create_aufgabe_neu_from_kwargs(kwargs)
    add_details(aufgabe, konto_infos, kontenplan)
    return aufgabe

# Verarbeitet eine Zeile und liefert Erfolg/Fehlschlag mit Beschreibung zurück
def process_row(zeilennr, row, kontenplan, form, user):
    beschreibung = row[0]
    data = build_form_data_from_row(row, form)
    data = attach_fragentyp(data, row[2])
    konto_infos = resolve_konten_from_row(row, kontenplan)
    if not konto_infos:
        return False, beschreibung
    erstelle_aufgabe_aus_zeile(beschreibung, row, konto_infos, data, kontenplan, user)
    return True, beschreibung

# Importiert alle Aufgaben aus dem Sheet und sammelt Erfolge/Fehler
def importiere_aufgaben_aus_excel(sheet, kontenplan, form, user):
    ok, fail = [], []
    for zeilennr, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        success, beschr = process_row(zeilennr, row, kontenplan, form, user)
        (ok if success else fail).append((zeilennr, beschr))
    return ok, fail

# Erzeugt eine vorbefüllte Import-Form
def erzeuge_standard_import_form(user):
    u = Unternehmen.objects.first(); k = Aufgabenkategorie.objects.first()
    return AufgabeImportForm(initial={'unternehmen_kategorie': u.id if u else None, 'fragentyp': k.id if k else None}, user=user)

# Zeigt Erfolg/Fehler im Django-Messages-Framework an
def handle_success_fail(request, erfolgreich, fehlgeschlagen):
    if erfolgreich:
        messages.success(request, _("%(anzahl)d Aufgaben erfolgreich importiert.") % {"anzahl": len(erfolgreich)})
    if fehlgeschlagen:
        fehlermeldung = ", ".join(f"Zeile {z} ('{b}')" for z, b in fehlgeschlagen)
        messages.error(request, _("%(anzahl)d Aufgaben konnten nicht importiert werden: %(fehler)s") % {"anzahl": len(fehlgeschlagen), "fehler": fehlermeldung})

# View: zeigt Formular an, importiert bei POST und leitet anschließend weiter
@lehrkraft_required
def aufgabe_import_form(request):
    if request.method == "POST":
        form = AufgabeImportForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            sheet = parse_excel_file(request.FILES['excel_datei']); kontenplan = form.cleaned_data['kontenplan']
            erfolgreich, fehlgeschlagen = importiere_aufgaben_aus_excel(sheet, kontenplan, form, request.user)
            handle_success_fail(request, erfolgreich, fehlgeschlagen)
            return redirect('posts:aufgaben_verwalten')
    else:
        form = erzeuge_standard_import_form(request.user)
    return render(request, 'posts/aufgabe_import_form.html', {'form': form})


# Prüft Pflichtfelder für eine Kontenzeile (Name/Kategorie dürfen nicht leer sein)
def konto_row_required_fields_ok(name, kategorie):
    return not (name is None or kategorie is None or str(name).strip() == "" or str(kategorie).strip() == "")

# Parst den Anfangsbestand und liefert (hat_bestand, betrag>0 oder None)
def parse_anfangsbestand(value):
    try:
        if value is None or str(value).strip() == "":
            return False, None
        betrag = float(value)
        return (betrag > 0), (betrag if betrag > 0 else None)
    except (TypeError, ValueError):
        return False, None

# Legt ein Konto-Objekt aus den Zeilenwerten an und gibt es zurück
def create_konto_from_row(kontenplan, nutzer, kontonummer, name, kategorie, unterkategorie, bilanzposition, steuerkonto, anfangsbestand):
    hat_bestand, betrag = parse_anfangsbestand(anfangsbestand)
    return Konto.objects.create(
        name=name, kategorie=kategorie, unterkategorie=unterkategorie, kontonummer=kontonummer,
        bilanzposition_nummer=bilanzposition, hat_anfangsbestand=hat_bestand, steuerkonto=steuerkonto,
        anfangsbestand_menge=betrag, kontenplan=kontenplan, erstellt_von=nutzer
    )

# Liest Konten aus Excel ein, erstellt sie und sammelt fehlerhafte Zeilen-Nummern
def importiere_konten_aus_excel(datei, kontenplan, nutzer):
    sheet = parse_excel_file(datei); fehler = []
    for idx, row in enumerate(sheet.iter_rows(min_row=2, max_col=7, values_only=True), start=2):
        name,kontonummer, kat, ukat, bilpos, steuer, ab = row
        if not konto_row_required_fields_ok(name, kat):
            fehler.append(idx); continue
        try:
            create_konto_from_row(kontenplan, nutzer, kontonummer, name, kat, ukat, bilpos, steuer, ab)
        except Exception:
            fehler.append(idx)
    return fehler

# Holt einen Kontenplan per ID oder wirft eine Exception
def get_kontenplan_by_id(kontenplan_id):
    return Kontenplan.objects.get(id=kontenplan_id)

# Zeigt resultierende Erfolg-/Hinweis-Messages für den Kontenimport an
def show_konten_import_result(request, fehler):
    if fehler:
        rows = ", ".join(map(str, fehler))
        messages.warning(request, _("Einige Zeilen wurden übersprungen (Reihen: %(rows)s)") % {"rows": rows})
    else:
        messages.success(request, _("Konten erfolgreich importiert."))

# View: verarbeitet den Konten-Excel-Import und leitet zur Verwaltung weiter
@lehrkraft_required
def verarbeite_excel_import(request):
    try:
        excel_datei = request.FILES.get('excel_datei'); kp_id = request.POST.get('kontenplan_id')
        kontenplan = get_kontenplan_by_id(kp_id)
        fehler = importiere_konten_aus_excel(excel_datei, kontenplan, request.user)
        show_konten_import_result(request, fehler)
    except Exception as e:
        messages.error(request, _("Fehler beim Import: %(err)s") % {"err": str(e)})
    return redirect('posts:konten_verwalten')
