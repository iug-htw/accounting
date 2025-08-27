#Logik für die Aufgabenerstellen über das Formular. 
from posts.views_logik.bibliotheken import _
from posts.views_logik.bibliotheken import *
from posts.views_logik.utils import *

''' Logik für das Aufgabenerstellen über das Formular posts/aufgabe_erstellen/
Im Formular werden die Informationen für die Modelle Aufgabe_neu und AufgabeDetail eingegeben und an das Backend gesendet und über diese Logik gespeichert. Dabei wird für jede Aufgabe ein Objekt in Aufgabe_neu erstellt 
und für jedes einzelne Konto wird ein Eintrag in AufgabeDetail erstellt. Zusätzlich wird für jedes einzelne extra Feedback (falls ein bestimmtes Konto falsch ist oder die falsche Lösung in einem bestimmten Bereich liegen soll) 
ebenfalls im Formular übergeben und hier gespeichert (pro Feedback ein Eintrag in Feedbackbereich)

'''

#Hilfsfunktionen

#Aufgabe aus dem Formular erzeugen, Metadaten setzen, speichern, Details speichern, Erfolgsmeldung setzen und Redirect zurückgeben.
def _process_valid_form_and_redirect(request, form):
    aufgabe = form.save(commit=False)
    aufgabe.ersteller = request.user.id
    aufgabe.rechnungsnummer = f"RE-{random.randint(10000, 99999)}"
    kontenplan = form.cleaned_data['kontenplan']
    aufgabe.aufgabeninfo = form.cleaned_data.get('aufgabeninfo', '')
    aufgabe.save()
    speichere_aufgabe_details(request, aufgabe, kontenplan)
    messages.success(request, _("Aufgabe und Details erfolgreich erstellt."))
    return redirect('frontpage')

#auslesen aller verschiener Einträge für Feedbackbereich (theoretisch unendlich möglich)
def _read_feedback_lists(request, index):
    feedback_von = request.POST.getlist(f'feedback_von_{index}[]')
    feedback_bis = request.POST.getlist(f'feedback_bis_{index}[]')
    feedback_texts = request.POST.getlist(f'feedback_text_{index}[]')
    konten_id = request.POST.getlist(f'konto_feedback_id_{index}[]')
    feedback_konto_texts = request.POST.getlist(f'konto_feedback_text_{index}[]')
    return feedback_von, feedback_bis, feedback_texts, konten_id, feedback_konto_texts

def _create_feedback_bereiche_betrag(aufgabe_detail, feedback_von, feedback_bis, feedback_texts):
    for von, bis, text in zip(feedback_von, feedback_bis, feedback_texts):
        if von and bis and text:
            Feedbackbereich.objects.create(
                aufgabe_detail=aufgabe_detail,
                von_betrag=float(von),
                bis_betrag=float(bis),
                feedback_text=text,
            )

def _create_feedback_bereiche_konto(aufgabe_detail, feedback_konto_texts, konten_id):
    for text, konto in zip(feedback_konto_texts, konten_id):
        if text and konto:
            Feedbackbereich.objects.create(
                aufgabe_detail=aufgabe_detail,
                feedback_text=text,
                konto_falsch=int(konto),
            )
###############################################
# Views
@lehrkraft_required
def aufgabe_neu_erstellen(request):
    if request.method == 'POST':
        form = Aufgabe_neu_Form(request.POST, user=request.user)
        if form.is_valid():
            return _process_valid_form_and_redirect(request, form)
        else:
            messages.error(request, _("Das Formular ist nicht gültig."))
    else:
        form = Aufgabe_neu_Form(user=request.user)
    konten = Konto.objects.filter(
        Q(kontenplan__nutzer=request.user) | Q(kontenplan__nutzer__is_superuser=True)
    ).order_by("name")
    return render(request, 'posts/aufgabe_erstellen.html', {'form': form, 'konten': konten})


def speichere_aufgabe_details(request, aufgabe, kontenplan):
    konto_ids = request.POST.getlist('konto_id[]')
    soll_haben = request.POST.getlist('soll_haben[]')
    betraege = request.POST.getlist('betrag[]')
    for i in range(len(konto_ids)):
        konto = Konto.objects.get(id=konto_ids[i])
        aufgabe_detail = AufgabeDetail.objects.create(
            aufgabe=aufgabe,
            konto=konto,
            soll_haben=soll_haben[i],
            betrag=betraege[i] if i < len(betraege) else None,
            kontenplan=kontenplan,
        )
        feedback_von, feedback_bis, feedback_texts, konten_id, feedback_konto_texts = _read_feedback_lists(request, i)
        _create_feedback_bereiche_betrag(aufgabe_detail, feedback_von, feedback_bis, feedback_texts)
        _create_feedback_bereiche_konto(aufgabe_detail, feedback_konto_texts, konten_id)
