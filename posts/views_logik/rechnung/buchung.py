# -*- coding: utf-8 -*-
# Kurzerklärung: Diese Datei zerlegt die Logik in kleine, fokussierte Hilfsfunktionen (<10 Zeilen) und behält alle Funktionen bei.

from posts.views_logik.bibliotheken import _
from posts.views_logik.bibliotheken import *
from posts.views_logik.utils import *
from posts.views import erlaubte_konten, ermittle_feedbackbereich_ids, ollama_threading

'''
Hier steht die Logik, um die Buchungen im Backend zu speichern und zu prüfen, ob diese richtig sind. Es wird dabei evaluiert, ob die Beträge/Konten oder beides richtig bzw. falsch sind. 
Darüber hinaus wird hier die Funktionalität abgewickelt, dass Konten auf bestimmten Bilanzpositionen abgeschlossen werden. Sprich, Konto A hat Kontonummer 100, Konto B hat Kontonummer 110:  
Folgender Buchungssatz: Konto B an Bank --> Hier wird im Hauptbuch nun Konto A angezeigt. Es wird also auf das verwiesene Bilanzierungskonto gebucht, welches vorher bei den Konten entsprechenden referenziert wurde.
Konto B wird also immer auf Konto A abgeschlossen, aber beide Konten gelten auch als richtig für den Buchungssatz (Also A an Bank und B an Bank wäre korrekt).
Zuletzt wird hier ebenfalls die Freie Buchung abgewickelt, also das Aufstellen eines Buchungssatzes ohne Referenz zu einer Aufgabe. Diese werden bei der GuV/Bilanz nicht angezeigt und sind im Hauptbuch entsprechend markiert. 
Diese Buchungen sind nicht umkehrbar. 

'''

# Liest die eingegebenen Konten- und Betragslisten aus dem POST-Request aus.
def parse_post_arrays(request):
    return (
        request.POST.getlist('soll_konto[]'),
        request.POST.getlist('haben_konto[]'),
        request.POST.getlist('soll_betrag[]'),
        request.POST.getlist('haben_betrag[]'),
    )

# Ersetzt Konten-IDs durch Konten der gleichen Bilanzposition mit gesetzter Kontonummer.
def ersetze_konto_durch_bilanzpositionskonto(konto_ids):
    neue_ids = []
    for konto_id in konto_ids:
        try:
            k = Konto.objects.get(id=konto_id)
            ersatz = Konto.objects.filter(
                bilanzposition_nummer=k.bilanzposition_nummer,
                kontonummer__isnull=False,
                kontenplan=k.kontenplan
            ).first()
            neue_ids.append(str(ersatz.id) if ersatz else konto_id)
        except Konto.DoesNotExist:
            neue_ids.append(konto_id)
    return neue_ids

# Bestimmt Status ('offen'/'bearbeitet') und Versuchsnummer.
def determine_status_und_versuch(ist_frei, aufgabe, user):
    if ist_frei:
        return 'offen', 0
    last = Buchung.objects.filter(aufgabe=aufgabe, nutzer=user).order_by('-versuch').first()
    return 'bearbeitet', (last.versuch + 1) if last else 1

# Erzeugt eine Buchung mit allen relevanten JSON-Feldern.
def create_buchung(aufgabe, user, repl_soll, repl_haben, soll_b, haben_b, orig_soll, orig_haben, status, versuch):
    return Buchung.objects.create(
        aufgabe=aufgabe, nutzer=user,
        antwort_konten_soll=json.dumps(repl_soll),
        antwort_konten_haben=json.dumps(repl_haben),
        antwort_betrag_soll=json.dumps(soll_b),
        antwort_betrag_haben=json.dumps(haben_b),
        original_konten_soll=json.dumps(orig_soll),
        original_konten_haben=json.dumps(orig_haben),
        status=status, versuch=versuch
    )

# Lädt die Nutzeraufgabe passend zur Aufgabe und zum Nutzer.
def get_nutzer_aufgabe(aufgabe, user):
    return NutzerAufgabe.objects.get(aufgabe=aufgabe, nutzer=user)

# Extrahiert Nutzerantworten (Konten/Beträge) aus der Buchung.
def get_nutzer_lists_from_buchung(buchung):
    s_k = json.loads(buchung.antwort_konten_soll)
    h_k = json.loads(buchung.antwort_konten_haben)
    s_b = [round(float(x), 2) for x in json.loads(buchung.antwort_betrag_soll)]
    h_b = [round(float(x), 2) for x in json.loads(buchung.antwort_betrag_haben)]
    return s_k, h_k, s_b, h_b

# Extrahiert erwartete Soll-/Haben-Konten und -Beträge aus NutzerAufgabe.
def get_aufgabe_expected_lists(nutzer_aufgabe):
    s_k = nutzer_aufgabe.soll_konten
    h_k = nutzer_aufgabe.haben_konten
    s_b = [round(float(b), 2) for b in nutzer_aufgabe.soll_betraege]
    h_b = [round(float(b), 2) for b in nutzer_aufgabe.haben_betraege]
    return s_k, h_k, s_b, h_b

# Ermittelt den Konto-Fehlerstatus (0=ok, 1=Soll falsch, 2=Haben falsch, 3=beides falsch).
def compute_konto_status(n_soll, n_haben, erlaubte_soll, erlaubte_haben):
    s_ok = set(n_soll).issubset(erlaubte_soll)
    h_ok = set(n_haben).issubset(erlaubte_haben)
    if not s_ok and not h_ok:
        return 3
    if not s_ok:
        return 1
    if not h_ok:
        return 2
    return 0

# Ermittelt den Betrag-Fehlerstatus (0=ok, 1=Soll falsch, 2=Haben falsch, 3=beides falsch).
def compute_betrag_status(n_soll_b, n_haben_b, a_soll_b, a_haben_b):
    s_ok = sum(n_soll_b) == sum(a_soll_b)
    h_ok = sum(n_haben_b) == sum(a_haben_b)
    if not s_ok and not h_ok:
        return 3
    if not s_ok:
        return 1
    if not h_ok:
        return 2
    return 0

# Prüft, ob Soll- und Habensumme der Nutzerantwort übereinstimmen (auf 2 Nachkommastellen).
def sums_equal(n_soll_b, n_haben_b):
    return round(sum(n_soll_b), 2) == round(sum(n_haben_b), 2)

# Schreibt Konto-/Betrag-Status in die Buchung und speichert sie.
def set_buchung_error_fields(buchung, konto_status, betrag_status):
    buchung.konto_korrekt = konto_status
    buchung.betrag_korrekt = betrag_status
    buchung.save()

# Ermittelt Feedback-Bereich-IDs, speichert sie in der Buchung und loggt sie.
def compute_and_save_feedback(buchung, aufgabe, nutzer_aufgabe, s_k_n, s_b_n, h_k_n, h_b_n):
    f_ids = ermittle_feedbackbereich_ids(
        aufgabe=aufgabe, nutzer_aufgabe=nutzer_aufgabe,
        soll_konten_nutzer=s_k_n, betraege_soll_nutzer=s_b_n,
        haben_konten_nutzer=h_k_n, betraege_haben_nutzer=h_b_n
    )
    buchung.feedback_bereiche_json = f_ids
    print("Feedbackbereich IDs:", f_ids)
    buchung.save(update_fields=["feedback_bereiche_json"])

# Aktualisiert Buchungs-/Aufgabenstatus je nach Korrektheit und speichert beide.
def update_statuses_and_save(buchung, nutzer_aufgabe, korrekt):
    if korrekt:
        buchung.status = "korrekt"
        nutzer_aufgabe.bearbeitungsstand = "korrekt"
    else:
        buchung.status = "bearbeitet"
        nutzer_aufgabe.bearbeitungsstand = "bearbeitet"
    buchung.save()
    nutzer_aufgabe.save()

# Startet ggf. einen Thread zur Feedback-Generierung mit Ollama.
def maybe_start_ollama_thread(buchung, nutzer_aufgabe, aufgabe):
    if (buchung.versuch == 3) and buchung.status != "korrekt":
        threading.Thread(
            target=ollama_threading,
            args=(buchung, nutzer_aufgabe, aufgabe.beschreibung, aufgabe.aufgabeninfo)
        ).start()

# Orchestriert Validierung, Feedback, Status-Updates und evtl. Ollama-Aufruf.
def process_validation_and_feedback(buchung, aufgabe, user):
    n_aufgabe = get_nutzer_aufgabe(aufgabe, user)
    s_k_n, h_k_n, s_b_n, h_b_n = get_nutzer_lists_from_buchung(buchung)
    s_k_a, h_k_a, s_b_a, h_b_a = get_aufgabe_expected_lists(n_aufgabe)
    konto_status = compute_konto_status(s_k_n, h_k_n, erlaubte_konten(s_k_a), erlaubte_konten(h_k_a))
    betrag_status = compute_betrag_status(s_b_n, h_b_n, s_b_a, h_b_a)
    set_buchung_error_fields(buchung, konto_status, betrag_status)
    compute_and_save_feedback(buchung, aufgabe, n_aufgabe, s_k_n, s_b_n, h_k_n, h_b_n)
    update_statuses_and_save(buchung, n_aufgabe, konto_status == 0 and betrag_status == 0 and sums_equal(s_b_n, h_b_n))
    maybe_start_ollama_thread(buchung, n_aufgabe, aufgabe)

# Legt eine Buchung an (mit Kontenersatz) und führt ggf. Validierung/Feedback durch.
def handle_nutzer_buchung(request, aufgabe, ist_frei):
    s_ids, h_ids, s_b, h_b = parse_post_arrays(request)
    orig_soll, orig_haben = s_ids, h_ids
    repl_soll = ersetze_konto_durch_bilanzpositionskonto(s_ids)
    repl_haben = ersetze_konto_durch_bilanzpositionskonto(h_ids)
    status, versuch = determine_status_und_versuch(ist_frei, aufgabe, request.user)
    a_ref = None if ist_frei else aufgabe
    buchung = create_buchung(a_ref, request.user, repl_soll, repl_haben, s_b, h_b, orig_soll, orig_haben, status, versuch)
    if not ist_frei:
        process_validation_and_feedback(buchung, a_ref, request.user)
    return buchung

# Prüft, ob eine Buchung vollständig korrekt ist (Konten, Beträge, Ausgleich).
def is_buchung_korrekt(buchung, nutzer_aufgabe):
    s_k_n = safe_parse(buchung.antwort_konten_soll)
    h_k_n = safe_parse(buchung.antwort_konten_haben)
    s_b_n = [round(float(b), 2) for b in safe_parse(buchung.antwort_betrag_soll)]
    h_b_n = [round(float(b), 2) for b in safe_parse(buchung.antwort_betrag_haben)]
    s_k_a = nutzer_aufgabe.soll_konten
    h_k_a = nutzer_aufgabe.haben_konten
    s_b_a = [round(float(b), 2) for b in nutzer_aufgabe.soll_betraege]
    h_b_a = [round(float(b), 2) for b in nutzer_aufgabe.haben_betraege]
    s_ok = set(s_k_n).issubset(erlaubte_konten(s_k_a))
    h_ok = set(h_k_n).issubset(erlaubte_konten(h_k_a))
    b_s_ok = sum(s_b_n) == sum(s_b_a)
    b_h_ok = sum(h_b_n) == sum(h_b_a)
    return s_ok and h_ok and b_s_ok and b_h_ok and (sum(s_b_n) == sum(h_b_n))

@login_required
def freie_buchung(request):
    user = request.user
    unternehmen = getattr(user, "unternehmen", None)
    kontenplan = getattr(unternehmen, "kontenplan", None)
    if request.user.role == 'teacher':
        kontenplan = Kontenplan.objects.get(id=1)
    if request.method == "POST":
        handle_nutzer_buchung(request, aufgabe=None, ist_frei=True)
        return redirect('frontpage')
    konten = Konto.objects.filter(kontenplan=kontenplan).order_by('kontonummer', 'name')
    context = {
        'konten': konten,
        'kontenplan_id': kontenplan.id,
        'block_buchung': False,
    }
    return render(request, 'posts/freie_buchung.html', context)